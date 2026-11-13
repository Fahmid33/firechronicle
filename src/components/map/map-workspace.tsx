"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo } from "react";
import { Info, MapPin, ShieldCheck } from "lucide-react";
import { useSelection } from "@/store/selection-store";
import { MONTHS, isEraCompatible } from "@/types/explorer";
import { PENDING_MAP_DATA, type MapData } from "@/types/map-data";
import { resolveMapData } from "@/lib/map/verified-data";
import { useMapData, useBlocksSummary } from "@/lib/api/queries";
import { LayerControls } from "@/components/map/layer-controls";
import { ScienceStatus } from "@/components/ui/science-status";
import { DataState } from "@/components/ui/data-state";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ParaMap = dynamic(() => import("@/components/map/para-map"), {
  ssr: false,
  loading: () => <div className="flex h-[440px] items-center justify-center bg-background sm:h-[480px] 2xl:h-[560px]"><DataState state="loading" title="Opening the Pará map" description="Loading the interactive map engine." /></div>,
});

export function MapWorkspace({ data }: { data?: MapData }) {
  const { data: fetchedMapData } = useMapData();
  const { data: blocksSummary } = useBlocksSummary();
  const effectiveData = data ?? fetchedMapData ?? PENDING_MAP_DATA;
  const year = useSelection(s => s.year);
  const month = useSelection(s => s.month);
  const layer = useSelection(s => s.activeLayer);
  const block = useSelection(s => s.block_id);
  const setBlock = useSelection(s => s.setBlock);
  const setLayer = useSelection(s => s.setLayer);
  const resolved = useMemo(() => resolveMapData(effectiveData, year, month, layer), [effectiveData, year, month, layer]);
  const compatible = isEraCompatible(year, layer);
  const blockIds = useMemo(() => resolved.blocks?.geojson.features.map(f => f.properties.block_id) ?? [], [resolved.blocks]);
  const selectedBlock = block && blockIds.includes(block) ? block : null;
  const overlay = resolved.hotspots ?? resolved.aggregates;

  const periodKey = `${year}-${String(month).padStart(2, "0")}`;
  const periodIdx = blocksSummary?.periods ? blocksSummary.periods.indexOf(periodKey) : -1;
  const blockValues = useMemo(() => {
    if (!blocksSummary || periodIdx === -1) return null;
    const map: Record<string, number | null> = {};
    for (const [id, item] of Object.entries(blocksSummary.blocks)) {
      map[id] = item.values[periodIdx] ?? null;
    }
    return map;
  }, [blocksSummary, periodIdx]);
  const era = year < 2012 ? "estimated" : "observed";

  useEffect(() => {
    if (!block) return;
    if (!resolved.boundary || !resolved.blocks || !blockIds.includes(block)) {
      setBlock(null);
      return;
    }
    const coverage = resolved.blocks.coverage?.find(c => c.blockId === block && c.year === year && c.month === month && c.layer === layer)?.status ?? null;
    setBlock(block, { sourceLabel: resolved.blocks.sourceLabel, boundaryVersion: resolved.boundary.version, coverageStatus: coverage, year, month, layer });
  }, [block, blockIds, resolved.boundary, resolved.blocks, year, month, layer, setBlock]);

  function selectBlock(id: string) {
    if (!resolved.boundary || !resolved.blocks || !blockIds.includes(id)) return;
    const coverage = resolved.blocks.coverage?.find(c => c.blockId === id && c.year === year && c.month === month && c.layer === layer)?.status ?? null;
    setBlock(id, { sourceLabel: resolved.blocks.sourceLabel, boundaryVersion: resolved.boundary.version, coverageStatus: coverage, year, month, layer });
  }

  return <section className="overflow-hidden rounded-xl border border-border bg-card" aria-label="Pará map workspace">
    <LayerControls provisionalAvailable={resolved.provisionalAvailable} />
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
      <p className="flex items-center gap-2 text-sm font-medium"><MapPin className="size-4 text-primary" aria-hidden="true" />Pará, Brazil</p>
      <p className="text-xs text-muted-foreground">{resolved.boundary ? `Official IBGE boundary · ${resolved.boundary.version}` : "Official Pará boundary pending"}</p>
    </div>
    <ParaMap
      data={resolved}
      selectedBlock={selectedBlock}
      onSelectBlock={selectBlock}
      blockValues={blockValues}
      era={era}
    />
    <div className="space-y-3 border-t border-border p-4">
      {/* Quantitative Choropleth Legend */}
      <div className="rounded-lg border border-border bg-card/60 p-3 text-xs space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-medium text-foreground">
            50 km Block Quantities ({era === "estimated" ? "Estimated VIIRS-equivalent" : "Observed S-NPP VIIRS"})
          </span>
          <span className="text-[11px] text-muted-foreground font-mono">
            {MONTHS[month - 1]} {year}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <div className="flex items-center gap-1.5">
            <span className="size-3.5 rounded border border-border bg-muted/20" />
            <span className="text-muted-foreground">Unobserved / NULL</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="size-3.5 rounded"
              style={{ backgroundColor: era === "estimated" ? "#b45309" : "#047857" }}
            />
            <span className="text-muted-foreground">1–10</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="size-3.5 rounded"
              style={{ backgroundColor: era === "estimated" ? "#d97706" : "#059669" }}
            />
            <span className="text-muted-foreground">11–50</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="size-3.5 rounded"
              style={{ backgroundColor: era === "estimated" ? "#f59e0b" : "#10b981" }}
            />
            <span className="text-muted-foreground">51–200</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="size-3.5 rounded"
              style={{ backgroundColor: era === "estimated" ? "#fbbf24" : "#34d399" }}
            />
            <span className="text-muted-foreground">201–1,000</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="size-3.5 rounded"
              style={{ backgroundColor: era === "estimated" ? "#fef08a" : "#a7f3d0" }}
            />
            <span className="text-muted-foreground">&gt;1,000</span>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground/80 pt-1">
          Colors indicate total monthly hotspot detections within each canonical 50 km block. Missing passes remain neutral (not zero). No 10 km precision is fabricated.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3"><ScienceStatus layer={layer} /><span className="text-xs text-muted-foreground" aria-live="polite">Requested period · {MONTHS[month - 1]} {year}</span></div>
      {!compatible && <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-background p-3 text-xs"><p className="text-muted-foreground">Unsupported layer for this era. The contextual basemap remains available.</p><Button variant="outline" className="h-11" onClick={() => setLayer(year < 2012 ? "estimated" : "observed")}>Use {year < 2012 ? "Estimated" : "Observed"} layer</Button></div>}
      {resolved.rejected && <p className="text-xs text-destructive" role="alert">Supplied geographic data could not be verified. Analytical layers and selection remain unavailable.</p>}
      <div className="flex flex-wrap items-center gap-3">
        {blockIds.length > 0 ? <><span id="block-label" className="text-xs text-muted-foreground">Supported 50 km block</span><Select value={selectedBlock} onValueChange={id => id && selectBlock(id)}><SelectTrigger aria-labelledby="block-label" className="h-11 min-w-40 data-[size=default]:h-11"><SelectValue placeholder="Choose a block" /></SelectTrigger><SelectContent alignItemWithTrigger={false}>{blockIds.map(id => <SelectItem key={id} value={id} className="min-h-11">{id}</SelectItem>)}</SelectContent></Select>{selectedBlock && <Button className="h-11" variant="ghost" onClick={() => setBlock(null)}>Clear selection</Button>}</> : <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground"><ShieldCheck className="size-4 shrink-0 text-primary" aria-hidden="true" />Selection unavailable · verified 50 km block polygons have not arrived.</p>}
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{overlay ? `${overlay.sourceLabel} · ${overlay.resolutionLabel} · coverage: ${overlay.coverageStatus ?? "Not supplied"}. Quantitative 50 km block choropleth active.` : (compatible && periodIdx !== -1 ? `50 km canonical grid (${blockIds.length} blocks) · Quantitative choropleth active for ${MONTHS[month - 1]} ${year}.` : "No scientific records loaded for this period. Coverage and detection counts remain unknown.")}</p>
      <p className="text-xs leading-relaxed text-muted-foreground">Basemap: <a className="rounded underline underline-offset-2 hover:text-foreground" href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · © <a className="rounded underline underline-offset-2 hover:text-foreground" href="https://openmaptiles.org/" target="_blank" rel="noreferrer">OpenMapTiles</a> · Data from <a className="rounded underline underline-offset-2 hover:text-foreground" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a></p>
      <div className="flex gap-2 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground"><Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><p>Basemap borders are geographic context, not the frozen study polygon. Historical estimates remain at 50 km. Panning outside Pará does not enable analysis.</p></div>
    </div>
  </section>;
}
