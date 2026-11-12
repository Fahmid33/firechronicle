import type {
  StatewideMonthlyPayload,
  CalendarMatrixPayload,
  BlocksSummaryPayload,
  ModelMetricsPayload,
} from "@/types/scientific-data";

/**
 * SYNTHETIC DEVELOPMENT FIXTURES ONLY.
 * These fixtures are for testing component error boundaries and fallback UI.
 * They DO NOT represent real satellite observations or scientific evidence.
 */

export const MOCK_STATEWIDE_PAYLOAD: StatewideMonthlyPayload = {
  regionId: "BR-PA",
  generatedAtUtc: "2026-11-12T00:00:00.000Z",
  provenance: {
    model_version: "firechronicle-nb2-v1.0-MOCK",
    historical_period: "2002-07 to 2011-12",
    observed_period: "2012-01 to 2020-12",
    total_historical_estimated_viirs: 100000.0,
    total_observed_viirs: 150000,
    total_observed_modis: 25000,
    clean_period_observed_viirs: 149000,
    clean_period_observed_modis: 24800,
    partial_month_notice: "DEVELOPMENT / SYNTHETIC MOCK DATA — NOT VALIDATED OBSERVATIONS",
  },
  series: Array.from({ length: 228 }, (_, i) => {
    const yr = 2002 + Math.floor(i / 12);
    const mo = (i % 12) + 1;
    const isUnsupported = yr === 2002 && mo < 7;
    const isHist = yr < 2012;
    return {
      year: yr,
      month: mo,
      month_name: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][mo - 1],
      period: `${yr}-${String(mo).padStart(2, "0")}`,
      value: isUnsupported ? null : (isHist ? 500 : 750),
      value_type: isUnsupported ? null : (isHist ? "estimated" : "observed"),
      status: isUnsupported ? "unsupported_period" : "ok",
      coverage_status: "synthetic_mock",
      measurement_unit: isUnsupported ? null : (isHist ? "VIIRS_S-NPP-equivalent_detection_count" : "VIIRS_S-NPP_detection_count"),
      estimated_viirs_count: isUnsupported ? null : (isHist ? 500 : null),
      observed_viirs_count: isUnsupported ? null : (!isHist ? 750 : null),
      observed_modis_count: isUnsupported ? null : (!isHist ? 120 : null),
      source: "SYNTHETIC DEVELOPMENT FIXTURE — NOT OBSERVATIONS",
    };
  }),
};

export const MOCK_CALENDAR_PAYLOAD: CalendarMatrixPayload = {
  regionId: "BR-PA",
  years: Array.from({ length: 19 }, (_, yIdx) => {
    const yr = 2002 + yIdx;
    return {
      year: yr,
      months: Array.from({ length: 12 }, (_, mIdx) => {
        const mo = mIdx + 1;
        const isUnsupported = yr === 2002 && mo < 7;
        const isHist = yr < 2012;
        return {
          month: mo,
          month_name: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][mIdx],
          period: `${yr}-${String(mo).padStart(2, "0")}`,
          value: isUnsupported ? null : (isHist ? 500 : 750),
          value_type: isUnsupported ? null : (isHist ? "estimated" : "observed"),
          status: isUnsupported ? "unsupported_period" : "ok",
          measurement_unit: isUnsupported ? null : (isHist ? "VIIRS_S-NPP-equivalent_detection_count" : "VIIRS_S-NPP_detection_count"),
        };
      }),
    };
  }),
};

export const MOCK_BLOCKS_SUMMARY: BlocksSummaryPayload = {
  regionId: "BR-PA",
  periods: Array.from({ length: 228 }, (_, i) => {
    const yr = 2002 + Math.floor(i / 12);
    const mo = (i % 12) + 1;
    return `${yr}-${String(mo).padStart(2, "0")}`;
  }),
  blocks: {
    "MOCK-001": {
      block_id: "MOCK-001",
      hist_sum: 1200.5,
      obs_viirs_sum: 3400.0,
      obs_modis_sum: 550.0,
      values: Array.from({ length: 228 }, (_, i) => (i < 6 ? null : 15.0)),
    },
  },
};

export const MOCK_MODEL_METRICS: ModelMetricsPayload = {
  regionId: "BR-PA",
  modelVersion: "firechronicle-nb2-v1.0-SYNTHETIC",
  generatedAtUtc: "2026-11-12T00:00:00.000Z",
  architecture: {
    family: "Generalized Linear Model",
    distribution: "Negative Binomial (NB2)",
    link: "log",
    dispersion_alpha: 0.33,
    poisson_deviance: 32.0,
    reference_month: 1,
    baseline_ratio_k: 6.05,
    predictors: ["log1p_modis", "daynight_N", "month fixed effects"],
  },
  training_provenance: {
    calibration_dataset: "MOCK FIXTURE",
    sample_design: "Paired-positive",
    training_records_count: 23010,
    temporal_training_set_2012_2018: 17919,
    temporal_test_set_2019_2020: 5091,
    geographic_training_blocks_count: 376,
    geographic_heldout_blocks_count: 94,
    excluded_period: "January 2012",
  },
  official_evaluation_metrics: {
    temporal_holdout_2019_2020: {
      evaluation_period: "2019-2020",
      sample_size: 5091,
      nb2_metrics: {
        native_cell_mae: 35.44,
        native_cell_medae: 13.68,
        native_cell_rmse: 84.53,
        monthly_wape_pct: 16.79,
        monthly_r2: 0.9148,
        aggregate_bias_pct: -11.5,
      },
      baseline_ratio_metrics: {
        native_cell_mae: 44.99,
        native_cell_medae: 16.48,
        native_cell_rmse: 104.99,
        monthly_wape_pct: 20.48,
        monthly_r2: 0.9009,
        aggregate_bias_pct: -12.91,
      },
      improvement_vs_baseline: {
        cell_mae_reduction: 9.55,
        monthly_wape_reduction_pct: 3.69,
        monthly_r2_gain: 0.0139,
      },
    },
    geographic_holdout_94_blocks: {
      evaluation_blocks: "94 blocks",
      sample_size: 5147,
      nb2_metrics: {
        native_cell_mae: 35.79,
        native_cell_medae: 15.19,
        native_cell_rmse: 75.01,
        spatial_wape_pct: 34.15,
        aggregate_bias_pct: 4.55,
      },
      baseline_ratio_metrics: {
        native_cell_mae: 53.87,
        native_cell_medae: 19.92,
        native_cell_rmse: 116.11,
        spatial_wape_pct: 51.39,
        aggregate_bias_pct: -4.38,
      },
      improvement_vs_baseline: {
        cell_mae_reduction: 18.08,
        spatial_wape_reduction_pct: 17.24,
      },
    },
  },
  scientific_limitations: [
    "DEVELOPMENT / SYNTHETIC TEST FIXTURE — NOT OBSERVATIONAL EVIDENCE",
  ],
};
