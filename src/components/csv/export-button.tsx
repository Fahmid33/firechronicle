"use client";

import { useState } from "react";
import { Download, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSelection } from "@/store/selection-store";
import { useStatewideTimeSeries, useBlocksSummary } from "@/lib/api/queries";
import { generateTimeSeriesCsv, downloadCsv } from "@/lib/csv/csv-export";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
  variant?: "outline" | "default" | "secondary" | "ghost";
  size?: "sm" | "default" | "lg";
}

export function ExportButton({ className, variant = "outline", size = "sm" }: Props) {
  const [downloaded, setDownloaded] = useState(false);
  const selectedBlock = useSelection((s) => s.block_id);

  const { data: statewide, isLoading: swLoading } = useStatewideTimeSeries();
  const { data: blocksSummary, isLoading: bLoading } = useBlocksSummary();

  const isSynthetic = process.env.NEXT_PUBLIC_DATA_MODE === "synthetic" || process.env.NEXT_PUBLIC_USE_MOCKS === "true";

  function handleExport() {
    if (!statewide) return;

    const csvContent = generateTimeSeriesCsv({
      regionId: "BR-PA",
      blockId: selectedBlock,
      statewide,
      blocksSummary,
      isSynthetic,
    });

    const targetScope = selectedBlock ? `block_${selectedBlock}` : "statewide";
    const filename = `firechronicle_BR-PA_${targetScope}_2002_2020.csv`;

    downloadCsv(filename, csvContent);
    setDownloaded(true);
    setTimeout(() => setDownloaded(false), 2500);
  }

  const isLoading = swLoading || (selectedBlock && bLoading);
  const label = selectedBlock ? `Export Block ${selectedBlock} CSV` : "Export Statewide CSV";

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      disabled={isLoading || !statewide}
      onClick={handleExport}
      className={cn("flex items-center gap-1.5 font-medium transition-all", className)}
      title="Download authoritative monthly time series (2002–2020 · 228 rows) formatted to RFC 4180"
    >
      {downloaded ? (
        <>
          <Check className="size-3.5 text-emerald-400" />
          <span>Downloaded!</span>
        </>
      ) : (
        <>
          <Download className="size-3.5 text-primary" />
          <span>{label}</span>
        </>
      )}
    </Button>
  );
}
