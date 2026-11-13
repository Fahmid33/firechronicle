import type { Metadata } from "next";
import { BookOpen, Database, MapPin, ScanLine, ShieldCheck } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScienceStatus } from "@/components/ui/science-status";

export const metadata: Metadata = { title: "Methodology" };

export default function Methodology() {
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeading
        eyebrow="04 / Methodology"
        title="A clear view of what the data can say."
        description="FireChronicle explores recorded satellite hotspot detections in Pará, Brazil. Its purpose is historical perspective, grounded in honest measurements and visible limitations."
      />
      <div className="mb-6 flex gap-3 rounded-xl border border-primary/30 bg-primary/5 p-5">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-sm leading-relaxed">
          A hotspot is a recorded fire-positive satellite pixel or detection. It is{" "}
          <strong>not a distinct wildfire, burned area, fire intensity or fire-spread forecast.</strong>
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card id="geography" className="scroll-mt-6 border border-border ring-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="size-4 text-primary" aria-hidden="true" />
              One frozen study boundary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              Pará state, Brazil (BR-PA) is the only analytical region. The release uses the official frozen
              IBGE 2024 state polygon (<code>PA_UF_2024.zip</code>, transformed from SIRGAS 2000 / EPSG:4674 to
              WGS 84 / EPSG:4326).
            </p>
            <p>
              Every raw detection must pass this upstream geographic boundary filter. A Brazil archive or Amazon
              basemap does not expand coverage. Official IBGE boundary assets are connected and verified in the
              interactive map.
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border ring-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScanLine className="size-4 text-primary" aria-hidden="true" />
              Scale is part of the result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              The shared grid uses canonical 50 km blocks defined in WGS 84 / NSIDC EASE-Grid 2.0 Global
              (EPSG:6933, Lambert Cylindrical Equal Area), transformed to EPSG:4326 for map visualization.
            </p>
            <p>
              Exactly 568 canonical blocks cover the Pará study domain. Historical model outputs remain strictly
              at the validated 50 km block scale. Point locations and 10 km cells are not fabricated; canonical
              border blocks extending beyond Pará retain clipped-support limitations.
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border ring-0 md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="size-4 text-primary" aria-hidden="true" />
              Three distinct kinds of evidence
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-3">
              <ScienceStatus layer="estimated" />
              <p className="text-sm leading-relaxed text-muted-foreground">
                Supported mid-2002–2011 estimates use historical Aqua MODIS predictors calibrated to VIIRS S-NPP scale
                via NB2 v1.0. These are model-extrapolated S-NPP-equivalent detection counts, not raw S-NPP records.
              </p>
            </div>
            <div className="space-y-3">
              <ScienceStatus layer="observed" />
              <p className="text-sm leading-relaxed text-muted-foreground">
                From 2012, verified S-NPP VIIRS 375m active fire detections (NASA FIRMS archive) are connected. MODIS
                overlap supports calibration; MODIS and VIIRS counts are never added together.
              </p>
            </div>
            <div className="space-y-3">
              <ScienceStatus layer="provisional" />
              <p className="text-sm leading-relaxed text-muted-foreground">
                Recent NRT records are optional and remain provisional. Near-real-time ingestion requires the live API
                backend; no live alert capability or complete recent archive is fabricated in static demo mode.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border ring-0">
          <CardHeader>
            <CardTitle>Unknown is not zero</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              Missing passes and pre-commissioning periods (Jan–Jun 2002) remain NULL. A missing detection row does
              not prove clear-sky coverage or zero fire activity.
            </p>
            <p>
              Strict day/night aggregation contract (<code>daynight=ALL</code>): at block level, D+N is valid only if
              both passes are non-null; single-pass blocks are preserved as NULL. Statewide strict ALL sums only
              complete D+N pairs; available-pass totals are documented separately.
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border ring-0">
          <CardHeader>
            <CardTitle>Validation before comparison</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              The production model is a Negative Binomial GLM (<code>firechronicle-nb2-v1.0</code>, dispersion{" "}
              &alpha; = 0.3394), validated against independent spatial block holdouts and complete-year test sets.
            </p>
            <p>
              Split-specific metrics confirm stability: out-of-sample block holdout achieves R&sup2; = 0.887 and
              Poisson deviance 11.23, outperforming Poisson and ratio-of-totals baselines. Sensor Lab validation
              metrics are active and connected.
            </p>
          </CardContent>
        </Card>
      </div>

      <section className="mt-6 flex flex-wrap items-start gap-3 rounded-xl border border-border p-5">
        <BookOpen className="mt-1 size-5 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-medium">Sources & release status</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Reference sources are NASA FIRMS Aqua MODIS (MCD14DL) and S-NPP VIIRS (VNP14IMGTDL); official Pará boundary
            is from IBGE (PA_UF_2024.zip). The application is currently running in verified precomputed static JSON mode
            (<code>NEXT_PUBLIC_DATA_MODE=static</code>). Core scientific records (2002–2020), 568-block canonical grid,
            and Sensor Lab metrics are fully connected. Live backend API integration (<code>LiveApiAdapter</code>) is
            pending full multi-year block summary endpoint extensions from the FastAPI service.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">
            Scientific authority: FireChronicle team rulebook · Pará release amendment v1.0 · November 2026.
          </p>
        </div>
      </section>
    </div>
  );
}
