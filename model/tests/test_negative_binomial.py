"""Unit tests for Model 1: Negative Binomial Count Regression.

Tests cover:
- Genuine Negative Binomial fitting with estimated dispersion (alpha > 0)
- Predictor preprocessing: log1p(M), month dummies, daynight indicators
- Consistent prediction on unseen categories
- Strict input validation (missing, negative, fractional, invalid months/daynight)
- Finite, non-negative prediction outputs
- Joblib serialization and deserialization
- Convergence tracking and failure handling
"""

import sys
from pathlib import Path
import tempfile
import joblib
import numpy as np
import pandas as pd
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from negative_binomial import (
    fit_negative_binomial,
    predict_negative_binomial,
    build_design_matrix,
)


@pytest.fixture
def synthetic_nb_df():
    """Load the dedicated synthetic NB training fixture."""
    csv_path = model_dir / "data" / "synthetic" / "synthetic_nb_training_BR-PA.csv"
    assert csv_path.exists(), f"Synthetic NB fixture not found at {csv_path}"
    return pd.read_csv(csv_path)


# --- 1. Fitting & Dispersion Tests ---

def test_fit_negative_binomial_estimates_dispersion(synthetic_nb_df):
    """Verify that fit_negative_binomial fits genuine NB2 and estimates alpha > 0."""
    model = fit_negative_binomial(synthetic_nb_df)

    assert model["model_type"] == "negative_binomial_nb2"
    assert model["converged"] is True
    assert model["dispersion_alpha"] > 0.0, "Model must estimate positive dispersion alpha."
    assert "log1p_modis" in model["feature_names"]
    assert "daynight_N" in model["feature_names"]
    assert "const" in model["feature_names"]
    assert model["params_exog"]["log1p_modis"] > 0.0, "log1p(M) coefficient should be positive."


# --- 2. Prediction & Output Constraints ---

def test_predict_finite_nonnegative_outputs(synthetic_nb_df):
    """Ensure all predictions are finite and strictly non-negative."""
    model = fit_negative_binomial(synthetic_nb_df)
    preds = predict_negative_binomial(model, synthetic_nb_df)

    assert isinstance(preds, pd.Series)
    assert len(preds) == len(synthetic_nb_df)
    assert np.all(np.isfinite(preds.values))
    assert np.all(preds.values >= 0.0)


def test_predict_zero_modis_count_produces_positive_baseline(synthetic_nb_df):
    """Verify that M = 0 produces a positive expected count due to the log link."""
    model = fit_negative_binomial(synthetic_nb_df)
    single_rec = {"modis_count": 0, "month": 8, "daynight": "D"}
    pred = predict_negative_binomial(model, single_rec)

    assert isinstance(pred, float)
    assert pred > 0.0, "Negative Binomial log-link mathematically predicts positive count at M=0."
    assert np.isfinite(pred)


# --- 3. Categorical Preprocessing & Unseen Month Handling ---

def test_predict_rejects_unobserved_month_by_default(synthetic_nb_df):
    """Months absent from training must be rejected by default, preventing silent aliasing."""
    # Train only on dry season months (7, 8, 9, 10)
    train_subset = synthetic_nb_df[synthetic_nb_df["month"].isin([7, 8, 9, 10])].copy()
    model = fit_negative_binomial(train_subset, reference_month=7)

    # Predict on an unobserved wet-season month (month 2)
    test_rec = pd.DataFrame([{
        "modis_count": 15,
        "month": 2,  # Not in training
        "daynight": "D",
    }])

    with pytest.raises(ValueError, match="unsupported month"):
        predict_negative_binomial(model, test_rec)


def test_model_bundle_records_unsupported_months(synthetic_nb_df):
    """Model bundle must record unobserved months in model['unsupported_months']."""
    train_subset = synthetic_nb_df[synthetic_nb_df["month"].isin([7, 8, 9, 10])].copy()
    model = fit_negative_binomial(train_subset, reference_month=7)

    assert "unsupported_months" in model
    expected_unsupported = sorted(list(set(range(1, 13)) - {7, 8, 9, 10}))
    assert model["unsupported_months"] == expected_unsupported


def test_predict_allows_unsupported_month_when_explicitly_flagged(synthetic_nb_df):
    """When allow_unsupported_categories=True, predictions evaluate without raising."""
    train_subset = synthetic_nb_df[synthetic_nb_df["month"].isin([7, 8, 9, 10])].copy()
    model = fit_negative_binomial(train_subset, reference_month=7)

    test_rec = pd.DataFrame([{
        "modis_count": 15,
        "month": 2,
        "daynight": "D",
    }])
    pred = predict_negative_binomial(model, test_rec, allow_unsupported_categories=True)
    assert len(pred) == 1
    assert np.isfinite(pred.iloc[0])
    assert pred.iloc[0] > 0.0


def test_design_matrix_columns_aligned(synthetic_nb_df):
    """Design matrix must match trained feature names exactly."""
    train_subset = synthetic_nb_df.head(60).copy()
    model = fit_negative_binomial(train_subset)

    X_pred = build_design_matrix(synthetic_nb_df.tail(10), feature_names=model["feature_names"])
    assert list(X_pred.columns) == model["feature_names"]


