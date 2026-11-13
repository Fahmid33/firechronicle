"""FastAPI Router for /api/v1 endpoints for Next.js / TypeScript + MapLibre Frontend.

Official contracts with strict scientific guardrails:
1. GET /api/v1/summary (and /api/v1/timeseries): Monthly & annual timeline for Pará (BR-PA) with ?daynight=ALL|D|N.
2. GET /api/v1/spatial (and /api/v1/grid): GeoJSON FeatureCollection for MapLibre with ?daynight=ALL|D|N.
3. GET /api/v1/blocks: 50km block polygons GeoJSON FeatureCollection for MapLibre.
4. GET /api/v1/hotspots: Individual point detections with provenance and ?daynight=D|N.
5. GET /api/v1/sensor-lab/calibration: 2012-2020 paired MODIS & VIIRS observations with null-safe ratio and log_ratio.
6. GET /api/v1/sensor-lab/metrics: Held-out validation metrics & biome breakdown.
7. GET /api/v1/model/info: Model metadata contract & scientific rules.
8. POST /api/v1/predict: Model inference with remote ML client & local fallback.
+ Companion: GET /api/v1/boundary (Official IBGE boundary GeoJSON) and GET /api/v1/health.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import DuckDBManager, get_db
from app.ml_client import MLModelClient
from app.schemas import (
    BlocksFeatureCollectionResponse,
    CalibrationResponse,
    HotspotListResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    PredictionStatus,
    SpatialFeatureCollectionResponse,
    TimeSeriesSummaryResponse,
    ValidationMetricsResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Frontend API v1"])


def get_ml_client(settings: Settings = Depends(get_settings)) -> MLModelClient:
    return MLModelClient(settings)


# -----------------------------------------------------------------------------
# Endpoint 1: Summary / Time Series
# -----------------------------------------------------------------------------
@router.get(
    "/summary",
    response_model=TimeSeriesSummaryResponse,
    summary="Get aggregated monthly fire count timeseries for Pará (BR-PA)",
)
@router.get(
    "/timeseries",
    response_model=TimeSeriesSummaryResponse,
    include_in_schema=False,
)
@router.get(
    "/harmonized",
    response_model=TimeSeriesSummaryResponse,
    summary="Get harmonized monthly timeline (estimated pre-2012 + observed 2012+) for Pará (BR-PA)",
)
def get_summary_timeseries(
    region_id: str = Query("BR-PA", description="Release geography code (BR-PA only)"),
    start_year: Optional[int] = Query(None, ge=2002, le=2026, description="Start year filter"),
    end_year: Optional[int] = Query(None, ge=2002, le=2026, description="End year filter"),
    daynight: str = Query("ALL", pattern="^(ALL|D|N)$", description="Orbit pass filter: ALL, D (day), or N (night)"),
    db: DuckDBManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return harmonized monthly fire count timeline for Pará (2002 to present)."""
    if region_id != settings.ANALYSIS_REGION_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "prediction_status": PredictionStatus.UNSUPPORTED_REGION,
                "error": f"Region '{region_id}' is not supported. Pará ({settings.ANALYSIS_REGION_ID}) is the sole release geography.",
            },
        )
    try:
        return db.get_timeseries_summary(region_id, start_year, end_year, daynight)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 2: Spatial Grid & Block GeoJSON
