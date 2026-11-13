"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Info, ShieldAlert, Sparkles } from "lucide-react";
import { useSelection } from "@/store/selection-store";
import { MONTHS } from "@/types/explorer";
import { useCalendarMatrix, useBlocksSummary } from "@/lib/api/queries";
import { ScienceStatus } from "@/components/ui/science-status";
import { cn } from "@/lib/utils";

export function CalendarShell() {
  const selectedYear = useSelection((s) => s.year);
  const selectedMonth = useSelection((s) => s.month);
  const selectedBlock = useSelection((s) => s.block_id);
  const setPeriod = useSelection((s) => s.setPeriod);

  // View mode: statewide vs selected block
  const [viewScope, setViewScope] = useState<"statewide" | "block">("statewide");

  const { data: calendarData, isLoading: calLoading, error: calError } = useCalendarMatrix();
  const { data: blocksData } = useBlocksSummary();

  const activeScope = selectedBlock && viewScope === "block" ? "block" : "statewide";
  const blockInfo = selectedBlock && blocksData ? blocksData.blocks[selectedBlock] : null;

  // Compute maximum detection count for color scale normalization
  const maxVal = useMemo(() => {
    if (activeScope === "block" && blockInfo) {
      return Math.max(...blockInfo.values.filter((v): v is number => v !== null), 100);
    }
    if (calendarData) {
      let m = 1;
      for (const y of calendarData.years) {
        for (const mo of y.months) {
          if (mo.value !== null && mo.value > m) m = mo.value;
        }
      }
      return m;
    }
    return 10000;
  }, [activeScope, blockInfo, calendarData]);

  // Color calculation based on value type and magnitude
  function getCellStyle(value: number | null, valueType: "estimated" | "observed" | null, status: string) {
    if (status === "insufficient_coverage") {
      return { bg: "bg-amber-500/10 border-amber-500/30 text-amber-200", label: "Insufficient coverage" };
    }
    if (status === "unsupported_period" || value === null && status === "missing") {
      return {
        bg: "bg-muted/30 border-muted/50 text-muted-foreground/40",
        label: status === "unsupported_period" ? "Unsupported" : "Missing",
      };
    }
    if (status === "partial_observation") {
      return {
        bg: "bg-amber-500/20 border-amber-500/50 text-amber-200",
        label: "Partial",
      };
    }
    if (value === null) {
      return {
        bg: "bg-background border-border/40 text-muted-foreground",
        label: "No data",
      };
    }

    // Normalized intensity [0.15, 0.9] using log1p
    const intensity = Math.min(1.0, Math.max(0.15, Math.log1p(value) / Math.log1p(maxVal)));

    if (valueType === "estimated") {
      // Warm Amber ramp
      return {
        bg: "border-amber-600/40 text-amber-100",
        style: {
          backgroundColor: `rgba(217, 119, 6, ${intensity * 0.75})`,
          borderColor: `rgba(245, 158, 11, ${Math.min(1, intensity + 0.2)})`,
        },
        label: `${value.toLocaleString()} est.`,
      };
    } else {
      // Emerald Observed ramp
      return {
        bg: "border-emerald-600/40 text-emerald-100",
        style: {
          backgroundColor: `rgba(16, 185, 129, ${intensity * 0.75})`,
          borderColor: `rgba(52, 211, 153, ${Math.min(1, intensity + 0.2)})`,
        },
        label: `${value.toLocaleString()} obs.`,
      };
    }
  }

  return (
    <section
      className="overflow-hidden rounded-xl border border-border bg-card shadow-sm"
      aria-labelledby="calendar-heatmap-title"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border p-5">
        <div>
          <h2 id="calendar-heatmap-title" className="flex items-center gap-2 text-base font-medium">
            <CalendarDays className="size-4 text-primary" aria-hidden="true" />
            Time Machine Heatmap (2002–2020)
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Year × Month burning activity record. Click any cell to synchronize the observation period.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {selectedBlock && (
            <div className="flex items-center rounded-lg border border-border bg-background p-1 text-xs">
              <button
                type="button"
                onClick={() => setViewScope("statewide")}
                className={cn(
                  "rounded-md px-3 py-1 font-medium transition-colors",
                  activeScope === "statewide" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                Statewide Pará
              </button>
              <button
                type="button"
                onClick={() => setViewScope("block")}
                className={cn(
                  "rounded-md px-3 py-1 font-medium transition-colors",
                  activeScope === "block" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                Block {selectedBlock}
              </button>
            </div>
          )}
          <ScienceStatus layer={selectedYear < 2012 ? "estimated" : "observed"} />
        </div>
      </div>

      {/* Main Heatmap Matrix */}
      <div className="overflow-x-auto p-5">
        {calLoading && (
          <div className="flex h-64 items-center justify-center text-xs text-muted-foreground">
            Loading 2002–2020 scientific calendar...
          </div>
        )}

        {calError && (
          <div className="flex h-64 items-center justify-center gap-2 text-xs text-destructive">
            <ShieldAlert className="size-4" />
            Failed to load calendar matrix: {(calError as Error).message}
          </div>
        )}

        {calendarData && (
          <div className="min-w-[720px]">
            {/* Month Column Headers */}
            <div className="mb-2 grid grid-cols-[64px_repeat(12,1fr)] gap-1.5 text-center text-xs font-medium text-muted-foreground">
              <span className="text-left font-normal text-muted-foreground/60">Year</span>
              {MONTHS.map((m) => (
                <span key={m}>{m.slice(0, 3)}</span>
              ))}
            </div>

            {/* Year Rows */}
            <div className="space-y-1.5">
              {calendarData.years.map((yRow) => {
                const yr = yRow.year;
                const isHist = yr < 2012;

                return (
                  <div key={yr} className="relative">
                    {/* Era separator banner above 2012 */}
                    {yr === 2012 && (
                      <div className="my-2.5 flex items-center gap-3 border-y border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                        <Sparkles className="size-3.5 text-emerald-400" />
                        <span>2012 Operational Era Transition — Suomi NPP VIIRS Active Archive Begins</span>
                      </div>
                    )}

                    <div className="grid grid-cols-[64px_repeat(12,1fr)] items-center gap-1.5">
                      {/* Year Label */}
                      <span className="font-mono text-xs font-semibold text-muted-foreground">
                        {yr}
                      </span>

                      {/* 12 Months */}
                      {yRow.months.map((mCol) => {
                        const mo = mCol.month;
                        const isSelected = selectedYear === yr && selectedMonth === mo;

                        // Block-level lookup if activeScope is block
                        let cellVal = mCol.value;
                        let cellType = mCol.value_type;
                        let cellStatus = mCol.status;

                        if (activeScope === "block" && blockInfo) {
                          const pIdx = (yr - 2002) * 12 + (mo - 1);
                          cellVal = blockInfo.values[pIdx] ?? null;
                          cellType = isHist ? "estimated" : "observed";
                          cellStatus = yr === 2002 && mo < 7 ? "unsupported_period" : cellVal === null ? "missing" : "ok";
                        }

                        const styleInfo = getCellStyle(cellVal, cellType, cellStatus);

                        const tooltipText =
                          cellStatus === "unsupported_period"
                            ? `${MONTHS[mo - 1]} ${yr}: Pre-Aqua launch period (unsupported)`
                            : cellStatus === "partial_observation"
                            ? yr === 2002
                              ? `${MONTHS[mo - 1]} ${yr}: Partial commissioning estimate (${cellVal?.toLocaleString()} VIIRS-equivalent detections; 37 complete pairs)`
                              : `${MONTHS[mo - 1]} ${yr}: Partial launch observation (${cellVal?.toLocaleString()} VIIRS detections)`
                            : cellStatus === "insufficient_coverage"
                            ? `${MONTHS[mo - 1]} ${yr}: Insufficient coverage — zero complete Day+Night pairs (NULL, not zero)`
                            : cellVal === null
                            ? `${MONTHS[mo - 1]} ${yr}: Unobserved / missing record (not verified zero)`
                            : `${MONTHS[mo - 1]} ${yr}: ${cellVal.toLocaleString()} detections (${cellType === "estimated" ? "Estimated VIIRS-equivalent" : "Observed VIIRS"})`;

                        return (
                          <button
                            key={mo}
                            type="button"
                            title={tooltipText}
                            aria-label={tooltipText}
                            aria-pressed={isSelected}
                            onClick={() => setPeriod(yr, mo)}
                            style={styleInfo.style}
                            className={cn(
                              "relative flex h-8 items-center justify-center rounded border text-[11px] font-mono transition-all",
                              styleInfo.bg,
                              isSelected && "ring-2 ring-primary ring-offset-2 ring-offset-background font-bold shadow-md",
                              "hover:scale-105 hover:z-10 cursor-pointer"
                            )}
                          >
                            {cellVal !== null ? (
                              cellVal >= 1000 ? `${(cellVal / 1000).toFixed(0)}k` : Math.round(cellVal)
                            ) : (
                              <span className="text-[9px] opacity-40">—</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Accessible Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border bg-card/50 p-4 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-4">
          <span className="font-medium text-foreground">Color scale:</span>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded border border-amber-500 bg-amber-500/70" />
            <span>Estimated (2002–2011 · Aqua MODIS → NB2 v1.0)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded border border-emerald-500 bg-emerald-500/70" />
            <span>Observed (2012–2020 · S-NPP VIIRS)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded border border-amber-400 bg-amber-500/20" />
            <span>Partial Observation / Commissioning (Jul 2002 & Jan 2012)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded border border-muted/50 bg-muted/30" />
            <span>Unsupported / Missing (NULL preserved, not zero)</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Info className="size-3.5 text-muted-foreground" />
          <span>Click any cell to update the observation period.</span>
        </div>
      </div>
    </section>
  );
}
