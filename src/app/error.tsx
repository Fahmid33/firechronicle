"use client";

import { DataState } from "@/components/ui/data-state";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div className="rounded-xl border border-border bg-card"><DataState state="error" title="This workspace could not be opened." description="An interface error interrupted this view. Your missing data has not been replaced with zero or demonstration results." onRetry={reset} /></div>;
}