# --- 4. Validation & Error Handling ---

def test_validation_rejects_missing_predictors():
    """Reject DataFrames missing required columns."""
    bad_df = pd.DataFrame({"random_col": [1, 2, 3]})
    with pytest.raises(ValueError, match="missing required predictor column"):
        build_design_matrix(bad_df)


def test_validation_rejects_invalid_months():
    """Reject month numbers outside 1..12 or fractional months."""
    bad_month_df = pd.DataFrame({
        "modis_count": [10, 20],
        "month": [13, 5],  # 13 is invalid
        "daynight": ["D", "N"]
    })
    with pytest.raises(ValueError, match="between 1 and 12"):
        build_design_matrix(bad_month_df)

    frac_month_df = pd.DataFrame({
        "modis_count": [10, 20],
        "month": [7.5, 8],
        "daynight": ["D", "N"]
    })
    with pytest.raises(ValueError, match="Fractional months"):
        build_design_matrix(frac_month_df)


def test_validation_rejects_invalid_daynight():
    """Reject daynight values other than 'D' or 'N'."""
    bad_dn_df = pd.DataFrame({
        "modis_count": [10, 20],
        "month": [7, 8],
        "daynight": ["D", "X"]  # 'X' is invalid
    })
    with pytest.raises(ValueError, match="Expected 'D' or 'N'"):
        build_design_matrix(bad_dn_df)


def test_fit_rejects_missing_target():
    """Reject training data lacking viirs_count."""
    no_target_df = pd.DataFrame({
        "modis_count": [10, 20],
        "month": [7, 8],
        "daynight": ["D", "N"]
    })
    with pytest.raises(ValueError, match="missing required target column"):
        fit_negative_binomial(no_target_df)


# --- 5. Serialization & Convergence Tracking ---

def test_joblib_serialization_and_predict(synthetic_nb_df):
    """Ensure the fitted model bundle serializes and reloads cleanly via joblib."""
    model = fit_negative_binomial(synthetic_nb_df)
    preds_orig = predict_negative_binomial(model, synthetic_nb_df.head(5))

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        joblib.dump(model, tmp_path)
        loaded_model = joblib.load(tmp_path)
        preds_loaded = predict_negative_binomial(loaded_model, synthetic_nb_df.head(5))
        np.testing.assert_allclose(preds_orig.values, preds_loaded.values, rtol=1e-5)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_convergence_flag_reported(synthetic_nb_df):
    """Verify that model dictionary captures convergence status."""
    model = fit_negative_binomial(synthetic_nb_df, maxiter=500)
    assert "converged" in model
    assert isinstance(model["converged"], bool)
    assert model["converged"] is True


def test_single_pass_training_avoids_singular_matrix(synthetic_nb_df):
    """Training on only 'D' or only 'N' rows must omit daynight_N to prevent singular matrix."""
    d_only_df = synthetic_nb_df[synthetic_nb_df["daynight"] == "D"].copy()
    model = fit_negative_binomial(d_only_df)

    # daynight_N must NOT be in feature names
    assert "daynight_N" not in model["feature_names"]
    assert model["daynight_mode"] == "single_pass_D"
    assert model["converged"] is True

    # Predict on matching 'D' pass succeeds
    pred_d = predict_negative_binomial(model, d_only_df.head(4))
    assert len(pred_d) == 4
    assert (pred_d > 0).all()

    # Predict on unobserved 'N' pass without override must raise ValueError
    n_sample = synthetic_nb_df[synthetic_nb_df["daynight"] == "N"].head(2)
    with pytest.raises(ValueError, match="unsupported daynight pass"):
        predict_negative_binomial(model, n_sample, allow_unsupported_categories=False)


def test_reference_month_fallback_recorded_and_extrapolation_warned(synthetic_nb_df):
    """When month 1 is unobserved, reference month must fall back to observed month and be recorded."""
    sub_df = synthetic_nb_df[synthetic_nb_df["month"].isin([7, 8, 9])].copy()
    model = fit_negative_binomial(sub_df, reference_month=1)

    # Reference month must fall back to 7 (first observed) and be accurately recorded
    assert model["reference_month"] == 7
    assert model["reference_month_fallback"] is True
    assert "month_7" not in model["feature_names"]
    assert "month_8" in model["feature_names"]
    assert "month_9" in model["feature_names"]

    # Predicting on unobserved month 2 must raise ValueError by default
    bad_rec = {"modis_count": 20, "month": 2, "daynight": "D"}
    with pytest.raises(ValueError, match="unsupported month"):
        predict_negative_binomial(model, bad_rec, allow_unsupported_categories=False)

    # With override, it must emit an explicit EXTRAPOLATION WARNING
    with pytest.warns(UserWarning, match="EXTRAPOLATION WARNING"):
        pred_extrap = predict_negative_binomial(model, bad_rec, allow_unsupported_categories=True)
        assert pred_extrap > 0.0
