<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Mission and authoritative scope

FireChronicle is a NASA Space Apps Challenge 2026 map-first historical burning-activity explorer for **Pará, Brazil only** (`region_id="BR-PA"`). Translate supported historical Aqua MODIS counts into estimated VIIRS S-NPP-equivalent hotspot detection counts; show actual S-NPP observations in the modern era.

Read all 10 pages of [the rulebook](docs/FireChronicle_FINAL_Team_Rulebook_Para_Brazil.pdf) before scientific or integration work. Source: Pará release amendment v1.0, effective 10 November 2026. The original supplied copy also remains at the project root. The PDF is authoritative; these documents do not approve new contracts. Follow [the delivery plan](docs/FRONTEND_PLAN.md), [API contract](docs/API_CONTRACT.md) and [handoff](docs/HANDOFF.md).

## Inspected technology stack

- Next.js 16.4.6 App Router, React/React DOM 19.3.0, TypeScript 5.9.3, strict mode, `@/*` → `src/*`.
- Tailwind CSS 4.3.3 through `@tailwindcss/turbopack`; CSS-first tokens in `src/app/globals.css`. No standalone Tailwind config is needed by the current setup.
- shadcn/ui `base-nova`, Base UI 1.9.0, Lucide React, `cn`, class-variance-authority, tw-animate-css. Existing UI primitives are in `src/components/ui/`.
- MapLibre GL JS 6.17.0, Recharts 3.10.1, Zustand 5.1.0, TanStack Query 5.107.1, Zod 4.6.7, Motion 14.12.0 are installed, but feature integration is pending.
- npm and `package-lock.json`; ESLint 9 with Next.js rules. Scripts: `dev`, `build`, `start`, `lint`. No automated test runner or test script yet.
- Current Next config enables Cache Components and Partial Prefetching. Consult installed Next.js guides before changing framework code; preserve the existing working configuration unless a verified blocker requires a fix.

## Folder and component conventions

Keep `src/app/` for routes, layouts and global styles; reuse `src/components/ui/` and `src/lib/utils.ts`. Create feature folders only as needed:

| Location | Responsibility |
| --- | --- |
| `src/components/map/`, `calendar/`, `charts/`, `layout/` | MapLibre, Time Machine, Recharts, responsive shell |
| `src/lib/api/` | Single typed request layer, Zod validation, mock/live adapters and query definitions |
| `src/store/` | Zustand geographic/time selection; no duplicate server-response cache |
| `src/types/` | Approved transport types and explicit presentation types |
| `src/mocks/` | Explicitly DEVELOPMENT / SYNTHETIC fixtures; never scientific evidence |
| `docs/`, `tests/` | Contracts/handoff and meaningful integration/interaction tests |

Use server components by default and client boundaries for interactive/browser-only features. Load MapLibre on the client. Keep TanStack Query responsible for server state; use stable geographic/time/source/mode query keys. Use existing libraries, accessible shadcn/Base UI controls and restrained motion. Do not scaffold another Next.js app or duplicate primitives.

Follow [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) for all future frontend implementation and consult [UI_REFERENCE.md](docs/UI_REFERENCE.md) for design rationale. Use the semantic global theme tokens and preserve Base UI/Nova behavior. Scientific status must remain distinguishable through text and pattern as well as color; never invent quantitative legend ranges.

## Scientific integrity and geography

