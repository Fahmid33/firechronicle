"""FireChronicle - Demonstration of Model 1: Negative Binomial Count Regression.

Scientific Scope:
- Region: Pará, Brazil (BR-PA)
- Input: Aqua MODIS (log1p(M), month, daynight)
- Reference: Suomi NPP VIIRS (counts)
- Unit: 50 km block x year x month x day/night

DISCLAIMER:
This demonstration uses SYNTHETIC mock data for algorithmic development and testing.
It does NOT claim to represent official NASA observations or validated models.
"""

import sys
from pathlib import Path

# Ensure model/ is in sys.path
base_dir = Path(__file__).resolve().parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

import numpy as np
import pandas as pd

from negative_binomial import fit_negative_binomial, predict_negative_binomial
from ratio_baseline import fit_ratio, predict_ratio


def main():
    print("=" * 75)
    print(" FireChronicle: Model 1 — Negative Binomial Count Regression Demo")
    print(" Region: Pará, Brazil (BR-PA) | Aqua MODIS -> Suomi NPP VIIRS")
    print("=" * 75)

    # 1. Load the dedicated synthetic regression dataset
    csv_path = base_dir / "data" / "synthetic" / "synthetic_nb_training_BR-PA.csv"
    print(f"\n[1] Loading synthetic dataset from:\n    {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"    Total rows loaded: {len(df)}")
    print(f"    Years: {sorted(df['year'].unique().tolist())}")
    print(f"    Blocks: {sorted(df['block_id'].unique().tolist())}")
    print(f"    Months: {sorted(df['month'].unique().tolist())}")

    # 2. Split into Training (2018-2019) and Held-out Evaluation (2020)
    train_df = df[df["year"].isin([2018, 2019])].copy()
    test_df = df[df["year"] == 2020].copy()

    print(f"\n[2] Partitioning Data:")
    print(f"    Training partition (2018-2019): {len(train_df)} rows")
    print(f"    Held-out partition (2020):      {len(test_df)} rows")

    # 3. Fit Negative Binomial Model
    print(f"\n[3] Fitting Negative Binomial Model (NB2 with log-link)...")
    nb_bundle = fit_negative_binomial(train_df, reference_month=1)

    print(f"    Optimization Converged: {nb_bundle['converged']}")
    print(f"    Log-Likelihood:         {nb_bundle['log_likelihood']:.2f}")
    print(f"    AIC:                    {nb_bundle['aic']:.2f}")
    print(f"    Estimated Dispersion Alpha: {nb_bundle['dispersion_alpha']:.4f}")
    print(f"    (Alpha > 0 confirms genuine Negative Binomial modeling overdispersion, Var = mu + alpha * mu^2)")

    print("\n    Estimated Exogenous Coefficients (Beta):")
    for feat in nb_bundle["feature_names"]:
        coef_val = nb_bundle["params_exog"][feat]
        print(f"      {feat:15s}: {coef_val:8.4f}  (exp(beta) = {np.exp(coef_val):.4f})")

    # 4. Illustrative Scenario Predictions
    print("\n[4] Illustrative Scenario Predictions:")
    scenarios = [
        {"scenario": "MODIS zero detection (August, Day)", "modis_count": 0, "month": 8, "daynight": "D"},
        {"scenario": "Moderate fire count (August, Day)", "modis_count": 45, "month": 8, "daynight": "D"},
        {"scenario": "Moderate fire count (August, Night)", "modis_count": 45, "month": 8, "daynight": "N"},
        {"scenario": "Peak fire count (September, Day)", "modis_count": 180, "month": 9, "daynight": "D"},
    ]

    # Also fit ratio baseline on the same training set for direct comparison
    k_baseline = fit_ratio(train_df)

    print(f"    {'Scenario':<42} | {'MODIS':<6} | {'Ratio Est.':<10} | {'NB Est.':<10}")
    print("    " + "-" * 75)
    for sc in scenarios:
        rec = {"modis_count": sc["modis_count"], "month": sc["month"], "daynight": sc["daynight"]}
        nb_pred = predict_negative_binomial(nb_bundle, rec)
        ratio_pred = predict_ratio(sc["modis_count"], k=k_baseline)
        print(f"    {sc['scenario']:<42} | {sc['modis_count']:6d} | {ratio_pred:10.2f} | {nb_pred:10.2f}")

    # 5. Critical Scientific Discussion: The Zero-MODIS Nuance
    print("\n" + "=" * 75)
    print(" [5] SCIENTIFIC INTEGRITY AUDIT: The Zero-MODIS Nuance (Rulebook p. 5)")
    print("=" * 75)
    print(" Notice that for MODIS = 0 in August, Day:")
    zero_case = {"modis_count": 0, "month": 8, "daynight": "D"}
    zero_nb = predict_negative_binomial(nb_bundle, zero_case)
    print(f"   * Ratio-of-Totals Baseline predicts: 0.00")
    print(f"   * Negative Binomial Model predicts:  {zero_nb:.2f}")
    print("\n IMPORTANT SCIENTIFIC CAUTION:")
    print(" A positive Negative Binomial estimate for zero MODIS detections is a")
    print(" mathematical consequence of the log link (mu = exp(intercept + month_effect) > 0).")
    print(" As mandated by the Final Team Rulebook (Section 4, p. 5):")
    print(" 'An NB nonzero estimate for zero MODIS detections is NOT itself evidence")
    print("  that missing fires were recovered.'")
    print(" It reflects the baseline expectation of the seasonal month, NOT verified physical fires.")

    # 6. Evaluation on Held-out 2020 Data
    print("\n" + "=" * 75)
    print(" [6] Out-of-Sample Performance Comparison on Held-out 2020 Data (N=96 rows)")
    print("=" * 75)

    y_test = test_df["viirs_count"].to_numpy(dtype=np.float64)
    pred_nb = predict_negative_binomial(nb_bundle, test_df).to_numpy(dtype=np.float64)
    pred_ratio = predict_ratio(test_df["modis_count"], k=k_baseline).to_numpy(dtype=np.float64)

    # MAE
    mae_ratio = np.mean(np.abs(pred_ratio - y_test))
    mae_nb = np.mean(np.abs(pred_nb - y_test))

    # Poisson deviance
    eps = 1e-9
    def calc_dev(y_true, y_est):
        mu = np.maximum(y_est, eps)
        t1 = np.where(y_true > 0, y_true * np.log(np.maximum(y_true, eps) / mu), 0.0)
        t2 = y_true - mu
        return 2.0 * np.sum(t1 - t2)

    dev_ratio = calc_dev(y_test, pred_ratio)
    dev_nb = calc_dev(y_test, pred_nb)

    print(f"    Metric                         | Model 0 (Ratio) | Model 1 (NegBin)")
    print("    " + "-" * 65)
    print(f"    Mean Absolute Error (MAE)      | {mae_ratio:15.2f} | {mae_nb:16.2f}")
    print(f"    Poisson Deviance               | {dev_ratio:15.2f} | {dev_nb:16.2f}")
    print(f"    Total Actual VIIRS: {int(np.sum(y_test)):,}")
    print(f"    Total Estimated by Ratio:  {int(np.sum(pred_ratio)):,}")
    print(f"    Total Estimated by NegBin: {int(np.sum(pred_nb)):,}")

    print("\n" + "=" * 75)
    print(" DEMONSTRATION COMPLETE (Candidate Evaluation - No Production Selection Yet)")
    print("=" * 75)


if __name__ == "__main__":
    main()
