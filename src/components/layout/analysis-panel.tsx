"use client";

import Link from "next/link";
import { ArrowUpRight, FileText, Info, LocateFixed, SlidersHorizontal } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useSelection } from "@/store/selection-store";
import { LAYERS, MONTHS, isEraCompatible } from "@/types/explorer";
import { ScienceStatus } from "@/components/ui/science-status";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export function AnalysisPanel() {
  const year = useSelection(s => s.year);
  const month = useSelection(s => s.month);
  const block = useSelection(s => s.block_id);
  const layer = useSelection(s => s.activeLayer);
  const blockMetadata = useSelection(s => s.blockMetadata);
  const metadata = blockMetadata?.year === year && blockMetadata.month === month && blockMetadata.layer === layer ? blockMetadata : null;
  const compatible = isEraCompatible(year, layer);
  const count: number | null = null;
  return <div className="flex h-full flex-col rounded-xl border border-border bg-card">
    <div className="flex items-center justify-between border-b border-border p-4"><h2 className="text-sm font-medium">Selection overview</h2><LocateFixed className="size-4 text-muted-foreground" aria-hidden="true" /></div>
    <div className="space-y-6 p-5">
      <div><p className="mb-2 text-xs tracking-wider text-muted-foreground uppercase">Study region</p><h3 className="text-xl font-medium">Pará, Brazil</h3><p className="mt-1 font-mono text-xs text-muted-foreground">BR-PA <span className="px-1">/</span> {block ?? "No block selected"}</p></div>
      <dl className="space-y-4 text-sm">
        <div><dt className="text-xs text-muted-foreground">Selected period</dt><dd className="mt-1 font-medium tabular-nums">{MONTHS[month - 1]} {year}</dd></div>
        <div><dt className="mb-2 text-xs text-muted-foreground">Requested layer</dt><dd><ScienceStatus layer={layer} /></dd></div>
        <div className="rounded-lg border border-border bg-background/50 p-4"><dt className="text-xs text-muted-foreground">Hotspot detection count</dt><dd className="mt-2 text-[28px] leading-9 tabular-nums">{count ?? "—"}</dd><dd className="mt-1 text-xs text-muted-foreground">{compatible ? "Awaiting data · availability unknown" : "Unsupported layer for this period"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Measurement</dt><dd className="mt-1 leading-relaxed">{layer === "estimated" ? "VIIRS S-NPP-equivalent hotspot detections" : "Recorded VIIRS S-NPP hotspot detections"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Spatial resolution</dt><dd className="mt-1">{LAYERS[layer].scale}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Expected source</dt><dd className="mt-1 leading-relaxed">{LAYERS[layer].source}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Selected-block coverage</dt><dd className="mt-1">{metadata?.coverageStatus ?? "Not supplied"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Block geometry source</dt><dd className="mt-1 leading-relaxed">{metadata?.sourceLabel ?? "Not supplied"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Selected boundary version</dt><dd className="mt-1">{metadata?.boundaryVersion ?? "Not supplied"}</dd></div>
      </dl>
      <div className="flex gap-2 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground"><Info className="mt-0.5 size-4 shrink-0 text-hotspot" aria-hidden="true" /><p>Coverage has not been supplied. Missing values remain unknown; a missing record is not evidence of zero activity.</p></div>
      <details className="border-t border-border pt-4 text-xs"><summary className="cursor-pointer rounded py-2 text-muted-foreground hover:text-foreground">Data provenance <FileText className="ml-1 inline size-3" aria-hidden="true" /></summary><dl className="mt-3 space-y-3 text-muted-foreground">{["Dataset / processing version", "Boundary version", "Model version", "Acquisition time (UTC)"].map(label => <div key={label}><dt>{label}</dt><dd className="mt-1 text-foreground">Not supplied</dd></div>)}</dl></details>
    </div>
    <Link href="/methodology" className="mt-auto flex min-h-12 items-center justify-between border-t border-border px-5 text-xs text-primary hover:bg-accent">Understand the measurement<ArrowUpRight className="size-4" aria-hidden="true" /></Link>
  </div>;
}

export function AnalysisLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <>
    <div className="mb-3 hidden justify-end md:flex xl:hidden"><Sheet open={open} onOpenChange={setOpen}><SheetTrigger render={<Button variant="outline" className="h-11 border-input" />}><SlidersHorizontal />Selection overview</SheetTrigger><SheetContent className="w-[min(360px,95vw)] overflow-y-auto"><SheetHeader><SheetTitle>Selection overview</SheetTitle><SheetDescription>Period, source and scientific context</SheetDescription></SheetHeader><div className="px-3 pb-4"><AnalysisPanel /></div></SheetContent></Sheet></div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"><div className="min-w-0 space-y-4">{children}</div><aside aria-label="Selected area analysis" className="md:hidden xl:block"><AnalysisPanel /></aside></div>
  </>;
}