# -----------------------------------------------------------------------------
@router.get(
    "/spatial",
    response_model=SpatialFeatureCollectionResponse,
    summary="Get spatial fire counts as GeoJSON FeatureCollection for MapLibre",
)
@router.get(
    "/grid",
    response_model=SpatialFeatureCollectionResponse,
    include_in_schema=False,
)
def get_spatial_grid(
    region_id: str = Query("BR-PA", description="Release geography code (BR-PA only)"),
    year: int = Query(..., ge=2002, le=2026, description="Target year"),
    month: int = Query(..., ge=1, le=12, description="Target month (1-12)"),
    resolution: str = Query("50km", pattern="^(50km|10km)$", description="Grid scale: '50km' block or '10km' cell"),
    daynight: str = Query("ALL", pattern="^(ALL|D|N)$", description="Orbit pass filter: ALL, D, or N"),
    db: DuckDBManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return GeoJSON FeatureCollection with equal-area polygon geometries."""
    if region_id != settings.ANALYSIS_REGION_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "prediction_status": PredictionStatus.UNSUPPORTED_REGION,
                "error": f"Region '{region_id}' is not supported. FireChronicle operates strictly within Pará ({settings.ANALYSIS_REGION_ID}).",
            },
        )
    try:
        return db.get_spatial_features(region_id, year, month, resolution, daynight)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 3: 50km Blocks GeoJSON Polygon (GET /api/v1/blocks)
# -----------------------------------------------------------------------------
@router.get(
    "/blocks",
    summary="Get pre-generated 50km block polygons GeoJSON FeatureCollection for MapLibre",
)
def get_blocks_geojson(
    region_id: str = Query("BR-PA", description="Release geography code (BR-PA only)"),
    db: DuckDBManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Serve precomputed 50km block polygon geometries across Pará (BR-PA)."""
    if region_id != settings.ANALYSIS_REGION_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Region '{region_id}' is unsupported. Only {settings.ANALYSIS_REGION_ID} is active."},
        )
    try:
        return db.get_blocks_geojson(region_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 4: Hotspot Point Detections
# -----------------------------------------------------------------------------
@router.get(
    "/hotspots",
    response_model=HotspotListResponse,
    summary="Get individual fire point detections inside Pará with provenance",
)
def get_hotspot_points(
    region_id: str = Query("BR-PA", description="Release geography code (BR-PA only)"),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)"),
    satellite: Optional[str] = Query(None, description="Satellite name filter (e.g. Aqua, Suomi-NPP)"),
    instrument: Optional[str] = Query(None, description="Instrument name filter (e.g. MODIS, VIIRS)"),
    daynight: Optional[str] = Query(None, pattern="^(D|N)$", description="Orbit pass filter: D or N"),
    limit: int = Query(100, ge=1, le=5000, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Row offset for pagination"),
    db: DuckDBManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Query point detections inside Pará with exact instrument and satellite provenance."""
    if region_id != settings.ANALYSIS_REGION_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "prediction_status": PredictionStatus.UNSUPPORTED_REGION,
                "error": f"Region '{region_id}' is not supported.",
            },
        )
    try:
        return db.get_hotspots(region_id, start_date, end_date, satellite, instrument, daynight, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 5: Sensor Lab Overlap Calibration (Strict Null-Safe log_ratio)
# -----------------------------------------------------------------------------
@router.get(
    "/sensor-lab/calibration",
    response_model=CalibrationResponse,
    summary="Get paired Aqua MODIS and VIIRS S-NPP monthly overlap observations",
)
def get_sensor_lab_calibration(
    region_id: str = Query("BR-PA", description="Release geography code (BR-PA only)"),
    start_year: Optional[int] = Query(None, ge=2012, le=2020, description="Start year of overlap period"),
    end_year: Optional[int] = Query(None, ge=2012, le=2020, description="End year of overlap period"),
    block_id: Optional[str] = Query(None, description="Specific 50km block ID filter"),
    daynight: str = Query("ALL", pattern="^(ALL|D|N)$", description="Orbit pass filter: ALL, D, or N"),
    db: DuckDBManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return paired 50km block observations with strict null-safe ratio and natural log calculations."""
    if region_id != settings.ANALYSIS_REGION_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Region '{region_id}' is unsupported."},
        )
    try:
        return db.get_calibration_pairs(region_id, start_year, end_year, block_id, daynight)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 6: Sensor Lab Validation Metrics
# -----------------------------------------------------------------------------
@router.get(
    "/sensor-lab/metrics",
    response_model=ValidationMetricsResponse,
    summary="Get held-out cross-validation metrics across Pará blocks and years",
)
def get_sensor_lab_metrics(
    db: DuckDBManager = Depends(get_db),
):
    """Return overall, yearly, and biome-specific validation metrics on held-out data."""
    try:
        return db.get_validation_metrics()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 7: Model Metadata Contract
# -----------------------------------------------------------------------------
@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Get ML model metadata, validation metrics, input features, and guardrails",
)
@router.get(
    "/model/info",
    response_model=ModelInfoResponse,
    summary="Get ML model metadata, input features, and scientific guardrails",
)
def get_model_info(
    settings: Settings = Depends(get_settings),
):
    """Read model_info.json and validation_metrics.json directly from disk and return combined metadata."""
    info_file = settings.DATA_DIR / "model_info.json"
    metrics_file = settings.DATA_DIR / "validation_metrics.json"
    if not info_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model metadata file not found: {info_file}",
        )
    try:
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                data["validation_metrics"] = json.load(f)
        else:
            data.setdefault("validation_metrics", None)
        return ModelInfoResponse.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoint 8: Predict & ML Inference Hooks (/api/v1/predict, /api/v1/ml/*)
# -----------------------------------------------------------------------------
@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Execute harmonized VIIRS-equivalent inference for a block/period",
)
@router.post(
    "/ml/predict",
    response_model=PredictResponse,
    include_in_schema=True,
    summary="ML batch/single inference hook",
)
@router.post(
    "/ml/infer",
    response_model=PredictResponse,
    include_in_schema=False,
)
async def post_predict(
    payload: PredictRequest,
    ml_client: MLModelClient = Depends(get_ml_client),
    settings: Settings = Depends(get_settings),
):
    """Perform model inference with HTTP remote client and local fallback."""
    if payload.region_id != settings.ANALYSIS_REGION_ID:
        res = await ml_client.predict(payload)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=res.model_dump(),
        )

    res = await ml_client.predict(payload)
    return res


# -----------------------------------------------------------------------------
# Companion Endpoints: Official IBGE Boundary GeoJSON & Health
# -----------------------------------------------------------------------------
@router.get(
    "/boundary",
    summary="Get official IBGE Pará (BR-PA) GeoJSON boundary for MapLibre map initialization",
)
def get_para_boundary(settings: Settings = Depends(get_settings)):
    """Serve official IBGE Pará boundary polygon GeoJSON."""
    geojson_path = settings.DATA_DIR / "para_boundary.geojson"
    if not geojson_path.exists():
        raise HTTPException(status_code=404, detail="Boundary GeoJSON file not found.")
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/health", summary="Health check endpoint")
def health_check():
    return {
        "status": "healthy",
        "service": "FireChronicle Pará Backend",
        "version": "1.0.0",
        "region_id": "BR-PA",
    }
