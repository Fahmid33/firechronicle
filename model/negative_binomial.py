"""FireChronicle - Model 1: Negative Binomial Count Regression.

Scientific Scope:
- Region: Pará, Brazil (region_id = 'BR-PA')
- Input satellite: Aqua MODIS (predictor: log1p(modis_count), month, daynight)
- Reference: Suomi NPP VIIRS (target: viirs_count)
- Modeling unit: 50 km block x year x month x day/night
- Objective: Estimate VIIRS S-NPP-equivalent hotspot detection counts.

SCIENTIFIC STATUS:
DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED
All models, parameters, and evaluations in this module are calibrated on
synthetic mock fixtures for algorithmic testing and comparison against the baseline.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
import statsmodels.discrete.discrete_model as dm

from ratio_baseline import _validate_count_array_or_series

MODEL_VERSION = "nb-candidate-v1.0-synthetic-demo"
SCIENTIFIC_STATUS = "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED"


FIXED_CALENDAR_MONTHS = list(range(1, 13))


def _validate_month(series: pd.Series, name: str = "month") -> np.ndarray:
    """Validate month values (must be whole integers between 1 and 12)."""
    if series.isna().any():
        raise ValueError(f"Missing (NaN/None) values found in '{name}'.")
    try:
        arr = pd.to_numeric(series, errors="raise").to_numpy()
    except (ValueError, TypeError) as e:
        raise TypeError(f"Non-numeric values found in '{name}': {e}") from e

    if not np.all(arr == np.floor(arr)):
        raise ValueError(f"Fractional months found in '{name}'. Months must be integers 1 to 12.")

    int_arr = arr.astype(int)
    if np.any((int_arr < 1) | (int_arr > 12)):
        raise ValueError(f"Invalid month values in '{name}'. All months must be between 1 and 12.")

    return int_arr


def _validate_daynight(series: pd.Series, name: str = "daynight") -> np.ndarray:
    """Validate day/night flags (must be strictly 'D' or 'N')."""
    if series.isna().any():
        raise ValueError(f"Missing (NaN/None) values found in '{name}'.")
    str_arr = series.astype(str).str.strip().str.upper().to_numpy()
    invalid_mask = ~np.isin(str_arr, ["D", "N"])
    if np.any(invalid_mask):
        invalid_examples = list(set(str_arr[invalid_mask]))[:3]
        raise ValueError(
            f"Invalid daynight flags in '{name}': {invalid_examples}. Expected 'D' or 'N'."
        )
    return str_arr


def build_design_matrix(
    df: pd.DataFrame,
    feature_names: Optional[List[str]] = None,
    reference_month: int = 1
) -> pd.DataFrame:
    """Construct a standardized design matrix for training or prediction.

    Fixed 12-Month Encoding:
    - const: Intercept term (1.0)
    - log1p_modis: ln(1 + modis_count)
    - daynight_N: Indicator (1.0 for Night 'N', 0.0 for Day 'D')
    - month_{m}: Indicator for each categorical month (m in 2..12, relative to reference_month=1)

    Identifiability:
    During training, only months with actual observations in train_df receive dummy columns,
    preventing singular matrices. Unobserved calendar months are tracked in model metadata.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}.")

    for required in ("modis_count", "month", "daynight"):
        if required not in df.columns:
            raise ValueError(f"DataFrame missing required predictor column: '{required}'")

    if len(df) == 0:
        raise ValueError("Cannot construct design matrix for empty DataFrame.")

    # Validate inputs strictly
    modis_arr = _validate_count_array_or_series(df["modis_count"], name="modis_count")
    month_arr = _validate_month(df["month"], name="month")
    dn_arr = _validate_daynight(df["daynight"], name="daynight")

    n_rows = len(df)
    const_col = np.ones(n_rows, dtype=np.float64)
    log1p_col = np.log1p(modis_arr)
    dn_col = (dn_arr == "N").astype(np.float64)

    if feature_names is None:
        # Training mode: build dummy columns for observed months (excluding reference_month)
        unique_months = sorted(list(set(month_arr)))
        ref_m = reference_month if reference_month in unique_months else unique_months[0]
        dummy_months = [m for m in unique_months if m != ref_m]

        cols: Dict[str, np.ndarray] = {
            "const": const_col,
            "log1p_modis": log1p_col,
        }
        # Include daynight_N only if both 'D' and 'N' are observed in training rows.
        # Single-pass datasets omit daynight_N to prevent singular/collinear matrices.
        if set(dn_arr) == {"D", "N"}:
            cols["daynight_N"] = dn_col

        for m in dummy_months:
            cols[f"month_{m}"] = (month_arr == m).astype(np.float64)

        X_train = pd.DataFrame(cols, index=df.index)
        X_train.attrs["reference_month"] = ref_m
        return X_train
    else:
        # Prediction mode: construct columns matching feature_names exactly
        cols = {
            "const": const_col,
            "log1p_modis": log1p_col,
        }
        if "daynight_N" in feature_names:
            cols["daynight_N"] = dn_col

        for col_name in feature_names:
            if col_name.startswith("month_"):
                m_val = int(col_name.split("_")[1])
                cols[col_name] = (month_arr == m_val).astype(np.float64)

        X_pred = pd.DataFrame(cols, index=df.index)
        return X_pred[feature_names]


