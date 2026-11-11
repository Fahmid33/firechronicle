import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Exercise the real TypeScript guards using the existing compiler and Node test
// runner. No frontend test dependency or production test-data endpoint is added.
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
const camera = compile(await readFile(new URL("../src/lib/map/map-camera.ts", import.meta.url), "utf8"))
  .replace('"@/lib/map/verified-data"', JSON.stringify(guardModule));
const { focusPara } = await import(asModule(camera));

// SYNTHETIC TEST GEOMETRY ONLY. A unit square at (0,0), NOT Pará, NOT an IBGE
// dataset, and never imported by the app. The manifest simulates trusted owner
// inputs to test structural gates; it is not evidence of geographic validity.
const polygon = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] };
const geojson = { type: "FeatureCollection", features: [{ type: "Feature", geometry: polygon, properties: {} }] };
function fixture() {
  return {
    boundary: { regionId: "BR-PA", approvedByDataOwner: true, crs: "EPSG:4326", sourceUrl: "https://www.ibge.gov.br/", sourceLabel: "SYNTHETIC TEST ONLY", version: "test-boundary", releaseYear: 2000, processingDate: "2000-01-01", edgePolicy: "TEST ONLY", geojson: structuredClone(geojson) },
    blocks: { regionId: "BR-PA", approvedByDataOwner: true, boundaryVersion: "test-boundary", calibrationScaleKm: 50, clippedToStudyBoundary: true, sourceLabel: "SYNTHETIC TEST ONLY", geojson: { type: "FeatureCollection", features: [{ type: "Feature", geometry: structuredClone(polygon), properties: { block_id: "TEST-ONLY" } }] }, coverage: [{ blockId: "TEST-ONLY", year: 2020, month: 9, layer: "observed", status: null }] },
    hotspots: null,
    aggregates: null,
  };
}
function provisional() {
  return { regionId: "BR-PA", approvedByDataOwner: true, boundaryVersion: "test-boundary", year: 2020, month: 9, layer: "provisional", coverageConfirmed: false, coverageStatus: null, sourceLabel: "SYNTHETIC TEST ONLY", resolutionLabel: "Test point geometry", geojson: { type: "FeatureCollection", features: [] } };
}

test("missing official boundary blocks every analytical geometry", () => {
  const data = fixture(); data.boundary = null;
  const result = resolveMapData(data, 2020, 9, "observed");
  assert.equal(result.boundary, null); assert.equal(result.blocks, null); assert.equal(result.hotspots, null);
});
test("rejects wrong region, absent approval, non-IBGE sources, and projected coordinates", () => {
  for (const change of [
    b => { b.regionId = "BR-AM"; },
    b => { b.approvedByDataOwner = false; },
    b => { b.sourceUrl = "https://ibge.gov.br.example.com/"; },
    b => { b.crs = "EPSG:6933"; },
    b => { b.geojson.features[0].geometry.coordinates[0][1] = [100000, 200000]; },
    b => { b.geojson = {}; },
  ]) {
    const data = fixture(); change(data.boundary);
    assert.equal(boundaryIsUsable(data.boundary), false);
  }
});
test("requires matching boundary, clipped support and the 50 km model scale", () => {
  for (const change of [
    b => { b.boundaryVersion = "different"; },
    b => { b.clippedToStudyBoundary = false; },
    b => { b.calibrationScaleKm = 10; },
    b => { b.geojson.features[0].properties.block_id = 123; },
    b => { b.geojson.features.push(structuredClone(b.geojson.features[0])); },
  ]) {
    const data = fixture(); change(data.blocks);
    assert.equal(resolveMapData(data, 2020, 9, "observed").blocks, null);
  }
});
test("retains backend block IDs and null coverage without synthesizing values", () => {
  const result = resolveMapData(fixture(), 2020, 9, "observed");
  assert.equal(result.blocks.geojson.features[0].properties.block_id, "TEST-ONLY");
  assert.equal(result.blocks.coverage[0].status, null);
  assert.equal(result.hotspots, null);
  assert.equal(result.aggregates, null);
});
test("NRT requires exact-period confirmed coverage and matching official domain", () => {
  const data = fixture(); data.hotspots = provisional();
  assert.equal(resolveMapData(data, 2020, 9, "provisional").provisionalAvailable, false);
  data.hotspots.coverageConfirmed = true;
  assert.equal(resolveMapData(data, 2020, 9, "provisional").provisionalAvailable, true);
  assert.notEqual(resolveMapData(data, 2020, 9, "provisional").hotspots, null);
  assert.equal(resolveMapData(data, 2020, 10, "provisional").hotspots, null);
  assert.equal(resolveMapData(data, 2020, 10, "provisional").provisionalAvailable, false);
  assert.equal(resolveMapData(data, 2011, 9, "provisional").hotspots, null);
  data.hotspots.boundaryVersion = "unverified";
  assert.equal(resolveMapData(data, 2020, 9, "provisional").provisionalAvailable, false);
});
test("observed geometry cannot appear as estimated or in another period", () => {
  const data = fixture(); data.hotspots = { ...provisional(), layer: "observed" };
  assert.notEqual(resolveMapData(data, 2020, 9, "observed").hotspots, null);
  assert.equal(resolveMapData(data, 2020, 9, "estimated").hotspots, null);
  assert.equal(resolveMapData(data, 2011, 9, "observed").hotspots, null);
  assert.equal(resolveMapData(data, 2020, 8, "observed").hotspots, null);
});
test("camera bounds traverse geometry and do not create a study polygon", () => {
  assert.deepEqual(geometryBounds(geojson), [[0, 0], [1, 1]]);
  assert.equal(geometryBounds({ type: "FeatureCollection", features: [] }), null);
});

test("initial/reset camera resizes first and restores the requested Pará focus", () => {
  const calls = [];
  const map = {
    resize: () => calls.push("resize"),
    stop: () => calls.push("stop"),
    jumpTo: options => calls.push(options),
    fitBounds: () => assert.fail("No boundary means no fabricated fit bounds"),
  };
  focusPara(map, null);
  assert.deepEqual(calls, ["resize", "stop", {
    center: [-52.5, -3.5], zoom: 5.2, bearing: 0, pitch: 0,
    padding: { top: 0, bottom: 0, left: 0, right: 0 },
  }]);
});

test("supplied geometry frames its actual bounds with padding sized to the viewport", () => {
  for (const width of [320, 984]) {
    let fit;
    let resized = false;
    focusPara({
      resize: () => { resized = true; },
      stop: () => {},
      getContainer: () => ({ clientWidth: width, clientHeight: 440 }),
      fitBounds: (bounds, options) => { assert.equal(resized, true); fit = { bounds, options }; },
      jumpTo: () => assert.fail("Geometry takes priority over the fallback camera"),
    }, fixture().boundary);
    assert.deepEqual(fit.bounds, [[0, 0], [1, 1]]);
    assert.equal(fit.options.duration, 0);
    assert.equal(fit.options.absolutePadding, false);
    assert.ok(fit.options.padding.left >= 16);
    assert.ok(fit.options.padding.left + fit.options.padding.right < width);
  }
});
