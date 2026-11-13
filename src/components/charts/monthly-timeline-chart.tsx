"use client";

import { useState, useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { TimelineDataPoint } from "@/lib/charts/chart-transforms";
import { useSelection } from "@/store/selection-store";
import { useMounted } from "@/lib/hooks/use-mounted";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  data: TimelineDataPoint[];
  scope: "statewide" | "block";
  blockId: string | null;
}

export function MonthlyTimelineChart({ data, scope, blockId }: Props) {
  const mounted = useMounted();
  const [showModis, setShowModis] = useState(false);
  const setPeriod = useSelection((s) => s.setPeriod);
  const selectedYear = useSelection((s) => s.year);
  const selectedMonth = useSelection((s) => s.month);

  const selectedPeriodKey = `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`;

  // Ticks for X-Axis: show January of every other year
  const xTicks = useMemo(() => {
    return data
      .filter((d) => d.month === 1 && d.year % 2 === 0)
      .map((d) => d.period);
  }, [data]);

  if (!mounted) {
    return (
      <div className="flex h-[360px] w-full items-center justify-center rounded-lg border border-border bg-card/30 text-xs text-muted-foreground">
        Loading interactive timeline...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Chart Controls & Scope Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="font-medium text-foreground">
            {scope === "block" && blockId ? `Block ${blockId} (50 km grid)` : "Statewide Pará"}
          </span>
          <span>· 2002–2020 Continuous Monthly Stream</span>
        </div>

        {scope === "statewide" && (
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1 text-muted-foreground hover:text-foreground">
            <input
              type="checkbox"
              checked={showModis}
              onChange={(e) => setShowModis(e.target.checked)}
              className="size-3.5 rounded border-input"
            />
            <span>Show Aqua MODIS Reference Line</span>
          </label>
        )}
      </div>

      {showModis && (
        <div className="flex items-center gap-2 rounded-md border border-sky-500/30 bg-sky-500/10 p-2.5 text-xs text-sky-200">
          <Info className="size-4 shrink-0" />
          <span>
            <strong>Scientific rule:</strong> Aqua MODIS raw counts are plotted for scale comparison only. MODIS and VIIRS counts are <strong>never</strong> added together.
          </span>
        </div>
      )}

      {/* Main Timeline Chart */}
      <div className="h-[340px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 15, left: 10, bottom: 25 }}
            onClick={(state) => {
              const active = (state as unknown as { activePayload?: Array<{ payload: TimelineDataPoint }> })?.activePayload;
              if (active && active.length > 0) {
                const pt = active[0].payload;
                if (pt?.year && pt?.month) {
                  setPeriod(pt.year, pt.month);
                }
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis
              dataKey="period"
              ticks={xTicks}
              tickFormatter={(val: string) => val.slice(0, 4)}
              stroke="rgba(255,255,255,0.4)"
              tick={{ fontSize: 11 }}
              dy={10}
            />
            <YAxis
              stroke="rgba(255,255,255,0.4)"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
              dx={-5}
            />

            {/* Transition Line at 2012-01 */}
            <ReferenceLine
              x="2012-01"
              stroke="#10b981"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: "2012: S-NPP VIIRS Era",
                position: "top",
                fill: "#10b981",
                fontSize: 10,
                offset: 5,
              }}
            />

            {/* Highlight Selected Period */}
            {selectedPeriodKey && (
              <ReferenceLine
                x={selectedPeriodKey}
                stroke="#ffffff"
                strokeWidth={1}
                strokeDasharray="2 2"
              />
            )}

            {/* Estimated VIIRS Curve (2002-07 to 2011-12) */}
            <Line
              type="monotone"
              dataKey="estimatedViirs"
              name="Estimated VIIRS-equivalent"
              stroke="#d97706"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, fill: "#f59e0b", stroke: "#ffffff", strokeWidth: 2 }}
              connectNulls={false}
            />

            {/* Observed VIIRS Curve (2012-01 to 2020-12) */}
            <Line
              type="monotone"
              dataKey="observedViirs"
              name="Observed S-NPP VIIRS"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, fill: "#34d399", stroke: "#ffffff", strokeWidth: 2 }}
              connectNulls={false}
            />

            {/* Optional Observed MODIS Curve */}
            {showModis && (
              <Line
                type="monotone"
                dataKey="observedModis"
                name="Observed Aqua MODIS (Raw)"
                stroke="#60a5fa"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                activeDot={{ r: 4, fill: "#93c5fd" }}
                connectNulls={false}
              />
            )}

            {/* Custom Scientific Tooltip */}
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const pt = payload[0].payload as TimelineDataPoint;
                const isSelected = pt.period === selectedPeriodKey;

                return (
                  <div className="z-50 min-w-48 rounded-lg border border-border bg-card/95 p-3 shadow-xl backdrop-blur-sm text-xs">
                    <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5 font-medium">
                      <span className="text-foreground">{pt.fullLabel}</span>
                      {isSelected && (
                        <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[10px] text-primary">
                          Selected
                        </span>
                      )}
                    </div>

                    <div className="mt-2 space-y-1.5">
                      {pt.status === "unsupported_period" ? (
                        <div className="text-muted-foreground/70 italic">
                          Pre-commissioning period (Aqua MODIS launched July 2002). No satellite observations.
                        </div>
                      ) : pt.status === "insufficient_coverage" ? (
                        <div className="text-amber-200 italic">Insufficient coverage — zero complete Day+Night pairs; statewide count unavailable (not zero).</div>
                      ) : pt.status === "missing" || pt.value === null ? (
                        <div className="text-muted-foreground/70 italic">
                          No detections / missing pass record (NULL preserved, not verified zero).
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-muted-foreground">Detection count:</span>
                            <span className="font-mono font-bold text-foreground">
                              {Math.round(pt.value).toLocaleString()}
                            </span>
                          </div>

                          <div className="flex items-center justify-between gap-3 text-[11px]">
                            <span className="text-muted-foreground">Measurement tier:</span>
                            <span
                              className={cn(
                                "font-medium",
                                pt.valueType === "estimated" ? "text-amber-400" : "text-emerald-400"
                              )}
                            >
                              {pt.valueType === "estimated"
                                ? "Estimated VIIRS-equivalent"
                                : "Observed S-NPP VIIRS"}
                            </span>
                          </div>

                          {pt.observedModis !== null && pt.observedModis !== undefined && (
                            <div className="flex items-center justify-between gap-3 text-[11px]">
                              <span className="text-muted-foreground">Aqua MODIS input:</span>
                              <span className="font-mono text-sky-300">
                                {pt.observedModis.toLocaleString()}
                              </span>
                            </div>
                          )}

                          {pt.period === "2002-07" && (
                            <div className="mt-1 rounded bg-amber-500/20 p-1 text-[10px] text-amber-200">
                              ⚠ Partial coverage: Aqua MODIS commissioned July 2002; first operational month.
                            </div>
                          )}

                          {pt.status === "partial_observation" && (
                            <div className="mt-1 rounded bg-amber-500/20 p-1 text-[10px] text-amber-200">
                              ⚠ Partial observation (VIIRS archive began Jan 20; days 1–19 unobserved; excluded from calibration).
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    <div className="mt-2.5 border-t border-border/60 pt-1 text-[10px] text-muted-foreground">
                      Click to sync period controls
                    </div>
                  </div>
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend & Scientific Provenance */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-4 rounded-full bg-amber-500" />
            <span>Estimated (2002–2011 · Aqua MODIS → NB2 v1.0)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-4 rounded-full bg-emerald-500" />
            <span>Observed (2012–2020 · S-NPP VIIRS 375m)</span>
          </div>
          {showModis && (
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-4 rounded-full border border-sky-400 border-dashed bg-sky-400/50" />
              <span>Aqua MODIS (Raw context)</span>
            </div>
          )}
        </div>

        <span className="text-[11px] text-muted-foreground/70">
          Jul 2002 partial · Jan 2012 partial · Jan–Jun 2002 unsupported (NULL preserved, not zero)
        </span>
      </div>
    </div>
  );
}
