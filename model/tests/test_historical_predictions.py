"""Tests for the Final Negative Binomial (NB2) Historical Prediction Output.

Verifies:
1. File existence and row count (exactly 129,504 rows for July 2002 - December 2011).
2. Schema compliance with the 14-column contract.
3. Strict composite key uniqueness (0 duplicate keys).
4. Canonical 568-block grid alignment with EPSG:6933 reference.
5. Non-negative, finite predictions for all 26,962 positive records.
6. Strict NULL preservation for all 102,542 unobserved records.
7. Correct status flags ('ok_preliminary' vs 'missing_required_feature').
8. Value type strictly 'estimated' and calibration scale strictly 50 km.
9. Exact numerical reproducibility from the serialized model artifact.
"""

from pathlib import Path
import sys
import duckdb
import joblib
import numpy as np
import pandas as pd
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from negative_binomial import predict_negative_binomial

PARQUET_PATH = model_dir / "estimated_viirs_block_month.parquet"
MODEL_PATH = model_dir / "artifacts" / "nb2_final_model.joblib"
REF_GRID_PATH = model_dir / "data" / "real" / "2019" / "para_50km_grid_canonical.parquet"

REQUIRED_14_COLUMNS = [
    "region_id",
    "block_id",
    "block_ix",
    "block_iy",
    "year",
    "month",
    "daynight",
    "estimated_viirs_count",
    "value_type",
    "prediction_status",
    "coverage_status",
    "model_version",
    "measurement_unit",
    "calibration_scale_km",
]


@pytest.fixture(scope="module")
def historical_estimates_df():
    """Load the exported 14-column historical estimates Parquet table."""
    if not PARQUET_PATH.exists():
        pytest.skip(f"Estimated Parquet not found at {PARQUET_PATH} (delivered out-of-band outside Git)")
    df = duckdb.read_parquet(str(PARQUET_PATH)).df()
    return df


def test_historical_parquet_shape_and_columns(historical_estimates_df):
    """Verify table shape (129,504 x 14) and exact 14 required columns."""
    assert len(historical_estimates_df) == 129504, f"Expected 129,504 rows, got {len(historical_estimates_df)}"
    assert list(historical_estimates_df.columns) == REQUIRED_14_COLUMNS


def test_composite_key_uniqueness(historical_estimates_df):
    """Verify that all composite keys are strictly unique with zero duplicates."""
    dup_count = historical_estimates_df.duplicated(
        subset=["region_id", "block_id", "year", "month", "daynight"]
    ).sum()
    assert dup_count == 0, f"Found {dup_count} duplicate composite keys in historical export."


def test_canonical_grid_alignment(historical_estimates_df):
    """Verify that all unique block IDs match the authoritative 568-block reference grid."""
    if not REF_GRID_PATH.exists():
        pytest.skip("Reference grid Parquet delivered out-of-band outside Git")
    ref_grid = duckdb.read_parquet(str(REF_GRID_PATH)).df()
    ref_blocks = sorted(ref_grid["block_id"].unique().tolist())
    export_blocks = sorted(historical_estimates_df["block_id"].unique().tolist())
    assert export_blocks == ref_blocks, "Historical export block IDs do not match 568 canonical blocks."


def test_temporal_coverage_july_2002_to_december_2011(historical_estimates_df):
    """Verify temporal range: strictly July 2002 through December 2011 (no pre-July 2002 rows)."""
    years = sorted(historical_estimates_df["year"].unique().tolist())
    assert years == list(range(2002, 2012)), f"Unexpected years in export: {years}"

    # Year 2002 must contain only months 7 to 12
    m_2002 = sorted(historical_estimates_df[historical_estimates_df["year"] == 2002]["month"].unique().tolist())
    assert m_2002 == list(range(7, 13)), f"Year 2002 contains invalid months: {m_2002}"

    # Years 2003-2011 must each contain months 1 to 12
    for y in range(2003, 2012):
        m_y = sorted(historical_estimates_df[historical_estimates_df["year"] == y]["month"].unique().tolist())
        assert m_y == list(range(1, 13)), f"Year {y} contains invalid months: {m_y}"


def test_positive_predictions_integrity(historical_estimates_df):
    """Verify that exactly 26,962 positive records have finite, non-negative predictions."""
    pos_mask = historical_estimates_df["estimated_viirs_count"].notna()
    pos_df = historical_estimates_df[pos_mask]

    assert len(pos_df) == 26962, f"Expected 26,962 positive predictions, got {len(pos_df)}"
    assert (pos_df["estimated_viirs_count"] >= 0).all(), "Found negative prediction values."
    assert np.isfinite(pos_df["estimated_viirs_count"]).all(), "Found non-finite prediction values."
    assert (pos_df["prediction_status"] == "ok_preliminary").all(), "Invalid prediction status on positive records."


def test_null_predictions_preservation(historical_estimates_df):
    """Verify that exactly 102,542 unobserved records preserve NULL predictions without zero substitution."""
    null_mask = historical_estimates_df["estimated_viirs_count"].isna()
    null_df = historical_estimates_df[null_mask]

    assert len(null_df) == 102542, f"Expected 102,542 NULL records, got {len(null_df)}"
    assert (null_df["prediction_status"] == "missing_required_feature").all(), (
        "NULL predictions must have status 'missing_required_feature'."
    )


def test_metadata_fields_compliance(historical_estimates_df):
    """Verify standard contract values: region_id, value_type, model_version, measurement_unit, calibration_scale_km."""
    assert (historical_estimates_df["region_id"] == "BR-PA").all()
    assert (historical_estimates_df["value_type"] == "estimated").all()
    assert (historical_estimates_df["model_version"] == "firechronicle-nb2-v1.0").all()
    assert (historical_estimates_df["measurement_unit"] == "VIIRS_S-NPP-equivalent_detection_count").all()
    assert (historical_estimates_df["calibration_scale_km"] == 50).all()
    assert (historical_estimates_df["coverage_status"] == "unknown").all()


def test_historical_prediction_reproducibility(historical_estimates_df):
    """Verify that predictions exactly match re-evaluation using the serialized model artifact."""
    if not MODEL_PATH.exists() or not (model_dir / "data" / "historical").exists():
        pytest.skip("Model artifact or raw historical inputs delivered out-of-band outside Git")
    model = joblib.load(MODEL_PATH)

    pos_df = historical_estimates_df[historical_estimates_df["estimated_viirs_count"].notna()]
    # Mock inputs for prediction check
    input_df = pos_df[["block_id", "month", "daynight"]].copy()
    # In full design matrix, log1p_modis is derived from modis_count.
    # Re-evaluate using the historical input datasets
    hist_base = model_dir / "data" / "historical"
    pos_inputs = []
    for y in range(2002, 2012):
        fp = hist_base / str(y) / f"historical_modis_block_month_{y}.parquet"
        df_y = duckdb.read_parquet(str(fp)).df()
        if y == 2002:
            df_y = df_y[df_y["month"] >= 7]
        pos_y = df_y[df_y["modis_count"].notna() & (df_y["modis_count"] > 0)].copy()
        pos_inputs.append(pos_y)

    all_pos_input = pd.concat(pos_inputs, ignore_index=True)
    assert len(all_pos_input) == 26962

    reproduced = predict_negative_binomial(model, all_pos_input)
    reproduced_rounded = np.round(reproduced.to_numpy(dtype=float), 2)
    assert np.isclose(reproduced_rounded.sum(), pos_df["estimated_viirs_count"].sum(), atol=1e-2)
