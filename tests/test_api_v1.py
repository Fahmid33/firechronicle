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


def test_ml_bridge_sync_webhook_auth_success(monkeypatch):
    """Webhook requests with valid environment-configured API key return demo_acknowledgement_only."""
    from app.config import get_settings

    test_key = "pytest-ephemeral-webhook-token"
    monkeypatch.setenv("WEBHOOK_API_KEY", test_key)
    get_settings.cache_clear()
    try:
        payload = {
            "batch_id": "batch-002",
            "model_version": "v1.2",
            "records": [{"block_id": "-101_-8", "year": 2005, "month": 8, "estimated_viirs_count": 55.4}],
        }
        res = client.post(
            "/ml-bridge/sync-predictions",
            json=payload,
            headers={"X-API-Key": test_key},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "demo_acknowledgement_only"
        assert "pending" in body["message"].lower()
    finally:
        monkeypatch.delenv("WEBHOOK_API_KEY", raising=False)
        get_settings.cache_clear()


# =============================================================================
# 8. PRODUCTION HARDENING & MULTI-YEAR VERIFICATION TESTS
# =============================================================================

def test_security_settings_no_hardcoded_secrets_and_cors(monkeypatch):
    """Ensure API keys default to None (no hardcoded secrets) and CORS forbids wildcard '*'."""
    from fastapi.middleware.cors import CORSMiddleware
    from app.config import Settings

    monkeypatch.delenv("ML_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_API_KEY", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.ML_MODEL_API_KEY is None
    assert s.WEBHOOK_API_KEY is None
    assert s.FRONTEND_URL == "http://localhost:3000"
    assert "*" not in s.CORS_ORIGINS

    cors_mw = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors_mw) == 1
    allow_origins = cors_mw[0].kwargs.get("allow_origins", [])
    assert "*" not in allow_origins
    assert len(allow_origins) >= 1


def test_multi_year_loading_and_2012_bounds_null_integrity():
    """Verify DuckDB glob multi-year load, canonical LEFT JOIN, 2012 totals, and strict NULL preservation."""
    from app.db import get_db

    db = get_db()
    years_present = [
        r[0]
        for r in db.con.execute("SELECT DISTINCT year FROM firechronicle_master ORDER BY year").fetchall()
    ]
    assert 2012 in years_present
    assert 2019 in years_present

    # Zero duplicate keys across entire multi-year panel
    total_rows, unique_keys = db.con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (region_id, block_id, year, month, daynight)) FROM firechronicle_master"
    ).fetchone()
    assert total_rows == unique_keys

    # Strict 2012 dense-panel canonical join integrity & NULL counts (must match verify.py)
    row_2012 = db.con.execute("""
        SELECT
            COUNT(*),
            COUNT(DISTINCT block_id),
            SUM(modis_count),
            SUM(viirs_count),
            COUNT(*) FILTER (WHERE modis_count IS NULL),
            COUNT(*) FILTER (WHERE viirs_count IS NULL)
        FROM firechronicle_master
        WHERE year = 2012
    """).fetchone()
    assert row_2012 == (13632, 568, 41074, 243498, 11024, 9114)

    # API-level 2012 totals check on summary & calibration endpoints
    sum_2012 = client.get("/api/v1/summary?region_id=BR-PA&start_year=2012&end_year=2012&daynight=ALL")
    assert sum_2012.status_code == 200
    viirs_sum_api = sum(pt["count"] for pt in sum_2012.json()["items"] if pt["count"] is not None)
    assert viirs_sum_api == 243498.0

    cal_2012 = client.get("/api/v1/sensor-lab/calibration?region_id=BR-PA&start_year=2012&end_year=2012&daynight=ALL")
    assert cal_2012.status_code == 200
    cal_items = cal_2012.json()["items"]
    assert sum(p["modis_count"] for p in cal_items if p["modis_count"] is not None) == 41074.0
    assert sum(p["viirs_count"] for p in cal_items if p["viirs_count"] is not None) == 243498.0

    # Spatial 2012-01 returns all 568 canonical blocks preserving None (not 0) for missing detections
    sp_jan = client.get("/api/v1/spatial?region_id=BR-PA&year=2012&month=1&resolution=50km&daynight=ALL")
    assert sp_jan.status_code == 200
    sp_features = sp_jan.json()["features"]
    assert len(sp_features) == 568
    null_blocks = [f for f in sp_features if f["properties"]["count"] is None]
    non_null_sum = sum(f["properties"]["count"] for f in sp_features if f["properties"]["count"] is not None)
    assert len(null_blocks) > 0
    assert non_null_sum == 445.0


