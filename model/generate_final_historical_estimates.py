"""FireChronicle - Final Negative Binomial (NB2) Model Training & Historical Prediction Pipeline.

This script executes the complete end-to-end reproducible workflow:
Phase 1: Verifies data selection and holdout results.
Phase 2: Trains the final NB2 model on the eligible 2012-2020 overlap population (excl. Jan 2012),
         and exports the fitted artifact and metadata reproducibly.
Phase 3 & 4: Generates genuine historical VIIRS-equivalent estimates for July 2002 - December 2011,
             strictly preserving NULLs, and exports the official 14-column Parquet contract.
Phase 5: Performs rigorous quality and consistency checks.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import duckdb
import joblib
import numpy as np
import pandas as pd

# Ensure model/ is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from negative_binomial import fit_negative_binomial, predict_negative_binomial

BASE_DIR = Path(__file__).resolve().parent
HISTORICAL_DIR = BASE_DIR / "data" / "historical"
REAL_DIR = BASE_DIR / "data" / "real"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
EVAL_DIR = BASE_DIR / "evaluation"

MODEL_VERSION = "firechronicle-nb2-v1.0"
SCIENTIFIC_STATUS = "EMPIRICALLY_CALIBRATED_RESEARCH_SPECIFICATION"

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


def train_final_model():
    """Train the final Negative Binomial model on the complete clean 2012-2020 paired population."""
    print("--- Phase 2: Training Final NB2 Model on Eligible 2012-2020 Overlap Data ---")
    years_real = list(range(2012, 2021))
    sparse_dfs = [
        duckdb.read_parquet(str(REAL_DIR / str(yr) / f"overlap_training_{yr}.parquet")).df()
        for yr in years_real
    ]
    all_sp = pd.concat(sparse_dfs, ignore_index=True)

    # Exclude truncated January 2012 (S-NPP VIIRS archive starts 2012-01-20)
    clean_sp = all_sp[~((all_sp["year"] == 2012) & (all_sp["month"] == 1))].copy()

    # Filter to paired-positive records
    paired = clean_sp[clean_sp["modis_count"].notna() & clean_sp["viirs_count"].notna()].copy()
    paired["modis_count"] = paired["modis_count"].astype(int)
    paired["viirs_count"] = paired["viirs_count"].astype(int)
    paired = paired[(paired["modis_count"] > 0) & (paired["viirs_count"] > 0)].copy()

    assert len(paired) == 23010, f"Expected 23,010 clean paired records, found {len(paired)}"

    # Fit genuine Negative Binomial (NB2 formulation)
    model_bundle = fit_negative_binomial(paired, reference_month=1)
    model_bundle["model_version"] = MODEL_VERSION
    model_bundle["scientific_status"] = SCIENTIFIC_STATUS
    model_bundle["is_production_ready"] = True
    model_bundle["trained_utc"] = datetime.now(timezone.utc).isoformat()
    model_bundle["training_population"] = {
        "description": "Clean paired-positive NASA FIRMS detections (modis_count > 0 and viirs_count > 0)",
        "years": [2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020],
        "exclusions": ["January 2012 excluded due to S-NPP VIIRS operational launch truncation"],
        "n_records": len(paired),
        "total_modis_detections": int(paired["modis_count"].sum()),
        "total_viirs_detections": int(paired["viirs_count"].sum()),
        "baseline_ratio_multiplier_k": float(paired["viirs_count"].sum() / paired["modis_count"].sum()),
    }

    # Save model artifact
    artifact_path = ARTIFACTS_DIR / "nb2_final_model.joblib"
    joblib.dump(model_bundle, artifact_path)
    print(f"Saved final model artifact to: {artifact_path}")

    # Produce model info JSON
    model_info = {
        "model_version": MODEL_VERSION,
        "model_type": "negative_binomial_nb2",
        "scientific_status": SCIENTIFIC_STATUS,
        "is_production_ready": True,
        "trained_utc": model_bundle["trained_utc"],
        "target": "VIIRS S-NPP-equivalent active fire hotspot detection count",
        "region_id": "BR-PA",
        "calibration_scale_km": 50,
        "spatial_crs": "EPSG:6933",
        "temporal_unit": "50 km block x calendar month x day/night pass",
        "training_population": model_bundle["training_population"],
        "dispersion_alpha": float(model_bundle["dispersion_alpha"]),
        "reference_month": model_bundle["reference_month"],
        "feature_schema": model_bundle["feature_names"],
        "fitted_coefficients_beta": model_bundle["params_exog"],
        "convergence": {
            "converged": model_bundle["converged"],
            "log_likelihood": float(model_bundle["log_likelihood"]),
            "aic": float(model_bundle["aic"]),
            "bic": float(model_bundle["bic"]),
            "nobs": model_bundle["n_obs"],
            "df_model": model_bundle["df_model"],
            "df_resid": model_bundle["df_resid"],
        },
        "evaluation_provenance": {
            "strategy_A_temporal_holdout": "Train 2012-2018, Test 2019-2020 (MAE=35.44, Dev=25.01, Bias=-11.50%)",
            "strategy_B_geographic_holdout": "Train 80% blocks, Test 20% blocks (MAE=35.79, Dev=20.95, Bias=+4.55%)",
            "verification_script": "model/evaluation/verify_reproducibility.py",
        },
        "scientific_limitations": [
            "Trained strictly on paired-positive observations (modis_count > 0 and viirs_count > 0).",
            "Conditional on Aqua MODIS detection: cannot infer fire activity where Aqua MODIS count is NULL or 0.",
            "Historical estimates represent satellite-detectable equivalents, not ground-truth burned area or fire perimeters.",
            "Unverified clear-sky telemetry: missing counts preserved as NULL, not confirmed zero fire activity."
        ]
    }

    for info_path in [ARTIFACTS_DIR / "model_info_final_nb2.json", BASE_DIR / "model_info_final_nb2.json"]:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(model_info, f, indent=2)
    print("Saved model info JSON to artifacts and root.")

    # Produce separate validation metrics JSON
    with open(EVAL_DIR / "multiyear_eval_results.json", "r", encoding="utf-8") as f:
        eval_results = json.load(f)

    val_metrics = {
        "model_version": MODEL_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "held_out_validation_provenance": "Evaluated on independent temporal and spatial partitions of 2012-2020 overlap collection",
        "strategy_A_temporal_holdout": eval_results["strategy_A_temporal_holdout"],
        "strategy_B_geographic_holdout": eval_results["strategy_B_geographic_holdout"],
        "sensitivity_experiment_zero_imputation": eval_results["sensitivity_experiment_zero_imputation"],
        "final_full_training_fit_statistics": {
            "n_records": model_bundle["n_obs"],
            "log_likelihood": float(model_bundle["log_likelihood"]),
            "aic": float(model_bundle["aic"]),
            "bic": float(model_bundle["bic"]),
            "dispersion_alpha": float(model_bundle["dispersion_alpha"]),
            "baseline_ratio_multiplier_k": model_bundle["training_population"]["baseline_ratio_multiplier_k"],
        }
    }

    for val_path in [ARTIFACTS_DIR / "validation_metrics_final_nb2.json", BASE_DIR / "validation_metrics_final_nb2.json"]:
        with open(val_path, "w", encoding="utf-8") as f:
            json.dump(val_metrics, f, indent=2)
    print("Saved validation metrics JSON to artifacts and root.")

    return model_bundle


def generate_historical_predictions(model_bundle):
    """Generate historical VIIRS-equivalent predictions for July 2002 - December 2011."""
    print("\n--- Phase 3 & 4: Generating Historical Predictions & Backend Handoff ---")
    hist_years = list(range(2002, 2012))
    panels = []
    for y in hist_years:
        fp_path = HISTORICAL_DIR / str(y) / f"historical_modis_block_month_{y}.parquet"
        df_y = duckdb.read_parquet(str(fp_path)).df()
        panels.append(df_y)

    all_hist = pd.concat(panels, ignore_index=True)
    assert len(all_hist) == 136320, f"Expected 136,320 historical rows, found {len(all_hist)}"

    # Exclude Jan-Jun 2002 from public export
    export_df = all_hist[~((all_hist["year"] == 2002) & (all_hist["month"] < 7))].copy()
    assert len(export_df) == 129504, f"Expected 129,504 export rows, found {len(export_df)}"

    pos_mask = export_df["modis_count"].notna() & (export_df["modis_count"] > 0)
    pos_df = export_df[pos_mask].copy()
    null_df = export_df[~pos_mask].copy()

    assert len(pos_df) == 26962, f"Expected 26,962 positive records, found {len(pos_df)}"
    assert len(null_df) == 102542, f"Expected 102,542 NULL records, found {len(null_df)}"

    # Predict expected counts on positive records using fitted NB2
    print(f"Applying frozen NB2 model to {len(pos_df):,} positive records...")
    pred_mu = predict_negative_binomial(model_bundle, pos_df, allow_unsupported_categories=False)
    pos_df["estimated_viirs_count"] = np.round(pred_mu.to_numpy(dtype=float), 2)
    pos_df["prediction_status"] = "ok_preliminary"

    # Assign null prediction status
    null_df["estimated_viirs_count"] = np.nan
    null_df["prediction_status"] = "missing_required_feature"

    # Combine back in exact canonical sorting
    combined = pd.concat([pos_df, null_df], ignore_index=True)
    combined = combined.sort_values(by=["year", "month", "block_ix", "block_iy", "daynight"]).reset_index(drop=True)

    combined["value_type"] = "estimated"
    combined["model_version"] = MODEL_VERSION
    combined["measurement_unit"] = "VIIRS_S-NPP-equivalent_detection_count"
    combined["calibration_scale_km"] = 50
    combined["coverage_status"] = combined["coverage_status"].fillna("unknown")

    # Build final 14-column contract table
    final_14 = combined[REQUIRED_14_COLUMNS].copy()
    final_14["block_ix"] = final_14["block_ix"].astype("int64")
    final_14["block_iy"] = final_14["block_iy"].astype("int64")
    final_14["year"] = final_14["year"].astype("int64")
    final_14["month"] = final_14["month"].astype("int64")
    final_14["calibration_scale_km"] = final_14["calibration_scale_km"].astype("int64")
    final_14["estimated_viirs_count"] = final_14["estimated_viirs_count"].astype("float64")

    # Export to official path: model/estimated_viirs_block_month.parquet
    out_path = BASE_DIR / "estimated_viirs_block_month.parquet"
    final_14.to_parquet(out_path, index=False)
    print(f"Exported official 14-column contract table to: {out_path}")
    print(f"Export shape: {final_14.shape}")

    return final_14, pos_df, null_df


def perform_phase5_checks(final_14, pos_df, null_df):
    """Perform all Phase 5 consistency and integrity checks."""
    print("\n--- Phase 5: Final Validation & Integrity Checks ---")

    # 1. Total rows
    assert len(final_14) == 129504, f"Row count mismatch: {len(final_14)} != 129,504"
    print("Check 1: Total rows exactly 129,504 (PASS)")

    # 2. Canonical blocks
    ref_grid = duckdb.read_parquet(str(REAL_DIR / "2019" / "para_50km_grid_canonical.parquet")).df()
    ref_blocks = sorted(ref_grid["block_id"].unique().tolist())
    export_blocks = sorted(final_14["block_id"].unique().tolist())
    assert export_blocks == ref_blocks, "Export blocks do not match canonical 568-block grid!"
    print("Check 2: All 568 canonical blocks present and match 2019 reference grid (PASS)")

    # 3. Composite key uniqueness
    dup_keys = final_14.duplicated(subset=["region_id", "block_id", "year", "month", "daynight"]).sum()
    assert dup_keys == 0, f"Found {dup_keys} duplicate composite keys!"
    print("Check 3: Composite keys strictly unique (0 duplicates) (PASS)")

    # 4. Temporal range: July 2002 to December 2011
    years_present = sorted(final_14["year"].unique().tolist())
    assert years_present == list(range(2002, 2012)), f"Unexpected years: {years_present}"
    m_2002 = sorted(final_14[final_14["year"] == 2002]["month"].unique().tolist())
    assert m_2002 == list(range(7, 13)), f"Unexpected 2002 months: {m_2002}"
    for y in range(2003, 2012):
        m_y = sorted(final_14[final_14["year"] == y]["month"].unique().tolist())
        assert m_y == list(range(1, 13)), f"Year {y} months not 1..12: {m_y}"
    print("Check 4: Temporal span strictly July 2002 - December 2011 (PASS)")

    # 5. Nonnegative, finite predictions
    preds = final_14["estimated_viirs_count"].dropna()
    assert (preds >= 0).all(), "Found negative prediction values!"
    assert np.isfinite(preds).all(), "Found non-finite prediction values!"
    print(f"Check 5: All {len(preds):,} predictions strictly non-negative and finite (PASS)")

    # 6. Null preservation
    null_preds = final_14["estimated_viirs_count"].isna().sum()
    assert null_preds == 102542, f"Null prediction count mismatch: {null_preds} != 102,542"
    assert (final_14[final_14["estimated_viirs_count"].isna()]["prediction_status"] == "missing_required_feature").all()
    print(f"Check 6: Exactly {null_preds:,} NULL predictions preserved with status 'missing_required_feature' (PASS)")

    # 7. Day/night integrity: passes are not aggregated into fabricated zeros
    dn_counts = final_14["daynight"].value_counts().to_dict()
    assert dn_counts == {"D": 64752, "N": 64752}, f"Unexpected daynight distribution: {dn_counts}"
    print(f"Check 7: Exactly 64,752 D and 64,752 N passes; no pass cross-contamination (PASS)")

    # 8. Reconcile all 26,962 positive input records
    assert len(pos_df) == 26962, f"Positive count mismatch: {len(pos_df)} != 26,962"
    pred_sum = float(pos_df["estimated_viirs_count"].sum())
    modis_sum = int(pos_df["modis_count"].sum())
    assert modis_sum == 617948, f"Historical MODIS detection sum mismatch: {modis_sum} != 617,948"
    print(f"Check 8: All 26,962 positive input records reconciled (Sum MODIS: 617,948; Sum Pred VIIRS: {pred_sum:,.2f}) (PASS)")

    # 9. Verify backend demo files untouched
    demo_hashes = {
        "estimated_viirs_block_month.parquet": "d59c49494d8d94a5a363dcb01bf422108b51b58a8f7603e228b7b0d8000fc6eb",
        "model_info.json": "4781c82a0dd2c9c8aebd1d0f0702f6895e375593a58bc6ce742f36c0783ec9ce",
        "validation_metrics.json": "ea1d7097d130b451bda821b8868af4e70a92dc300216d3ff010ad7b8341001dd"
    }
    import hashlib
    for fname, exp_hash in demo_hashes.items():
        p = BASE_DIR / "backend_integration_demo" / fname
        act_hash = hashlib.sha256(p.read_bytes()).hexdigest().lower()
        assert act_hash == exp_hash, f"Backend demo file {fname} modified!"
    print("Check 9: Backend integration demo files verified 100% untouched byte-for-byte (PASS)")

    print("\nAll Phase 5 checks passed cleanly!")


if __name__ == "__main__":
    model_bundle = train_final_model()
    final_14, pos_df, null_df = generate_historical_predictions(model_bundle)
    perform_phase5_checks(final_14, pos_df, null_df)
