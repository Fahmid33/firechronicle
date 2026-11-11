# FireChronicle frontend delivery plan

Authority: [rulebook](FireChronicle_FINAL_Team_Rulebook_Para_Brazil.pdf), Pará release amendment v1.0, all 10 pages; especially pp. 2–9. Read with [API_CONTRACT](API_CONTRACT.md), [DESIGN_SYSTEM](DESIGN_SYSTEM.md) and [HANDOFF](HANDOFF.md). Phases 1 and 2 are implemented. Phase 3 now has a working interactive basemap; official geometry and scientific integration gates remain pending.

## Inspected foundation

The existing `src/app/` now contains the four FireChronicle routes and a persistent dashboard shell, with global design tokens and Geist fonts. Existing Base UI/Nova primitives remain in `src/components/ui/`; `src/lib/utils.ts` exports `cn`. Strict TypeScript and the `@/*` alias are configured. The requested stack is installed (see root AGENTS.md). Phase 2 adds a per-provider Zustand selection store and modular layout/map-placeholder/calendar/chart-pending components. The placeholder has now been replaced by MapLibre. A query provider, API adapters and approved geospatial assets remain pending; seven Node map-guard tests are available through `npm run test:map`. Keep the existing app and npm lockfile.

## Phase 1 — Project foundation and documentation

**Status:** Complete. Rulebook, architecture, API register, handoff and design-system documentation are available.

**Dependencies:** Existing project and complete rulebook review.

**Acceptance:** Root AGENTS.md, this plan, API_CONTRACT.md and HANDOFF.md agree with the PDF. Preserve the generated Next.js rules. Record actual installed dependencies, current scripts and unresolved schemas. Provide the authoritative PDF at the requested docs path while preserving the supplied root original. Run lint/build and report outcomes. No dashboard implementation or unrelated dependencies.

## Phase 2 — Premium NASA-inspired dashboard layout

**Status:** Implemented on 11 November 2026. The default Next.js welcome page has been replaced.

**Dependencies:** Phase 1; existing shadcn/Base UI primitives.

**Acceptance:** Responsive shell with dominant map space, collapsible scientific panels and persistent status/source/period/scale/coverage labels. Midnight navy, forest green and warm amber tokens; elegant readable typography, accessible focus/keyboard controls and reduced-motion support. Include loading/error/missing/unsupported states. Any synthetic preview has a prominent DEVELOPMENT / SYNTHETIC label. No fabricated statistics; shell does not block map delivery. Advanced animation is deferred.

**Delivered:** `/` Explore, `/time-machine`, `/sensor-lab` and `/methodology`; shared header with identity, reference sensors and methodology access; desktop collapsible navigation and mobile Base UI sheet; desktop analysis sidebar, tablet analysis sheet and mobile in-flow analysis. The map placeholder occupies approximately 75% of the desktop central columns; no geographic shapes or points are rendered. All missing scientific values remain empty/null.

Reusable components live in `src/components/layout/`, `map/`, `calendar/`, `charts/` and existing `ui/`. `src/store/selection-store.tsx` creates one Zustand store per provider with fixed `region_id=BR-PA`, nullable `block_id`, selected year/month and requested layer. Client navigation retains selections; full reload resets to the explicit September 2020 starting view. Month/year controls and calendar buttons update shared state; crossing the 2012 era selects the corresponding layer. Explicit incompatible layer requests show Unsupported. The 2002–2026 navigation bounds do not claim processed availability; NRT support remains pending.

The calendar currently presents a selected-year month selector with unknown availability, not a populated historical heatmap. Sensor Lab has calibration, held-out comparison, model roles and pending validation metrics, with no decorative chart or fictional confidence bands. Shared state components handle pending/loading/empty/error/unsupported; route loading/error boundaries provide recovery. No mock scientific fixtures, backend requests, endpoint contracts or new dependencies were introduced. Layer names are UI types, not approved wire enums.

**Remaining acceptance:** Full real-data map/calendar connectivity, scientific status mapping, numeric legends, screen-reader review and automated feature tests belong to later phases. Geometry validation/block selection, actual yearly matrix and chart rendering are not completed by this shell.

**Phase 2 verification:** `npm run lint`, `npx tsc --noEmit` and `npm run build` passed after the final code changes; all four routes prerender successfully. Temporary headless-Chrome smoke checks passed for navigation expansion, month/year updates, era/layer compatibility, selection persistence across routes, calendar selection, pending Sensor Lab evidence, methodology, mobile navigation, tablet analysis and reduced motion. No browser runtime/console errors were reported. The desktop map column measured 984 px against a 320 px analysis column (about 75% of their combined width); no whole-page horizontal overflow at 1440, 900, 390 or 320 px. Desktop/calendar/mobile screenshots were inspected. This is targeted smoke verification, not a full accessibility audit or a newly installed test suite. The existing localhost development server was reused and left running.

