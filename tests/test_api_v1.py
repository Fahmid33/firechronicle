"""Comprehensive test suite for FireChronicle Pará (BR-PA) Backend.

Validates:
1. Shared Master Dataset ingestion & 12-col backend view derived automatically.
2. Release Geography Guardrail: Pará (BR-PA) ONLY. Rejection of BR-AM, BR-MT, etc.
3. Era Separation: mid-2002 to 2011 (estimated), 2012+ (observed), no MODIS+VIIRS addition.
4. Day/Night Filtering: ?daynight=ALL|D|N supported across summary, spatial, and calibration.
5. 50km Blocks GeoJSON Endpoint: GET /api/v1/blocks returns valid FeatureCollection.
6. Strict Null & Zero Integrity:
   - Missing data is None, never substituted with 0.
   - log_ratio = LN(viirs_count / modis_count) is null when modis <= 0 or counts missing.
   - Zero NaN or Infinity values.
7. All 7 required /api/v1 frontend contracts + boundary + health.
8. ML Bridge status, local prediction fallback, and webhook authentication.
"""

import math
import pytest
from fastapi.testclient import TestClient

from app.grid import (
    coords_to_block_id,
    coords_to_grid_id,
    epsg6933_to_lonlat,
    grid_id_to_block_id,
    lonlat_to_epsg6933,
)
from app.main import app
from app.schemas import PredictionStatus, ValueType

client = TestClient(app)


# =============================================================================
# 1. RELEASE GEOGRAPHY GUARDRAIL (PARÁ, BR-PA ONLY)
# =============================================================================

def test_summary_region_guardrail_success():
    """BR-PA should return 200 OK with Pará summary data."""
    response = client.get("/api/v1/summary?region_id=BR-PA")
    assert response.status_code == 200
    data = response.json()
    assert data["region_id"] == "BR-PA"
    assert data["region_name"] == "Pará, Brazil"
    assert len(data["items"]) > 0


def test_summary_region_guardrail_rejection():
    """Regions outside Pará (e.g. Amazonas BR-AM, Mato Grosso BR-MT) must be rejected."""
    for rejected_region in ["BR-AM", "BR-MT", "US-CA", "BRAZIL"]:
        response = client.get(f"/api/v1/summary?region_id={rejected_region}")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "BR-PA" in str(detail) or "unsupported" in str(detail).lower()


def test_spatial_region_guardrail_rejection():
    """Spatial queries outside BR-PA must be rejected."""
    response = client.get("/api/v1/spatial?region_id=BR-AM&year=2018&month=8")
    assert response.status_code == 400


def test_predict_region_guardrail_rejection():
    """Inference requests outside BR-PA must be rejected with prediction_status='unsupported_region'."""
    payload = {
        "region_id": "BR-AM",
        "year": 2008,
        "month": 8,
        "block_id": "-101_-8",
        "modis_count": 25.0,
    }
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["region_id"] == "BR-AM"
    assert data["predictions"][0]["prediction_status"] == PredictionStatus.UNSUPPORTED_REGION.value
    assert data["predictions"][0]["estimated_viirs_count"] is None


# =============================================================================
# 2. MEASUREMENT ERA & TEMPORAL SEPARATION
# =============================================================================

def test_era_separation_in_timeseries():
    """Historical era (2002-2011) must be 'estimated'; 2012+ must be 'observed' or gap."""
    response = client.get("/api/v1/summary?region_id=BR-PA&start_year=2003&end_year=2019&daynight=ALL")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) > 0
    assert data["contains_synthetic_demo_data"] is True
    assert data["synthetic_demo_notice"] is not None

    for pt in items:
        yr = pt["year"]
        if yr < 2012:
            assert pt["value_type"] == ValueType.ESTIMATED.value
            assert pt["is_harmonized_estimate"] is True
            assert pt["label"] in ("Estimated historical extrapolation", "Data gap or unobserved period")
        else:
            assert pt["value_type"] in (ValueType.OBSERVED.value, ValueType.PROVISIONAL_NRT.value)
            assert pt["is_harmonized_estimate"] is False
            assert "Observed" in pt["label"] or "Provisional" in pt["label"] or "gap" in pt["label"]


