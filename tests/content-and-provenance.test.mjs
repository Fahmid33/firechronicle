import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = join(__dirname, '..');

test('Methodology page content accurately reflects connected scientific data and boundaries', () => {
  const methPath = join(root, 'src/app/methodology/page.tsx');
  const content = readFileSync(methPath, 'utf8');

  // Verify outdated claims are removed
  assert.ok(!content.includes('Boundary assets are still pending'), 'Must not claim boundary assets are pending');
  assert.ok(!content.includes('The model card and validation results have not yet been connected'), 'Must not claim model card not connected');
  assert.ok(!content.includes('This interface currently displays no scientific records'), 'Must not claim no scientific records');
  assert.ok(!content.includes('Negative Binomial is a candidate'), 'Must not claim NB is only a candidate');

  // Verify authoritative statements are present
  assert.ok(content.includes('PA_UF_2024.zip'), 'Must cite IBGE 2024 boundary zip');
  assert.ok(content.includes('EPSG:6933, Lambert Cylindrical Equal Area'), 'Must cite EPSG:6933 Lambert Cylindrical Equal Area');
  assert.ok(content.includes('568 canonical blocks'), 'Must cite 568 canonical blocks');
  assert.ok(content.includes('firechronicle-nb2-v1.0'), 'Must cite production model version firechronicle-nb2-v1.0');
  assert.ok(content.includes('NEXT_PUBLIC_DATA_MODE=static'), 'Must cite static demonstration mode');
  assert.ok(content.includes('LiveApiAdapter'), 'Must cite LiveApiAdapter integration status');
  assert.ok(content.includes('daynight=ALL'), 'Must document strict daynight=ALL contract');

  // Verify authoritative metrics directly matching validation_metrics_final_nb2.json
  assert.ok(content.includes('20.95'), 'Must cite authoritative geographic holdout Poisson deviance 20.95');
  assert.ok(content.includes('25.01'), 'Must cite authoritative temporal holdout Poisson deviance 25.01');
  assert.ok(content.includes('0.994'), 'Must cite authoritative geographic holdout correlation 0.994');
  assert.ok(!content.includes('11.23'), 'Must not cite obsolete deviance 11.23');
  assert.ok(!content.includes('0.887'), 'Must not cite obsolete R2 0.887');
});

test('Status labels throughout UI distinguish verified data from pending layers', () => {
  // 1. src/app/page.tsx
  const pageContent = readFileSync(join(root, 'src/app/page.tsx'), 'utf8');
  assert.ok(!pageContent.includes('Awaiting scientific data'), 'Page must not say Awaiting scientific data');
  assert.ok(pageContent.includes('Precomputed static data (2002–2020)'), 'Page must show verified precomputed static data badge');

  // 2. src/components/layout/dashboard-shell.tsx
  const shellContent = readFileSync(join(root, 'src/components/layout/dashboard-shell.tsx'), 'utf8');
  assert.ok(!shellContent.includes('Scientific data integration pending'), 'Footer must not say data integration pending');
  assert.ok(shellContent.includes('Static demo mode (live API backend integration pending)'), 'Footer must state static demo mode with live backend pending');

  // 3. src/types/explorer.ts
  const expContent = readFileSync(join(root, 'src/types/explorer.ts'), 'utf8');
  assert.ok(!expContent.includes('Pending observed geometry'), 'Explorer types must not say Pending observed geometry');
  assert.ok(expContent.includes('50 km canonical grid blocks (point locations pending live API)'), 'Observed scale must cite 50 km canonical grid blocks');
  assert.ok(expContent.includes('Unconnected NRT layer (requires live API)'), 'Provisional scale must cite unconnected NRT layer');

  // 4. src/components/calendar/period-controls.tsx
  const pcContent = readFileSync(join(root, 'src/components/calendar/period-controls.tsx'), 'utf8');
  assert.ok(!pcContent.includes('Explore time. Availability pending.'), 'Period controls must not say Availability pending');
  assert.ok(pcContent.includes('2002–2020 verified archive · 2021+ pending data'), 'Period controls must state 2002-2020 verified archive');

  // 5. src/components/map/layer-controls.tsx
  const lcContent = readFileSync(join(root, 'src/components/map/layer-controls.tsx'), 'utf8');
  assert.ok(!lcContent.includes('{LAYERS[key].source} · availability pending'), 'Layer controls must not say generic availability pending');
  assert.ok(lcContent.includes('Historical Aqua MODIS → NB2 v1.0 · precomputed 50 km estimates connected'), 'Estimated layer description must cite connected estimates');
  assert.ok(lcContent.includes('VIIRS S-NPP · verified 2012–2020 archive connected'), 'Observed layer description must cite connected archive');

  // 6. src/components/map/map-workspace.tsx
  const mwContent = readFileSync(join(root, 'src/components/map/map-workspace.tsx'), 'utf8');
  assert.ok(mwContent.includes('Quantitative choropleth active'), 'Map workspace must confirm active quantitative choropleth when compatible');

  // 7. src/components/calendar/calendar-shell.tsx
  const csContent = readFileSync(join(root, 'src/components/calendar/calendar-shell.tsx'), 'utf8');
  assert.ok(csContent.includes('Partial Observation / Commissioning (Jul 2002 & Jan 2012)'), 'Calendar legend must include Jul 2002 & Jan 2012');
});

