"""Strict Pydantic v2 data models for FireChronicle Pará (BR-PA) API and ML Handoffs.

Non-negotiable Guardrails enforced:
- region_id must be "BR-PA". Unsupported regions trigger prediction_status="unsupported_region".
- Missing/unprocessed values must remain None (strict null integrity, NEVER substituted with 0).
- value_type strictly distinguishes "estimated", "observed", and "provisional_nrt".
- log_ratio and ratio calculations are strictly null-safe (None when modis <= 0 or counts missing, zero NaN/Inf).
- PredictionStatus strictly matches official values.
- Support for ?daynight=ALL|D|N filters.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegionId(str, Enum):
    """Release geography guardrail: Pará, Brazil ONLY."""
    PARA = "BR-PA"


class DayNightFilter(str, Enum):
    """Satellite orbit passes."""
    ALL = "ALL"
    DAY = "D"
    NIGHT = "N"


class ValueType(str, Enum):
    """Measurement era distinction."""
    ESTIMATED = "estimated"          # Mid-2002 to 2011 (Aqua MODIS -> VIIRS S-NPP equiv)
    OBSERVED = "observed"            # 2012+ (Actual observed VIIRS S-NPP detections)
    PROVISIONAL_NRT = "provisional_nrt"  # Recent Near-Real-Time VIIRS S-NPP detections


class CoverageStatus(str, Enum):
    """Clear-sky and satellite observation integrity."""
    VERIFIED = "verified"    # Confirmed clear-sky observation coverage
    UNKNOWN = "unknown"      # Missing detection row without explicit zero verification
    MISSING = "missing"      # Data gap or unobserved orbital pass
    INSUFFICIENT = "insufficient"  # Insufficient clear-sky or orbital pass coverage
    COVERAGE_UNADJUSTED = "coverage_unadjusted"  # Unadjusted coverage indicator


class ProcessingStatus(str, Enum):
    """Processing stage."""
    COMPLETED = "completed"
    PENDING = "pending"
    NOT_PROCESSED = "not_processed"


class PredictionStatus(str, Enum):
    """Exact prediction status codes required by scientific guardrails."""
    OK_PRELIMINARY = "ok_preliminary"
    UNSUPPORTED_REGION = "unsupported_region"
    UNSUPPORTED_PERIOD = "unsupported_period"
    OUT_OF_TRAINING_RANGE = "out_of_training_range"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    MISSING_REQUIRED_FEATURE = "missing_required_feature"
    MODEL_ERROR = "model_error"
    NOT_PROCESSED = "not_processed"


# ---------------------------------------------------------
# Time Series & Summary Schemas
# ---------------------------------------------------------

class TimeSeriesMonthlyPoint(BaseModel):
    """Monthly aggregated fire detection point for Pará timeline."""
    model_config = ConfigDict(use_enum_values=True)

    year: int
    month: int
    period: str  # YYYY-MM
    daynight: str = "ALL"  # "ALL", "D", or "N"
    count: Optional[float] = None  # None if missing/unprocessed; NEVER substitute 0
    estimated_count: Optional[float] = None  # Alias / ML estimated count when value_type=="estimated"
    value_type: ValueType
    label: str  # e.g. "Estimated historical extrapolation", "Observed S-NPP"
    prediction_status: Optional[Union[PredictionStatus, str]] = None
    coverage_status: Optional[Union[CoverageStatus, str]] = None
    coverage_notes: Optional[str] = None
    model_version: Optional[str] = None
    measurement_unit: Optional[str] = None
    calibration_scale_km: Optional[int] = None
    frp_total_mw: Optional[float] = None
    is_harmonized_estimate: bool
    is_synthetic_demo: bool = False
    data_source_tier: Optional[str] = None  # e.g. "synthetic_demo_estimates" vs "pilot_2019_observations"


class TimeSeriesSummaryResponse(BaseModel):
    """Response contract for /api/v1/timeseries and /api/v1/summary."""
    region_id: str = "BR-PA"
    region_name: str = "Pará, Brazil"
    daynight_filter: str = "ALL"
    data_start_date: str = "2002-07"
    data_end_date: str
    harmonization_boundary_date: str = "2012-01"
    scientific_guardrail_note: str = (
        "Mid-2002 to 2011 values are harmonized 50km block estimates extrapolated from Aqua MODIS. "
        "2012+ values are actual observed VIIRS S-NPP. Aqua MODIS and VIIRS counts are NEVER added together."
    )
    contains_synthetic_demo_data: bool = False
    synthetic_demo_notice: Optional[str] = None
    data_provenance_summary: Optional[Dict[str, Any]] = None
    total_months: int
    items: List[TimeSeriesMonthlyPoint]


# ---------------------------------------------------------
# Spatial Grid & Block Schemas (GeoJSON FeatureCollection)
# ---------------------------------------------------------

class GeoJSONGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]


class SpatialFeatureProperties(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str  # block_id ("{block_ix}_{block_iy}") or grid_id ("{ix}_{iy}")
    block_id: Optional[str] = None
    grid_id: Optional[str] = None
    block_ix: Optional[int] = None
    block_iy: Optional[int] = None
    ix: Optional[int] = None
    iy: Optional[int] = None
    resolution: Literal["50km", "10km"]
    year: int
    month: int
    daynight: Optional[str] = "ALL"
    count: Optional[float] = None  # None preserves strict null integrity
    estimated_count: Optional[float] = None
    value_type: ValueType
    label: str
    prediction_status: Optional[Union[PredictionStatus, str]] = None
    coverage_status: Optional[Union[CoverageStatus, str]] = None
    coverage_notes: Optional[str] = None
    model_version: Optional[str] = None
    measurement_unit: Optional[str] = None
    calibration_scale_km: Optional[int] = None
    frp_sum: Optional[float] = None
    is_synthetic_demo: bool = False


class SpatialFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: SpatialFeatureProperties


class SpatialFeatureCollectionResponse(BaseModel):
    """GeoJSON FeatureCollection contract for MapLibre /api/v1/spatial."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    metadata: Dict[str, Any]
    features: List[SpatialFeature]


