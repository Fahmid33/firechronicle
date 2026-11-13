import { MONTHS } from "@/types/explorer";
import type { StatewideMonthlyPayload, BlocksSummaryPayload } from "@/types/scientific-data";

export interface TimelineDataPoint {
  period: string; // "YYYY-MM"
  year: number;
  month: number;
  label: string; // "Jul '02"
  fullLabel: string; // "July 2002"
  value: number | null;
  estimatedViirs: number | null;
  observedViirs: number | null;
  observedModis: number | null;
  status: "ok" | "unsupported_period" | "partial_observation" | "missing" | "insufficient_coverage";
  valueType: "estimated" | "observed" | null;
  passes?: number | null;
}

export interface SeasonalDataPoint {
  month: number;
  monthName: string; // "Jan", "Feb", ...
  historicalAvg: number | null;
  historicalCount: number;
  modernAvg: number | null;
  modernCount: number;
}

export interface AnnualTotalPoint {
  year: number;
  total: number | null;
  validMonthsCount: number;
  era: "partial_historical" | "historical_estimated" | "modern_observed";
  label: string;
}

/**
 * Transforms statewide or block-specific monthly time series into unified timeline points.
 * Preserves genuine nulls — NEVER replaces missing or unobserved data with 0.
 */
export function buildTimelineData(
  statewide: StatewideMonthlyPayload | null | undefined,
  blocksSummary: BlocksSummaryPayload | null | undefined,
  scope: "statewide" | "block",
  selectedBlockId: string | null
): TimelineDataPoint[] {
  if (scope === "block" && selectedBlockId && blocksSummary?.blocks[selectedBlockId] && statewide?.series) {
    const block = blocksSummary.blocks[selectedBlockId];
    return statewide.series.map((ref, idx) => {
      const monthIdx = ref.month - 1;
      const monthName = MONTHS[monthIdx] ?? `M${ref.month}`;
      const yrShort = String(ref.year).slice(-2);
      const isHist = ref.year < 2012;
      const val = block.values[idx] ?? null;

      let status: TimelineDataPoint["status"] = ref.status;
      if (ref.status === "unsupported_period") {
        status = "unsupported_period";
      } else if (val === null) {
        status = "missing";
      } else if (ref.status === "partial_observation") {
        status = "partial_observation";
      } else {
        status = "ok";
      }

      return {
        period: ref.period,
        year: ref.year,
        month: ref.month,
        label: `${monthName.slice(0, 3)} '${yrShort}`,
        fullLabel: `${monthName} ${ref.year}`,
        value: val,
        estimatedViirs: isHist && val !== null ? val : null,
        observedViirs: !isHist && val !== null ? val : null,
        observedModis: null,
        status,
        valueType: isHist ? (val !== null ? "estimated" : null) : (val !== null ? "observed" : null),
      };
    });
  }

  // Fallback to Statewide Pará
  if (!statewide?.series) return [];

  return statewide.series.map((p) => {
    const monthIdx = p.month - 1;
    const monthName = MONTHS[monthIdx] ?? `M${p.month}`;
    const yrShort = String(p.year).slice(-2);
    const isHist = p.year < 2012;

    const insufficient = isHist && (p.status === "insufficient_coverage" || p.complete_pairs_count === 0);

    return {
      period: p.period,
      year: p.year,
      month: p.month,
      label: `${monthName.slice(0, 3)} '${yrShort}`,
      fullLabel: `${monthName} ${p.year}`,
      value: insufficient ? null : p.value,
      estimatedViirs: isHist && !insufficient && p.estimated_viirs_count !== null ? p.estimated_viirs_count : null,
      observedViirs: !isHist && p.observed_viirs_count !== null ? p.observed_viirs_count : null,
      observedModis: p.observed_modis_count,
      status: insufficient ? "insufficient_coverage" : p.status,
      valueType: insufficient ? null : p.value_type,
      passes: p.available_estimates_count,
    };
  });
}

/**
 * Builds 12-month seasonal perspective comparing:
 * - Historical baseline (2003-2011, excluding unsupported Jan-Jun 2002 and partial Jul 2002)
 * - Modern observed (2012-2020, excluding partial observation Jan 2012 where days 1-19 were unobserved)
 */
export function buildSeasonalData(timeline: TimelineDataPoint[]): SeasonalDataPoint[] {
  const result: SeasonalDataPoint[] = [];

  for (let m = 1; m <= 12; m++) {
    const monthName = MONTHS[m - 1] ? MONTHS[m - 1].slice(0, 3) : `M${m}`;

    // Historical: 2003-2011 (9 complete years)
    const histPoints = timeline.filter(
      (p) => p.month === m && p.year >= 2003 && p.year <= 2011 && p.value !== null
    );
    const histSum = histPoints.reduce((acc, p) => acc + (p.value ?? 0), 0);
    const historicalAvg = histPoints.length > 0 ? Math.round(histSum / histPoints.length) : null;

    // Modern: 2012-2020 (excluding partial observation 2012-01 where days 1-19 were unobserved; Jan averages 8 complete years 2013-2020)
    const modernPoints = timeline.filter(
      (p) => p.month === m && p.year >= 2012 && p.year <= 2020 && p.value !== null && p.status !== "partial_observation"
    );
    const modernSum = modernPoints.reduce((acc, p) => acc + (p.value ?? 0), 0);
    const modernAvg = modernPoints.length > 0 ? Math.round(modernSum / modernPoints.length) : null;

    result.push({
      month: m,
      monthName,
      historicalAvg,
      historicalCount: histPoints.length,
      modernAvg,
      modernCount: modernPoints.length,
    });
  }

  return result;
}

/**
 * Computes annual totals (2002-2020).
 * Clearly tags 2002 as partial (Jul-Dec only).
 */
export function buildAnnualTotals(timeline: TimelineDataPoint[]): AnnualTotalPoint[] {
  const years = Array.from(new Set(timeline.map((p) => p.year))).sort((a, b) => a - b);
  const result: AnnualTotalPoint[] = [];

  for (const yr of years) {
    const yrPoints = timeline.filter((p) => p.year === yr && p.value !== null);
    const total = yrPoints.length > 0 ? Math.round(yrPoints.reduce((acc, p) => acc + (p.value ?? 0), 0)) : null;

    let era: AnnualTotalPoint["era"] = "modern_observed";
    let label = `${yr} (Observed VIIRS)`;

    if (yr === 2002) {
      era = "partial_historical";
      label = "2002 (Partial: Jul-Dec only)";
    } else if (yr < 2012) {
      era = "historical_estimated";
      label = `${yr} (Estimated VIIRS-equivalent)`;
    }

    result.push({
      year: yr,
      total,
      validMonthsCount: yrPoints.length,
      era,
      label,
    });
  }

  return result;
}