test('August 2005 historical coverage terminology and counts are strictly verified', () => {
  const statewideRaw = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  const aug05 = statewideRaw.series.find(s => s.period === '2005-08');

  assert.ok(aug05, 'August 2005 record must exist in statewide monthly series');
  assert.strictEqual(aug05.expected_passes, 1136, 'Expected passes must be exactly 1,136 (568 blocks * 2)');
  assert.strictEqual(aug05.available_estimates_count, 517, 'Available estimates count must be 517');
  assert.strictEqual(aug05.complete_pairs_count, 177, 'Complete Day+Night pairs must be 177');
  assert.strictEqual(aug05.single_pass_count, 163, 'Single-pass count must be 163');
  assert.strictEqual(aug05.value, 161940.5, 'Strict ALL statewide value must be 161,940.5');
  assert.strictEqual(aug05.available_passes_value, 169376.6, 'Available passes statewide sum must be 169,376.6');

  // Mathematical consistency and terminology
  assert.strictEqual(aug05.complete_pairs_count * 2 + aug05.single_pass_count, aug05.available_estimates_count, '177*2 + 163 must equal 517 passes');
  assert.strictEqual(aug05.complete_pairs_count + aug05.single_pass_count + 228, 568, '177 + 163 + 228 must equal 568 total blocks');
  assert.ok(aug05.completeness_notice.includes('228 blocks with no available estimated passes; observation coverage unknown'), 'August 2005 completeness notice must explicitly document 228 blocks with no available estimated passes');
  assert.ok(!aug05.completeness_notice.includes('zero detections'), 'Must not describe unobserved blocks as zero detections');
});

test('July 2002 and January 2012 partial status and values are synchronized in calendar and statewide series', () => {
  const statewideRaw = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  const calendarRaw = JSON.parse(readFileSync(join(root, 'public/data/calendar/calendar_matrix.json'), 'utf8'));

  // July 2002
  const swJul02 = statewideRaw.series.find(s => s.period === '2002-07');
  assert.ok(swJul02);
  assert.strictEqual(swJul02.status, 'partial_observation', 'July 2002 statewide status must be partial_observation');
  assert.strictEqual(swJul02.value, 3462.9, 'July 2002 statewide value must be 3,462.9');
  assert.strictEqual(swJul02.complete_pairs_count, 37, 'July 2002 must have 37 complete pairs');
  assert.strictEqual(swJul02.single_pass_count, 170, 'July 2002 must have 170 single-pass blocks');

  const cal2002 = calendarRaw.years.find(y => y.year === 2002);
  const calJul02 = cal2002?.months.find(m => m.period === '2002-07');
  assert.ok(calJul02);
  assert.strictEqual(calJul02.status, 'partial_observation', 'July 2002 calendar status must be partial_observation');
  assert.strictEqual(calJul02.value, 3462.9, 'July 2002 calendar value must be 3,462.9');

  // January 2012
  const swJan12 = statewideRaw.series.find(s => s.period === '2012-01');
  assert.ok(swJan12);
  assert.strictEqual(swJan12.status, 'partial_observation', 'January 2012 statewide status must be partial_observation');
  assert.strictEqual(swJan12.value, 445.0, 'January 2012 statewide value must be 445.0');

  const cal2012 = calendarRaw.years.find(y => y.year === 2012);
  const calJan12 = cal2012?.months.find(m => m.period === '2012-01');
  assert.ok(calJan12);
  assert.strictEqual(calJan12.status, 'partial_observation', 'January 2012 calendar status must be partial_observation');
  assert.strictEqual(calJan12.value, 445.0, 'January 2012 calendar value must be 445.0');
});

test('AnalysisPanel coverage semantics distinguish complete pairs from incomplete/unobserved estimates', () => {
  const panelPath = join(root, 'src/components/layout/analysis-panel.tsx');
  const content = readFileSync(panelPath, 'utf8');

  // Verify block-level incomplete status
  assert.ok(content.includes('Incomplete D/N estimates; combined value unavailable'), 'Must use truthful combined status for block-level nulls');
  assert.ok(content.includes('Complete D+N estimate'), 'Must label non-null block estimates as complete D+N estimate');

  // Verify statewide provenance distinguishes complete pairs, single-pass, and unobserved blocks
  assert.ok(content.includes('complete Day+Night pairs'), 'Must report complete Day+Night pairs');
  assert.ok(content.includes('single-pass'), 'Must report single-pass blocks');
  assert.ok(content.includes('blocks with no available estimated passes; observation coverage unknown'), 'Must report unobserved blocks accurately');
});
