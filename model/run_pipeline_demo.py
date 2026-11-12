"""FireChronicle - Evaluation Pipeline Demonstration Runner.

Executes the dual-strategy (temporal and geographic) holdout evaluation on the
576-row synthetic multiblock dataset and writes 'model/demo_model_comparison.json'.
"""

from pathlib import Path
import json
import pandas as pd

from validation_pipeline import run_evaluation_pipeline


def main():
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "data" / "synthetic" / "synthetic_eval_multiblock_BR-PA.csv"
    out_json = base_dir / "demo_model_comparison.json"

    print("=" * 75)
    print(" FireChronicle: Reproducible Model Evaluation Pipeline Demo")
    print(" Dual-Strategy Holdout: Temporal & Geographic Split Evaluation")
    print("=" * 75)

    print(f"\n[1] Loading paired synthetic multiblock table from:\n    {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"\n[2] Executing pipeline and generating report...")
    report = run_evaluation_pipeline(df, output_report_path=out_json)

    print("\n[3] Temporal Holdout Results (Train 2017-2019, Test 2020):")
    temp_res = report["strategy_A_temporal_holdout"]
    m0_temp = temp_res["model_0_ratio_of_totals"]
    m1_temp = temp_res["model_1_negative_binomial"]
    print(f"    {'Metric':<30} | {'Model 0 (Ratio)':<18} | {'Model 1 (NegBin)':<18}")
    print("    " + "-" * 72)
    print(f"    {'Mean Absolute Error (MAE)':<30} | {m0_temp['mean_absolute_error']:<18.4f} | {m1_temp['mean_absolute_error']:<18.4f}")
    print(f"    {'Mean Poisson Deviance':<30} | {m0_temp['mean_poisson_deviance']:<18.4f} | {m1_temp['mean_poisson_deviance']:<18.4f}")
    print(f"    {'Aggregate Bias %':<30} | {m0_temp['aggregate_count_bias_percent']:<18.2f}% | {m1_temp['aggregate_count_bias_percent']:<18.2f}%")
    print(f"    {'Monthly Profile Corr (r)':<30} | {m0_temp['seasonal_agreement']['monthly_profile_correlation']:<18.4f} | {m1_temp['seasonal_agreement']['monthly_profile_correlation']:<18.4f}")
    print(f"    {'Peak Month Match':<30} | {str(m0_temp['seasonal_agreement']['peak_month_match']):<18} | {str(m1_temp['seasonal_agreement']['peak_month_match']):<18}")

    print("\n[4] Geographic Holdout Results (Train 4 blocks, Test 2 disjoint blocks):")
    geo_res = report["strategy_B_geographic_holdout"]
    m0_geo = geo_res["model_0_ratio_of_totals"]
    m1_geo = geo_res["model_1_negative_binomial"]
    print(f"    {'Metric':<30} | {'Model 0 (Ratio)':<18} | {'Model 1 (NegBin)':<18}")
    print("    " + "-" * 72)
    print(f"    {'Mean Absolute Error (MAE)':<30} | {m0_geo['mean_absolute_error']:<18.4f} | {m1_geo['mean_absolute_error']:<18.4f}")
    print(f"    {'Mean Poisson Deviance':<30} | {m0_geo['mean_poisson_deviance']:<18.4f} | {m1_geo['mean_poisson_deviance']:<18.4f}")
    print(f"    {'Aggregate Bias %':<30} | {m0_geo['aggregate_count_bias_percent']:<18.2f}% | {m1_geo['aggregate_count_bias_percent']:<18.2f}%")
    print(f"    {'Monthly Profile Corr (r)':<30} | {m0_geo['seasonal_agreement']['monthly_profile_correlation']:<18.4f} | {m1_geo['seasonal_agreement']['monthly_profile_correlation']:<18.4f}")
    print(f"    {'Peak Month Match':<30} | {str(m0_geo['seasonal_agreement']['peak_month_match']):<18} | {str(m1_geo['seasonal_agreement']['peak_month_match']):<18}")

    print("\n" + "=" * 75)
    print(f" Status: {report['model_selection_status']}")
    print("=" * 75)


if __name__ == "__main__":
    main()
