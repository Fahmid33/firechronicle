# FireChronicle — Earth Observation Fire Explorer

**FireChronicle** provides a continuous, multi-decadal record of satellite active fire hotspot detections across **Pará, Brazil (`region_id = "BR-PA"`)** from 2002 through 2020. Developed for the **NASA Space Apps Challenge 2026**.

The application bridges the sensor discontinuity between historical **Aqua MODIS** (2002–2011) and modern **S-NPP VIIRS 375m** (2012–2020) active fire records using an empirically calibrated and independently validated Generalized Linear Model (**Negative Binomial NB2 v1.0**).

---

## Deployment & Demo

- **Target Demo URL**: [https://firechronicle.vercel.app](https://firechronicle.vercel.app) *(deployment-ready; awaiting authorization to publish)*
- **Team Repository**: [inan001/firechronicle](https://github.com/inan001/firechronicle)
- **User Fork**: [Farjad20/firechronicle](https://github.com/Farjad20/firechronicle)
- **Active Branch**: `feature/frontend-demo`

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
| **Static Demo (Default)** | `NEXT_PUBLIC_DATA_MODE=static` | Fast, offline-capable static JSON files in `public/data/` generated directly from authoritative workspace artifacts. Zero backend required. |
| **Live API Mode** | `NEXT_PUBLIC_DATA_MODE=live`<br>`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` | Connects to FastAPI backend (`/api/v1/...`). Network/server errors throw `ApiHttpError` and **never** fall back to synthetic data. |
| **Synthetic Mock Mode** | `NEXT_PUBLIC_DATA_MODE=synthetic` or `NEXT_PUBLIC_USE_MOCKS=true` | Uses synthetic fixtures in `src/mocks/fixtures.ts`. Displays prominent `DEVELOPMENT / SYNTHETIC` watermarks and CSV headers. |

---

## Scientific Rules & Data Integrity

1. **No Sensor Summation**: Aqua MODIS and S-NPP VIIRS counts are separate observational tiers and are **never** summed together.
2. **Missingness vs. Zero**: Missing passes, pre-commissioning months, and unobserved blocks are preserved as `null` / empty strings. A missing observation is **not** evidence of zero fire activity.
3. **Spatial Scale Integrity**: Historical estimates remain at the calibrated 50 km model block resolution. No 10 km precision is fabricated.
4. **Partial Period Accounting**:
   - **Jan–Jun 2002**: Unobserved / unsupported (Aqua MODIS launched July 2002).
   - **July 2002**: First operational month; partially covered.
   - **January 2012**: S-NPP VIIRS launched; data archive began Jan 20 (days 1–19 unobserved; excluded from model calibration).
5. **Observational Caveat**: Visual consistency across seasonal cycles reflects fitted model fixed effects ($\beta_{\text{month}}$), but does not constitute independent proof of true historical fire activity without ground truth.

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
# Run full automated test suite (19 tests)
npm test

# Run focused MapLibre geometry & camera tests (9 tests)
npm run test:map

# Run real static dataset validation (5 tests)
npm run test:data

# Run DataClient adapter tests (3 tests)
npm run test:client

# Run Recharts transformation tests (1 test)
npm run test:charts

# Run CSV export tests (1 test)
npm run test:csv
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
  - Active only when `NEXT_PUBLIC_DATA_MODE=synthetic` or `NEXT_PUBLIC_USE_MOCKS=true`.
  - All synthetic views and exports display explicit `DEVELOPMENT / SYNTHETIC` banners.

---

## Known Behaviors & Demo Interactions to Avoid

- **Global Contextual Basemap**: The dark basemap tiles cover the globe for geographic context, but analytical layers, block selection, and data queries are strictly restricted to Pará (`BR-PA`). Panning outside Pará does not enable data or selection.
- **Jan–Jun 2002**: Attempting to query historical estimates for Jan–Jun 2002 will correctly show “Unsupported Period” because satellite observations began in July 2002.
- **NRT Active Fire Layer**: Real-time NRT layers are provisional and only active when confirmed coverage arrives from a live server.
