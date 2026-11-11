import type { Metadata } from "next";
import { PageHeading } from "@/components/layout/page-heading";
import { AnalysisLayout } from "@/components/layout/analysis-panel";
import { PeriodControls } from "@/components/calendar/period-controls";
import { CalendarShell } from "@/components/calendar/calendar-shell";
import { ComparisonPanel } from "@/components/charts/comparison-panel";

export const metadata: Metadata = { title: "Time Machine" };

export default function TimeMachine() {
  return <><PageHeading eyebrow="02 / Time Machine" title="History, month by month." description="Explore the historical record with a clear distinction between estimates, observations and genuine data gaps." /><AnalysisLayout><PeriodControls /><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-dashed border-border bg-card p-4"><p className="text-xs font-medium text-status-estimated">Mid-2002–2011 / Estimated</p><p className="mt-2 text-xs leading-relaxed text-muted-foreground">Aqua MODIS-based historical extrapolation, where supported.</p></div><div className="rounded-lg border border-border bg-card p-4"><p className="text-xs font-medium text-status-observed">2012 onward / Observed</p><p className="mt-2 text-xs leading-relaxed text-muted-foreground">Actual S-NPP detections where available. NRT remains Provisional.</p></div></div><CalendarShell /><ComparisonPanel seasonal /></AnalysisLayout></>;
}
