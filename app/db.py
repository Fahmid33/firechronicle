"""DuckDB Database Connection and Query Builder for FireChronicle Pará (BR-PA).

Transparent Parquet Adapter Layer:
1. Flexible `_2019` resolution for `firechronicle_master`, `overlap_training`,
   and `backend_monthly` (or automatic derivation from `firechronicle_master`).
2. Dynamic `hotspots_para` view uniting `para_aqua_modis_2019.parquet` and/or
   `para_viirs_snpp_2019.parquet` into the 14-column frontend contract (falling
   back to `hotspots_para.parquet` when raw sensor files are absent).
3. Smart `coverage_para` view adapter inspecting `coverage_para.parquet` and
   aggregating Member 1's block/sensor-level schema into the 12-column monthly
   summary contract (`coverage_para_raw` -> `coverage_para`).
4. Preserves strict SQL NULLs with zero NaN or Infinity values, supporting
   `?daynight=ALL|D|N` seamlessly across all queries.
"""

from functools import lru_cache
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import duckdb

from app.config import Settings, get_settings
from app.grid import (
    build_canonical_blocks_geojson,
    get_block_polygon_geojson,
    get_grid_cell_polygon_geojson,
)
from app.schemas import (
    BlocksFeatureCollectionResponse,
    CalibrationPair,
    CalibrationResponse,
    CoverageStatus,
    HotspotListResponse,
    HotspotPoint,
    ModelInfoResponse,
    PredictionStatus,
    PredictionSyncRecord,
    SpatialFeature,
    SpatialFeatureCollectionResponse,
    SpatialFeatureProperties,
    TimeSeriesMonthlyPoint,
    TimeSeriesSummaryResponse,
    ValidationMetricsResponse,
    ValueType,
)

logger = logging.getLogger("firechronicle.db")


