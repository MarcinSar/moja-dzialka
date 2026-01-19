"""
LiDAR cache management service.

Handles:
- Cache lookup for LAZ and Potree files
- LRU tracking via Redis
- Cache statistics
- Cleanup of old tiles
"""

import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis
from loguru import logger

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
    """Get Redis client."""
    return redis.from_url(REDIS_URL)


@dataclass
class CacheEntry:
    """Represents a cached LiDAR tile."""
    tile_id: str
    laz_path: Optional[Path]
    potree_path: Optional[Path]
    laz_size: int
    potree_size: int
    created_at: datetime
    last_accessed: datetime

    @property
    def total_size(self) -> int:
        return self.laz_size + self.potree_size

    @property
    def has_laz(self) -> bool:
        return self.laz_path is not None and self.laz_path.exists()

    @property
    def has_potree(self) -> bool:
        return self.potree_path is not None and self.potree_path.exists()


def check_cache(tile_id: str) -> CacheEntry:
    """
    Check cache status for a tile.

    Args:
        tile_id: Tile identifier

    Returns:
        CacheEntry with current status
    """
    laz_path = LAZ_CACHE_PATH / f"{tile_id}.laz"
    potree_path = POTREE_PATH / tile_id
    potree_metadata = potree_path / "metadata.json"

    # Get sizes
    laz_size = laz_path.stat().st_size if laz_path.exists() else 0
    potree_size = sum(
        f.stat().st_size for f in potree_path.rglob("*") if f.is_file()
    ) if potree_path.exists() else 0

    # Get Redis metadata
    client = get_redis_client()
    metadata = client.hgetall(f"lidar:cache:{tile_id}")

    created_at = datetime.fromisoformat(
        metadata.get(b"created_at", b"").decode() or datetime.utcnow().isoformat()
    )
    last_accessed = datetime.fromisoformat(
        metadata.get(b"last_accessed", b"").decode() or datetime.utcnow().isoformat()
    )

    return CacheEntry(
        tile_id=tile_id,
        laz_path=laz_path if laz_path.exists() else None,
        potree_path=potree_path if potree_metadata.exists() else None,
        laz_size=laz_size,
        potree_size=potree_size,
        created_at=created_at,
        last_accessed=last_accessed,
    )


def update_access_time(tile_id: str) -> None:
    """Update last access time for LRU tracking."""
    client = get_redis_client()
    now = time.time()
    client.zadd("lidar:cache:lru", {tile_id: now})
    client.hset(f"lidar:cache:{tile_id}", "last_accessed", datetime.utcnow().isoformat())


def get_cache_stats() -> dict:
    """Get overall cache statistics."""
    client = get_redis_client()

    # Count tiles
    tile_count = 0
    total_laz_size = 0
    total_potree_size = 0

    for key in client.scan_iter("lidar:cache:*"):
        key_str = key.decode()
        if key_str == "lidar:cache:lru":
            continue

        tile_id = key_str.split(":")[-1]
        metadata = client.hgetall(key)

        tile_count += 1
        total_laz_size += int(metadata.get(b"laz_size", 0))
        total_potree_size += int(metadata.get(b"potree_size", 0))

    # Check actual disk usage
    laz_disk_usage = sum(
        f.stat().st_size for f in LAZ_CACHE_PATH.glob("*.laz")
    ) if LAZ_CACHE_PATH.exists() else 0

    potree_disk_usage = sum(
        f.stat().st_size
        for d in POTREE_PATH.iterdir() if d.is_dir()
        for f in d.rglob("*") if f.is_file()
    ) if POTREE_PATH.exists() else 0

    return {
        "tile_count": tile_count,
        "total_size_bytes": total_laz_size + total_potree_size,
        "total_size_gb": (total_laz_size + total_potree_size) / (1024 ** 3),
        "laz_size_bytes": total_laz_size,
        "potree_size_bytes": total_potree_size,
        "disk_laz_bytes": laz_disk_usage,
        "disk_potree_bytes": potree_disk_usage,
        "max_size_gb": MAX_CACHE_SIZE_GB,
        "usage_percent": ((total_laz_size + total_potree_size) / (MAX_CACHE_SIZE_GB * 1024 ** 3)) * 100,
    }


