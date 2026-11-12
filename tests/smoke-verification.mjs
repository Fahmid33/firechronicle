import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = join(__dirname, '..');

test('complete frontend asset and scientific data smoke verification', async () => {
  // 1. Verify all 4 routes have prerendered static pages in .next/server/app
  const routes = ['index.html', 'time-machine.html', 'sensor-lab.html', 'methodology.html'];
  const appBuildDir = join(root, '.next/server/app');

  if (existsSync(appBuildDir)) {
    for (const r of routes) {
      const pagePath = join(appBuildDir, r);
      assert.ok(existsSync(pagePath), `Route prerender must exist: ${r}`);
      const content = readFileSync(pagePath, 'utf8');
      assert.ok(content.length > 500, `Page content must be non-empty for ${r}`);
    }
  }

  // 2. Verify all static JSON scientific files exist and are non-empty
  const jsonFiles = [
    'public/data/geo/para_boundary.json',
    'public/data/geo/para_50km_blocks.json',
    'public/data/timeseries/statewide_monthly.json',
    'public/data/calendar/calendar_matrix.json',
    'public/data/blocks/blocks_summary.json',
    'public/data/sensor_lab/model_metrics.json',
  ];

  for (const f of jsonFiles) {
    const fullPath = join(root, f);
    assert.ok(existsSync(fullPath), `Static file must exist: ${f}`);
    const data = JSON.parse(readFileSync(fullPath, 'utf8'));
    assert.ok(data, `Must be valid JSON: ${f}`);
  }

  // 3. Verify Boundary details
  const boundary = JSON.parse(readFileSync(join(root, 'public/data/geo/para_boundary.json'), 'utf8'));
  assert.strictEqual(boundary.regionId, 'BR-PA');
  assert.strictEqual(boundary.approvedByDataOwner, true);
  assert.strictEqual(boundary.version, 'IBGE-PA-UF-2024-v1.0');
  assert.strictEqual(boundary.geojson.type, 'FeatureCollection');
  assert.strictEqual(boundary.geojson.features[0].geometry.type, 'MultiPolygon');
  assert.strictEqual(boundary.geojson.features[0].geometry.coordinates.length, 35);

  // 4. Verify Canonical 50 km Blocks
  const blocks = JSON.parse(readFileSync(join(root, 'public/data/geo/para_50km_blocks.json'), 'utf8'));
  assert.strictEqual(blocks.regionId, 'BR-PA');
  assert.strictEqual(blocks.geojson.features.length, 568);
  assert.strictEqual(blocks.calibrationScaleKm, 50);

  // 5. Verify Statewide Time Series
  const statewide = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  assert.strictEqual(statewide.series.length, 228);
  assert.strictEqual(statewide.series[0].period, '2002-01');
  assert.strictEqual(statewide.series[0].status, 'unsupported_period');
  assert.strictEqual(statewide.series[0].value, null);
  assert.strictEqual(statewide.series[227].period, '2020-12');
  assert.strictEqual(statewide.series[227].value_type, 'observed');

  // 6. Verify Model Metrics
  const metrics = JSON.parse(readFileSync(join(root, 'public/data/sensor_lab/model_metrics.json'), 'utf8'));
  assert.strictEqual(metrics.modelVersion, 'firechronicle-nb2-v1.0');
  assert.strictEqual(metrics.officialEvaluationMetrics.strategy_A_temporal_holdout.nb2.mae, 35.4374);
  assert.strictEqual(metrics.officialEvaluationMetrics.strategy_B_geographic_holdout.nb2.mae, 35.7903);
});
