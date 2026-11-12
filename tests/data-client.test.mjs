import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Compile modules using TypeScript
const compile = (source) => ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
}).outputText;
const asModule = (source) => "data:text/javascript;base64," + Buffer.from(source).toString("base64");

// 1. Compile schemas
const typesSrc = compile(await readFile(new URL("../src/types/scientific-data.ts", import.meta.url), "utf8"))
  .replace('"@/types/explorer"', JSON.stringify(import.meta.resolve("../src/types/explorer.ts")))
  .replace('"zod"', JSON.stringify(import.meta.resolve("zod")));
await import(asModule(typesSrc));

// 2. Compile static adapter
const staticSrc = compile(await readFile(new URL("../src/lib/api/adapters/static-adapter.ts", import.meta.url), "utf8"))
  .replace('"@/types/scientific-data"', JSON.stringify(asModule(typesSrc)));
const { StaticJsonAdapter } = await import(asModule(staticSrc));

// 3. Compile mock adapter
const fixturesSrc = compile(await readFile(new URL("../src/mocks/fixtures.ts", import.meta.url), "utf8"))
  .replace('"@/types/scientific-data"', JSON.stringify(asModule(typesSrc)));
await import(asModule(fixturesSrc));

const mockSrc = compile(await readFile(new URL("../src/lib/api/adapters/mock-adapter.ts", import.meta.url), "utf8"))
  .replace('"@/types/scientific-data"', JSON.stringify(asModule(typesSrc)))
  .replace('"@/mocks/fixtures"', JSON.stringify(asModule(fixturesSrc)));
const { MockAdapter } = await import(asModule(mockSrc));

// 4. Compile live adapter
const liveSrc = compile(await readFile(new URL("../src/lib/api/adapters/live-adapter.ts", import.meta.url), "utf8"))
  .replace('"@/types/scientific-data"', JSON.stringify(asModule(typesSrc)));
const { LiveApiAdapter } = await import(asModule(liveSrc));

// -----------------------------------------------------------------------------
// TESTS
// -----------------------------------------------------------------------------

test("StaticJsonAdapter loads real scientific data and passes Zod schema validation", async () => {
  const adapter = new StaticJsonAdapter();
  assert.equal(adapter.mode, "static");
  assert.equal(adapter.isSynthetic, false);

  const tsData = await adapter.getStatewideTimeSeries();
  assert.equal(tsData.regionId, "BR-PA");
  assert.equal(tsData.series.length, 228);
  assert.equal(tsData.provenance.total_observed_viirs, 2196531);
  assert.equal(tsData.provenance.total_observed_modis, 344071);

  const calData = await adapter.getCalendarMatrix();
  assert.equal(calData.regionId, "BR-PA");
  assert.equal(calData.years.length, 19);

  const blocksData = await adapter.getBlocksSummary();
  assert.equal(blocksData.regionId, "BR-PA");
  assert.equal(Object.keys(blocksData.blocks).length, 568);

  const metricsData = await adapter.getModelMetrics();
  assert.equal(metricsData.modelVersion, "firechronicle-nb2-v1.0");
  assert.equal(metricsData.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.mae, 35.4374);
  assert.equal(metricsData.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.meanPoissonDeviance, 25.0056);
});

test("MockAdapter returns synthetic fixtures stamped as DEVELOPMENT / SYNTHETIC", async () => {
  const adapter = new MockAdapter();
  assert.equal(adapter.mode, "mock");
  assert.equal(adapter.isSynthetic, true);

  const tsData = await adapter.getStatewideTimeSeries();
  assert.equal(tsData.provenance.model_version, "firechronicle-nb2-v1.0-MOCK");
  assert.ok(tsData.provenance.partial_month_notice.includes("DEVELOPMENT / SYNTHETIC"));

  const metrics = await adapter.getModelMetrics();
  assert.ok(metrics.scientificLimitations[0].includes("DEVELOPMENT / SYNTHETIC"));
});

test("LiveApiAdapter never silently falls back to synthetic data on failure", async () => {
  // Point to a non-existent port to simulate network failure
  const adapter = new LiveApiAdapter("http://127.0.0.1:54321");
  assert.equal(adapter.mode, "live");
  assert.equal(adapter.isSynthetic, false);

  await assert.rejects(
    async () => {
      await adapter.getStatewideTimeSeries();
    },
    (err) => {
      assert.ok(err instanceof Error);
      assert.ok(err.message.includes("Live API network failure") || err.message.includes("fetch failed"));
      // Crucial: Must NOT return mock data or synthetic flag!
      return true;
    }
  );
});