## Phase 3 — Interactive MapLibre Pará map

**Status:** Interactive basemap implemented on 11 November 2026. Official boundary rendering and verified analytical selection await the frozen assets; the full scientific acceptance gate remains pending.

**Delivered:** `MapWorkspace` retains the shell and dynamically loads `ParaMap` with SSR disabled. MapLibre 6.17 ESM uses an explicitly bundled same-origin worker asset. OpenFreeMap's public dark style provides real contextual geography, pan, keyboard navigation, zoom and reset to Pará. Attribution remains accessible in the native control and always-visible linked credits. Base UI controls have 44 px targets; explicit viewport sizing and ResizeObserver handle mobile and navigation resizing. Control camera changes use zero-duration updates. Listeners, observers and the MapLibre instance are removed on unmount/retry.

Repository inspection found no frozen IBGE GeoJSON, canonical block polygons, observation files or API adapters. The map displays **Official Pará study boundary pending** and **Selection unavailable**; scientific sources start empty. Initial center/zoom is contextual framing, never a boundary or membership approximation. Basemap administrative lines are not the study polygon.

`src/types/map-data.ts` defines internal rendering inputs, not FastAPI envelopes. `src/lib/map/verified-data.ts` gates owner approval/provenance, BR-PA, coordinate structure, boundary version, clipped support, 50 km scale and canonical string IDs. Separate sources/layers prepare the official boundary, selectable calibration blocks, observed points, hollow provisional points, and observed/provisional aggregate outlines. No numeric ramps, estimates or detection points are synthesized. Exact-period confirmed coverage is required for NRT. Incompatible eras keep the basemap available and offer a compatible layer.

Verified block hover/click and a keyboard selector are ready for supplied data. Pointer selection requires a rendered official-polygon hit and a known supplied block ID. Selection metadata is period/layer-scoped and refreshed or cleared when inputs change. Counts remain null. Real-block end-to-end verification is blocked by absent official geometry.

**Remaining handoff:** Frozen IBGE polygon/manifest, Backend A's clipped block geometries/IDs, Backend B-approved schemas, per-period coverage and actual observations. Approved adapters for `/api/v1/regions`, `/api/v1/harmonized` and `/api/v1/hotspots` will map transport data to renderer props; no new API envelope or endpoint is assumed. See HANDOFF for connection details.

**Verification:** Lint, standalone TypeScript, production build and all seven `npm run test:map` tests pass. Chrome checks verify actual rendered tiles/labels, a full-height WebGL canvas, zoom/reset/pan, resize after navigation collapse, route unmount/remount, pending geometry, disabled NRT, no invented block selection, and no page overflow at 1440/390/320 px. Simulating a blocked style request shows the error/retry state and recovers without a duplicate canvas. Desktop/mobile screenshots were inspected. A separate production-mode check passes worker initialization, visible map height, zoom and absence of runtime/hydration errors. Real official-boundary/block acceptance remains pending, not simulated in the application.

**Dependencies:** Phase 2 minimum shell; Member 1 frozen official IBGE polygon and provenance; Backend A geometry/CRS handoff; approved basemap source/attribution.

**Acceptance:** Client-only MapLibre map fits and clearly outlines Pará; outside geography remains contextual. Display only supplied official boundary geometry, with no approximate fallback. Loading and missing-asset messages are useful. No outside-Pará analytics. Observed point layers, if supplied, contain real reported coordinates and source metadata; no generated estimated points. Map resizes and cleans up correctly.

## Phase 4 — Selectable geographic blocks and linked selection state

**Dependencies:** Phase 3; approved 50 km block geometry/IDs, clipped-support metadata and Backend A selection semantics; approved geometry transport (route still unresolved).

**Acceptance:** Clicking a supported block sets the canonical backend `block_id` under `BR-PA`; Zustand holds selection and time, TanStack Query holds responses. Boundary blocks explain clipped support. Outside/unsupported areas cannot request results. Selection updates linked panel/query state without stale values. Drawn areas and verified municipalities remain optional until backend validation and aggregation are approved. No 10 km display of historical predictions.

## Phase 5 — Historical year-by-month Time Machine

**Dependencies:** Phase 4; approved calendar/coverage schemas and fixtures through the planned shared interface; at least one supported historical and observed period for live acceptance.

