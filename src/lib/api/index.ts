import type { IDataClient, DataSourceMode } from "@/types/scientific-data";
import { StaticJsonAdapter } from "./adapters/static-adapter";
import { LiveApiAdapter } from "./adapters/live-adapter";
import { MockAdapter } from "./adapters/mock-adapter";

export * from "./adapters/static-adapter";
export * from "./adapters/live-adapter";
export * from "./adapters/mock-adapter";

/**
 * Resolves data client mode with deterministic precedence:
 * 1. NEXT_PUBLIC_DATA_MODE ("static" | "live" | "mock")
 * 2. NEXT_PUBLIC_USE_MOCKS ("true" -> "mock", "live" -> "live", "false" with URL -> "live")
 * 3. Default: "static" (verified real JSON)
 */
export function resolveClientMode(): DataSourceMode {
  const explicitMode = process.env.NEXT_PUBLIC_DATA_MODE?.toLowerCase();
  if (explicitMode === "mock") return "mock";
  if (explicitMode === "live") return "live";
  if (explicitMode === "static") return "static";

  const legacyMocks = process.env.NEXT_PUBLIC_USE_MOCKS?.toLowerCase();
  if (legacyMocks === "true" || legacyMocks === "mock") return "mock";
  if (legacyMocks === "live" || (legacyMocks === "false" && process.env.NEXT_PUBLIC_API_BASE_URL)) return "live";

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
