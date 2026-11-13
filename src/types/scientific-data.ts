import { z } from "zod";

// -----------------------------------------------------------------------------
// 1. Statewide Monthly Time Series
// -----------------------------------------------------------------------------
export const MonthlySeriesItemSchema = z.object({
  year: z.number().int().min(2002).max(2026),
  month: z.number().int().min(1).max(12),
  month_name: z.string(),
  period: z.string().regex(/^\d{4}-\d{2}$/),
  value: z.number().nullable(),
  value_type: z.enum(["estimated", "observed"]).nullable(),
  status: z.enum(["ok", "unsupported_period", "partial_observation", "missing", "insufficient_coverage"]),
  coverage_status: z.string(),
  measurement_unit: z.string().nullable(),
  expected_passes: z.number().int().optional(),
  available_estimates_count: z.number().int().nullable().optional(),
  missing_estimates_count: z.number().int().nullable().optional(),
  estimated_viirs_count: z.number().nullable(),
  strict_both_passes_value: z.number().nullable().optional(),
  available_passes_value: z.number().nullable().optional(),
  complete_pairs_count: z.number().int().optional(),
  single_pass_count: z.number().int().optional(),
  observed_viirs_count: z.number().nullable(),
  observed_modis_count: z.number().nullable(),
  source: z.string(),
  completeness_notice: z.string().optional(),
});

export type MonthlySeriesItem = z.infer<typeof MonthlySeriesItemSchema>;

export const StatewideMonthlyPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  generatedAtUtc: z.string(),
  provenance: z.object({
    model_version: z.string(),
    historical_period: z.string(),
    observed_period: z.string(),
    clean_overlap_period: z.string().optional(),
    total_historical_expected_passes: z.number().int().optional(),
    total_historical_available_estimates: z.number().int().optional(),
    total_historical_missing_estimates: z.number().int().optional(),
    total_historical_estimated_viirs: z.number(),
    total_historical_available_passes_sum: z.number().optional(),
    total_historical_complete_pair_block_months: z.number().int().optional(),
    total_historical_single_pass_block_months: z.number().int().optional(),
    total_historical_zero_pass_block_months: z.number().int().optional(),
    aggregation_rule: z.string().optional(),
    total_observed_viirs: z.number().int(),
    total_observed_modis: z.number().int(),
    clean_period_observed_viirs: z.number().int(),
    clean_period_observed_modis: z.number().int(),
    partial_month_notice: z.string(),
    scientific_integrity_rule: z.string().optional(),
  }),
  series: z.array(MonthlySeriesItemSchema),
});

export type StatewideMonthlyPayload = z.infer<typeof StatewideMonthlyPayloadSchema>;

// -----------------------------------------------------------------------------
// 2. Calendar Matrix
// -----------------------------------------------------------------------------
export const CalendarMonthItemSchema = z.object({
  month: z.number().int().min(1).max(12),
  month_name: z.string(),
  period: z.string(),
  value: z.number().nullable(),
  value_type: z.enum(["estimated", "observed"]).nullable(),
  status: z.enum(["ok", "unsupported_period", "partial_observation", "missing", "insufficient_coverage"]),
  measurement_unit: z.string().nullable(),
  coverage_notice: z.string().optional(),
});

export type CalendarMonthItem = z.infer<typeof CalendarMonthItemSchema>;

export const CalendarYearRowSchema = z.object({
  year: z.number().int().min(2002).max(2026),
  months: z.array(CalendarMonthItemSchema).length(12),
});

export type CalendarYearRow = z.infer<typeof CalendarYearRowSchema>;

export const CalendarMatrixPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  years: z.array(CalendarYearRowSchema),
});

export type CalendarMatrixPayload = z.infer<typeof CalendarMatrixPayloadSchema>;

