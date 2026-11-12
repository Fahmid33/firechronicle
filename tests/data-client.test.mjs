import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Compile modules using TypeScript
const compile = (source) => ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
}).outputText;
const asModule = (source) => "data:text/javascript;base64," + Buffer.from(source).toString("base64");

// 1. Compile schemas & explorer types
const explorerSrc = compile(await readFile(new URL("../src/types/explorer.ts", import.meta.url), "utf8"));
const explorerModule = asModule(explorerSrc);

const typesSrc = compile(await readFile(new URL("../src/types/scientific-data.ts", import.meta.url), "utf8"))
  .replace('"@/types/explorer"', JSON.stringify(explorerModule))
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
  .replace('"@/types/scientific-data"', JSON.stringify(asModule(typesSrc)))
  .replace('"@/types/explorer"', JSON.stringify(explorerModule));
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

test("LiveApiAdapter transforms documented backend /harmonized and /summary responses", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/api/v1/harmonized")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            region_id: "BR-PA",
            items: [
              {
                year: 2002,
                month: 7,
                period: "2002-07",
                estimated_viirs_count: 3462.9,
                value_type: "estimated",
                prediction_status: "ok_preliminary",
                measurement_unit: "VIIRS_S-NPP-equivalent_detection_count",
              },
              {
                year: 2012,
                month: 1,
                period: "2012-01",
                observed_viirs_count: 445,
                value_type: "observed",
                prediction_status: "partial_observation",
                measurement_unit: "VIIRS_S-NPP-equivalent_detection_count",
              },
              {
                year: 2020,
                month: 12,
                period: "2020-12",
                observed_viirs_count: 12345,
                value_type: "observed",
                prediction_status: "ok",
                measurement_unit: "VIIRS_S-NPP-equivalent_detection_count",
              },
            ],
          }),
        };
      }
      if (u.includes("/api/v1/summary")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            region_id: "BR-PA",
            model_version: "firechronicle-nb2-v1.0",
            total_observed_viirs: 2196531,
            total_observed_modis: 344071,
            clean_period_observed_viirs: 2196086,
            clean_period_observed_modis: 343528,
            total_historical_estimated_viirs: 2874515.5,
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "Not Found" };
    };

    const adapter = new LiveApiAdapter("http://localhost:8000");
    const tsData = await adapter.getStatewideTimeSeries();

    assert.equal(tsData.regionId, "BR-PA");
    assert.equal(tsData.series.length, 3);
    assert.equal(tsData.series[0].value, 3462.9);
    assert.equal(tsData.series[0].value_type, "estimated");
    assert.equal(tsData.series[0].status, "ok");
    assert.equal(tsData.series[1].value, 445);
    assert.equal(tsData.series[1].status, "partial_observation");
    assert.equal(tsData.series[2].value, 12345);
    assert.equal(tsData.series[2].status, "ok");
    assert.equal(tsData.provenance.model_version, "firechronicle-nb2-v1.0");
    assert.equal(tsData.provenance.total_observed_viirs, 2196531);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("LiveApiAdapter constructs CalendarMatrixPayload from monthly time series", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/api/v1/harmonized")) {
        // Return 12 months for 2012
        const items = [];
        for (let m = 1; m <= 12; m++) {
          items.push({
            year: 2012,
            month: m,
            period: `2012-${String(m).padStart(2, "0")}`,
            observed_viirs_count: m === 1 ? 445 : 1000 * m,
            value_type: "observed",
            prediction_status: m === 1 ? "partial_observation" : "ok",
          });
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ region_id: "BR-PA", items }),
        };
      }
      if (u.includes("/api/v1/summary")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ region_id: "BR-PA" }),
        };
      }
      return { ok: false, status: 404, text: async () => "Not Found" };
    };

    const adapter = new LiveApiAdapter("http://localhost:8000");
    const calData = await adapter.getCalendarMatrix();

    assert.equal(calData.regionId, "BR-PA");
    assert.equal(calData.years.length, 1);
    assert.equal(calData.years[0].year, 2012);
    assert.equal(calData.years[0].months.length, 12);
    assert.equal(calData.years[0].months[0].status, "partial_observation");
    assert.equal(calData.years[0].months[1].status, "ok");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("LiveApiAdapter documents multi-decadal block summary limitation", async () => {
  const adapter = new LiveApiAdapter("http://localhost:8000");
  await assert.rejects(
    async () => {
      await adapter.getBlocksSummary();
    },
    (err) => {
      assert.ok(err instanceof Error);
      assert.ok(err.message.includes("LiveApiAdapter limitation: Multi-decadal 228-month block time series"));
      assert.ok(err.message.includes("NEXT_PUBLIC_DATA_MODE=static"));
      return true;
    }
  );
});

