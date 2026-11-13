import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = join(__dirname, '..');

test('chart data transformations preserve nulls and calculate era aggregates', async () => {
  const statewideRaw = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  const blocksRaw = JSON.parse(readFileSync(join(root, 'public/data/blocks/blocks_summary.json'), 'utf8'));

  assert.strictEqual(statewideRaw.series.length, 228);

  const timeline = statewideRaw.series.map(p => {
    const isHist = p.year < 2012;
    return {
      period: p.period,
      year: p.year,
      month: p.month,
      value: p.value,
      estimatedViirs: isHist && p.estimated_viirs_count !== null ? p.estimated_viirs_count : null,
      observedViirs: !isHist && p.observed_viirs_count !== null ? p.observed_viirs_count : null,
      observedModis: p.observed_modis_count,
      status: p.status,
    };
  });

  // Verify first 6 months of 2002 are null
  for (let m = 1; m <= 6; m++) {
    const pt = timeline.find(p => p.year === 2002 && p.month === m);
    assert.strictEqual(pt.value, null, `2002-0${m} value must be null`);
    assert.strictEqual(pt.estimatedViirs, null, `2002-0${m} estimatedViirs must be null`);
    assert.strictEqual(pt.observedViirs, null, `2002-0${m} observedViirs must be null`);
    assert.strictEqual(pt.status, 'unsupported_period');
  }

  // Verify July 2002 is positive estimated
  const jul02 = timeline.find(p => p.year === 2002 && p.month === 7);
  assert.ok(jul02.value > 0, '2002-07 must be positive');
  assert.strictEqual(jul02.estimatedViirs, jul02.value);
  assert.strictEqual(jul02.observedViirs, null);

  // Verify January 2012 is observed
  const jan12 = timeline.find(p => p.year === 2012 && p.month === 1);
  assert.strictEqual(jan12.status, 'partial_observation');
  assert.ok(jan12.observedViirs > 0);
  assert.strictEqual(jan12.estimatedViirs, null);

  // Test seasonal calculation
  for (let m = 1; m <= 12; m++) {
    const histPoints = timeline.filter(p => p.month === m && p.year >= 2003 && p.year <= 2011 && p.value !== null);
    // Modern points exclude partial observation 2012-01 (Jan 1-19 unobserved)
    const modernPoints = timeline.filter(p => p.month === m && p.year >= 2012 && p.year <= 2020 && p.value !== null && p.status !== 'partial_observation');
    const expectedHistoricalYears = { 2: 5, 3: 2, 4: 1, 5: 6 }[m] ?? 9;
    assert.strictEqual(histPoints.length, expectedHistoricalYears,
      `Month ${m} must count only years with valid complete Day+Night pairs`);
    const expectedModernYears = m === 1 ? 8 : 9;
    assert.strictEqual(modernPoints.length, expectedModernYears, `Month ${m} must have ${expectedModernYears} modern years (Jan 2012 partial excluded)`);
  }

  // Peak fire months (August, September, October) must be vastly higher than wet season (March, April)
  const sepHist = timeline.filter(p => p.month === 9 && p.year >= 2003 && p.year <= 2011).reduce((s, p) => s + p.value, 0) / 9;
  const aprHist = timeline.filter(p => p.month === 4 && p.year >= 2003 && p.year <= 2011).reduce((s, p) => s + p.value, 0) / 9;
  assert.ok(sepHist > 10 * aprHist, 'September historical detections must be >10x April detections in Pará');

  // Verify block summary lookup
  const firstBlockId = Object.keys(blocksRaw.blocks)[0];
  const blockData = blocksRaw.blocks[firstBlockId];
  assert.strictEqual(blockData.values.length, 228);
});
