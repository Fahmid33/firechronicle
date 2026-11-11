import { ChartNoAxesCombined } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DataState } from "@/components/ui/data-state";

export function ComparisonPanel({ seasonal = false }: { seasonal?: boolean }) {
  return <Card className="border border-border ring-0"><CardHeader><CardTitle className="flex items-center gap-2"><ChartNoAxesCombined className="size-4 text-primary" aria-hidden="true" />{seasonal ? "Seasonal perspective" : "Predicted and observed"}</CardTitle><CardDescription>{seasonal ? "Patterns across comparable months and measurement tiers." : "Held-out S-NPP observations against MODIS-based estimates."}</CardDescription></CardHeader><CardContent><div className="rounded-lg border border-dashed border-border bg-background/50"><DataState state={seasonal ? "empty" : "pending"} title={seasonal ? "A time series needs a supported area." : "Evidence before a curve."} description={seasonal ? "Seasonal summaries will appear after verified block selection and comparable monthly data are available." : "The held-out predictions and actual observations have not been supplied. No comparison curve or confidence interval is shown."} /></div></CardContent></Card>;
}
