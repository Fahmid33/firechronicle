import type { FeatureCollection, Geometry, Position } from "geojson";
import { z } from "zod";
import type { MapData, FrozenBoundary } from "@/types/map-data";
import type { DataLayer } from "@/types/explorer";
import { isEraCompatible } from "@/types/explorer";

const position = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)]);
const ring = z.array(position).min(4).refine(r => r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1], "Polygon rings must be closed");
const area = z.discriminatedUnion("type", [
  z.object({ type: z.literal("Polygon"), coordinates: z.array(ring).min(1) }),
  z.object({ type: z.literal("MultiPolygon"), coordinates: z.array(z.array(ring).min(1)).min(1) }),
]);
const point = z.object({ type: z.literal("Point"), coordinates: position });
const collection = (geometry: typeof area | typeof point) => z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(z.object({ type: z.literal("Feature"), geometry, properties: z.record(z.string(), z.unknown()).nullable() })),
});

export function boundaryIsUsable(boundary: FrozenBoundary | null): boundary is FrozenBoundary {
  if (!boundary || boundary.regionId !== "BR-PA" || boundary.approvedByDataOwner !== true || boundary.crs !== "EPSG:4326") return false;
  if (!collection(area).safeParse(boundary.geojson).success) return false;
  try {
    const host = new URL(boundary.sourceUrl).hostname;
    if (host !== "ibge.gov.br" && !host.endsWith(".ibge.gov.br")) return false;
  } catch { return false; }
  return Boolean(boundary.version && boundary.sourceLabel && boundary.releaseYear && boundary.processingDate && boundary.edgePolicy && boundary.geojson.features.length);
}

// Bounds are for camera framing only. They NEVER decide geographic membership.
export function geometryBounds(data: FeatureCollection<Geometry>): [[number, number], [number, number]] | null {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  function visit(coords: unknown) {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      const [lng, lat] = coords as Position;
      west = Math.min(west, lng); east = Math.max(east, lng);
      south = Math.min(south, lat); north = Math.max(north, lat);
    } else coords.forEach(visit);
  }
  data.features.forEach(f => { if ("coordinates" in f.geometry) visit(f.geometry.coordinates); });
  return Number.isFinite(west) ? [[west, south], [east, north]] : null;
}

export function resolveMapData(data: MapData, year: number, month: number, layer: DataLayer) {
  const boundary = boundaryIsUsable(data.boundary) ? data.boundary : null;
  const blocks = data.blocks;
  const validBlocks = Boolean(boundary && blocks && blocks.regionId === "BR-PA" && blocks.approvedByDataOwner === true && blocks.boundaryVersion === boundary.version && blocks.calibrationScaleKm === 50 && blocks.clippedToStudyBoundary === true && blocks.sourceLabel && collection(area).safeParse(blocks.geojson).success && blocks.geojson.features.every(f => typeof f.properties?.block_id === "string" && f.properties.block_id.trim().length > 0) && new Set(blocks.geojson.features.map(f => f.properties.block_id)).size === blocks.geojson.features.length);
  function visibleOverlay<T extends MapData["hotspots"] | MapData["aggregates"]>(overlay: T): T | null {
    if (!boundary || !overlay || overlay.regionId !== "BR-PA" || overlay.approvedByDataOwner !== true || overlay.boundaryVersion !== boundary.version || !overlay.sourceLabel || !overlay.resolutionLabel || overlay.layer !== layer || overlay.year !== year || overlay.month !== month || !isEraCompatible(year, layer)) return null;
    if (layer === "provisional" && overlay.coverageConfirmed !== true) return null;
    const schema = overlay === data.hotspots ? collection(point) : collection(area);
    return schema.safeParse(overlay.geojson).success ? overlay : null;
  }
  // NRT is available only for the exact selected period with confirmed coverage.
  const provisionalAvailable = [data.hotspots, data.aggregates].some(o => o?.layer === "provisional" && o.coverageConfirmed === true && o.year === year && o.month === month && o.regionId === "BR-PA" && o.approvedByDataOwner === true && boundary && o.boundaryVersion === boundary.version && o.sourceLabel && o.resolutionLabel && (o === data.hotspots ? collection(point) : collection(area)).safeParse(o.geojson).success && year >= 2012);
  return {
    boundary,
    blocks: validBlocks ? blocks : null,
    hotspots: visibleOverlay(data.hotspots),
    aggregates: visibleOverlay(data.aggregates),
    provisionalAvailable: Boolean(provisionalAvailable),
    rejected: Boolean((data.boundary && !boundary) || (blocks && !validBlocks)),
  };
}
