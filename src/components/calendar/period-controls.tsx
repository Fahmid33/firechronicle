"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useSelection } from "@/store/selection-store";
import { FIRST_YEAR, LAST_YEAR, MONTHS } from "@/types/explorer";

export function PeriodControls() {
  const year = useSelection(s => s.year);
  const month = useSelection(s => s.month);
  const setPeriod = useSelection(s => s.setPeriod);
  function move(delta: number) {
    const index = year * 12 + month - 1 + delta;
    setPeriod(Math.floor(index / 12), index % 12 + 1);
  }
  return <section aria-label="Observation period controls" className="rounded-xl border border-border bg-card p-4">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><CalendarDays className="size-5 text-primary" aria-hidden="true" /><div><h2 className="text-sm font-medium">Observation period</h2><p className="mt-1 text-xs text-muted-foreground">2002–2020 verified archive · 2021+ pending data</p></div></div>
      <div className="flex flex-wrap items-end gap-2">
        <Button variant="ghost" size="icon" className="size-11" aria-label="Previous month" disabled={year === FIRST_YEAR && month === 1} onClick={() => move(-1)}><ChevronLeft /></Button>
        <div className="space-y-1"><label id="month-label" className="block text-xs text-muted-foreground">Month</label><Select value={String(month)} onValueChange={v => v && setPeriod(year, Number(v))}><SelectTrigger aria-labelledby="month-label" className="h-11 min-w-32 data-[size=default]:h-11"><SelectValue>{MONTHS[month - 1]}</SelectValue></SelectTrigger><SelectContent alignItemWithTrigger={false}>{MONTHS.map((name, i) => <SelectItem className="min-h-11" key={name} value={String(i + 1)}>{name}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><label id="year-label" className="block text-xs text-muted-foreground">Year</label><Select value={String(year)} onValueChange={v => v && setPeriod(Number(v), month)}><SelectTrigger aria-labelledby="year-label" className="h-11 min-w-24 data-[size=default]:h-11"><SelectValue>{year}</SelectValue></SelectTrigger><SelectContent alignItemWithTrigger={false}>{Array.from({ length: LAST_YEAR - FIRST_YEAR + 1 }, (_, i) => FIRST_YEAR + i).map(y => <SelectItem className="min-h-11" key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent></Select></div>
        <Button variant="ghost" size="icon" className="size-11" aria-label="Next month" disabled={year === LAST_YEAR && month === 12} onClick={() => move(1)}><ChevronRight /></Button>
      </div>
    </div>
    <p className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">2002–2026 is a navigation range, not a complete data archive. Changing era selects the corresponding historical or observed layer.</p>
  </section>;
}
