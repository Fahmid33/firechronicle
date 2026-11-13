"use client";

import Link from "next/link";
import { ArrowUpRight, FileText, Info, LocateFixed, SlidersHorizontal, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useSelection } from "@/store/selection-store";
import { LAYERS, MONTHS, isEraCompatible } from "@/types/explorer";
import { ScienceStatus } from "@/components/ui/science-status";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useStatewideTimeSeries, useBlocksSummary } from "@/lib/api/queries";
import { ExportButton } from "@/components/csv/export-button";

export function AnalysisPanel() {
  const year = useSelection((s) => s.year);
  const month = useSelection((s) => s.month);
  const block = useSelection((s) => s.block_id);
  const layer = useSelection((s) => s.activeLayer);
  const setBlock = useSelection((s) => s.setBlock);
  const blockMetadata = useSelection((s) => s.blockMetadata);
  const metadata =
    blockMetadata?.year === year && blockMetadata.month === month && blockMetadata.layer === layer
      ? blockMetadata
      : null;
  const compatible = isEraCompatible(year, layer);

  const { data: statewide } = useStatewideTimeSeries();
  const { data: blocksSummary } = useBlocksSummary();

  const periodKey = `${year}-${String(month).padStart(2, "0")}`;

  // Retrieve detection count and period metadata
  let count: number | null = null;
  let statusNotice = "Awaiting data · availability unknown";
  let coverageNote = metadata?.coverageStatus ?? "Not supplied";

  if (block && blocksSummary?.blocks[block]) {
    const pIdx = blocksSummary.periods?.indexOf(periodKey) ?? -1;
    if (pIdx !== -1) {
      count = blocksSummary.blocks[block].values[pIdx] ?? null;
      if (year === 2002 && month <= 6) {
        statusNotice = "Pre-commissioning period (Aqua MODIS launched July 2002)";
        coverageNote = "Unsupported period";
      } else if (periodKey === "2002-07") {
        if (count !== null) {
          statusNotice = "Partial commissioning estimate (Aqua MODIS operational July 2002; complete D+N pair)";
          coverageNote = "Complete D+N estimate (operational commissioning month)";
        } else {
          statusNotice = "Incomplete D/N estimates (combined daynight=ALL value remains NULL)";
          coverageNote = "Incomplete D/N estimates; combined value unavailable";
        }
      } else if (periodKey === "2012-01") {
        if (count !== null) {
          statusNotice = "Partial observation (S-NPP launched; Jan 1–19 unobserved)";
          coverageNote = "Partial month coverage";
        } else {
          statusNotice = "Unobserved block (NULL preserved, not zero)";
          coverageNote = "Unobserved / missing record";
        }
      } else if (count !== null) {
        statusNotice =
          year < 2012
            ? "Estimated VIIRS-equivalent (Aqua MODIS → NB2 v1.0; complete D+N pair)"
            : "Recorded S-NPP VIIRS 375m detection count";
        coverageNote =
          year < 2012
            ? "Complete D+N estimate"
            : "Recorded satellite observation (S-NPP VIIRS)";
      } else {
        statusNotice =
          year < 2012
            ? "Incomplete D/N estimates (combined daynight=ALL value remains NULL)"
            : "No detections / unobserved pass (NULL preserved, not zero)";
        coverageNote =
          year < 2012
            ? "Incomplete D/N estimates; combined value unavailable"
            : "Unobserved / missing pass record";
      }
    }
  } else if (statewide?.series) {
    const sw = statewide.series.find((s) => s.period === periodKey);
    if (sw) {
      count = sw.value;
      if (sw.status === "unsupported_period") {
        statusNotice = "Pre-commissioning period (Aqua MODIS launched July 2002)";
        coverageNote = "Unsupported period";
      } else if (periodKey === "2002-07" || (sw.status === "partial_observation" && year === 2002)) {
        statusNotice = "Partial observation (Aqua MODIS operational commissioning month; partial month coverage)";
        const unobservedJuly = 568 - (sw.complete_pairs_count ?? 0) - (sw.single_pass_count ?? 0);
        coverageNote = sw.complete_pairs_count != null
          ? `${sw.available_estimates_count} of ${sw.expected_passes ?? 1136} passes (${sw.complete_pairs_count} complete Day+Night pairs, ${sw.single_pass_count} single-pass; ${unobservedJuly} blocks with no available estimated passes; observation coverage unknown)`
          : "Operational commissioning month (July 2002)";
      } else if (sw.status === "partial_observation") {
        statusNotice = "Partial observation (S-NPP launched; Jan 1–19 unobserved)";
        coverageNote = "Partial month coverage";
      } else if (sw.status === "insufficient_coverage" || (year < 2012 && sw.complete_pairs_count === 0)) {
        count = null;
        statusNotice = "Insufficient coverage — no complete Day+Night block pairs; no valid combined total";
        const noPassBlocks = 568 - (sw.single_pass_count ?? 0);
        coverageNote = `0 complete pairs; ${sw.single_pass_count ?? 0} single-pass blocks; ${noPassBlocks} blocks with no available estimates. NULL is not zero.`;
      } else if (count !== null) {
        if (year < 2012) {
          const pairsText = sw.complete_pairs_count != null ? `${sw.complete_pairs_count} complete D+N pairs` : "complete pairs";
          statusNotice = `Estimated VIIRS-equivalent (${sw.available_estimates_count} of 1,136 available passes; ${pairsText})`;
          const unobservedBlocks = 568 - (sw.complete_pairs_count ?? 0) - (sw.single_pass_count ?? 0);
          coverageNote = sw.complete_pairs_count != null
            ? `${sw.available_estimates_count} of ${sw.expected_passes ?? 1136} passes (${sw.complete_pairs_count} complete Day+Night pairs, ${sw.single_pass_count} single-pass; ${unobservedBlocks} blocks with no available estimated passes; observation coverage unknown)`
            : `${sw.available_estimates_count} available passes`;
        } else {
          statusNotice = "Recorded S-NPP VIIRS 375m statewide total";
          coverageNote = "Authoritative monthly satellite composite";
        }
      } else {
        statusNotice = "No detections recorded (NULL preserved, not zero)";
        coverageNote = "Unobserved / missing record";
      }
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="text-sm font-medium">Selection overview</h2>
        <LocateFixed className="size-4 text-muted-foreground" aria-hidden="true" />
      </div>
      <div className="space-y-6 p-5">
        <div>
          <p className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Study region</p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-xl font-medium">Pará, Brazil</h3>
            {block && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setBlock(null)}
                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                <X className="mr-1 size-3" />
                Clear block
              </Button>
            )}
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            BR-PA <span className="px-1">/</span> {block ? `Block ${block} (50 km)` : "Statewide Pará"}
          </p>
        </div>

        <dl className="space-y-4 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Selected period</dt>
            <dd className="mt-1 font-medium tabular-nums">
              {MONTHS[month - 1]} {year}
            </dd>
          </div>
          <div>
            <dt className="mb-2 text-xs text-muted-foreground">Requested layer</dt>
            <dd>
              <ScienceStatus layer={layer} />
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-background/50 p-4">
            <dt className="text-xs text-muted-foreground">Hotspot detection count</dt>
            <dd className="mt-2 text-[28px] font-mono font-bold leading-9 tabular-nums text-foreground">
              {count !== null ? Math.round(count).toLocaleString() : "—"}
            </dd>
            <dd className="mt-1 text-xs text-muted-foreground">
              {!compatible ? "Unsupported layer for this period" : statusNotice}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Measurement</dt>
            <dd className="mt-1 leading-relaxed">
              {layer === "estimated"
                ? "VIIRS S-NPP-equivalent hotspot detections"
                : "Recorded VIIRS S-NPP hotspot detections"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Spatial resolution</dt>
            <dd className="mt-1">{LAYERS[layer].scale}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Expected source</dt>
            <dd className="mt-1 leading-relaxed">{LAYERS[layer].source}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Coverage status</dt>
            <dd className="mt-1">{coverageNote}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Block geometry source</dt>
            <dd className="mt-1 leading-relaxed">
              {metadata?.sourceLabel ?? "WGS 84 / NSIDC EASE-Grid 2.0 Global (EPSG:6933, Lambert Cylindrical Equal Area) 50 km canonical grid (568 blocks)"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Selected boundary version</dt>
            <dd className="mt-1">
              {metadata?.boundaryVersion
                ? `IBGE Malha Estadual ${metadata.boundaryVersion}`
                : "IBGE Malha Estadual 2024 (EPSG:4674 → EPSG:4326)"}
            </dd>
          </div>
        </dl>

        <div className="flex gap-2 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden="true" />
          <p>
            Missing values remain unknown; a missing record is not evidence of zero activity. MODIS and VIIRS detections are never added together.
          </p>
        </div>

        <details className="border-t border-border pt-4 text-xs">
          <summary className="cursor-pointer rounded py-2 text-muted-foreground hover:text-foreground">
            Data provenance <FileText className="ml-1 inline size-3" aria-hidden="true" />
          </summary>
          <dl className="mt-3 space-y-3 text-muted-foreground">
            <div>
              <dt>Dataset / processing version</dt>
              <dd className="mt-1 text-foreground">S-NPP VIIRS 375m (VNP14IMGTDL) / Aqua MODIS (MCD14DL)</dd>
            </div>
            <div>
              <dt>Boundary version</dt>
              <dd className="mt-1 text-foreground">IBGE Malha Estadual 2024 (PA_UF_2024.zip)</dd>
            </div>
            <div>
              <dt>Model version</dt>
              <dd className="mt-1 text-foreground">firechronicle-nb2-v1.0 (GLM Negative Binomial, α = 0.3394)</dd>
            </div>
            <div>
              <dt>Acquisition time (UTC)</dt>
              <dd className="mt-1 text-foreground">{MONTHS[month - 1]} {year} (Monthly composite)</dd>
            </div>
          </dl>
        </details>

        <div className="border-t border-border pt-4">
          <ExportButton className="w-full justify-center h-10" />
        </div>
      </div>
      <Link
        href="/methodology"
        className="mt-auto flex min-h-12 items-center justify-between border-t border-border px-5 text-xs text-primary hover:bg-accent"
      >
        Understand the measurement
        <ArrowUpRight className="size-4" aria-hidden="true" />
      </Link>
    </div>
  );
}

export function AnalysisLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="mb-3 hidden justify-end md:flex xl:hidden">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger render={<Button variant="outline" className="h-11 border-input" />}>
            <SlidersHorizontal />
            Selection overview
          </SheetTrigger>
          <SheetContent className="w-[min(360px,95vw)] overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Selection overview</SheetTitle>
              <SheetDescription>Period, source and scientific context</SheetDescription>
            </SheetHeader>
            <div className="px-3 pb-4">
              <AnalysisPanel />
            </div>
          </SheetContent>
        </Sheet>
      </div>
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">{children}</div>
        <aside aria-label="Selected area analysis" className="md:hidden xl:block">
          <AnalysisPanel />
        </aside>
      </div>
    </>
  );
}
