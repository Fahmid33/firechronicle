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

export class StaticJsonAdapter implements IDataClient {
  readonly mode: DataSourceMode = "static";
  readonly isSynthetic: boolean = false;

  private async loadJson(subPath: string): Promise<unknown> {
    if (typeof window === "undefined") {
      // Server-side (Node / Next.js prerender / test)
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      const fullPath = path.join(process.cwd(), "public", "data", subPath);
      const raw = await fs.readFile(fullPath, "utf-8");
      return JSON.parse(raw);
    } else {
      // Client-side (Browser)
      const url = `/data/${subPath}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch static dataset '${url}': HTTP ${res.status}`);
      }
      return res.json();
    }
  }

  async getStatewideTimeSeries(): Promise<StatewideMonthlyPayload> {
    const raw = await this.loadJson("timeseries/statewide_monthly.json");
    const parsed = StatewideMonthlyPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Static statewide time series failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getCalendarMatrix(): Promise<CalendarMatrixPayload> {
    const raw = await this.loadJson("calendar/calendar_matrix.json");
    const parsed = CalendarMatrixPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Static calendar matrix failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getBlocksSummary(): Promise<BlocksSummaryPayload> {
    const raw = await this.loadJson("blocks/blocks_summary.json");
    const parsed = BlocksSummaryPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Static blocks summary failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }

  async getModelMetrics(): Promise<ModelMetricsPayload> {
    const raw = await this.loadJson("sensor_lab/model_metrics.json");
    const parsed = ModelMetricsPayloadSchema.safeParse(raw);
    if (!parsed.success) {
      throw new Error(`Static model metrics failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data;
  }
}
