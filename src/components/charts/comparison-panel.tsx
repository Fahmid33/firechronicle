"use client";

import { useState, useMemo } from "react";
import {
  ChartNoAxesCombined,
  CalendarDays,
  Flame,
  BarChart3,
  MapPin,
  ShieldAlert,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useSelection } from "@/store/selection-store";
import { useStatewideTimeSeries, useBlocksSummary } from "@/lib/api/queries";
import {
  buildTimelineData,
  buildSeasonalData,
  buildAnnualTotals,
} from "@/lib/charts/chart-transforms";
import { MonthlyTimelineChart } from "@/components/charts/monthly-timeline-chart";
import { SeasonalCycleChart } from "@/components/charts/seasonal-cycle-chart";
import { AnnualTotalsChart } from "@/components/charts/annual-totals-chart";
import { ExportButton } from "@/components/csv/export-button";
import { cn } from "@/lib/utils";

interface Props {
  seasonal?: boolean;
}

export function ComparisonPanel({ seasonal = false }: Props) {
  const [activeTab, setActiveTab] = useState<"timeline" | "seasonal" | "annual">(
    seasonal ? "seasonal" : "timeline"
  );
  const [viewScope, setViewScope] = useState<"statewide" | "block">("statewide");

  const selectedBlock = useSelection((s) => s.block_id);
  const activeScope = selectedBlock && viewScope === "block" ? "block" : "statewide";

  const {
    data: statewideData,
    isLoading: statewideLoading,
    error: statewideError,
  } = useStatewideTimeSeries();
  const { data: blocksSummary, isLoading: blocksLoading } = useBlocksSummary();

  const isLoading = statewideLoading || (activeScope === "block" && blocksLoading);
  const error = statewideError;

  // Memoized transformed datasets
  const timelineData = useMemo(() => {
    return buildTimelineData(statewideData, blocksSummary, activeScope, selectedBlock);
  }, [statewideData, blocksSummary, activeScope, selectedBlock]);

  const seasonalData = useMemo(() => {
    return buildSeasonalData(timelineData);
  }, [timelineData]);

  const annualData = useMemo(() => {
    return buildAnnualTotals(timelineData);
  }, [timelineData]);

  return (
    <Card className="border border-border ring-0">
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <ChartNoAxesCombined className="size-4 text-primary" aria-hidden="true" />
              {activeTab === "seasonal"
                ? "Seasonal Climatology & Fixed Effects"
                : activeTab === "annual"
                ? "Annual Burning Season Totals"
                : "Continuous Multi-Decadal Timeline (2002–2020)"}
            </CardTitle>
            <CardDescription className="mt-1">
              {activeTab === "seasonal"
                ? "Comparing 12-month historical estimated baseline against modern observed patterns."
                : activeTab === "annual"
                ? "Annual totals across 19 years with clear historical and modern tier boundaries."
                : "Aqua MODIS-derived historical estimates (2002–2011) and S-NPP VIIRS observations (2012–2020)."}
            </CardDescription>
          </div>

          {/* Scope Selector & CSV Export */}
          <div className="flex flex-wrap items-center gap-2">
            {selectedBlock && (
              <div className="flex items-center rounded-lg border border-border bg-muted/40 p-1 text-xs">
                <button
                  type="button"
                  onClick={() => setViewScope("statewide")}
                  className={cn(
                    "rounded-md px-3 py-1 font-medium transition-colors",
                    activeScope === "statewide"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Statewide Pará
                </button>
                <button
                  type="button"
                  onClick={() => setViewScope("block")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition-colors",
                    activeScope === "block"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <MapPin className="size-3 text-primary" />
                  Block {selectedBlock}
                </button>
              </div>
            )}
            <ExportButton />
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-b border-border pb-3">
          <button
            type="button"
            onClick={() => setActiveTab("timeline")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "timeline"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )}
          >
            <CalendarDays className="size-3.5" />
            Monthly Timeline (2002–2020)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("seasonal")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "seasonal"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )}
          >
            <Flame className="size-3.5" />
            Seasonal Climatology (12 Months)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("annual")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "annual"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )}
          >
            <BarChart3 className="size-3.5" />
            Annual Totals
          </button>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading && (
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border text-xs text-muted-foreground">
            Loading scientific fire time series...
          </div>
        )}

        {error && (
          <div className="flex h-64 items-center justify-center gap-2 rounded-lg border border-destructive/40 text-xs text-destructive">
            <ShieldAlert className="size-4" />
            Failed to load time series: {(error as Error).message}
          </div>
        )}

        {!isLoading && !error && (
          <div>
            {activeTab === "timeline" && (
              <MonthlyTimelineChart
                data={timelineData}
                scope={activeScope}
                blockId={selectedBlock}
              />
            )}
            {activeTab === "seasonal" && (
              <SeasonalCycleChart
                data={seasonalData}
                scope={activeScope}
                blockId={selectedBlock}
              />
            )}
            {activeTab === "annual" && (
              <AnnualTotalsChart
                data={annualData}
                scope={activeScope}
                blockId={selectedBlock}
              />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
