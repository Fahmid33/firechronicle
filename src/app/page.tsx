import Link from "next/link";
import { ArrowRight, CalendarDays, Info } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { AnalysisLayout } from "@/components/layout/analysis-panel";
import { MapWorkspace } from "@/components/map/map-workspace";
import { PeriodControls } from "@/components/calendar/period-controls";

export default function Explore() {
  return <>
    <PageHeading eyebrow="01 / Earth observation explorer" title="A longer view of fire activity." description="Explore satellite hotspot detections across time in Pará, Brazil. Historical estimates and actual observations, clearly distinguished." action={<span className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs text-muted-foreground"><Info className="size-3.5" aria-hidden="true" />Awaiting scientific data</span>} />
    <AnalysisLayout><MapWorkspace /><PeriodControls />
      <Link href="/time-machine" className="group flex min-h-20 items-center gap-4 rounded-xl border border-border bg-card px-5 py-4 transition-colors hover:bg-accent"><span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border text-primary"><CalendarDays className="size-5" aria-hidden="true" /></span><div className="min-w-0"><h2 className="text-sm font-medium">Every month has a context.</h2><p className="mt-1 text-xs leading-relaxed text-muted-foreground">Open Time Machine to explore the calendar and its data gaps.</p></div><ArrowRight className="ml-auto size-4 shrink-0 text-primary" aria-hidden="true" /></Link>
    </AnalysisLayout>
  </>;
}
