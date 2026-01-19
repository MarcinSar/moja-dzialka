"""
REST API endpoints for LiDAR data processing.

Endpoints:
- POST /api/v1/lidar/request - Start LiDAR processing job
- GET /api/v1/lidar/status/{job_id} - Get job status
- GET /api/v1/lidar/tile/{tile_id}/{path} - Serve Potree files
- GET /api/v1/lidar/check - Check if LiDAR is available for location
"""

import json
import os
from pathlib import Path
from typing import Optional

import redis
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.tasks import celery_app
from app.tasks.lidar_tasks import (
    POTREE_PATH,
    check_tile_availability,
    process_lidar_for_parcel,
)

router = APIRouter(prefix="/lidar", tags=["lidar"])

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL)


class LidarRequest(BaseModel):
    """Request to start LiDAR processing."""
    parcel_id: str = Field(..., description="Unique parcel identifier")
    lat: float = Field(..., ge=49, le=55, description="Latitude (WGS84)")
    lon: float = Field(..., ge=14, le=24, description="Longitude (WGS84)")
    session_id: str = Field(..., description="WebSocket session ID for progress updates")
    parcel_bbox: Optional[tuple] = Field(
        None,
        description="Optional (min_x, min_y, max_x, max_y) in EPSG:2180 to crop"
    )


class LidarResponse(BaseModel):
    """Response from LiDAR request."""
    job_id: str
    status: str
    message: str


class LidarStatusResponse(BaseModel):
    """Response from status check."""
    job_id: str
    status: str  # pending, processing, ready, error
    progress: float
    message: str
    potree_url: Optional[str] = None


class LidarCheckResponse(BaseModel):
    """Response from availability check."""
    tile_id: str
    available: bool
    cached: bool
    estimated_time_seconds: int


@router.post("/request", response_model=LidarResponse)
async def request_lidar_processing(request: LidarRequest) -> LidarResponse:
    """
    Start LiDAR processing for a parcel.

    The job runs asynchronously. Progress updates are sent via WebSocket
    to the session_id channel. Use GET /status/{job_id} to poll status.

    Returns:
        job_id to track the processing
    """
    # Check if already processing for this parcel/session
    redis_client = get_redis()
    existing_job = redis_client.get(f"lidar:active:{request.session_id}:{request.parcel_id}")

    if existing_job:
        job_id = existing_job.decode()
        result = AsyncResult(job_id, app=celery_app)
        if not result.ready():
            return LidarResponse(
                job_id=job_id,
                status="processing",
                message="Job już w toku"
            )

    # Start new Celery task
    task = process_lidar_for_parcel.delay(
        parcel_id=request.parcel_id,
        lat=request.lat,
        lon=request.lon,
        session_id=request.session_id,
        parcel_bbox=request.parcel_bbox,
    )

    # Track active job
    redis_client.setex(
        f"lidar:active:{request.session_id}:{request.parcel_id}",
        3600,  # 1 hour TTL
        task.id,
    )

    return LidarResponse(
        job_id=task.id,
        status="pending",
        message="Przetwarzanie rozpoczęte"
    )


@router.get("/status/{job_id}", response_model=LidarStatusResponse)
async def get_lidar_status(job_id: str) -> LidarStatusResponse:
    """
    Get status of a LiDAR processing job.

    Use this endpoint for polling if WebSocket is not available.
    """
    # First check Redis cache (faster than Celery result backend)
    redis_client = get_redis()
    cached_status = redis_client.get(f"lidar:job:{job_id}:status")

    if cached_status:
        data = json.loads(cached_status)
        return LidarStatusResponse(
            job_id=job_id,
            status=data.get("status", "unknown"),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            potree_url=data.get("potree_url"),
        )

    # Fallback to Celery result
    result = AsyncResult(job_id, app=celery_app)

    if result.pending:
        return LidarStatusResponse(
            job_id=job_id,
            status="pending",
            progress=0,
            message="Oczekuje w kolejce..."
        )
    elif result.successful():
        data = result.get()
        return LidarStatusResponse(
            job_id=job_id,
            status="ready" if data.get("success") else "error",
            progress=100 if data.get("success") else 0,
            message=data.get("error", "Gotowe!"),
            potree_url=data.get("potree_url"),
        )
    elif result.failed():
        return LidarStatusResponse(
            job_id=job_id,
            status="error",
            progress=0,
            message=str(result.result) if result.result else "Nieznany błąd"
        )
    else:
        return LidarStatusResponse(
            job_id=job_id,
            status="processing",
            progress=50,
            message="Przetwarzanie..."
        )


@router.get("/check")
async def check_lidar_availability(
    lat: float = Query(..., ge=49, le=55, description="Latitude (WGS84)"),
    lon: float = Query(..., ge=14, le=24, description="Longitude (WGS84)"),
) -> LidarCheckResponse:
    """
    Check if LiDAR data is available for a location.

    Returns tile info and estimated processing time.
    """
    result = check_tile_availability.delay(lat, lon)
    data = result.get(timeout=10)

    # Estimate time based on cache status
    if data.get("cached"):
        estimated_time = 2  # Seconds
    elif data.get("laz_cached"):
        estimated_time = 15  # Just conversion
    else:
        estimated_time = 60  # Full download + conversion

    return LidarCheckResponse(
        tile_id=data["tile_id"],
        available=data["available"],
        cached=data["cached"],
        estimated_time_seconds=estimated_time,
    )


@router.get("/tile/{tile_id}/{path:path}")
async def serve_potree_file(tile_id: str, path: str):
    """
    Serve Potree files for a tile.

    Potree 2.0 files:
    - metadata.json - Tile metadata
    - hierarchy.bin - Octree structure
    - octree.bin - Point data

    Args:
        tile_id: Tile identifier
        path: File path within tile directory (e.g., "metadata.json")
    """
    # Validate tile_id (prevent path traversal)
    if ".." in tile_id or "/" in tile_id:
        raise HTTPException(status_code=400, detail="Invalid tile_id")

    file_path = POTREE_PATH / tile_id / path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine content type
    content_types = {
        ".json": "application/json",
        ".bin": "application/octet-stream",
        ".js": "application/javascript",
    }
    suffix = file_path.suffix.lower()
    content_type = content_types.get(suffix, "application/octet-stream")

    # Update LRU access time
    try:
        redis_client = get_redis()
        import time
        redis_client.zadd("lidar:cache:lru", {tile_id: time.time()})
    except Exception:
        pass  # Non-critical

    return FileResponse(
        path=file_path,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 1 day
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/tile/{tile_id}")
async def get_tile_metadata(tile_id: str):
    """Get metadata for a Potree tile."""
    if ".." in tile_id or "/" in tile_id:
        raise HTTPException(status_code=400, detail="Invalid tile_id")

    metadata_path = POTREE_PATH / tile_id / "metadata.json"

    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Tile not found")

    with open(metadata_path) as f:
        metadata = json.load(f)

    return JSONResponse(content=metadata)
