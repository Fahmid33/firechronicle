"""FireChronicle - Baseline Validation Metrics Evaluator.

Computes validation metrics on held-out synthetic data (2020, block 121_-51)
and exports 'model/validation_metrics.json' as required by Rulebook Section 5 (p. 6).

IMPORTANT:
This evaluation assesses algorithm mechanics on a single joint synthetic hold-out
cell slice. It does NOT claim independent orthogonal temporal and geographic cross-validation.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

from ratio_baseline import fit_ratio, predict_ratio
from validation_pipeline import validate_overlap_table

MODEL_VERSION = "ratio-baseline-v1.0-synthetic-demo"
SCIENTIFIC_STATUS = "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED"


def evaluate_baseline():
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "data" / "synthetic" / "synthetic_overlap_BR-PA.csv"

    df = pd.read_csv(csv_path)

    # Validate table and filter out ineligible coverage records
    eligible_df, audit = validate_overlap_table(df)

    # Training partition: eligible 2018-2019 data (blocks 120_-50, 121_-50, 120_-51)
    train_df = eligible_df[eligible_df["year"].isin([2018, 2019])].copy()

    # Test partition: eligible 2020 data (block 121_-51)
    test_df = eligible_df[eligible_df["year"] == 2020].copy()

    k = fit_ratio(train_df)

    # Generate predictions on test set
    y_true = test_df["viirs_count"].to_numpy(dtype=np.float64)
    y_pred = predict_ratio(test_df["modis_count"], k=k).to_numpy(dtype=np.float64)
    n = len(y_true)

    # 1. Mean Absolute Error (MAE)
    mae = float(np.mean(np.abs(y_pred - y_true)))

    # 2. Aggregate count bias: (sum(y_pred) - sum(y_true)) / sum(y_true)
    sum_true = float(np.sum(y_true))
    sum_pred = float(np.sum(y_pred))
    signed_agg_error = round(float(sum_pred - sum_true), 2)
    aggregate_bias_pct = float(((sum_pred - sum_true) / sum_true) * 100.0) if sum_true > 0 else 0.0

    # 3. Poisson deviance (Mean and Total)
    eps = 1e-9
    mu = np.maximum(y_pred, eps)
    term1 = np.where(y_true > 0, y_true * np.log(np.maximum(y_true, eps) / mu), 0.0)
    term2 = y_true - mu
    dev_sum = float(2.0 * np.sum(term1 - term2))
    mean_poisson_deviance = round(float(dev_sum / n), 4)
    total_poisson_deviance = round(dev_sum, 4)

    metrics = {
        "model_version": MODEL_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "is_production_validation": False,
        "evaluation_dataset": "synthetic_overlap_BR-PA.csv (year=2020, block_id=121_-51, N=6)",
        "held_out_strategy": (
            "Single joint spatio-temporal holdout slice on synthetic test fixture "
            "(year=2020, block_id=121_-51). Note: This single hold-out slice demonstrates pipeline "
            "metrics only; it does NOT claim separate or orthogonal temporal and geographic "
            "cross-validation folds."
        ),
        "eligible_sample_count": len(test_df),
        "excluded_records_count": audit["excluded_records"],
        "unknown_coverage_sample_count": int((test_df["coverage_status"].astype(str).str.lower().isin(["unknown", "coverage_unadjusted"])).sum()),
        "coverage_policy": audit["coverage_policy"],
        "fitted_multiplier_k": round(k, 4),
        "metrics": {
            "mean_absolute_error": round(mae, 4),
            "aggregate_count_bias_percent": round(aggregate_bias_pct, 4),
            "signed_aggregate_count_error": signed_agg_error,
            "mean_poisson_deviance": mean_poisson_deviance,
            "total_poisson_deviance": total_poisson_deviance,
            "poisson_deviance_scale": "mean_poisson_deviance is normalized per block-month record (2/N * sum(d_i)); total_poisson_deviance is unnormalized sum (2 * sum(d_i)).",
            "sum_observed_viirs": int(sum_true),
            "sum_estimated_viirs": round(sum_pred, 2)
        },
        "scientific_limitations": [
            "Cannot recover missed detections when modis_count is zero.",
            "Evaluated strictly on synthetic mock fixture; not validated against true NASA FIRMS Pará observations.",
            "A larger, multi-year empirical dataset will be required to execute separate temporal and spatial holdout experiments."
        ]
    }

    out_path = base_dir / "validation_metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, allow_nan=False)

    print(f"Validation metrics exported to {out_path}:")
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    evaluate_baseline()
