"""Unit tests for the FireChronicle Ratio-of-Totals Baseline Model.

Tests cover:
- Correct multiplier calculation (k = sum(viirs) / sum(modis))
- Predictions across scalar, list, numpy array, and pandas Series inputs
- Zero MODIS input producing exactly 0.0
- Rejection of invalid data (missing, negative, infinite, fractional, non-numeric)
- Rejection of zero MODIS denominator in fit_ratio
"""

import sys
from pathlib import Path

# Ensure model/ directory is in sys.path regardless of current working directory
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

import numpy as np
import pandas as pd
import pytest

from ratio_baseline import fit_ratio, predict_ratio


# --- 1. Multiplier (k) Calculation Tests ---

def test_fit_ratio_multiplier_calculation():
    """Verify k is computed as sum(viirs_count) / sum(modis_count) on training rows."""
    df = pd.DataFrame({
        "region_id": ["BR-PA", "BR-PA", "BR-PA"],
        "modis_count": [10, 20, 70],      # Sum = 100
        "viirs_count": [32, 64, 224],     # Sum = 320
    })
    k = fit_ratio(df)
    assert isinstance(k, float)
    assert pytest.approx(k, rel=1e-6) == 3.20


def test_fit_ratio_uses_training_rows_only():
    """Verify that splitting data ensures only training rows determine k."""
    full_df = pd.DataFrame({
        "modis_count": [100, 100, 100],
        "viirs_count": [300, 300, 999],  # Last row has outlier
    })
    train_df = full_df.iloc[:2]  # Training rows only
    k = fit_ratio(train_df)
    assert pytest.approx(k, rel=1e-6) == 3.00


# --- 2. Prediction Tests ---

def test_predict_ratio_scalar():
    """Verify prediction with a scalar input."""
    result = predict_ratio(50, k=3.2)
    assert isinstance(result, float)
    assert pytest.approx(result, rel=1e-6) == 160.0


def test_predict_ratio_list_and_array():
    """Verify predictions with list and numpy array inputs."""
    counts_list = [10, 20, 30]
    preds_list = predict_ratio(counts_list, k=3.0)
    assert isinstance(preds_list, np.ndarray)
    np.testing.assert_allclose(preds_list, [30.0, 60.0, 90.0])

    counts_tuple = (10, 20)
    preds_tuple = predict_ratio(counts_tuple, k=3.0)
    assert isinstance(preds_tuple, np.ndarray)
    np.testing.assert_allclose(preds_tuple, [30.0, 60.0])

    counts_arr = np.array([5, 15], dtype=np.int64)
    preds_arr = predict_ratio(counts_arr, k=2.0)
    assert isinstance(preds_arr, np.ndarray)
    np.testing.assert_allclose(preds_arr, [10.0, 30.0])


def test_predict_ratio_pandas_series():
    """Verify predictions with a pandas Series preserve index."""
    s = pd.Series([10, 25], index=["block_A", "block_B"])
    preds = predict_ratio(s, k=3.0)
    assert isinstance(preds, pd.Series)
    assert list(preds.index) == ["block_A", "block_B"]
    np.testing.assert_allclose(preds.values, [30.0, 75.0])


# --- 3. Zero Input Tests ---

def test_predict_ratio_zero_scalar():
    """A MODIS value of zero is allowed for prediction and should produce 0.0."""
    result = predict_ratio(0, k=3.5)
    assert result == 0.0
    assert isinstance(result, float)


def test_predict_ratio_zero_in_array():
    """Zero counts within an array should strictly output 0.0."""
    counts = [0, 10, 0]
    preds = predict_ratio(counts, k=4.0)
    np.testing.assert_allclose(preds, [0.0, 40.0, 0.0])


# --- 4. Zero Denominator Tests ---

def test_fit_ratio_zero_denominator():
    """Reject a zero total MODIS denominator in training data."""
    zero_modis_df = pd.DataFrame({
        "modis_count": [0, 0, 0],
        "viirs_count": [5, 12, 8],
    })
    with pytest.raises(ValueError, match="zero denominator"):
        fit_ratio(zero_modis_df)


# --- 5. Data Validation Tests (Rejection of Invalid Values) ---

