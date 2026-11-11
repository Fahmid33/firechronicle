import { Circle, Clock3, ScanLine } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { LAYERS, type DataLayer } from "@/types/explorer";

export function LayerMark({ layer }: { layer: DataLayer }) {
  if (layer === "provisional") return <Clock3 className="size-4 text-status-provisional" aria-hidden="true" />;
  if (layer === "estimated") return <ScanLine className="size-4 text-status-estimated" aria-hidden="true" />;
  return <Circle className="size-3 fill-current text-status-observed" aria-hidden="true" />;
}

export function ScienceStatus({ layer }: { layer: DataLayer }) {
  return <Badge variant="outline" className={cn("h-auto max-w-full gap-2 rounded-md px-2 py-1 text-wrap leading-relaxed", layer === "observed" ? "text-status-observed" : "text-status-estimated", layer === "estimated" && "border-dashed", layer === "provisional" && "border-dotted")}><LayerMark layer={layer} />{LAYERS[layer].description}</Badge>;
}
