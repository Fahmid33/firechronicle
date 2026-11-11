"use client";

import { CalendarDays, Info } from "lucide-react";
import { useSelection } from "@/store/selection-store";
import { MONTHS } from "@/types/explorer";
import { Button } from "@/components/ui/button";
import { ScienceStatus } from "@/components/ui/science-status";
import { cn } from "@/lib/utils";

export function CalendarShell() {
  const year = useSelection(s => s.year);
  const selectedMonth = useSelection(s => s.month);
  const setPeriod = useSelection(s => s.setPeriod);
  return <section className="overflow-hidden rounded-xl border border-border bg-card" aria-labelledby="calendar-title">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5"><div><h2 id="calendar-title" className="flex items-center gap-2 text-base font-medium"><CalendarDays className="size-4 text-primary" aria-hidden="true" />{year} <span className="text-muted-foreground">/ Monthly record</span></h2><p className="mt-2 text-xs text-muted-foreground">Choose a month to update the shared observation period.</p></div><ScienceStatus layer={year < 2012 ? "estimated" : "observed"} /></div>
    <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4">
      {MONTHS.map((month, i) => <Button key={month} variant="ghost" aria-pressed={selectedMonth === i + 1} aria-label={`${month} ${year}, availability unknown`} onClick={() => setPeriod(year, i + 1)} className={cn("h-auto min-h-28 flex-col items-start justify-between gap-3 rounded-lg border border-dotted border-input px-4 py-3 text-left transition-colors", selectedMonth === i + 1 && "border-solid border-primary bg-primary/5 ring-1 ring-primary")}><span className="flex w-full items-center justify-between text-sm">{month.slice(0, 3)}<span className="text-xs text-muted-foreground">{String(i + 1).padStart(2, "0")}</span></span><span className="text-xl text-muted-foreground">—</span><span className="text-xs font-normal text-muted-foreground">Awaiting coverage</span></Button>)}
    </div>
    <div className="flex gap-2 border-t border-border p-4 text-xs leading-relaxed text-muted-foreground"><Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><p>No monthly counts have been loaded. These empty month controls do not indicate verified zeros or processing status. Daily detail will appear only where supported.</p></div>
  </section>;
}