def fit_negative_binomial(
    train_df: pd.DataFrame,
    reference_month: int = 1,
    maxiter: int = 500
) -> Dict[str, Any]:
    """Fit a genuine Negative Binomial count model (NB2) with estimated dispersion.

    Formula:
        ln(mu) = beta_0 + beta_1 * log1p(M) + beta_2 * I(N) + sum(beta_m * I(month_m))
        Var(V | X) = mu + alpha * mu^2

    Parameters
    ----------
    train_df : pd.DataFrame
        DataFrame containing 'modis_count', 'viirs_count', 'month', 'daynight'.
    reference_month : int, optional
        Baseline month for dummy coding (default 1).
    maxiter : int, optional
        Maximum iterations for maximum likelihood optimization (default 500).

    Returns
    -------
    dict
        Model bundle containing fitted parameters, dispersion alpha,
        feature definitions, observed/unsupported months, and convergence metadata.
    """
    if not isinstance(train_df, pd.DataFrame):
        raise TypeError(f"train_df must be a pandas DataFrame, got {type(train_df).__name__}.")

    if "viirs_count" not in train_df.columns:
        raise ValueError("train_df is missing required target column: 'viirs_count'")

    # Validate target counts
    y_arr = _validate_count_array_or_series(train_df["viirs_count"], name="viirs_count")

    # Build training design matrix
    X_df = build_design_matrix(train_df, feature_names=None, reference_month=reference_month)
    feature_names = list(X_df.columns)
    actual_ref_month = int(X_df.attrs.get("reference_month", reference_month))

    observed_months = sorted(train_df["month"].astype(int).unique().tolist())
    unsupported_months = sorted(list(set(FIXED_CALENDAR_MONTHS) - set(observed_months)))
    dn_observed = sorted(list(set(train_df["daynight"].astype(str).str.strip().str.upper().unique())))
    daynight_mode = "combined_day_night" if "daynight_N" in feature_names else f"single_pass_{dn_observed[0]}"

    # Instantiate genuine Negative Binomial (NB2 formulation)
    nb_model = dm.NegativeBinomial(y_arr, X_df, loglike_method="nb2")

    # Fit parameters via Maximum Likelihood Estimation
    fit_res = nb_model.fit(disp=False, maxiter=maxiter)

    converged = bool(fit_res.mle_retvals.get("converged", False))
    alpha = float(fit_res.params["alpha"]) if "alpha" in fit_res.params else 0.0

    # Exogenous coefficients excluding dispersion parameter
    params_exog = fit_res.params.drop("alpha").to_dict()

    return {
        "model_type": "negative_binomial_nb2",
        "model_version": MODEL_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "is_production_ready": False,
        "fitted_results": fit_res,
        "params_exog": params_exog,
        "dispersion_alpha": alpha,
        "feature_names": feature_names,
        "reference_month": actual_ref_month,
        "requested_reference_month": reference_month,
        "reference_month_fallback": bool(actual_ref_month != reference_month),
        "daynight_mode": daynight_mode,
        "daynight_supported": dn_observed,
        "daynight_term_included": "daynight_N" in feature_names,
        "training_months": observed_months,
        "unsupported_months": unsupported_months,
        "converged": converged,
        "log_likelihood": float(fit_res.llf),
        "aic": float(fit_res.aic),
        "bic": float(fit_res.bic),
        "n_obs": int(fit_res.nobs),
        "df_model": int(fit_res.df_model),
        "df_resid": int(fit_res.df_resid),
    }


