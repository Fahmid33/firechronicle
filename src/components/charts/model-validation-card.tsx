"use client";

import { useModelMetrics } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCheck, Cpu, Database, TrendingDown } from "lucide-react";

export function ModelValidationCard() {
  const { data: metrics, isLoading, error } = useModelMetrics();

  if (isLoading) {
    return (
      <Card className="border border-border ring-0">
        <CardContent className="p-6 text-center text-xs text-muted-foreground">
          Loading authoritative validation metrics...
        </CardContent>
      </Card>
    );
  }

  if (error || !metrics) {
    return (
      <Card className="border border-destructive/40 ring-0">
        <CardContent className="p-6 text-center text-xs text-destructive">
          Failed to load model metrics: {error ? (error as Error).message : "No data"}
        </CardContent>
      </Card>
    );
  }

  const stratA = metrics.officialEvaluationMetrics.strategy_A_temporal_holdout;
  const stratB = metrics.officialEvaluationMetrics.strategy_B_geographic_holdout;
  const arch = metrics.architecture;
  const prov = metrics.trainingProvenance;

  return (
    <div className="space-y-6">
      {/* Model Benchmark Card */}
      <Card className="border border-border ring-0">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCheck className="size-4 text-primary" />
                Empirical Evaluation: NB2 v1.0 vs Baseline
              </CardTitle>
              <CardDescription className="mt-1">
                Authoritative validation against held-out S-NPP VIIRS observations.
              </CardDescription>
            </div>
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-400">
              Verified Production Benchmark
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Strategy A: Temporal Holdout */}
          <div className="rounded-lg border border-border bg-card/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-primary">
                  {stratA.title}
                </h4>
                <p className="mt-0.5 text-xs text-muted-foreground">{stratA.description}</p>
              </div>
              <span className="font-mono text-xs text-muted-foreground">N = {stratA.sampleSize.toLocaleString()}</span>
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[500px] text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="pb-2 font-medium">Metric</th>
                    <th className="pb-2 font-medium">Ratio Baseline (k = 5.87)</th>
                    <th className="pb-2 font-medium text-emerald-400">NB2 v1.0 Production</th>
                    <th className="pb-2 font-medium text-primary">Improvement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  <tr>
                    <td className="py-2 text-foreground font-medium">Mean Poisson Deviance</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.meanPoissonDeviance.toFixed(2)}</td>
                    <td className="py-2 font-mono font-bold text-emerald-300">{stratA.nb2.meanPoissonDeviance.toFixed(2)}</td>
                    <td className="py-2 font-mono text-primary flex items-center gap-1">
                      <TrendingDown className="size-3" />
                      -{(stratA.baselineRatio.meanPoissonDeviance - stratA.nb2.meanPoissonDeviance).toFixed(2)} (-54.8%)
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Mean Absolute Error (MAE)</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.mae.toFixed(2)}</td>
                    <td className="py-2 font-mono font-bold text-emerald-300">{stratA.nb2.mae.toFixed(2)}</td>
                    <td className="py-2 font-mono text-primary flex items-center gap-1">
                      <TrendingDown className="size-3" />
                      -{(stratA.baselineRatio.mae - stratA.nb2.mae).toFixed(2)} (-21.2%)
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Median Absolute Error (MedAE)</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.medae.toFixed(2)}</td>
                    <td className="py-2 font-mono text-emerald-300">{stratA.nb2.medae.toFixed(2)}</td>
                    <td className="py-2 font-mono text-primary">
                      -{(stratA.baselineRatio.medae - stratA.nb2.medae).toFixed(2)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Monthly Evaluation WAPE</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.monthlyWapePct?.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-emerald-300">{stratA.nb2.monthlyWapePct?.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-primary">
                      -{((stratA.baselineRatio.monthlyWapePct ?? 0) - (stratA.nb2.monthlyWapePct ?? 0)).toFixed(2)}%
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Monthly Evaluation R²</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.monthlyR2?.toFixed(4)}</td>
                    <td className="py-2 font-mono text-emerald-300">{stratA.nb2.monthlyR2?.toFixed(4)}</td>
                    <td className="py-2 font-mono text-emerald-400">+0.0139</td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Aggregate Count Bias</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratA.baselineRatio.aggregateBiasPct.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-emerald-300">{stratA.nb2.aggregateBiasPct.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-muted-foreground">+1.41% closer to 0</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Strategy B: Geographic Holdout */}
          <div className="rounded-lg border border-border bg-card/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-primary">
                  {stratB.title}
                </h4>
                <p className="mt-0.5 text-xs text-muted-foreground">{stratB.description}</p>
              </div>
              <span className="font-mono text-xs text-muted-foreground">N = {stratB.sampleSize.toLocaleString()}</span>
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[500px] text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="pb-2 font-medium">Metric</th>
                    <th className="pb-2 font-medium">Ratio Baseline (k = 5.98)</th>
                    <th className="pb-2 font-medium text-emerald-400">NB2 v1.0 Production</th>
                    <th className="pb-2 font-medium text-primary">Improvement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  <tr>
                    <td className="py-2 text-foreground font-medium">Mean Poisson Deviance</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratB.baselineRatio.meanPoissonDeviance.toFixed(2)}</td>
                    <td className="py-2 font-mono font-bold text-emerald-300">{stratB.nb2.meanPoissonDeviance.toFixed(2)}</td>
                    <td className="py-2 font-mono text-primary flex items-center gap-1">
                      <TrendingDown className="size-3" />
                      -{(stratB.baselineRatio.meanPoissonDeviance - stratB.nb2.meanPoissonDeviance).toFixed(2)} (-62.8%)
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Mean Absolute Error (MAE)</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratB.baselineRatio.mae.toFixed(2)}</td>
                    <td className="py-2 font-mono font-bold text-emerald-300">{stratB.nb2.mae.toFixed(2)}</td>
                    <td className="py-2 font-mono text-primary flex items-center gap-1">
                      <TrendingDown className="size-3" />
                      -{(stratB.baselineRatio.mae - stratB.nb2.mae).toFixed(2)} (-33.6%)
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-foreground font-medium">Spatial Evaluation WAPE</td>
                    <td className="py-2 font-mono text-muted-foreground">{stratB.baselineRatio.spatialWapePct?.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-emerald-300">{stratB.nb2.spatialWapePct?.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-primary">
                      -{((stratB.baselineRatio.spatialWapePct ?? 0) - (stratB.nb2.spatialWapePct ?? 0)).toFixed(2)}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Model Architecture & Provenance Grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="border border-border ring-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Cpu className="size-4 text-primary" />
              Statistical Specification
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Model Family</span>
              <span className="font-mono text-foreground">{arch.family}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Distribution</span>
              <span className="font-mono text-foreground">{arch.distribution} (Negative Binomial 2)</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Link Function</span>
              <span className="font-mono text-foreground">{arch.link}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Dispersion Parameter (α)</span>
              <span className="font-mono text-foreground">{arch.dispersionAlpha} (overdispersion modeled)</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Baseline Multiplier (k)</span>
              <span className="font-mono text-foreground">{arch.baselineRatioMultiplierK}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">AIC / BIC</span>
              <span className="font-mono text-foreground">210,357.6 / 210,478.2</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border ring-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Database className="size-4 text-primary" />
              Training Provenance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Calibration Overlap</span>
              <span className="font-mono text-foreground">{prov.calibrationDataset}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Paired-Positive Cell-Months</span>
              <span className="font-mono text-foreground">{prov.trainingRecordsCount.toLocaleString()}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Paired MODIS Hotspots</span>
              <span className="font-mono text-foreground">{prov.pairedModisTotal.toLocaleString()}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Paired VIIRS Hotspots</span>
              <span className="font-mono text-foreground">{prov.pairedViirsTotal.toLocaleString()}</span>
            </div>
            <div className="flex justify-between border-b border-border/50 pb-2">
              <span className="text-muted-foreground">Spatial Units</span>
              <span className="font-mono text-foreground">568 canonical 50 km blocks</span>
            </div>
            <div className="text-[11px] text-muted-foreground/80 pt-1">
              {prov.excludedPeriod}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
