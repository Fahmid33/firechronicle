"""FireChronicle — Preparation of the 2019 Analysis-Ready ML Dataset.

This module converts eligible outer-join NULL counterparts from the 2019 NASA FIRMS
Pará outer-join handoff (overlap_training_2019.parquet) into integer zero (0) under
the Data Engineer's preliminary conditional approval.

SCIENTIFIC ASSUMPTIONS & POLICY:
1. Input Scope: 2019 calendar year (Jan 1 - Dec 31, 2019) across Pará, Brazil (BR-PA).
2. Data Engineer Reconciliation: The NASA annual country archives for Brazil
   (modis_2019_Brazil.csv and viirs-snpp_2019_Brazil.csv) were completely processed
   without internal temporal gaps or missing months.
3. Outer-Join NULL Reconciliation: In an outer join of active fire detections, a cell
   present in one sensor but absent in the other indicates no active fire records were
   returned by FIRMS for that block-month-daynight cell. Under the preliminary 2019 policy,
   these eligible absent positive-detection counterparts are converted to integer zero (0).
4. Zero Meaning: An imputed zero count strictly represents ZERO RECORDED FIRMS POSITIVE
   DETECTIONS. It does NOT represent verified clear-sky observation coverage or zero physical
   fires (e.g. fire could be obscured by clouds or occur between satellite overpasses).
5. Observational Coverage: coverage_status remains 'unknown'.
6. Annual Non-Transferability: This conversion approval is strictly conditional on the 2019
   source audit and must NOT be automatically applied to other years without independent
   source reconciliation.
7. Independent NASA Archive Verification: NASA archive checksum and record-total verification
   remains unperformed.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

# Expected 10-column ML Schema
EXPECTED_COLUMNS = [
    "region_id",
    "block_id",
    "block_ix",
    "block_iy",
    "year",
    "month",
    "daynight",
    "modis_count",
    "viirs_count",
    "coverage_status",
]

# Invariants expected from 2019 NASA Pará source reconciliation
EXPECTED_TOTAL_ROWS = 4638
EXPECTED_MODIS_SUM = 33705
EXPECTED_VIIRS_SUM = 215918
EXPECTED_MODIS_NULLS = 2036
EXPECTED_VIIRS_NULLS = 118
EXPECTED_BOTH_POSITIVE = 2484


def load_and_verify_sources(
    overlap_path: str | Path,
    master_path: Optional[str | Path] = None,
    coverage_path: Optional[str | Path] = None,
    manifest_path: Optional[str | Path] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load the 2019 raw datasets and cross-verify upstream invariants.

    Parameters
    ----------
    overlap_path : str or Path
        Path to overlap_training_2019.parquet
    master_path : str or Path, optional
        Path to firechronicle_master_2019.parquet
    coverage_path : str or Path, optional
        Path to coverage_para.parquet
    manifest_path : str or Path, optional
        Path to manifest.json

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Any]]
        The loaded overlap DataFrame and verification metadata.
    """
    overlap_p = Path(overlap_path)
    if not overlap_p.exists():
        # Check candidate year subdirectories under parent or model/data/real
        candidates = [
            overlap_p.parent / "2019" / overlap_p.name,
            Path("model/data/real/2019") / overlap_p.name,
            Path("data/real/2019") / overlap_p.name,
        ]
        for c in candidates:
            if c.exists():
                overlap_p = c
                break

    if not overlap_p.exists():
        raise FileNotFoundError(f"Input overlap dataset not found: {overlap_p}")

    df_overlap = pd.read_parquet(overlap_p)
    verification: Dict[str, Any] = {
        "overlap_file": str(overlap_p.resolve()),
        "input_records": len(df_overlap),
        "checks_passed": True,
        "details": {},
    }

    # Verify column existence and order
    if list(df_overlap.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            f"Overlap dataset columns {list(df_overlap.columns)} do not match expected schema {EXPECTED_COLUMNS}"
        )

    # Verify row count
    if len(df_overlap) != EXPECTED_TOTAL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL_ROWS} rows in overlap table, found {len(df_overlap)}"
        )

    # Verify initial positive sums and nulls
    modis_null_count = int(df_overlap["modis_count"].isna().sum())
    viirs_null_count = int(df_overlap["viirs_count"].isna().sum())
    modis_sum = int(df_overlap["modis_count"].sum())
    viirs_sum = int(df_overlap["viirs_count"].sum())

    if modis_null_count != EXPECTED_MODIS_NULLS:
        raise ValueError(
            f"Expected {EXPECTED_MODIS_NULLS} missing MODIS counts, found {modis_null_count}"
        )
    if viirs_null_count != EXPECTED_VIIRS_NULLS:
        raise ValueError(
            f"Expected {EXPECTED_VIIRS_NULLS} missing VIIRS counts, found {viirs_null_count}"
        )
    if modis_sum != EXPECTED_MODIS_SUM:
        raise ValueError(
            f"Expected initial MODIS sum {EXPECTED_MODIS_SUM}, found {modis_sum}"
        )
    if viirs_sum != EXPECTED_VIIRS_SUM:
        raise ValueError(
            f"Expected initial VIIRS sum {EXPECTED_VIIRS_SUM}, found {viirs_sum}"
        )

    verification["details"]["initial_modis_nulls"] = modis_null_count
    verification["details"]["initial_viirs_nulls"] = viirs_null_count
    verification["details"]["initial_modis_sum"] = modis_sum
    verification["details"]["initial_viirs_sum"] = viirs_sum

    # Cross-verify manifest / audit if provided
    if manifest_path is not None:
        man_p = Path(manifest_path)
        if not man_p.exists():
            if (overlap_p.parent / man_p.name).exists():
                man_p = overlap_p.parent / man_p.name
            elif (overlap_p.parent / "audit_2019.json").exists():
                man_p = overlap_p.parent / "audit_2019.json"
            elif (overlap_p.parent / "manifest.json").exists():
                man_p = overlap_p.parent / "manifest.json"
        if man_p.exists():
            with open(man_p, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            verification["manifest"] = {
                "source_files": manifest_data.get("source_files", manifest_data.get("input_files", {})),
                "original_to_para_counts": manifest_data.get("original_to_para_counts", manifest_data.get("counts", {})),
                "monthly_counts": manifest_data.get("monthly_counts", {}),
            }
            # Verify counts in manifest / audit
            orig_counts = manifest_data.get("original_to_para_counts") or manifest_data.get("counts", {})
            modis_cnt = orig_counts.get("aqua_para", orig_counts.get("aqua_modis"))
            viirs_cnt = orig_counts.get("snpp_para", orig_counts.get("snpp_viirs"))
            if modis_cnt != EXPECTED_MODIS_SUM:
                raise ValueError(
                    f"Manifest aqua count ({modis_cnt}) != expected {EXPECTED_MODIS_SUM}"
                )
            if viirs_cnt != EXPECTED_VIIRS_SUM:
                raise ValueError(
                    f"Manifest viirs count ({viirs_cnt}) != expected {EXPECTED_VIIRS_SUM}"
                )

    # Cross-verify master table if provided
    if master_path is not None:
        mst_p = Path(master_path)
        if not mst_p.exists():
            if (overlap_p.parent / mst_p.name).exists():
                mst_p = overlap_p.parent / mst_p.name
        if mst_p.exists():
            df_mst = pd.read_parquet(mst_p)
            keys = ["region_id", "block_id", "year", "month", "daynight"]
            if not (df_overlap[keys] == df_mst[keys]).all().all():
                raise ValueError("Keys in overlap table and master table do not match exactly.")
            if not df_overlap["modis_count"].equals(df_mst["modis_count"]):
                raise ValueError("MODIS counts in overlap table and master table do not match.")
            if not df_overlap["viirs_count"].equals(df_mst["viirs_count"]):
                raise ValueError("VIIRS counts in overlap table and master table do not match.")
            verification["master_verified"] = True

    # Cross-verify coverage table if provided
    if coverage_path is not None:
        cov_p = Path(coverage_path)
        if not cov_p.exists():
            if (overlap_p.parent / cov_p.name).exists():
                cov_p = overlap_p.parent / cov_p.name
            elif (overlap_p.parent / "coverage_para_2019.parquet").exists():
                cov_p = overlap_p.parent / "coverage_para_2019.parquet"
            elif (overlap_p.parent / "coverage_para.parquet").exists():
                cov_p = overlap_p.parent / "coverage_para.parquet"
        if cov_p.exists():
            df_cov = pd.read_parquet(cov_p)
            # Verify that null counts correspond exactly to 'No positive record in returned FIRMS data'
            cov_aqua = df_cov[df_cov["sensor"] == "AQUA_MODIS"].set_index(
                ["region_id", "block_id", "year", "month", "daynight"]
            )
            cov_viirs = df_cov[df_cov["sensor"] == "SNPP_VIIRS"].set_index(
                ["region_id", "block_id", "year", "month", "daynight"]
            )
            overlap_idx = df_overlap.set_index(["region_id", "block_id", "year", "month", "daynight"])

            modis_null_idx = overlap_idx[overlap_idx["modis_count"].isna()].index
            viirs_null_idx = overlap_idx[overlap_idx["viirs_count"].isna()].index

            aqua_ev = cov_aqua.loc[modis_null_idx, "observation_evidence"].unique()
            viirs_ev = cov_viirs.loc[viirs_null_idx, "observation_evidence"].unique()

            expected_ev_options = {
                "No positive record in returned FIRMS data; observation coverage unverified",
                "No positive FIRMS detection for this sensor in sparse union; observation coverage unverified",
            }
            if not set(aqua_ev).issubset(expected_ev_options):
                raise ValueError(
                    f"Unexpected observation evidence for MODIS nulls: {aqua_ev}. "
                    "Cannot confirm absence of processing gap!"
                )
            if not set(viirs_ev).issubset(expected_ev_options):
                raise ValueError(
                    f"Unexpected observation evidence for VIIRS nulls: {viirs_ev}. "
                    "Cannot confirm absence of processing gap!"
                )
            verification["coverage_evidence_verified"] = True

    return df_overlap, verification


def transform_to_analysis_ready(
    df: pd.DataFrame,
    source_verification: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Transform the 2019 overlap table to analysis-ready format.

    Converts eligible outer-join NULL counterparts (absent positive-detection records
    in processed 2019 annual archive) into whole integer 0.

    Parameters
    ----------
    df : pd.DataFrame
        The loaded 10-column overlap DataFrame.
    source_verification : dict, optional
        Metadata from load_and_verify_sources.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Any]]
        The derived analysis-ready DataFrame and conversion audit metadata.
    """
    df_out = df.copy()

    # Pre-conversion audit
    initial_modis_nulls = int(df_out["modis_count"].isna().sum())
    initial_viirs_nulls = int(df_out["viirs_count"].isna().sum())
    initial_modis_sum = int(df_out["modis_count"].sum())
    initial_viirs_sum = int(df_out["viirs_count"].sum())

    # Retain masks of existing positive values to verify they remain unaltered
    orig_modis_pos_mask = df_out["modis_count"].notna()
    orig_viirs_pos_mask = df_out["viirs_count"].notna()
    orig_modis_pos_values = df_out.loc[orig_modis_pos_mask, "modis_count"].copy()
    orig_viirs_pos_values = df_out.loc[orig_viirs_pos_mask, "viirs_count"].copy()

    # Eligible outer-join NULL conversion:
    # Under preliminary 2019 policy, convert only absent positive detection cells to 0
    df_out["modis_count"] = df_out["modis_count"].fillna(0).astype("Int64")
    df_out["viirs_count"] = df_out["viirs_count"].fillna(0).astype("Int64")

    # Post-conversion audit
    final_modis_nulls = int(df_out["modis_count"].isna().sum())
    final_viirs_nulls = int(df_out["viirs_count"].isna().sum())
    final_modis_sum = int(df_out["modis_count"].sum())
    final_viirs_sum = int(df_out["viirs_count"].sum())

    # Invariant Verification
    if final_modis_nulls != 0:
        raise ValueError(f"MODIS count still contains {final_modis_nulls} null values after conversion.")
    if final_viirs_nulls != 0:
        raise ValueError(f"VIIRS count still contains {final_viirs_nulls} null values after conversion.")
    if final_modis_sum != initial_modis_sum:
        raise ValueError(
            f"MODIS detection sum changed during conversion: initial={initial_modis_sum}, final={final_modis_sum}"
        )
    if final_viirs_sum != initial_viirs_sum:
        raise ValueError(
            f"VIIRS detection sum changed during conversion: initial={initial_viirs_sum}, final={final_viirs_sum}"
        )

    # Verify no positive counts were altered
    if not (df_out.loc[orig_modis_pos_mask, "modis_count"] == orig_modis_pos_values).all():
        raise ValueError("Original positive MODIS counts were modified during transformation!")
    if not (df_out.loc[orig_viirs_pos_mask, "viirs_count"] == orig_viirs_pos_values).all():
        raise ValueError("Original positive VIIRS counts were modified during transformation!")

    # Verify non-negativity and integer types
    if (df_out["modis_count"] < 0).any():
        raise ValueError("Derived dataset contains negative MODIS counts.")
    if (df_out["viirs_count"] < 0).any():
        raise ValueError("Derived dataset contains negative VIIRS counts.")

    # Verify composite key uniqueness
    keys = ["block_id", "year", "month", "daynight"]
    if df_out.duplicated(subset=keys).any():
        raise ValueError("Derived dataset contains duplicate composite keys (block_id, year, month, daynight).")

    # Verify coverage status remains strictly 'unknown'
    if not (df_out["coverage_status"] == "unknown").all():
        raise ValueError("Coverage status must remain 'unknown' (coverage-unadjusted).")

    # Verify columns and schema contract
    if list(df_out.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"Derived columns {list(df_out.columns)} do not match schema {EXPECTED_COLUMNS}")

    # Compute sensor zero distribution on analysis-ready dataset
    modis_zero = int((df_out["modis_count"] == 0).sum())
    viirs_zero = int((df_out["viirs_count"] == 0).sum())
    both_zero = int(((df_out["modis_count"] == 0) & (df_out["viirs_count"] == 0)).sum())
    modis_zero_viirs_pos = int(((df_out["modis_count"] == 0) & (df_out["viirs_count"] > 0)).sum())
    modis_pos_viirs_zero = int(((df_out["modis_count"] > 0) & (df_out["viirs_count"] == 0)).sum())
    both_pos = int(((df_out["modis_count"] > 0) & (df_out["viirs_count"] > 0)).sum())

    audit = {
        "dataset_name": "overlap_training_2019_analysis_ready.parquet",
        "region_id": "BR-PA",
        "year": 2019,
        "record_count": len(df_out),
        "modis_nulls_converted_to_zero": initial_modis_nulls,
        "viirs_nulls_converted_to_zero": initial_viirs_nulls,
        "both_positive_records_unaltered": both_pos,
        "total_modis_detections": final_modis_sum,
        "total_viirs_detections": final_viirs_sum,
        "zero_detection_distribution": {
            "both_zero_count": both_zero,
            "modis_zero_viirs_positive_count": modis_zero_viirs_pos,
            "modis_positive_viirs_zero_count": modis_pos_viirs_zero,
            "both_positive_count": both_pos,
            "modis_zero_count": modis_zero,
            "viirs_zero_count": viirs_zero,
        },
        "invariants_passed": {
            "row_count_equals_4638": len(df_out) == EXPECTED_TOTAL_ROWS,
            "modis_nulls_converted_equals_2036": initial_modis_nulls == EXPECTED_MODIS_NULLS,
            "viirs_nulls_converted_equals_118": initial_viirs_nulls == EXPECTED_VIIRS_NULLS,
            "modis_total_equals_33705": final_modis_sum == EXPECTED_MODIS_SUM,
            "viirs_total_equals_215918": final_viirs_sum == EXPECTED_VIIRS_SUM,
            "all_positive_counts_preserved": True,
            "no_duplicate_keys": True,
            "nonnegative_whole_integers": True,
            "coverage_status_remains_unknown": True,
        },
        "source_verification": source_verification or {},
    }

    return df_out, audit


def build_full_audit_document(
    transformation_audit: Dict[str, Any],
    manifest_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a comprehensive, auditable JSON dictionary documenting the 2019 derivation."""
    return {
        "title": "FireChronicle — 2019 Analysis-Ready ML Dataset Derivation Audit",
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "region_id": "BR-PA",
        "target_sensor": "Suomi NPP VIIRS (375 m)",
        "input_sensor": "Aqua MODIS (1 km)",
        "calibration_unit": "50 km block x year x month x daynight",
        "status": "PRELIMINARY_ANALYSIS_READY",
        "scientific_assumptions": [
            "2019 NASA FIRMS annual country archives for Brazil (modis_2019_Brazil.csv and viirs-snpp_2019_Brazil.csv) were completely processed for Pará without internal temporal gaps.",
            "Absent detection records in an outer join of positive detections represent blocks where FIRMS returned zero active fire records for that sensor in that month.",
            "Converted zeros strictly represent ZERO RECORDED FIRMS POSITIVE DETECTIONS, not verified clear-sky coverage, zero physical fires, or fire absence under cloud cover.",
            "Observational coverage is unverified; coverage_status is preserved as 'unknown' across all 4,638 records.",
            "This conversion is approved conditionally for the 2019 pilot only; it does NOT automatically apply to multi-year datasets.",
            "Independent NASA archive checksum and record-total verification has not been performed.",
        ],
        "source_files_manifest": manifest_data.get("source_files", {}) if manifest_data else {},
        "transformation_metrics": {
            "total_records": transformation_audit["record_count"],
            "modis_nulls_converted": transformation_audit["modis_nulls_converted_to_zero"],
            "viirs_nulls_converted": transformation_audit["viirs_nulls_converted_to_zero"],
            "both_positive_records": transformation_audit["both_positive_records_unaltered"],
            "total_modis_detections": transformation_audit["total_modis_detections"],
            "total_viirs_detections": transformation_audit["total_viirs_detections"],
            "zero_distribution": transformation_audit["zero_detection_distribution"],
        },
        "invariants_verified": transformation_audit["invariants_passed"],
        "modeling_implications": {
            "ratio_baseline_model_0": (
                "For the 2,036 records with modis_count=0 and viirs_count>0, Model 0 (Ratio-of-Totals) "
                "strictly outputs 0.0 VIIRS-equivalent predictions. It cannot recover detection counts missed by Aqua MODIS."
            ),
            "negative_binomial_model_1": (
                "Model 1 (Negative Binomial regression with log link) estimates an intercept-based baseline "
                "rate when modis_count=0. While this produces non-zero predictions, it reflects empirical average "
                "detection rates rather than physical fire recovery."
            ),
            "multi_year_validation_status": (
                "This single-year 2019 dataset is appropriate only for preliminary feasibility checks and within-sample "
                "or geographic cross-validation exploration. Final scientific validation requires multi-year overlap data "
                "(e.g. 2012-2021) with strictly independent temporal holdouts."
            ),
        },
    }