@pytest.mark.parametrize("invalid_val", [np.nan, None])
def test_validation_rejects_missing(invalid_val):
    """Reject missing values in training data and prediction inputs."""
    df = pd.DataFrame({
        "modis_count": [10, invalid_val],
        "viirs_count": [30, 60],
    })
    with pytest.raises(ValueError, match="missing"):
        fit_ratio(df)

    with pytest.raises(ValueError, match="missing"):
        predict_ratio(invalid_val, k=3.0)


def test_validation_rejects_negative():
    """Reject negative detection counts."""
    neg_train_df = pd.DataFrame({
        "modis_count": [-5, 20],
        "viirs_count": [10, 40],
    })
    with pytest.raises(ValueError, match="negative"):
        fit_ratio(neg_train_df)

    with pytest.raises(ValueError, match="negative"):
        predict_ratio(-10, k=3.0)

    with pytest.raises(ValueError, match="negative"):
        predict_ratio([5, -2, 10], k=3.0)


def test_validation_rejects_infinite():
    """Reject infinite detection counts."""
    inf_df = pd.DataFrame({
        "modis_count": [10, np.inf],
        "viirs_count": [30, 50],
    })
    with pytest.raises(ValueError, match="infinite"):
        fit_ratio(inf_df)

    with pytest.raises(ValueError, match="infinite"):
        predict_ratio(np.inf, k=3.0)


def test_validation_rejects_fractional():
    """Reject fractional counts (detection counts must be whole integers)."""
    frac_df = pd.DataFrame({
        "modis_count": [10.5, 20],
        "viirs_count": [30, 60],
    })
    with pytest.raises(ValueError, match="fractional"):
        fit_ratio(frac_df)

    with pytest.raises(ValueError, match="fractional"):
        predict_ratio(3.7, k=3.0)

    with pytest.raises(ValueError, match="fractional"):
        predict_ratio([10, 4.25], k=3.0)


@pytest.mark.parametrize("nonnumeric_val", ["ten", True, False, [1, "two"]])
def test_validation_rejects_nonnumeric(nonnumeric_val):
    """Reject strings, booleans, and mixed non-numeric values."""
    with pytest.raises((TypeError, ValueError)):
        predict_ratio(nonnumeric_val, k=3.0)


def test_fit_ratio_rejects_missing_columns():
    """Reject DataFrames lacking the required columns."""
    bad_df = pd.DataFrame({"random_col": [1, 2, 3]})
    with pytest.raises(ValueError, match="missing required column"):
        fit_ratio(bad_df)


def test_predict_ratio_rejects_invalid_k():
    """Reject invalid k multipliers (negative, NaN, non-numeric)."""
    with pytest.raises(ValueError, match="non-negative"):
        predict_ratio(10, k=-1.5)

    with pytest.raises(ValueError, match="finite"):
        predict_ratio(10, k=np.nan)

    with pytest.raises(TypeError):
        predict_ratio(10, k="three")


# --- 6. Synthetic Dataset Contract Tests ---

def test_synthetic_dataset_block_id_format_and_coverage():
    """Confirm the synthetic dataset follows canonical bx_by block IDs and unknown coverage."""
    import re

    csv_path = model_dir / "data" / "synthetic" / "synthetic_overlap_BR-PA.csv"
    assert csv_path.exists(), f"Synthetic dataset not found at {csv_path}"

    df = pd.read_csv(csv_path)
    assert len(df) > 0, "Synthetic dataset is empty"

    # Verify canonical region_id
    assert (df["region_id"] == "BR-PA").all(), "All records must have region_id = 'BR-PA'"

    # Verify canonical block_id format: "bx_by" (e.g. "120_-50")
    block_pattern = re.compile(r"^-?\d+_-?\d+$")
    for block_id in df["block_id"]:
        assert isinstance(block_id, str), f"block_id {block_id} must be a string"
        assert block_pattern.match(block_id), f"block_id '{block_id}' does not match canonical 'bx_by' format"

    # Verify coverage_status is 'unknown' (coverage-unadjusted)
    assert (df["coverage_status"] == "unknown").all(), "Synthetic records must use coverage_status = 'unknown'"

    # Verify fit_ratio succeeds on this synthetic table
    k = fit_ratio(df)
    assert k > 0, f"Fitted multiplier k must be positive, got {k}"
