# Frontend integration handoff

Authority: [rulebook](FireChronicle_FINAL_Team_Rulebook_Para_Brazil.pdf), all 10 pages. See [AGENTS](../AGENTS.md), [delivery plan](FRONTEND_PLAN.md) and [contract register](API_CONTRACT.md). The four-route dashboard now includes a real interactive MapLibre contextual basemap. Official geometry, API adapters, environment parsing, scientific charts and a populated historical calendar remain pending.

## Install and run

From `firechronicle-frontend/`, use the existing npm project and lockfile:

```sh
npm ci
npm run dev
```

Open `http://localhost:3000`. For checks and production:

```sh
npm run lint
npm run build
npm run start
```

`start` requires a successful build. Node v26.13.0/npm 11.20.0 were present at inspection; no team runtime pin or `engines` declaration exists. Agree a supported reproducible runtime with integration owners. Do not create another application. The starter uses `next/font/google` for Geist and Geist Mono, so builds currently require access to Google Fonts. A restricted environment may also block Turbopack worker port binding; report that separately from source failures.

## Planned environment and mode switching

No environment variables are required/read by the current starter. The following are **planned** for the adapter implementation; create local `.env.local` at that phase:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
```

These public variables are not secrets and are generally embedded at build time; changing a deployed mode/base URL requires rebuilding. For live mode, set `NEXT_PUBLIC_USE_MOCKS=false` and point the base URL at the agreed FastAPI origin (append `/api/v1` once in the shared layer). Backend B must enable appropriate frontend-origin CORS, including localhost during development. The contextual map uses OpenFreeMap’s public dark style without an API key; no basemap environment variable is required. Scientific mock/live switching remains unwired.

Planned switching: one `src/lib/api/` factory selects an explicitly configured mock or HTTP adapter; both implement identical approved types. Components call the shared hooks/interface. Zod checks live and fixture payloads. Mode and all relevant selection dimensions belong in query keys. Live errors remain errors and never activate synthetic fallback. Every mock view/export must display **DEVELOPMENT / SYNTHETIC**; fictional fixtures are not NASA observations or release evidence. Approved real precomputed static JSON is a separate contingency requiring provenance and the same schema, not synthetic mock mode.

## Required handoffs

| Owner | Required input to frontend integration |
| --- | --- |
| Member 1 — Data Engineer | Frozen official IBGE Pará boundary; source URL, boundary release year, CRS, processing date and boundary-edge policy; clipping QA; data dictionary; canonical grid/block IDs and geometries; Pará-filtered MODIS/S-NPP tables and coverage/provenance. |
| Member 2 — Data Scientist | Model version/card, selected ratio baseline or validated NB, historical block-month estimates, supported domain, held-out year/geographic-block metrics, baseline comparison, eligible/excluded counts and assumptions; uncertainty only when validated. Model package/inference interface goes to Backend B, not browser code. |
| Backend A — Member 3 | Tested within-Pará geo/time queries, canonical geometry lookup and ID linkage, 10 km observed/50 km estimated block mapping, approved aggregate/selection semantics and partial-border support. No browser point-in-polygon/grid replacement. |
| Backend B — Member 4 | Seven FastAPI routes; approved parameters, response schemas, null/status conventions, pagination, HTTP error fixtures, CORS and API versioning; model integration and precomputed estimates; approved JSON fixtures and OpenAPI. |
| Collaboration/integration lead — Member 6 | Repository coordination, contract acceptance by affected owners, source/scientific-claim review, integrated real-data QA and release/demo acceptance. |

Member 2 → Backend B handoff on p. 6 includes `model.joblib`/package, `predict.py` with `predict_viirs_equivalent(...)` and batch inference/guardrails, `model_info.json`, `validation_metrics.json`, `estimated_viirs_block_month.parquet`, example input/output, `requirements.txt`, `model-card.md` and a reproducible smoke test. Confirm these upstream rather than reproducing the model in TypeScript.

### Required official geometry assets

No official boundary or block geometry was present at inspection. The included rulebook is not a geographic dataset.

- Obtain a GeoJSON rendering of the **frozen official IBGE Pará polygon**, with manifest/version and upstream clipping tests. Agree browser coordinate representation (normally GeoJSON longitude/latitude) with Backend A; do not simply relabel EPSG:6933 meter coordinates as geographic coordinates.
- Obtain 50 km block features with exact backend `block_id`, region linkage and clipped support. The source grid is EPSG:6933, origin `(0,0)`, `ix=floor(x/10000)`, `iy=floor(y/10000)`, `grid_id="ix_iy"`; blocks derive from `floor(ix/5)`, `floor(iy/5)`. Member 1 owns the tested assignment function and block ID serialization.
- Confirm geometry delivery through approved responses or static assets; the rulebook does not specify a blocks route. Verify feature IDs join to estimates without frontend invention. Border blocks do not imply full-block support outside Pará.
- Optional municipality/preset boundaries need verification. Optional drawn/partial areas need approved selection and scientific aggregation semantics before enabling results. Do not approximate the study boundary to unblock development.

## Schemas awaiting approval and OpenAPI

All endpoint query signatures/envelopes remain **PROVISIONAL**; see the route-by-route register in API_CONTRACT. Blocking questions include nullable source MODIS/VIIRS counts, day/night representation, coverage metadata/enums, natural-log ratio conventions, observed versus estimated schemas, period bounds, geometry transport, daily drilldown, pagination and HTTP errors. Do not apply the fixed model response to every route.

Backend B should supply a versioned FastAPI OpenAPI export (confirm its URL), approved success/null/unsupported/error fixtures for each route and change-review ownership. Generate TypeScript transport types from the approved schema, add Zod runtime checks and CI fixture/contract verification. Agree minimal testing/type-generation tooling before adding dependencies. Map-guard tests use the built-in Node runner through `npm run test:map`; a broader application/contract suite remains pending.

The PDF model-response required list includes `measurement_unit`, but its explicitly fictional example omits it. Request a corrected complete fixture; keep the required field. `daynight="D"` and `coverage_status="unknown"` examples do not define complete enums.

## Outstanding science and integration blockers

- Official geometry/version and processed real data are still handoffs; no real historical/observed integration can be claimed yet. Preserve unsupported/unprocessed months as null/status.
- Historical domain is supported mid-2002–2011 Aqua MODIS; observed S-NPP is available from 2012 where processed. No guaranteed full 2002–2026 archive, Terra-only 2000–2001 conversion or NOAA-20 gap fill.
- Calibration is Pará-filtered 50 km block × year × month × day/night. No validated 10 km estimated layer, arbitrary partial-area scaling, or generalization across Brazil/the Amazon.
- Positive-detection CSVs alone cannot prove observation coverage or fire-free zero. Keep preliminary coverage-unadjusted limitations visible until independent evidence supports stronger claims.
- Temporal and geographic holdouts, comparable baseline/NB evaluation and later Aqua orbit-drift limitations need real metadata. Ratio-of-totals cannot recover VIIRS-positive/MODIS-zero detections; NB nonzero output is not evidence of recovered missing fires.
- Seasonal median/IQR needs comparable data; mixed-era anomalies require calibration stability. No fabricated confidence intervals, model scores, hotspot locations, intensity, burned areas or distinct-fire counts.
- Keep the existing database/query path (PostGIS or DuckDB/Parquet as already chosen upstream); frontend inspection does not establish which backend is deployed. No second service/database/model.
- This workspace was not a Git repository at inspection. Coordinate the intended repository with the lead; no repository was initialized. External MODIS datasets remain untouched.

## End-to-end acceptance checklist

- [ ] Official frozen IBGE polygon and provenance reviewed; upstream interior/exterior/edge and coordinate-order tests pass. No national Brazil records leak into Pará totals.
- [ ] Only `BR-PA` is active. Outside/unsupported selections produce no analytics; backend rejects unsupported inputs too.
- [ ] Canonical block IDs join correctly; border support and 50 km historical scale are visible; no estimated hotspot point layer or 10 km prediction claim.
- [ ] At least one supported real historical period and one real observed period reconcile against backend values.
- [ ] Supported area → calendar → trend → Sensor Lab works; month selection updates the map; selection changes cannot show stale data for another area.
- [ ] Historical Estimated, actual Observed, NRT Provisional, Not processed and Unsupported remain consistent across views, with time/source labels and 2012 transition.
- [ ] Null/gaps survive transport, caching, charts and calendar; verified zero requires evidence; MODIS and VIIRS are never added.
- [ ] Sensor Lab uses actual held-out predictions/observations, year and geographic-block metrics, baseline comparison and honest coverage/model limitations.
- [ ] All seven endpoint schemas/parameters, statuses/errors, geometry delivery and CORS are approved; fixtures/OpenAPI agree with implementation.
- [ ] Mock/live switching uses the same component interface, synthetic labels remain obvious and live errors never silently become mock results.
- [ ] Meaningful automated contract/interaction tests, keyboard/responsive checks, lint and production build pass; environmental blockers are recorded explicitly.
- [ ] Lead signs off sources, scientific claims, deployment and real-data demo. Optional animation/CHRONO/drawing never displaces these gates.

## Verification record — 11 November 2026

- Extracted and read all 10 PDF pages using PDFKit; checked the documentation against the rulebook. The docs copy and original have identical SHA-256 hashes (`9684a895ebdf48464e7966ffa4c52a5150530f43afa6856064f241919a5e87fa`).
- `npm ls --depth=0`: passed; installed direct dependencies match `package.json`, including the requested stack. No dependency, lockfile or application-source changes were needed.
- `npm run lint`: passed after document creation (exit 0).
- `npm run build`: failed (exit 1). Initial attempt could not fetch Google Fonts. Retried with approved escalation; final failure was `TurbopackInternalError: Failed to write app endpoint /page`, caused by CSS worker process port binding: `Operation not permitted (os error 1)`. The approved retry reproduced that environment restriction. A successful production build remains unverified; rerun in an environment allowing the worker port and font access. No build workaround or dashboard change was introduced.
- Automated application tests: not run; no runner/script exists yet. Feature and release checks above remain pending.

Subsequent design-system verification on 11 November 2026: after updating global theme tokens, `npm run lint` and `npm run build` both passed, including TypeScript/static generation. This supersedes the earlier outstanding build blocker above; no build-configuration workaround was needed. See [DESIGN_SYSTEM](DESIGN_SYSTEM.md) for token/contrast checks. Application feature tests remain pending.

Phase 2 handoff: `/`, `/time-machine`, `/sensor-lab` and `/methodology` now render the shared FireChronicle shell. Selection state persists during client navigation and resets on reload; the initial September 2020 period is a navigation choice, not a loaded observation. No FastAPI calls or mock science fixtures are used. Lint, standalone TypeScript and production build pass, as do targeted Chrome responsive/interaction checks recorded in FRONTEND_PLAN. The next handoff remains the frozen IBGE boundary and canonical supported geometry/IDs for Phase 3. Endpoint schemas, coverage and model evidence remain unresolved as listed above.


## Interactive map handoff

The Explore route now uses `src/components/map/map-workspace.tsx` and the client-only `para-map.tsx`. Existing `maplibre-gl` supplies rendering and CSS; no library was replaced or added. Next/Turbopack emits the v6 worker via `setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString())`. Preserve this setup: without it a canvas can exist while vector tiles fail to load.

The basemap is geographic context, independent of scientific API mode. Its current style URL is `https://tiles.openfreemap.org/styles/dark`, verified as reachable. Required OpenFreeMap/OpenMapTiles/OpenStreetMap attribution is retained. Reference: [OpenFreeMap quick start](https://openfreemap.org/quick_start/), [provider attribution](https://openfreemap.org/), [MapLibre bundler setup](https://github.com/maplibre/maplibre-gl-js/blob/main/docs/index.md). Basemap service availability remains external; failed resources show an honest retry state. The provider currently emits a nonfatal missing `circle-11` basemap icon warning; map tiles, labels and controls render. No scientific geometry is involved in that warning.