def save_analysis_ready_dataset(
    df: pd.DataFrame,
    output_parquet_path: str | Path,
    audit_dict: Dict[str, Any],
    output_audit_path: Optional[str | Path] = None,
) -> None:
    """Save the derived analysis-ready Parquet dataset and its companion audit report."""
    out_p = Path(output_parquet_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Save Parquet with preserved types
    df.to_parquet(out_p, index=False)

    # Save JSON audit report
    if output_audit_path is not None:
        audit_p = Path(output_audit_path)
    else:
        audit_p = out_p.parent / f"{out_p.stem}_audit.json"

    with open(audit_p, "w", encoding="utf-8") as f:
        json.dump(audit_dict, f, indent=2, allow_nan=False)


def print_cli_summary(audit: Dict[str, Any], output_path: Path, audit_path: Path) -> None:
    """Print a clean summary of the transformation to stdout."""
    tm = audit["transformation_metrics"]
    zd = tm["zero_distribution"]

    print("=" * 75)
    print(" FireChronicle — 2019 Analysis-Ready Dataset Generation")
    print("=" * 75)
    print(f" [STATUS]: DERIVATION COMPLETED SUCCESSFULLY")
    print(f" Output Parquet:    {output_path}")
    print(f" Audit Report:      {audit_path}")
    print(f"\n [1] Dataset Invariants & Record Counts:")
    print(f"     Total Records:                 {tm['total_records']:,} (Expected: 4,638)")
    print(f"     MODIS Nulls Converted to Zero: {tm['modis_nulls_converted']:,} (Expected: 2,036)")
    print(f"     VIIRS Nulls Converted to Zero: {tm['viirs_nulls_converted']:,} (Expected: 118)")
    print(f"     Both Sensors Positive (>0):    {tm['both_positive_records']:,} (Expected: 2,484)")
    print(f"\n [2] Preserved Detection Count Totals:")
    print(f"     Aqua MODIS Total Detections:   {tm['total_modis_detections']:,} (Expected: 33,705)")
    print(f"     Suomi NPP VIIRS Detections:    {tm['total_viirs_detections']:,} (Expected: 215,918)")
    print(f"\n [3] Zero-Detection Distribution (Post-Conversion):")
    print(f"     Both Zero (M=0, V=0):                         {zd['both_zero_count']:,}")
    print(f"     MODIS=0, VIIRS>0 (Detection-Count Mismatch):   {zd['modis_zero_viirs_positive_count']:,} (43.9%)")
    print(f"     MODIS>0, VIIRS=0 (Detection-Count Mismatch):   {zd['modis_positive_viirs_zero_count']:,} (2.54%)")
    print(f"     Both Positive (M>0, V>0):                     {zd['both_positive_count']:,} (53.56%)")
    print(f"\n [4] Invariants Verified:")
    for k, v in audit["invariants_verified"].items():
        print(f"     * {k}: {'PASS' if v else 'FAIL'}")
    print(f"\n [?] Scientific Notices & Limitations:")
    for notice in audit["scientific_assumptions"]:
        print(f"     * {notice}")
    print("=" * 75)


def resolve_year_dataset_paths(
    year: int | str = 2019,
    base_dir: str | Path = "model/data/real",
) -> Dict[str, Path]:
    """Resolve standard input dataset paths for a given historical year folder.

    Checks model/data/real/<year>/ first, falling back to model/data/real/ if needed.
    """
    base = Path(base_dir)
    year_dir = base / str(year)
    search_dirs = [year_dir, base] if year_dir.exists() else [base]

    def _find_file(candidates: list[str]) -> Path:
        for d in search_dirs:
            for c in candidates:
                p = d / c
                if p.exists():
                    return p
        return year_dir / candidates[0]

    return {
        "year_dir": year_dir if year_dir.exists() else base,
        "overlap": _find_file([f"overlap_training_{year}.parquet", "overlap_training.parquet"]),
        "master": _find_file([f"firechronicle_master_{year}.parquet", "firechronicle_master.parquet"]),
        "coverage": _find_file([f"coverage_para_{year}.parquet", "coverage_para.parquet"]),
        "manifest": _find_file([f"audit_{year}.json", f"manifest_{year}.json", "manifest.json"]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="FireChronicle — Prepare the Analysis-Ready Parquet dataset."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2019,
        help="Target year (default: 2019)",
    )
    parser.add_argument(
        "--input-overlap",
        type=str,
        default=None,
        help="Path to raw overlap table (default: auto-resolved from model/data/real/<year>/)",
    )
    parser.add_argument(
        "--input-master",
        type=str,
        default=None,
        help="Path to master table for cross-verification",
    )
    parser.add_argument(
        "--input-coverage",
        type=str,
        default=None,
        help="Path to coverage table for evidence verification",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to source audit/manifest JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for analysis-ready Parquet (default: model/data/processed/overlap_training_<year>_analysis_ready.parquet)",
    )
    parser.add_argument(
        "--output-audit",
        type=str,
        default=None,
        help="Output path for audit JSON report (default: alongside output parquet)",
    )

    args = parser.parse_args()

    # Resolve standard paths for the selected year
    paths = resolve_year_dataset_paths(year=args.year)
    overlap_path = Path(args.input_overlap) if args.input_overlap else paths["overlap"]
    master_path = Path(args.input_master) if args.input_master else paths["master"]
    coverage_path = Path(args.input_coverage) if args.input_coverage else paths["coverage"]
    manifest_path = Path(args.manifest) if args.manifest else paths["manifest"]
    output_path = Path(args.output) if args.output else Path(f"model/data/processed/overlap_training_{args.year}_analysis_ready.parquet")

    # Load and verify sources
    df_raw, source_verif = load_and_verify_sources(
        overlap_path=overlap_path,
        master_path=master_path,
        coverage_path=coverage_path,
        manifest_path=manifest_path,
    )

    # Perform transformation
    df_analysis, trans_audit = transform_to_analysis_ready(
        df_raw,
        source_verification=source_verif,
    )

    # Build full audit document
    manifest_data = source_verif.get("manifest")
    audit_doc = build_full_audit_document(trans_audit, manifest_data=manifest_data)

    # Save results
    audit_path = Path(args.output_audit) if args.output_audit else output_path.parent / f"{output_path.stem}_audit.json"
    save_analysis_ready_dataset(df_analysis, output_path, audit_doc, audit_path)

    # Print summary
    print_cli_summary(audit_doc, output_path, audit_path)


if __name__ == "__main__":
    main()