**Acceptance:** Year × month calendar follows selected area; selecting a month updates map/time state. Mid-2002–2011 supported estimates are visibly distinct (e.g. hatching); actual S-NPP begins only where available from 2012, with a visible era transition. Show Provisional NRT, Not processed, Unsupported and missing states explicitly. `null` never becomes zero. Period availability comes from backend coverage, not an assumed complete date range. Daily drilldown appears only when supported. No arbitrary mixed-era anomaly claims.

## Phase 6 — Time-series charts and Sensor Lab

**Dependencies:** Phase 5; approved timeseries/model-info responses; Member 2 held-out predictions, observations, baseline comparison and validation evidence.

**Acceptance:** Recharts shows genuine gaps and status/source/period labels consistently with map/calendar. Comparable seasonal median/IQR is available only with approved backend results and comparable coverage; no browser scientific calculation. Sensor Lab compares MODIS-based prediction against actual S-NPP for a held-out overlap year using only MODIS predictors. Report real temporal/geographic holdout results, eligible sample counts, selected model, 50 km scale and limitations. Baseline is ratio-of-totals; deploy NB only with material demonstrated improvement. Confidence intervals require validation. Mixed-era comparisons require calibration stability evidence.

## Phase 7 — FastAPI mock/live data adapters

**Dependencies:** Phase 1 contract coordination starts immediately; final integration depends on Backend B-approved endpoint parameters, schemas, statuses, fixtures/errors and CORS, plus Backend A queries and Members 1/2 data/model handoffs. Do not postpone interface coordination until charts are finished.

**Acceptance:** One `src/lib/api/` boundary provides typed requests and Zod runtime checks through interchangeable mock/live adapters. Only public base URL and explicit mock flag configure mode; no component rewrite. Mode participates in caching to prevent fixture/live mixing. Synthetic fixtures are labeled in views/exports and cannot mask a live error. Queries include all approved geographic/time/sensor dimensions; stale requests are cancelled or isolated. Invalid payloads/HTTP errors remain explicit; preserve null and exact backend statuses. Validate each of the seven routes against approved fixtures/OpenAPI. No second backend or frontend model inference.

## Phase 8 — Automated testing and backend handoff

**Dependencies:** Phases 3–7 working together, approved real data and contracts; agreed application test tooling (Node map-guard tests exist; broader application tooling remains pending); integration lead release review.

**Acceptance:** Meaningful adapter/schema tests cover nullable values, verified zeros, exact statuses, sensor/era distinctions, malformed responses and mock/live parity. Interaction/end-to-end tests cover supported selection → historical calendar → trend → Sensor Lab and time → map updates, outside-region rejection, errors and missing coverage. Check keyboard accessibility and responsive map/panels. Lint/build pass, or environmental blockers are recorded precisely. Reconcile at least one real historical period and one observed period with backend totals. Complete HANDOFF checklist and approved scientific-claim review before release.

## Delivery priority and release gates

Rulebook milestones (p. 9): feature freeze at end of 11 November 2026; integration/deployment QA on 12 November; submission on 13 November (portal cutoff to be confirmed by the lead). These are targets, not a claim that milestones are complete.

Work toward the smallest real supported area and historical/observed periods first. Blocked geometry stays unavailable; unprocessed years stay Not processed. If NB is unstable, use the evaluated ratio baseline with its MODIS-zero limitation. If coverage evidence is absent, show preliminary coverage-unadjusted detected-pixel counts. If API hosting fails, only use lead-approved precomputed static JSON through the same approved schema, with provenance intact. Cut animations, optional CHRONO, drawing, daily drilldown and exports before real map/calendar connectivity or scientific accuracy.


## Camera correction — 12 November 2026

The fallback and Reset View now share `src/lib/map/map-camera.ts`: center `[-52.5, -3.5]`, zoom `5.2`, zero bearing/pitch. These are camera coordinates only. Initial load reapplies focus after `map.resize()` using the visible container; actual verified geometry bounds take priority with viewport-aware padding. Repeated year/month/layer updates do not reframe the map. Geometry changes reframe once, while ResizeObserver keeps the canvas aligned with dashboard width changes. Plain scroll zoom is enabled alongside drag and the existing zoom/reset buttons.

Repository reinspection still found no frozen official IBGE boundary or canonical block GeoJSON. The UI says “Official Pará boundary pending”; the existing verified-data interface, real-ID-only selection, scientific nulls and provenance sidebar remain intact.

Chrome checks confirmed exact initial center/zoom after loading, drag, plain scroll zoom, zoom buttons, reset, camera preservation on period/layout changes, mobile visible dimensions and attribution. No runtime/hydration errors were reported. Nine map/data/camera tests, `npm run lint`, `npx tsc --noEmit` and `npm run build` pass.