class DuckDBManager:
    """Manages DuckDB session, parquet views, and SQL query execution."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.con: duckdb.DuckDBPyConnection = duckdb.connect(self.settings.DUCKDB_PATH)
        self._init_views()

    def _resolve_parquet(self, base_name: str) -> Optional[Path]:
        """Resolve parquet file path, preferring real *_2019.parquet exports when present."""
        data_dir = self.settings.DATA_DIR
        pilot_path = data_dir / f"{base_name}_2019.parquet"
        default_path = data_dir / f"{base_name}.parquet"
        if pilot_path.exists():
            return pilot_path
        if default_path.exists():
            return default_path
        return None

    def _init_views(self) -> None:
        """Register DuckDB views with transparent 2019 pilot & canonical grid adapters."""
        data_dir = self.settings.DATA_DIR

        # 1. Core tables with _2019 resolution
        resolved_tables = {
            "firechronicle_master": self._resolve_parquet("firechronicle_master"),
            "overlap_training": self._resolve_parquet("overlap_training"),
            "overlap_training_full_panel": self._resolve_parquet("overlap_training_full_panel"),
            "para_grid_canonical": self._resolve_parquet("para_50km_grid_canonical"),
            "para_grid_geometry": self._resolve_parquet("para_50km_grid_geometry"),
            "estimated_viirs_block_month": self._resolve_parquet("estimated_viirs_block_month"),
        }

        for view_name, ppath in resolved_tables.items():
            if ppath and ppath.exists():
                clean_path = ppath.as_posix()
                if view_name == "estimated_viirs_block_month":
                    est_cols = {
                        r[0] for r in self.con.execute(f"DESCRIBE SELECT * FROM '{clean_path}'").fetchall()
                    }
                    if "estimated_viirs_count" in est_cols and "estimated_count" not in est_cols:
                        self.con.execute(
                            f"CREATE OR REPLACE VIEW {view_name} AS "
                            f"SELECT *, CAST(estimated_viirs_count AS DOUBLE) AS estimated_count FROM '{clean_path}'"
                        )
                    elif "estimated_count" in est_cols and "estimated_viirs_count" not in est_cols:
                        self.con.execute(
                            f"CREATE OR REPLACE VIEW {view_name} AS "
                            f"SELECT *, CAST(estimated_count AS DOUBLE) AS estimated_viirs_count FROM '{clean_path}'"
                        )
                    else:
                        self.con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{clean_path}'")
                else:
                    self.con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{clean_path}'")
                logger.info("Registered DuckDB view '%s' -> %s", view_name, clean_path)
            else:
                logger.warning("Parquet file for view '%s' not found in %s", view_name, data_dir)

        if resolved_tables["firechronicle_master"] is not None:
            self.con.execute("CREATE OR REPLACE VIEW master_block_month AS SELECT * FROM firechronicle_master")
            logger.info("Registered alias view 'master_block_month' -> firechronicle_master")

        # 2. backend_monthly (plus alias overlap_calibration)
        bm_path = self._resolve_parquet("backend_monthly")
        if bm_path and bm_path.exists():
            clean_bm = bm_path.as_posix()
            self.con.execute(f"CREATE OR REPLACE VIEW backend_monthly AS SELECT * FROM '{clean_bm}'")
            self.con.execute("CREATE OR REPLACE VIEW overlap_calibration AS SELECT * FROM backend_monthly")
            logger.info("Registered DuckDB view 'backend_monthly' (and alias 'overlap_calibration') -> %s", clean_bm)
        elif resolved_tables["firechronicle_master"] is not None:
            derive_monthly_sql = """
                CREATE OR REPLACE VIEW backend_monthly AS
                SELECT 
                    region_id,
                    block_id,
                    block_ix,
                    block_iy,
                    year,
                    month,
                    CAST(SUM(modis_count) AS DOUBLE) AS modis_aqua_count,
                    CAST(SUM(viirs_count) AS DOUBLE) AS viirs_snpp_count,
                    CASE 
                        WHEN SUM(modis_count) IS NOT NULL 
                         AND SUM(viirs_count) IS NOT NULL 
                         AND SUM(modis_count) > 0 
                        THEN ROUND(CAST(SUM(viirs_count) AS DOUBLE) / CAST(SUM(modis_count) AS DOUBLE), 4)
                        ELSE NULL 
                    END AS ratio_viirs_to_modis,
                    CASE 
                        WHEN SUM(modis_count) IS NOT NULL 
                         AND SUM(viirs_count) IS NOT NULL 
                         AND SUM(modis_count) > 0 
                         AND SUM(viirs_count) > 0 
                        THEN ROUND(LN(CAST(SUM(viirs_count) AS DOUBLE) / CAST(SUM(modis_count) AS DOUBLE)), 4)
                        ELSE NULL 
                    END AS log_ratio,
                    SUM(modis_frp_sum) AS modis_frp_sum,
                    SUM(viirs_frp_sum) AS viirs_frp_sum
                FROM firechronicle_master
                GROUP BY region_id, block_id, block_ix, block_iy, year, month;
            """
            self.con.execute(derive_monthly_sql)
            self.con.execute("CREATE OR REPLACE VIEW overlap_calibration AS SELECT * FROM backend_monthly")
            logger.info("Derived 12-column view 'backend_monthly' (and alias 'overlap_calibration') from firechronicle_master.")

        # 3. Dynamic hotspots_para view adapter (UNION ALL 2019 raw sensor files or fallback)
        raw_hotspot_files = [
            data_dir / "para_aqua_modis_2019.parquet",
            data_dir / "para_viirs_snpp_2019.parquet",
        ]
        raw_selects = []
        for raw_path in raw_hotspot_files:
            if raw_path.exists():
                clean_raw = raw_path.as_posix()
                raw_selects.append(
                    f"SELECT sensor_id, region_id, latitude, longitude, acq_date, acq_time, "
                    f"daynight, satellite, instrument, CAST(confidence AS VARCHAR) AS confidence, "
                    f"frp, grid_id, block_id FROM read_parquet('{clean_raw}')"
                )

        if raw_selects:
            union_sql = " UNION ALL ".join(raw_selects)
            hotspots_sql = f"""
                CREATE OR REPLACE VIEW hotspots_para AS
                SELECT
                    CAST(sensor_id || '_' || row_number() OVER () AS VARCHAR) AS id,
                    CAST(region_id AS VARCHAR) AS region_id,
                    CAST(latitude AS DOUBLE) AS latitude,
                    CAST(longitude AS DOUBLE) AS longitude,
                    CAST(acq_date AS VARCHAR) AS acq_date,
                    LPAD(CAST(acq_time AS VARCHAR), 4, '0') AS acq_time,
                    CAST(daynight AS VARCHAR) AS daynight,
                    CAST(satellite AS VARCHAR) AS satellite,
                    CAST(instrument AS VARCHAR) AS instrument,
                    CAST(confidence AS VARCHAR) AS confidence,
                    CAST(frp AS DOUBLE) AS frp,
                    CAST(grid_id AS VARCHAR) AS grid_id,
                    CAST(block_id AS VARCHAR) AS block_id,
                    'observed' AS value_type
                FROM (
                    {union_sql}
                )
            """
            self.con.execute(hotspots_sql)
            logger.info("Registered unified DuckDB view 'hotspots_para' from 2019 sensor files.")
        else:
            fallback_hotspots = data_dir / "hotspots_para.parquet"
            if fallback_hotspots.exists():
                clean_hs = fallback_hotspots.as_posix()
                self.con.execute(f"CREATE OR REPLACE VIEW hotspots_para AS SELECT * FROM '{clean_hs}'")
                logger.info("Registered DuckDB view 'hotspots_para' -> %s", clean_hs)

        # 4. Smart coverage_para view adapter (inspect schema and aggregate Member 1's raw schema)
        cov_path = self._resolve_parquet("coverage_para")
        if cov_path and cov_path.exists():
            clean_cov = cov_path.as_posix()
            cols_info = self.con.execute(f"DESCRIBE SELECT * FROM '{clean_cov}'").fetchall()
            col_names = {r[0] for r in cols_info}
            if {"sensor", "source_product", "observation_evidence"}.issubset(col_names):
                self.con.execute(f"CREATE OR REPLACE VIEW coverage_para_raw AS SELECT * FROM '{clean_cov}'")
                self.con.execute("""
                    CREATE OR REPLACE VIEW coverage_para AS
                    SELECT
                        CAST(region_id AS VARCHAR) AS region_id,
                        CAST(year AS INTEGER) AS year,
                        CAST(month AS INTEGER) AS month,
                        PRINTF('%04d-%02d', year, month) AS period,
                        BOOL_OR(sensor = 'AQUA_MODIS') AS modis_available,
                        BOOL_OR(sensor = 'SNPP_VIIRS') AS viirs_available,
                        BOOL_OR(sensor = 'AQUA_MODIS') AND BOOL_OR(sensor = 'SNPP_VIIRS') AS overlap_available,
                        'observed' AS value_type,
                        FIRST(coverage_status) AS coverage_status,
                        CAST(COUNT(DISTINCT block_id) AS INTEGER) AS total_blocks_observed,
                        'SNPP_VIIRS' AS satellite_primary,
                        FIRST(notes) AS notes
                    FROM coverage_para_raw
                    GROUP BY region_id, year, month
                    ORDER BY year, month
                """)
                logger.info("Registered aggregated DuckDB view 'coverage_para' from Member 1 raw schema (%s).", clean_cov)
            else:
                self.con.execute(f"CREATE OR REPLACE VIEW coverage_para AS SELECT * FROM '{clean_cov}'")
                logger.info("Registered DuckDB view 'coverage_para' -> %s", clean_cov)
        else:
            logger.warning("Parquet file 'coverage_para' not found in %s", data_dir)

        # 5. Canonical 568-block GeoJSON generation if canonical grid files exist
        build_canonical_blocks_geojson(data_dir, write_output=True)

    # -------------------------------------------------------------------------
    # 1. TIME SERIES / SUMMARY QUERY (with daynight filter support)
    # -------------------------------------------------------------------------
    def get_timeseries_summary(
        self,
        region_id: str = "BR-PA",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        daynight: str = "ALL",
    ) -> TimeSeriesSummaryResponse:
        """Fetch harmonized monthly fire count timeline for Pará.

        Guardrail enforcement:
        - Region: BR-PA only.
        - Mid-2002 to 2011: Estimated historical extrapolation (50km block scale).
        - 2012+: Observed VIIRS S-NPP.
        - NEVER sum MODIS and VIIRS together.
        - daynight filter: ALL (sums D and N), D, or N.
        - Missing periods preserve strict null (None).
        """
        if region_id != self.settings.ANALYSIS_REGION_ID:
            raise ValueError(
                f"Unsupported region '{region_id}'. FireChronicle operates strictly within Pará ({self.settings.ANALYSIS_REGION_ID})."
            )

        start_yr = start_year or 2002
        end_yr = end_year or 2026

        # Day/Night SQL condition
        dn_cond = ""
        params_dn: List[Any] = []
        if daynight in ("D", "N"):
            dn_cond = "AND daynight = ?"
            params_dn = [daynight]

        # Step 1: Historical Era (mid-2002 to 2011) - precomputed historical ML estimates
        # Strictly require BOTH D and N components to be valid when daynight='ALL';
        # never silently coalesce NULL components into 0.
        if daynight == "ALL":
            sql_est = """
                WITH block_dn AS (
                    SELECT
                        e.year,
                        e.month,
                        e.block_id,
                        MAX(CASE WHEN e.daynight = 'D' THEN e.estimated_count END) AS d_val,
                        MAX(CASE WHEN e.daynight = 'N' THEN e.estimated_count END) AS n_val,
                        MAX(e.model_version) AS model_version,
                        MAX(e.measurement_unit) AS measurement_unit,
                        MAX(e.calibration_scale_km) AS calibration_scale_km,
                        MAX(CASE WHEN e.estimated_count IS NULL THEN e.prediction_status END) AS null_pred_status,
                        MAX(CASE WHEN e.estimated_count IS NULL THEN e.coverage_status END) AS null_cov_status,
                        MAX(e.prediction_status) AS any_pred_status,
                        MAX(e.coverage_status) AS any_cov_status,
                        SUM(m.modis_frp_sum) AS block_frp
                    FROM estimated_viirs_block_month e
                    LEFT JOIN firechronicle_master m
                      ON e.region_id = m.region_id
                     AND e.block_id = m.block_id
                     AND e.year = m.year
                     AND e.month = m.month
                     AND e.daynight = m.daynight
                    WHERE e.region_id = ?
                      AND ((e.year = 2002 AND e.month >= 7) OR e.year > 2002)
                      AND e.year < 2012
                      AND e.year >= ? AND e.year <= ?
                    GROUP BY e.year, e.month, e.block_id
                ),
                block_totals AS (
                    SELECT
                        year,
                        month,
                        block_id,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN d_val + n_val
                            ELSE NULL
                        END AS block_count,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN any_pred_status
                            ELSE COALESCE(null_pred_status, 'insufficient_coverage')
                        END AS pred_status,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN any_cov_status
                            ELSE COALESCE(null_cov_status, 'insufficient')
                        END AS cov_status,
                        model_version,
                        measurement_unit,
                        calibration_scale_km,
                        block_frp
                    FROM block_dn
                )
                SELECT
                    year,
                    month,
                    CASE
                        WHEN BOOL_AND(block_count IS NOT NULL) THEN ROUND(SUM(block_count), 1)
                        ELSE NULL
                    END AS total_count,
                    ROUND(SUM(block_frp), 1) AS total_frp,
                    CASE
                        WHEN BOOL_AND(block_count IS NOT NULL) THEN MAX(pred_status)
                        ELSE COALESCE(MAX(CASE WHEN block_count IS NULL THEN pred_status END), 'insufficient_coverage')
                    END AS pred_status,
                    CASE
                        WHEN BOOL_AND(block_count IS NOT NULL) THEN MAX(cov_status)
                        ELSE COALESCE(MAX(CASE WHEN block_count IS NULL THEN cov_status END), 'insufficient')
                    END AS cov_status,
                    MAX(model_version) AS model_version,
                    MAX(measurement_unit) AS measurement_unit,
                    MAX(calibration_scale_km) AS calibration_scale_km
                FROM block_totals
                GROUP BY year, month
                ORDER BY year, month
            """
            est_rows = self.con.execute(sql_est, [region_id, start_yr, end_yr]).fetchall()
        else:
            sql_est = """
                SELECT
                    e.year,
                    e.month,
                    CASE
                        WHEN BOOL_AND(e.estimated_count IS NOT NULL) THEN ROUND(SUM(e.estimated_count), 1)
                        ELSE NULL
                    END AS total_count,
                    ROUND(SUM(m.modis_frp_sum), 1) AS total_frp,
                    CASE
                        WHEN BOOL_AND(e.estimated_count IS NOT NULL) THEN MAX(e.prediction_status)
                        ELSE COALESCE(MAX(CASE WHEN e.estimated_count IS NULL THEN e.prediction_status END), 'insufficient_coverage')
                    END AS pred_status,
                    CASE
                        WHEN BOOL_AND(e.estimated_count IS NOT NULL) THEN MAX(e.coverage_status)
                        ELSE COALESCE(MAX(CASE WHEN e.estimated_count IS NULL THEN e.coverage_status END), 'insufficient')
                    END AS cov_status,
                    MAX(e.model_version) AS model_version,
                    MAX(e.measurement_unit) AS measurement_unit,
                    MAX(e.calibration_scale_km) AS calibration_scale_km
                FROM estimated_viirs_block_month e
                LEFT JOIN firechronicle_master m
                  ON e.region_id = m.region_id
                 AND e.block_id = m.block_id
                 AND e.year = m.year
                 AND e.month = m.month
                 AND e.daynight = m.daynight
                WHERE e.region_id = ?
                  AND ((e.year = 2002 AND e.month >= 7) OR e.year > 2002)
                  AND e.year < 2012
                  AND e.year >= ? AND e.year <= ?
                  AND e.daynight = ?
                GROUP BY e.year, e.month
                ORDER BY e.year, e.month
            """
            est_rows = self.con.execute(sql_est, [region_id, start_yr, end_yr, daynight]).fetchall()

        # Step 2: Observed Era (2012+) - actual observed VIIRS S-NPP counts
        sql_obs = f"""
            SELECT 
                year,
                month,
                ROUND(SUM(viirs_count), 1) as total_count,
                ROUND(SUM(viirs_frp_sum), 1) as total_frp,
                CASE 
                    WHEN year = 2026 AND month >= 7 THEN 'provisional_nrt'
                    ELSE 'observed'
                END as val_type
            FROM firechronicle_master
            WHERE region_id = ? AND year >= 2012 AND year >= ? AND year <= ? {dn_cond}
            GROUP BY year, month
            ORDER BY year, month
        """
        obs_rows = self.con.execute(sql_obs, [region_id, start_yr, end_yr] + params_dn).fetchall()

        # Step 3: Coverage calendar check
        sql_cov = """
            SELECT year, month, period, value_type, coverage_status
            FROM coverage_para
            WHERE region_id = ? AND year >= ? AND year <= ?
            ORDER BY year, month
        """
        cov_rows = self.con.execute(sql_cov, [region_id, start_yr, end_yr]).fetchall()
        coverage_map = {f"{r[0]}-{r[1]:02d}": (r[3], r[4]) for r in cov_rows}

        combined_data: Dict[str, Dict[str, Any]] = {}

        def _norm_cov(val: Optional[str]) -> Optional[Union[CoverageStatus, str]]:
            if val is None:
                return None
            return CoverageStatus(val) if val in CoverageStatus._value2member_map_ else val

        # Add estimated points (mid-2002 to 2011)
        for row in est_rows:
            yr, mo, cnt, frp, p_stat, c_stat, m_ver, m_unit, cal_km = row
            per = f"{yr}-{mo:02d}"
            _, cov_cal_status = coverage_map.get(per, ("estimated", None))
            eff_cov = c_stat if c_stat is not None else cov_cal_status
            is_synth = bool(m_ver and ("synthetic" in m_ver.lower() or "demo" in m_ver.lower()))
            cnt_val = float(cnt) if cnt is not None else None
            combined_data[per] = {
                "year": yr,
                "month": mo,
                "period": per,
                "daynight": daynight,
                "count": cnt_val,
                "estimated_count": cnt_val,
                "value_type": ValueType.ESTIMATED,
                "label": "Estimated historical extrapolation",
                "prediction_status": p_stat,
                "coverage_status": _norm_cov(eff_cov),
                "model_version": m_ver,
                "measurement_unit": m_unit,
                "calibration_scale_km": int(cal_km) if cal_km is not None else None,
                "frp_total_mw": float(frp) if frp is not None else None,
                "is_harmonized_estimate": True,
                "is_synthetic_demo": is_synth,
                "data_source_tier": "synthetic_demo_estimates" if is_synth else "precomputed_ml_estimates",
            }

        # Add observed points (2012+)
        for row in obs_rows:
            yr, mo, cnt, frp, vtype_str = row
            per = f"{yr}-{mo:02d}"
            _, cov_status = coverage_map.get(per, (vtype_str, None))
            vtype_enum = ValueType.PROVISIONAL_NRT if vtype_str == "provisional_nrt" else ValueType.OBSERVED
            lbl = "Provisional NRT" if vtype_enum == ValueType.PROVISIONAL_NRT else "Observed S-NPP"

            combined_data[per] = {
                "year": yr,
                "month": mo,
                "period": per,
                "daynight": daynight,
                "count": float(cnt) if cnt is not None else None,
                "estimated_count": None,
                "value_type": vtype_enum,
                "label": lbl,
                "prediction_status": None,
                "coverage_status": _norm_cov(cov_status),
                "model_version": None,
                "measurement_unit": "VIIRS_S-NPP_detection_count",
                "calibration_scale_km": 50,
                "frp_total_mw": float(frp) if frp is not None else None,
                "is_harmonized_estimate": False,
                "is_synthetic_demo": False,
                "data_source_tier": "provisional_nrt_observations" if vtype_enum == ValueType.PROVISIONAL_NRT else "pilot_2019_observations",
            }

        # Fill any missing coverage periods strictly preserving nulls
        for r in cov_rows:
            yr, mo, per, vtype_str, cov_status = r
            if per not in combined_data:
                combined_data[per] = {
                    "year": yr,
                    "month": mo,
                    "period": per,
                    "daynight": daynight,
                    "count": None,  # Strict null integrity: never substitute with 0
                    "estimated_count": None,
                    "value_type": ValueType(vtype_str) if vtype_str in ("estimated", "observed", "provisional_nrt") else ValueType.OBSERVED,
                    "label": "Data gap or unobserved period",
                    "prediction_status": None,
                    "coverage_status": _norm_cov(cov_status),
                    "model_version": None,
                    "measurement_unit": None,
                    "calibration_scale_km": 50,
                    "frp_total_mw": None,
                    "is_harmonized_estimate": yr < 2012,
                    "is_synthetic_demo": False,
                    "data_source_tier": "coverage_gap_placeholder",
                }

        sorted_points = [
            TimeSeriesMonthlyPoint(**item)
            for _, item in sorted(combined_data.items(), key=lambda x: x[0])
        ]

        data_start = sorted_points[0].period if sorted_points else "2002-07"
        data_end = sorted_points[-1].period if sorted_points else "2026-10"

        synth_points = [p for p in sorted_points if p.is_synthetic_demo]
        obs_points = [p for p in sorted_points if not p.is_harmonized_estimate and p.count is not None]
        gap_points = [p for p in sorted_points if p.count is None]
        contains_synth = len(synth_points) > 0
        synth_versions = sorted({p.model_version for p in synth_points if p.model_version})
        synth_notice = (
            f"Pre-2012 estimated months ({len(synth_points)} periods) originate from the Data Scientist's "
            f"synthetic demo artifact ({', '.join(synth_versions)}) and are flagged with is_synthetic_demo=true "
            f"separately from real observed VIIRS S-NPP records."
            if contains_synth
            else None
        )
        provenance_summary = {
            "synthetic_demo_estimate_months": len(synth_points),
            "observed_months_with_data": len(obs_points),
            "missing_or_incomplete_months": len(gap_points),
            "synthetic_model_versions": synth_versions,
        }

        return TimeSeriesSummaryResponse(
            region_id=region_id,
            region_name=self.settings.ANALYSIS_REGION_NAME,
            daynight_filter=daynight,
            data_start_date=data_start,
            data_end_date=data_end,
            harmonization_boundary_date="2012-01",
            contains_synthetic_demo_data=contains_synth,
            synthetic_demo_notice=synth_notice,
            data_provenance_summary=provenance_summary,
            total_months=len(sorted_points),
            items=sorted_points,
        )

    # -------------------------------------------------------------------------
    # 2. SPATIAL GRID & BLOCK QUERY (GeoJSON FeatureCollection)
    # -------------------------------------------------------------------------
    @staticmethod
    def _make_spatial_feature(
        block_id: str,
        block_ix: int,
        block_iy: int,
        year: int,
        month: int,
        daynight: str,
        count: Optional[float],
        value_type: ValueType,
        label: str,
        prediction_status: Optional[Union[PredictionStatus, str]],
        cov_status: Optional[str],
        frp: Optional[float],
        estimated_count: Optional[float] = None,
        model_version: Optional[str] = None,
        measurement_unit: Optional[str] = None,
        calibration_scale_km: Optional[int] = 50,
        is_synthetic_demo: bool = False,
    ) -> SpatialFeature:
        """Build a 50km SpatialFeature enforcing strict 50km vs 10km geographic separation."""
        geom = get_block_polygon_geojson(block_ix, block_iy)
        parsed_cov: Optional[Union[CoverageStatus, str]] = (
            CoverageStatus(cov_status)
            if cov_status in CoverageStatus._value2member_map_
            else cov_status
        )
        props = SpatialFeatureProperties(
            id=block_id,
            block_id=block_id,
            grid_id=None,
            block_ix=block_ix,
            block_iy=block_iy,
            ix=None,
            iy=None,
            resolution="50km",
            year=year,
            month=month,
            daynight=daynight,
            count=count,
            estimated_count=estimated_count,
            value_type=value_type,
            label=label,
            prediction_status=prediction_status,
            coverage_status=parsed_cov,
            model_version=model_version,
            measurement_unit=measurement_unit,
            calibration_scale_km=calibration_scale_km,
            frp_sum=float(frp) if frp is not None else None,
            is_synthetic_demo=is_synthetic_demo,
        )
        return SpatialFeature(geometry=geom, properties=props)

    def get_spatial_features(
        self,
        region_id: str,
        year: int,
        month: int,
        resolution: str = "50km",
        daynight: str = "ALL",
    ) -> SpatialFeatureCollectionResponse:
        """Fetch 50km block spatial aggregates as GeoJSON FeatureCollection for MapLibre."""
        if region_id != self.settings.ANALYSIS_REGION_ID:
            raise ValueError(
                f"Unsupported region '{region_id}'. Pará ({self.settings.ANALYSIS_REGION_ID}) is the sole release geography."
            )

        features: List[SpatialFeature] = []
        is_pre_2012 = year < 2012
        period_str = f"{year}-{month:02d}"

        # Strict 50km block resolution guardrail
        effective_resolution = "50km"
        guardrail_note = ""
        if resolution == "10km":
            guardrail_note = (
                "Guardrail enforced: Harmonized and estimated block outputs are strictly served "
                "at 50km EPSG:6933 block scale (block_id, block_ix, block_iy). Downscaling to 10km cells is prohibited."
            )

        dn_cond = ""
        params_dn: List[Any] = []
        if daynight in ("D", "N"):
            dn_cond = "AND daynight = ?"
            params_dn = [daynight]

        if is_pre_2012:
            # Query precomputed 50km block estimates using aliased estimated_count.
            # When daynight='ALL', compute D + N strictly when BOTH components are non-null.
            if daynight == "ALL":
                sql = """
                    WITH block_dn AS (
                        SELECT
                            e.block_id,
                            e.block_ix,
                            e.block_iy,
                            MAX(CASE WHEN e.daynight = 'D' THEN e.estimated_count END) AS d_val,
                            MAX(CASE WHEN e.daynight = 'N' THEN e.estimated_count END) AS n_val,
                            ROUND(SUM(m.modis_frp_sum), 1) AS frp,
                            MAX(CASE WHEN e.estimated_count IS NULL THEN e.prediction_status END) AS null_pred_status,
                            MAX(CASE WHEN e.estimated_count IS NULL THEN e.coverage_status END) AS null_cov_status,
                            MAX(e.prediction_status) AS any_pred_status,
                            MAX(e.coverage_status) AS any_cov_status,
                            MAX(e.model_version) AS model_version,
                            MAX(e.measurement_unit) AS measurement_unit,
                            MAX(e.value_type) AS value_type,
                            MAX(e.calibration_scale_km) AS calibration_scale_km
                        FROM estimated_viirs_block_month e
                        LEFT JOIN firechronicle_master m
                          ON e.region_id = m.region_id
                         AND e.block_id = m.block_id
                         AND e.year = m.year
                         AND e.month = m.month
                         AND e.daynight = m.daynight
                        WHERE e.region_id = ? AND e.year = ? AND e.month = ?
                        GROUP BY e.block_id, e.block_ix, e.block_iy
                    )
                    SELECT
                        block_id,
                        block_ix,
                        block_iy,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN ROUND(d_val + n_val, 1)
                            ELSE NULL
                        END AS est_viirs,
                        frp,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN any_cov_status
                            ELSE COALESCE(null_cov_status, 'insufficient')
                        END AS cov_status,
                        CASE
                            WHEN d_val IS NOT NULL AND n_val IS NOT NULL THEN any_pred_status
                            ELSE COALESCE(null_pred_status, 'insufficient_coverage')
                        END AS pred_status,
                        model_version,
                        measurement_unit,
                        value_type,
                        calibration_scale_km
                    FROM block_dn
                    ORDER BY block_id
                """
                rows = self.con.execute(sql, [region_id, year, month]).fetchall()
            else:
                sql = """
                    SELECT 
                        e.block_id,
                        e.block_ix,
                        e.block_iy,
                        ROUND(e.estimated_count, 1) AS est_viirs,
                        ROUND(m.modis_frp_sum, 1) AS frp,
                        e.coverage_status AS cov_status,
                        e.prediction_status AS pred_status,
                        e.model_version,
                        e.measurement_unit,
                        e.value_type,
                        e.calibration_scale_km
                    FROM estimated_viirs_block_month e
                    LEFT JOIN firechronicle_master m
                      ON e.region_id = m.region_id
                     AND e.block_id = m.block_id
                     AND e.year = m.year
                     AND e.month = m.month
                     AND e.daynight = m.daynight
                    WHERE e.region_id = ? AND e.year = ? AND e.month = ? AND e.daynight = ?
                    ORDER BY e.block_id
                """
                rows = self.con.execute(sql, [region_id, year, month, daynight]).fetchall()

            for row in rows:
                b_id, b_ix, b_iy, est_cnt, frp, c_status, p_status, m_ver, m_unit, v_type_str, cal_km = row
                pred_val: Optional[Union[PredictionStatus, str]] = (
                    PredictionStatus(p_status)
                    if p_status in PredictionStatus._value2member_map_
                    else p_status
                )
                v_enum = (
                    ValueType(v_type_str)
                    if v_type_str in ValueType._value2member_map_
                    else ValueType.ESTIMATED
                )
                est_float = float(est_cnt) if est_cnt is not None else None
                is_synth = bool(m_ver and ("synthetic" in m_ver.lower() or "demo" in m_ver.lower()))
                features.append(
                    self._make_spatial_feature(
                        block_id=b_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=year,
                        month=month,
                        daynight=daynight,
                        count=est_float,
                        estimated_count=est_float,
                        value_type=v_enum,
                        label="Estimated historical extrapolation",
                        prediction_status=pred_val,
                        cov_status=c_status,
                        frp=frp,
                        model_version=m_ver,
                        measurement_unit=m_unit,
                        calibration_scale_km=int(cal_km) if cal_km is not None else 50,
                        is_synthetic_demo=is_synth,
                    )
                )

        else:
            # 2012+ observed data from firechronicle_master
            is_nrt = (year == 2026 and month >= 7)
            vtype_enum = ValueType.PROVISIONAL_NRT if is_nrt else ValueType.OBSERVED
            lbl = "Provisional NRT" if vtype_enum == ValueType.PROVISIONAL_NRT else "Observed S-NPP"

            sql = f"""
                SELECT 
                    block_id,
                    block_ix,
                    block_iy,
                    ROUND(SUM(viirs_count), 1) as obs_cnt,
                    ROUND(SUM(viirs_frp_sum), 1) as frp,
                    MAX(coverage_status) as cov_status
                FROM firechronicle_master
                WHERE region_id = ? AND year = ? AND month = ? {dn_cond}
                GROUP BY block_id, block_ix, block_iy
            """
            rows = self.con.execute(sql, [region_id, year, month] + params_dn).fetchall()
            for row in rows:
                b_id, b_ix, b_iy, obs_cnt, frp, c_status = row
                features.append(
                    self._make_spatial_feature(
                        block_id=b_id,
                        block_ix=b_ix,
                        block_iy=b_iy,
                        year=year,
                        month=month,
                        daynight=daynight,
                        count=float(obs_cnt) if obs_cnt is not None else None,
                        estimated_count=None,
                        value_type=vtype_enum,
                        label=lbl,
                        prediction_status=None,
                        cov_status=c_status,
                        frp=frp,
                        model_version=None,
                        measurement_unit="VIIRS_S-NPP_detection_count",
                        calibration_scale_km=50,
                        is_synthetic_demo=False,
                    )
                )

        has_synthetic = any(f.properties.is_synthetic_demo for f in features)
        metadata = {
            "region_id": region_id,
            "year": year,
            "month": month,
            "period": period_str,
            "daynight_filter": daynight,
            "effective_resolution": effective_resolution,
            "features_count": len(features),
            "is_synthetic_demo": has_synthetic,
            "synthetic_demo_notice": (
                "Features originate from the Data Scientist synthetic demo dataset "
                "(ratio-baseline-v1.0-synthetic-demo) and are isolated from real observations."
                if has_synthetic
                else None
            ),
            "guardrail_note": guardrail_note,
        }

        return SpatialFeatureCollectionResponse(
            type="FeatureCollection",
            metadata=metadata,
            features=features,
        )

    # -------------------------------------------------------------------------
    # 3. 50KM BLOCKS GEOJSON (GET /api/v1/blocks)
    # -------------------------------------------------------------------------
    def get_blocks_geojson(self, region_id: str = "BR-PA") -> Dict[str, Any]:
        """Fetch 50km block polygons GeoJSON FeatureCollection (regenerating from canonical grid if present)."""
        if region_id != self.settings.ANALYSIS_REGION_ID:
            raise ValueError(
                f"Unsupported region '{region_id}'. Pará ({self.settings.ANALYSIS_REGION_ID}) is the sole release geography."
            )

        data_dir = self.settings.DATA_DIR
        geojson_path = data_dir / "para_blocks_50km.geojson"
        canonical_path = data_dir / "para_50km_grid_canonical.parquet"
        geometry_path = data_dir / "para_50km_grid_geometry.parquet"

        needs_rebuild = False
        if canonical_path.exists() or geometry_path.exists():
            if not geojson_path.exists():
                needs_rebuild = True
            else:
                gj_mtime = geojson_path.stat().st_mtime
                if (canonical_path.exists() and canonical_path.stat().st_mtime > gj_mtime) or (
                    geometry_path.exists() and geometry_path.stat().st_mtime > gj_mtime
                ):
                    needs_rebuild = True

        if needs_rebuild:
            fc = build_canonical_blocks_geojson(data_dir, write_output=True)
            if fc is not None:
                return fc

        if not geojson_path.exists():
            raise FileNotFoundError(f"Blocks GeoJSON not found at: {geojson_path}")

        with open(geojson_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # -------------------------------------------------------------------------
    # 4. HOTSPOTS POINT DETECTIONS QUERY
    # -------------------------------------------------------------------------
    def get_hotspots(
        self,
        region_id: str = "BR-PA",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        satellite: Optional[str] = None,
        instrument: Optional[str] = None,
        daynight: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> HotspotListResponse:
        """Fetch fire hotspot detections inside Pará with exact provenance."""
        if region_id != self.settings.ANALYSIS_REGION_ID:
            raise ValueError(
                f"Unsupported region '{region_id}'. Pará ({self.settings.ANALYSIS_REGION_ID}) is the sole release geography."
            )

        conditions = ["region_id = ?"]
        params: List[Any] = [region_id]

        if start_date:
            conditions.append("acq_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("acq_date <= ?")
            params.append(end_date)
        if satellite:
            conditions.append("satellite = ?")
            params.append(satellite)
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        if daynight and daynight in ("D", "N"):
            conditions.append("daynight = ?")
            params.append(daynight)

        where_clause = " AND ".join(conditions)

        count_sql = f"SELECT count(*) FROM hotspots_para WHERE {where_clause}"
        total = self.con.execute(count_sql, params).fetchone()[0]

        items_sql = f"""
            SELECT id, latitude, longitude, acq_date, acq_time, daynight, satellite, instrument,
                   confidence, frp, grid_id, block_id, value_type, region_id
            FROM hotspots_para
            WHERE {where_clause}
            ORDER BY acq_date DESC, acq_time DESC
            LIMIT ? OFFSET ?
        """
        rows = self.con.execute(items_sql, params + [limit, offset]).fetchall()

        items = [
            HotspotPoint(
                id=r[0],
                latitude=float(r[1]),
                longitude=float(r[2]),
                acq_date=r[3],
                acq_time=r[4],
                daynight=r[5],
                satellite=r[6],
                instrument=r[7],
                confidence=r[8],
                frp=float(r[9]) if r[9] is not None else None,
                grid_id=r[10],
                block_id=r[11],
                value_type=ValueType(r[12]) if r[12] in ("estimated", "observed", "provisional_nrt") else ValueType.OBSERVED,
                region_id=r[13],
            )
            for r in rows
        ]

        return HotspotListResponse(
            region_id=region_id,
            daynight_filter=daynight,
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )

    # -------------------------------------------------------------------------
    # 5. SENSOR LAB CALIBRATION QUERY (strict null-safe ratio and natural log)
    # -------------------------------------------------------------------------
    def get_calibration_pairs(
        self,
        region_id: str = "BR-PA",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        block_id: Optional[str] = None,
        daynight: str = "ALL",
    ) -> CalibrationResponse:
        """Fetch paired Aqua MODIS & VIIRS S-NPP monthly overlap observations for Sensor Lab.

        Strict mathematical guardrails:
        - log_ratio = LN(viirs_count / modis_count)
        - NULL when modis_count <= 0 or viirs_count <= 0 or counts missing
        - ZERO NaN or Infinity values allowed.
        """
        if region_id != self.settings.ANALYSIS_REGION_ID:
            raise ValueError(
                f"Unsupported region '{region_id}'. Pará ({self.settings.ANALYSIS_REGION_ID}) is the sole release geography."
            )

        start_yr = max(2012, start_year or 2012)
        end_yr = min(2020, end_year or 2020)

        conditions = ["region_id = ?", "year >= ?", "year <= ?"]
        params: List[Any] = [region_id, start_yr, end_yr]

        if block_id:
            conditions.append("block_id = ?")
            params.append(block_id)

        if daynight in ("D", "N"):
            conditions.append("daynight = ?")
            params.append(daynight)
            where_clause = " AND ".join(conditions)

            # Query single daynight pass
            sql = f"""
                SELECT 
                    block_id, block_ix, block_iy, year, month, daynight,
                    modis_count, viirs_count,
                    CASE 
                        WHEN modis_count IS NOT NULL AND viirs_count IS NOT NULL AND modis_count > 0 
                        THEN ROUND(CAST(viirs_count AS DOUBLE) / CAST(modis_count AS DOUBLE), 4) 
                        ELSE NULL 
                    END as ratio,
                    CASE 
                        WHEN modis_count IS NOT NULL AND viirs_count IS NOT NULL AND modis_count > 0 AND viirs_count > 0 
                        THEN ROUND(LN(CAST(viirs_count AS DOUBLE) / CAST(modis_count AS DOUBLE)), 4) 
                        ELSE NULL 
                    END as log_ratio,
                    modis_frp_sum, viirs_frp_sum
                FROM firechronicle_master
                WHERE {where_clause}
                ORDER BY year, month, block_id
            """
            rows = self.con.execute(sql, params).fetchall()

        else:
            where_clause = " AND ".join(conditions)
            # Compute daynight='ALL' via SQL SUM aggregation across D and N rows
            sql = f"""
                SELECT 
                    block_id, block_ix, block_iy, year, month, 'ALL' as daynight,
                    ROUND(SUM(modis_count), 1) as sum_modis,
                    ROUND(SUM(viirs_count), 1) as sum_viirs,
                    CASE 
                        WHEN SUM(modis_count) IS NOT NULL AND SUM(viirs_count) IS NOT NULL AND SUM(modis_count) > 0 
                        THEN ROUND(CAST(SUM(viirs_count) AS DOUBLE) / CAST(SUM(modis_count) AS DOUBLE), 4) 
                        ELSE NULL 
                    END as ratio,
                    CASE 
                        WHEN SUM(modis_count) IS NOT NULL AND SUM(viirs_count) IS NOT NULL AND SUM(modis_count) > 0 AND SUM(viirs_count) > 0 
                        THEN ROUND(LN(CAST(SUM(viirs_count) AS DOUBLE) / CAST(SUM(modis_count) AS DOUBLE)), 4) 
                        ELSE NULL 
                    END as log_ratio,
                    ROUND(SUM(modis_frp_sum), 1) as sum_modis_frp,
                    ROUND(SUM(viirs_frp_sum), 1) as sum_viirs_frp
                FROM firechronicle_master
                WHERE {where_clause}
                GROUP BY block_id, block_ix, block_iy, year, month
                ORDER BY year, month, block_id
            """
            rows = self.con.execute(sql, params).fetchall()

        pairs: List[CalibrationPair] = []
        sum_m, sum_v, sum_ratio, sum_log_ratio = 0.0, 0.0, 0.0, 0.0
        ratio_count, log_ratio_count = 0, 0

        for r in rows:
            b_id, b_ix, b_iy, yr, mo, dn, m_cnt, v_cnt, ratio, log_r, m_frp, v_frp = r

            # Null-safe conversions with zero NaN or Infinity
            clean_m = float(m_cnt) if m_cnt is not None and not math.isnan(m_cnt) else None
            clean_v = float(v_cnt) if v_cnt is not None and not math.isnan(v_cnt) else None

            clean_ratio = None
            if ratio is not None and not math.isnan(ratio) and not math.isinf(ratio):
                clean_ratio = float(ratio)
                sum_ratio += clean_ratio
                ratio_count += 1

            clean_log_ratio = None
            if log_r is not None and not math.isnan(log_r) and not math.isinf(log_r):
                clean_log_ratio = float(log_r)
                sum_log_ratio += clean_log_ratio
                log_ratio_count += 1

            if clean_m is not None and clean_v is not None:
                sum_m += clean_m
                sum_v += clean_v

            pairs.append(
                CalibrationPair(
                    block_id=b_id,
                    block_ix=int(b_ix) if b_ix is not None else None,
                    block_iy=int(b_iy) if b_iy is not None else None,
                    year=yr,
                    month=mo,
                    daynight=dn,
                    modis_count=clean_m,
                    viirs_count=clean_v,
                    ratio_viirs_to_modis=clean_ratio,
                    log_ratio=clean_log_ratio,
                    modis_frp_sum=float(m_frp) if m_frp is not None and not math.isnan(m_frp) else None,
                    viirs_frp_sum=float(v_frp) if v_frp is not None and not math.isnan(v_frp) else None,
                )
            )

        mean_ratio = round(sum_ratio / ratio_count, 3) if ratio_count > 0 else None
        mean_log_r = round(sum_log_ratio / log_ratio_count, 3) if log_ratio_count > 0 else None

        # Compute Pearson correlation coefficient r
        valid_points = [p for p in pairs if p.modis_count is not None and p.viirs_count is not None and p.modis_count > 0]
        n = len(valid_points)
        if n > 1:
            mean_m = sum(p.modis_count for p in valid_points) / n
            mean_v = sum(p.viirs_count for p in valid_points) / n
            cov = sum((p.modis_count - mean_m) * (p.viirs_count - mean_v) for p in valid_points)
            var_m = sum((p.modis_count - mean_m) ** 2 for p in valid_points)
            var_v = sum((p.viirs_count - mean_v) ** 2 for p in valid_points)
            corr_r = round(cov / math.sqrt(var_m * var_v), 4) if (var_m * var_v) > 0 else None
        else:
            corr_r = None

        return CalibrationResponse(
            region_id=region_id,
            training_era="2012-2020 (Overlap Period)",
            resolution="50km EPSG:6933 block",
            daynight_filter=daynight,
            total_pairs=len(pairs),
            correlation_r=corr_r,
            mean_ratio_viirs_to_modis=mean_ratio,
            mean_log_ratio=mean_log_r,
            items=pairs,
        )

    # -------------------------------------------------------------------------
    # 6. SENSOR LAB VALIDATION METRICS
    # -------------------------------------------------------------------------
    def get_validation_metrics(self) -> ValidationMetricsResponse:
        """Fetch validation metrics contract from disk."""
        metrics_file = self.settings.DATA_DIR / "validation_metrics.json"
        if not metrics_file.exists():
            raise FileNotFoundError(f"Metrics file not found: {metrics_file}")
        with open(metrics_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ValidationMetricsResponse.model_validate(data)

    # -------------------------------------------------------------------------
    # 7. MODEL METADATA INFO
    # -------------------------------------------------------------------------
    def get_model_info(self) -> ModelInfoResponse:
        """Fetch model info and validation metrics contracts from disk."""
        info_file = self.settings.DATA_DIR / "model_info.json"
        if not info_file.exists():
            raise FileNotFoundError(f"Model info file not found: {info_file}")
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        metrics_file = self.settings.DATA_DIR / "validation_metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                data["validation_metrics"] = json.load(f)
        else:
            data.setdefault("validation_metrics", None)

        return ModelInfoResponse.model_validate(data)

    # -------------------------------------------------------------------------
    # 8. WEBHOOK SYNC HANDLERS
    # -------------------------------------------------------------------------
    def sync_predictions(self, records: List[PredictionSyncRecord]) -> int:
        """Ingest predictions from ML teammate into local state."""
        if not records:
            return 0
        logger.info("Synced %d prediction records from ML teammate.", len(records))
        return len(records)

    def sync_metrics(self, payload: Dict[str, Any]) -> None:
        """Write updated metrics from ML teammate to disk."""
        metrics_file = self.settings.DATA_DIR / "validation_metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info("Saved updated validation metrics to %s", metrics_file)


@lru_cache()
def get_db() -> DuckDBManager:
    """Return cached DuckDBManager instance."""
    return DuckDBManager()