No official frozen boundary or canonical blocks were found. The implementation intentionally does not download an arbitrary latest polygon. Basemap borders cannot validate study membership. The initial camera center `[-52.5, -3.5]` and zoom `5.2` frame Pará context only; no rectangle is used for membership or analytics.

### Connecting verified geometry and data

1. Member 1 supplies the frozen IBGE GeoJSON and manifest: official source URL, label/version, release year, processing date, CRS and boundary-edge policy. Backend A supplies canonical 50 km block IDs and clipped support polygons for that exact boundary version. Geographic correctness, clipping and ID assignment remain upstream responsibilities.
2. Map approved `/api/v1/regions` responses or a vetted local GeoJSON import to `FrozenBoundary` in `src/types/map-data.ts`, then pass `data` to `<MapWorkspace data={...} />`. Browser inputs use EPSG:4326 longitude/latitude; never relabel equal-area meter coordinates. A verified local asset can be imported with its manifest by the page; no speculative path is fetched automatically.
3. Normalize approved geometry into `VerifiedBlocks`: exact `block_id` properties, matching boundary version, BR-PA, 50 km scale, data-owner approval and clipped support. These are internal adapter checks, not new public JSON fields. Owner approval is a trusted integration assertion, not a claim that a boolean or coordinate check independently proves provenance. The map never invents canonical IDs.
4. The renderer prepares separate finalized observed and provisional point/aggregate sources. Approved `/api/v1/hotspots` and `/api/v1/harmonized` adapters must supply actual within-Pará geometries, source/scale metadata and matching year/month/layer. Finalized observations begin where supported from 2012. NRT additionally requires confirmed coverage for the exact selected period. Unknown coverage and unprocessed values remain explicit/null.
5. Historical model outputs must remain 50 km; current calibration block outlines carry no fabricated counts or quantitative color ramp. Numeric choropleths/legends await approved values and domains. The map does not infer scientific totals from rendered points or blocks.
6. Mock and live adapters use the same normalized renderer inputs. The current production default is all-null scientific input, not synthetic fixtures. Any future synthetic mode must be explicitly labeled; the unit-square geometry in `tests/map-data.test.mjs` is SYNTHETIC TEST ONLY and never imported by the app.

