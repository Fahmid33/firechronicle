"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ReferenceLine,
} from "recharts";
import type { AnnualTotalPoint } from "@/lib/charts/chart-transforms";
import { useSelection } from "@/store/selection-store";
import { useMounted } from "@/lib/hooks/use-mounted";
import { AlertCircle, Calendar } from "lucide-react";

interface Props {
  data: AnnualTotalPoint[];
  scope: "statewide" | "block";
  blockId: string | null;
}

export function AnnualTotalsChart({ data, scope, blockId }: Props) {
  const mounted = useMounted();
  const selectedYear = useSelection((s) => s.year);
  const setPeriod = useSelection((s) => s.setPeriod);
  const selectedMonth = useSelection((s) => s.month);

  if (!mounted) {
    return (
      <div className="flex h-[360px] w-full items-center justify-center rounded-lg border border-border bg-card/30 text-xs text-muted-foreground">
        Loading annual burning totals...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="font-medium text-foreground">
            {scope === "block" && blockId ? `Block ${blockId}` : "Statewide Pará"}
          </span>
          <span>· Annual Hotspot Detection Totals (2002–2020)</span>
        </div>

        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Calendar className="size-3.5" />
          <span>Click any year to select</span>
        </div>
      </div>

      {/* Main Bar Chart */}
      <div className="h-[340px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 10, right: 15, left: 10, bottom: 20 }}
            onClick={(state) => {
              const active = (state as unknown as { activePayload?: Array<{ payload: AnnualTotalPoint }> })?.activePayload;
              if (active && active.length > 0) {
                const pt = active[0].payload;
                if (pt?.year) {
                  setPeriod(pt.year, selectedMonth);
                }
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis
              dataKey="year"
              stroke="rgba(255,255,255,0.4)"
              tick={{ fontSize: 11 }}
              dy={5}
            />
            <YAxis
              stroke="rgba(255,255,255,0.4)"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
              dx={-5}
            />

            {/* Transition Line at 2012 */}
            <ReferenceLine
              x={2012}
              stroke="#10b981"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: "Observed S-NPP VIIRS Era",
                position: "top",
                fill: "#10b981",
                fontSize: 10,
                offset: 5,
              }}
            />

            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const pt = payload[0].payload as AnnualTotalPoint;
                const isSelected = pt.year === selectedYear;

                return (
                  <div className="z-50 min-w-52 rounded-lg border border-border bg-card/95 p-3 shadow-xl backdrop-blur-sm text-xs">
                    <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5 font-medium">
                      <span className="text-foreground">{pt.year}</span>
                      {isSelected && (
                        <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[10px] text-primary">
                          Active Year
                        </span>
                      )}
                    </div>

                    <div className="mt-2 space-y-1.5">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Annual total:</span>
                        <span className="font-mono font-bold text-foreground">
                          {pt.total !== null ? pt.total.toLocaleString() : "—"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-3 text-[11px]">
                        <span className="text-muted-foreground">Data stream:</span>
                        <span
                          className={
                            pt.era === "modern_observed"
                              ? "text-emerald-400 font-medium"
                              : "text-amber-400 font-medium"
                          }
                        >
                          {pt.era === "modern_observed"
                            ? "Observed S-NPP VIIRS"
                            : "Estimated VIIRS-equivalent"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-3 text-[11px]">
                        <span className="text-muted-foreground">Coverage months:</span>
                        <span className="font-mono text-foreground">
                          {pt.validMonthsCount} / 12
                        </span>
                      </div>

                      {pt.year === 2002 && (
                        <div className="mt-1 flex items-start gap-1 rounded bg-amber-500/20 p-1 text-[10px] text-amber-200">
                          <AlertCircle className="size-3 shrink-0 mt-0.5" />
                          <span>Partial year: Aqua MODIS launched July 2002 (Jan–Jun unobserved; July first operational month).</span>
                        </div>
                      )}

                      {pt.year === 2012 && (
                        <div className="mt-1 flex items-start gap-1 rounded bg-amber-500/20 p-1 text-[10px] text-amber-200">
                          <AlertCircle className="size-3 shrink-0 mt-0.5" />
                          <span>Transition year: S-NPP VIIRS operational from Jan 20 (Jan 1–19 unobserved).</span>
                        </div>
                      )}

                      {[2004, 2005, 2007, 2010].includes(pt.year) && (
                        <div className="mt-1 rounded bg-amber-500/10 p-1 text-[10px] text-amber-300">
                          🔥 Historical severe drought / peak fire year in Pará.
                        </div>
                      )}
                    </div>

                    <div className="mt-2.5 border-t border-border/60 pt-1 text-[10px] text-muted-foreground">
                      Click to select {pt.year}
                    </div>
                  </div>
                );
              }}
            />

            <Bar dataKey="total" maxBarSize={32} radius={[4, 4, 0, 0]}>
              {data.map((entry) => {
                const isSelected = entry.year === selectedYear;
                let fill = "#10b981"; // Modern observed
                if (entry.year === 2002) {
                  fill = "#f59e0b"; // 2002 partial
                } else if (entry.year < 2012) {
                  fill = "#d97706"; // Estimated
                }

                return (
                  <Cell
                    key={`bar-${entry.year}`}
                    fill={fill}
                    fillOpacity={isSelected ? 1.0 : 0.8}
                    stroke={isSelected ? "#ffffff" : "transparent"}
                    strokeWidth={isSelected ? 2 : 0}
                    className="cursor-pointer transition-all hover:opacity-100"
                  />
                );
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded border border-amber-400 bg-amber-500/30" />
            <span>2002 Partial (Jul–Dec only · 6 months)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded bg-amber-600" />
            <span>2003–2011 Estimated (Aqua MODIS → NB2 v1.0)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-3 rounded bg-emerald-500" />
            <span>2012–2020 Observed (S-NPP VIIRS 375m)</span>
          </div>
        </div>

        <span className="text-[11px] text-muted-foreground/70">
          Statewide totals reflect strict daynight=ALL (sums exclusively complete D+N pairs; unadjusted for cloud cover)
        </span>
      </div>
    </div>
  );
}
