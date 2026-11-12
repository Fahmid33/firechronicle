import type { IDataClient, DataSourceMode } from "@/types/scientific-data";
import { StaticJsonAdapter } from "./adapters/static-adapter";
import { LiveApiAdapter } from "./adapters/live-adapter";
import { MockAdapter } from "./adapters/mock-adapter";

export * from "./adapters/static-adapter";
export * from "./adapters/live-adapter";
export * from "./adapters/mock-adapter";

export function resolveClientMode(): DataSourceMode {
  const envMocks = process.env.NEXT_PUBLIC_USE_MOCKS?.toLowerCase();
  if (envMocks === "true" || envMocks === "mock") {
    return "mock";
  }
  if (envMocks === "live" || (envMocks === "false" && process.env.NEXT_PUBLIC_API_BASE_URL)) {
    return "live";
  }
  // Default for production demo: Verified Precomputed Static JSON
  return "static";
}

export function createDataClient(modeOverride?: DataSourceMode): IDataClient {
  const mode = modeOverride || resolveClientMode();
  switch (mode) {
    case "mock":
      return new MockAdapter();
    case "live":
      return new LiveApiAdapter();
    case "static":
    default:
      return new StaticJsonAdapter();
  }
}

// Default application singleton client
export const dataClient = createDataClient();