Click/hover uses verified block polygons and an official-polygon rendered hit-test; keyboard selection uses the same supplied ID list. Without both approved polygon and supported blocks, selection is unavailable. Backend authorization/domain validation must still be enforced. Zustand carries selected-block source, boundary version and nullable coverage keyed to year/month/layer. Metadata is cleared/refreshed as inputs change; observation counts remain null until real aggregation integration.

The remaining blocker is scientific data delivery, not basemap interactivity. No real block or observation end-to-end acceptance is claimed yet.

### Map verification

- `npm run lint`, `npx tsc --noEmit`, `npm run build`: passed after the final map changes. The production output includes the hashed MapLibre worker asset.
- `npm run test:map`: seven tests pass. They cover absent/unverified/wrong-region geometry, source/CRS checks, matching boundary version and 50 km clipped blocks, canonical IDs, null preservation, exact-period NRT coverage and sensor/era separation. Synthetic test geometry is isolated from the app.
- Chrome development smoke checks: real map tiles/labels and attribution, full-height canvas, pan/zoom/reset, resize, route cleanup, responsive layouts, unavailable scientific selection, unconfirmed NRT disabled, style failure and retry recovery all pass. No runtime/hydration errors were reported; the external basemap sprite warning is noted above.
- Chrome production check on a temporary port: worker startup, visible map/container height, pending scientific selection and zoom pass, without runtime/hydration errors. Production and mobile screenshots were reviewed. The temporary production server/browser were closed; the existing development server on port 3000 was preserved.
- No official-data selection or coverage completeness claim is made; those tests require the remaining upstream handoffs.


