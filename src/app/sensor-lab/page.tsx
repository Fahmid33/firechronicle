import type { Metadata } from "next";
import { ArrowRight, FlaskConical } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { ComparisonPanel } from "@/components/charts/comparison-panel";
import { ModelValidationCard } from "@/components/charts/model-validation-card";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "Sensor Lab" };

export default function SensorLab() {
  return (
    <>
      <PageHeading
        eyebrow="03 / Sensor Lab"
        title="The science behind the translation."
        description="A transparent look at how Aqua MODIS detections inform historical S-NPP-equivalent estimates — and where the evidence ends."
      />
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-5 text-sm">
        <FlaskConical className="size-5 text-primary" aria-hidden="true" />
        <span>Aqua MODIS predictors</span>
        <ArrowRight className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-amber-400 font-medium">firechronicle-nb2-v1.0 (GLM Negative Binomial)</span>
        <ArrowRight className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-emerald-400 font-medium">Estimated S-NPP-equivalent counts</span>
        <Badge variant="outline" className="ml-auto h-7 border-emerald-500/40 text-emerald-400">
          Production model validated
        </Badge>
      </div>

      <div className="space-y-6">
        <ComparisonPanel />
        <ModelValidationCard />
      </div>
    </>
  );
}