def predict_negative_binomial(
    model: Dict[str, Any],
    input_data: Union[pd.DataFrame, Dict[str, Any]],
    allow_unsupported_categories: bool = False
) -> Union[pd.Series, float]:
    """Predict expected VIIRS-equivalent detection counts using the fitted Negative Binomial model.

    Formula:
        mu = exp(X * beta)

    Parameters
    ----------
    model : dict
        Model bundle returned by fit_negative_binomial().
    input_data : pd.DataFrame or dict
        Input observations containing 'modis_count', 'month', 'daynight'.
    allow_unsupported_categories : bool, optional
        If False (default), raises ValueError when input contains months unobserved
        during model training, preventing silent aliasing. If True, maps unobserved
        months to reference level with a recorded limitation.

    Returns
    -------
    pd.Series or float
        Expected VIIRS-equivalent detection counts (strictly non-negative).
    """
    if not isinstance(model, dict) or "params_exog" not in model or "feature_names" not in model:
        raise TypeError("Invalid model artifact passed to predict_negative_binomial.")

    is_single_dict = isinstance(input_data, dict)
    if is_single_dict:
        df = pd.DataFrame([input_data])
    elif isinstance(input_data, pd.DataFrame):
        df = input_data.copy()
    else:
        raise TypeError(f"input_data must be a DataFrame or dict, got {type(input_data).__name__}.")

    for required in ("modis_count", "month", "daynight"):
        if required not in df.columns:
            raise ValueError(f"Input data missing required column: '{required}'")

    # Validate inputs rigorously before conversions
    valid_months = _validate_month(df["month"], name="month")
    valid_dn = _validate_daynight(df["daynight"], name="daynight")
    _ = _validate_count_array_or_series(df["modis_count"], name="modis_count")

    # Validate day/night pass support (e.g. single-pass trained models)
    if "daynight_supported" in model:
        supported_dn = set(model["daynight_supported"])
        input_dn = set(valid_dn)
        unsupported_dn = input_dn - supported_dn
        if unsupported_dn and not allow_unsupported_categories:
            raise ValueError(
                f"Prediction failed: Input contains unsupported daynight pass(es) {sorted(unsupported_dn)}. "
                f"Model was trained exclusively on {sorted(supported_dn)} passes."
            )

    # Validate that all input months were observed during model training
    input_months = set(valid_months)
    training_months = set(model.get("training_months", FIXED_CALENDAR_MONTHS))
    unobserved = input_months - training_months

    if unobserved:
        if not allow_unsupported_categories:
            raise ValueError(
                f"Prediction failed: Input contains unsupported month(s) {sorted(unobserved)} "
                f"that were unobserved during model training (training months: {sorted(training_months)}). "
                "Negative Binomial cannot predict on unobserved seasonal categories without arbitrary assumptions."
            )
        else:
            import warnings
            ref_m = model.get("reference_month", 1)
            warnings.warn(
                f"EXTRAPOLATION WARNING: Input contains unsupported month(s) {sorted(unobserved)} "
                f"not observed during training (training months: {sorted(training_months)}). "
                f"Extrapolating by mapping unsupported months to the reference month ({ref_m}) baseline.",
                UserWarning,
                stacklevel=2,
            )

    # Build aligned prediction matrix matching trained features
    X_pred = build_design_matrix(df, feature_names=model["feature_names"])

    # Compute expected counts: mu = exp(X * beta)
    beta = np.array([model["params_exog"][col] for col in model["feature_names"]], dtype=np.float64)
    linear_pred = X_pred.to_numpy(dtype=np.float64).dot(beta)

    # Clip extreme values to prevent overflow while ensuring strictly non-negative output
    mu = np.exp(np.clip(linear_pred, -30.0, 30.0))

    if is_single_dict:
        return float(mu[0])

    return pd.Series(mu, index=df.index, name="predicted_viirs_count")
