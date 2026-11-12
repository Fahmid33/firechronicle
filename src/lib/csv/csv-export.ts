import type { StatewideMonthlyPayload, BlocksSummaryPayload } from "@/types/scientific-data";

export interface CsvExportOptions {
  regionId?: string;
  blockId: string | null; // null for statewide Pará
  statewide: StatewideMonthlyPayload | null | undefined;
  blocksSummary: BlocksSummaryPayload | null | undefined;
  isSynthetic?: boolean;
}

/**
 * Escapes a cell value according to RFC 4180.
 */
function escapeCsv(val: string | number | null | undefined): string {
  if (val === null || val === undefined) return "";
  const str = String(val);
  if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Generates an authoritative, RFC-4180 compliant CSV string for the
 * currently active statewide or selected-block monthly time series.
 *
 * Preserves NULL values — never converts missing records to 0.
 * Labels daynight as ALL when aggregated across passes, documenting the aggregation.
 */
export function generateTimeSeriesCsv(options: CsvExportOptions): string {
  const {
    regionId = "BR-PA",
    blockId,
    statewide,
    blocksSummary,
    isSynthetic = false,
  } = options;

  const lines: string[] = [];

  // Metadata comments / Provenance
  if (isSynthetic) {
    lines.push("# ==============================================================================");
    lines.push("# WARNING: DEVELOPMENT / SYNTHETIC DATA ACTIVE");
    lines.push("# This export contains synthetic mock fixtures and MUST NOT be used for science.");
    lines.push("# ==============================================================================");
  }

  lines.push("# FireChronicle Earth Observation Explorer - Scientific Time Series Export");
  lines.push(`# Region: ${regionId} (Pará, Brazil)`);
  lines.push(`# Scope: ${blockId ? `Block ${blockId} (50 km EASE-Grid 2.0 / EPSG:6933 grid cell)` : "Statewide Pará (Strict daynight=ALL)"}`);
  lines.push(`# Exported at (UTC): ${new Date().toISOString()}`);
  lines.push("# Scientific Integrity Rule: Aqua MODIS and S-NPP VIIRS detections are NEVER summed together.");
  lines.push("# Day/Night Policy: daynight column is labeled 'ALL'. At block level, D+N is valid only if both passes exist; at statewide level, totals sum only complete pairs.");
  lines.push("# Missing Data Policy: Pre-commissioning (Jan-Jun 2002) and missing passes are preserved as NULL (empty), NOT zero.");
  lines.push("# Model Specification: firechronicle-nb2-v1.0 (Negative Binomial GLM, alpha = 0.3394)");
  lines.push("#");

  // Official CSV Column Header
  const headers = [
    "region_id",
    "block_id",
    "year",
    "month",
    "daynight",
    "value",
    "value_type",
    "status",
    "measurement_unit",
    "model_version",
  ];
  lines.push(headers.join(","));

  const targetBlockId = blockId ?? "STATEWIDE";

  if (blockId && blocksSummary?.blocks[blockId] && statewide?.series) {
    // Selected 50 km block export
    const block = blocksSummary.blocks[blockId];

    statewide.series.forEach((ref, idx) => {
      const yr = ref.year;
      const mo = ref.month;
      const val = block.values[idx] ?? null;
      const isHist = yr < 2012;

      let status = ref.status;
      if (ref.status === "unsupported_period") {
        status = "unsupported_period";
      } else if (val === null) {
        status = "missing";
      } else if (ref.status === "partial_observation") {
        status = "partial_observation";
      } else {
        status = "ok";
      }

      const valueType = isHist ? (val !== null ? "estimated" : "") : (val !== null ? "observed" : "");
      let unit = "";
      let modelVersion = "";

      if (valueType === "estimated") {
        unit = "VIIRS_S-NPP-equivalent_detection_count";
        modelVersion = "firechronicle-nb2-v1.0";
      } else if (valueType === "observed") {
        unit = "VIIRS_S-NPP_detection_count";
        modelVersion = "N/A (S-NPP VIIRS Direct Observation)";
      }

      const row = [
        escapeCsv(regionId),
        escapeCsv(targetBlockId),
        escapeCsv(yr),
        escapeCsv(mo),
        "ALL",
        escapeCsv(val !== null ? Number(val.toFixed(2)) : null),
        escapeCsv(valueType),
        escapeCsv(status),
        escapeCsv(unit),
        escapeCsv(modelVersion),
      ];
      lines.push(row.join(","));
    });
  } else if (statewide?.series) {
    // Statewide Pará export
    statewide.series.forEach((s) => {
      const yr = s.year;
      const mo = s.month;
      const val = s.value;
      const valueType = s.value_type ?? "";
      let unit = "";
      let modelVersion = "";

      if (valueType === "estimated") {
        unit = "VIIRS_S-NPP-equivalent_detection_count";
        modelVersion = "firechronicle-nb2-v1.0";
      } else if (valueType === "observed") {
        unit = "VIIRS_S-NPP_detection_count";
        modelVersion = "N/A (S-NPP VIIRS Direct Observation)";
      }

      const row = [
        escapeCsv(regionId),
        escapeCsv("STATEWIDE"),
        escapeCsv(yr),
        escapeCsv(mo),
        "ALL",
        escapeCsv(val !== null ? Number(val.toFixed(2)) : null),
        escapeCsv(valueType),
        escapeCsv(s.status),
        escapeCsv(unit),
        escapeCsv(modelVersion),
      ];
      lines.push(row.join(","));
    });
  }

  return lines.join("\n");
}

/**
 * Triggers a browser download of the CSV content.
 */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
