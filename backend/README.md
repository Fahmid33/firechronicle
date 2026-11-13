# FIRECHRONICLE — PARÁ, BRAZIL
**NASA Space Apps Challenge 2026: Harmonization of MODIS and VIIRS Hot Spots**
*Backend Architecture Deliverables (Members 3 & 4)*

---

## 🛰️ System Architecture & Data Contract
**FireChronicle Backend** is a production-ready **FastAPI + DuckDB + Parquet** REST API (`/api/v1`) providing harmonized fire hotspot intelligence for **Pará state (`region_id="BR-PA"`), Brazil**.

### 1. Shared Master Dataset Source of Truth
The backend ingests and serves the team's official data contracts directly from `data/`:
* **`firechronicle_master.parquet` (15 Columns):**
  `region_id`, `block_id`, `block_ix`, `block_iy`, `year`, `month`, `daynight`, `modis_count` *(nullable)*, `viirs_count` *(nullable)*, `modis_frp_sum` *(nullable)*, `viirs_frp_sum` *(nullable)*, `coverage_status`, `processing_status`, `modis_source_version`, `viirs_source_version`.
* **`overlap_training.parquet` (10 Columns):**
  `region_id`, `block_id`, `block_ix`, `block_iy`, `year`, `month`, `modis_count`, `viirs_count`, `modis_frp_sum`, `viirs_frp_sum`.
* **`backend_monthly.parquet` (12 Columns):**
  `region_id`, `block_id`, `block_ix`, `block_iy`, `year`, `month`, `daynight`, `modis_count`, `viirs_count`, `modis_frp_sum`, `viirs_frp_sum`, `log_ratio`.
* **`coverage_para.parquet` (12 Columns):**
  `region_id`, `year`, `month`, `period`, `modis_available`, `viirs_available`, `overlap_available`, `value_type`, `coverage_status`, `total_blocks_observed`, `satellite_primary`, `notes`.
* **`para_boundary.geojson`:** Official IBGE Pará boundary polygon.
* **`para_blocks_50km.geojson`:** 50 km equal-area block polygon FeatureCollection for MapLibre.

### 2. DuckDB Engine & Dynamic Views
- **View Registration:** DuckDB mounts all Parquet datasets as high-performance zero-copy views.
- **Derived 12-Column View:** Dynamically computes `backend_monthly` with strict null-safe ratio and natural logarithm:
  $$\text{log\_ratio} = \ln\left(\frac{\text{viirs\_count}}{\text{modis\_count}}\right)$$
  Returns strictly `NULL` when `modis_count <= 0`, `viirs_count <= 0`, or counts are missing, ensuring **zero NaN or Infinity values**.
- **Day/Night Query Support:** Full support for `?daynight=ALL|D|N` on summary, spatial, and sensor-lab endpoints.

---

## 🛡️ Non-Negotiable Scientific Guardrails
1. **Release Geography (Pará, `BR-PA` Only):**
   Active analysis is restricted strictly to Pará (`BR-PA`). All other states (`BR-AM`, `BR-MT`, etc.) are rejected with HTTP 400 and `prediction_status="unsupported_region"`.
2. **Spatial System (EPSG:6933 Equal-Area):**
   - 10 km base cells: $ix = \lfloor x / 10000 \rfloor$, $iy = \lfloor y / 10000 \rfloor$.
   - 50 km calibration blocks: $\text{block\_ix} = \lfloor ix / 5 \rfloor$, $\text{block\_iy} = \lfloor iy / 5 \rfloor$.
   - Prohibits arbitrary downscaling of 50 km model estimates into 10 km cells prior to 2012.
3. **Measurement & Era Rules (NEVER ADD MODIS + VIIRS):**
   - **Mid-2002 to 2011:** Extrapolated VIIRS equivalent counts from Aqua MODIS at 50 km block scale (`value_type="estimated"`).
   - **2012 to finalized archive:** Actual observed VIIRS S-NPP detection counts (`value_type="observed"`).
   - **Recent NRT:** Near-real-time VIIRS detections (`value_type="provisional_nrt"`).
   - MODIS and VIIRS counts are **never added together**.
4. **Strict Null & Zero Integrity:**
   Missing or cloudy detection records remain `null` (never replaced with `0` unless verified clear-sky coverage exists).

---

