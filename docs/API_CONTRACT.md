# FastAPI contract register

Authority: [rulebook](FireChronicle_FINAL_Team_Rulebook_Para_Brazil.pdf), pp. 6–8. Routes and release requirements below are binding. **All public query parameters, JSON envelopes, endpoint-specific field mappings, pagination and HTTP error shapes are PROVISIONAL pending approval.** No endpoint schema or adapter is implemented in this task.

Member 1 approves geographic/grid/processed-data schemas; Member 2 approves model inputs/outputs; Backend A supplies tested queries/geometries; Backend B (Member 4) approves public API shapes; the collaboration lead coordinates agreement by affected owners. This document does not grant contract-change approval.

## Exact endpoint requirements (rulebook p. 7)

| Method and route | Rulebook definition |
| --- | --- |
| `GET /api/v1/regions` | Return Pará BR-PA only as active region, its polygon/bounds, processed years and statuses; Brazil is geographic context, not a second supported analysis region. |
| `GET /api/v1/harmonized` | Return 50 km estimated block values or separately identified observed summaries, with year/month and type/status. |
| `GET /api/v1/timeseries` | Monthly values for supported user-selected area within Pará, keeping genuine data gaps. |
| `GET /api/v1/calendar` | Year × month burning calendar plus optional daily drilldown and data type labels. |
| `GET /api/v1/hotspots` | Actual reported hotspot point locations in Pará, with source metadata; paginate and bound queries. |
| `GET /api/v1/model-info` | Selected baseline/model, held-out results, calibration units, region=Pará, uncertainty and limitations. |
| `GET /api/v1/coverage` | Availability for Pará per year/month, unknown/verified status and unsupported reasons. |

Request examples are deferred until query signatures are approved.

## Locked model response (not a universal endpoint envelope)

Rulebook p. 6 defines **one shared model response**. It does not establish that every endpoint returns this object, or specify how objects are wrapped in map/calendar/timeseries payloads.

| Required model field | Binding definition / unresolved detail |
| --- | --- |
| `region_id` | Exactly `"BR-PA"`. |
| `block_id` | Canonical backend 50 km block identifier. Grid derivation is fixed on p. 3; serialization/geometry linkage must be confirmed with Member 1/Backend A. Do not reuse the PDF's fictional example as an actual block. |
| `year`, `month` | Model's year/month keys. Supported periods come from metadata; do not assume every month exists. Public validation rules remain to be approved. |
| `daynight` | Required modeling dimension. The fictional example uses `"D"`; complete enum, combined/all behavior and query representation are unresolved. |
| `estimated_viirs_count` | Number or `null`; no coercion of unsupported/missing estimates to zero. Fractional estimates must not silently become integer observations. |
| `value_type` | Exactly `"estimated"` for this model response. Other endpoint value-type enums require approval. |
| `prediction_status` | Preserve the exact model status listed below. |
| `coverage_status` | Required. PDF example uses `"unknown"`; complete enum and verification evidence remain unresolved. |
| `model_version` | Required model identifier from backend metadata. |
| `measurement_unit` | Exactly `"VIIRS_S-NPP-equivalent_detection_count"` for the model output. |
| `calibration_scale_km` | Exactly `50`. No validated 10 km historical inference implied. |

Model prediction statuses (p. 6): `ok_preliminary`, `unsupported_region`, `unsupported_period`, `out_of_training_range`, `insufficient_coverage`, `missing_required_feature`, `model_error`. Preserve null and exact status together. Validated intervals are optional; field names, confidence level and validation must be supplied before use.

The illustrative numeric response on p. 6 is explicitly fictional and omits `measurement_unit`, although the required-field list includes it. Follow the required list and request a corrected complete fixture from Backend B; do not treat the example as real data or silently relax validation.

## Shared scientific semantics

