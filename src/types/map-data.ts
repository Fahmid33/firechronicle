import type { FeatureCollection, MultiPolygon, Point, Polygon } from "geojson";
import type { DataLayer } from "@/types/explorer";

// Internal rendering inputs, NOT proposed FastAPI JSON schemas. Approved adapters
// must validate transport data and supply owner-verified geometry/provenance.
export type AreaGeometry = Polygon | MultiPolygon;
export type AreaCollection = FeatureCollection<AreaGeometry>;

export type FrozenBoundary = {
  regionId: "BR-PA";
  approvedByDataOwner: true;
  crs: "EPSG:4326";
  sourceUrl: string;
  sourceLabel: string;
  version: string;
  releaseYear: number;
  processingDate: string;
  edgePolicy: string;
  geojson: AreaCollection;
};

export type BlockSelectionMetadata = {
  sourceLabel: string | null;
  boundaryVersion: string | null;
  coverageStatus: string | null;
  year: number;
  month: number;
  layer: DataLayer;
};

export type VerifiedBlocks = {
  regionId: "BR-PA";
  approvedByDataOwner: true;
  boundaryVersion: string;
  calibrationScaleKm: 50;
  clippedToStudyBoundary: true;
  sourceLabel: string;
  geojson: FeatureCollection<AreaGeometry, { block_id: string }>;
  coverage?: ReadonlyArray<{
    blockId: string;
    year: number;
    month: number;
    layer: DataLayer;
    status: string | null;
  }>;
};

export type ObservedOverlay<G extends Point | AreaGeometry> = {
  regionId: "BR-PA";
  approvedByDataOwner: true;
  boundaryVersion: string;
  year: number;
  month: number;
  layer: "observed" | "provisional";
  coverageConfirmed: boolean;
  coverageStatus: string | null;
  sourceLabel: string;
  resolutionLabel: string;
  geojson: FeatureCollection<G>;
};

export type MapData = {
  boundary: FrozenBoundary | null;
  blocks: VerifiedBlocks | null;
  hotspots: ObservedOverlay<Point> | null;
  aggregates: ObservedOverlay<AreaGeometry> | null;
};

export const PENDING_MAP_DATA: MapData = {
  boundary: null,
  blocks: null,
  hotspots: null,
  aggregates: null,
};
