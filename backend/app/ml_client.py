"""ML Model Client for FireChronicle Backend.

Supports two-way integration:
1. Instant retrieval of precomputed historical ML estimates from `data/estimated_viirs_block_month.parquet`
   (keyed by region_id, block_id, year, month, daynight) for pre-2012 queries.
2. Authenticated HTTP client (X-API-Key / Authorization: Bearer) to remote Data Science ML service.
3. Local empirical calibration model (scripts/predict.py) for ad-hoc / batch inference via /api/v1/ml/*.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import Settings, get_settings
from app.schemas import (
    CoverageStatus,
    PredictBlockInput,
    PredictRequest,
    PredictResponse,
    PredictionStatus,
    SingleBlockPrediction,
    ValueType,
)
from scripts.predict import predict_single_block

logger = logging.getLogger("firechronicle.ml_client")


class MLModelClient:
    """Client for querying precomputed estimates or invoking the Data Science Harmonization Model."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    @staticmethod
    def _parse_block_indices(block_id: str) -> tuple[Optional[int], Optional[int]]:
        """Extract 50km (block_ix, block_iy) integers from block_id '{ix}_{iy}'."""
        parts = str(block_id).split("_")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                return None, None
        return None, None

    async def predict(self, request: PredictRequest) -> PredictResponse:
        """Execute prediction request with precomputed cache, remote HTTP attempt, or local fallback."""
        # 1. Non-negotiable geographic guardrail: Pará (BR-PA) ONLY
        if request.region_id != self.settings.ANALYSIS_REGION_ID:
            blocks_to_predict = self._normalize_blocks(request)
            error_preds = []
            for b in blocks_to_predict:
                b_ix, b_iy = self._parse_block_indices(b.block_id)
                error_preds.append(
                    SingleBlockPrediction(
                        block_id=b.block_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=request.year,
                        month=request.month,
                        daynight=b.daynight or request.daynight or "ALL",
                        estimated_viirs_count=None,
                        estimated_count=None,
                        prediction_status=PredictionStatus.UNSUPPORTED_REGION,
                        model_version="guardrail-v1",
                        error_message=(
                            f"Region '{request.region_id}' is unsupported. "
                            f"FireChronicle operates strictly within Pará ({self.settings.ANALYSIS_REGION_ID})."
                        ),
                    )
                )
            return PredictResponse(
                region_id=request.region_id,
                year=request.year,
                month=request.month,
                daynight=request.daynight or "ALL",
                predictions=error_preds,
                total_predictions=len(error_preds),
            )

        # 2. Temporal guardrail check
        if request.year < 2002 or (request.year == 2002 and request.month < 7):
            blocks_to_predict = self._normalize_blocks(request)
            error_preds = []
            for b in blocks_to_predict:
                b_ix, b_iy = self._parse_block_indices(b.block_id)
                error_preds.append(
                    SingleBlockPrediction(
                        block_id=b.block_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=request.year,
                        month=request.month,
                        daynight=b.daynight or request.daynight or "ALL",
                        estimated_viirs_count=None,
                        estimated_count=None,
                        prediction_status=PredictionStatus.UNSUPPORTED_PERIOD,
                        model_version="guardrail-v1",
                        error_message=f"Period {request.year}-{request.month:02d} predates Aqua MODIS launch (July 2002).",
                    )
                )
            return PredictResponse(
                region_id=request.region_id,
                year=request.year,
                month=request.month,
                daynight=request.daynight or "ALL",
                predictions=error_preds,
                total_predictions=len(error_preds),
            )

        # 3. For pre-2012 historical queries where modis_count is omitted, retrieve precomputed ML estimate instantly
        if request.year < 2012 and (request.modis_count is None and not any(b.modis_count is not None for b in self._normalize_blocks(request))):
            precomputed_resp = self._lookup_precomputed_estimates(request)
            if precomputed_resp:
                return precomputed_resp

        # 4. Attempt remote ML HTTP Service if configured
        if self.settings.ML_MODEL_API_URL:
            try:
                remote_resp = await self._query_remote_ml(request)
                if remote_resp:
                    return remote_resp
            except Exception as e:
                logger.warning("Remote ML service failed or timed out: %s. Engaging local fallback.", e)

        # 5. Local fallback execution using empirical calibration regression
        return self._local_fallback_predict(request)

    def _normalize_blocks(self, request: PredictRequest) -> List[PredictBlockInput]:
        """Normalize request to a list of block inputs; reject missing block identifiers."""
        if request.blocks and len(request.blocks) > 0:
            return request.blocks
        if request.block_id:
            return [
                PredictBlockInput(
                    block_id=request.block_id,
                    modis_count=request.modis_count,
                    modis_frp_sum=request.modis_frp_sum,
                    daynight=request.daynight or "ALL",
                )
            ]
        raise ValueError(
            "Missing required block identifier: provide 'block_id' or a non-empty 'blocks' list."
        )

    def _lookup_precomputed_estimates(self, request: PredictRequest) -> Optional[PredictResponse]:
        """Instant retrieval of precomputed historical predictions from DuckDB / Parquet cache."""
        est_file = self.settings.DATA_DIR / "estimated_viirs_block_month.parquet"
        if not est_file.exists():
            return None

        from app.db import get_db
        db = get_db()
        blocks = self._normalize_blocks(request)
        dn = request.daynight or "ALL"
        results: List[SingleBlockPrediction] = []

        for b in blocks:
            b_dn = b.daynight or dn
            b_ix, b_iy = self._parse_block_indices(b.block_id)
            params: List[Any] = [request.region_id, b.block_id, request.year, request.month]

            if b_dn in ("D", "N"):
                params.append(b_dn)
                sql = """
                    SELECT
                        estimated_count,
                        prediction_status,
                        coverage_status,
                        model_version,
                        measurement_unit,
                        value_type,
                        calibration_scale_km,
                        1 as row_cnt
                    FROM estimated_viirs_block_month
                    WHERE region_id = ? AND block_id = ? AND year = ? AND month = ? AND daynight = ?
                    LIMIT 1
                """
            else:
                sql = """
                    WITH dn AS (
                        SELECT
                            MAX(CASE WHEN daynight = 'D' THEN estimated_count END) AS d_val,
                            MAX(CASE WHEN daynight = 'N' THEN estimated_count END) AS n_val,
                            MAX(CASE WHEN estimated_count IS NULL THEN prediction_status END) AS null_pred_status,
                            MAX(CASE WHEN estimated_count IS NULL THEN coverage_status END) AS null_cov_status,
                            MAX(CASE WHEN estimated_count IS NOT NULL THEN prediction_status END) AS valid_pred_status,
                            MAX(CASE WHEN estimated_count IS NOT NULL THEN coverage_status END) AS valid_cov_status,
                            MAX(model_version) AS model_version,
                            MAX(measurement_unit) AS measurement_unit,
                            MAX(value_type) AS value_type,
                            MAX(calibration_scale_km) AS calibration_scale_km,
                            COUNT(*) AS row_cnt
                        FROM estimated_viirs_block_month
                        WHERE region_id = ? AND block_id = ? AND year = ? AND month = ?
                          AND daynight IN ('D', 'N')
                    )
                    SELECT
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN ROUND(d_val + n_val, 2)
                            ELSE NULL
                        END AS estimated_count,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN COALESCE(valid_pred_status, 'ok_preliminary')
                            ELSE COALESCE(null_pred_status, 'missing_required_feature')
                        END AS prediction_status,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN valid_cov_status
                            ELSE COALESCE(null_cov_status, 'unknown')
                        END AS coverage_status,
                        model_version,
                        measurement_unit,
                        value_type,
                        calibration_scale_km,
                        row_cnt
                    FROM dn
                """

            try:
                row = db.con.execute(sql, params).fetchone()
                if row and row[7] and row[7] > 0:
                    est_cnt = float(row[0]) if row[0] is not None else None
                    p_status = (
                        PredictionStatus(row[1])
                        if row[1] in PredictionStatus._value2member_map_
                        else row[1]
                    )
                    c_status = (
                        CoverageStatus(row[2])
                        if row[2] in CoverageStatus._value2member_map_
                        else row[2]
                    )
                    m_ver = row[3]
                    m_unit = row[4]
                    v_type = (
                        ValueType(row[5])
                        if row[5] in ValueType._value2member_map_
                        else ValueType.ESTIMATED
                    )
                    cal_km = int(row[6]) if row[6] is not None else 50
                    is_synth = bool(m_ver and ("synthetic" in m_ver.lower() or "demo" in m_ver.lower()))
                    results.append(
                        SingleBlockPrediction(
                            block_id=b.block_id,
                            block_ix=b_ix,
                            block_iy=b_iy,
                            year=request.year,
                            month=request.month,
                            daynight=b_dn,
                            estimated_viirs_count=est_cnt,
                            estimated_count=est_cnt,
                            value_type=v_type,
                            prediction_status=p_status,
                            coverage_status=c_status,
                            model_version=m_ver,
                            measurement_unit=m_unit,
                            calibration_scale_km=cal_km,
                            is_synthetic_demo=is_synth,
                            error_message=None,
                        )
                    )
                else:
                    # Missing from precomputed table
                    results.append(
                        SingleBlockPrediction(
                            block_id=b.block_id,
                            block_ix=b_ix,
                            block_iy=b_iy,
                            year=request.year,
                            month=request.month,
                            daynight=b_dn,
                            estimated_viirs_count=None,
                            estimated_count=None,
                            value_type=ValueType.ESTIMATED,
                            prediction_status=PredictionStatus.MISSING_REQUIRED_FEATURE,
                            coverage_status=CoverageStatus.MISSING,
                            model_version=None,
                            measurement_unit=None,
                            calibration_scale_km=50,
                            is_synthetic_demo=False,
                            error_message="Block estimate not found in precomputed historical cache.",
                        )
                    )
            except Exception as e:
                logger.warning("Error querying precomputed estimates: %s", e)
                return None

        has_synth = any(p.is_synthetic_demo for p in results)
        return PredictResponse(
            region_id=request.region_id,
            year=request.year,
            month=request.month,
            daynight=dn,
            is_synthetic_demo=has_synth,
            synthetic_demo_notice=(
                "Predictions retrieved from synthetic demo precomputed estimates."
                if has_synth
                else None
            ),
            predictions=results,
            total_predictions=len(results),
        )

    async def _query_remote_ml(self, request: PredictRequest) -> Optional[PredictResponse]:
        """Query remote ML model via authenticated HTTP headers."""
        url = f"{self.settings.ML_MODEL_API_URL.rstrip('/')}/predict"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.settings.ML_MODEL_API_KEY or "",
            "Authorization": f"Bearer {self.settings.ML_MODEL_API_KEY or ''}",
        }
        async with httpx.AsyncClient(timeout=self.settings.ML_MODEL_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=request.model_dump(), headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return PredictResponse.model_validate(data)
            logger.warning("Remote ML returned non-200 code: %d %s", resp.status_code, resp.text)
            return None

    def _local_fallback_predict(self, request: PredictRequest) -> PredictResponse:
        """Run local calibration regression in dev, or return safe model_not_ready NULL payload in production."""
        blocks = self._normalize_blocks(request)
        results: List[SingleBlockPrediction] = []
        resp_status = "ok"
        resp_error: Optional[str] = None

        for b in blocks:
            modis_c = b.modis_count
            frp_s = b.modis_frp_sum
            b_dn = b.daynight or request.daynight or "ALL"
            b_ix, b_iy = self._parse_block_indices(b.block_id)

            try:
                est_viirs, status_str, err_msg = predict_single_block(
                    region_id=request.region_id,
                    year=request.year,
                    month=request.month,
                    block_id=b.block_id,
                    modis_count=modis_c,
                    modis_frp_sum=frp_s,
                    daynight=b_dn,
                    features=b.features,
                )
                status_enum = PredictionStatus(status_str) if status_str else None
                results.append(
                    SingleBlockPrediction(
                        block_id=b.block_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=request.year,
                        month=request.month,
                        daynight=b_dn,
                        estimated_viirs_count=est_viirs,
                        estimated_count=est_viirs,
                        prediction_status=status_enum,
                        model_version="local-empirical-v1.2-dev-only",
                        error_message=err_msg,
                    )
                )
            except NotImplementedError:
                resp_status = "model_not_ready"
                resp_error = "Validated model interface not connected"
                results.append(
                    SingleBlockPrediction(
                        block_id=b.block_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=request.year,
                        month=request.month,
                        daynight=b_dn,
                        estimated_viirs_count=None,
                        estimated_count=None,
                        prediction_status=PredictionStatus.NOT_PROCESSED,
                        model_version=None,
                        error_message=resp_error,
                    )
                )

        return PredictResponse(
            region_id=request.region_id,
            year=request.year,
            month=request.month,
            daynight=request.daynight or "ALL",
            status=resp_status,
            error=resp_error,
            synthetic_demo_notice=(
                "UNVALIDATED DEV-ONLY HEURISTIC FALLBACK (local-empirical-v1.2-dev-only). "
                "Not scientifically validated; do not use in production."
                if resp_status == "ok"
                else None
            ),
            predictions=results,
            total_predictions=len(results),
        )

    async def check_status(self) -> Dict[str, Any]:
        """Check status of remote ML service, precomputed estimates, and local fallback availability."""
        remote_ok = False
        if self.settings.ML_MODEL_API_URL:
            try:
                headers = {}
                if self.settings.ML_MODEL_API_KEY:
                    headers["X-API-Key"] = self.settings.ML_MODEL_API_KEY
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(
                        f"{self.settings.ML_MODEL_API_URL.rstrip('/')}/health",
                        headers=headers,
                    )
                    remote_ok = resp.status_code == 200
            except Exception:
                remote_ok = False

        master_exists = (
            bool(list(self.settings.DATA_DIR.glob("**/firechronicle_master_*.parquet")))
            or (self.settings.DATA_DIR / "firechronicle_master.parquet").exists()
            or bool(self.settings.REAL_DATA_DIR and list(self.settings.REAL_DATA_DIR.glob("**/firechronicle_master_*.parquet")))
        )
        precomputed_exists = (self.settings.DATA_DIR / "estimated_viirs_block_month.parquet").exists()

        return {
            "remote_ml_service_available": remote_ok,
            "remote_ml_url": self.settings.ML_MODEL_API_URL,
            "local_fallback_available": not self.settings.is_production,
            "master_dataset_available": master_exists,
            "precomputed_estimates_available": precomputed_exists,
            "active_mode": (
                "remote_http"
                if remote_ok
                else ("model_not_ready" if self.settings.is_production else "precomputed_and_dev_fallback")
            ),
        }
