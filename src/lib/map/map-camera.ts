import type { Map as MapLibreMap } from "maplibre-gl";
import type { FrozenBoundary } from "@/types/map-data";
import { geometryBounds } from "@/lib/map/verified-data";

// Approximate camera positioning ONLY: this is never scientific geometry.
export const PARA_CAMERA = {
  center: [-52.5, -3.5] as [number, number],
  zoom: 5.2,
  bearing: 0,
  pitch: 0,
};

export function focusPara(map: MapLibreMap, boundary: FrozenBoundary | null) {
  // Camera calculations must use the actual, laid-out viewport.
  map.resize();
  map.stop();
  const bounds = boundary && geometryBounds(boundary.geojson);
  if (bounds) {
    const { clientWidth, clientHeight } = map.getContainer();
    const inset = Math.min(40, Math.max(16, Math.min(clientWidth, clientHeight) * 0.06));
    map.fitBounds(bounds, {
      padding: { top: inset, bottom: inset, left: inset, right: inset + 56 },
      maxZoom: 8,
      bearing: 0,
      pitch: 0,
      duration: 0,
      absolutePadding: false,
    });
  } else {
    map.jumpTo({ ...PARA_CAMERA, padding: { top: 0, bottom: 0, left: 0, right: 0 } });
  }
}
