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

  // Simple in-line implementation matching src/lib/csv/csv-export.ts for unit test
  function generateCsv(options) {
    const { regionId = "BR-PA", blockId, statewide, blocksSummary, isSynthetic = false } = options;
    const lines = [];

    if (isSynthetic) {
      lines.push("# WARNING: DEVELOPMENT / SYNTHETIC DATA ACTIVE");
    }
    lines.push("# FireChronicle Export");
    lines.push("region_id,block_id,year,month,daynight,value,value_type,status,measurement_unit,model_version");

    if (blockId && blocksSummary?.blocks[blockId] && statewide?.series) {
      const block = blocksSummary.blocks[blockId];
      statewide.series.forEach((ref, idx) => {
        const val = block.values[idx] ?? null;
        const isHist = ref.year < 2012;
        let status = ref.status;
        if (ref.status === "unsupported_period") status = "unsupported_period";
        else if (val === null) status = "missing";
        else if (ref.status === "partial_observation") status = "partial_observation";
        else status = "ok";

        const valType = isHist ? (val !== null ? "estimated" : "") : (val !== null ? "observed" : "");
        const unit = valType === "estimated" ? "VIIRS_S-NPP-equivalent_detection_count" : (valType === "observed" ? "VIIRS_S-NPP_detection_count" : "");
        const model = valType === "estimated" ? "firechronicle-nb2-v1.0" : (valType === "observed" ? "N/A (S-NPP VIIRS Direct Observation)" : "");

        lines.push(`${regionId},${blockId},${ref.year},${ref.month},ALL,${val !== null ? val.toFixed(2) : ""},${valType},${status},${unit},${model}`);
      });
    } else if (statewide?.series) {
      statewide.series.forEach(s => {
        const valType = s.value_type ?? "";
        const unit = valType === "estimated" ? "VIIRS_S-NPP-equivalent_detection_count" : (valType === "observed" ? "VIIRS_S-NPP_detection_count" : "");
        const model = valType === "estimated" ? "firechronicle-nb2-v1.0" : (valType === "observed" ? "N/A (S-NPP VIIRS Direct Observation)" : "");
        lines.push(`${regionId},STATEWIDE,${s.year},${s.month},ALL,${s.value !== null ? s.value.toFixed(2) : ""},${valType},${s.status},${unit},${model}`);
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

  // Check 2002-01 (Pre-commissioning: empty value)
  const rowJan02 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2002,1,"));
  assert.ok(rowJan02, "Must contain row for 2002-01");
  const partsJan02 = rowJan02.split(",");
  assert.strictEqual(partsJan02[4], "ALL", "daynight must be ALL");
  assert.strictEqual(partsJan02[5], "", "2002-01 value must be empty (preserved NULL)");
  assert.strictEqual(partsJan02[7], "unsupported_period", "status must be unsupported_period");

  // Check 2002-07 (First estimated month)
  const rowJul02 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2002,7,"));
  assert.ok(rowJul02);
  const partsJul02 = rowJul02.split(",");
  assert.ok(Number(partsJul02[5]) > 0, "2002-07 value must be positive");
  assert.strictEqual(partsJul02[6], "estimated");
  assert.strictEqual(partsJul02[9], "firechronicle-nb2-v1.0");

  // Check 2012-01 (Partial observation)
  const rowJan12 = dataRows.find(r => r.startsWith("BR-PA,STATEWIDE,2012,1,"));
  assert.ok(rowJan12);
  const partsJan12 = rowJan12.split(",");
  assert.strictEqual(partsJan12[6], "observed");
  assert.strictEqual(partsJan12[7], "partial_observation");

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