def test_2012_partial_coverage_metadata_passthrough():
    """Verify coverage_status flows unaltered ('unknown', never 'verified') with Jan 2012 partial availability."""
    res = client.get("/api/v1/summary?region_id=BR-PA&start_year=2012&end_year=2012&daynight=ALL")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 12
    for pt in items:
        assert pt["coverage_status"] == "unknown"
        assert pt["coverage_status"] != "verified"

    jan_pt = [pt for pt in items if pt["period"] == "2012-01"][0]
    assert jan_pt["coverage_notes"] is not None
    assert "2012-01-20" in jan_pt["coverage_notes"]

    sp_jan = client.get("/api/v1/spatial?region_id=BR-PA&year=2012&month=1&resolution=50km&daynight=ALL")
    assert sp_jan.status_code == 200
    for feat in sp_jan.json()["features"]:
        assert feat["properties"]["coverage_status"] == "unknown"
        assert feat["properties"]["coverage_notes"] is not None
        assert "2012-01-20" in feat["properties"]["coverage_notes"]


def test_strict_timeline_separation_pre_and_post_2012():
    """Verify strict timeline era boundary between pre-2012 estimates and 2012+ observed VIIRS."""
    res = client.get("/api/v1/harmonized?region_id=BR-PA&start_year=2003&end_year=2020&daynight=ALL")
    assert res.status_code == 200
    items = res.json()["items"]
    pre_2012 = [pt for pt in items if pt["year"] < 2012]
    post_2012 = [pt for pt in items if pt["year"] >= 2012]
    assert len(pre_2012) > 0 and len(post_2012) > 0
    for pt in pre_2012:
        assert pt["value_type"] == ValueType.ESTIMATED.value
        assert pt["is_harmonized_estimate"] is True
    for pt in post_2012:
        assert pt["value_type"] in (ValueType.OBSERVED.value, ValueType.PROVISIONAL_NRT.value)
        assert pt["is_harmonized_estimate"] is False


def test_production_predict_fallback_guard(monkeypatch):
    """Ensure local 3.82 heuristic raises NotImplementedError when running in production mode."""
    from app.config import get_settings
    from scripts.predict import predict_single_block

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(NotImplementedError, match="Real ML model not yet connected"):
            predict_single_block("BR-PA", 2005, 8, "-100_-10", modis_count=25.0)
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        get_settings.cache_clear()


def test_generate_fixtures_safety_guard():
    """Verify generate_fixtures cannot overwrite real NASA/IBGE/ML metadata artifacts."""
    from scripts.generate_fixtures import _safe_synthetic_output_path

    for forbidden in (
        "firechronicle_master.parquet",
        "firechronicle_master_2012.parquet",
        "para_boundary.geojson",
        "model_info.json",
        "validation_metrics.json",
    ):
        with pytest.raises(PermissionError):
            _safe_synthetic_output_path(forbidden)

    ok_path = _safe_synthetic_output_path("synthetic_test_export.parquet")
    assert ok_path.name == "synthetic_test_export.parquet"


