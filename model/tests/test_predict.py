"""Smoke and unit tests for the Data Scientist -> Backend B handoff interface.

Validates compliance with FireChronicle Final Team Rulebook (Section 5, p. 6):
- Exact dictionary response schema
- Proper status codes (ok_preliminary, unsupported_region, unsupported_period, out_of_training_range, etc.)
- Strict null preservation (never substituting 0 for error/unsupported conditions)
- Robust model artifact loading across execution paths
"""

import sys
from pathlib import Path
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from predict import predict_viirs_equivalent, predict_batch, load_model, _find_model_path


REQUIRED_SCHEMA_KEYS = {
    "region_id",
    "block_id",
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
}


def test_predict_valid_record_schema():
    """Verify that a valid inference request produces the exact Rulebook p. 6 schema."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2005,
        "month": 9,
        "daynight": "D",
        "modis_count": 45,
        "coverage_status": "unknown",
    }
    resp = predict_viirs_equivalent(input_rec)

    # Check all required keys exist
    assert REQUIRED_SCHEMA_KEYS.issubset(resp.keys())
    assert resp["region_id"] == "BR-PA"
    assert resp["block_id"] == "120_-50"
    assert resp["year"] == 2005
    assert resp["month"] == 9
    assert resp["daynight"] == "D"
    assert resp["value_type"] == "estimated"
    assert resp["prediction_status"] == "ok_preliminary"
    assert resp["coverage_status"] == "unknown"
    assert resp["model_version"] == "ratio-baseline-v1.0-synthetic-demo"
    assert resp["measurement_unit"] == "VIIRS_S-NPP-equivalent_detection_count"
    assert resp["calibration_scale_km"] == 50
    assert isinstance(resp["estimated_viirs_count"], float)
    assert resp["estimated_viirs_count"] == pytest.approx(144.0, rel=1e-3)


def test_unsupported_region_returns_null():
    """Requests outside Pará must return null and 'unsupported_region'."""
    input_rec = {
        "region_id": "BR-AM",  # Amazonas, not Pará
        "block_id": "999_-99",
        "year": 2005,
        "month": 9,
        "daynight": "D",
        "modis_count": 50,
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "unsupported_region"
    assert resp["estimated_viirs_count"] is None


def test_unsupported_period_returns_null():
    """Pre-2002 requests (before Aqua MODIS) must return null and 'unsupported_period'."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 1999,
        "month": 9,
        "daynight": "D",
        "modis_count": 50,
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "unsupported_period"
    assert resp["estimated_viirs_count"] is None


def test_pre_july_2002_aqua_science_record_rejected():
    """Aqua MODIS public science began July 2002; earlier 2002 months must be rejected."""
    # Jan-Jun 2002 is unsupported
    for m in (1, 3, 5, 6):
        rec = {
            "region_id": "BR-PA",
            "block_id": "120_-50",
            "year": 2002,
            "month": m,
            "daynight": "D",
            "modis_count": 20,
        }
        resp = predict_viirs_equivalent(rec)
        assert resp["prediction_status"] == "unsupported_period"
        assert resp["estimated_viirs_count"] is None

    # July 2002 onward is supported
    valid_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2002,
        "month": 7,
        "daynight": "D",
        "modis_count": 20,
    }
    resp_valid = predict_viirs_equivalent(valid_rec)
    assert resp_valid["prediction_status"] == "ok_preliminary"
    assert resp_valid["estimated_viirs_count"] is not None


def test_malformed_and_missing_block_id_rejected():
    """Missing, empty, or non-canonical block IDs must be rejected."""
    bad_blocks = [None, "", "   ", "PA_BLK_01", "120.5_-50.2", "block_1", "120-50"]
    for bad_b in bad_blocks:
        rec = {
            "region_id": "BR-PA",
            "block_id": bad_b,
            "year": 2005,
            "month": 9,
            "daynight": "D",
            "modis_count": 30,
        }
        resp = predict_viirs_equivalent(rec)
        assert resp["prediction_status"] == "missing_required_feature"
        assert resp["estimated_viirs_count"] is None


def test_out_of_training_range_returns_null():
    """Future dates outside calibration scope must return null and 'out_of_training_range'."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2030,
        "month": 9,
        "daynight": "D",
        "modis_count": 50,
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "out_of_training_range"
    assert resp["estimated_viirs_count"] is None


def test_missing_modis_count_returns_null():
    """Missing modis_count must return null and 'missing_required_feature'."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2005,
        "month": 9,
        "daynight": "D",
        # modis_count omitted
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "missing_required_feature"
    assert resp["estimated_viirs_count"] is None


def test_insufficient_coverage_returns_null():
    """Insufficient coverage records must return null and 'insufficient_coverage'."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2005,
        "month": 9,
        "daynight": "D",
        "modis_count": 45,
        "coverage_status": "insufficient",
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "insufficient_coverage"
    assert resp["estimated_viirs_count"] is None


def test_zero_modis_count_prediction():
    """MODIS count of 0 yields 0.0 with 'ok_preliminary'."""
    input_rec = {
        "region_id": "BR-PA",
        "block_id": "120_-50",
        "year": 2005,
        "month": 9,
        "daynight": "D",
        "modis_count": 0,
    }
    resp = predict_viirs_equivalent(input_rec)
    assert resp["prediction_status"] == "ok_preliminary"
    assert resp["estimated_viirs_count"] == 0.0


def test_backend_never_substitutes_zero_for_null():
    """Ensure null is strictly preserved across all non-ok status codes (Rulebook p. 6)."""
    error_cases = [
        {"region_id": "BR-MT", "block_id": "120_-50", "year": 2005, "month": 9, "daynight": "D", "modis_count": 10},
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 1998, "month": 9, "daynight": "D", "modis_count": 10},
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 2035, "month": 9, "daynight": "D", "modis_count": 10},
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 2005, "month": 9, "daynight": "D", "coverage_status": "insufficient", "modis_count": 10},
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 2005, "month": 9, "daynight": "D"},
    ]
    for case in error_cases:
        out = predict_viirs_equivalent(case)
        assert out["estimated_viirs_count"] is None, f"Expected None for status {out['prediction_status']}, got {out['estimated_viirs_count']}"
        assert out["prediction_status"] != "ok_preliminary"


def test_robust_model_path_resolution():
    """Verify that _find_model_path successfully finds model.joblib or fallback in artifacts."""
    resolved = _find_model_path()
    assert resolved.exists()
    assert resolved.suffix == ".joblib"

    # Test loading explicit path
    loaded = load_model(resolved)
    assert loaded["multiplier_k"] == pytest.approx(3.20, rel=1e-3)


def test_predict_batch():
    """Batch inference processes a list of observations into standardized response dicts."""
    records = [
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 2005, "month": 8, "daynight": "D", "modis_count": 10},
        {"region_id": "BR-PA", "block_id": "120_-50", "year": 2005, "month": 9, "daynight": "D", "modis_count": 20},
    ]
    results = predict_batch(records)
    assert len(results) == 2
    assert results[0]["estimated_viirs_count"] == pytest.approx(32.0, rel=1e-3)
    assert results[1]["estimated_viirs_count"] == pytest.approx(64.0, rel=1e-3)