def test_harmonized_endpoint_and_null_all_isolation():
    """Verify /api/v1/harmonized alias, synthetic demo flags, and strict D+N completeness for ALL."""
    res_all = client.get("/api/v1/harmonized?region_id=BR-PA&start_year=2005&end_year=2005&daynight=ALL")
    res_d = client.get("/api/v1/harmonized?region_id=BR-PA&start_year=2005&end_year=2005&daynight=D")
    res_n = client.get("/api/v1/harmonized?region_id=BR-PA&start_year=2005&end_year=2005&daynight=N")
    assert res_all.status_code == res_d.status_code == res_n.status_code == 200

    all_map = {pt["period"]: pt for pt in res_all.json()["items"]}
    d_map = {pt["period"]: pt for pt in res_d.json()["items"]}
    n_map = {pt["period"]: pt for pt in res_n.json()["items"]}

    # 2005-08 has complete D & N across all blocks
    assert all_map["2005-08"]["count"] is not None
    assert all_map["2005-08"]["is_synthetic_demo"] is True
    assert all_map["2005-08"]["model_version"] == "ratio-baseline-v1.0-synthetic-demo"
    assert math.isclose(all_map["2005-08"]["count"], round(d_map["2005-08"]["count"] + n_map["2005-08"]["count"], 1), abs_tol=0.2)

    # 2005-09 has block -101_-10 with N=NULL -> N and ALL must preserve NULL (never coerce NULL to 0)
    assert d_map["2005-09"]["count"] is not None
    assert n_map["2005-09"]["count"] is None
    assert n_map["2005-09"]["prediction_status"] == PredictionStatus.INSUFFICIENT_COVERAGE.value
    assert all_map["2005-09"]["count"] is None
    assert all_map["2005-09"]["prediction_status"] == PredictionStatus.INSUFFICIENT_COVERAGE.value
    assert all_map["2005-09"]["coverage_status"] == "insufficient"


# =============================================================================
# 3. DAY/NIGHT FILTERING (?daynight=ALL|D|N)
# =============================================================================

def test_daynight_summary_filter():
    """Test ?daynight filter on summary timeseries."""
    res_all = client.get("/api/v1/summary?region_id=BR-PA&daynight=ALL")
    res_d = client.get("/api/v1/summary?region_id=BR-PA&daynight=D")
    res_n = client.get("/api/v1/summary?region_id=BR-PA&daynight=N")

    assert res_all.status_code == 200
    assert res_d.status_code == 200
    assert res_n.status_code == 200

    items_all = res_all.json()["items"]
    items_d = res_d.json()["items"]
    items_n = res_n.json()["items"]

    assert len(items_all) == len(items_d) == len(items_n)
    # Check that day and night counts are individually less than or equal to ALL
    for pt_all, pt_d, pt_n in zip(items_all, items_d, items_n):
        if pt_all["count"] is not None and pt_d["count"] is not None and pt_n["count"] is not None:
            assert pt_d["count"] <= pt_all["count"]
            assert pt_n["count"] <= pt_all["count"]


def test_daynight_spatial_filter():
    """Test ?daynight filter on spatial grid."""
    res_d = client.get("/api/v1/spatial?region_id=BR-PA&year=2019&month=8&daynight=D")
    res_n = client.get("/api/v1/spatial?region_id=BR-PA&year=2019&month=8&daynight=N")
    assert res_d.status_code == 200
    assert res_n.status_code == 200
    assert res_d.json()["metadata"]["daynight_filter"] == "D"
    assert res_n.json()["metadata"]["daynight_filter"] == "N"


# =============================================================================
# 4. 50KM BLOCKS GEOJSON (GET /api/v1/blocks)
# =============================================================================

def test_get_blocks_endpoint():
    """Test GET /api/v1/blocks endpoint returning 50km block polygons."""
    res = client.get("/api/v1/blocks?region_id=BR-PA")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0

    first_block = data["features"][0]
    assert first_block["type"] == "Feature"
    assert "geometry" in first_block
    assert first_block["geometry"]["type"] == "Polygon"
    assert "properties" in first_block
    assert first_block["properties"]["region_id"] == "BR-PA"
    assert first_block["properties"]["resolution"] == "50km"


def test_get_blocks_unsupported_region():
    """Requesting blocks outside BR-PA must return 400 Bad Request."""
    res = client.get("/api/v1/blocks?region_id=BR-AM")
    assert res.status_code == 400