- Measurement is satellite fire-positive pixels/detections, not distinct wildfires, burned area, intensity, deforestation or forecasts.
- Mid-2002–2011: supported Aqua MODIS-based estimates labeled **Estimated · historical extrapolation**. From 2012: actual S-NPP where available, labeled **Observed · S-NPP**. NRT, if supported, is **Provisional · NRT**. Show the 2012 transition and genuine gaps; do not promise a complete 2002–2026 archive.
- Never add MODIS and VIIRS counts to construct a harmonized count. Never call historical estimates observed S-NPP detections.
- Use one official frozen IBGE Pará polygon with source URL, release year, CRS, processing date and agreed boundary-edge policy. No invented polygon or bounding-box membership substitute. Outside Pará may be map context only; unsupported selections produce no analytics.
- Backend-owned grid: EPSG:6933, 10,000 m cells, origin `(0,0)`, floor indices; nested 50 km blocks from `floor(ix/5)`, `floor(iy/5)`. Consume approved IDs/geometries; do not recompute a competing grid in the browser.
- Historical predictions remain at the validated **50 km** scale. Actual observed points may retain coordinates and observed summaries may use 10 km cells. Explain clipped support for blocks crossing the state border. Partial/drawn selections require approved backend aggregation semantics.
- Keep unavailable/unsupported values `null` and preserve exact statuses. Zero requires usable observation evidence; absent positive-detection rows do not establish a verified zero. No `null`→`0`, interpolation across gaps, invented hotspot points, metrics or confidence bands.
- Each displayed value must identify status, time period and source. Keep model scale, coverage and extrapolation limitations visible. Positive-detection-only evidence means preliminary, coverage-unadjusted results.
- Retain backend provenance: dataset, spacecraft, processing version, UTC acquisition time, fire-type availability, confidence, FRP and coordinates where applicable. Do not infer fire types, kiln masks, NOAA-20 substitutions or coverage corrections.
- Gate mixed-era comparisons on demonstrated calibration stability; prefer season-matched, comparable measurement tiers. Real validated intervals are optional, never synthesized by the frontend.

## Frontend/backend separation and API rules

Frontend owns presentation, interaction, selection state and validated transport consumption. Member 1 owns boundary/grid/data schemas; Member 2 owns model science; Backend A owns geo/time queries and aggregation; Backend B owns FastAPI, HTTP errors and public schemas. The integration lead coordinates approval by all affected owners.

Use only the agreed FastAPI `/api/v1` service and one typed access layer. Scientific aggregation, model training/inference, geographic membership and archive processing stay outside React. Prefer backend precomputed monthly estimates. No second backend, database, MCP server or model service.

The rulebook fixes a model response, but endpoint envelopes/parameters remain **PROVISIONAL** until Backend B and affected owners approve fixtures/OpenAPI. Do not apply model fields indiscriminately to every endpoint. Preserve `region_id`, `block_id`, `year`, `month`, `daynight`, `value_type`, `prediction_status`, `coverage_status`, `measurement_unit`, `model_version`, `calibration_scale_km` where applicable. Do not finalize nullable sensor counts, day/night enums, coverage enums or natural-log ratio conventions locally.

Plan `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` and `NEXT_PUBLIC_USE_MOCKS=true` (not wired yet). Mock/live adapters must expose the same approved interface so components do not change. Make synthetic mode unmistakable in every view/export; live failures must never fall back silently to synthetic fixtures. Public env variables contain no secrets.

## Verification and Git safety

Run `npm ci` for a fresh install, then `npm run lint` and `npm run build` for changes. Report actual results and environmental blockers. Add meaningful schema/adapter and interaction tests as features land: preserve nulls and statuses, reject unsupported selections, distinguish eras, synchronize map/calendar/trends, and prove mock/live parity. Do not claim tests ran before a runner exists. See HANDOFF for release acceptance.

Inspect repository status before edits. This workspace was not a Git repository at initial inspection; do not initialize one or assume a clean diff. Preserve teammate work and the generated Next.js agent block. Never delete/modify external MODIS files, including `../modis/` or `../modis_2025_all_countries.zip`. No destructive resets, force pushes, unrelated dependency installs or contract changes without authorization and affected-owner agreement. Keep commits scoped; exclude secrets, generated caches and bulk datasets.

## Prioritized delivery

Complete foundation/documentation first. Then deliver the responsive NASA-inspired shell, working official Pará map, linked supported block selection, calendar, trends/Sensor Lab, approved adapters and release QA as detailed in FRONTEND_PLAN. Start backend contract/geometry coordination immediately; use only visibly synthetic fixtures while blocked. Prioritize a real map → calendar → trend → Sensor Lab path over animations, CHRONO and extra features. This initial task authorizes documentation/configuration inspection only, not dashboard implementation.
