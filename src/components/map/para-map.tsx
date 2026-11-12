"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap, MapMouseEvent, ErrorEvent as MapLibreErrorEvent } from "maplibre-gl";
import { AlertCircle, LocateFixed, Minus, Plus, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataState } from "@/components/ui/data-state";
import { MAP_IDS, highlightBlock, syncMapLayers } from "@/lib/map/map-layers";
import type { resolveMapData } from "@/lib/map/verified-data";
import type { FrozenBoundary } from "@/types/map-data";
import { focusPara, PARA_CAMERA } from "@/lib/map/map-camera";

export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/dark";

type Props = {
  data: ReturnType<typeof resolveMapData>;
  selectedBlock: string | null;
  onSelectBlock: (blockId: string) => void;
  blockValues?: Record<string, number | null> | null;
  era?: "estimated" | "observed" | null;
};

export default function ParaMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const latest = useRef(props);
  const framedGeometry = useRef<FrozenBoundary["geojson"] | null | undefined>(undefined);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [issue, setIssue] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [hoveredBlock, setHoveredBlock] = useState<string | null>(null);

  useEffect(() => { latest.current = props; }, [props]);

  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;

    async function initialize() {
      const { Map, AttributionControl, ScaleControl, setWorkerUrl } = await import("maplibre-gl");
      if (disposed || !container.current) return;
      // MapLibre v6 ESM needs an explicit worker asset under Next/Turbopack.
      setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString());
      const map = new Map({
        container: container.current,
        style: BASEMAP_STYLE,
        ...PARA_CAMERA,
        minZoom: 2,
        maxZoom: 16,
        renderWorldCopies: false,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        cooperativeGestures: false,
        canvasContextAttributes: { antialias: false },
      });
      mapRef.current = map;
      cleanup = () => { map.remove(); if (mapRef.current === map) mapRef.current = null; };
      map.addControl(new AttributionControl({ compact: true }), "bottom-right");
      map.addControl(new ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-left");
      map.getCanvas().setAttribute("aria-label", "Interactive contextual map centered on Pará. Use arrow keys to pan and plus or minus to zoom. Analytical selection requires verified blocks.");
      const styles = getComputedStyle(document.documentElement);
      const colors = {
        green: styles.getPropertyValue("--amazon").trim(),
        amber: styles.getPropertyValue("--hotspot").trim(),
        text: styles.getPropertyValue("--foreground").trim(),
        border: styles.getPropertyValue("--input").trim(),
      };
      const onLoad = () => {
        if (disposed) return;
        syncMapLayers(map, latest.current.data, colors, latest.current.blockValues, latest.current.era);
        highlightBlock(map, MAP_IDS.selection, latest.current.selectedBlock);
        // Apply once after style loading and resize, even without a boundary.
        // Subsequent data/selection updates must not reset a user's camera.
        focusPara(map, latest.current.data.boundary);
        framedGeometry.current = latest.current.data.boundary?.geojson ?? null;
        setStatus("ready");
      };
      const onError = (event: MapLibreErrorEvent) => {
        if (disposed) return;
        if (process.env.NODE_ENV !== "production") console.warn("FireChronicle basemap resource:", event.error.message);
        setIssue("Some basemap resources could not be loaded. Check your connection and retry the map.");
        if (!map.isStyleLoaded()) setStatus("error");
      };
      const onContextLost = (event: Event) => {
        event.preventDefault();
        if (!disposed) { setStatus("error"); setIssue("Map rendering was interrupted. Retry to restore the WebGL view."); }
      };
      function hitBlock(event: MapMouseEvent): string | null {
        const data = latest.current.data;
        if (!data.boundary || !data.blocks || !map.getLayer(MAP_IDS.blockFill)) return null;
        // Rendered official polygon hit-test, never a bounding box or derived grid.
        const hits = map.queryRenderedFeatures(event.point, { layers: [MAP_IDS.boundaryFill, MAP_IDS.blockFill] });
        if (!hits.some(f => f.layer.id === MAP_IDS.boundaryFill)) return null;
        const id = hits.find(f => f.layer.id === MAP_IDS.blockFill)?.properties?.block_id;
        return typeof id === "string" && data.blocks.geojson.features.some(f => f.properties.block_id === id) ? id : null;
      }
      let previousHover: string | null = null;
      const onMove = (event: MapMouseEvent) => {
        const id = hitBlock(event);
        if (id === previousHover) return;
        previousHover = id;
        highlightBlock(map, MAP_IDS.hover, id);
        map.getCanvas().style.cursor = id ? "pointer" : "";
        setHoveredBlock(id);
      };
      const onClick = (event: MapMouseEvent) => {
        const id = hitBlock(event);
        if (id) latest.current.onSelectBlock(id);
      };
      const clearHover = () => {
        previousHover = null;
        highlightBlock(map, MAP_IDS.hover, null);
        map.getCanvas().style.cursor = "";
        if (!disposed) setHoveredBlock(null);
      };
      map.on("load", onLoad);
      map.on("error", onError);
      map.on("mousemove", onMove);
      map.on("click", onClick);
      const canvas = map.getCanvas();
      canvas.addEventListener("mouseleave", clearHover);
      canvas.addEventListener("webglcontextlost", onContextLost);
      const resizeObserver = new ResizeObserver(() => { if (!disposed) map.resize(); });
      resizeObserver.observe(container.current);
      cleanup = () => {
        resizeObserver.disconnect();
        canvas.removeEventListener("mouseleave", clearHover);
        canvas.removeEventListener("webglcontextlost", onContextLost);
        map.off("load", onLoad);
        map.off("error", onError);
        map.off("mousemove", onMove);
        map.off("click", onClick);
        map.remove();
        if (mapRef.current === map) mapRef.current = null;
      };
    }

    initialize().catch(() => {
      if (!disposed) { setStatus("error"); setIssue("The map could not start. WebGL and access to the basemap service are required."); }
    });
    return () => { disposed = true; cleanup?.(); };
  }, [retry]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== "ready" || !map.getLayer(MAP_IDS.boundaryFill)) return;
    const styles = getComputedStyle(document.documentElement);
    syncMapLayers(
      map,
      props.data,
      {
        green: styles.getPropertyValue("--amazon").trim(),
        amber: styles.getPropertyValue("--hotspot").trim(),
        text: styles.getPropertyValue("--foreground").trim(),
        border: styles.getPropertyValue("--input").trim(),
      },
      props.blockValues,
      props.era
    );
  }, [props.data, props.blockValues, props.era, status]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && status === "ready") highlightBlock(map, MAP_IDS.selection, props.selectedBlock);
  }, [props.selectedBlock, status]);

  useEffect(() => {
    const map = mapRef.current;
    const geometry = props.data.boundary?.geojson ?? null;
    if (!map || status !== "ready" || framedGeometry.current === geometry) return;
    focusPara(map, props.data.boundary);
    framedGeometry.current = geometry;
  }, [props.data.boundary, status]);

  function resetView() {
    const map = mapRef.current;
    if (!map) return;
    focusPara(map, props.data.boundary);
  }
  function retryMap() { setStatus("loading"); setIssue(null); setRetry(value => value + 1); }

  return <div className="fc-map relative h-[440px] bg-background sm:h-[480px] 2xl:h-[560px]" aria-label="Interactive Pará basemap" aria-busy={status === "loading"}>
    <div ref={container} className="absolute inset-0" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
    <div className="absolute top-3 right-3 z-10 flex flex-col gap-1 rounded-lg border border-border bg-card p-1 shadow-panel" role="group" aria-label="Map navigation">
      <Button variant="ghost" size="icon" className="size-11" disabled={status !== "ready"} aria-label="Zoom in" onClick={() => mapRef.current?.zoomIn({ duration: 0 })}><Plus /></Button>
      <Button variant="ghost" size="icon" className="size-11" disabled={status !== "ready"} aria-label="Zoom out" onClick={() => mapRef.current?.zoomOut({ duration: 0 })}><Minus /></Button>
      <Button variant="ghost" size="icon" className="size-11" disabled={status !== "ready"} aria-label="Reset view to Pará" onClick={resetView}><LocateFixed /></Button>
    </div>
    {status === "loading" && <div className="pointer-events-none absolute top-3 left-3 max-w-[calc(100%-96px)] rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground" role="status">Loading contextual basemap…</div>}
    {status === "error" && <div className="absolute inset-0 flex items-center justify-center bg-background/90 p-4"><DataState state="error" title="The basemap is unavailable." description={issue ?? "Map rendering could not start."} onRetry={retryMap} /></div>}
    {issue && status !== "error" && <div className="absolute top-3 left-3 max-w-[calc(100%-96px)] rounded-lg border border-border bg-card p-3 text-xs"><p className="flex gap-2 text-muted-foreground" role="alert"><AlertCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />{issue}</p><Button variant="ghost" className="mt-2 h-11" onClick={retryMap}><RotateCcw />Retry basemap</Button></div>}
    {hoveredBlock && status === "ready" && (
      <div className="pointer-events-none absolute top-3 left-3 max-w-[calc(100%-96px)] rounded-md border border-border bg-card/95 px-3 py-2 font-mono text-xs shadow-md">
        <div className="font-semibold text-foreground">Block {hoveredBlock}</div>
        <div className="text-[11px] text-muted-foreground">
          {props.blockValues && props.blockValues[hoveredBlock] !== undefined && props.blockValues[hoveredBlock] !== null
            ? `${Math.round(props.blockValues[hoveredBlock]!).toLocaleString()} detections (${props.era === "estimated" ? "Estimated VIIRS-eq" : "Observed VIIRS"})`
            : "No recorded detections / NULL"}
        </div>
      </div>
    )}
    <p className="sr-only">Basemap geography is contextual. Only verified supported block polygons can update analytical selection. Keyboard users may use the supported-block selector below the map.</p>
  </div>;
}
