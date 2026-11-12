"""FireChronicle - Model Export Script.

Trains the Ratio-of-Totals baseline model on the synthetic Pará overlap dataset
(training years 2018-2019) and serializes the model artifact with metadata
to 'model/model.joblib' and 'model/artifacts/ratio_model.joblib'.

IMPORTANT:
This model is trained exclusively on synthetic test fixtures for pipeline
integration. It is NOT scientifically validated on real NASA Pará data.
"""

from pathlib import Path
import joblib
import pandas as pd

from ratio_baseline import fit_ratio
from validation_pipeline import validate_overlap_table

MODEL_VERSION = "ratio-baseline-v1.0-synthetic-demo"
MODEL_STATUS = "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED"


def export_baseline_model():
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "data" / "synthetic" / "synthetic_overlap_BR-PA.csv"

    df = pd.read_csv(csv_path)

    # Validate table and filter out ineligible coverage records (preserving coverage policy)
    eligible_df, audit = validate_overlap_table(df)

    # Train strictly on eligible 2018-2019 rows (preserving 2020 for held-out evaluation)
    train_mask = eligible_df["year"].isin([2018, 2019])
    train_df = eligible_df[train_mask].copy()

    k = fit_ratio(train_df)

    model_payload = {
        "model_type": "ratio_of_totals",
        "model_version": MODEL_VERSION,
        "model_status": MODEL_STATUS,
        "is_production_ready": False,
        "region_id": "BR-PA",
        "multiplier_k": float(k),
        "calibration_scale_km": 50,
        "training_years": [2018, 2019],
        "training_modis_sum": int(train_df["modis_count"].sum()),
        "training_viirs_sum": int(train_df["viirs_count"].sum()),
        "training_rows_count": len(train_df),
        "coverage_policy": audit["coverage_policy"],
        "unknown_coverage_rows_count": audit["unknown_coverage_records"],
        "measurement_unit": "VIIRS_S-NPP-equivalent_detection_count",
        "scientific_disclaimer": (
            "DEMO ONLY: Multiplier fitted exclusively on mock synthetic test fixtures. "
            "Not derived from or validated on actual NASA FIRMS Pará observations."
        )
    }

    # Export to root model/ for Backend B and to artifacts/ for versioned tracking
    out_paths = [
        base_dir / "model.joblib",
        base_dir / "artifacts" / "ratio_model.joblib",
    ]

    for p in out_paths:
        joblib.dump(model_payload, p)
        print(f"Exported baseline model artifact to: {p}")

    return model_payload


if __name__ == "__main__":
    payload = export_baseline_model()
    print(f"Multiplier k = {payload['multiplier_k']:.4f}")
    print(f"Status: {payload['model_status']}")