def test_nested_9yr_glob_loading_and_expected_totals(tmp_path):
    """Verify recursive nested real/YYYY/*.parquet glob loads 2012-2020 and enforces 344,071 / 2,196,531 totals."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from app.config import Settings
    from app.db import DuckDBManager, EXPECTED_2012_2020_MODIS_TOTAL, EXPECTED_2012_2020_VIIRS_TOTAL

    real_root = tmp_path / "real"
    years = list(range(2012, 2021))
    modis_per_yr = [38230] * 8 + [EXPECTED_2012_2020_MODIS_TOTAL - 38230 * 8]
    viirs_per_yr = [244059] * 8 + [EXPECTED_2012_2020_VIIRS_TOTAL - 244059 * 8]

    for yr, m_val, v_val in zip(years, modis_per_yr, viirs_per_yr):
        yr_dir = real_root / str(yr)
        yr_dir.mkdir(parents=True, exist_ok=True)
        tbl = pa.table({
            "region_id": ["BR-PA"],
            "block_id": ["-100_-10"],
            "block_ix": pa.array([-100], type=pa.int32()),
            "block_iy": pa.array([-10], type=pa.int32()),
            "year": pa.array([yr], type=pa.int32()),
            "month": pa.array([8], type=pa.int32()),
            "daynight": ["D"],
            "modis_count": pa.array([m_val], type=pa.int64()),
            "viirs_count": pa.array([v_val], type=pa.int64()),
            "modis_frp_sum": pa.array([100.0], type=pa.float64()),
            "viirs_frp_sum": pa.array([200.0], type=pa.float64()),
            "coverage_status": ["unknown"],
            "processing_status": ["preliminary"],
            "modis_source_version": ["6.2"],
            "viirs_source_version": ["2"],
        })
        pq.write_table(tbl, yr_dir / f"firechronicle_master_{yr}.parquet")

    db = DuckDBManager(Settings(_env_file=None, DATA_DIR=tmp_path, REAL_DATA_DIR=real_root))
    summary = db.validate_multiyear_totals(require_full_nine_years=True)
    assert summary["year_count"] == 9
    assert summary["modis_total"] == EXPECTED_2012_2020_MODIS_TOTAL
    assert summary["viirs_total"] == EXPECTED_2012_2020_VIIRS_TOTAL
    assert summary["totals_match_expected_9yr"] is True

    # Verify mismatch raises ValueError explicitly
    bad_tbl = pa.table({
        "region_id": ["BR-PA"],
        "block_id": ["-100_-10"],
        "block_ix": pa.array([-100], type=pa.int32()),
        "block_iy": pa.array([-10], type=pa.int32()),
        "year": pa.array([2020], type=pa.int32()),
        "month": pa.array([9], type=pa.int32()),
        "daynight": ["D"],
        "modis_count": pa.array([1], type=pa.int64()),
        "viirs_count": pa.array([1], type=pa.int64()),
        "modis_frp_sum": pa.array([1.0], type=pa.float64()),
        "viirs_frp_sum": pa.array([1.0], type=pa.float64()),
        "coverage_status": ["unknown"],
        "processing_status": ["preliminary"],
        "modis_source_version": ["6.2"],
        "viirs_source_version": ["2"],
    })
    pq.write_table(bad_tbl, real_root / "2020" / "firechronicle_master_2020_extra.parquet")
    db_bad = DuckDBManager(Settings(_env_file=None, DATA_DIR=tmp_path, REAL_DATA_DIR=real_root))
    with pytest.raises(ValueError, match="multi-year total mismatch"):
        db_bad.validate_multiyear_totals(require_full_nine_years=True)


def test_explicit_duplicate_key_failure(tmp_path):
    """Verify duplicate (block_id, year, month, daynight) keys raise ValueError instead of silent dedup."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from app.config import Settings
    from app.db import DuckDBManager

    dup_tbl = pa.table({
        "region_id": ["BR-PA", "BR-PA"],
        "block_id": ["-100_-10", "-100_-10"],
        "block_ix": pa.array([-100, -100], type=pa.int32()),
        "block_iy": pa.array([-10, -10], type=pa.int32()),
        "year": pa.array([2012, 2012], type=pa.int32()),
        "month": pa.array([8, 8], type=pa.int32()),
        "daynight": ["D", "D"],
        "modis_count": pa.array([10, 12], type=pa.int64()),
        "viirs_count": pa.array([40, 44], type=pa.int64()),
        "modis_frp_sum": pa.array([100.0, 120.0], type=pa.float64()),
        "viirs_frp_sum": pa.array([200.0, 220.0], type=pa.float64()),
        "coverage_status": ["unknown", "unknown"],
        "processing_status": ["preliminary", "preliminary"],
        "modis_source_version": ["6.2", "6.2"],
        "viirs_source_version": ["2", "2"],
    })
    pq.write_table(dup_tbl, tmp_path / "firechronicle_master_2012.parquet")

    with pytest.raises(ValueError, match="Duplicate keys detected"):
        DuckDBManager(Settings(_env_file=None, DATA_DIR=tmp_path))


def test_predict_requires_explicit_block_id_no_arbitrary_default():
    """Verify POST /api/v1/predict rejects missing block_id/blocks rather than using an arbitrary default."""
    payload = {
        "region_id": "BR-PA",
        "year": 2005,
        "month": 8,
        "modis_count": 25.0,
    }
    res = client.post("/api/v1/predict", json=payload)
    assert res.status_code == 400
    assert "block_id" in res.json()["detail"]


def test_production_ml_client_graceful_fallback_no_500(monkeypatch):
    """In production without validated ML interface, /api/v1/predict returns model_not_ready with NULLs (not 500)."""
    from app.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ML_MODEL_API_URL", raising=False)
    get_settings.cache_clear()
    try:
        payload = {
            "region_id": "BR-PA",
            "year": 2005,
            "month": 8,
            "block_id": "-100_-10",
            "modis_count": 25.0,
        }
        res = client.post("/api/v1/predict", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "model_not_ready"
        assert body["error"] == "Validated model interface not connected"
        pred = body["predictions"][0]
        assert pred["estimated_viirs_count"] is None
        assert pred["estimated_count"] is None
        assert pred["prediction_status"] == PredictionStatus.NOT_PROCESSED.value
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        get_settings.cache_clear()


def test_synthetic_fixture_metadata_flags(tmp_path, monkeypatch):
    """Verify generate_fixtures metadata explicitly flags fictional/demonstration-only status."""
    import json
    import scripts.generate_fixtures as gf

    monkeypatch.setattr(gf, "DATA_DIR", tmp_path)
    gf.generate_metadata_contracts()

    with open(tmp_path / "demo_model_info.json", "r", encoding="utf-8") as f:
        mi = json.load(f)
    with open(tmp_path / "demo_validation_metrics.json", "r", encoding="utf-8") as f:
        vm = json.load(f)

    assert mi["is_synthetic_demo"] is True
    assert mi["fictional_demo_only"] is True
    assert mi["is_production_ready"] is False
    assert mi["scientific_status"] == "DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED"

    assert vm["is_synthetic_demo"] is True
    assert vm["fictional_demo_only"] is True
    assert vm["is_production_validation"] is False