test("LiveApiAdapter transforms documented backend /model-info and /sensor-lab/metrics responses", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/api/v1/model-info")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            region_id: "BR-PA",
            model_version: "firechronicle-nb2-v1.0",
            architecture: {
              family: "Generalized Linear Model (GLM)",
              distribution: "Negative Binomial (NB2)",
              link: "log",
              dispersion_alpha: 0.3394,
              baseline_ratio_multiplier_k: 6.0538,
            },
            training_provenance: {
              calibration_dataset: "2012-2020 Real Observed Overlap",
              training_records_count: 23010,
              paired_modis_total: 342397,
              paired_viirs_total: 2072819,
            },
          }),
        };
      }
      if (u.includes("/api/v1/sensor-lab/metrics")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            region_id: "BR-PA",
            official_evaluation_metrics: {
              strategy_A_temporal_holdout: {
                title: "Strategy A: Temporal Holdout (2019-2020)",
                description: "Temporal holdout evaluation",
                sample_size: 5091,
                nb2: {
                  mae: 35.4374,
                  medae: 13.6789,
                  rmse: 84.5314,
                  mean_poisson_deviance: 25.0056,
                  aggregate_bias_pct: -11.5,
                  monthly_correlation: 0.9772,
                  dispersion_alpha: 0.329,
                },
                baseline_ratio: {
                  mae: 44.9884,
                  medae: 16.4782,
                  rmse: 104.9943,
                  mean_poisson_deviance: 55.3136,
                  aggregate_bias_pct: -12.9,
                  monthly_correlation: 0.9854,
                  fitted_k: 6.0538,
                },
                comparison: {
                  mae_reduction: 9.551,
                  deviance_reduction: 30.308,
                },
              },
              strategy_B_geographic_holdout: {
                title: "Strategy B: Geographic Holdout",
                description: "Geographic holdout evaluation",
                sample_size: 5147,
                nb2: {
                  mae: 35.7909,
                  medae: 14.12,
                  rmse: 85.12,
                  mean_poisson_deviance: 20.95,
                  aggregate_bias_pct: -10.2,
                  monthly_correlation: 0.965,
                  dispersion_alpha: 0.335,
                },
                baseline_ratio: {
                  mae: 53.87,
                  medae: 18.23,
                  rmse: 112.45,
                  mean_poisson_deviance: 56.35,
                  aggregate_bias_pct: -14.1,
                  monthly_correlation: 0.97,
                  fitted_k: 6.0538,
                },
                comparison: {
                  mae_reduction: 18.0791,
                  deviance_reduction: 35.4,
                },
              },
            },
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "Not Found" };
    };

    const adapter = new LiveApiAdapter("http://localhost:8000");
    const metricsData = await adapter.getModelMetrics();

    assert.equal(metricsData.modelVersion, "firechronicle-nb2-v1.0");
    assert.equal(metricsData.architecture.dispersionAlpha, 0.3394);
    assert.equal(metricsData.trainingProvenance.trainingRecordsCount, 23010);
    assert.equal(metricsData.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.mae, 35.4374);
    assert.equal(metricsData.officialEvaluationMetrics.strategy_B_geographic_holdout.nb2.mae, 35.7909);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("LiveApiAdapter queries /spatial with separate year, month, resolution, region_id, and daynight parameters", async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = "";
  try {
    globalThis.fetch = async (url) => {
      interceptedUrl = String(url);
      return {
        ok: true,
        status: 200,
        json: async () => ({ type: "FeatureCollection", features: [] }),
      };
    };

    const adapter = new LiveApiAdapter("http://localhost:8000");
    await adapter.getSpatial({
      year: 2020,
      month: 9,
      resolution: "50km",
      regionId: "BR-PA",
      daynight: "ALL",
    });

    assert.ok(interceptedUrl.includes("/api/v1/spatial?"));
    assert.ok(interceptedUrl.includes("year=2020"));
    assert.ok(interceptedUrl.includes("month=9"));
    assert.ok(interceptedUrl.includes("resolution=50km"));
    assert.ok(interceptedUrl.includes("region_id=BR-PA"));
    assert.ok(interceptedUrl.includes("daynight=ALL"));
    // Crucial: Ensure unsupported 'period' parameter is NOT used
    assert.ok(!interceptedUrl.includes("period="), "Must not use unsupported period parameter");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