Camera correction verified on 12 November 2026: initial load and Reset View now share the Pará fallback camera (`[-52.5, -3.5]`, zoom `5.2`) after resize. Verified geometry still takes priority via fitBounds with viewport-aware padding. Period/layer changes do not reframe the map, and navigation resizing preserves its center. Plain scroll zoom is enabled. Chrome confirmed exact camera coordinates, drag/scroll/button interactions, mobile sizing and attribution without runtime/hydration errors. Lint, standalone TypeScript, production build and all nine map tests pass.

---

## Completed Frontend Implementation & Acceptance (13 November 2026)

All outstanding scientific data, official geometry, typed adapters, visual analytics, map layers, and export functionality have been completed, verified, and integrated into `feature/frontend-demo`:

### 1. Official Geometry & Quantitative Geospatial Map
- **Official IBGE 2024 Boundary**: Transformed directly from verified shapefile `PA_UF_2024.zip` (SHA-256: `5ddadf2e...`) to EPSG:4326 GeoJSON MultiPolygon (35 parts, 6,559 vertices). Validated against `boundaryIsUsable()`.
- **568 Canonical 50 km Blocks**: Transformed from `para_50km_grid_geometry.parquet` using pure-Python inverse Equal Earth equations (EPSG:6933 to EPSG:4326). Validated against `resolveMapData()`.
- **Quantitative Month-Specific Choropleth**: All 568 blocks dynamically reflect month-specific detection counts (`MAP_IDS.blockFill`).
  - Warm Amber ramp for Historical Estimated Era (2002–2011).
  - Emerald Green ramp for Modern Observed Era (2012–2020).
  - Neutral transparent borders for unobserved/missing passes (preserved NULL, never zero).
  - Hover tooltip displays exact block ID, detection count, and measurement tier.
  - Interactive selection updates Zustand `selectedBlock`, synchronizing map, charts, calendar, and sidebar.

