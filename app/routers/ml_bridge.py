"""ML Bridge Router for FireChronicle Backend.

Provides authenticated webhook and sync endpoints for the Data Science teammate:
1. GET /ml-bridge/status: Probe remote ML service and local fallback availability.
2. POST /ml-bridge/predict: Test prediction engine directly.
3. POST /ml-bridge/sync-predictions: Inbound webhook to receive batch predictions.
4. POST /ml-bridge/sync-metrics: Inbound webhook to update validation metrics.
"""

import hmac
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.db import DuckDBManager, get_db
from app.ml_client import MLModelClient
from app.schemas import (
    MLBridgeStatusResponse,
    MetricsSyncPayload,
    PredictRequest,
    PredictResponse,
    PredictionSyncPayload,
    WebhookStatusResponse,
)

logger = logging.getLogger("firechronicle.ml_bridge")
router = APIRouter(prefix="/ml-bridge", tags=["ML Bridge & Teammate Webhook"])


def verify_webhook_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify inbound webhook authentication token from environment settings."""
    expected_key = settings.WEBHOOK_API_KEY
    if not expected_key:
        logger.warning("WEBHOOK_API_KEY is not configured in environment; rejecting webhook request.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: WEBHOOK_API_KEY is not configured.",
        )

    # Check X-API-Key header
    if x_api_key and hmac.compare_digest(x_api_key, expected_key):
        return True

    # Check Authorization: Bearer <key>
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and hmac.compare_digest(parts[1], expected_key):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Invalid or missing API key for ML Bridge webhook.",
    )


@router.get(
    "/status",
    response_model=MLBridgeStatusResponse,
    summary="Probe ML connectivity status (remote HTTP service & local fallback)",
)
async def get_bridge_status(
    settings: Settings = Depends(get_settings),
):
    """Check connectivity to remote ML model API and verify local fallback readiness."""
    client = MLModelClient(settings)
    status_data = await client.check_status()
    return MLBridgeStatusResponse(**status_data)


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Test prediction pipeline directly through ML Bridge",
)
async def bridge_predict(
    payload: PredictRequest,
    settings: Settings = Depends(get_settings),
):
    """Invoke prediction engine via ML Bridge."""
    client = MLModelClient(settings)
    return await client.predict(payload)


@router.post(
    "/sync-predictions",
    response_model=WebhookStatusResponse,
    summary="Inbound webhook: acknowledge batch predictions from Data Science teammate",
)
def sync_predictions(
    payload: PredictionSyncPayload,
    authenticated: bool = Depends(verify_webhook_auth),
    db: DuckDBManager = Depends(get_db),
):
    """Validate and acknowledge inbound batch predictions from the ML teammate.

    NOTE: Real durable storage (Parquet/DuckDB persistence) and read-back verification
    are pending delivery of the validated Data Science model interface.
    """
    count = db.sync_predictions(payload.records)
    return WebhookStatusResponse(
        status="demo_acknowledgement_only",
        records_received=count,
        message=(
            f"Demo acknowledgement only: received {count} prediction records from batch "
            f"'{payload.batch_id}' (model {payload.model_version}). Real persistent storage and "
            "read-back verification are pending the delivery of the validated Data Science model interface."
        ),
    )


@router.post(
    "/sync-metrics",
    response_model=WebhookStatusResponse,
    summary="Inbound webhook: update validation metrics from Data Science teammate",
)
def sync_metrics(
    payload: MetricsSyncPayload,
    authenticated: bool = Depends(verify_webhook_auth),
    db: DuckDBManager = Depends(get_db),
):
    """Ingest updated held-out cross-validation metrics calculated by ML teammate."""
    db.sync_metrics(payload.model_dump())
    return WebhookStatusResponse(
        status="success",
        records_received=1,
        message=f"Validation metrics for model '{payload.model_version}' updated successfully.",
    )
