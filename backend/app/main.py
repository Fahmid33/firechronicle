"""FastAPI application entry point for FireChronicle Backend.

NASA Space Apps 2026: Harmonization of MODIS and VIIRS Hot Spots (Pará, Brazil).
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import get_db, validate_and_initialize_db
from app.routers import api_v1, ml_bridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("firechronicle.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI Lifespan Context Manager:
    - Runs BEFORE the server starts listening for requests.
    - Calls validate_and_initialize_db().
    - If duplicates or errors occur, sys.exit(1) inside db.py kills the process instantly,
      preventing the API from appearing operational.
    """
    print("[Startup] Initializing FireChronicle Backend...")

    # Run our strict validation & connection routine
    db_conn = validate_and_initialize_db(require_full_nine_years=False)

    # Store the active DuckDB connection in app state so endpoints can query it
    app.state.db = db_conn

    yield  # Server runs and handles requests here...

    # --- SHUTDOWN PHASE ---
    print("[Shutdown] Closing database connection...")
    get_db.cache_clear()
    db_conn.close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="FireChronicle — Pará, Brazil Backend",
        description=(
            "NASA Space Apps 2026 Submission: Harmonization of MODIS and VIIRS Hot Spots.\n\n"
            "Serves harmonized historical estimates (2002-2011) and observed VIIRS S-NPP detections (2012+) "
            "for Pará state (BR-PA), Brazil using DuckDB, Parquet, and EPSG:6933 equal-area spatial indexing."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS strictly using FRONTEND_URL environment variable (never allow "*")
    frontend_origins = [
        origin.strip()
        for origin in settings.FRONTEND_URL.split(",")
        if origin.strip() and origin.strip() != "*"
    ]
    if not frontend_origins:
        frontend_origins = ["http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning("ValueError on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Bad Request", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal Server Error", "detail": str(exc)},
        )

    # Register Routers
    app.include_router(api_v1.router)
    app.include_router(ml_bridge.router)

    @app.get("/health", summary="Health check endpoint")
    def health_check():
        """Health check endpoint. Only reachable if startup validation passed successfully."""
        return {
            "status": "operational",
            "database_integrity": "verified",
            "model_status": "not_ready",
        }

    @app.get("/", summary="Root API health and metadata")
    def root():
        return {
            "name": "FireChronicle — Pará, Brazil Backend",
            "challenge": "NASA Space Apps 2026: Harmonization of MODIS and VIIRS Hot Spots",
            "release_geography": {
                "region_id": settings.ANALYSIS_REGION_ID,
                "region_name": settings.ANALYSIS_REGION_NAME,
                "spatial_system": "EPSG:6933 Equal-Area (10km base cell, 50km block)",
            },
            "status": "operational",
            "documentation": "/docs",
            "endpoints": {
                "summary": "/api/v1/summary",
                "spatial": "/api/v1/spatial?year=2018&month=8&resolution=50km",
                "blocks": "/api/v1/blocks",
                "hotspots": "/api/v1/hotspots?limit=10",
                "sensor_lab_calibration": "/api/v1/sensor-lab/calibration",
                "sensor_lab_metrics": "/api/v1/sensor-lab/metrics",
                "model_info": "/api/v1/model/info",
                "predict": "/api/v1/predict",
                "boundary": "/api/v1/boundary",
                "ml_bridge_status": "/ml-bridge/status",
            },
        }

    return app


app = create_app()
