import type {
  IDataClient,
  DataSourceMode,
  StatewideMonthlyPayload,
  CalendarMatrixPayload,
  BlocksSummaryPayload,
  ModelMetricsPayload,
} from "@/types/scientific-data";
import {
  MOCK_STATEWIDE_PAYLOAD,
  MOCK_CALENDAR_PAYLOAD,
  MOCK_BLOCKS_SUMMARY,
  MOCK_MODEL_METRICS,
} from "@/mocks/fixtures";

export class MockAdapter implements IDataClient {
  readonly mode: DataSourceMode = "mock";
  readonly isSynthetic: boolean = true;

  async getStatewideTimeSeries(): Promise<StatewideMonthlyPayload> {
    return structuredClone(MOCK_STATEWIDE_PAYLOAD);
  }

  async getCalendarMatrix(): Promise<CalendarMatrixPayload> {
    return structuredClone(MOCK_CALENDAR_PAYLOAD);
  }

  async getBlocksSummary(): Promise<BlocksSummaryPayload> {
    return structuredClone(MOCK_BLOCKS_SUMMARY);
  }

  async getModelMetrics(): Promise<ModelMetricsPayload> {
    return structuredClone(MOCK_MODEL_METRICS);
  }
}