// -----------------------------------------------------------------------------
// 3. Block-Level Monthly Time Series
// -----------------------------------------------------------------------------
export const BlockSummaryItemSchema = z.object({
  block_id: z.string(),
  hist_sum: z.number(),
  hist_strict_sum: z.number().optional(),
  hist_available_sum: z.number().optional(),
  obs_viirs_sum: z.number(),
  obs_modis_sum: z.number(),
  values: z.array(z.number().nullable()),
});

export type BlockSummaryItem = z.infer<typeof BlockSummaryItemSchema>;

export const BlocksSummaryPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  periods: z.array(z.string()),
  blocks: z.record(z.string(), BlockSummaryItemSchema),
});

export type BlocksSummaryPayload = z.infer<typeof BlocksSummaryPayloadSchema>;

// -----------------------------------------------------------------------------
// 4. Model Evaluation Metadata (Sensor Lab)
// -----------------------------------------------------------------------------
export const EvaluationSplitSchema = z.object({
  title: z.string(),
  description: z.string(),
  sampleSize: z.number().int(),
  nb2: z.object({
    mae: z.number(),
    medae: z.number(),
    rmse: z.number(),
    meanPoissonDeviance: z.number(),
    totalPoissonDeviance: z.number().optional(),
    aggregateBiasPct: z.number(),
    monthlyCorrelation: z.number(),
    monthlyWapePct: z.number().optional(),
    spatialWapePct: z.number().optional(),
    monthlyR2: z.number().optional(),
    dispersionAlpha: z.number(),
  }),
  baselineRatio: z.object({
    mae: z.number(),
    medae: z.number(),
    rmse: z.number(),
    meanPoissonDeviance: z.number(),
    totalPoissonDeviance: z.number().optional(),
    aggregateBiasPct: z.number(),
    monthlyCorrelation: z.number(),
    monthlyWapePct: z.number().optional(),
    spatialWapePct: z.number().optional(),
    monthlyR2: z.number().optional(),
    fittedK: z.number(),
  }),
  comparison: z.object({
    maeReduction: z.number(),
    devianceReduction: z.number(),
    monthlyWapeReductionPct: z.number().optional(),
    spatialWapeReductionPct: z.number().optional(),
  }),
});

export const ModelMetricsPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  modelVersion: z.string(),
  generatedAtUtc: z.string(),
  scientificStatus: z.string(),
  architecture: z.object({
    family: z.string(),
    distribution: z.string(),
    link: z.string(),
    dispersionAlpha: z.number(),
    logLikelihood: z.number(),
    aic: z.number(),
    bic: z.number(),
    referenceMonth: z.number().int(),
    baselineRatioMultiplierK: z.number(),
    predictors: z.array(z.string()),
  }),
  trainingProvenance: z.object({
    calibrationDataset: z.string(),
    sampleDesign: z.string(),
    trainingRecordsCount: z.number().int(),
    pairedModisTotal: z.number().int(),
    pairedViirsTotal: z.number().int(),
    temporalTrainingSet2012_2018: z.number().int(),
    temporalTestSet2019_2020: z.number().int(),
    geographicTrainingBlocksCount: z.number().int(),
    geographicHeldoutBlocksCount: z.number().int(),
    excludedPeriod: z.string(),
  }),
  officialEvaluationMetrics: z.object({
    strategy_A_temporal_holdout: EvaluationSplitSchema,
    strategy_B_geographic_holdout: EvaluationSplitSchema,
  }),
  scientificLimitations: z.array(z.string()),
});

export type ModelMetricsPayload = z.infer<typeof ModelMetricsPayloadSchema>;

// -----------------------------------------------------------------------------
// 5. Data Client Types & Adapter Interface
// -----------------------------------------------------------------------------
export type DataSourceMode = "static" | "live" | "mock";

export interface IDataClient {
  readonly mode: DataSourceMode;
  readonly isSynthetic: boolean;
  getStatewideTimeSeries(): Promise<StatewideMonthlyPayload>;
  getCalendarMatrix(): Promise<CalendarMatrixPayload>;
  getBlocksSummary(): Promise<BlocksSummaryPayload>;
  getModelMetrics(): Promise<ModelMetricsPayload>;
}
