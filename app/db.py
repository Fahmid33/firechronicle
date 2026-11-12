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

    def _resolve_glob_expr(self, glob_pattern: str, fallback_file: Optional[str] = None) -> Optional[str]:
        """Resolve a DuckDB glob expression across multi-year parquet files without preferring a single year."""
        data_dir = self.settings.DATA_DIR
        matched = sorted(data_dir.glob(glob_pattern))
        if matched:
            return f"{data_dir.as_posix()}/{glob_pattern}"
        if fallback_file:
            fb_path = data_dir / fallback_file
            if fb_path.exists():
                return fb_path.as_posix()
        return None

    def _load_audit_period_notes(self) -> Dict[str, str]:
        """Extract Data Engineer source date/completeness limitations from audit_*.json files."""
        notes_by_period: Dict[str, str] = {}
        data_dir = self.settings.DATA_DIR
        for audit_file in sorted(data_dir.glob("audit_*.json")):
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    audit = json.load(f)
                yr = audit.get("year")
                viirs_src = (audit.get("source") or {}).get("viirs_snpp") or {}
                d_min = viirs_src.get("source_date_min")
                if yr == 2012 and d_min and d_min > "2012-01-01":
                    notes_by_period["2012-01"] = (
                        f"Partial January 2012 availability: VIIRS S-NPP archive begins {d_min} "
                        f"({audit_file.name})."
                    )
            except Exception as e:
                logger.warning("Could not parse audit metadata %s: %s", audit_file, e)
        return notes_by_period

    def _init_views(self) -> None:
        """Register DuckDB views using multi-year glob patterns and canonical dense-grid joins."""
        data_dir = self.settings.DATA_DIR

        # 0. Canonical 50km grid and geometry (required for sparse-to-dense relational join)
        for view_name, fname in (
            ("para_grid_canonical", "para_50km_grid_canonical.parquet"),
            ("para_grid_geometry", "para_50km_grid_geometry.parquet"),
        ):
            fpath = data_dir / fname
            if fpath.exists():
                clean_path = fpath.as_posix()
                self.con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{clean_path}'")
                logger.info("Registered DuckDB view '%s' -> %s", view_name, clean_path)
            else:
                logger.warning("Parquet file for view '%s' not found in %s", view_name, data_dir)

        has_canonical = (data_dir / "para_50km_grid_canonical.parquet").exists()

        # 1. Multi-year firechronicle_master via DuckDB glob + canonical grid LEFT JOIN sparse master
        master_expr = self._resolve_glob_expr("firechronicle_master_*.parquet", "firechronicle_master.parquet")
        if master_expr:
            self.con.execute(
                f"CREATE OR REPLACE VIEW firechronicle_master_sparse AS SELECT * FROM '{master_expr}'"
            )
            logger.info("Registered DuckDB sparse master view -> %s", master_expr)

            if has_canonical:
                self.con.execute("""
                    CREATE OR REPLACE VIEW full_dense_panel AS
                    SELECT
                        c.region_id,
                        c.block_id,
                        c.block_ix,
                        c.block_iy,
                        y.year,
                        m.month,
                        dn.daynight
                    FROM para_grid_canonical c
                    CROSS JOIN (SELECT DISTINCT year FROM firechronicle_master_sparse) y
                    CROSS JOIN (SELECT UNNEST(GENERATE_SERIES(1, 12)) AS month) m
                    CROSS JOIN (SELECT UNNEST(['D', 'N']) AS daynight) dn
                """)
                self.con.execute("""
                    CREATE OR REPLACE VIEW firechronicle_master AS
                    SELECT
                        f.region_id,
                        f.block_id,
                        f.block_ix,
                        f.block_iy,
                        f.year,
                        f.month,
                        f.daynight,
                        s.modis_count,
                        s.viirs_count,
                        s.modis_frp_sum,
                        s.viirs_frp_sum,
                        COALESCE(s.coverage_status, 'unknown') AS coverage_status,
                        s.processing_status,
                        s.modis_source_version,
                        s.viirs_source_version
                    FROM full_dense_panel f
                    LEFT JOIN (
                        SELECT
                            region_id,
                            block_id,
                            block_ix,
                            block_iy,
                            year,
                            month,
                            daynight,
                            modis_count,
                            viirs_count,
                            modis_frp_sum,
                            viirs_frp_sum,
                            coverage_status,
                            processing_status,
                            modis_source_version,
                            viirs_source_version
                        FROM firechronicle_master_sparse
                        QUALIFY ROW_NUMBER() OVER (
                            PARTITION BY region_id, block_id, year, month, daynight
                            ORDER BY modis_source_version NULLS LAST, viirs_source_version NULLS LAST
                        ) = 1
                    ) s
                      ON f.region_id = s.region_id
                     AND f.block_id = s.block_id
                     AND f.year = s.year
                     AND f.month = s.month
                     AND f.daynight = s.daynight
                """)
                logger.info(
                    "Registered canonical dense relational view 'firechronicle_master' (canonical grid LEFT JOIN master sparse)."
                )
            else:
                self.con.execute("CREATE OR REPLACE VIEW firechronicle_master AS SELECT * FROM firechronicle_master_sparse")

            self.con.execute("CREATE OR REPLACE VIEW master_block_month AS SELECT * FROM firechronicle_master")
            logger.info("Registered alias view 'master_block_month' -> firechronicle_master")
        else:
            logger.warning("No firechronicle_master parquet files found in %s", data_dir)

        # 2. Multi-year overlap_training, full panel, and estimated_viirs_block_month
        multi_views = {
            "overlap_training": ("overlap_training_[0-9][0-9][0-9][0-9].parquet", "overlap_training.parquet"),
            "overlap_training_full_panel": ("overlap_training_full_panel_*.parquet", None),
        }
        for view_name, (glob_pat, fb) in multi_views.items():
            expr = self._resolve_glob_expr(glob_pat, fb)
            if expr:
                self.con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{expr}'")
                logger.info("Registered DuckDB view '%s' -> %s", view_name, expr)

        est_path = data_dir / "estimated_viirs_block_month.parquet"
        if est_path.exists():
            clean_est = est_path.as_posix()
            est_cols = {
                r[0] for r in self.con.execute(f"DESCRIBE SELECT * FROM '{clean_est}'").fetchall()
            }
            if "estimated_viirs_count" in est_cols and "estimated_count" not in est_cols:
                self.con.execute(
                    f"CREATE OR REPLACE VIEW estimated_viirs_block_month AS "
                    f"SELECT *, CAST(estimated_viirs_count AS DOUBLE) AS estimated_count FROM '{clean_est}'"
                )
            elif "estimated_count" in est_cols and "estimated_viirs_count" not in est_cols:
                self.con.execute(
                    f"CREATE OR REPLACE VIEW estimated_viirs_block_month AS "
                    f"SELECT *, CAST(estimated_count AS DOUBLE) AS estimated_viirs_count FROM '{clean_est}'"
                )
            else:
                self.con.execute(f"CREATE OR REPLACE VIEW estimated_viirs_block_month AS SELECT * FROM '{clean_est}'")
            logger.info("Registered DuckDB view 'estimated_viirs_block_month' -> %s", clean_est)

        # 3. backend_monthly (plus alias overlap_calibration) using multi-year glob
        bm_expr = self._resolve_glob_expr("backend_monthly_*.parquet", "backend_monthly.parquet")
        if bm_expr:
            self.con.execute(f"CREATE OR REPLACE VIEW backend_monthly AS SELECT * FROM '{bm_expr}'")
            self.con.execute("CREATE OR REPLACE VIEW overlap_calibration AS SELECT * FROM backend_monthly")
            logger.info("Registered DuckDB view 'backend_monthly' (and alias 'overlap_calibration') -> %s", bm_expr)
        elif master_expr:
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

        # 4. Dynamic hotspots_para view adapter across multi-year sensor globs or fallback
        raw_hotspot_globs = [
            "para_aqua_modis_*.parquet",
            "para_viirs_snpp_*.parquet",
        ]
        raw_selects = []
        for raw_pat in raw_hotspot_globs:
            expr = self._resolve_glob_expr(raw_pat)
            if expr:
                raw_selects.append(
                    f"SELECT sensor_id, region_id, latitude, longitude, acq_date, acq_time, "
                    f"daynight, satellite, instrument, CAST(confidence AS VARCHAR) AS confidence, "
                    f"frp, grid_id, block_id FROM read_parquet('{expr}')"
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
            logger.info("Registered unified DuckDB view 'hotspots_para' from sensor glob files.")
        else:
            fallback_hotspots = data_dir / "hotspots_para.parquet"
            if fallback_hotspots.exists():
                clean_hs = fallback_hotspots.as_posix()
                self.con.execute(f"CREATE OR REPLACE VIEW hotspots_para AS SELECT * FROM '{clean_hs}'")
                logger.info("Registered DuckDB view 'hotspots_para' -> %s", clean_hs)

        # 5. Smart coverage_para view adapter using multi-year coverage_para_*.parquet glob (never coercing 'verified')
        cov_expr = self._resolve_glob_expr("coverage_para_*.parquet", "coverage_para.parquet")
        if cov_expr:
            cols_info = self.con.execute(f"DESCRIBE SELECT * FROM '{cov_expr}'").fetchall()
            col_names = {r[0] for r in cols_info}
            if {"sensor", "source_product", "observation_evidence"}.issubset(col_names):
                self.con.execute(f"CREATE OR REPLACE VIEW coverage_para_raw AS SELECT * FROM '{cov_expr}'")
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
                        COALESCE(
                            MAX(CASE WHEN LOWER(coverage_status) != 'verified' THEN coverage_status END),
                            FIRST(coverage_status)
                        ) AS coverage_status,
                        CAST(COUNT(DISTINCT block_id) AS INTEGER) AS total_blocks_observed,
                        'SNPP_VIIRS' AS satellite_primary,
                        FIRST(notes) AS notes
                    FROM coverage_para_raw
                    GROUP BY region_id, year, month
                    ORDER BY year, month
                """)
                logger.info("Registered multi-year aggregated DuckDB view 'coverage_para' from %s.", cov_expr)
            else:
                self.con.execute(f"CREATE OR REPLACE VIEW coverage_para AS SELECT * FROM '{cov_expr}'")
                logger.info("Registered DuckDB view 'coverage_para' -> %s", cov_expr)
        else:
            logger.warning("Parquet file 'coverage_para' not found in %s", data_dir)

        # 6. Canonical 568-block GeoJSON generation if canonical grid files exist
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

        # Step 2: Observed Era (2012+) - actual observed VIIRS S-NPP counts + direct coverage_status passthrough
        sql_obs = f"""
            SELECT 
                year,
                month,
                ROUND(SUM(viirs_count), 1) as total_count,
                ROUND(SUM(viirs_frp_sum), 1) as total_frp,
                CASE 
                    WHEN year = 2026 AND month >= 7 THEN 'provisional_nrt'
                    ELSE 'observed'
                END as val_type,
                MAX(coverage_status) as master_cov_status
            FROM firechronicle_master
            WHERE region_id = ? AND year >= 2012 AND year >= ? AND year <= ? {dn_cond}
            GROUP BY year, month
            ORDER BY year, month
        """
        obs_rows = self.con.execute(sql_obs, [region_id, start_yr, end_yr] + params_dn).fetchall()

        # Step 3: Coverage calendar & Data Engineer limitations passthrough
        sql_cov = """
            SELECT year, month, period, value_type, coverage_status, notes
            FROM coverage_para
            WHERE region_id = ? AND year >= ? AND year <= ?
            ORDER BY year, month
        """
        cov_rows = self.con.execute(sql_cov, [region_id, start_yr, end_yr]).fetchall()
        coverage_map = {f"{r[0]}-{r[1]:02d}": (r[3], r[4], r[5]) for r in cov_rows}
        audit_notes = self._load_audit_period_notes()

        combined_data: Dict[str, Dict[str, Any]] = {}

        def _norm_cov(val: Optional[str]) -> Optional[Union[CoverageStatus, str]]:
            if val is None:
                return None
            return CoverageStatus(val) if val in CoverageStatus._value2member_map_ else val

        def _merge_cov_note(period_str: str, base_note: Optional[str]) -> Optional[str]:
            parts = []
            if period_str in audit_notes:
                parts.append(audit_notes[period_str])
            if base_note:
                parts.append(base_note)
            return " | ".join(parts) if parts else None

        # Add estimated points (mid-2002 to 2011)
        for row in est_rows:
            yr, mo, cnt, frp, p_stat, c_stat, m_ver, m_unit, cal_km = row
            per = f"{yr}-{mo:02d}"
            _, cov_cal_status, cov_note = coverage_map.get(per, ("estimated", None, None))
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
                "coverage_notes": _merge_cov_note(per, cov_note),
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
            yr, mo, cnt, frp, vtype_str, master_cov_status = row
            per = f"{yr}-{mo:02d}"
            _, cov_status, cov_note = coverage_map.get(per, (vtype_str, None, None))
            eff_cov = cov_status if cov_status is not None else master_cov_status
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
                "coverage_status": _norm_cov(eff_cov),
                "coverage_notes": _merge_cov_note(per, cov_note),
                "model_version": None,
                "measurement_unit": "VIIRS_S-NPP_detection_count",
                "calibration_scale_km": 50,
                "frp_total_mw": float(frp) if frp is not None else None,
                "is_harmonized_estimate": False,
                "is_synthetic_demo": False,
                "data_source_tier": "provisional_nrt_observations" if vtype_enum == ValueType.PROVISIONAL_NRT else "observed_firms_archive",
            }

        # Fill any missing coverage periods strictly preserving nulls
        for r in cov_rows:
            yr, mo, per, vtype_str, cov_status, cov_note = r
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
                    "coverage_notes": _merge_cov_note(per, cov_note),
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
        coverage_notes: Optional[str] = None,
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
            coverage_notes=coverage_notes,
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
            # 2012+ observed data from canonical dense firechronicle_master (strict NULL + coverage_status passthrough)
            is_nrt = (year == 2026 and month >= 7)
            vtype_enum = ValueType.PROVISIONAL_NRT if is_nrt else ValueType.OBSERVED
            lbl = "Provisional NRT" if vtype_enum == ValueType.PROVISIONAL_NRT else "Observed S-NPP"
            audit_notes = self._load_audit_period_notes()
            cov_note_row = self.con.execute(
                "SELECT notes FROM coverage_para WHERE region_id = ? AND year = ? AND month = ? LIMIT 1",
                [region_id, year, month],
            ).fetchone()
            note_parts = []
            if period_str in audit_notes:
                note_parts.append(audit_notes[period_str])
            if cov_note_row and cov_note_row[0]:
                note_parts.append(cov_note_row[0])
            period_cov_note = " | ".join(note_parts) if note_parts else None

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
                ORDER BY block_id
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
                        coverage_notes=period_cov_note,
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
            conditions.append("(modis_count IS NOT NULL OR viirs_count IS NOT NULL)")
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
                    modis_frp_sum, viirs_frp_sum,
                    coverage_status
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
                    ROUND(SUM(viirs_frp_sum), 1) as sum_viirs_frp,
                    MAX(coverage_status) as coverage_status
                FROM firechronicle_master
                WHERE {where_clause}
                GROUP BY block_id, block_ix, block_iy, year, month
                HAVING SUM(modis_count) IS NOT NULL OR SUM(viirs_count) IS NOT NULL
                ORDER BY year, month, block_id
            """
            rows = self.con.execute(sql, params).fetchall()

        pairs: List[CalibrationPair] = []
        sum_m, sum_v, sum_ratio, sum_log_ratio = 0.0, 0.0, 0.0, 0.0
        ratio_count, log_ratio_count = 0, 0

        for r in rows:
            b_id, b_ix, b_iy, yr, mo, dn, m_cnt, v_cnt, ratio, log_r, m_frp, v_frp, cov_stat = r

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
                    coverage_status=(
                        CoverageStatus(cov_stat)
                        if cov_stat in CoverageStatus._value2member_map_
                        else cov_stat
                    ),
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
        """Validate/acknowledge prediction records from ML teammate (demo acknowledgement only).

        NOTE: Real durable storage and read-back verification are pending the delivery
        of the validated Data Science model interface.
        """
        if not records:
            return 0
        logger.info(
            "Demo acknowledgement only: received %d prediction records (durable storage pending validated DS model interface).",
            len(records),
        )
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
