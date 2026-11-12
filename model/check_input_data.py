"""FireChronicle - Real-Data Intake Checker.

Validates and audits paired satellite overlap tables delivered by Member 1 (Data Engineer)
before any model fitting or evaluation. Supports both CSV and Parquet formats.

Data Engineer Input Contract (Rulebook Section 5 & 8):
- region_id: VARCHAR (must be strictly 'BR-PA')
- block_id: VARCHAR (must match canonical EPSG:6933 'bx_by' format)
- block_ix: BIGINT (optional, 50km X-index)
- block_iy: BIGINT (optional, 50km Y-index)
- year: BIGINT (>= 2002)
- month: BIGINT (1..12)
- daynight: VARCHAR ('D' or 'N')
- modis_count: BIGINT (non-negative integer)
- viirs_count: BIGINT (non-negative integer)
- coverage_status: VARCHAR (e.g. 'unknown', 'coverage_unadjusted', 'insufficient')

IMPORTANT:
This intake checker does NOT train models, does NOT select production candidates,
and does NOT modify production artifacts.
"""

import argparse
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

CANONICAL_BLOCK_PATTERN = re.compile(r"^-?\d+_-?\d+$")
REQUIRED_COLUMNS = [
    "region_id", "block_id", "year", "month", "daynight",
    "modis_count", "viirs_count", "coverage_status"
]
OPTIONAL_COLUMNS = ["block_ix", "block_iy"]
REQUIRED_NON_NULL_COLUMNS = [
    "region_id", "block_id", "year", "month", "daynight", "coverage_status"
]
COUNT_COLUMNS = ["modis_count", "viirs_count"]


