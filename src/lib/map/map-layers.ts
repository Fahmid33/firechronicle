import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";
import type { GeoJSON } from "geojson";
import type { resolveMapData } from "@/lib/map/verified-data";

export const MAP_IDS = {
  boundary: "fc-boundary",
  boundaryFill: "fc-boundary-support",
  boundaryLine: "fc-boundary-line",
  blocks: "fc-blocks",
  blockFill: "fc-block-support",
  blockLine: "fc-block-line",
  hover: "fc-block-hover",
  selection: "fc-block-selection",
  hotspots: "fc-hotspots",
  provisionalHotspots: "fc-provisional-hotspots",
  aggregates: "fc-observed-aggregates",
  provisionalAggregates: "fc-provisional-aggregates",
} as const;

const EMPTY = { type: "FeatureCollection", features: [] } as const;

function source(map: MapLibreMap, id: string, data: GeoJSON | null) {
  const existing = map.getSource(id) as GeoJSONSource | undefined;
  if (existing) existing.setData(data ?? { type: "FeatureCollection", features: [] });
  else map.addSource(id, { type: "geojson", data: data ?? { ...EMPTY, features: [] } });
}

// No count ramp or estimated points. Geometry marks indicate selection/support,
// not quantitative activity, certainty, or a finer validated model resolution.
export function syncMapLayers(map: MapLibreMap, data: ReturnType<typeof resolveMapData>, colors: { green: string; amber: string; text: string; border: string }) {
  source(map, MAP_IDS.boundary, data.boundary?.geojson ?? null);
  source(map, MAP_IDS.blocks, data.blocks?.geojson ?? null);
  source(map, MAP_IDS.hotspots, data.hotspots?.layer === "observed" ? data.hotspots.geojson : null);
  source(map, MAP_IDS.provisionalHotspots, data.hotspots?.layer === "provisional" ? data.hotspots.geojson : null);
  source(map, MAP_IDS.aggregates, data.aggregates?.layer === "observed" ? data.aggregates.geojson : null);
  source(map, MAP_IDS.provisionalAggregates, data.aggregates?.layer === "provisional" ? data.aggregates.geojson : null);
  if (map.getLayer(MAP_IDS.boundaryFill)) return;
  map.addLayer({ id: MAP_IDS.boundaryFill, type: "fill", source: MAP_IDS.boundary, paint: { "fill-color": colors.green, "fill-opacity": 0.035 } });
  map.addLayer({ id: MAP_IDS.aggregates, type: "line", source: MAP_IDS.aggregates, paint: { "line-color": colors.green, "line-width": 1 } });
  map.addLayer({ id: MAP_IDS.provisionalAggregates, type: "line", source: MAP_IDS.provisionalAggregates, paint: { "line-color": colors.amber, "line-width": 1, "line-dasharray": [1, 2] } });
  map.addLayer({ id: MAP_IDS.blockFill, type: "fill", source: MAP_IDS.blocks, paint: { "fill-color": colors.border, "fill-opacity": 0.08 } });
  map.addLayer({ id: MAP_IDS.blockLine, type: "line", source: MAP_IDS.blocks, paint: { "line-color": colors.border, "line-width": 1, "line-dasharray": [3, 2] } });
  map.addLayer({ id: MAP_IDS.boundaryLine, type: "line", source: MAP_IDS.boundary, paint: { "line-color": colors.green, "line-width": 2 } });
  for (const [id, color, width] of [[MAP_IDS.hover, colors.text, 2], [MAP_IDS.selection, colors.green, 3]] as const) {
    map.addLayer({ id, type: "line", source: MAP_IDS.blocks, filter: ["==", ["get", "block_id"], ""], paint: { "line-color": color, "line-width": width } });
  }
  map.addLayer({ id: MAP_IDS.hotspots, type: "circle", source: MAP_IDS.hotspots, paint: { "circle-radius": 3, "circle-color": colors.amber, "circle-stroke-color": colors.text, "circle-stroke-width": 0.5 } });
  map.addLayer({ id: MAP_IDS.provisionalHotspots, type: "circle", source: MAP_IDS.provisionalHotspots, paint: { "circle-radius": 4, "circle-opacity": 0, "circle-stroke-color": colors.amber, "circle-stroke-width": 1.5 } });
}

export function highlightBlock(map: MapLibreMap, id: typeof MAP_IDS.hover | typeof MAP_IDS.selection, blockId: string | null) {
  if (map.getLayer(id)) map.setFilter(id, ["==", ["get", "block_id"], blockId ?? ""]);
}