# =============================================================================
# 5. STRICT NULL & ZERO INTEGRITY & NULL-SAFE log_ratio
# =============================================================================

def test_calibration_null_safe_log_ratio():
    """Verify log_ratio = LN(viirs_count / modis_count) returns NULL when modis<=0, with NO NaN/Inf."""
    res = client.get("/api/v1/sensor-lab/calibration?region_id=BR-PA&daynight=ALL")
    assert res.status_code == 200
    data = res.json()
    pairs = data["items"]
    assert len(pairs) > 0

    for p in pairs:
        m = p.get("modis_count")
        v = p.get("viirs_count")
        lr = p.get("log_ratio")
        r = p.get("ratio_viirs_to_modis")

        # No NaN or Infinity allowed
        if lr is not None:
            assert not math.isnan(lr)
            assert not math.isinf(lr)
        if r is not None:
            assert not math.isnan(r)
            assert not math.isinf(r)

        # Strict null integrity: when modis is None or <= 0, ratio and log_ratio must be None
        if m is None or m <= 0:
            assert r is None
            assert lr is None

        # When viirs is None or <= 0, log_ratio must be None
        if v is None or v <= 0:
            assert lr is None


def test_predict_precomputed_historical_retrieval():
    """Precomputed historical predictions (pre-2012) are served instantly from parquet."""
    payload = {
        "region_id": "BR-PA",
        "year": 2005,
        "month": 8,
        "block_id": "-100_-10",
    }
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["is_synthetic_demo"] is True
    pred = body["predictions"][0]
    assert pred["prediction_status"] == PredictionStatus.OK_PRELIMINARY.value
    assert pred["estimated_viirs_count"] is not None
    assert pred["estimated_count"] == pred["estimated_viirs_count"]
    assert pred["model_version"] == "ratio-baseline-v1.0-synthetic-demo"
    assert pred["measurement_unit"] == "VIIRS_S-NPP-equivalent_detection_count"
    assert pred["is_synthetic_demo"] is True

    # Block -101_-10 in 2005-09 has D=96.0 and N=NULL -> N and ALL must return None (NOT 96.0)
    res_d = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 9, "daynight": "D", "block_id": "-101_-10"})
    res_n = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 9, "daynight": "N", "block_id": "-101_-10"})
    res_all = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 9, "daynight": "ALL", "block_id": "-101_-10"})
    assert res_d.json()["predictions"][0]["estimated_count"] == 96.0
    assert res_n.json()["predictions"][0]["estimated_count"] is None
    assert res_n.json()["predictions"][0]["prediction_status"] == PredictionStatus.INSUFFICIENT_COVERAGE.value
    assert res_n.json()["predictions"][0]["coverage_status"] == "insufficient"
    assert res_all.json()["predictions"][0]["estimated_count"] is None
    assert res_all.json()["predictions"][0]["prediction_status"] == PredictionStatus.INSUFFICIENT_COVERAGE.value
    assert res_all.json()["predictions"][0]["coverage_status"] == "insufficient"


def test_predict_missing_feature_null_preservation():
    """Missing modis_count for un-precomputed block must return prediction_status='missing_required_feature' with None."""
    payload = {
        "region_id": "BR-PA",
        "year": 2008,
        "month": 8,
        "block_id": "9999_9999",  # Non-existent block without modis_count
    }
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    pred = response.json()["predictions"][0]
    assert pred["prediction_status"] == PredictionStatus.MISSING_REQUIRED_FEATURE.value
    assert pred["estimated_viirs_count"] is None


def test_predict_pre_aqua_period_guardrail():
    """Pre-July 2002 requests must return prediction_status='unsupported_period'."""
    payload = {
        "region_id": "BR-PA",
        "year": 2001,
        "month": 8,
        "block_id": "-101_-8",
        "modis_count": 10.0,
    }
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    pred = response.json()["predictions"][0]
    assert pred["prediction_status"] == PredictionStatus.UNSUPPORTED_PERIOD.value
    assert pred["estimated_viirs_count"] is None


# =============================================================================
# 6. ALL 7 REQUIRED CONTRACT ENDPOINTS
# =============================================================================

