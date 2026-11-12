"""FireChronicle - Reproducible Model Evaluation Pipeline.

Scientific Scope:
- Region: Pará, Brazil (region_id = 'BR-PA')
- Modeling unit: 50 km block x year x month x day/night
- Input sensor: Aqua MODIS
- Target sensor: Suomi NPP VIIRS
- Objective: Reusable dual-strategy (temporal and geographic) holdout evaluation
  comparing Model 0 (Ratio-of-Totals) and Model 1 (Negative Binomial).

IMPORTANT SCIENTIFIC STATUS:
DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED
All metrics in this pipeline are computed on synthetic mock fixtures for
algorithmic development. Neither candidate model is promoted or chosen
until verified empirical NASA Pará data from Member 1 is evaluated.
"""

from pathlib import Path
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from ratio_baseline import fit_ratio, predict_ratio, _validate_count_array_or_series
from negative_binomial import fit_negative_binomial, predict_negative_binomial

CANONICAL_BLOCK_PATTERN = re.compile(r"^-?\d+_-?\d+$")
EPSILON = 1e-9


def validate_overlap_table(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Validate the canonical paired Data Engineer overlap table.

    Required Schema:
        region_id, block_id, year, month, daynight, modis_count, viirs_count, coverage_status

    Validation Rules:
    - Region must strictly be 'BR-PA' (Pará state).
    - Block ID must follow canonical 'bx_by' format (regex ^-?\\d+_-?\\d+$).
    - Year >= 2002 (Aqua MODIS era).
    - Month in 1..12.
    - Daynight in ('D', 'N').
    - Detection counts must be non-negative whole integers (no NaNs, no negatives).
    - Composite keys (block_id, year, month, daynight) must be unique.
    - Coverage eligibility: records with coverage_status == 'insufficient' are
      flagged as ineligible without converting missing data to zero.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, int]]
        Eligible rows DataFrame and auditing counts (total, eligible, excluded).
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}.")

    required_cols = {
        "region_id", "block_id", "year", "month", "daynight",
        "modis_count", "viirs_count", "coverage_status"
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Overlap table missing required column(s): {sorted(missing_cols)}")

    total_records = len(df)
    if total_records == 0:
        raise ValueError("Overlap table contains zero records.")

    # 1. Validate Region (Pará only: Rulebook Section 1, p. 2)
    invalid_regions = set(df["region_id"].unique()) - {"BR-PA"}
    if invalid_regions:
        raise ValueError(
            f"Overlap table contains invalid regions: {sorted(invalid_regions)}. "
            "Only Pará ('BR-PA') is supported."
        )

    # 2. Validate Canonical Block IDs (Rulebook Section 2, p. 3)
    for blk in df["block_id"].unique():
        if not isinstance(blk, str) or not CANONICAL_BLOCK_PATTERN.match(blk):
            raise ValueError(
                f"Invalid block_id '{blk}'. Must match canonical 'bx_by' EPSG:6933 format (e.g. '120_-50')."
            )

    # 3. Validate Date & Category Fields
    if (df["year"] < 2002).any():
        raise ValueError("Overlap table contains years prior to 2002 (Aqua MODIS launch).")

    if ((df["month"] < 1) | (df["month"] > 12)).any():
        raise ValueError("Overlap table contains month values outside 1..12.")

    invalid_dn = set(df["daynight"].str.upper().unique()) - {"D", "N"}
    if invalid_dn:
        raise ValueError(f"Overlap table contains invalid daynight values: {sorted(invalid_dn)}.")

    # 4. Composite Key Uniqueness (No Duplicate Block-Time Passes)
    dup_mask = df.duplicated(subset=["block_id", "year", "month", "daynight"], keep=False)
    if dup_mask.any():
        sample_dups = df[dup_mask][["block_id", "year", "month", "daynight"]].head(2).to_dict(orient="records")
        raise ValueError(
            f"Duplicate records found for composite key (block_id, year, month, daynight): {sample_dups}"
        )

    # 5. Check Coverage Eligibility Without Silently Imputing Zero
    if df["coverage_status"].isna().any():
        null_cov_count = int(df["coverage_status"].isna().sum())
        raise ValueError(
            f"Overlap table contains {null_cov_count} missing (NaN/null) coverage_status values. "
            "Coverage status must be explicitly specified (e.g. 'unknown', 'coverage_unadjusted', 'complete')."
        )

    coverage_series = df["coverage_status"].astype(str).str.strip().str.lower()
    valid_coverage_statuses = {
        "unknown", "coverage_unadjusted", "complete", "verified",
        "insufficient", "missing", "unsupported"
    }
    invalid_cov = set(coverage_series.unique()) - valid_coverage_statuses
    if invalid_cov:
        raise ValueError(
            f"Overlap table contains unrecognized coverage_status values: {sorted(invalid_cov)}. "
            f"Expected one of: {sorted(valid_coverage_statuses)}"
        )

    ineligible_cov_mask = coverage_series.isin(["insufficient", "missing", "unsupported"])
    unknown_mask = coverage_series.isin(["unknown", "coverage_unadjusted"])
    complete_mask = coverage_series.isin(["complete", "verified"])

    # 6. Exclude Incomplete/Missing Count Rows from Training
    # Do not silently convert missing counts to 0; preserve distinction between unobserved and zero.
    missing_modis_mask = df["modis_count"].isna()
    missing_viirs_mask = df["viirs_count"].isna()
    missing_counts_mask = missing_modis_mask | missing_viirs_mask

    exclusion_mask = ineligible_cov_mask | missing_counts_mask
    eligible_df = df[~exclusion_mask].copy()

    audit_counts = {
        "total_records": total_records,
        "eligible_records": len(eligible_df),
        "excluded_records": int(exclusion_mask.sum()),
        "excluded_ineligible_coverage": int(ineligible_cov_mask.sum()),
        "excluded_missing_modis_count": int(missing_modis_mask.sum()),
        "excluded_missing_viirs_count": int(missing_viirs_mask.sum()),
        "both_positive_complete_records": int((~missing_modis_mask & ~missing_viirs_mask).sum()),
        "unknown_coverage_records": int(unknown_mask.sum()),
        "verified_coverage_records": int(complete_mask.sum()),
        "coverage_policy": (
            "PRELIMINARY_UNADJUSTED_CALIBRATION: Records with 'unknown' or 'coverage_unadjusted' "
            "status are included for preliminary baseline calibration under Rulebook Section 3 & 4. "
            "They do NOT represent verified clear-sky observation proof or verified fire-free zeros."
        ),
        "training_conditioning_warning": (
            "SCIENTIFIC BIAS NOTICE: Training exclusively on both-positive rows (where both sensors detected fires) "
            "conditions on dual-sensor detection. It discards MODIS-positive/VIIRS-unobserved and "
            "VIIRS-positive/MODIS-unobserved rows, which can introduce selection bias and overestimate "
            "baseline multipliers. Retain and evaluate these groups separately once zero-versus-unobserved is resolved."
        ),
    }

    if len(eligible_df) == 0:
        raise ValueError("Zero records remain after filtering out insufficient coverage or missing count records.")

    # 7. Validate Nonnegative Integer Counts on Eligible Rows
    _validate_count_array_or_series(eligible_df["modis_count"], name="modis_count")
    _validate_count_array_or_series(eligible_df["viirs_count"], name="viirs_count")

    return eligible_df, audit_counts


def split_temporal_holdout(
    df: pd.DataFrame,
    train_years: List[int],
    test_years: List[int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Partition table by calendar years, guaranteeing strictly zero temporal leakage."""
    if set(train_years).intersection(set(test_years)):
        raise ValueError(
            f"Temporal split leakage: train_years {train_years} and test_years {test_years} overlap."
        )

    train_df = df[df["year"].isin(train_years)].copy()
    test_df = df[df["year"].isin(test_years)].copy()

    if len(train_df) == 0:
        raise ValueError(f"Training partition is empty for years {train_years}.")
    if len(test_df) == 0:
        raise ValueError(f"Testing partition is empty for years {test_years}.")

    # Assert zero row overlap
    assert set(train_df.index).isdisjoint(set(test_df.index)), "Row index overlap detected in temporal split."
    return train_df, test_df


def split_geographic_holdout(
    df: pd.DataFrame,
    train_blocks: List[str],
    test_blocks: List[str],
    years: Optional[List[int]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Partition table by spatial blocks, guaranteeing strictly zero geographic leakage."""
    if set(train_blocks).intersection(set(test_blocks)):
        raise ValueError(
            f"Geographic split leakage: train_blocks {train_blocks} and test_blocks {test_blocks} overlap."
        )

    base = df if years is None else df[df["year"].isin(years)]
    train_df = base[base["block_id"].isin(train_blocks)].copy()
    test_df = base[base["block_id"].isin(test_blocks)].copy()

    if len(train_df) == 0:
        raise ValueError(f"Training partition is empty for blocks {train_blocks}.")
    if len(test_df) == 0:
        raise ValueError(f"Testing partition is empty for blocks {test_blocks}.")

    # Assert zero row overlap
    assert set(train_df.index).isdisjoint(set(test_df.index)), "Row index overlap detected in geographic split."
    return train_df, test_df


def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    test_df: pd.DataFrame
) -> Dict[str, Any]:
    """Calculate statistical performance metrics with documented formulas and zero-safe handling.

    Metrics:
    - MAE: Mean Absolute Error (1/N * sum(|y - y_hat|))
    - Mean Poisson Deviance: 2/N * sum(y * ln(y / mu) - (y - mu))
    - Aggregate Count Bias %: (sum(y_hat) - sum(y)) / sum(y) * 100
    - Monthly Profile Correlation: Pearson correlation of 12-month aggregated sums
    - Peak-Month Match: True if argmax(monthly_obs) == argmax(monthly_pred)
    - Geographic Block Bias: Block-by-block bias percentage
    """
    n = len(y_true)
    if n == 0:
        raise ValueError("Cannot calculate metrics for empty predictions array.")

    # 1. Mean Absolute Error (MAE)
    mae = float(np.mean(np.abs(y_pred - y_true)))

    # 2. Aggregate Count Bias % (Strict JSON compliance: never return Inf or NaN)
    sum_true = float(np.sum(y_true))
    sum_pred = float(np.sum(y_pred))
    signed_agg_error = round(float(sum_pred - sum_true), 2)
    if sum_true > 0:
        bias_pct = round(float(((sum_pred - sum_true) / sum_true) * 100.0), 4)
        bias_reason = None
    else:
        # Undefined when observed sum is 0; do not emit float('inf') or NaN.
        bias_pct = 0.0 if sum_pred == 0.0 else None
        bias_reason = (
            "Zero total observed detections in evaluation subset; percentage bias is undefined."
            if sum_pred > 0.0 else None
        )

    # 3. Poisson Deviance (Mean & Total)
    mu = np.maximum(y_pred, EPSILON)
    term1 = np.where(y_true > 0, y_true * np.log(np.maximum(y_true, EPSILON) / mu), 0.0)
    term2 = y_true - mu
    dev_sum = float(2.0 * np.sum(term1 - term2))
    mean_poisson_deviance = round(float(dev_sum / n), 4) if np.isfinite(dev_sum) else None
    total_poisson_deviance = round(dev_sum, 4) if np.isfinite(dev_sum) else None

    # 4. Seasonal & Monthly Agreement
    temp_df = test_df.copy()
    temp_df["_obs"] = y_true
    temp_df["_pred"] = y_pred

    monthly_grp = temp_df.groupby("month")[["_obs", "_pred"]].sum()
    obs_monthly = monthly_grp["_obs"].to_numpy()
    pred_monthly = monthly_grp["_pred"].to_numpy()

    peak_obs_m = int(monthly_grp["_obs"].idxmax()) if len(monthly_grp) > 0 else 0
    peak_pred_m = int(monthly_grp["_pred"].idxmax()) if len(monthly_grp) > 0 else 0
    peak_match = bool(peak_obs_m == peak_pred_m)

    if len(obs_monthly) > 1 and np.std(obs_monthly) > 0 and np.std(pred_monthly) > 0:
        corr_val = float(np.corrcoef(obs_monthly, pred_monthly)[0, 1])
        monthly_corr = round(corr_val, 4) if np.isfinite(corr_val) else None
    else:
        monthly_corr = 1.0 if np.allclose(obs_monthly, pred_monthly) else 0.0

    # 5. Geographic Block Bias (Undefined on zero observed detections)
    block_grp = temp_df.groupby("block_id")[["_obs", "_pred"]].sum()
    block_bias_dict = {}
    for blk_id, row in block_grp.iterrows():
        b_true = float(row["_obs"])
        b_pred = float(row["_pred"])
        signed_count_error = round(float(b_pred - b_true), 2)
        if b_true > 0:
            b_bias = round(float(((b_pred - b_true) / b_true * 100.0)), 2)
            undef_reason = None
        else:
            # When b_true == 0, percentage bias is mathematically undefined.
            # Do NOT assign 0.0% bias; return null and report signed count error.
            b_bias = None
            undef_reason = (
                f"Zero observed VIIRS detections; percentage bias is undefined. "
                f"Signed count error: {signed_count_error:+0.2f} (predicted {b_pred:.1f} vs 0 observed)."
            )

        block_bias_dict[str(blk_id)] = {
            "observed_count": int(b_true),
            "predicted_count": round(b_pred, 2),
            "bias_percent": b_bias,
            "signed_count_error": signed_count_error,
            "undefined_bias_reason": undef_reason,
        }

    return {
        "n_eval_records": n,
        "sum_observed": int(sum_true),
        "sum_predicted": round(sum_pred, 2),
        "signed_aggregate_count_error": signed_agg_error,
        "mean_absolute_error": round(mae, 4),
        "aggregate_count_bias_percent": bias_pct,
        "aggregate_count_bias_undefined_reason": bias_reason,
        "mean_poisson_deviance": mean_poisson_deviance,
        "total_poisson_deviance": total_poisson_deviance,
        "poisson_deviance_scale": "mean_poisson_deviance is normalized per block-month record (2/N * sum(d_i)); total_poisson_deviance is unnormalized sum (2 * sum(d_i)).",
        "seasonal_agreement": {
            "peak_observed_month": peak_obs_m,
            "peak_predicted_month": peak_pred_m,
            "peak_month_match": peak_match,
            "monthly_profile_correlation": monthly_corr,
        },
        "geographic_block_bias": block_bias_dict,
    }


def evaluate_split(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> Dict[str, Any]:
    """Train Model 0 and Model 1 independently on train_df and evaluate on test_df."""
    # --- Model 0: Ratio-of-Totals Baseline ---
    k_baseline = fit_ratio(train_df)
    preds_ratio = predict_ratio(test_df["modis_count"], k=k_baseline)
    y_test = test_df["viirs_count"].to_numpy(dtype=np.float64)
    y_pred_ratio = np.array(preds_ratio, dtype=np.float64)

    metrics_ratio = calculate_metrics(y_test, y_pred_ratio, test_df)
    metrics_ratio["fitted_parameter_k"] = round(k_baseline, 4)

    # --- Model 1: Negative Binomial Candidate ---
    nb_model = fit_negative_binomial(train_df, reference_month=1)
    preds_nb = predict_negative_binomial(nb_model, test_df)
    y_pred_nb = np.array(preds_nb, dtype=np.float64)

    metrics_nb = calculate_metrics(y_test, y_pred_nb, test_df)
    metrics_nb["estimated_dispersion_alpha"] = round(nb_model["dispersion_alpha"], 4)
    metrics_nb["optimization_converged"] = nb_model["converged"]

    return {
        "model_0_ratio_of_totals": metrics_ratio,
        "model_1_negative_binomial": metrics_nb,
    }


def run_evaluation_pipeline(
    df: pd.DataFrame,
    output_report_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Execute the full reproducible evaluation pipeline across temporal and geographic splits.

    Parameters
    ----------
    df : pd.DataFrame
        Paired overlap table matching canonical schema.
    output_report_path : Path, optional
        Path to write the synthetic demo comparison JSON.

    Returns
    -------
    dict
        Complete evaluation report containing temporal and geographic results.
    """
    eligible_df, audit = validate_overlap_table(df)

    # Strategy A: Temporal Holdout (Train earlier years, test on final held-out year)
    years = sorted(eligible_df["year"].unique().tolist())
    if len(years) < 2:
        raise ValueError(f"Need at least 2 distinct years for temporal holdout, got: {years}")
    train_years = years[:-1]
    test_years = [years[-1]]

    temp_train, temp_test = split_temporal_holdout(eligible_df, train_years, test_years)
    temporal_results = evaluate_split(temp_train, temp_test)
    temporal_results["split_description"] = {
        "train_years": train_years,
        "test_years": test_years,
        "train_records": len(temp_train),
        "test_records": len(temp_test),
        "evaluated_blocks": sorted(temp_test["block_id"].unique().tolist()),
    }

    # Strategy B: Geographic Holdout (Train on subset of blocks, test on disjoint blocks)
    blocks = sorted(eligible_df["block_id"].unique().tolist())
    if len(blocks) < 2:
        raise ValueError(f"Need at least 2 distinct blocks for geographic holdout, got: {blocks}")

    # 2/3 blocks for training, 1/3 disjoint blocks for spatial testing
    split_idx = max(1, int(len(blocks) * 0.65))
    train_blocks = blocks[:split_idx]
    test_blocks = blocks[split_idx:]

    geo_train, geo_test = split_geographic_holdout(eligible_df, train_blocks, test_blocks, years=years)
    geographic_results = evaluate_split(geo_train, geo_test)
    geographic_results["split_description"] = {
        "train_blocks": train_blocks,
        "test_blocks": test_blocks,
        "evaluated_years": years,
        "train_records": len(geo_train),
        "test_records": len(geo_test),
    }

    report = {
        "scientific_status": "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED",
        "is_production_validation": False,
        "disclaimer": (
            "All results are computed on synthetic mock test fixtures for algorithmic pipeline testing. "
            "Neither model is promoted or chosen for production until empirical NASA Pará data is processed."
        ),
        "data_audit": audit,
        "strategy_A_temporal_holdout": temporal_results,
        "strategy_B_geographic_holdout": geographic_results,
        "model_selection_status": "NO_DECISION_MADE (Evaluation pipeline operational; awaiting empirical Pará dataset)",
    }

    if output_report_path:
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, allow_nan=False)
        print(f"Evaluation report written to: {output_report_path}")

    return report
