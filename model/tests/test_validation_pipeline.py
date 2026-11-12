"""Unit tests for the Reproducible Model Evaluation Pipeline.

Validates:
- Schema and canonical block ID verification
- Composite key uniqueness (block_id, year, month, daynight)
- Coverage eligibility without silent zero imputation
- Split independence and zero row/group leakage (temporal and geographic)
- Metric calculation formulas and zero-denominator safety
- Insufficient data failure handling
- End-to-end pipeline execution
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from validation_pipeline import (
    validate_overlap_table,
    split_temporal_holdout,
    split_geographic_holdout,
    calculate_metrics,
    evaluate_split,
    run_evaluation_pipeline,
)


@pytest.fixture
def multiblock_df():
    """Load the dedicated synthetic multiblock evaluation fixture."""
    csv_path = model_dir / "data" / "synthetic" / "synthetic_eval_multiblock_BR-PA.csv"
    assert csv_path.exists(), f"Synthetic multiblock fixture not found at {csv_path}"
    return pd.read_csv(csv_path)


# --- 1. Schema & Data Validation Tests ---

def test_validate_overlap_table_valid(multiblock_df):
    """Confirm canonical multiblock fixture passes validation cleanly."""
    eligible_df, audit = validate_overlap_table(multiblock_df)
    assert len(eligible_df) == len(multiblock_df)
    assert audit["total_records"] == 576
    assert audit["eligible_records"] == 576
    assert audit["excluded_records"] == 0


def test_validate_overlap_table_rejects_missing_cols(multiblock_df):
    """Reject table if any required column is missing."""
    bad_df = multiblock_df.drop(columns=["modis_count"])
    with pytest.raises(ValueError, match="missing required column"):
        validate_overlap_table(bad_df)


def test_validate_overlap_table_rejects_non_para(multiblock_df):
    """Reject records outside Pará ('BR-PA')."""
    bad_df = multiblock_df.copy()
    bad_df.loc[0, "region_id"] = "BR-AM"
    with pytest.raises(ValueError, match="invalid regions"):
        validate_overlap_table(bad_df)


def test_validate_overlap_table_rejects_invalid_block_id(multiblock_df):
    """Reject block IDs not matching the canonical 'bx_by' format."""
    bad_df = multiblock_df.copy()
    bad_df.loc[0, "block_id"] = "INVALID_NAME"
    with pytest.raises(ValueError, match="Must match canonical 'bx_by'"):
        validate_overlap_table(bad_df)


def test_validate_overlap_table_rejects_duplicate_composite_keys(multiblock_df):
    """Reject table with duplicate (block_id, year, month, daynight) entries."""
    dup_df = pd.concat([multiblock_df, multiblock_df.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate records found for composite key"):
        validate_overlap_table(dup_df)


def test_validate_overlap_table_coverage_eligibility(multiblock_df):
    """Insufficient coverage records are excluded without zero imputation."""
    mod_df = multiblock_df.copy()
    mod_df.loc[0:2, "coverage_status"] = "insufficient"

    eligible_df, audit = validate_overlap_table(mod_df)
    assert audit["excluded_records"] == 3
    assert audit["eligible_records"] == len(multiblock_df) - 3
    assert audit["unknown_coverage_records"] == len(multiblock_df) - 3
    assert "coverage_policy" in audit
    assert len(eligible_df) == len(multiblock_df) - 3


def test_validate_overlap_table_rejects_null_coverage(multiblock_df):
    """Never silently convert null coverage to unknown; raise ValueError."""
    bad_df = multiblock_df.copy()
    bad_df.loc[0, "coverage_status"] = None
    with pytest.raises(ValueError, match="missing .* coverage_status"):
        validate_overlap_table(bad_df)


def test_validate_overlap_table_rejects_unrecognized_coverage(multiblock_df):
    """Reject unrecognized coverage status strings."""
    bad_df = multiblock_df.copy()
    bad_df.loc[0, "coverage_status"] = "fantasy_status"
    with pytest.raises(ValueError, match="unrecognized coverage_status"):
        validate_overlap_table(bad_df)


def test_validate_overlap_table_excludes_missing_counts_with_audit(multiblock_df):
    """Missing count rows must be excluded from training without zero imputation, and reported in audit."""
    mod_df = multiblock_df.copy()
    mod_df["modis_count"] = mod_df["modis_count"].astype("Int64")
    mod_df["viirs_count"] = mod_df["viirs_count"].astype("Int64")
    mod_df.loc[0, "modis_count"] = pd.NA
    mod_df.loc[1, "viirs_count"] = pd.NA

    eligible_df, audit = validate_overlap_table(mod_df)
    assert len(eligible_df) == len(multiblock_df) - 2
    assert audit["excluded_records"] == 2
    assert audit["excluded_missing_modis_count"] == 1
    assert audit["excluded_missing_viirs_count"] == 1
    assert audit["both_positive_complete_records"] == len(multiblock_df) - 2
    assert "training_conditioning_warning" in audit


# --- 2. Split Independence & Leakage Prevention Tests ---

def test_temporal_split_independence_and_no_leakage(multiblock_df):
    """Verify temporal split has disjoint years and zero row leakage."""
    train_df, test_df = split_temporal_holdout(multiblock_df, train_years=[2017, 2018, 2019], test_years=[2020])

    assert set(train_df["year"].unique()) == {2017, 2018, 2019}
    assert set(test_df["year"].unique()) == {2020}
    assert set(train_df["year"]).isdisjoint(set(test_df["year"]))
    assert set(train_df.index).isdisjoint(set(test_df.index))


def test_temporal_split_rejects_overlapping_years(multiblock_df):
    """Reject temporal split when train and test years overlap."""
    with pytest.raises(ValueError, match="Temporal split leakage"):
        split_temporal_holdout(multiblock_df, train_years=[2018, 2019], test_years=[2019, 2020])


def test_geographic_split_independence_and_no_leakage(multiblock_df):
    """Verify geographic split has disjoint blocks and zero row leakage."""
    train_blks = ["120_-50", "121_-50", "120_-51", "121_-51"]
    test_blks = ["122_-50", "122_-51"]

    train_df, test_df = split_geographic_holdout(multiblock_df, train_blocks=train_blks, test_blocks=test_blks)

    assert set(train_df["block_id"].unique()) == set(train_blks)
    assert set(test_df["block_id"].unique()) == set(test_blks)
    assert set(train_df["block_id"]).isdisjoint(set(test_df["block_id"]))
    assert set(train_df.index).isdisjoint(set(test_df.index))


def test_geographic_split_rejects_overlapping_blocks(multiblock_df):
    """Reject geographic split when train and test blocks overlap."""
    with pytest.raises(ValueError, match="Geographic split leakage"):
        split_geographic_holdout(multiblock_df, train_blocks=["120_-50"], test_blocks=["120_-50", "121_-50"])


# --- 3. Metric Calculations & Zero Safety ---

def test_calculate_metrics_exact_deterministic(multiblock_df):
    """Verify metrics calculation on known exact values."""
    sub_df = multiblock_df.head(4).copy()
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 35.0, 35.0])

    metrics = calculate_metrics(y_true, y_pred, sub_df)
    assert metrics["mean_absolute_error"] == pytest.approx(3.5, rel=1e-4)
    assert metrics["sum_observed"] == 100
    assert metrics["sum_predicted"] == 100.0
    assert metrics["aggregate_count_bias_percent"] == pytest.approx(0.0, abs=1e-4)
    assert metrics["mean_poisson_deviance"] >= 0.0


def test_calculate_metrics_zero_denominator_safe(multiblock_df):
    """Verify zero observed counts do not trigger division by zero or NaN/Inf."""
    sub_df = multiblock_df.head(2).copy()
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([0.0, 0.0])

    metrics = calculate_metrics(y_true, y_pred, sub_df)
    assert metrics["aggregate_count_bias_percent"] == 0.0
    assert metrics["mean_absolute_error"] == 0.0
    assert metrics["signed_aggregate_count_error"] == 0.0

    # Non-zero prediction with zero observation must return None for bias_pct (not float('inf'))
    y_pred_positive = np.array([10.0, 20.0])
    metrics_pos = calculate_metrics(y_true, y_pred_positive, sub_df)
    assert metrics_pos["aggregate_count_bias_percent"] is None
    assert metrics_pos["aggregate_count_bias_undefined_reason"] is not None
    assert metrics_pos["signed_aggregate_count_error"] == 30.0


def test_zero_observed_block_bias_returns_null_and_signed_error(multiblock_df):
    """When a block has 0 observed VIIRS fires, percentage bias must be None, not 0.0%."""
    sub_df = multiblock_df.head(2).copy()
    sub_df["block_id"] = ["120_-50", "120_-50"]
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([25.0, 15.0])

    metrics = calculate_metrics(y_true, y_pred, sub_df)
    blk_bias = metrics["geographic_block_bias"]["120_-50"]

    assert blk_bias["observed_count"] == 0
    assert blk_bias["predicted_count"] == 40.0
    assert blk_bias["bias_percent"] is None
    assert blk_bias["signed_count_error"] == 40.0
    assert "undefined" in blk_bias["undefined_bias_reason"].lower()


def test_deviance_mean_and_total_both_reported(multiblock_df):
    """Both normalized mean deviance and unnormalized total deviance must be reported."""
    sub_df = multiblock_df.head(4).copy()
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 35.0, 35.0])

    metrics = calculate_metrics(y_true, y_pred, sub_df)
    assert "mean_poisson_deviance" in metrics
    assert "total_poisson_deviance" in metrics
    assert metrics["total_poisson_deviance"] == pytest.approx(metrics["mean_poisson_deviance"] * 4, rel=1e-3)


# --- 4. Pipeline Execution & Insufficient Data Handling ---

def test_insufficient_data_failures(multiblock_df):
    """Pipeline must raise clear error if years or blocks are insufficient for holdouts."""
    one_year_df = multiblock_df[multiblock_df["year"] == 2018].copy()
    with pytest.raises(ValueError, match="Need at least 2 distinct years"):
        run_evaluation_pipeline(one_year_df)

    one_block_df = multiblock_df[multiblock_df["block_id"] == "120_-50"].copy()
    with pytest.raises(ValueError, match="Need at least 2 distinct blocks"):
        run_evaluation_pipeline(one_block_df)


def test_full_evaluation_pipeline_execution(multiblock_df, tmp_path):
    """Execute end-to-end pipeline and verify both strategies and models evaluate with strict JSON export."""
    out_file = tmp_path / "test_comparison.json"
    report = run_evaluation_pipeline(multiblock_df, output_report_path=out_file)

    assert out_file.exists()
    # Confirm JSON has no NaN or Infinity by loading strictly
    import json
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["scientific_status"] == "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED"
    assert "strategy_A_temporal_holdout" in report
    assert "strategy_B_geographic_holdout" in report

    # Check both Model 0 and Model 1 were evaluated
    for strat in ("strategy_A_temporal_holdout", "strategy_B_geographic_holdout"):
        assert "model_0_ratio_of_totals" in report[strat]
        assert "model_1_negative_binomial" in report[strat]
        m0 = report[strat]["model_0_ratio_of_totals"]
        m1 = report[strat]["model_1_negative_binomial"]
        assert m0["mean_absolute_error"] > 0
        assert m1["mean_absolute_error"] > 0
        assert m0["mean_poisson_deviance"] > 0
        assert m1["mean_poisson_deviance"] > 0
        assert "monthly_profile_correlation" in m0["seasonal_agreement"]
        assert "monthly_profile_correlation" in m1["seasonal_agreement"]

    # Verify no winning model decision was made
    assert "NO_DECISION_MADE" in report["model_selection_status"]
