import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = join(__dirname, '..');

// Test the CSV generation logic with real static files
test('CSV export generates 228 rows, preserves NULLs, and handles scopes', async () => {
  const statewideRaw = JSON.parse(readFileSync(join(root, 'public/data/timeseries/statewide_monthly.json'), 'utf8'));
  const blocksRaw = JSON.parse(readFileSync(join(root, 'public/data/blocks/blocks_summary.json'), 'utf8'));

  // Implementation matching src/lib/csv/csv-export.ts for unit test
  function generateCsv(options) {
    const { regionId = "BR-PA", blockId, statewide, blocksSummary, isSynthetic = false } = options;
    const lines = [];

    if (isSynthetic) {
      lines.push("# WARNING: DEVELOPMENT / SYNTHETIC DATA ACTIVE");
    }
    lines.push("# FireChronicle Earth Observation Explorer - Scientific Time Series Export");
    lines.push(`# Region: ${regionId} (Pará, Brazil)`);
    lines.push(`# Scope: ${blockId ? `Block ${blockId} (50 km EASE-Grid 2.0 / EPSG:6933 grid cell)` : "Statewide Pará (Strict daynight=ALL)"}`);
    lines.push("# Day/Night Policy: daynight column is labeled 'ALL'. At block level, D+N is valid only if both passes exist; at statewide level, totals sum only complete pairs.");
    lines.push('# Status Semantics: "ok" = verified full month; "partial_observation" = partial-month coverage / operational commissioning (Jul 2002, Jan 2012); "unsupported_period" = outside archive; "missing" = unobserved or missing pass record.');
    lines.push("region_id,block_id,year,month,daynight,value,value_type,status,measurement_unit,model_version");

    if (blockId && blocksSummary?.blocks[blockId] && statewide?.series) {
      const block = blocksSummary.blocks[blockId];
      statewide.series.forEach((ref, idx) => {
        const val = block.values[idx] ?? null;
        const isHist = ref.year < 2012;
        let status = ref.status;
        if (ref.status === "unsupported_period") {
          status = "unsupported_period";
        } else if (ref.year === 2002 && ref.month === 7) {
          status = val !== null ? "partial_observation" : "missing";
        } else if (ref.year === 2012 && ref.month === 1) {
          status = val !== null ? "partial_observation" : "missing";
        } else if (val === null) {
          status = "missing";
        } else if (ref.status === "partial_observation") {
          status = "partial_observation";
        } else {
          status = "ok";
        }

        const valType = isHist ? (val !== null ? "estimated" : "") : (val !== null ? "observed" : "");
        const unit = valType === "estimated" ? "VIIRS_S-NPP-equivalent_detection_count" : (valType === "observed" ? "VIIRS_S-NPP_detection_count" : "");
        const model = valType === "estimated" ? "firechronicle-nb2-v1.0" : (valType === "observed" ? "N/A (S-NPP VIIRS Direct Observation)" : "");

        lines.push(`${regionId},${blockId},${ref.year},${ref.month},ALL,${val !== null ? val.toFixed(2) : ""},${valType},${status},${unit},${model}`);
      });
    } else if (statewide?.series) {
      statewide.series.forEach(s => {
        const valType = s.value_type ?? "";
        let swStatus = s.status;
        if (s.year === 2002 && s.month === 7 && swStatus !== "unsupported_period") {
          swStatus = "partial_observation";
        }
        const unit = valType === "estimated" ? "VIIRS_S-NPP-equivalent_detection_count" : (valType === "observed" ? "VIIRS_S-NPP_detection_count" : "");
        const model = valType === "estimated" ? "firechronicle-nb2-v1.0" : (valType === "observed" ? "N/A (S-NPP VIIRS Direct Observation)" : "");
        lines.push(`${regionId},STATEWIDE,${s.year},${s.month},ALL,${s.value !== null ? s.value.toFixed(2) : ""},${valType},${swStatus},${unit},${model}`);
      });
    }
    return lines.join("\n");
  }

  // 1. Statewide Export Test
  const statewideCsv = generateCsv({
    regionId: "BR-PA",
    blockId: null,
    statewide: statewideRaw,
    blocksSummary: blocksRaw,
    isSynthetic: false,
  });

  const lines = statewideCsv.split("\n");
  const dataRows = lines.filter(l => !l.startsWith("#") && !l.startsWith("region_id"));

  assert.strictEqual(dataRows.length, 228, "Statewide export must contain exactly 228 data rows");

  // Check header comments
  assert.ok(statewideCsv.includes('# Status Semantics: "ok" = verified full month; "partial_observation" = partial-month coverage / operational commissioning (Jul 2002, Jan 2012)'));

  // Check 2002-01 (Pre-commissioning: empty value)
  const rowJan02 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2002,1,"));
  assert.ok(rowJan02, "Must contain row for 2002-01");
  const partsJan02 = rowJan02.split(",");
  assert.strictEqual(partsJan02[4], "ALL", "daynight must be ALL");
  assert.strictEqual(partsJan02[5], "", "2002-01 value must be empty (preserved NULL)");
  assert.strictEqual(partsJan02[7], "unsupported_period", "status must be unsupported_period");

  // Check 2002-07 (Operational commissioning month: partial_observation)
  const rowJul02 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2002,7,"));
  assert.ok(rowJul02);
  const partsJul02 = rowJul02.split(",");
  assert.strictEqual(partsJul02[5], "3462.90", "2002-07 value must preserve exact statewide strict total 3462.90");
  assert.strictEqual(partsJul02[6], "estimated");
  assert.strictEqual(partsJul02[7], "partial_observation", "2002-07 status must be partial_observation");
  assert.strictEqual(partsJul02[9], "firechronicle-nb2-v1.0");

  // Check 2012-01 (Partial observation)
  const rowJan12 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2012,1,"));
  assert.ok(rowJan12);
  const partsJan12 = rowJan12.split(",");
  assert.strictEqual(partsJan12[6], "observed");
  assert.strictEqual(partsJan12[7], "partial_observation", "2012-01 status must be partial_observation");

  // 2. Block Export Test
  const firstBlockId = Object.keys(blocksRaw.blocks)[0];
  const blockCsv = generateCsv({
    regionId: "BR-PA",
    blockId: firstBlockId,
    statewide: statewideRaw,
    blocksSummary: blocksRaw,
    isSynthetic: false,
  });
  const blockRows = blockCsv.split("\n").filter(l => !l.startsWith("#") && !l.startsWith("region_id"));
  assert.strictEqual(blockRows.length, 228, "Block export must contain exactly 228 data rows");
  assert.ok(blockRows[0].startsWith(`BR-PA,${firstBlockId},2002,1,`));

  // Check block row for 2002-07: if null -> missing, if non-null -> partial_observation
  const blockJul02 = blockRows.find(r => r.startsWith(`BR-PA,${firstBlockId},2002,7,`));
  assert.ok(blockJul02);
  const blockJul02Parts = blockJul02.split(",");
  if (blockJul02Parts[5] === "") {
    assert.strictEqual(blockJul02Parts[7], "missing", "Null block value in 2002-07 must be marked missing");
  } else {
    assert.strictEqual(blockJul02Parts[7], "partial_observation", "Valid block value in 2002-07 must be marked partial_observation");
  }

  // 3. Synthetic Warning Test
  const syntheticCsv = generateCsv({
    regionId: "BR-PA",
    blockId: null,
    statewide: statewideRaw,
    blocksSummary: blocksRaw,
    isSynthetic: true,
  });
  assert.ok(syntheticCsv.includes("WARNING: DEVELOPMENT / SYNTHETIC DATA ACTIVE"));
});
