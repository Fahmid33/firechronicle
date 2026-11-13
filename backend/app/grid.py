"""Spatial projection and Equal-Area Grid indexing for FireChronicle.

Enforces EPSG:6933 Equal-Area projection:
- 10 km base cells: floor(x / 10000), floor(y / 10000) -> grid_id = "{ix}_{iy}"
- 50 km calibration blocks: floor(ix / 5), floor(iy / 5) -> block_id = "{block_ix}_{block_iy}"
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("firechronicle.grid")

try:
    import pyproj
    _HAS_PYPROJ = True
    _TRANSFORMER_TO_6933 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
    _TRANSFORMER_TO_4326 = pyproj.Transformer.from_crs("EPSG:6933", "EPSG:4326", always_xy=True)
except Exception:
    _HAS_PYPROJ = False
    _TRANSFORMER_TO_6933 = None
    _TRANSFORMER_TO_4326 = None

# WGS 84 Ellipsoid constants for EPSG:6933 fallback
_WGS84_A = 6378137.0
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = 2 * _WGS84_F - _WGS84_F * _WGS84_F
_WGS84_E = math.sqrt(_WGS84_E2)
_PHI_1 = math.radians(30.0)  # Standard parallel 30 deg N
_M1 = math.cos(_PHI_1) / math.sqrt(1.0 - _WGS84_E2 * (math.sin(_PHI_1) ** 2))

# Cell dimensions in meters
CELL_SIZE_M = 10000.0  # 10 km
BLOCK_SIZE_M = 50000.0  # 50 km
CELLS_PER_BLOCK = 5

# Pará (BR-PA) Approximate Bounding Box (EPSG:4326)
PARA_BBOX_WGS84 = {
    "min_lon": -58.898,
    "max_lon": -46.061,
    "min_lat": -9.841,
    "max_lat": 2.591,
}


def _q_func(phi: float) -> float:
    s = math.sin(phi)
    es = _WGS84_E * s
    term1 = s / (1.0 - _WGS84_E2 * s * s)
    term2 = (1.0 / (2.0 * _WGS84_E)) * math.log((1.0 - es) / (1.0 + es))
    return (1.0 - _WGS84_E2) * (term1 - term2)


def lonlat_to_epsg6933(lon: float, lat: float) -> Tuple[float, float]:
    """Convert EPSG:4326 (lon, lat in degrees) to EPSG:6933 (x, y in meters)."""
    if _HAS_PYPROJ and _TRANSFORMER_TO_6933 is not None:
        try:
            x, y = _TRANSFORMER_TO_6933.transform(lon, lat)
            return float(x), float(y)
        except Exception:
            pass

    # Mathematical formulation for EPSG:6933 (Lambert Cylindrical Equal-Area)
    lam = math.radians(lon)
    phi = math.radians(lat)
    x = _WGS84_A * _M1 * lam
    y = (_WGS84_A * _q_func(phi)) / (2.0 * _M1)
    return float(x), float(y)


def epsg6933_to_lonlat(x: float, y: float) -> Tuple[float, float]:
    """Convert EPSG:6933 (x, y in meters) to EPSG:4326 (lon, lat in degrees)."""
    if _HAS_PYPROJ and _TRANSFORMER_TO_4326 is not None:
        try:
            lon, lat = _TRANSFORMER_TO_4326.transform(x, y)
            return float(lon), float(lat)
        except Exception:
            pass

    # Direct inverse for EPSG:6933
    lam = x / (_WGS84_A * _M1)
    lon = math.degrees(lam)
    q = (2.0 * y * _M1) / _WGS84_A
    
    # Newton-Raphson iteration for latitude
    phi = math.asin(min(1.0, max(-1.0, q / 2.0)))
    for _ in range(10):
        s = math.sin(phi)
        c = math.cos(phi)
        es = _WGS84_E * s
        denom = (1.0 - es * es) ** 2
        f = _q_func(phi) - q
        f_prime = (1.0 - _WGS84_E2) * (2.0 * c / denom)
        if abs(f_prime) < 1e-12:
            break
        delta = f / f_prime
        phi -= delta
        if abs(delta) < 1e-10:
            break
    lat = math.degrees(phi)
    return float(lon), float(lat)


def coords_to_grid_id(lon: float, lat: float) -> Tuple[int, int, str]:
    """Calculate 10 km base cell indices (ix, iy) and grid_id = '{ix}_{iy}'."""
    x, y = lonlat_to_epsg6933(lon, lat)
    ix = math.floor(x / CELL_SIZE_M)
    iy = math.floor(y / CELL_SIZE_M)
    return ix, iy, f"{ix}_{iy}"


def coords_to_block_id(lon: float, lat: float) -> Tuple[int, int, str]:
    """Calculate 50 km calibration block indices (block_ix, block_iy) and block_id = '{block_ix}_{block_iy}'."""
    ix, iy, _ = coords_to_grid_id(lon, lat)
    block_ix = math.floor(ix / CELLS_PER_BLOCK)
    block_iy = math.floor(iy / CELLS_PER_BLOCK)
    return block_ix, block_iy, f"{block_ix}_{block_iy}"


def grid_id_to_block_id(grid_id: str) -> str:
    """Derive 50 km block_id from 10 km grid_id without downscaling or data loss."""
    parts = grid_id.split("_")
    if len(parts) != 2:
        raise ValueError(f"Invalid grid_id format: '{grid_id}'. Expected '{{ix}}_{{iy}}'")
    ix = int(parts[0])
    iy = int(parts[1])
    block_ix = math.floor(ix / CELLS_PER_BLOCK)
    block_iy = math.floor(iy / CELLS_PER_BLOCK)
    return f"{block_ix}_{block_iy}"


def get_grid_cell_bbox_epsg6933(ix: int, iy: int) -> Tuple[float, float, float, float]:
    """Return EPSG:6933 bounds (xmin, ymin, xmax, ymax) for a 10 km cell."""
    xmin = ix * CELL_SIZE_M
    ymin = iy * CELL_SIZE_M
    xmax = (ix + 1) * CELL_SIZE_M
    ymax = (iy + 1) * CELL_SIZE_M
    return xmin, ymin, xmax, ymax


def get_block_bbox_epsg6933(block_ix: int, block_iy: int) -> Tuple[float, float, float, float]:
    """Return EPSG:6933 bounds (xmin, ymin, xmax, ymax) for a 50 km block."""
    xmin = block_ix * BLOCK_SIZE_M
    ymin = block_iy * BLOCK_SIZE_M
    xmax = (block_ix + 1) * BLOCK_SIZE_M
    ymax = (block_iy + 1) * BLOCK_SIZE_M
    return xmin, ymin, xmax, ymax


def get_grid_cell_polygon_geojson(ix: int, iy: int) -> Dict[str, Any]:
    """Generate GeoJSON geometry for a 10 km cell projected to EPSG:4326."""
    xmin, ymin, xmax, ymax = get_grid_cell_bbox_epsg6933(ix, iy)
    p1 = epsg6933_to_lonlat(xmin, ymin)
    p2 = epsg6933_to_lonlat(xmax, ymin)
    p3 = epsg6933_to_lonlat(xmax, ymax)
    p4 = epsg6933_to_lonlat(xmin, ymax)
    return {
        "type": "Polygon",
        "coordinates": [[
            [round(p1[0], 5), round(p1[1], 5)],
            [round(p2[0], 5), round(p2[1], 5)],
            [round(p3[0], 5), round(p3[1], 5)],
            [round(p4[0], 5), round(p4[1], 5)],
            [round(p1[0], 5), round(p1[1], 5)],
        ]],
    }


def get_block_polygon_geojson(block_ix: int, block_iy: int) -> Dict[str, Any]:
    """Generate GeoJSON geometry for a 50 km block projected to EPSG:4326."""
    xmin, ymin, xmax, ymax = get_block_bbox_epsg6933(block_ix, block_iy)
    p1 = epsg6933_to_lonlat(xmin, ymin)
    p2 = epsg6933_to_lonlat(xmax, ymin)
    p3 = epsg6933_to_lonlat(xmax, ymax)
    p4 = epsg6933_to_lonlat(xmin, ymax)
    return {
        "type": "Polygon",
        "coordinates": [[
            [round(p1[0], 5), round(p1[1], 5)],
            [round(p2[0], 5), round(p2[1], 5)],
            [round(p3[0], 5), round(p3[1], 5)],
            [round(p4[0], 5), round(p4[1], 5)],
            [round(p1[0], 5), round(p1[1], 5)],
        ]],
    }


def is_in_para_bbox(lon: float, lat: float) -> bool:
    """Fast bounding box check for Pará (BR-PA)."""
    return (
        PARA_BBOX_WGS84["min_lon"] <= lon <= PARA_BBOX_WGS84["max_lon"]
        and PARA_BBOX_WGS84["min_lat"] <= lat <= PARA_BBOX_WGS84["max_lat"]
    )


def build_canonical_blocks_geojson(
    data_dir: Path,
    write_output: bool = True,
) -> Optional[Dict[str, Any]]:
    """Build 50 km EPSG:6933 GeoJSON FeatureCollection from canonical grid parquet files.

    Reads `para_50km_grid_canonical.parquet` (and optional `para_area_km2` from
    `para_50km_grid_geometry.parquet`). Writes `para_blocks_50km.geojson` if
    canonical/geometry files exist and `write_output=True`. Returns None when
    neither parquet file is present.
    """
    canonical_path = data_dir / "para_50km_grid_canonical.parquet"
    geometry_path = data_dir / "para_50km_grid_geometry.parquet"

    if not canonical_path.exists() and not geometry_path.exists():
        return None

    import duckdb

    con = duckdb.connect()
    try:
        area_map: Dict[str, Optional[float]] = {}
        geom_cols: set[str] = set()
        if geometry_path.exists():
            clean_geom = geometry_path.as_posix()
            geom_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{clean_geom}'").fetchall()}
            if {"block_id", "para_area_km2"}.issubset(geom_cols):
                area_rows = con.execute(
                    f"SELECT CAST(block_id AS VARCHAR), CAST(para_area_km2 AS DOUBLE) FROM '{clean_geom}'"
                ).fetchall()
                area_map = {bid: (round(float(area), 3) if area is not None else None) for bid, area in area_rows}

        source_path = canonical_path if canonical_path.exists() else geometry_path
        clean_src = source_path.as_posix()
        src_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{clean_src}'").fetchall()}

        region_expr = "CAST(region_id AS VARCHAR)" if "region_id" in src_cols else "'BR-PA'"
        has_ix_iy = {"block_ix", "block_iy"}.issubset(src_cols)
        if has_ix_iy:
            rows = con.execute(
                f"SELECT {region_expr}, CAST(block_id AS VARCHAR), CAST(block_ix AS INTEGER), CAST(block_iy AS INTEGER) "
                f"FROM '{clean_src}' ORDER BY block_ix, block_iy"
            ).fetchall()
        else:
            raw_rows = con.execute(
                f"SELECT {region_expr}, CAST(block_id AS VARCHAR) FROM '{clean_src}' ORDER BY block_id"
            ).fetchall()
            rows = []
            for reg, bid in raw_rows:
                parts = str(bid).split("_")
                rows.append((reg, bid, int(parts[0]), int(parts[1])))

        features: List[Dict[str, Any]] = []
        for reg, bid, b_ix, b_iy in rows:
            para_area = area_map.get(bid)
            features.append(
                {
                    "type": "Feature",
                    "id": bid,
                    "properties": {
                        "block_id": bid,
                        "block_ix": int(b_ix),
                        "block_iy": int(b_iy),
                        "region_id": str(reg or "BR-PA"),
                        "resolution": "50km",
                        "spatial_system": "EPSG:6933",
                        "para_area_km2": para_area,
                    },
                    "geometry": get_block_polygon_geojson(int(b_ix), int(b_iy)),
                }
            )

        fc: Dict[str, Any] = {
            "type": "FeatureCollection",
            "name": "para_blocks_50km",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": features,
        }

        if write_output:
            out_path = data_dir / "para_blocks_50km.geojson"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fc, f, indent=2)
            logger.info(
                "Generated canonical %d-block GeoJSON -> %s",
                len(features),
                out_path,
            )

        return fc
    finally:
        con.close()
