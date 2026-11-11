// Presentation types only. Public FastAPI envelopes remain provisional.
export type DataLayer = "observed" | "estimated" | "provisional";
export type PanelState = "pending" | "loading" | "empty" | "error" | "unsupported";

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
// Navigation bounds, not a claim of processed or supported observations.
export const FIRST_YEAR = 2002;
export const LAST_YEAR = 2026;

export const LAYERS: Record<DataLayer, { label: string; description: string; source: string; scale: string }> = {
  observed: { label: "Observed", description: "Observed · S-NPP", source: "VIIRS S-NPP · finalized archive", scale: "Pending observed geometry" },
  estimated: { label: "Estimated", description: "Estimated · historical extrapolation", source: "Historical Aqua MODIS → S-NPP-equivalent", scale: "50 km model calibration blocks" },
  provisional: { label: "Provisional", description: "Provisional · NRT", source: "VIIRS S-NPP · near-real-time", scale: "Pending observed geometry" },
};

export function isEraCompatible(year: number, layer: DataLayer) {
  return layer === "estimated" ? year < 2012 : year >= 2012;
}
