"""FireChronicle - Demonstration of the Ratio-of-Totals Baseline Model.

Scientific Scope:
- Region: Pará, Brazil (BR-PA)
- Input Satellite: Aqua MODIS
- Reference Satellite: Suomi NPP VIIRS
- Modeling Unit: 50 km block x year x month x day/night (block_id formatted as "bx_by")
- Objective: Estimate VIIRS S-NPP-equivalent hotspot detection counts.

NOTE: This demonstration uses SYNTHETIC mock data for development and testing.
It does NOT claim to represent official NASA observations or validated models.
Canonical block IDs (e.g. "120_-50") are synthetic labels and are not derived
from actual Pará coordinates.
"""

import sys
from pathlib import Path

# Ensure model/ directory is in sys.path regardless of execution directory
base_dir = Path(__file__).resolve().parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

import pandas as pd
from ratio_baseline import fit_ratio, predict_ratio


def main():
    print("=" * 70)
    print(" FireChronicle: Ratio-of-Totals Baseline Model Demonstration")
    print(" Region: Pará, Brazil (BR-PA) | Aqua MODIS -> Suomi NPP VIIRS")
    print("=" * 70)

    # 1. Locate and load the synthetic overlap dataset
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "data" / "synthetic" / "synthetic_overlap_BR-PA.csv"

    print(f"\n[1] Loading synthetic dataset from:\n    {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"    Rows loaded: {len(df)}")
    print(f"    Columns: {list(df.columns)}")
    print(f"    Blocks represented: {sorted(df['block_id'].unique().tolist())}")
    print(f"    Years represented: {sorted(int(y) for y in df['year'].unique())}")
    print(f"    Coverage status: {df['coverage_status'].unique().tolist()} (coverage-unadjusted)")

    # 2. Split data: 2018-2019 as training, 2020 as hold-out evaluation
    # (Holds out complete year 2020 and independent block 121_-51)
    train_mask = df["year"].isin([2018, 2019])
    train_df = df[train_mask].copy()
    test_df = df[~train_mask].copy()

    print(f"\n[2] Training on 2018-2019 rows ({len(train_df)} rows)...")
    sum_modis_train = train_df["modis_count"].sum()
    sum_viirs_train = train_df["viirs_count"].sum()

    print(f"    Total Training MODIS Hotspot Detections: {sum_modis_train:,}")
    print(f"    Total Training VIIRS Hotspot Detections: {sum_viirs_train:,}")

    # 3. Fit the multiplier k on training data ONLY
    k = fit_ratio(train_df)
    print(f"\n[3] Fitted Multiplier (k = sum(VIIRS) / sum(MODIS)):")
    print(f"    k = {k:.4f}")
    print(f"    Physical Meaning: For every 1 Aqua MODIS hotspot detection in a 50 km block")
    print(f"    in Pará, this baseline estimates ~{k:.2f} VIIRS S-NPP-equivalent detections.")
    print(f"    (VIIRS detects more hotspots primarily because of its higher 375m spatial resolution).")

    # 4. Illustrative Historical Projection & Scientific Limitation of Zero-MODIS
    print("\n[4] Illustrative Historical Estimation (Pre-VIIRS Era):")
    print("    Suppose historical Aqua MODIS recorded the following dry season counts in Pará:")

    historical_cases = [
        {"scenario": "Low activity block (wet transition)", "modis_count": 0},
        {"scenario": "Moderate fire month (July)", "modis_count": 45},
        {"scenario": "Peak dry season month (September)", "modis_count": 180},
    ]

    for case in historical_cases:
        m_count = case["modis_count"]
        pred_viirs = predict_ratio(m_count, k)
        print(f"    - {case['scenario']}:")
        print(f"      MODIS count: {m_count:3d}  ==>  Estimated VIIRS-equivalent: {pred_viirs:7.2f}")

    print("\n    >>> SCIENTIFIC NOTE ON ZERO DETECTIONS (Rulebook p. 4 & 5):")
    print("    Notice that predict_ratio(0, k) = 0.0.")
    print("    This is an inherent mathematical limitation of the Ratio-of-Totals model,")
    print("    NOT evidence of zero fires or a verified fire-free observation.")
    print("    Because VIIRS 375m detects smaller/cooler fires that 1 km MODIS misses (M=0),")
    print("    Model 0 cannot recover missed S-NPP detections when MODIS count is zero.")

    # 5. Evaluate on Hold-out (2020 synthetic data)
    print(f"\n[5] Evaluating on Synthetic 2020 Hold-out Data ({len(test_df)} rows):")
    test_df["predicted_viirs"] = predict_ratio(test_df["modis_count"], k)
    sample_view = test_df[["block_id", "month", "daynight", "modis_count", "viirs_count", "predicted_viirs", "coverage_status"]].head(5)
    print(sample_view.to_string(index=False))

    print("\n" + "=" * 70)
    print(" DEMONSTRATION COMPLETE (Using Synthetic Data - Not NASA Official)")
    print("=" * 70)


if __name__ == "__main__":
    main()
