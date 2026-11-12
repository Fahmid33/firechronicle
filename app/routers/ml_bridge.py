"""ML Bridge Router for FireChronicle Backend.

Provides authenticated webhook and sync endpoints for the Data Science teammate:
1. GET /ml-bridge/status: Probe remote ML service and local fallback availability.
2. POST /ml-bridge/predict: Test prediction engine directly.
3. POST /ml-bridge/sync-predictions: Inbound webhook to receive batch predictions.
4. POST /ml-bridge/sync-metrics: Inbound webhook to update validation metrics.
"""

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

router = APIRouter(prefix="/ml-bridge", tags=["ML Bridge & Teammate Webhook"])


def verify_webhook_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify inbound webhook authentication token."""
    expected_key = settings.WEBHOOK_API_KEY

    # Check X-API-Key header
    if x_api_key and x_api_key == expected_key:
        return True

    # Check Authorization: Bearer <key>
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected_key:
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
    summary="Inbound webhook: sync batch predictions from Data Science teammate",
)
def sync_predictions(
    payload: PredictionSyncPayload,
    authenticated: bool = Depends(verify_webhook_auth),
    db: DuckDBManager = Depends(get_db),
):
    """Ingest precomputed or newly trained prediction batches from the ML teammate."""
    count = db.sync_predictions(payload.records)
    return WebhookStatusResponse(
        status="success",
        records_received=count,
        message=f"Successfully synced {count} prediction records from batch '{payload.batch_id}' (model {payload.model_version}).",
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