## 📁 Project Structure
```text
firechronicle-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, CORS (*), lifespan DuckDB loader, exception handlers
│   ├── config.py               # Pydantic settings (.env: ML_MODEL_API_KEY, ML_MODEL_API_URL)
│   ├── schemas.py              # Strict Pydantic v2 schemas preserving NULLs & exact status enums
│   ├── db.py                   # DuckDB connection manager, master table queries, and 12-col / D-N SQL views
│   ├── grid.py                 # EPSG:6933 <-> EPSG:4326 coordinate projection & 50km block GeoJSON generator
│   ├── ml_client.py            # Two-way ML model API bridge & sync runner
│   └── routers/
│       ├── api_v1.py           # All 7 frontend endpoints + blocks GeoJSON
│       └── ml_bridge.py        # ML teammate sync, push, and test endpoints
├── data/
│   ├── firechronicle_master.parquet # 15-column master source of truth
│   ├── overlap_training.parquet     # 10-column ML training/overlap table
│   ├── backend_monthly.parquet      # 12-column combined monthly table
│   ├── coverage_para.parquet        # Coverage & availability companion
│   ├── para_boundary.geojson        # Official IBGE Pará boundary polygon
│   ├── para_blocks_50km.geojson     # Generated 50km block polygons FeatureCollection for MapLibre
│   ├── model_info.json
│   └── validation_metrics.json
├── scripts/
│   ├── generate_fixtures.py    # Generates valid fixtures matching the exact 15-col master spec
│   ├── predict.py              # Standalone local empirical calibration regression fallback
│   └── run_smoke_test.py       # Automated smoke test suite
└── tests/
    └── test_api_v1.py          # Pytest suite (23 unit, contract, and guardrail tests)
```

---

## 📡 API Endpoints Reference

### Frontend Endpoints (`/api/v1`)
| Endpoint | Method | Parameters | Description |
|---|---|---|---|
| `/api/v1/summary` | `GET` | `region_id`, `start_year`, `end_year`, `daynight=ALL\|D\|N` | Harmonized monthly fire timeline (2002–present) strictly preserving era tags. |
| `/api/v1/spatial` | `GET` | `region_id`, `year`, `month`, `resolution`, `daynight=ALL\|D\|N` | GeoJSON FeatureCollection with projected polygon geometries for MapLibre. |
| `/api/v1/blocks` | `GET` | `region_id=BR-PA` | 50 km block polygons GeoJSON FeatureCollection for MapLibre grid layers. |
| `/api/v1/hotspots` | `GET` | `region_id`, `start_date`, `end_date`, `satellite`, `instrument`, `daynight=D\|N`, `limit`, `offset` | Filterable, paginated point fire detections with sensor provenance. |
| `/api/v1/sensor-lab/calibration` | `GET` | `region_id`, `start_year`, `end_year`, `block_id`, `daynight=ALL\|D\|N` | 2012–2020 paired MODIS & VIIRS observations with null-safe ratio and `log_ratio`. |
| `/api/v1/sensor-lab/metrics` | `GET` | — | Cross-validation metrics ($R^2=0.942$, MAE, RMSE, Biome breakdown). |
| `/api/v1/model/info` | `GET` | — | Model architecture, training era, input features, and scientific guardrails. |
| `/api/v1/predict` | `POST` | `region_id`, `year`, `month`, `daynight`, `blocks` | Inference endpoint querying remote ML model or local empirical fallback. |
| `/api/v1/boundary` | `GET` | — | Official IBGE Pará polygon boundary for map initialization and masking. |
| `/api/v1/health` | `GET` | — | Health check and active release geography status. |

### Data Scientist ML Bridge (`/ml-bridge`)
| Endpoint | Method | Authentication | Purpose |
|---|---|---|---|
| `/ml-bridge/status` | `GET` | None | Probes remote ML service availability and local fallback readiness. |
| `/ml-bridge/predict` | `POST` | None | Direct prediction test through the ML bridge. |
| `/ml-bridge/sync-predictions` | `POST` | `X-API-Key` or `Bearer` token | Webhook to receive batch predictions from the ML teammate into DuckDB. |
| `/ml-bridge/sync-metrics` | `POST` | `X-API-Key` or `Bearer` token | Webhook to update validation metrics from the ML teammate. |

---

## 🧪 Testing & Verification

Run the full pytest suite (23 tests):
```bash
pytest -v tests/test_api_v1.py
```

Run the smoke test script:
```bash
python scripts/run_smoke_test.py
```
