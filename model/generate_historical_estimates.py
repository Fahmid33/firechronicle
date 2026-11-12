"""FireChronicle - Synthetic Historical Estimates Parquet Generator.

Generates the sample historical estimates table required by Rulebook Section 5 (p. 6):
'model/estimated_viirs_block_month.parquet' (14 columns)
Keyed by: region_id, block_id, year, month, daynight.
Retains estimation and coverage statuses.
"""

from pathlib import Path
import shutil
import numpy as np
import pandas as pd

from predict import predict_viirs_equivalent

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


def generate_synthetic_historical_parquet():
    base_dir = Path(__file__).resolve().parent
    handoff_dir = base_dir / "backend_integration_demo"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    # Use canonical Pará blocks from the frozen EPSG:6933 grid
    blocks = ["-100_-10", "-101_-10", "-100_-11", "-101_-11"]
    years = [2003, 2004, 2005]  # Illustrative pre-VIIRS Aqua MODIS years
    months = [7, 8, 9, 10]      # Peak dry season months
    daynights = ["D", "N"]

    records = []
    rng = np.random.default_rng(42)

    for yr in years:
        for mo in months:
            for blk in blocks:
                for dn in daynights:
                    parts = blk.split("_")
                    b_ix = int(parts[0])
                    b_iy = int(parts[1])

                    # Primary integration smoke test case: -100_-10, 2005, month 9
                    if blk == "-100_-10" and yr == 2005 and mo == 9:
                        if dn == "D":
                            m_count = 45  # Predicts 144.0 (k=3.20)
                            cov = "unknown"
                        else:
                            m_count = 15  # Predicts 48.0 (k=3.20)
                            cov = "unknown"
                    # NULL / status test case: -101_-10, 2005, month 9
                    elif blk == "-101_-10" and yr == 2005 and mo == 9:
                        if dn == "D":
                            m_count = 30  # Predicts 96.0
                            cov = "unknown"
                        else:
                            m_count = None  # Insufficient coverage
                            cov = "insufficient"
                    else:
                        base_rate = 50 if mo in (8, 9) else 15
                        if dn == "N":
                            base_rate = int(base_rate * 0.25)
                        m_count = int(rng.poisson(base_rate))
                        cov = "unknown"

                    input_rec = {
                        "region_id": "BR-PA",
                        "block_id": blk,
                        "year": yr,
                        "month": mo,
                        "daynight": dn,
                        "modis_count": m_count,
                        "coverage_status": cov,
                    }

                    pred = predict_viirs_equivalent(input_rec)

                    records.append({
                        "region_id": pred["region_id"],
                        "block_id": pred["block_id"],
                        "block_ix": b_ix,
                        "block_iy": b_iy,
                        "year": pred["year"],
                        "month": pred["month"],
                        "daynight": pred["daynight"],
                        "estimated_viirs_count": pred["estimated_viirs_count"],
                        "value_type": pred["value_type"],
                        "prediction_status": pred["prediction_status"],
                        "coverage_status": pred["coverage_status"],
                        "model_version": pred["model_version"],
                        "measurement_unit": pred["measurement_unit"],
                        "calibration_scale_km": pred["calibration_scale_km"],
                    })

    df_out = pd.DataFrame(records)
    df_out = df_out[REQUIRED_14_COLUMNS]
    df_out["block_ix"] = df_out["block_ix"].astype("int64")
    df_out["block_iy"] = df_out["block_iy"].astype("int64")
    df_out["year"] = df_out["year"].astype("int64")
    df_out["month"] = df_out["month"].astype("int64")
    df_out["calibration_scale_km"] = df_out["calibration_scale_km"].astype("int64")
    df_out["estimated_viirs_count"] = df_out["estimated_viirs_count"].astype("float64")

    # Export to Parquet in both root and handoff directory
    parquet_path = base_dir / "estimated_viirs_block_month.parquet"
    handoff_parquet = handoff_dir / "estimated_viirs_block_month.parquet"
    df_out.to_parquet(parquet_path, index=False)
    df_out.to_parquet(handoff_parquet, index=False)

    # Sync metadata JSON files to handoff dir
    for fname in ["model_info.json", "validation_metrics.json"]:
        shutil.copy2(base_dir / fname, handoff_dir / fname)

    print(f"Generated historical estimates Parquet at: {parquet_path}")
    print(f"Handoff folder: {handoff_dir}")
    print(f"Rows: {len(df_out)}")
    print(f"Columns (14): {list(df_out.columns)}")
    return parquet_path


if __name__ == "__main__":
    generate_synthetic_historical_parquet()