def load_dataset(filepath: Union[str, Path]) -> pd.DataFrame:
    """Load dataset from CSV or Parquet file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found at: {path}")

    suffix = path.suffix.lower()
    if suffix in (".parquet", ".pq"):
        try:
            return pd.read_parquet(path)
        except Exception:
            import duckdb
            df = duckdb.read_parquet(str(path)).df()
            for col in COUNT_COLUMNS:
                if col in df.columns:
                    df[col] = df[col].astype("Int64")
            return df
    elif suffix in (".csv", ".txt"):
        return pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Expected .csv or .parquet.")


def check_overlap_dataset(
    df: pd.DataFrame,
    source_label: str = "Input Dataset",
    train_years: Optional[List[int]] = None,
    test_years: Optional[List[int]] = None,
    train_blocks: Optional[List[str]] = None,
    test_blocks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute a comprehensive intake audit on the paired overlap dataset.

    Returns an audit dictionary containing validation flags, errors, warnings,
    coverage distributions, and sensor-zero mismatch metrics.
    """
    errors: List[str] = []
    warnings: List[str] = []

    total_records = len(df)
    if total_records == 0:
        return {
            "source_label": source_label,
            "is_schema_valid": False,
            "errors": ["Dataset contains 0 rows."],
            "warnings": [],
            "record_count": 0,
        }

    # 1. Schema & Required Columns Check
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required column(s): {missing_cols}")
        return {
            "source_label": source_label,
            "is_schema_valid": False,
            "errors": errors,
            "warnings": warnings,
            "record_count": total_records,
            "missing_summary": {},
        }

    # Check for missing values across all columns (Do not silently convert to 0)
    missing_summary = {}
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            missing_summary[col] = null_count
            if col in REQUIRED_NON_NULL_COLUMNS:
                errors.append(f"Required identifier/metadata column '{col}' contains {null_count} missing (NaN/null) values.")
            elif col in COUNT_COLUMNS:
                warnings.append(
                    f"Nullable count column '{col}' contains {null_count} missing (NULL/<NA>) values. "
                    "Preserved as NULL; not converted to zero. Requires training eligibility handling."
                )

    # 2. Region Validation (Rulebook Section 1, p. 2: Pará only)
    unique_regions = df["region_id"].dropna().unique().tolist()
    invalid_regions = [r for r in unique_regions if r != "BR-PA"]
    if invalid_regions:
        errors.append(
            f"Invalid region(s) detected: {invalid_regions}. Only Pará ('BR-PA') is supported. "
            "Data Engineer must filter out non-Pará records."
        )

    # 3. Canonical Block ID Validation (Rulebook Section 2, p. 3)
    unique_blocks = df["block_id"].dropna().unique().tolist()
    malformed_blocks = [b for b in unique_blocks if not (isinstance(b, str) and CANONICAL_BLOCK_PATTERN.match(b))]
    if malformed_blocks:
        sample_bad = malformed_blocks[:5]
        errors.append(
            f"Malformed block IDs detected ({len(malformed_blocks)} unique): {sample_bad}. "
            "Must match canonical 'bx_by' format derived from EPSG:6933 50km indexes."
        )

    # 4. Optional block_ix and block_iy Consistency Check
    has_block_indexes = "block_ix" in df.columns and "block_iy" in df.columns
    block_index_mismatches = 0
    if has_block_indexes:
        ix_num = pd.to_numeric(df["block_ix"], errors="coerce")
        iy_num = pd.to_numeric(df["block_iy"], errors="coerce")
        if ix_num.isna().any() or iy_num.isna().any():
            bad_ix = int(ix_num.isna().sum())
            bad_iy = int(iy_num.isna().sum())
            errors.append(
                f"Malformed or missing values in optional block indexes: "
                f"block_ix has {bad_ix} invalid/null values, block_iy has {bad_iy} invalid/null values."
            )
        else:
            ix_series = ix_num.astype(int).astype(str)
            iy_series = iy_num.astype(int).astype(str)
            expected_ids = ix_series + "_" + iy_series
            mismatch_mask = expected_ids != df["block_id"]
            block_index_mismatches = int(mismatch_mask.sum())
            if block_index_mismatches > 0:
                sample_mismatches = df[mismatch_mask][["block_id", "block_ix", "block_iy"]].head(3).to_dict(orient="records")
                errors.append(
                    f"{block_index_mismatches} rows have block_id inconsistent with block_ix/block_iy: {sample_mismatches}"
                )

    # 5. Temporal Field Checks
    years = sorted(df["year"].dropna().unique().tolist())
    if any(y < 2002 for y in years):
        errors.append("Dataset contains years prior to 2002 (Aqua MODIS launch). Historical pre-2002 data is unsupported.")

    if 2002 in years:
        early_2002_mask = (df["year"] == 2002) & (df["month"].isin(range(1, 7)))
        if early_2002_mask.any():
            errors.append(
                f"Dataset contains {int(early_2002_mask.sum())} records from Jan-Jun 2002. "
                "Aqua MODIS public science operations began July 2002 (Rulebook Section 1 & 3: Mid-2002–2011)."
            )

    months = sorted(df["month"].dropna().unique().tolist())
    invalid_months = [m for m in months if m not in range(1, 13)]
    if invalid_months:
        errors.append(f"Invalid month values detected: {invalid_months}. Must be integers 1 to 12.")

    if len(months) < 12:
        warnings.append(
            f"Dataset covers only {len(months)} of 12 months (observed: {months}). "
            "Unobserved months cannot be evaluated by seasonal models without extrapolation assumptions."
        )

    # 6. Day/Night Categories
    dn_counts = df["daynight"].value_counts().to_dict()
    invalid_dn = [dn for dn in dn_counts if str(dn).upper() not in ("D", "N")]
    if invalid_dn:
        errors.append(f"Invalid daynight categories: {invalid_dn}. Expected strictly 'D' or 'N'.")

    # 7. Non-negative Integer Count Validation (Evaluated strictly on non-null values)
    for count_col in COUNT_COLUMNS:
        series = df[count_col]
        # Check numeric
        try:
            arr = pd.to_numeric(series, errors="raise").to_numpy()
        except (ValueError, TypeError) as e:
            errors.append(f"Column '{count_col}' contains non-numeric values: {e}")
            continue

        valid_mask = ~np.isnan(arr)
        valid_arr = arr[valid_mask]

        if len(valid_arr) > 0:
            if np.isinf(valid_arr).any():
                errors.append(f"Column '{count_col}' contains infinite values.")
            if (valid_arr < 0).any():
                errors.append(f"Column '{count_col}' contains negative detection counts.")
            if not np.all(valid_arr == np.floor(valid_arr)):
                errors.append(f"Column '{count_col}' contains fractional detection counts (must be whole integers).")

    # 8. Composite Key Uniqueness (block_id, year, month, daynight)
    key_cols = ["block_id", "year", "month", "daynight"]
    dup_mask = df.duplicated(subset=key_cols, keep=False)
    dup_count = int(dup_mask.sum())
    if dup_count > 0:
        sample_dups = df[dup_mask][key_cols].head(3).to_dict(orient="records")
        errors.append(
            f"Duplicate records found for composite key (block_id, year, month, daynight): "
            f"{dup_count} duplicate rows detected. Examples: {sample_dups}"
        )

    # 9. Coverage Status & Scientific Verification
    coverage_counts = df["coverage_status"].astype(str).str.lower().value_counts().to_dict()
    has_insufficient = coverage_counts.get("insufficient", 0)
    has_unknown = coverage_counts.get("unknown", 0) + coverage_counts.get("coverage_unadjusted", 0)

    if has_unknown > 0:
        warnings.append(
            f"Coverage Audit: {has_unknown} records marked 'unknown' or 'coverage_unadjusted'. "
            "Per Rulebook Section 3 (p. 4), 'unknown' represents coverage-unadjusted FIRMS detections without "
            "clear-sky proof. Do NOT treat 'unknown' coverage as complete or verified zero observations."
        )
    if has_insufficient > 0:
        warnings.append(
            f"{has_insufficient} records marked 'insufficient' coverage. These will be excluded "
            "from model fitting without setting counts to zero."
        )

    # 10. Sensor Detection Analysis (Paired Complete vs Single-Sensor Detections)
    modis_has_count = df["modis_count"].notna()
    viirs_has_count = df["viirs_count"].notna()
    both_complete = int((modis_has_count & viirs_has_count).sum())
    modis_missing = int((~modis_has_count & viirs_has_count).sum())
    viirs_missing = int((modis_has_count & ~viirs_has_count).sum())
    both_missing = int((~modis_has_count & ~viirs_has_count).sum())
    both_strictly_positive = int(((df["modis_count"].fillna(0) > 0) & (df["viirs_count"].fillna(0) > 0)).sum())

    paired_summary = {
        "paired_complete_records": both_complete,
        "both_sensors_positive": both_complete,
        "both_sensors_strictly_positive": both_strictly_positive,
        "modis_null_viirs_positive": modis_missing,
        "viirs_null_modis_positive": viirs_missing,
        "both_sensors_null": both_missing,
        "both_sensors_positive_pct": round((both_complete / total_records * 100.0), 2) if total_records > 0 else 0.0,
        "both_strictly_positive_pct": round((both_strictly_positive / total_records * 100.0), 2) if total_records > 0 else 0.0,
    }

    if modis_missing > 0:
        warnings.append(
            f"Sensor Detection Mismatch (Missing MODIS): {modis_missing} rows ({round(modis_missing / total_records * 100.0, 2)}%) "
            "have VIIRS positive counts but MODIS count is NULL/<NA>. These represent blocks where Aqua MODIS had no positive detections. "
            "Model 0 (Ratio-of-Totals) cannot train on NULL predictors."
        )
    if viirs_missing > 0:
        warnings.append(
            f"Sensor Detection Mismatch (Missing VIIRS): {viirs_missing} rows ({round(viirs_missing / total_records * 100.0, 2)}%) "
            "have MODIS positive counts but VIIRS count is NULL/<NA>. Calibration models cannot train without a target value."
        )

    # Zero-count analysis on valid paired records
    valid_counts_mask = modis_has_count & viirs_has_count
    m_counts = df.loc[valid_counts_mask, "modis_count"]
    v_counts = df.loc[valid_counts_mask, "viirs_count"]

    modis_zero = int((m_counts == 0).sum())
    viirs_zero = int((v_counts == 0).sum())
    both_zero = int(((m_counts == 0) & (v_counts == 0)).sum())
    modis_zero_viirs_pos = int(((m_counts == 0) & (v_counts > 0)).sum())
    modis_pos_viirs_zero = int(((m_counts > 0) & (v_counts == 0)).sum())

    sensor_zero_summary = {
        "evaluated_records": int(valid_counts_mask.sum()),
        "modis_zero_count": modis_zero,
        "viirs_zero_count": viirs_zero,
        "both_zero_count": both_zero,
        "modis_zero_viirs_positive_count": modis_zero_viirs_pos,
        "modis_positive_viirs_zero_count": modis_pos_viirs_zero,
        "modis_zero_viirs_pos_pct": round((modis_zero_viirs_pos / total_records * 100.0), 2) if total_records > 0 else 0.0,
    }

    if modis_zero_viirs_pos > 0:
        warnings.append(
            f"Sensor Detection-Count Mismatch: {modis_zero_viirs_pos} rows ({sensor_zero_summary['modis_zero_viirs_pos_pct']}%) "
            "have MODIS-zero/VIIRS-positive counts (MODIS=0, VIIRS>0). "
            "Model 0 (Ratio-of-Totals) cannot recover these counts. "
            "Note: These are sensor detection-count mismatches, NOT confirmed physical fires or proven subpixel detections."
        )

    # 11. Configurable Train/Test Holdout Verification (If provided)
    split_audit = {}
    if train_years is not None and test_years is not None:
        year_overlap = set(train_years).intersection(set(test_years))
        if year_overlap:
            errors.append(f"Configured temporal split has overlapping years: {year_overlap}")
        split_audit["temporal_split_configured"] = {
            "train_years": train_years,
            "test_years": test_years,
            "train_records": int(df["year"].isin(train_years).sum()),
            "test_records": int(df["year"].isin(test_years).sum()),
            "has_leakage": bool(year_overlap),
        }

    if train_blocks is not None and test_blocks is not None:
        block_overlap = set(train_blocks).intersection(set(test_blocks))
        if block_overlap:
            errors.append(f"Configured geographic split has overlapping blocks: {block_overlap}")
        split_audit["geographic_split_configured"] = {
            "train_blocks": train_blocks,
            "test_blocks": test_blocks,
            "train_records": int(df["block_id"].isin(train_blocks).sum()),
            "test_records": int(df["block_id"].isin(test_blocks).sum()),
            "has_leakage": bool(block_overlap),
        }

    is_valid = len(errors) == 0
    if len(errors) > 0:
        status = "FAIL"
    elif len(warnings) > 0:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    return {
        "source_label": source_label,
        "status": status,
        "is_schema_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "record_count": total_records,
        "summary": {
            "regions": unique_regions,
            "years_count": len(years),
            "years": years,
            "months_count": len(months),
            "months": months,
            "blocks_count": len(unique_blocks),
            "blocks": sorted(unique_blocks),
            "daynight_distribution": dn_counts,
            "coverage_distribution": coverage_counts,
            "has_block_indexes": has_block_indexes,
            "block_index_mismatches": block_index_mismatches,
        },
        "paired_summary": paired_summary,
        "sensor_zero_analysis": sensor_zero_summary,
        "missing_summary": missing_summary,
        "split_audit": split_audit,
    }


