"use client";

import { Layers3 } from "lucide-react";
import { useSelection } from "@/store/selection-store";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LayerMark } from "@/components/ui/science-status";
import { LAYERS, type DataLayer } from "@/types/explorer";

const LAYER_STATUS_DESCRIPTIONS: Record<DataLayer, string> = {
  estimated: "Historical Aqua MODIS → NB2 v1.0 · precomputed 50 km estimates connected",
  observed: "VIIRS S-NPP · verified 2012–2020 archive connected",
  provisional: "VIIRS S-NPP · near-real-time · layer pending live API",
};

export function LayerControls({ provisionalAvailable = false }: { provisionalAvailable?: boolean }) {
  const layer = useSelection(s => s.activeLayer);
  const setLayer = useSelection(s => s.setLayer);
  return <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
    <h2 className="flex items-center gap-2 text-sm font-medium"><Layers3 className="size-4 text-muted-foreground" aria-hidden="true" />Data layers</h2>
    <Tabs value={layer} onValueChange={v => { if (v === "observed" || v === "estimated" || v === "provisional") setLayer(v); }}>
      <TabsList aria-label="Requested data layer" className="h-auto! max-w-full flex-wrap gap-1 bg-background p-1">
        {(Object.keys(LAYERS) as DataLayer[]).map(key => <TabsTrigger key={key} value={key} disabled={key === "provisional" && !provisionalAvailable} className="h-10! gap-2 px-3 text-xs data-active:border-input data-active:bg-surface-elevated"><LayerMark layer={key} />{LAYERS[key].label}</TabsTrigger>)}
      </TabsList>
      {(Object.keys(LAYERS) as DataLayer[]).map(key => <TabsContent key={key} value={key} className="max-w-sm px-1 text-xs text-muted-foreground">{LAYER_STATUS_DESCRIPTIONS[key]}</TabsContent>)}
      {!provisionalAvailable && <p className="max-w-sm px-1 text-xs text-muted-foreground">Provisional NRT unavailable in static demo mode · live backend required.</p>}
    </Tabs>
  </div>;
}
