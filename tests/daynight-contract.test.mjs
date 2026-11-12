import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = join(__dirname, '..');

test('Priority 1: Backend daynight=ALL contract reconciliation', async (t) => {
  const tsRaw = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  const blocksRaw = JSON.parse(readFileSync(join(root, 'public/data/blocks/blocks_summary.json'), 'utf8'));
  const calRaw = JSON.parse(readFileSync(join(root, 'public/data/calendar/calendar_matrix.json'), 'utf8'));
  const mapLookup = JSON.parse(readFileSync(join(root, 'public/data/geo/period_block_values.json'), 'utf8'));

  await t.test('1. Statewide provenance matches official audited pass breakdown', () => {
    const prov = tsRaw.provenance;
    assert.strictEqual(prov.total_historical_expected_passes, 129504, '114 months * 568 blocks * 2 passes = 129,504 expected passes');
    assert.strictEqual(prov.total_historical_available_estimates, 26962, 'Total non-null passes must be exactly 26,962');
    assert.strictEqual(prov.total_historical_missing_estimates, 102542, 'Total missing passes must be exactly 102,542');
    assert.strictEqual(prov.total_historical_complete_pair_block_months, 6516, 'Exactly 6,516 block-months with both D and N passes');
    assert.strictEqual(prov.total_historical_single_pass_block_months, 13930, 'Exactly 13,930 block-months with single pass');
    assert.strictEqual(prov.total_historical_zero_pass_block_months, 44306, 'Exactly 44,306 block-months with zero passes');
    assert.strictEqual(prov.total_historical_estimated_viirs, 2874515.5, 'Strict ALL statewide historical sum must be 2,874,515.5');
    assert.strictEqual(prov.total_historical_available_passes_sum, 3557995.8, 'Available-pass statewide historical sum must be 3,557,995.8');
    assert.ok(prov.aggregation_rule.includes('strict daynight=ALL'), 'Aggregation rule must document strict daynight=ALL');
  });

  await t.test('2. Statewide monthly series uses strict ALL as primary value while preserving available passes', () => {
    const histMonths = tsRaw.series.filter(s => s.year < 2012 && s.status === 'ok');
    assert.strictEqual(histMonths.length, 114, '114 historical operational months (2002-07 to 2011-12)');

    let sumStrict = 0;
    let sumAvail = 0;
    let sumCompletePairs = 0;
    let sumSinglePasses = 0;

    for (const m of histMonths) {
      assert.strictEqual(m.value, m.strict_both_passes_value, `Month ${m.period}: primary value must match strict_both_passes_value`);
      assert.ok(m.available_passes_value >= m.strict_both_passes_value, `Month ${m.period}: available pass sum must be >= strict sum`);
      assert.strictEqual(typeof m.complete_pairs_count, 'number');
      assert.strictEqual(typeof m.single_pass_count, 'number');

      sumStrict += m.value;
      sumAvail += m.available_passes_value;
      sumCompletePairs += m.complete_pairs_count;
      sumSinglePasses += m.single_pass_count;
    }

    assert.strictEqual(sumCompletePairs, 6516, 'Sum of complete pairs must be 6,516');
    assert.strictEqual(sumSinglePasses, 13930, 'Sum of single passes must be 13,930');
    assert.ok(Math.abs(sumStrict - 2874515.5) < 1.0, `Sum of strict monthly values (${sumStrict.toFixed(1)}) must match ~2,874,515.5`);
    assert.ok(Math.abs(sumAvail - 3557995.8) < 1.0, `Sum of available pass monthly values (${sumAvail.toFixed(1)}) must match ~3,557,995.8`);
  });

  await t.test('3. Block-level strict ALL contract: single-pass months are NULL, complete pairs are non-null', () => {
    const blocks = blocksRaw.blocks;
    assert.strictEqual(Object.keys(blocks).length, 568, 'All 568 canonical blocks must be present');

    let totalStrictBlockSum = 0;
    let totalAvailBlockSum = 0;
    let nullCountHist = 0;
    let positiveCountHist = 0;

    // First 114 operational months correspond to indices 6 through 119 (index 0-5 are 2002-01 to 2002-06 unsupported)
    for (const bId of Object.keys(blocks)) {
      const b = blocks[bId];
      assert.strictEqual(b.hist_sum, b.hist_strict_sum, `Block ${bId}: hist_sum must represent hist_strict_sum`);
      assert.ok(b.hist_available_sum >= b.hist_strict_sum, `Block ${bId}: available sum must be >= strict sum`);

      totalStrictBlockSum += b.hist_strict_sum;
      totalAvailBlockSum += b.hist_available_sum;

      for (let idx = 6; idx < 120; idx++) {
        const val = b.values[idx];
        if (val === null) {
          nullCountHist++;
        } else {
          positiveCountHist++;
          assert.ok(val > 0, `Block ${bId} month idx ${idx}: positive count expected`);
        }
      }
    }

    // Exactly 6,516 block-months have both passes, exactly 13,930 + 44,306 = 58,236 have < 2 passes
    assert.strictEqual(positiveCountHist, 6516, 'Exactly 6,516 historical block-months must be non-null under strict ALL');
    assert.strictEqual(nullCountHist, 58236, 'Exactly 58,236 historical block-months must be NULL (13,930 single-pass + 44,306 zero-pass)');
    assert.ok(Math.abs(totalStrictBlockSum - 2874515.5) < 1.0, `Sum of block strict sums (${totalStrictBlockSum.toFixed(1)}) must match ~2,874,515.5`);
    assert.ok(Math.abs(totalAvailBlockSum - 3557995.8) < 1.0, `Sum of block available sums (${totalAvailBlockSum.toFixed(1)}) must match ~3,557,995.8`);
  });

  await t.test('4. Map period lookup reflects strict ALL: single-pass blocks are NOT present (neutral/uncolored)', () => {
    const periods = blocksRaw.periods;
    // Check historical periods
    for (let idx = 6; idx < 120; idx++) {
      const p = periods[idx];
      const periodMap = mapLookup[p] || {};
      const blockCountInMap = Object.keys(periodMap).length;

      // In statewide time series, complete_pairs_count tells us how many blocks have complete pairs
      const tsMonth = tsRaw.series[idx];
      assert.strictEqual(blockCountInMap, tsMonth.complete_pairs_count, `Period ${p}: map should contain exactly ${tsMonth.complete_pairs_count} blocks`);
    }
  });

  await t.test('5. Calendar matrix mirrors statewide strict ALL values', () => {
    for (const yrRow of calRaw.years) {
      for (const mItem of yrRow.months) {
        const tsMatch = tsRaw.series.find(s => s.period === mItem.period);
        assert.ok(tsMatch, `Calendar item ${mItem.period} must exist in timeseries`);
        assert.strictEqual(mItem.value, tsMatch.value, `Calendar value for ${mItem.period} must match timeseries value`);
        assert.strictEqual(mItem.status, tsMatch.status, `Calendar status for ${mItem.period} must match timeseries status`);
      }
    }
  });
});