def test_endpoint_1_summary():
    """Contract: GET /api/v1/summary."""
    res = client.get("/api/v1/summary?region_id=BR-PA")
    assert res.status_code == 200
    d = res.json()
    assert d["region_id"] == "BR-PA"
    assert "items" in d and len(d["items"]) > 0


def test_endpoint_2_spatial():
    """Contract: GET /api/v1/spatial enforcing strict 50km vs 10km separation."""
    for yr, mo in ((2019, 9), (2005, 8)):
        res = client.get(f"/api/v1/spatial?region_id=BR-PA&year={yr}&month={mo}&resolution=50km")
        assert res.status_code == 200
        d = res.json()
        assert d["type"] == "FeatureCollection"
        assert "features" in d and len(d["features"]) > 0
        props = d["features"][0]["properties"]
        assert props["block_id"] is not None
        assert props["block_ix"] is not None
        assert props["block_iy"] is not None
        # Strict 50km vs 10km separation: 10km cell fields must remain null on 50km layers
        assert props["grid_id"] is None
        assert props["ix"] is None
        assert props["iy"] is None

    # Verify 2005-09 spatial preserves NULL on -101_-10 for N and ALL
    res_sp_all = client.get("/api/v1/spatial?region_id=BR-PA&year=2005&month=9&resolution=50km&daynight=ALL")
    assert res_sp_all.status_code == 200
    sp_data = res_sp_all.json()
    assert sp_data["metadata"]["is_synthetic_demo"] is True
    by_block = {f["properties"]["block_id"]: f["properties"] for f in sp_data["features"]}
    assert by_block["-101_-10"]["count"] is None
    assert by_block["-101_-10"]["prediction_status"] == PredictionStatus.INSUFFICIENT_COVERAGE.value
    assert by_block["-101_-10"]["coverage_status"] == "insufficient"
    assert by_block["-100_-10"]["count"] is not None


def test_endpoint_3_hotspots():
    """Contract: GET /api/v1/hotspots."""
    res = client.get("/api/v1/hotspots?region_id=BR-PA&limit=15&offset=0")
    assert res.status_code == 200
    d = res.json()
    assert d["region_id"] == "BR-PA"
    assert len(d["items"]) <= 15


def test_endpoint_4_calibration():
    """Contract: GET /api/v1/sensor-lab/calibration."""
    res = client.get("/api/v1/sensor-lab/calibration?region_id=BR-PA")
    assert res.status_code == 200
    d = res.json()
    assert d["region_id"] == "BR-PA"
    assert d["total_pairs"] > 0
    assert d["correlation_r"] > 0.8
    assert d["mean_ratio_viirs_to_modis"] > 2.0


def test_endpoint_5_metrics():
    """Contract: GET /api/v1/sensor-lab/metrics serving Data Scientist validation_metrics.json."""
    res = client.get("/api/v1/sensor-lab/metrics")
    assert res.status_code == 200
    d = res.json()
    assert d["model_version"] == "ratio-baseline-v1.0-synthetic-demo"
    assert "metrics" in d
    assert "mean_absolute_error" in d["metrics"]
    assert d["fitted_multiplier_k"] == 3.2


def test_endpoint_6_model_info():
    """Contract: GET /api/v1/model-info and /api/v1/model/info serving combined JSON metadata."""
    for url in ("/api/v1/model-info", "/api/v1/model/info"):
        res = client.get(url)
        assert res.status_code == 200
        d = res.json()
        assert d["model_version"] == "ratio-baseline-v1.0-synthetic-demo"
        assert d["is_production_ready"] is False
        assert "features" in d and "modis_count" in d["features"]
        assert "limitations" in d and len(d["limitations"]) > 0
        assert d["validation_metrics"] is not None
        assert "metrics" in d["validation_metrics"]


