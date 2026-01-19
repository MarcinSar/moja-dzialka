"""
Celery tasks for LiDAR data processing.

Main workflow:
1. Receive parcel_id and coordinates
2. Get corresponding LiDAR tile from GUGiK
3. Download LAZ file (if not cached)
4. Convert to Potree format (if not cached)
5. Publish progress events via Redis pub/sub
6. Return URL to Potree data
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis
from celery import shared_task
from loguru import logger

from app.services.gugik_lidar import (
    LidarTile,
    download_laz,
    get_tile_for_point,
)
from app.tasks.potree_converter import (
    PotreeConversionError,
    convert_laz_to_potree,
    get_potree_info,
)

# Paths for LiDAR data storage
LIDAR_BASE_PATH = Path(os.getenv("LIDAR_DATA_PATH", "/data/lidar"))
LAZ_CACHE_PATH = LIDAR_BASE_PATH / "laz_cache"
POTREE_PATH = LIDAR_BASE_PATH / "potree"

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Cache settings
LAZ_CACHE_TTL_DAYS = 7
POTREE_CACHE_TTL_DAYS = 30
MAX_CACHE_SIZE_GB = 150


def get_redis_client() -> redis.Redis:
    """Get Redis client for pub/sub."""
    return redis.from_url(REDIS_URL)


def publish_progress(
    session_id: str,
    job_id: str,
    progress: float,
    status: str,
    message: str,
    potree_url: Optional[str] = None,
) -> None:
    """
    Publish progress event to Redis pub/sub.

    Frontend subscribes to channel: lidar:progress:{session_id}
    """
    client = get_redis_client()

    event = {
        "type": "lidar_progress" if status == "processing" else f"lidar_{status}",
        "job_id": job_id,
        "progress": progress,
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if potree_url:
        event["potree_url"] = potree_url

    channel = f"lidar:progress:{session_id}"
    client.publish(channel, json.dumps(event))

    # Also store in Redis for polling fallback
    client.setex(
        f"lidar:job:{job_id}:status",
        3600,  # 1 hour TTL
        json.dumps(event),
    )

    logger.debug(f"Published progress to {channel}: {progress:.1f}% - {message}")


@shared_task(
    bind=True,
    name="app.tasks.lidar_tasks.process_lidar_for_parcel",
    max_retries=3,
    default_retry_delay=30,
)
def process_lidar_for_parcel(
    self,
    parcel_id: str,
    lat: float,
    lon: float,
    session_id: str,
    parcel_bbox: Optional[tuple] = None,
) -> dict:
    """
    Main task: Process LiDAR data for a parcel.

    Args:
        parcel_id: Unique parcel identifier
        lat: Centroid latitude (WGS84)
        lon: Centroid longitude (WGS84)
        session_id: WebSocket session ID for progress updates
        parcel_bbox: Optional (min_x, min_y, max_x, max_y) in EPSG:2180

    Returns:
        Dictionary with potree_url and metadata
    """
    job_id = self.request.id
    logger.info(f"Starting LiDAR processing for parcel {parcel_id}, job {job_id}")

    # Progress callback wrapper
    def on_progress(progress: float, message: str):
        publish_progress(session_id, job_id, progress, "processing", message)

    try:
        # Step 1: Get tile for coordinates
        on_progress(5.0, "Identyfikuję tile LiDAR...")
        tile = get_tile_for_point(lat, lon)
        logger.info(f"Tile for ({lat}, {lon}): {tile.tile_id}")

        # Step 2: Check if Potree already exists
        potree_output = POTREE_PATH / tile.tile_id
        if potree_output.exists() and (potree_output / "metadata.json").exists():
            logger.info(f"Potree cache hit for tile {tile.tile_id}")
            on_progress(100.0, "Dane Potree już w cache!")
            potree_url = f"/api/v1/lidar/tile/{tile.tile_id}/"
            publish_progress(
                session_id, job_id, 100.0, "ready",
                "Gotowe!", potree_url
            )
            return {
                "success": True,
                "potree_url": potree_url,
                "tile_id": tile.tile_id,
                "cached": True,
            }

        # Step 3: Download LAZ file
        on_progress(10.0, "Pobieram dane LiDAR z GUGiK...")
        LAZ_CACHE_PATH.mkdir(parents=True, exist_ok=True)

        # Run async download in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            laz_path = loop.run_until_complete(
                download_laz(tile, LAZ_CACHE_PATH, on_progress)
            )
        finally:
            loop.close()

        # Step 4: Convert to Potree
        on_progress(70.0, "Konwertuję do formatu 3D...")
        POTREE_PATH.mkdir(parents=True, exist_ok=True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            potree_path = loop.run_until_complete(
                convert_laz_to_potree(
                    laz_path, potree_output, on_progress, parcel_bbox
                )
            )
        finally:
            loop.close()

        # Step 5: Update cache metadata
        _update_cache_metadata(tile.tile_id, laz_path, potree_path)

        # Step 6: Return success
        potree_url = f"/api/v1/lidar/tile/{tile.tile_id}/"
        potree_info = get_potree_info(potree_path)

        on_progress(100.0, "Gotowe!")
        publish_progress(
            session_id, job_id, 100.0, "ready",
            "Dane 3D gotowe do wyświetlenia!", potree_url
        )

        return {
            "success": True,
            "potree_url": potree_url,
            "tile_id": tile.tile_id,
            "points": potree_info.get("points", 0),
            "cached": False,
        }

    except Exception as e:
        logger.error(f"LiDAR processing failed for {parcel_id}: {e}")
        publish_progress(
            session_id, job_id, 0, "error",
            f"Błąd przetwarzania: {str(e)}"
        )

        # Retry on transient errors
        if isinstance(e, (ConnectionError, TimeoutError)):
            raise self.retry(exc=e)

        return {
            "success": False,
            "error": str(e),
        }


def _update_cache_metadata(tile_id: str, laz_path: Path, potree_path: Path) -> None:
    """Update Redis cache metadata for LRU tracking."""
    client = get_redis_client()

    metadata = {
        "tile_id": tile_id,
        "laz_path": str(laz_path),
        "potree_path": str(potree_path),
        "laz_size": laz_path.stat().st_size if laz_path.exists() else 0,
        "potree_size": sum(
            f.stat().st_size for f in potree_path.rglob("*") if f.is_file()
        ) if potree_path.exists() else 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_accessed": datetime.utcnow().isoformat(),
    }

    client.hset(f"lidar:cache:{tile_id}", mapping=metadata)
    client.zadd("lidar:cache:lru", {tile_id: time.time()})


@shared_task(name="app.tasks.lidar_tasks.cleanup_lidar_cache")
def cleanup_lidar_cache() -> dict:
    """
    Periodic task: Clean up old LiDAR cache files.

    Runs every 6 hours via Celery beat.
    Removes oldest tiles when cache exceeds MAX_CACHE_SIZE_GB.
    """
    logger.info("Starting LiDAR cache cleanup...")

    client = get_redis_client()
    stats = {"removed_tiles": 0, "freed_bytes": 0}

    # Calculate current cache size
    total_size = 0
    tiles = []

    for key in client.scan_iter("lidar:cache:*"):
        if key == b"lidar:cache:lru":
            continue

        tile_id = key.decode().split(":")[-1]
        metadata = client.hgetall(key)

        if metadata:
            laz_size = int(metadata.get(b"laz_size", 0))
            potree_size = int(metadata.get(b"potree_size", 0))
            last_accessed = client.zscore("lidar:cache:lru", tile_id) or 0

            tiles.append({
                "tile_id": tile_id,
                "size": laz_size + potree_size,
                "last_accessed": last_accessed,
            })
            total_size += laz_size + potree_size

    logger.info(f"Current cache size: {total_size / (1024**3):.2f} GB")

    # Remove oldest tiles if over limit
    max_size = MAX_CACHE_SIZE_GB * (1024 ** 3)
    if total_size > max_size:
        # Sort by last accessed (oldest first)
        tiles.sort(key=lambda t: t["last_accessed"])

        for tile in tiles:
            if total_size <= max_size * 0.8:  # Reduce to 80% of max
                break

            _remove_tile_cache(tile["tile_id"], client)
            total_size -= tile["size"]
            stats["removed_tiles"] += 1
            stats["freed_bytes"] += tile["size"]

    logger.info(
        f"Cache cleanup complete: removed {stats['removed_tiles']} tiles, "
        f"freed {stats['freed_bytes'] / (1024**3):.2f} GB"
    )

    return stats


def _remove_tile_cache(tile_id: str, client: redis.Redis) -> None:
    """Remove a tile from cache (files and Redis metadata)."""
    import shutil

    laz_file = LAZ_CACHE_PATH / f"{tile_id}.laz"
    potree_dir = POTREE_PATH / tile_id

    if laz_file.exists():
        laz_file.unlink()

    if potree_dir.exists():
        shutil.rmtree(potree_dir)

    client.delete(f"lidar:cache:{tile_id}")
    client.zrem("lidar:cache:lru", tile_id)

    logger.debug(f"Removed tile {tile_id} from cache")


@shared_task(name="app.tasks.lidar_tasks.check_tile_availability")
def check_tile_availability(lat: float, lon: float) -> dict:
    """
    Quick check if LiDAR data is available for a location.

    Returns tile info without downloading.
    """
    tile = get_tile_for_point(lat, lon)

    # Check if already cached
    potree_exists = (POTREE_PATH / tile.tile_id / "metadata.json").exists()
    laz_exists = (LAZ_CACHE_PATH / f"{tile.tile_id}.laz").exists()

    return {
        "tile_id": tile.tile_id,
        "available": True,  # GUGiK covers all of Poland
        "cached": potree_exists,
        "laz_cached": laz_exists,
        "bbox": tile.bbox_2180,
    }
