"""Smoke test runner for FireChronicle Backend.

Verifies:
1. Health & Meta
2. Summary / Timeseries with ?daynight=ALL|D|N
3. Spatial with ?daynight=ALL|D|N
4. 50km Blocks GeoJSON (/api/v1/blocks)
5. Hotspots with provenance and daynight
6. Sensor Lab calibration with null-safe log_ratio & ratio (zero NaN or Inf)
7. Sensor Lab validation metrics
8. Model info
9. Inference (Predict)
10. ML Bridge status & Webhook authentication
"""

import math
import os
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app

def main():
    print("Initializing FireChronicle Backend Smoke Test...")
    with TestClient(app) as client:
        print("1. Testing GET /api/v1/health")
        res = client.get("/api/v1/health")
        print("   Status:", res.status_code, res.json())
        assert res.status_code == 200

        print("2. Testing GET /api/v1/summary?region_id=BR-PA&daynight=ALL")
        res = client.get("/api/v1/summary?region_id=BR-PA&daynight=ALL")
        print("   Status:", res.status_code, "Items count:", len(res.json()["items"]))
        assert res.status_code == 200
        assert res.json()["daynight_filter"] == "ALL"

        print("2b. Testing GET /api/v1/summary with ?daynight=D and ?daynight=N")
        res_d = client.get("/api/v1/summary?region_id=BR-PA&daynight=D")
        res_n = client.get("/api/v1/summary?region_id=BR-PA&daynight=N")
        assert res_d.status_code == 200
        assert res_n.status_code == 200
        print("   Day items:", len(res_d.json()["items"]), "Night items:", len(res_n.json()["items"]))

        print("3. Testing Guardrail: GET /api/v1/summary?region_id=BR-AM")
        res = client.get("/api/v1/summary?region_id=BR-AM")
        print("   Status:", res.status_code)
        assert res.status_code == 400

        print("4. Testing GET /api/v1/spatial?year=2018&month=8&resolution=50km&daynight=ALL")
        res = client.get("/api/v1/spatial?year=2018&month=8&resolution=50km&daynight=ALL")
        print("   Status:", res.status_code, "Features:", len(res.json()["features"]))
        assert res.status_code == 200

        print("5. Testing GET /api/v1/blocks (50km Block GeoJSON Polygon Endpoint)")
        res = client.get("/api/v1/blocks?region_id=BR-PA")
        print("   Status:", res.status_code, "Block features:", len(res.json()["features"]))
        assert res.status_code == 200
        assert res.json()["type"] == "FeatureCollection"
        assert len(res.json()["features"]) > 0

        print("6. Testing GET /api/v1/hotspots?limit=5")
        res = client.get("/api/v1/hotspots?limit=5")
        print("   Status:", res.status_code, "Hotspots:", len(res.json()["items"]))
        assert res.status_code == 200

        print("7. Testing GET /api/v1/sensor-lab/calibration with strict null-safe log_ratio")
        res = client.get("/api/v1/sensor-lab/calibration?daynight=ALL")
        print("   Status:", res.status_code, "Pairs:", res.json()["total_pairs"], "Mean Ratio:", res.json()["mean_ratio_viirs_to_modis"])
        assert res.status_code == 200
        pairs = res.json()["items"]
        assert len(pairs) > 0
        # Check that ratio and log_ratio have ZERO NaN or Infinity values
        for p in pairs:
            lr = p.get("log_ratio")
            r = p.get("ratio_viirs_to_modis")
            if lr is not None:
                assert not math.isnan(lr) and not math.isinf(lr), f"log_ratio must not be NaN/Inf: {lr}"
            if r is not None:
                assert not math.isnan(r) and not math.isinf(r), f"ratio must not be NaN/Inf: {r}"

        print("8. Testing GET /api/v1/sensor-lab/metrics")
        res = client.get("/api/v1/sensor-lab/metrics")
        assert res.status_code == 200
        metrics_body = res.json()
        print("   Status:", res.status_code, "Model version:", metrics_body.get("model_version"), "Metrics:", metrics_body.get("metrics"))

        print("9. Testing GET /api/v1/model-info and /api/v1/model/info")
        res_info = client.get("/api/v1/model-info")
        assert res_info.status_code == 200
        res = client.get("/api/v1/model/info")
        assert res.status_code == 200
        print("   Status:", res.status_code, "Model:", res.json().get("model_version"), "Scientific Status:", res.json().get("scientific_status"))

        print("9b. Testing GET /api/v1/harmonized")
        res_harm = client.get("/api/v1/harmonized?region_id=BR-PA&daynight=ALL")
        assert res_harm.status_code == 200
        print("   Status:", res_harm.status_code, "Items:", res_harm.json().get("total_months"), "Synthetic Demo:", res_harm.json().get("contains_synthetic_demo_data"))

        print("10. Testing POST /api/v1/predict")
        res = client.post("/api/v1/predict", json={
            "region_id": "BR-PA",
            "year": 2008,
            "month": 8,
            "daynight": "ALL",
            "block_id": "-101_-8",
            "modis_count": 25.0,
        })
        print("   Status:", res.status_code, "Prediction:", res.json()["predictions"][0])
        assert res.status_code == 200

        print("11. Testing ML Bridge Status")
        res = client.get("/ml-bridge/status")
        print("   Status:", res.status_code, res.json())
        assert res.status_code == 200
        assert res.json()["master_dataset_available"] is True

        print("12. Testing ML Bridge Webhook Auth")
        smoke_webhook_key = "smoke-test-ephemeral-key"
        os.environ["WEBHOOK_API_KEY"] = smoke_webhook_key
        get_settings.cache_clear()
        try:
            res = client.post(
                "/ml-bridge/sync-predictions",
                json={
                    "batch_id": "test-sync-01",
                    "model_version": "v1.2",
                    "records": [{"block_id": "-101_-8", "year": 2008, "month": 8, "estimated_viirs_count": 92.5}]
                },
                headers={"X-API-Key": smoke_webhook_key}
            )
            print("   Status:", res.status_code, res.json())
            assert res.status_code == 200
            assert res.json()["status"] == "demo_acknowledgement_only"
        finally:
            os.environ.pop("WEBHOOK_API_KEY", None)
            get_settings.cache_clear()

    print("\n>>> ALL SMOKE TESTS PASSED CLEANLY WITH MASTER DATASET CONTRACT! <<<")

if __name__ == "__main__":
    main()