def get_oldest_tiles(limit: int = 10) -> list[tuple[str, float]]:
    """Get oldest tiles by last access time (for cleanup)."""
    client = get_redis_client()
    return client.zrange("lidar:cache:lru", 0, limit - 1, withscores=True)


def remove_tile(tile_id: str) -> dict:
    """
    Remove a tile from cache.

    Args:
        tile_id: Tile identifier

    Returns:
        Dictionary with removal stats
    """
    client = get_redis_client()

    laz_path = LAZ_CACHE_PATH / f"{tile_id}.laz"
    potree_path = POTREE_PATH / tile_id

    stats = {
        "tile_id": tile_id,
        "laz_removed": False,
        "potree_removed": False,
        "bytes_freed": 0,
    }

    if laz_path.exists():
        stats["bytes_freed"] += laz_path.stat().st_size
        laz_path.unlink()
        stats["laz_removed"] = True
        logger.info(f"Removed LAZ cache: {laz_path}")

    if potree_path.exists():
        for f in potree_path.rglob("*"):
            if f.is_file():
                stats["bytes_freed"] += f.stat().st_size
        shutil.rmtree(potree_path)
        stats["potree_removed"] = True
        logger.info(f"Removed Potree cache: {potree_path}")

    # Remove Redis metadata
    client.delete(f"lidar:cache:{tile_id}")
    client.zrem("lidar:cache:lru", tile_id)

    return stats


def cleanup_expired_tiles() -> dict:
    """
    Remove tiles older than their TTL.

    Returns:
        Cleanup statistics
    """
    client = get_redis_client()
    stats = {"removed_tiles": 0, "bytes_freed": 0, "errors": []}

    now = datetime.utcnow()
    laz_max_age_seconds = LAZ_CACHE_TTL_DAYS * 24 * 60 * 60
    potree_max_age_seconds = POTREE_CACHE_TTL_DAYS * 24 * 60 * 60

    for key in client.scan_iter("lidar:cache:*"):
        key_str = key.decode()
        if key_str == "lidar:cache:lru":
            continue

        tile_id = key_str.split(":")[-1]

        try:
            metadata = client.hgetall(key)
            created_at_str = metadata.get(b"created_at", b"").decode()

            if not created_at_str:
                continue

            created_at = datetime.fromisoformat(created_at_str)
            age_seconds = (now - created_at).total_seconds()

            # Check if expired
            should_remove = age_seconds > potree_max_age_seconds

            if should_remove:
                result = remove_tile(tile_id)
                stats["removed_tiles"] += 1
                stats["bytes_freed"] += result["bytes_freed"]

        except Exception as e:
            stats["errors"].append(f"{tile_id}: {str(e)}")
            logger.error(f"Error checking tile {tile_id}: {e}")

    return stats


def cleanup_to_size_limit() -> dict:
    """
    Remove oldest tiles until cache is under size limit.

    Returns:
        Cleanup statistics
    """
    stats = get_cache_stats()

    if stats["total_size_gb"] <= MAX_CACHE_SIZE_GB:
        return {"removed_tiles": 0, "bytes_freed": 0, "message": "Cache within limits"}

    result = {"removed_tiles": 0, "bytes_freed": 0}
    target_size = MAX_CACHE_SIZE_GB * 0.8 * (1024 ** 3)  # Clean to 80%
    current_size = stats["total_size_bytes"]

    # Get tiles sorted by last access (oldest first)
    oldest_tiles = get_oldest_tiles(limit=100)

    for tile_id_bytes, _ in oldest_tiles:
        if current_size <= target_size:
            break

        tile_id = tile_id_bytes.decode() if isinstance(tile_id_bytes, bytes) else tile_id_bytes

        try:
            removal_result = remove_tile(tile_id)
            current_size -= removal_result["bytes_freed"]
            result["removed_tiles"] += 1
            result["bytes_freed"] += removal_result["bytes_freed"]
        except Exception as e:
            logger.error(f"Failed to remove tile {tile_id}: {e}")

    result["final_size_gb"] = current_size / (1024 ** 3)
    return result


def ensure_cache_directories() -> None:
    """Ensure cache directories exist."""
    LAZ_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    POTREE_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cache directories ensured: {LAZ_CACHE_PATH}, {POTREE_PATH}")