# ---------------------------------------------------------
# 50km Block Polygon Feature Schema (GET /api/v1/blocks)
# ---------------------------------------------------------

class BlockPolygonProperties(BaseModel):
    block_id: str
    block_ix: int
    block_iy: int
    region_id: str = "BR-PA"
    resolution: str = "50km"
    spatial_system: str = "EPSG:6933"


class BlockPolygonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    properties: BlockPolygonProperties
    geometry: GeoJSONGeometry


class BlocksFeatureCollectionResponse(BaseModel):
    """GeoJSON FeatureCollection contract for MapLibre /api/v1/blocks."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    name: str = "para_blocks_50km"
    metadata: Dict[str, Any]
    features: List[BlockPolygonFeature]


# ---------------------------------------------------------
# Hotspot Point Detections Schema
# ---------------------------------------------------------

class HotspotPoint(BaseModel):
    """Individual fire detection point with full provenance."""
    model_config = ConfigDict(use_enum_values=True)

    id: str
    latitude: float
    longitude: float
    acq_date: str  # YYYY-MM-DD
    acq_time: str  # HHMM
    daynight: Optional[str] = "D"
    satellite: str  # "Aqua", "Terra", "Suomi-NPP"
    instrument: str  # "MODIS", "VIIRS"
    confidence: Optional[str] = None
    frp: Optional[float] = None
    grid_id: str  # 10 km base cell
    block_id: str  # 50 km calibration block
    value_type: ValueType
    region_id: str = "BR-PA"


class HotspotListResponse(BaseModel):
    """Response contract for /api/v1/hotspots."""
    region_id: str = "BR-PA"
    daynight_filter: Optional[str] = None
    total: int
    limit: int
    offset: int
    items: List[HotspotPoint]


# ---------------------------------------------------------
# Sensor Lab Overlap Calibration & Validation Schemas
# ---------------------------------------------------------

class CalibrationPair(BaseModel):
    """Paired Aqua MODIS and VIIRS S-NPP monthly aggregate for a 50km block."""
    block_id: str
    block_ix: Optional[int] = None
    block_iy: Optional[int] = None
    year: int
    month: int
    daynight: Optional[str] = "ALL"
    modis_count: Optional[float] = None
    viirs_count: Optional[float] = None
    ratio_viirs_to_modis: Optional[float] = None
    log_ratio: Optional[float] = None  # Strictly null-safe (None when modis<=0 or viirs<=0, no NaN/Inf)
    modis_frp_sum: Optional[float] = None
    viirs_frp_sum: Optional[float] = None
    coverage_status: Optional[Union[CoverageStatus, str]] = None


class CalibrationResponse(BaseModel):
    """Response contract for /api/v1/sensor-lab/calibration."""
    region_id: str = "BR-PA"
    training_era: str = "2012-2020 (Overlap Period)"
    resolution: str = "50km EPSG:6933 block"
    daynight_filter: str = "ALL"
    total_pairs: int
    correlation_r: Optional[float] = None
    mean_ratio_viirs_to_modis: Optional[float] = None
    mean_log_ratio: Optional[float] = None
    items: List[CalibrationPair]


class ValidationMetricsResponse(BaseModel):
    """Response contract for /api/v1/sensor-lab/metrics."""
    model_config = ConfigDict(extra="allow")

    model_version: Optional[str] = None
    scientific_status: Optional[str] = None
    is_production_validation: Optional[bool] = None
    evaluation_dataset: Optional[str] = None
    held_out_strategy: Optional[str] = None
    eligible_sample_count: Optional[int] = None
    excluded_records_count: Optional[int] = None
    unknown_coverage_sample_count: Optional[int] = None
    coverage_policy: Optional[str] = None
    fitted_multiplier_k: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    scientific_limitations: Optional[List[str]] = None
    spatial_resolution: Optional[str] = "50km EPSG:6933 block"
    temporal_resolution: Optional[str] = "Monthly"
    held_out_period: Optional[str] = None
    metrics_overall: Optional[Dict[str, Any]] = None
    yearly_metrics: Optional[List[Dict[str, Any]]] = None
    biome_metrics: Optional[List[Dict[str, Any]]] = None
    methodology_notes: Optional[str] = None


# ---------------------------------------------------------
# Model Metadata Schema
# ---------------------------------------------------------

class ModelInfoResponse(BaseModel):
    """Response contract for /api/v1/model-info and /api/v1/model/info."""
    model_config = ConfigDict(extra="allow")

    model_name: Optional[str] = None
    model_version: Optional[str] = None
    scientific_status: Optional[str] = None
    is_production_ready: Optional[bool] = None
    target: Optional[str] = None
    region: Optional[str] = None
    supported_years: Optional[Dict[str, Any]] = None
    features: Optional[List[str]] = None
    calibration_scale_km: Optional[int] = None
    spatial_crs: Optional[str] = None
    temporal_resolution: Optional[str] = None
    multiplier_k: Optional[float] = None
    training_evidence: Optional[str] = None
    disclaimer: Optional[str] = None
    framework: Optional[str] = None
    target_resolution: Optional[str] = "50 km x 50 km (EPSG:6933 equal-area block)"
    training_era: Optional[str] = "2012-2020 Aqua MODIS & VIIRS S-NPP overlap in Pará (BR-PA)"
    extrapolation_era: Optional[str] = "Mid-2002 to 2011 historical Aqua MODIS -> VIIRS-equivalent"
    precomputed_estimates_dataset: Optional[str] = None
    input_features: Optional[List[str]] = None
    scientific_guardrails: Optional[List[str]] = None
    limitations: Optional[List[str]] = None
    validation_metrics: Optional[ValidationMetricsResponse] = None


# ---------------------------------------------------------
# Predict Request & Response Schemas
# ---------------------------------------------------------

class PredictBlockInput(BaseModel):
    block_id: str
    modis_count: Optional[float] = None
    modis_frp_sum: Optional[float] = None
    daynight: Optional[str] = "ALL"
    features: Optional[Dict[str, float]] = None


class PredictRequest(BaseModel):
    """Contract for POST /api/v1/predict and ML Model client."""
    region_id: str
    year: int
    month: int
    daynight: Optional[str] = "ALL"
    blocks: Optional[List[PredictBlockInput]] = None
    block_id: Optional[str] = None
    modis_count: Optional[float] = None
    modis_frp_sum: Optional[float] = None


class SingleBlockPrediction(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    block_id: str
    block_ix: Optional[int] = None
    block_iy: Optional[int] = None
    year: int
    month: int
    daynight: str = "ALL"
    estimated_viirs_count: Optional[float] = None
    estimated_count: Optional[float] = None
    value_type: Optional[ValueType] = ValueType.ESTIMATED
    prediction_status: Optional[Union[PredictionStatus, str]] = None
    coverage_status: Optional[Union[CoverageStatus, str]] = None
    coverage_notes: Optional[str] = None
    model_version: Optional[str] = None
    measurement_unit: Optional[str] = None
    calibration_scale_km: Optional[int] = None
    is_synthetic_demo: bool = False
    error_message: Optional[str] = None


class PredictResponse(BaseModel):
    """Response contract for POST /api/v1/predict."""
    region_id: str
    year: int
    month: int
    daynight: str = "ALL"
    is_synthetic_demo: bool = False
    synthetic_demo_notice: Optional[str] = None
    predictions: List[SingleBlockPrediction]
    total_predictions: int


# ---------------------------------------------------------
# ML Bridge Webhook & Sync Schemas
# ---------------------------------------------------------

class PredictionSyncRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    block_id: str
    year: int
    month: int
    daynight: Optional[str] = "ALL"
    estimated_viirs_count: Optional[float] = None
    estimated_count: Optional[float] = None
    modis_count: Optional[float] = None
    value_type: Optional[ValueType] = ValueType.ESTIMATED
    prediction_status: Optional[Union[PredictionStatus, str]] = None
    coverage_status: Optional[Union[CoverageStatus, str]] = None
    measurement_unit: Optional[str] = None
    calibration_scale_km: Optional[int] = None


class PredictionSyncPayload(BaseModel):
    batch_id: str
    model_version: str
    records: List[PredictionSyncRecord]


class MetricsSyncPayload(BaseModel):
    model_version: str
    updated_at: str
    metrics_overall: Dict[str, float]
    yearly_metrics: List[Dict[str, Any]]
    biome_metrics: List[Dict[str, Any]]


class WebhookStatusResponse(BaseModel):
    status: str
    records_received: int
    message: str


class MLBridgeStatusResponse(BaseModel):
    remote_ml_service_available: bool
    remote_ml_url: Optional[str]
    local_fallback_available: bool
    master_dataset_available: bool
    active_mode: str