def print_audit_report(audit: Dict[str, Any]) -> None:
    """Print human-readable audit report to console."""
    print("=" * 75)
    print(f" FireChronicle — Real-Data Intake Audit: {audit['source_label']}")
    print("=" * 75)

    if audit.get("status") == "PASS":
        print("\n [STATUS]: PASS (SCHEMA & STRUCTURAL CHECKS PASSED)")
        print(" [CAUTION]: STATUS PASS confirms table schema, column types, and ID syntax only.")
        print(" It does NOT prove that Member 1's upstream IBGE Pará clipping, NASA sensor filtering")
        print(" (Aqua vs Terra, S-NPP vs NOAA-20), clear-sky coverage, or scientific validity were verified.")
    elif audit.get("status") == "PASS_WITH_WARNINGS":
        print("\n [STATUS]: PASS WITH WARNINGS (Schema & Structure Valid; Missing Counts or Unknown Coverage Flagged)")
        print(" [NOTICE]: Structural schema, column types, and spatial IDs are valid. Nullable count columns")
        print(" or unverified coverage are present and require explicit handling during model calibration.")
    else:
        print("\n [STATUS]: FAIL (Fatal Schema or Structural Errors Detected)")

    print(f"\n [1] Dataset Size & Dimensions:")
    print(f"     Total Records:  {audit['record_count']:,}")

    if "summary" in audit:
        s = audit["summary"]
        print(f"     Regions:        {s['regions']}")
        print(f"     Years ({s['years_count']}):      {s['years']}")
        print(f"     Months ({s['months_count']}):     {s['months']}")
        print(f"     Blocks ({s['blocks_count']}):     {s['blocks'][:8]} {'...' if s['blocks_count'] > 8 else ''}")
        print(f"     Day/Night:      {s['daynight_distribution']}")
        print(f"     Coverage:       {s['coverage_distribution']}")
        if s.get("has_block_indexes"):
            print(f"     50km Indexes:   Present (block_ix, block_iy); Mismatches = {s['block_index_mismatches']}")

    if "paired_summary" in audit:
        ps = audit["paired_summary"]
        print(f"\n [2] Sensor Paired Completeness (Data Engineer Outer-Join Handoff):")
        print(f"     Paired Complete (Non-Null Counts): {ps.get('paired_complete_records', ps.get('both_sensors_positive', 0)):,} ({ps['both_sensors_positive_pct']}%)")
        if "both_sensors_strictly_positive" in ps:
            print(f"     Both Sensors Positive (>0):        {ps['both_sensors_strictly_positive']:,} ({ps['both_strictly_positive_pct']}%)")
        print(f"     MODIS Null (<NA>), VIIRS Positive: {ps['modis_null_viirs_positive']:,}")
        print(f"     VIIRS Null (<NA>), MODIS Positive: {ps['viirs_null_modis_positive']:,}")
        print(f"     Both Sensors Null:                 {ps['both_sensors_null']:,}")

    if "sensor_zero_analysis" in audit:
        sz = audit["sensor_zero_analysis"]
        print(f"\n [3] Zero-Count Distribution (On Paired Complete Rows):")
        print(f"     Both Zero (M=0, V=0):                         {sz['both_zero_count']:,}")
        print(f"     MODIS=0, VIIRS>0 (Detection-Count Mismatch):   {sz['modis_zero_viirs_positive_count']:,} ({sz['modis_zero_viirs_pos_pct']}%)")
        print(f"     MODIS>0, VIIRS=0 (Detection-Count Mismatch):   {sz['modis_positive_viirs_zero_count']:,}")

    if audit.get("errors"):
        print(f"\n [!] FATAL ERRORS ({len(audit['errors'])}):")
        for err in audit["errors"]:
            print(f"     * {err}")

    if audit.get("warnings"):
        print(f"\n [?] WARNINGS & SCIENTIFIC NOTICES ({len(audit['warnings'])}):")
        for warn in audit["warnings"]:
            print(f"     * {warn}")

    if audit.get("split_audit"):
        print(f"\n [3] Configured Holdout Splits:")
        for name, info in audit["split_audit"].items():
            print(f"     * {name}: Train records={info['train_records']}, Test records={info['test_records']}, Leakage={info['has_leakage']}")

    print("\n" + "=" * 75)


def main():
    parser = argparse.ArgumentParser(
        description="FireChronicle Real-Data Intake Checker — Validates paired overlap tables from Member 1."
    )
    parser.add_argument("filepath", type=str, help="Path to input .csv or .parquet overlap file")
    parser.add_argument("--train-years", nargs="+", type=int, default=None, help="Configured training years")
    parser.add_argument("--test-years", nargs="+", type=int, default=None, help="Configured held-out testing years")
    parser.add_argument("--train-blocks", nargs="+", type=str, default=None, help="Configured training block IDs")
    parser.add_argument("--test-blocks", nargs="+", type=str, default=None, help="Configured held-out testing block IDs")

    args = parser.parse_args()

    try:
        df = load_dataset(args.filepath)
        audit = check_overlap_dataset(
            df,
            source_label=Path(args.filepath).name,
            train_years=args.train_years,
            test_years=args.test_years,
            train_blocks=args.train_blocks,
            test_blocks=args.test_blocks,
        )
        print_audit_report(audit)
        sys.exit(0 if audit["is_schema_valid"] else 1)
    except Exception as e:
        print(f"Intake check failed to run: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