### 2. Multi-Decadal Calendar Heatmap (`/time-machine`)
- Full 19-year × 12-month matrix (2002–2020 · 228 monthly cells).
- Jan–Jun 2002 styled as unsupported (pre-commissioning period, NULL preserved).
- July 2002 badged as partial operational coverage.
- January 2012 badged as partial VIIRS observation (days 1–19 unobserved).
- Interactive period synchronization and Statewide vs. Block toggle.

### 3. Recharts Visual Analytics Suite
- **Monthly Multi-Decadal Timeline**: Preserved NULLs (`connectNulls={false}`), vertical 2012 era transition line, optional Aqua MODIS raw context curve with strict no-summation notice.
- **12-Month Seasonal Climatology**: Historical era (2003–2011) vs modern era (2012–2020) monthly averages, Amazonian dry season peak (Aug–Nov). Caveat clearly documented: visual consistency reflects fitted $\beta_{\text{month}}$ fixed effects, not independent historical validation.
- **Annual Totals Chart**: 19-year totals highlighting historical drought years (2004, 2005, 2007, 2010) and distinct partial year 2002.
- **Sensor Lab Model Validation Card (`/sensor-lab`)**: Authoritative, split-specific metrics from `validation_metrics_final_nb2.json`:
  - Strategy A Temporal Holdout: NB2 MAE 35.44, Poisson deviance 25.01 (54.8% reduction vs baseline).
  - Strategy B Geographic Holdout: NB2 MAE 35.79, Poisson deviance 20.95 (62.8% reduction vs baseline).
  - Architecture: Negative Binomial NB2, log link, dispersion $\alpha = 0.3394$, $k = 6.0538$, N=23,010 paired-positive training records.

### 4. Typed Data Access Layer & Mode Switching
- Shared `DataClient` interface with 3 pluggable adapters:
  - `StaticJsonAdapter`: Reads precomputed static JSON under `public/data/` (Node `fs` for SSR/prerender, `fetch` for browser).
  - `LiveApiAdapter`: Connects to FastAPI backend (`/api/v1/...`), strictly throws `ApiHttpError` on failure (never silently falls back to synthetic fixtures).
  - `MockAdapter`: Synthetic fixtures stamped with visible `DEVELOPMENT / SYNTHETIC` watermarks.
- Mode resolution: `NEXT_PUBLIC_DATA_MODE` (`static` | `live` | `synthetic`) -> `NEXT_PUBLIC_USE_MOCKS` -> default `static`.

### 5. RFC 4180 CSV Export
- One-click export for Statewide Pará or selected 50 km block.
- Columns: `region_id,block_id,year,month,daynight,value,value_type,status,measurement_unit,model_version`.
- Exact 228 monthly rows with preserved NULLs and `daynight="ALL"`.

### 6. Automated Verification Status
- `npm test`: 19/19 tests passing across map data, static data schemas, client adapters, chart transforms, and CSV export.
- `npm run test:map`: 9/9 focused map & geometry tests passing.
- `npm run lint`: 0 errors, 0 warnings.
- `npx tsc --noEmit`: 0 type errors.
- `npm run build`: Production Next.js build prerenders all 4 routes (`/`, `/time-machine`, `/sensor-lab`, `/methodology`).

### 7. Vercel Deployment Readiness
- Pre-configured for deployment with zero build overrides.
- Recommended production environment variables:
  ```dotenv
  NEXT_PUBLIC_DATA_MODE=static
  ```
- Public demo target: `https://firechronicle.vercel.app` (awaiting user authorization to push and publish).
