"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { SeasonalDataPoint } from "@/lib/charts/chart-transforms";
import { useSelection } from "@/store/selection-store";
import { useMounted } from "@/lib/hooks/use-mounted";
import { MONTHS } from "@/types/explorer";
import { Flame, Info } from "lucide-react";

interface Props {
  data: SeasonalDataPoint[];
  scope: "statewide" | "block";
  blockId: string | null;
}

export function SeasonalCycleChart({ data, scope, blockId }: Props) {
  const mounted = useMounted();
  const selectedMonth = useSelection((s) => s.month);
  const setPeriod = useSelection((s) => s.setPeriod);
  const selectedYear = useSelection((s) => s.year);

  if (!mounted) {
    return (
      <div className="flex h-[360px] w-full items-center justify-center rounded-lg border border-border bg-card/30 text-xs text-muted-foreground">
        Loading seasonal climatology...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Perspective Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="font-medium text-foreground">
            {scope === "block" && blockId ? `Block ${blockId}` : "Statewide Pará"}
          </span>
          <span>· 12-Month Climatological Seasonal Profile</span>
        </div>

        <div className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-muted-foreground">
          <Flame className="size-3.5 text-amber-500" />
          <span>Peak burning season: August – November</span>
        </div>
      </div>

      {/* Main Bar Chart comparing Historical Avg vs Modern Avg */}
      <div className="h-[340px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 10, right: 15, left: 10, bottom: 15 }}
            onClick={(state) => {
              const active = (state as unknown as { activePayload?: Array<{ payload: SeasonalDataPoint }> })?.activePayload;
              if (active && active.length > 0) {
                const pt = active[0].payload;
                if (pt?.month) {
                  setPeriod(selectedYear, pt.month);
                }
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis
              dataKey="monthName"
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
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const pt = payload[0].payload as SeasonalDataPoint;
                const isSelected = pt.month === selectedMonth;

                return (
                  <div className="z-50 min-w-48 rounded-lg border border-border bg-card/95 p-3 shadow-xl backdrop-blur-sm text-xs">
                    <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5 font-medium">
                      <span className="text-foreground">{MONTHS[pt.month - 1]}</span>
                      {isSelected && (
                        <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[10px] text-primary">
                          Active Month
                        </span>
                      )}
                    </div>

                    <div className="mt-2 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-1.5 text-muted-foreground">
                          <span className="size-2 rounded-full bg-amber-500" />
                          <span>Historical Mean (2003–2011):</span>
                        </span>
                        <span className="font-mono font-medium text-amber-300">
                          {pt.historicalAvg !== null ? pt.historicalAvg.toLocaleString() : "—"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-1.5 text-muted-foreground">
                          <span className="size-2 rounded-full bg-emerald-500" />
                          <span>Modern Mean ({pt.month === 1 ? "2013–2020 · 8 full yrs" : "2012–2020 · 9 yrs"}):</span>
                        </span>
                        <span className="font-mono font-medium text-emerald-300">
                          {pt.modernAvg !== null ? pt.modernAvg.toLocaleString() : "—"}
                        </span>
                      </div>

                      {pt.month === 1 && (
                        <div className="mt-1 rounded bg-amber-500/10 p-1 text-[10px] text-amber-300/90">
                          * January modern mean excludes partial Jan 2012 observation (days 1–19 unobserved); averages 8 complete years (2013–2020).
                        </div>
                      )}

                      <div className="mt-1 border-t border-border/50 pt-1 text-[11px] text-muted-foreground">
                        {pt.month >= 8 && pt.month <= 11
                          ? "Dry season peak: elevated deforestation and pasture burning."
                          : pt.month <= 5
                          ? "Wet season low: frequent cloud cover and high relative humidity."
                          : "Transitional period between wet and dry seasons."}
                      </div>
                    </div>

                    <div className="mt-2.5 border-t border-border/60 pt-1 text-[10px] text-muted-foreground">
                      Click to inspect this month
                    </div>
                  </div>
                );
              }}
            />
            <Legend
              verticalAlign="top"
              height={36}
              formatter={(value: string) => <span className="text-xs text-muted-foreground">{value}</span>}
            />
            <Bar
              dataKey="historicalAvg"
              name="Historical Era Average (2003–2011 · Estimated)"
              fill="#d97706"
              radius={[4, 4, 0, 0]}
              maxBarSize={30}
            />
            <Bar
              dataKey="modernAvg"
              name="Modern Era Average (2012–2020 · Observed; Jan: 2013–2020)"
              fill="#10b981"
              radius={[4, 4, 0, 0]}
              maxBarSize={30}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Scientific Data Provenance & Limitations */}
      <div className="rounded-lg border border-border bg-card/40 p-3 text-xs leading-relaxed text-muted-foreground space-y-1.5">
        <p className="flex items-start gap-2">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <span>
            <strong>Observational caveat:</strong> These charts illustrate available observed and estimated detection patterns, subject to sensor differences and incomplete observation coverage. Seasonal patterns reflect the empirical fixed-effect estimates (&beta;<sub>month</sub>) fitted to the 2012–2020 overlap, but visual consistency does not constitute independent validation of true historical fire activity without historical VIIRS ground truth.
          </span>
        </p>
        <div className="text-[11px] text-muted-foreground/80 pl-6 space-y-0.5">
          <p>• <strong>July 2002:</strong> Partially covered (Aqua MODIS commissioned July 2002; first active operational month).</p>
          <p>• <strong>January 2012:</strong> Partial VIIRS month (S-NPP archive began Jan 20; days 1–19 unobserved). Excluded from model calibration and excluded from the modern January climatological average (which reflects 8 complete observation years: 2013–2020).</p>
          <p>• <strong>Sensor eras:</strong> 2003–2011 represents Aqua MODIS-derived NB2 estimates; 2012–2020 represents direct S-NPP VIIRS observations.</p>
          <p>• <strong>Historical coverage:</strong> Satellite orbital gaps and cloud obscuration are unadjusted; missing records are preserved as NULL, never zero.</p>
        </div>
      </div>
    </div>
  );
}
