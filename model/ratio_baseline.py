"""FireChronicle - Ratio-of-Totals Baseline Model.

Scientific Scope:
- Region: Pará, Brazil (region_id = 'BR-PA')
- Input satellite: Aqua MODIS
- Reference: Suomi NPP VIIRS
- Modeling unit: 50 km block x year x month x day/night
- Goal: Estimate VIIRS S-NPP-equivalent hotspot detection counts (not unique fires).

NOTE:
This module implements an initial statistical baseline model.
The calculations are intended for algorithmic development and testing,
and do not claim official NASA validated calibration parameters.
"""

from typing import Any, Union
import numpy as np
import pandas as pd


def _validate_single_count(val: Any, name: str = "count") -> int:
    """Validate a single detection count value.

    Rejects boolean, non-numeric, NaN, infinite, negative, or fractional values.
    Returns the count as an integer.
    """
    if isinstance(val, (bool, np.bool_)):
        raise TypeError(f"Invalid detection count for '{name}': booleans are not allowed.")

    if not isinstance(val, (int, float, np.integer, np.floating)):
        raise TypeError(f"Invalid detection count for '{name}': value '{val}' must be numeric.")

    if np.isnan(val):
        raise ValueError(f"Invalid detection count for '{name}': missing (NaN/None) value is not allowed.")

    if np.isinf(val):
        raise ValueError(f"Invalid detection count for '{name}': infinite values are not allowed.")

    if val < 0:
        raise ValueError(f"Invalid detection count for '{name}': negative value {val} is not allowed.")

    # Check whether the numeric value represents a whole number
    if float(val) % 1.0 != 0.0:
        raise ValueError(f"Invalid detection count for '{name}': fractional value {val} is not allowed (counts must be whole integers).")

    return int(val)


def _validate_count_array_or_series(
    counts: Union[list, tuple, np.ndarray, pd.Series],
    name: str = "count"
) -> np.ndarray:
    """Validate an array-like collection of detection counts.

    Rejects missing, negative, infinite, fractional, or non-numeric values.
    Returns a 1D numpy array of float64 counts.
    """
    if isinstance(counts, pd.Series):
        raw_items = counts.tolist()
    elif isinstance(counts, np.ndarray):
        raw_items = counts.flatten().tolist()
    elif isinstance(counts, (list, tuple)):
        raw_items = list(counts)
    else:
        raise TypeError(f"Expected array-like input for '{name}', got {type(counts).__name__}.")

    if len(raw_items) == 0:
        raise ValueError(f"Detection counts collection '{name}' cannot be empty.")

    validated = [_validate_single_count(item, name=name) for item in raw_items]
    return np.array(validated, dtype=np.float64)


def fit_ratio(train_df: pd.DataFrame) -> float:
    """Fit the Ratio-of-Totals multiplier k using training rows only.

    Formula:
        k = sum(viirs_count) / sum(modis_count)

    Parameters
    ----------
    train_df : pd.DataFrame
        DataFrame containing 'modis_count' and 'viirs_count' columns.

    Returns
    -------
    float
        The fitted multiplier k (VIIRS-equivalent per MODIS detection).

    Raises
    ------
    TypeError
        If train_df is not a pandas DataFrame.
    ValueError
        If required columns are missing, data is invalid, or the total MODIS sum is zero.
    """
    if not isinstance(train_df, pd.DataFrame):
        raise TypeError(f"train_df must be a pandas DataFrame, got {type(train_df).__name__}.")

    required_cols = {"modis_count", "viirs_count"}
    missing_cols = required_cols - set(train_df.columns)
    if missing_cols:
        raise ValueError(f"train_df is missing required column(s): {sorted(missing_cols)}")

    if len(train_df) == 0:
        raise ValueError("train_df contains zero rows. Cannot fit model on empty data.")

    # Validate MODIS and VIIRS counts
    modis_arr = _validate_count_array_or_series(train_df["modis_count"], name="modis_count")
    viirs_arr = _validate_count_array_or_series(train_df["viirs_count"], name="viirs_count")

    sum_modis = float(np.sum(modis_arr))
    sum_viirs = float(np.sum(viirs_arr))

    if sum_modis == 0.0:
        raise ValueError(
            "Total MODIS count in training data is 0. Cannot compute ratio with a zero denominator."
        )

    k = sum_viirs / sum_modis
    return float(k)


def predict_ratio(
    modis_counts: Union[int, float, list, tuple, np.ndarray, pd.Series],
    k: float
) -> Union[float, np.ndarray, pd.Series]:
    """Predict VIIRS S-NPP-equivalent detection counts given Aqua MODIS counts.

    Formula:
        predicted_viirs = modis_count * k

    A MODIS count of 0 is valid and will strictly return 0.0.

    Parameters
    ----------
    modis_counts : scalar, list, numpy.ndarray, or pandas.Series
        Non-negative integer Aqua MODIS hotspot detection counts.
    k : float
        The ratio-of-totals multiplier (must be non-negative and finite).

    Returns
    -------
    float, numpy.ndarray, or pandas.Series
        Estimated VIIRS-equivalent detection counts. Scalar inputs return float,
        pd.Series inputs return pd.Series, and array-like collections (list, tuple,
        or np.ndarray) return a 1D or reshaped numpy.ndarray.

    Raises
    ------
    TypeError / ValueError
        If modis_counts contains invalid counts or k is invalid.
    """
    # Validate k
    if isinstance(k, (bool, np.bool_)):
        raise TypeError("Multiplier k cannot be a boolean.")
    if not isinstance(k, (int, float, np.integer, np.floating)):
        raise TypeError(f"Multiplier k must be numeric, got {type(k).__name__}.")
    if np.isnan(k) or np.isinf(k) or k < 0:
        raise ValueError(f"Multiplier k must be a finite, non-negative number. Got: {k}")

    # Check for missing None input
    if modis_counts is None:
        raise ValueError("Invalid detection count for 'modis_counts': missing (NaN/None) value is not allowed.")

    # Scalar input
    if isinstance(modis_counts, (int, float, np.integer, np.floating, bool, np.bool_)):
        validated_scalar = _validate_single_count(modis_counts, name="modis_counts")
        if validated_scalar == 0:
            return 0.0
        return float(validated_scalar * k)

    # Pandas Series input
    if isinstance(modis_counts, pd.Series):
        validated_arr = _validate_count_array_or_series(modis_counts, name="modis_counts")
        pred_arr = validated_arr * k
        # Ensure 0 input strictly yields 0.0
        pred_arr[validated_arr == 0] = 0.0
        return pd.Series(pred_arr, index=modis_counts.index, name="predicted_viirs_count")

    # Array or list input
    if isinstance(modis_counts, (list, tuple, np.ndarray)):
        validated_arr = _validate_count_array_or_series(modis_counts, name="modis_counts")
        pred_arr = validated_arr * k
        # Ensure 0 input strictly yields 0.0
        pred_arr[validated_arr == 0] = 0.0
        if isinstance(modis_counts, np.ndarray):
            return pred_arr.reshape(modis_counts.shape)
        return pred_arr

    raise TypeError(
        f"Unsupported type for modis_counts: {type(modis_counts).__name__}. "
        "Expected int, float, list, np.ndarray, or pd.Series."
    )
