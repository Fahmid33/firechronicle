"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, BookOpen, CalendarDays, ChevronLeft, ChevronRight, Compass, FlaskConical, Globe2, Menu, Satellite, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SelectionProvider } from "@/store/selection-store";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Explore", icon: Compass },
  { href: "/time-machine", label: "Time Machine", icon: CalendarDays },
  { href: "/sensor-lab", label: "Sensor Lab", icon: FlaskConical },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
];

function Navigation({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return <nav aria-label="Main navigation" className="space-y-2 p-3">{navigation.map(({ href, label, icon: Icon }) => (
    <Tooltip key={href}>
      <TooltipTrigger render={<Link href={href} onClick={onNavigate} aria-current={pathname === href ? "page" : undefined} aria-label={label} className={cn("relative flex min-h-11 items-center gap-3 rounded-lg border border-transparent px-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground", collapsed && "justify-center px-0", pathname === href && "border-border bg-accent text-foreground before:absolute before:inset-y-3 before:left-0 before:w-0.5 before:rounded-full before:bg-primary")} />}>
        <Icon className="size-[18px] shrink-0" aria-hidden="true" /><span className={collapsed ? "sr-only" : ""}>{label}</span>
      </TooltipTrigger>
      {collapsed && <TooltipContent side="right" className="bg-popover text-foreground">{label}</TooltipContent>}
    </Tooltip>
  ))}</nav>;
}

export function DashboardShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  return <SelectionProvider><TooltipProvider delay={200}>
    <a href="#main-content" className="fixed top-2 left-2 z-[100] -translate-y-24 rounded-md bg-primary px-4 py-3 text-primary-foreground focus:translate-y-0">Skip to content</a>
    <header className="relative z-30 flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-3 md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger render={<Button variant="ghost" size="icon" className="size-11 md:hidden" aria-label="Open navigation" />}><Menu /></SheetTrigger>
          <SheetContent side="left" className="w-[min(320px,90vw)] overflow-y-auto">
            <SheetHeader><SheetTitle>FireChronicle</SheetTitle><SheetDescription>Pará Earth-observation explorer</SheetDescription></SheetHeader>
            <Navigation onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
        <Link href="/" className="flex items-center gap-3" aria-label="FireChronicle home">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-primary/40 bg-primary/10 text-primary"><Satellite className="size-5" aria-hidden="true" /></span>
          <span><span className="block text-base font-semibold tracking-tight">Fire<span className="text-primary">Chronicle</span></span><span className="hidden text-xs text-muted-foreground sm:block">Earth observation / historical perspective</span></span>
        </Link>
        <div className="ml-5 hidden items-center gap-2 border-l border-border pl-6 text-sm lg:flex"><Globe2 className="size-4 text-primary" aria-hidden="true" /><span>Pará, Brazil</span><span className="font-mono text-xs text-muted-foreground">BR-PA</span></div>
      </div>
      <div className="flex items-center gap-4">
        <div className="hidden text-right xl:block"><p className="text-xs text-foreground">Aqua MODIS <span className="px-1 text-muted-foreground">/</span> VIIRS S-NPP</p><p className="mt-0.5 text-xs text-muted-foreground">NASA FIRMS · reference sources</p></div>
        <Link href="/methodology" aria-label="About and methodology" className="flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-lg border border-border px-3 text-xs text-muted-foreground transition-colors hover:border-input hover:text-foreground"><BookOpen className="size-4" aria-hidden="true" /><span className="hidden sm:inline">About & methodology</span><ArrowUpRight className="hidden size-3 sm:block" aria-hidden="true" /></Link>
      </div>
    </header>
    <div className="flex flex-1">
      <aside aria-label="Workspace navigation" className={cn("sticky top-0 hidden h-[calc(100svh-65px)] shrink-0 flex-col border-r border-border bg-card/40 md:flex", collapsed ? "w-[72px]" : "w-56")}>
        <div className="flex h-16 items-center justify-center border-b border-border">
          <Button variant="ghost" size="icon" className="size-11 text-muted-foreground" aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight /> : <ChevronLeft />}</Button>
        </div>
        <Navigation collapsed={collapsed} />
        <div className="mt-auto border-t border-border p-4 text-muted-foreground">{collapsed ? <ShieldCheck className="mx-auto size-5" aria-label="Pará-only analytical coverage" /> : <p className="text-xs leading-relaxed">One study region.<br /><span className="text-foreground">Transparent science.</span></p>}</div>
      </aside>
      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 p-4 outline-none lg:p-6">{children}</main>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-xs text-muted-foreground md:px-6"><span>FireChronicle <span className="px-1">/</span> NASA Space Apps Challenge 2026</span><span>Pará (BR-PA) · Static demo mode (live API backend integration pending)</span></footer>
  </TooltipProvider></SelectionProvider>;
}
