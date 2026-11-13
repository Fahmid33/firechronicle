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
    scientific_integrity_rule: "SYNTHETIC FIXTURE — NOT OBSERVATIONAL EVIDENCE",
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
      expected_passes: 1136,
      available_estimates_count: isUnsupported ? 0 : 450,
      missing_estimates_count: isUnsupported ? 1136 : 686,
      estimated_viirs_count: isUnsupported ? null : (isHist ? 500 : null),
      observed_viirs_count: isUnsupported ? null : (!isHist ? 750 : null),
      observed_modis_count: isUnsupported ? null : (!isHist ? 120 : null),
      source: "SYNTHETIC DEVELOPMENT FIXTURE — NOT OBSERVATIONS",
      completeness_notice: "SYNTHETIC DEVELOPMENT FIXTURE",
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
          coverage_notice: "SYNTHETIC DEVELOPMENT FIXTURE",
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
  scientificStatus: "SYNTHETIC_DEVELOPMENT_FIXTURE",
  architecture: {
    family: "Generalized Linear Model (GLM)",
    distribution: "Negative Binomial (NB2)",
    link: "log",
    dispersionAlpha: 0.3394,
    logLikelihood: -105163.79,
    aic: 210357.58,
    bic: 210478.24,
    referenceMonth: 1,
    baselineRatioMultiplierK: 6.0538,
    predictors: ["log1p_modis", "daynight_N", "month fixed effects"],
  },
  trainingProvenance: {
    calibrationDataset: "MOCK FIXTURE",
    sampleDesign: "Paired-positive",
    trainingRecordsCount: 23010,
    pairedModisTotal: 342397,
    pairedViirsTotal: 2072819,
    temporalTrainingSet2012_2018: 17919,
    temporalTestSet2019_2020: 5091,
    geographicTrainingBlocksCount: 376,
    geographicHeldoutBlocksCount: 94,
    excludedPeriod: "January 2012",
  },
  officialEvaluationMetrics: {
    strategy_A_temporal_holdout: {
      title: "Strategy A: Temporal Holdout (2019–2020)",
      description: "Synthetic test fixture",
      sampleSize: 5091,
      nb2: {
        mae: 35.44,
        medae: 13.68,
        rmse: 84.53,
        meanPoissonDeviance: 25.01,
        aggregateBiasPct: -11.5,
        monthlyCorrelation: 0.9772,
        monthlyWapePct: 16.79,
        monthlyR2: 0.9148,
        dispersionAlpha: 0.329,
      },
      baselineRatio: {
        mae: 44.99,
        medae: 16.48,
        rmse: 104.99,
        meanPoissonDeviance: 55.31,
        aggregateBiasPct: -12.91,
        monthlyCorrelation: 0.9854,
        monthlyWapePct: 20.48,
        monthlyR2: 0.9009,
        fittedK: 5.8696,
      },
      comparison: {
        maeReduction: 9.55,
        devianceReduction: 30.3,
        monthlyWapeReductionPct: 3.69,
      },
    },
    strategy_B_geographic_holdout: {
      title: "Strategy B: Grouped Geographic Holdout (94 Blocks)",
      description: "Synthetic test fixture",
      sampleSize: 5147,
      nb2: {
        mae: 35.79,
        medae: 15.19,
        rmse: 75.01,
        meanPoissonDeviance: 20.95,
        aggregateBiasPct: 4.55,
        monthlyCorrelation: 0.9936,
        spatialWapePct: 34.15,
        dispersionAlpha: 0.347,
      },
      baselineRatio: {
        mae: 53.87,
        medae: 19.92,
        rmse: 116.11,
        meanPoissonDeviance: 56.35,
        aggregateBiasPct: -4.38,
        monthlyCorrelation: 0.9926,
        spatialWapePct: 51.39,
        fittedK: 5.9849,
      },
      comparison: {
        maeReduction: 18.08,
        devianceReduction: 35.4,
        spatialWapeReductionPct: 17.24,
      },
    },
  },
  scientificLimitations: [
    "DEVELOPMENT / SYNTHETIC TEST FIXTURE — NOT OBSERVATIONAL EVIDENCE",
  ],
};
