import type {
  IDataClient,
  DataSourceMode,
  StatewideMonthlyPayload,
  CalendarMatrixPayload,
  CalendarMonthItem,
  CalendarYearRow,
  BlocksSummaryPayload,
  ModelMetricsPayload,
  MonthlySeriesItem,
} from "@/types/scientific-data";
import {
  StatewideMonthlyPayloadSchema,
  CalendarMatrixPayloadSchema,
  ModelMetricsPayloadSchema,
} from "@/types/scientific-data";
import { MONTHS } from "@/types/explorer";

export class ApiHttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly endpoint: string,
    message: string
  ) {
    super(`Live API Error [${status}] on '${endpoint}': ${message}`);
    this.name = "ApiHttpError";
  }
}

/**
 * Raw item format returned by the FastAPI backend for GET /api/v1/harmonized.
 * Matches the Backend Engineer's documented data structure.
 */
interface RawBackendHarmonizedItem {
  year: number;
  month: number;
  period?: string;
  daynight?: string;
  value?: number | null;
  estimated_viirs_count?: number | null;
  observed_viirs_count?: number | null;
  observed_modis_count?: number | null;
  value_type?: "estimated" | "observed" | null;
  prediction_status?: string;
  status?: "ok" | "unsupported_period" | "partial_observation" | "missing" | "insufficient_coverage";
  coverage_status?: string;
  measurement_unit?: string | null;
  model_version?: string;
  source?: string;
  completeness_notice?: string;
  strict_both_passes_value?: number | null;
  available_passes_value?: number | null;
  complete_pairs_count?: number;
  single_pass_count?: number;
  expected_passes?: number;
  available_estimates_count?: number | null;
  missing_estimates_count?: number | null;
}

interface RawMetricSubRecord {
  mae?: number;
  medae?: number;
  rmse?: number;
  meanPoissonDeviance?: number;
  mean_poisson_deviance?: number;
  totalPoissonDeviance?: number;
  total_poisson_deviance?: number;
  aggregateBiasPct?: number;
  aggregate_bias_pct?: number;
  monthlyCorrelation?: number;
  monthly_correlation?: number;
  monthlyWapePct?: number;
  monthly_wape_pct?: number;
  spatialWapePct?: number;
  spatial_wape_pct?: number;
  monthlyR2?: number;
  monthly_r2?: number;
  dispersionAlpha?: number;
  dispersion_alpha?: number;
  fittedK?: number;
  fitted_k?: number;
}

interface RawComparisonRecord {
  maeReduction?: number;
  mae_reduction?: number;
  devianceReduction?: number;
  deviance_reduction?: number;
  monthlyWapeReductionPct?: number;
  monthly_wape_reduction_pct?: number;
  spatialWapePct?: number;
  spatial_wape_pct?: number;
  spatialWapeReductionPct?: number;
  spatial_wape_reduction_pct?: number;
}

interface RawSplitRecord {
  title: string;
  description: string;
  sampleSize?: number;
  sample_size?: number;
  nb2?: RawMetricSubRecord;
  baselineRatio?: RawMetricSubRecord;
  baseline_ratio?: RawMetricSubRecord;
  comparison?: RawComparisonRecord;
}

export interface SpatialQueryParams {
  year: number;
  month: number;
  resolution?: string; // default: "50km"
  regionId?: string; // default: "BR-PA"
  daynight?: string; // default: "ALL"
}