- Respect `region_id`, `block_id`, `year`, `month`, `daynight`, `value_type`, `prediction_status`, `coverage_status`, `measurement_unit`, `model_version` and `calibration_scale_km` **where applicable**. Region listings and observed point records need not carry model-only fields; exact endpoint applicability is pending.
- Historical supported mid-2002–2011 values are **Estimated · historical extrapolation** using Aqua MODIS. From 2012, available actual S-NPP observations are **Observed · S-NPP**. Optional NRT is **Provisional · NRT**. **Not processed** and **Unsupported** must remain visible. These are presentation requirements, not a newly approved wire enum.
- Measurements count detected satellite pixels, not unique wildfires. MODIS and VIIRS are never added to make a harmonized total. Actual observed counts and estimated counts remain distinguishable throughout all payloads/views.
- Preserve nulls. Missing positive rows do not verify zero. Only usable observation evidence permits a verified zero. Count nullability for the MODIS/VIIRS source tables is still a coordination question; it must not be resolved by blanket zero filling.
- Identical frozen IBGE Pará membership applies to all sensors/periods upstream. Backend owns EPSG:6933 grid assignment and supported-area validation. Historical estimates use 50 km blocks; observed summaries may use 10 km cells and points retain actual reported coordinates.
- Provenance must retain source dataset, spacecraft, processing version, UTC acquisition time, fire-type availability, confidence, FRP and latitude/longitude where applicable. Exact public nesting/field names are unresolved.
- Coverage based only on positive-detection CSVs is preliminary/coverage-unadjusted. Seasonal comparisons require comparable measurement tiers; mixed-era anomalies require demonstrated calibration stability.

## Endpoint-specific approval register — PROVISIONAL

The following are **coordination questions, not approved parameter or field names**.

| Route | Input decisions needed | Response decisions needed |
| --- | --- | --- |
| `regions` | Whether any query is accepted; unsupported-region behavior. | Polygon GeoJSON vs geometry link, CRS/bounds order, frozen boundary manifest, processed-year/status structure. Only BR-PA is active. |
| `harmonized` | Geographic selection, period/range, day/night, estimate/observed choice, scale constraints. | Estimated-block vs observed-summary representation, model-object wrapping, border support, geometry linkage, gaps and source labels. |
| `timeseries` | Supported block/area selection, range and day/night; drawn-area transport/aggregation if supported. | Monthly ordering, explicit gap representation, status/provenance per value, aggregation rules, comparable seasonal summaries. |
| `calendar` | Selection, supported year range, day/night; optional daily drilldown request. | Year/month layout, absent vs unprocessed vs unsupported vs verified zero, type/status mapping; daily support indicator and schema. |
| `hotspots` | Allowed sensors/periods, bounded spatial/time query, maximum size, pagination. | Actual coordinates/CRS, sensor/provenance representation, stable pagination, timestamps, confidence/FRP nullability; no synthetic model points. |
| `model-info` | Current vs versioned model selection. | Selected baseline/NB identity, holdout metrics and samples, calibration units, supported domain, model card/version, validated uncertainty or absence, limitations. |
| `coverage` | Spatial granularity, period range, sensor/daynight dimensions. | Availability by year/month, coverage enum, evidence for verified zeros, unsupported reasons, coverage provenance; mapping to model coverage status. |

Cross-route blockers: parameter names/defaults/requiredness, date inclusivity and UTC rules, supported ranges, error HTTP codes/body, no-result semantics, response envelopes, cache/version policy and CORS. Do not automatically convert HTTP errors into scientific `prediction_status` values or silently fall back to mock data.

The rulebook supplies no dedicated blocks-geometry route. Backend A/B must approve how the frontend obtains 50 km geometries and IDs through existing responses or an agreed asset handoff. Do not invent another endpoint as confirmed.

## Scientific coordination questions

1. Members 1/2 and Backend B: nullable MODIS/VIIRS counts, missing-feature behavior and independent evidence for zero observations.
2. Members 1/2 and Backend B: full day/night enum, filtering/aggregation and combined-view behavior.
3. Members 1/2 and Backend B: coverage metadata, exact statuses, evidence and processing/NRT provenance.
4. Member 2 and Backend B: natural-log ratio convention, numerator/denominator, zero/null handling and intended display. The mandatory model baseline remains `sum(V) / sum(M)` learned within each training fold (p. 5); this is not approval for a frontend log-ratio formula.
5. Members 1/2 and Backend A/B: partial-block/drawn-area behavior without arbitrary downscaling of historical estimates.

## Planned integration boundary

Use one typed API layer with Zod checks and mock/live adapters exposing the same approved interface. Keep live responses separate from explicitly DEVELOPMENT / SYNTHETIC fixtures and preserve scientific statuses. Prefer precomputed monthly estimates; never retrain or process the archive on a click.

Recommend Backend B publish the FastAPI OpenAPI schema (standard `/openapi.json` location subject to confirmation), version it with approved fixtures, and generate transport types from it. Add runtime validation and CI contract checks against representative null/status/error payloads. No type generator/test dependency is installed by this documentation task. OpenAPI approval must precede declaring inferred endpoint shapes final.
