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
  status: z.enum(["ok", "unsupported_period", "partial_observation", "missing"]),
  coverage_status: z.string(),
  measurement_unit: z.string().nullable(),
  estimated_viirs_count: z.number().nullable(),
  observed_viirs_count: z.number().nullable(),
  observed_modis_count: z.number().nullable(),
  source: z.string(),
});

export type MonthlySeriesItem = z.infer<typeof MonthlySeriesItemSchema>;

export const StatewideMonthlyPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  generatedAtUtc: z.string(),
  provenance: z.object({
    model_version: z.string(),
    historical_period: z.string(),
    observed_period: z.string(),
    total_historical_estimated_viirs: z.number(),
    total_observed_viirs: z.number().int(),
    total_observed_modis: z.number().int(),
    clean_period_observed_viirs: z.number().int(),
    clean_period_observed_modis: z.number().int(),
    partial_month_notice: z.string(),
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
  status: z.enum(["ok", "unsupported_period", "partial_observation", "missing"]),
  measurement_unit: z.string().nullable(),
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
export const EvaluationMetricsSchema = z.object({
  native_cell_mae: z.number(),
  native_cell_medae: z.number(),
  native_cell_rmse: z.number(),
  monthly_wape_pct: z.number().optional(),
  spatial_wape_pct: z.number().optional(),
  monthly_r2: z.number().optional(),
  aggregate_bias_pct: z.number(),
});

export const ModelMetricsPayloadSchema = z.object({
  regionId: z.literal("BR-PA"),
  modelVersion: z.string(),
  generatedAtUtc: z.string(),
  architecture: z.object({
    family: z.string(),
    distribution: z.string(),
    link: z.string(),
    dispersion_alpha: z.number(),
    poisson_deviance: z.number(),
    reference_month: z.number().int(),
    baseline_ratio_k: z.number(),
    predictors: z.array(z.string()),
  }),
  training_provenance: z.object({
    calibration_dataset: z.string(),
    sample_design: z.string(),
    training_records_count: z.number().int(),
    temporal_training_set_2012_2018: z.number().int(),
    temporal_test_set_2019_2020: z.number().int(),
    geographic_training_blocks_count: z.number().int(),
    geographic_heldout_blocks_count: z.number().int(),
    excluded_period: z.string(),
  }),
  official_evaluation_metrics: z.object({
    temporal_holdout_2019_2020: z.object({
      evaluation_period: z.string(),
      sample_size: z.number().int(),
      nb2_metrics: EvaluationMetricsSchema,
      baseline_ratio_metrics: EvaluationMetricsSchema,
      improvement_vs_baseline: z.object({
        cell_mae_reduction: z.number(),
        monthly_wape_reduction_pct: z.number(),
        monthly_r2_gain: z.number(),
      }),
    }),
    geographic_holdout_94_blocks: z.object({
      evaluation_blocks: z.string(),
      sample_size: z.number().int(),
      nb2_metrics: EvaluationMetricsSchema,
      baseline_ratio_metrics: EvaluationMetricsSchema,
      improvement_vs_baseline: z.object({
        cell_mae_reduction: z.number(),
        spatial_wape_reduction_pct: z.number(),
      }),
    }),
  }),
  scientific_limitations: z.array(z.string()),
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
