import type {
  IDataClient,
  DataSourceMode,
  StatewideMonthlyPayload,
  CalendarMatrixPayload,
  BlocksSummaryPayload,
  ModelMetricsPayload,
} from "@/types/scientific-data";
import {
  StatewideMonthlyPayloadSchema,
  CalendarMatrixPayloadSchema,
  BlocksSummaryPayloadSchema,
  ModelMetricsPayloadSchema,
} from "@/types/scientific-data";

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

export class LiveApiAdapter implements IDataClient {
  readonly mode: DataSourceMode = "live";
  readonly isSynthetic: boolean = false;
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  }

  private async request(endpoint: string): Promise<unknown> {
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

  async getStatewideTimeSeries(): Promise<StatewideMonthlyPayload> {
    const raw = await this.request("/timeseries?region_id=BR-PA");
    const parsed = StatewideMonthlyPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Live API timeseries payload failed validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getCalendarMatrix(): Promise<CalendarMatrixPayload> {
    const raw = await this.request("/calendar?region_id=BR-PA");
    const parsed = CalendarMatrixPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Live API calendar payload failed validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getBlocksSummary(): Promise<BlocksSummaryPayload> {
    const raw = await this.request("/harmonized?region_id=BR-PA");
    const parsed = BlocksSummaryPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Live API harmonized blocks payload failed validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getModelMetrics(): Promise<ModelMetricsPayload> {
    const raw = await this.request("/model-info?region_id=BR-PA");
    const parsed = ModelMetricsPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Live API model-info payload failed validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }
}
