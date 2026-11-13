# FireChronicle — Earth Observation Fire Explorer

[![Live Demo](https://img.shields.io/badge/Live_Demo-firechronicle.vercel.app-10b981?style=for-the-badge&logo=vercel&logoColor=white)](https://firechronicle.vercel.app/)
[![GitHub Repository](https://img.shields.io/badge/GitHub-inan001%2Ffirechronicle-blue?style=for-the-badge&logo=github)](https://github.com/inan001/firechronicle)
[![Production Branch](https://img.shields.io/badge/Production_Branch-main-green?style=for-the-badge&logo=git)](https://github.com/inan001/firechronicle/tree/main)
[![Test Suite](https://img.shields.io/badge/Tests-37%20Passing-success?style=for-the-badge)](https://github.com/inan001/firechronicle)

**FireChronicle** provides a continuous, multi-decadal record of satellite active fire hotspot detections across **Pará, Brazil (`region_id = "BR-PA"`)** from 2002 through 2020. Developed for the **NASA Space Apps Challenge 2026**.

The application bridges the sensor discontinuity between historical **Aqua MODIS** (2002–2011) and modern **S-NPP VIIRS 375m** (2012–2020) active fire records using an empirically calibrated Generalized Linear Model (**Negative Binomial NB2 v1.0**), evaluated using held-out temporal and geographic validation.

> 🚀 **Public Live Application**: [https://firechronicle.vercel.app/](https://firechronicle.vercel.app/)  
> Deployed from production branch `main` on Vercel with zero-backend static data architecture.

---

## Deployment & Repository Status

- **Public Live Application**: [https://firechronicle.vercel.app/](https://firechronicle.vercel.app/) *(Confirmed public production deployment)*
- **Official Team Repository**: [inan001/firechronicle](https://github.com/inan001/firechronicle)
- **Production Branch**: `main` *(Authoritative release branch)*
- **Development Fork**: [Farjad20/firechronicle](https://github.com/Farjad20/firechronicle)
- **Deployment Platform**: Next.js 16.4.6 (Turbopack) on Vercel (`NEXT_PUBLIC_DATA_MODE=static`)

---

## Key Architecture & Features

1. **Interactive Geospatial Map (MapLibre GL JS v6)**:
   - Official **IBGE 2024** Pará state boundary (EPSG:4674 transformed to EPSG:4326).
   - **568 canonical 50 km blocks** (WGS 84 / NSIDC EASE-Grid 2.0 Global, EPSG:6933, Lambert Cylindrical Equal Area inverted to EPSG:4326 GeoJSON).
   - **Quantitative block-level choropleth**: dynamically colored by month-specific detection counts (Amber ramp for 2002–2011 estimated era, Emerald ramp for 2012–2020 observed era).
   - Interactive hover cards and click selection across all 568 blocks.
   - Missing/unobserved passes preserved as neutral uncolored cells (never zero).
2. **Multi-Decadal Calendar Heatmap (2002–2020)**:
   - 19 years × 12 months matrix (228 cells).
   - Pre-commissioning period (Jan–Jun 2002) styled as unsupported (preserved NULL).
   - January 2012 badged as partial observation (S-NPP archive began Jan 20; days 1–19 unobserved).
   - Interactive synchronization to period selection controls.
   - Toggle between Statewide Pará and Selected 50 km Block.
3. **Recharts Visual Analytics Suite**:
   - **Monthly Multi-Decadal Timeline**: 2002–2020 continuous time series with preserved gaps, 2012 transition line, and optional raw Aqua MODIS context line.
   - **12-Month Seasonal Climatology**: Historical era (2003–2011) vs. modern era (2012–2020) monthly averages illustrating the Amazonian dry-season burning peak (August–November).
   - **Annual Totals Chart**: 19-year burning season sums highlighting historical severe drought years (2004, 2005, 2007, 2010).
4. **Sensor Lab (`/sensor-lab`)**:
   - Authoritative, split-specific validation benchmark comparing the baseline Ratio-of-Totals model against production NB2 v1.0.
   - Model specification: Generalized Linear Model with negative binomial log-link incorporating $\log(1 + \text{MODIS count})$ (`log1p_modis`), categorical calendar month fixed effects (`month_2` through `month_12`, reference month January), and an overpass day/night indicator (`daynight_N`). Does not include block-specific spatial fixed effects, ensuring uniform spatial calibration across Pará.
   - Temporal holdout (2019–2020, N=5,091): NB2 MAE 35.44 (vs 44.99 baseline), Poisson deviance 25.01 (vs 55.31 baseline, 54.8% reduction), WAPE 16.79% (vs 20.48%).
   - Geographic holdout (94 blocks, N=5,147): NB2 MAE 35.79 (vs 53.87 baseline), Poisson deviance 20.95 (vs 56.35 baseline, 62.8% reduction), WAPE 34.15% (vs 51.39%).
   - Full statistical provenance: NB2 dispersion $\alpha = 0.3394$, multiplier $k = 6.0538$, N=23,010 paired-positive training records.
5. **Full RFC 4180 CSV Export**:
   - One-click export for Statewide Pará or any selected 50 km block.
   - Columns: `region_id,block_id,year,month,daynight,value,value_type,status,measurement_unit,model_version`.
   - Exact 228 monthly rows with preserved NULLs and Day/Night labeling (`daynight="ALL"`).

---

## Operating Modes

The frontend uses a pluggable, typed `DataClient` architecture resolved via environment variables:

| Mode | Environment Config | Description |
| --- | --- | --- |
| **Static Demo (Default)** | `NEXT_PUBLIC_DATA_MODE=static` | Fast, zero-backend static mode serving bundled JSON files in `public/data/` generated directly from authoritative workspace artifacts. Zero backend server required. *(Note: MapLibre basemap tiles stream from OpenFreeMap and require network access; see Known Limitations).* |
| **Live API Mode** | `NEXT_PUBLIC_DATA_MODE=live`<br>`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` | Connects to FastAPI backend (`/api/v1/...`). Network/server errors throw `ApiHttpError` and **never** fall back to synthetic data. |
| **Synthetic Mock Mode** | `NEXT_PUBLIC_DATA_MODE=mock` or `NEXT_PUBLIC_USE_MOCKS=true` | Uses synthetic fixtures in `src/mocks/fixtures.ts`. Displays prominent `DEVELOPMENT / SYNTHETIC` watermarks and CSV headers. |

> [!NOTE]
> **Demo Default & Live Mode Integration Status**: `NEXT_PUBLIC_DATA_MODE=static` is the default demonstration mode. Live mode is not fully integrated for block time series because the backend does not yet expose the full multi-year block-summary contract (228 periods × 568 blocks = ~130,000 values) required by the frontend for 50 km block drilldown. Live mode supports statewide monthly time series (`/api/v1/harmonized` + `/api/v1/summary`), calendar matrices, period-specific spatial slices (`/api/v1/spatial?year=YYYY&month=MM&resolution=50km&region_id=BR-PA&daynight=ALL`), block catalogs (`/api/v1/blocks`), and model evaluation metrics (`/api/v1/model-info` + `/api/v1/sensor-lab/metrics`).

---

## Scientific Rules & Data Integrity

1. **No Sensor Summation**: Aqua MODIS and S-NPP VIIRS counts are separate observational tiers and are **never** summed together.
2. **Missingness vs. Zero**: Missing passes, pre-commissioning months, and unobserved blocks are preserved as `null` / empty strings. A missing observation is **not** evidence of zero fire activity.
3. **Spatial Scale Integrity**: Historical estimates remain at the calibrated 50 km model block resolution. No 10 km precision is fabricated.
4. **Partial Period Accounting**:
   - **Jan–Jun 2002**: Unobserved / unsupported. NASA's Aqua satellite was launched on **May 4, 2002**; following on-orbit instrument checkout and calibration, the operational active fire science archive begins in **July 2002** (which is also a partial month). Pre-July 2002 periods have no operational active fire data and are strictly preserved as unsupported (`null`).
   - **July 2002**: First operational month in the archive; partially covered and badged accordingly in the time series and calendar.
   - **January 2012**: S-NPP VIIRS launched October 28, 2011; active fire data archive began January 20, 2012 (days 1–19 unobserved; badged as partial observation and excluded from model calibration).
5. **Observational & Model Caveats**: Visual consistency across seasonal cycles reflects fitted month fixed effects ($\beta_{\text{month}}$). Model predictions represent conditional statistical expectations ($\mathbb{E}[Y \mid X]$), not independent physical proof of on-the-ground fire perimeters or burned area.
6. **Strict Day/Night Aggregation (`daynight=ALL`) & Zero Interpretation**: At the 50 km block level, a combined D+N count is valid if and only if both passes exist; if either is NULL, the block ALL value is preserved as NULL. Statewide totals sum exclusively complete D+N pairs (available single passes are excluded from the main sum to prevent diurnal sampling bias). **Critical Scientific Caveat**: Historical statewide sums of zero resulting from the absence of complete D+N pairs in a given month do **not** establish zero physical fire activity on the ground. Unobserved fires or single-pass detections may have been present, but incomplete pairs are withheld from the strict aggregate to preserve diurnal consistency across decades.

---

## Known Limitations & Methodological Constraints

1. **Spatial Scale Constraint**: All historical inferences are produced strictly at the 50 km canonical grid cell level (WGS 84 / NSIDC EASE-Grid 2.0 Global, EPSG:6933, 568 blocks across Pará). Sub-block downscaling (e.g., 10 km or 1 km) is not supported or claimed.
2. **Diurnal Pass Incompleteness**: Aqua MODIS provides nominal 01:30 and 13:30 local overpasses. Incomplete passes (where only Day or Night is recorded) cannot form a valid `daynight=ALL` observation and are preserved as NULL at the block level and omitted from strict statewide sums.
3. **Sensor Coverage & Cloud/Smoke Sensitivity**: Spaceborne passive optical and thermal infrared sensors rely on clear-sky radiative transmission. Heavy cloud cover, dense atmospheric aerosols, or thick smoke can obscure or attenuate thermal radiation from the surface, leading to potential omission or undercounting of hotspots by satellites. These are physical sensing constraints inherent to satellite active fire radiometry.
4. **Statistical Expectation vs. Physical Ground Truth**: Model predictions represent conditional statistical expectations of VIIRS 375m-equivalent hotspot counts ($\mathbb{E}[Y \mid X]$), conditional on Aqua MODIS detection. They do not represent direct field-verified censuses of physical fire perimeters, flame fronts, or burned area (hectares).
5. **Historical Extrapolation & Calibration Domain Shift**: The model was calibrated on 2012–2020 paired-positive observations ($N = 23,010$ records, maximum observed MODIS count $M = 504$). The historical era (2002–2011) encompassed severe Amazonian drought years (notably 2004, 2005, 2007, and 2010) characterized by substantially higher regional fire activity and elevated fire radiative power, including 35 block-month observations where MODIS counts exceeded the calibration maximum ($M > 504$, reaching up to $M = 1,001$). While the log-linear formulation maintains parametric monotonicity across high counts, predictions for counts exceeding the calibration range represent statistical extrapolation beyond the observed empirical training support.
6. **Live API Multi-Year Block Drilldown**: Live API mode currently supports statewide series, calendar matrices, period spatial slices, and model metrics. Interactive multi-year block drilldown (129,504 block-month values) is currently powered by verified static JSON in `public/data/`.
7. **Basemap Network Connectivity**: While scientific data payloads are bundled and served locally with zero backend dependencies, the interactive MapLibre map canvas requires network access to load OpenFreeMap vector basemap tiles (`tiles.openfreemap.org`).

---

## Getting Started

### Prerequisites
- Node.js 20+ (tested on Node v24.22.1 / npm 12.2.2)

### Installation
```bash
npm ci
```

### Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### Running Verification Tests
```bash
# Run full automated test suite (37 tests across 8 test suites)
npm test

# Run focused MapLibre geometry & camera tests (9 tests)
npm run test:map

# Run real static dataset validation (5 tests)
npm run test:data

# Run DataClient adapter & schema validation tests (8 tests)
npm run test:client

# Run Recharts transformation tests (1 test)
npm run test:charts

# Run CSV export tests (1 test)
npm run test:csv

# Run frontend asset & static data smoke tests (1 test)
npm run test:smoke

# Run backend daynight=ALL contract & geometry tests (7 tests)
npm run test:contract

# Run UI methodology, status label & coverage tests (5 tests)
npm run test:content
```

### Linting & Production Build
```bash
# ESLint check (0 errors, 0 warnings)
npm run lint

# Next.js production build & static prerendering
npm run build
```

---

## Summary of Elements: Real vs. Synthetic

- **Real Elements**:
  - Pará boundary GeoJSON (official IBGE 2024 `PA_UF_2024.zip`, 35 MultiPolygon parts, 6,559 vertices).
  - 50 km grid block GeoJSON (568 canonical blocks from `para_50km_grid_geometry.parquet`, inverse EPSG:6933 Lambert Cylindrical Equal Area).
  - Statewide monthly time series (2002–2020, 228 months, exact historical NB2 predictions and observed VIIRS counts).
  - Block-level monthly values (568 blocks × 228 periods = 129,504 block-month values).
  - Validation metrics (Strategy A temporal holdout and Strategy B geographic holdout directly from `validation_metrics_final_nb2.json`).
- **Synthetic Elements**:
  - Active only when `NEXT_PUBLIC_DATA_MODE=mock` or `NEXT_PUBLIC_USE_MOCKS=true`.
  - All synthetic views and exports display explicit `DEVELOPMENT / SYNTHETIC` banners.

---

## Known Behaviors & Demo Interactions to Avoid

- **Global Contextual Basemap**: The dark basemap tiles cover the globe for geographic context, but analytical layers, block selection, and data queries are strictly restricted to Pará (`BR-PA`). Panning outside Pará does not enable data or selection.
- **Jan–Jun 2002**: Attempting to query historical estimates for Jan–Jun 2002 will correctly show “Unsupported Period” because operational satellite science observations began in July 2002.
- **NRT Active Fire Layer**: Real-time NRT layers are provisional and only active when confirmed coverage arrives from a live server.

---

## Team & Contributions

Developed for the **NASA Space Apps Challenge 2026**.

| Contributor | Verified Repository Roles & Contributions | Key Pull Requests |
| :--- | :--- | :--- |
| **Inan Dilir Hamim**<br>([@inan001](https://github.com/inan001)) | **Project Lead & Repository Owner**<br>• Repository maintenance, architectural leadership, and code review.<br>• Production Vercel deployment orchestration and releases. | Merged PRs #1, #2, #3, #4, #5 |
| **Farjad**<br>([@Farjad20](https://github.com/Farjad20)) | **Data Science, Geospatial Frontend & Data Integration Engineer**<br>• **Data Science**: Formulated, trained, and validated the authoritative **NB2 v1.0** Generalized Linear Model ($k=6.0538$, $\alpha=0.3394$); engineered historical reconstruction pipeline for 2002–2011 Aqua MODIS; conducted split-sample temporal (Holdout A) and geographic (Holdout B) validation evaluations.<br>• **Frontend Architecture**: Implemented full Next.js 16 frontend, pluggable typed `DataClient` architecture, static data generation pipeline (`public/data/`), MapLibre GL JS choropleth integration with official IBGE 2024 boundary and 568 canonical blocks, multi-decadal calendar heatmap, Recharts time-series suite, Sensor Lab (`/sensor-lab`), strict `daynight=ALL` contract reconciliation, and RFC 4180 CSV export. | [PR #1 (Data Science)](https://github.com/inan001/firechronicle/pull/1)<br>[PR #2 (Frontend & Data Integration)](https://github.com/inan001/firechronicle/pull/2) |
| **Sufian Nabil**<br>([@fairjordan04](https://github.com/fairjordan04)) | **Backend Engineer** *(Documented PR Contributor)*<br>• FastAPI application structure, DuckDB analytical engine integration, spatial REST endpoints, and NB2 backend model service. | [PR #4 (Backend Integration)](https://github.com/inan001/firechronicle/pull/4) |
| **Syed Fahmid Arefeen**<br>([@Fahmid33](https://github.com/Fahmid33)) | **Data Engineer** *(Documented PR Contributor)*<br>• MODIS and VIIRS historical data generation notebooks, Google Colab workflows, and data engineering pipelines. | [PR #3 (Data Engineering)](https://github.com/inan001/firechronicle/pull/3)<br>[PR #5 (Colab Documentation)](https://github.com/inan001/firechronicle/pull/5) |

> [!NOTE]
> Detailed responsibilities above are derived from verified Git commit history and merged Pull Requests. Team members should confirm preferred public names, titles, and affiliations before final competition submission.

---

## License

Not yet specified. Licensing decisions remain with the project team.
