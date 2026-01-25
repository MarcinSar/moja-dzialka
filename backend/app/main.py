"""
moja-dzialka Backend API

FastAPI application for plot search and AI conversation.
"""

from contextlib import asynccontextmanager
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.services.database import check_all_connections, close_all_connections
from app.api.conversation_v2 import router as conversation_router
from app.api.search import router as search_router
from app.api.lidar import router as lidar_router
from app.api.leads import router as leads_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting moja-dzialka API...")

    # Check database connections
    db_status = await check_all_connections()
    for db, status in db_status.items():
        if status["connected"]:
            logger.info(f"{db}: connected (latency: {status.get('latency_ms', 'N/A')}ms)")
        else:
            logger.warning(f"{db}: not connected - {status.get('error', 'unknown error')}")

    yield

    # Shutdown
    logger.info("Shutting down moja-dzialka API...")
    await close_all_connections()


app = FastAPI(
    title="moja-dzialka API",
    description="System rekomendacji dzialek budowlanych w województwie pomorskim",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# INCLUDE ROUTERS
# =============================================================================

# All APIs now use v2 architecture
app.include_router(conversation_router, prefix="/api")  # /api/v2/conversation
app.include_router(search_router, prefix="/api/v1")     # Search stays at v1 (no changes needed)
app.include_router(lidar_router, prefix="/api/v1")      # LiDAR stays at v1
app.include_router(leads_router, prefix="/api/v1")      # Leads at v1


# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "moja-dzialka"}


@app.get("/health")
async def health():
    """Detailed health check with database status."""
    start = time.time()
    db_status = await check_all_connections()
    check_time_ms = int((time.time() - start) * 1000)

    # Determine overall status
    all_connected = all(s.get("connected", False) for s in db_status.values())
    status = "ok" if all_connected else "degraded"

    return {
        "status": status,
        "version": "0.1.0",
        "check_time_ms": check_time_ms,
        "databases": db_status,
    }


@app.get("/api")
async def api_info():
    """API information and available endpoints."""
    return {
        "name": "moja-dzialka API",
        "version": "2.0.0",
        "architecture": "Software 3.0 with 7-layer memory model",
        "endpoints": {
            "conversation": {
                "websocket": "/api/v2/conversation/ws",
                "chat": "POST /api/v2/conversation/chat",
                "state": "GET /api/v2/conversation/user/{user_id}/state",
                "history": "GET /api/v2/conversation/user/{user_id}/history",
                "funnel": "GET /api/v2/conversation/user/{user_id}/funnel",
                "finalize": "POST /api/v2/conversation/user/{user_id}/finalize",
                "delete": "DELETE /api/v2/conversation/user/{user_id}",
            },
            "search": {
                "search": "POST /api/v1/search/",
                "similar": "GET /api/v1/search/similar/{parcel_id}",
                "parcel": "GET /api/v1/search/parcel/{parcel_id}",
                "map": "POST /api/v1/search/map",
                "gminy": "GET /api/v1/search/gminy",
                "gmina": "GET /api/v1/search/gmina/{name}",
                "mpzp_symbols": "GET /api/v1/search/mpzp-symbols",
                "stats": "GET /api/v1/search/stats",
            },
            "lidar": {
                "request": "POST /api/v1/lidar/request",
                "status": "GET /api/v1/lidar/status/{job_id}",
                "check": "GET /api/v1/lidar/check",
                "tile": "GET /api/v1/lidar/tile/{tile_id}/{path}",
            },
            "leads": {
                "submit": "POST /api/v1/leads",
                "count": "GET /api/v1/leads/count",
            },
            "health": {
                "root": "GET /",
                "health": "GET /health",
            },
        },
    }