def test_ml_handoff_estimated_count_alias_and_50km_aggregation():
    """Verify estimated_count DuckDB alias, strict D+N completeness, 50km block keys, and nullable statuses."""
    from app.db import get_db
    from app.schemas import PredictionSyncRecord, SingleBlockPrediction

    db = get_db()
    row = db.con.execute(
        "SELECT block_id, block_ix, block_iy, estimated_viirs_count, estimated_count "
        "FROM estimated_viirs_block_month LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[4] == row[3]

    # Strict 50km enforcement even when 10km is requested
    res_sp = client.get("/api/v1/spatial?region_id=BR-PA&year=2005&month=8&resolution=10km")
    assert res_sp.status_code == 200
    assert res_sp.json()["metadata"]["effective_resolution"] == "50km"

    # SQL D + N SUM aggregation check for precomputed historical estimates when both D & N are valid
    res_d = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 8, "daynight": "D", "block_id": "-100_-10"})
    res_n = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 8, "daynight": "N", "block_id": "-100_-10"})
    res_all = client.post("/api/v1/predict", json={"region_id": "BR-PA", "year": 2005, "month": 8, "daynight": "ALL", "block_id": "-100_-10"})
    assert res_d.status_code == res_n.status_code == res_all.status_code == 200
    p_d = res_d.json()["predictions"][0]
    p_n = res_n.json()["predictions"][0]
    p_all = res_all.json()["predictions"][0]
    assert p_all["block_ix"] == -100 and p_all["block_iy"] == -10
    assert math.isclose(p_all["estimated_count"], round(p_d["estimated_count"] + p_n["estimated_count"], 1), abs_tol=0.2)

    # Pydantic nullable prediction and status integrity
    null_pred = SingleBlockPrediction(block_id="-100_-10", year=2005, month=8)
    assert null_pred.estimated_viirs_count is None
    assert null_pred.estimated_count is None
    assert null_pred.prediction_status is None
    assert null_pred.coverage_status is None
    null_sync = PredictionSyncRecord(block_id="-100_-10", year=2005, month=8)
    assert null_sync.estimated_viirs_count is None
    assert null_sync.prediction_status is None
    assert null_sync.coverage_status is None


def test_endpoint_7_predict():
    """Contract: POST /api/v1/predict."""
    payload = {
        "region_id": "BR-PA",
        "year": 2005,
        "month": 9,
        "block_id": "-101_-8",
        "modis_count": 35.0,
    }
    res = client.post("/api/v1/predict", json=payload)
    assert res.status_code == 200
    d = res.json()
    assert d["total_predictions"] == 1
    assert d["predictions"][0]["prediction_status"] == PredictionStatus.OK_PRELIMINARY.value


def test_ml_predict_integration_hook():
    """Contract: POST /api/v1/ml/predict integration hook for ML batch inference."""
    payload = {
        "region_id": "BR-PA",
        "year": 2005,
        "month": 9,
        "block_id": "-101_-8",
        "modis_count": 35.0,
    }
    res = client.post("/api/v1/ml/predict", json=payload)
    assert res.status_code == 200
    assert res.json()["predictions"][0]["prediction_status"] == PredictionStatus.OK_PRELIMINARY.value


def test_companion_boundary_endpoint():
    """Companion: GET /api/v1/boundary returns official IBGE Pará GeoJSON."""
    res = client.get("/api/v1/boundary")
    assert res.status_code == 200
    d = res.json()
    assert d["type"] == "FeatureCollection"
    assert d["features"][0]["properties"]["region_id"] == "BR-PA"


# =============================================================================
# 7. ML BRIDGE STATUS & WEBHOOK AUTHENTICATION
# =============================================================================

def test_ml_bridge_status():
    """Check ML bridge connectivity probe."""
    res = client.get("/ml-bridge/status")
    assert res.status_code == 200
    d = res.json()
    assert d["local_fallback_available"] is True
    assert d["master_dataset_available"] is True


def test_ml_bridge_sync_webhook_auth_failure():
    """Webhook requests without API key must be 401."""
    payload = {
        "batch_id": "batch-001",
        "model_version": "v1.2",
        "records": [{"block_id": "-101_-8", "year": 2005, "month": 8, "estimated_viirs_count": 55.4}],
    }
    res = client.post("/ml-bridge/sync-predictions", json=payload)
    assert res.status_code == 401


def test_ml_bridge_sync_webhook_auth_success():
    """Webhook requests with valid API key succeed."""
    payload = {
        "batch_id": "batch-002",
        "model_version": "v1.2",
        "records": [{"block_id": "-101_-8", "year": 2005, "month": 8, "estimated_viirs_count": 55.4}],
    }
    valid_key = "firechronicle_webhook_sync_key_2026"

    res = client.post(
        "/ml-bridge/sync-predictions",
        json=payload,
        headers={"X-API-Key": valid_key},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
