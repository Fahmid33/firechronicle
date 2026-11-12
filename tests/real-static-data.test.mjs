import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Compile and load the real verified-data validator
const asModule = (source) => "data:text/javascript;base64," + Buffer.from(source).toString("base64");
const compile = (source) => ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
}).outputText;

const explorer = asModule(compile(await readFile(new URL("../src/types/explorer.ts", import.meta.url), "utf8")));
const guards = compile(await readFile(new URL("../src/lib/map/verified-data.ts", import.meta.url), "utf8"))
  .replace('"@/types/explorer"', JSON.stringify(explorer))
  .replace('"zod"', JSON.stringify(import.meta.resolve("zod")));
const guardModule = asModule(guards);
const { resolveMapData, boundaryIsUsable, geometryBounds } = await import(guardModule);

// Read generated real static data
const boundaryData = JSON.parse(await readFile(new URL("../public/data/geo/para_boundary.json", import.meta.url), "utf8"));
const blocksData = JSON.parse(await readFile(new URL("../public/data/geo/para_50km_blocks.json", import.meta.url), "utf8"));
const timeseriesData = JSON.parse(await readFile(new URL("../public/data/timeseries/statewide_monthly.json", import.meta.url), "utf8"));
const calendarData = JSON.parse(await readFile(new URL("../public/data/calendar/calendar_matrix.json", import.meta.url), "utf8"));
const modelData = JSON.parse(await readFile(new URL("../public/data/sensor_lab/model_metrics.json", import.meta.url), "utf8"));

test("real official IBGE boundary passes boundaryIsUsable check", () => {
  assert.equal(boundaryIsUsable(boundaryData), true);
  assert.notEqual(geometryBounds(boundaryData.geojson), null);
  assert.equal(boundaryData.regionId, "BR-PA");
  assert.equal(boundaryData.approvedByDataOwner, true);
  assert.equal(boundaryData.crs, "EPSG:4326");
  assert.equal(boundaryData.releaseYear, 2024);
  assert.equal(boundaryData.geojson.features.length, 1);
  assert.equal(boundaryData.geojson.features[0].geometry.type, "MultiPolygon");
  assert.equal(boundaryData.geojson.features[0].geometry.coordinates.length, 35);
});

test("real canonical 50 km blocks pass resolveMapData validation", () => {
  const mapData = {
    boundary: boundaryData,
    blocks: blocksData,
    hotspots: null,
    aggregates: null,
  };
  const resolved = resolveMapData(mapData, 2020, 9, "observed");
  assert.notEqual(resolved.boundary, null);
  assert.notEqual(resolved.blocks, null);
  assert.equal(resolved.rejected, false);
  assert.equal(resolved.blocks.geojson.features.length, 568);
  
  // Verify unique block_ids
  const ids = resolved.blocks.geojson.features.map(f => f.properties.block_id);
  assert.equal(new Set(ids).size, 568);
  assert.ok(ids.includes("-104_-16"));
});

test("real statewide time series preserves gaps and correct sensor totals", () => {
  assert.equal(timeseriesData.regionId, "BR-PA");
  assert.equal(timeseriesData.series.length, 228); // 19 full years (2002-2020) x 12 months = 228
  
  // Check 2002-01 is unsupported_period and null
  const m1_2002 = timeseriesData.series.find(s => s.period === "2002-01");
  assert.equal(m1_2002.status, "unsupported_period");
  assert.equal(m1_2002.value, null);
  
  // Check 2002-07 is estimated
  const m7_2002 = timeseriesData.series.find(s => s.period === "2002-07");
  assert.equal(m7_2002.value_type, "estimated");
  assert.ok(m7_2002.value > 0);
  
  // Check 2012-01 is partial_observation
  const m1_2012 = timeseriesData.series.find(s => s.period === "2012-01");
  assert.equal(m1_2012.status, "partial_observation");
  assert.equal(m1_2012.value_type, "observed");
  assert.equal(m1_2012.value, 445);
  
  // Provenance totals
  assert.equal(timeseriesData.provenance.total_observed_viirs, 2196531);
  assert.equal(timeseriesData.provenance.total_observed_modis, 344071);
});

test("calendar matrix covers 2002-2020 with 19 years and 12 months", () => {
  assert.equal(calendarData.regionId, "BR-PA");
  assert.equal(calendarData.years.length, 19);
  calendarData.years.forEach(y => {
    assert.equal(y.months.length, 12);
  });
});

test("model metrics match official NB2 v1.0 specifications", () => {
  assert.equal(modelData.modelVersion, "firechronicle-nb2-v1.0");
  assert.equal(modelData.architecture.baselineRatioMultiplierK, 6.0538);
  assert.equal(modelData.trainingProvenance.trainingRecordsCount, 23010);
  assert.equal(modelData.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.mae, 35.4374);
  assert.equal(modelData.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.meanPoissonDeviance, 25.0056);
  assert.equal(modelData.officialEvaluationMetrics.strategy_B_geographic_holdout.nb2.mae, 35.7903);
  assert.equal(modelData.officialEvaluationMetrics.strategy_B_geographic_holdout.nb2.meanPoissonDeviance, 20.9497);
});
