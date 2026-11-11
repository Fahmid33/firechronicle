import { DataState } from "@/components/ui/data-state";

export default function Loading() {
  return <div className="min-h-[60svh] rounded-xl border border-border bg-card"><DataState state="loading" title="Opening your workspace" description="Preparing the interface. No scientific values are being inferred." /></div>;
}
