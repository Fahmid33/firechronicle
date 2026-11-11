import { AlertCircle, Ban, Database, LoaderCircle, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { PanelState } from "@/types/explorer";
import { cn } from "@/lib/utils";

const icons = { pending: Database, loading: LoaderCircle, empty: Search, error: AlertCircle, unsupported: Ban };

export function DataState({ state = "pending", title, description, onRetry, compact = false }: {
  state?: PanelState; title: string; description: string; onRetry?: () => void; compact?: boolean;
}) {
  const Icon = icons[state];
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "gap-3 px-4 py-8" : "gap-4 px-6 py-12")} aria-busy={state === "loading"}>
      <div className={cn("flex size-12 items-center justify-center rounded-xl border border-border bg-surface-elevated", state === "error" ? "text-destructive" : "text-muted-foreground")}>
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <div className="max-w-sm space-y-2" role={state === "error" ? "alert" : undefined}>
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
      {state === "loading" && <div className="w-48 space-y-2" aria-hidden="true"><Skeleton className="h-2 w-full" /><Skeleton className="mx-auto h-2 w-2/3" /></div>}
      {state === "error" && onRetry && <Button className="h-11" variant="outline" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