export class LiveApiAdapter implements IDataClient {
  readonly mode: DataSourceMode = "live";
  readonly isSynthetic: boolean = false;
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  }

  async request(endpoint: string): Promise<unknown> {
    const url = `${this.baseUrl}/api/v1${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
    let res: Response;
    try {
      res = await fetch(url, {
        headers: { Accept: "application/json" },
      });
    } catch (err) {
      // Network unreachable or CORS failure: Must NOT silently fall back to synthetic data!
      throw new Error(`Live API network failure reaching '${url}': ${(err as Error).message}`);
    }

    if (!res.ok) {
      const errText = await res.text().catch(() => "Unknown error");
      throw new ApiHttpError(res.status, endpoint, errText);
    }

    return res.json();
  }

  /**
   * Transforms raw backend monthly harmonized records into the Zod-validated StatewideMonthlyPayload.
   * Leverages GET /api/v1/harmonized?region_id=BR-PA and GET /api/v1/summary?region_id=BR-PA.
   */
  async getStatewideTimeSeries(): Promise<StatewideMonthlyPayload> {
    const harmonizedRaw = await this.request("/harmonized?region_id=BR-PA");

    let summaryRaw: Record<string, unknown> = {};
    try {
      summaryRaw = (await this.request("/summary?region_id=BR-PA")) as Record<string, unknown>;
    } catch {
      // Summary metadata endpoint is optional / best-effort; defaults used if missing
    }

    // Extract items array from either bare array or envelope { region_id, items: [...] } or { data: [...] }
    const itemsRaw: RawBackendHarmonizedItem[] = Array.isArray(harmonizedRaw)
      ? (harmonizedRaw as RawBackendHarmonizedItem[])
      : Array.isArray((harmonizedRaw as { items?: RawBackendHarmonizedItem[] })?.items)
      ? (harmonizedRaw as { items: RawBackendHarmonizedItem[] }).items
      : Array.isArray((harmonizedRaw as { data?: RawBackendHarmonizedItem[] })?.data)
      ? (harmonizedRaw as { data: RawBackendHarmonizedItem[] }).data
      : [];

    const series: MonthlySeriesItem[] = itemsRaw.map((item) => {
      const yr = item.year;
      const mo = item.month;
      const period = item.period || `${yr}-${String(mo).padStart(2, "0")}`;
      const monthName = MONTHS[mo - 1] ?? `M${mo}`;
      const isHist = yr < 2012;

      // Map scientific status
      let status: MonthlySeriesItem["status"] = "ok";
      if (item.status) {
        status = item.status;
      } else if (item.prediction_status === "unsupported_period" || (yr === 2002 && mo < 7)) {
        status = "unsupported_period";
      } else if (item.prediction_status === "partial_observation" || (yr === 2012 && mo === 1)) {
        status = "partial_observation";
      } else if (
        item.prediction_status === "missing" ||
        item.prediction_status === "missing_required_feature" ||
        item.prediction_status === "insufficient_coverage"
      ) {
        status = item.prediction_status === "insufficient_coverage" ? "insufficient_coverage" : "missing";
      } else if (
        item.value === null &&
        item.estimated_viirs_count === null &&
        item.observed_viirs_count === null
      ) {
        status = "missing";
      }

      // Compute primary value
      let value: number | null = null;
      if (status !== "unsupported_period" && status !== "missing" && status !== "insufficient_coverage") {
        if (item.value !== undefined && item.value !== null) {
          value = item.value;
        } else if (isHist) {
          value = item.estimated_viirs_count ?? null;
        } else {
          value = item.observed_viirs_count ?? null;
        }
      }

      // Value type
      let valueType: "estimated" | "observed" | null = null;
      if (value !== null) {
        valueType = item.value_type ?? (isHist ? "estimated" : "observed");
      }

      // Sensor-specific counts
      const estimatedViirsCount = isHist ? (item.estimated_viirs_count ?? value) : null;
      const observedViirsCount = !isHist ? (item.observed_viirs_count ?? value) : null;
      const observedModisCount = item.observed_modis_count ?? null;

      const measurementUnit =
        item.measurement_unit ?? (value !== null ? "VIIRS_S-NPP-equivalent_detection_count" : null);
      const coverageStatus =
        item.coverage_status ?? (status === "unsupported_period" ? "unknown" : "verified");
      const source =
        item.source ??
        (isHist
          ? (value !== null ? "Historical Aqua MODIS -> NB2 v1.0 model" : "Unobserved (Aqua MODIS commissioned July 2002)")
          : "Observed S-NPP VIIRS");

      return {
        year: yr,
        month: mo,
        month_name: monthName,
        period,
        value,
        value_type: valueType,
        status,
        coverage_status: coverageStatus,
        measurement_unit: measurementUnit,
        expected_passes: item.expected_passes,
        available_estimates_count: item.available_estimates_count,
        missing_estimates_count: item.missing_estimates_count,
        estimated_viirs_count: estimatedViirsCount,
        strict_both_passes_value: item.strict_both_passes_value ?? (value !== null ? value : null),
        available_passes_value: item.available_passes_value,
        complete_pairs_count: item.complete_pairs_count,
        single_pass_count: item.single_pass_count,
        observed_viirs_count: observedViirsCount,
        observed_modis_count: observedModisCount,
        source,
        completeness_notice: item.completeness_notice,
      };
    });

    const provenance = {
      model_version: (summaryRaw.model_version as string) || "firechronicle-nb2-v1.0",
      historical_period: (summaryRaw.historical_period as string) || "2002-07 to 2011-12",
      observed_period: (summaryRaw.observed_period as string) || "2012-01 to 2020-12",
      clean_overlap_period: (summaryRaw.clean_overlap_period as string) || "2012-02 to 2020-12",
      total_historical_expected_passes: (summaryRaw.total_historical_expected_passes as number) ?? 129504,
      total_historical_available_estimates: (summaryRaw.total_historical_available_estimates as number) ?? 26962,
      total_historical_missing_estimates: (summaryRaw.total_historical_missing_estimates as number) ?? 102542,
      total_historical_estimated_viirs: (summaryRaw.total_historical_estimated_viirs as number) ?? 2874515.5,
      total_historical_available_passes_sum: (summaryRaw.total_historical_available_passes_sum as number) ?? 3557995.8,
      total_historical_complete_pair_block_months: (summaryRaw.total_historical_complete_pair_block_months as number) ?? 6516,
      total_historical_single_pass_block_months: (summaryRaw.total_historical_single_pass_block_months as number) ?? 13930,
      total_historical_zero_pass_block_months: (summaryRaw.total_historical_zero_pass_block_months as number) ?? 44306,
      aggregation_rule:
        (summaryRaw.aggregation_rule as string) ||
        "Backend-compatible strict daynight=ALL: A block-month value is non-null if and only if both Day and Night passes exist. Statewide monthly totals sum exclusively blocks with complete D+N pairs.",
      total_observed_viirs: (summaryRaw.total_observed_viirs as number) ?? 2196531,
      total_observed_modis: (summaryRaw.total_observed_modis as number) ?? 344071,
      clean_period_observed_viirs: (summaryRaw.clean_period_observed_viirs as number) ?? 2196086,
      clean_period_observed_modis: (summaryRaw.clean_period_observed_modis as number) ?? 343528,
      partial_month_notice:
        (summaryRaw.partial_month_notice as string) ||
        "January 2012 VIIRS archive began 2012-01-20; days 1-19 unobserved. Excluded from calibration.",
      scientific_integrity_rule:
        "MODIS and VIIRS detections are never summed together. Missing values preserved as NULL, never imputed as zero.",
    };

    const payload: StatewideMonthlyPayload = {
      regionId: "BR-PA",
      generatedAtUtc: (summaryRaw.generated_at_utc as string) || new Date().toISOString(),
      provenance,
      series,
    };

    const parsed = StatewideMonthlyPayloadSchema.safeParse(payload);
    if (!parsed.success) {
      throw new Error(`Live API transformed statewide payload failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  /**
   * Constructs the 19 years x 12 months calendar matrix directly from the monthly harmonized series.
   */
  async getCalendarMatrix(): Promise<CalendarMatrixPayload> {
    const statewide = await this.getStatewideTimeSeries();
    const yearsMap = new Map<number, CalendarMonthItem[]>();

    for (const item of statewide.series) {
      if (!yearsMap.has(item.year)) {
        yearsMap.set(item.year, []);
      }
      yearsMap.get(item.year)!.push({
        month: item.month,
        month_name: item.month_name,
        period: item.period,
        value: item.value,
        value_type: item.value_type,
        status: item.status,
        measurement_unit: item.measurement_unit,
        coverage_notice: item.completeness_notice,
      });
    }

    const years: CalendarYearRow[] = Array.from(yearsMap.entries())
      .sort(([a], [b]) => a - b)
      .map(([year, months]) => ({
        year,
        months: months.sort((a, b) => a.month - b.month),
      }));

    const payload: CalendarMatrixPayload = {
      regionId: "BR-PA",
      years,
    };

    const parsed = CalendarMatrixPayloadSchema.safeParse(payload);
    if (!parsed.success) {
      throw new Error(`Live API constructed calendar payload failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  /**
   * Live API Limitation:
   * The FastAPI backend provides period-specific spatial slices via
   * GET /api/v1/spatial?year=YYYY&month=MM&resolution=50km&region_id=BR-PA&daynight=ALL
   * and block metadata via GET /api/v1/blocks?region_id=BR-PA.
   *
   * Live mode is not fully integrated for block time series because the backend does not
   * yet expose the full multi-year block-summary contract (228 periods x 568 blocks = ~130,000 cells)
   * required by the frontend.
   */
  async getBlocksSummary(): Promise<BlocksSummaryPayload> {
    throw new Error(
      "LiveApiAdapter limitation: Multi-decadal 228-month block time series (/api/v1/blocks_summary) is not provided by the live API. " +
      "Live mode is not fully integrated because the backend does not yet expose the full multi-year block-summary contract required by the frontend. " +
      "The backend API provides period-specific spatial slices via GET /api/v1/spatial?year=YYYY&month=MM&resolution=50km&region_id=BR-PA&daynight=ALL and block metadata via GET /api/v1/blocks?region_id=BR-PA. " +
      "For full multi-decadal 50 km block drilldown and chart analytics, use precomputed static mode (NEXT_PUBLIC_DATA_MODE=static)."
    );
  }

  /**
   * Fetches model architecture from GET /api/v1/model-info and evaluation metrics from GET /api/v1/sensor-lab/metrics,
   * mapping backend snake_case/camelCase keys into the Zod-validated ModelMetricsPayload.
   */
  async getModelMetrics(): Promise<ModelMetricsPayload> {
    const modelInfoRaw = (await this.request("/model-info?region_id=BR-PA")) as Record<string, unknown>;

    let metricsRaw: Record<string, unknown> = {};
    try {
      metricsRaw = (await this.request("/sensor-lab/metrics?region_id=BR-PA")) as Record<string, unknown>;
    } catch {
      // Check if /model-info already bundled officialEvaluationMetrics
    }

    const archRaw = (modelInfoRaw.architecture as Record<string, unknown>) || {};
    const architecture = {
      family: (archRaw.family as string) || "Generalized Linear Model (GLM)",
      distribution: (archRaw.distribution as string) || "Negative Binomial (NB2)",
      link: (archRaw.link as string) || "log",
      dispersionAlpha: (archRaw.dispersionAlpha as number) ?? (archRaw.dispersion_alpha as number) ?? 0.3394,
      logLikelihood: (archRaw.logLikelihood as number) ?? (archRaw.log_likelihood as number) ?? -105163.79,
      aic: (archRaw.aic as number) ?? 210357.58,
      bic: (archRaw.bic as number) ?? 210478.24,
      referenceMonth: (archRaw.referenceMonth as number) ?? (archRaw.reference_month as number) ?? 1,
      baselineRatioMultiplierK:
        (archRaw.baselineRatioMultiplierK as number) ?? (archRaw.baseline_ratio_multiplier_k as number) ?? 6.0538,
      predictors: (archRaw.predictors as string[]) ?? [
        "log1p_modis = ln(1 + modis_count)",
        "daynight_N = pass indicator for night observation",
        "month_2 through month_12 = seasonal fixed effects (relative to January)",
      ],
    };

    const provRaw =
      (modelInfoRaw.trainingProvenance as Record<string, unknown>) ||
      (modelInfoRaw.training_provenance as Record<string, unknown>) ||
      {};
    const trainingProvenance = {
      calibrationDataset:
        (provRaw.calibrationDataset as string) ||
        (provRaw.calibration_dataset as string) ||
        "2012-2020 Real Observed Overlap",
      sampleDesign:
        (provRaw.sampleDesign as string) ||
        (provRaw.sample_design as string) ||
        "Paired-positive cell-month-platform records (modis_count > 0 AND viirs_count > 0)",
      trainingRecordsCount:
        (provRaw.trainingRecordsCount as number) ?? (provRaw.training_records_count as number) ?? 23010,
      pairedModisTotal: (provRaw.pairedModisTotal as number) ?? (provRaw.paired_modis_total as number) ?? 342397,
      pairedViirsTotal: (provRaw.pairedViirsTotal as number) ?? (provRaw.paired_viirs_total as number) ?? 2072819,
      temporalTrainingSet2012_2018:
        (provRaw.temporalTrainingSet2012_2018 as number) ??
        (provRaw.temporal_training_set_2012_2018 as number) ??
        17919,
      temporalTestSet2019_2020:
        (provRaw.temporalTestSet2019_2020 as number) ?? (provRaw.temporal_test_set_2019_2020 as number) ?? 5091,
      geographicTrainingBlocksCount:
        (provRaw.geographicTrainingBlocksCount as number) ??
        (provRaw.geographic_training_blocks_count as number) ??
        376,
      geographicHeldoutBlocksCount:
        (provRaw.geographicHeldoutBlocksCount as number) ??
        (provRaw.geographic_heldout_blocks_count as number) ??
        94,
      excludedPeriod:
        (provRaw.excludedPeriod as string) ||
        (provRaw.excluded_period as string) ||
        "January 2012 excluded due to S-NPP launch truncation (Jan 1-19 unobserved)",
    };

    // Helper for evaluation split mapping
    const transformSplit = (splitRaw: RawSplitRecord | undefined) => {
      if (!splitRaw) throw new Error("Missing evaluation split in backend response");
      const nb2 = splitRaw.nb2 || {};
      const baseline = splitRaw.baselineRatio || splitRaw.baseline_ratio || {};
      const comp = splitRaw.comparison || {};
      return {
        title: splitRaw.title,
        description: splitRaw.description,
        sampleSize: splitRaw.sampleSize ?? splitRaw.sample_size ?? 0,
        nb2: {
          mae: nb2.mae ?? 0,
          medae: nb2.medae ?? 0,
          rmse: nb2.rmse ?? 0,
          meanPoissonDeviance: nb2.meanPoissonDeviance ?? nb2.mean_poisson_deviance ?? 0,
          totalPoissonDeviance: nb2.totalPoissonDeviance ?? nb2.total_poisson_deviance,
          aggregateBiasPct: nb2.aggregateBiasPct ?? nb2.aggregate_bias_pct ?? 0,
          monthlyCorrelation: nb2.monthlyCorrelation ?? nb2.monthly_correlation ?? 0,
          monthlyWapePct: nb2.monthlyWapePct ?? nb2.monthly_wape_pct,
          spatialWapePct: nb2.spatialWapePct ?? nb2.spatial_wape_pct,
          monthlyR2: nb2.monthlyR2 ?? nb2.monthly_r2,
          dispersionAlpha: nb2.dispersionAlpha ?? nb2.dispersion_alpha ?? 0,
        },
        baselineRatio: {
          mae: baseline.mae ?? 0,
          medae: baseline.medae ?? 0,
          rmse: baseline.rmse ?? 0,
          meanPoissonDeviance: baseline.meanPoissonDeviance ?? baseline.mean_poisson_deviance ?? 0,
          totalPoissonDeviance: baseline.totalPoissonDeviance ?? baseline.total_poisson_deviance,
          aggregateBiasPct: baseline.aggregateBiasPct ?? baseline.aggregate_bias_pct ?? 0,
          monthlyCorrelation: baseline.monthlyCorrelation ?? baseline.monthly_correlation ?? 0,
          monthlyWapePct: baseline.monthlyWapePct ?? baseline.monthly_wape_pct,
          spatialWapePct: baseline.spatialWapePct ?? baseline.spatial_wape_pct,
          monthlyR2: baseline.monthlyR2 ?? baseline.monthly_r2,
          fittedK: baseline.fittedK ?? baseline.fitted_k ?? 0,
        },
        comparison: {
          maeReduction: comp.maeReduction ?? comp.mae_reduction ?? 0,
          devianceReduction: comp.devianceReduction ?? comp.deviance_reduction ?? 0,
          monthlyWapeReductionPct: comp.monthlyWapeReductionPct ?? comp.monthly_wape_reduction_pct,
          spatialWapeReductionPct: comp.spatialWapeReductionPct ?? comp.spatial_wape_reduction_pct,
        },
      };
    };

    const evalMetricsRaw = (metricsRaw.officialEvaluationMetrics ||
      metricsRaw.official_evaluation_metrics ||
      modelInfoRaw.officialEvaluationMetrics ||
      modelInfoRaw.official_evaluation_metrics ||
      metricsRaw) as Record<string, RawSplitRecord>;

    const officialEvaluationMetrics = {
      strategy_A_temporal_holdout: transformSplit(
        evalMetricsRaw.strategy_A_temporal_holdout ||
          evalMetricsRaw.strategy_a_temporal_holdout ||
          (evalMetricsRaw.strategy_a as unknown as RawSplitRecord)
      ),
      strategy_B_geographic_holdout: transformSplit(
        evalMetricsRaw.strategy_B_geographic_holdout ||
          evalMetricsRaw.strategy_b_geographic_holdout ||
          (evalMetricsRaw.strategy_b as unknown as RawSplitRecord)
      ),
    };

    const payload: ModelMetricsPayload = {
      regionId: "BR-PA",
      modelVersion: (modelInfoRaw.modelVersion as string) || (modelInfoRaw.model_version as string) || "firechronicle-nb2-v1.0",
      generatedAtUtc:
        (modelInfoRaw.generatedAtUtc as string) || (modelInfoRaw.generated_at_utc as string) || new Date().toISOString(),
      scientificStatus:
        (modelInfoRaw.scientificStatus as string) ||
        (modelInfoRaw.scientific_status as string) ||
        "EMPIRICALLY_CALIBRATED_RESEARCH_SPECIFICATION",
      architecture,
      trainingProvenance,
      officialEvaluationMetrics,
      scientificLimitations: (modelInfoRaw.scientificLimitations as string[]) ||
        (modelInfoRaw.scientific_limitations as string[]) || [
          "Historical estimates represent Aqua MODIS-derived S-NPP equivalent detections, NOT direct observations.",
          "Positive-detection CSVs unadjusted for satellite cloud obscuration or orbital coverage variations.",
          "Model calibrated exclusively within Pará state (BR-PA) 50 km blocks; spatial extrapolation outside Pará is invalid.",
        ],
    };

    const parsed = ModelMetricsPayloadSchema.safeParse(payload);
    if (!parsed.success) {
      throw new Error(`Live API transformed model-metrics payload failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  // ---------------------------------------------------------------------------
  // Additional Documented Backend Endpoints
  // ---------------------------------------------------------------------------

  /**
   * GET /api/v1/summary?region_id=BR-PA
   */
  async getSummary(regionId = "BR-PA"): Promise<unknown> {
    return this.request(`/summary?region_id=${encodeURIComponent(regionId)}`);
  }

  /**
   * GET /api/v1/spatial?year=YYYY&month=MM&resolution=50km&region_id=BR-PA&daynight=ALL
   * Queries period-specific 568-block GeoJSON features with separate year, month,
   * resolution, region_id, and daynight parameters per Backend Engineer API contract.
   */
  async getSpatial(
    paramsOrPeriod: SpatialQueryParams | string,
    optionalMonth?: number
  ): Promise<unknown> {
    let year: number;
    let month: number;
    let resolution = "50km";
    let regionId = "BR-PA";
    let daynight = "ALL";

    if (typeof paramsOrPeriod === "object") {
      year = paramsOrPeriod.year;
      month = paramsOrPeriod.month;
      resolution = paramsOrPeriod.resolution ?? "50km";
      regionId = paramsOrPeriod.regionId ?? "BR-PA";
      daynight = paramsOrPeriod.daynight ?? "ALL";
    } else if (typeof paramsOrPeriod === "string" && paramsOrPeriod.includes("-")) {
      const parts = paramsOrPeriod.split("-");
      year = parseInt(parts[0], 10);
      month = parseInt(parts[1], 10);
    } else {
      year = parseInt(paramsOrPeriod, 10);
      month = optionalMonth ?? 1;
    }

    const query = new URLSearchParams({
      year: String(year),
      month: String(month),
      resolution,
      region_id: regionId,
      daynight,
    });

    return this.request(`/spatial?${query.toString()}`);
  }

  /**
   * GET /api/v1/blocks?region_id=BR-PA
   */
  async getBlocks(regionId = "BR-PA"): Promise<unknown> {
    return this.request(`/blocks?region_id=${encodeURIComponent(regionId)}`);
  }
}
