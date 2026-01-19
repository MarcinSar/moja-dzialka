"""
GUGiK LiDAR data downloader service.

Downloads LAZ files from Polish GUGiK geoportal (ISOK project).
LiDAR data covers entire Poland with density 4-20 pts/m².

Data source: https://mapy.geoportal.gov.pl
Format: LAZ (compressed LAS)
Tile size: ~1x1 km
"""

import asyncio
import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx
from loguru import logger

# GUGiK WCS (Web Coverage Service) endpoint for LiDAR data
GUGIK_WCS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NumerycznyModelTerenuEVRF2007/WCS/DigitalTerrainModelFormatLAZ"

# Alternative: direct download from ISOK
ISOK_BASE_URL = "https://opendata.geoportal.gov.pl/NumDan662"

# EPSG:2180 (PUWG 1992) bounds for Poland
POLAND_BOUNDS = {
    "min_x": 140000,
    "max_x": 900000,
    "min_y": 120000,
    "max_y": 900000,
}

# LiDAR tile grid parameters (ISOK project)
# Tiles are 1km x 1km in EPSG:2180
TILE_SIZE_M = 1000


@dataclass
class LidarTile:
    """Represents a GUGiK LiDAR tile."""
    tile_id: str          # e.g., "N-34-63-D-c-2-3"
    grid_x: int           # X index in grid
    grid_y: int           # Y index in grid
    bbox_2180: tuple      # (min_x, min_y, max_x, max_y) in EPSG:2180
    center_wgs84: tuple   # (lat, lon) in WGS84
    download_url: str     # Direct download URL


def get_tile_for_point(lat: float, lon: float) -> LidarTile:
    """
    Get LiDAR tile ID for a given WGS84 point.

    Args:
        lat: Latitude in WGS84 (e.g., 54.35)
        lon: Longitude in WGS84 (e.g., 18.62)

    Returns:
        LidarTile with tile information
    """
    # Convert WGS84 to EPSG:2180 (PUWG 1992)
    x_2180, y_2180 = wgs84_to_2180(lat, lon)

    # Calculate grid indices
    grid_x = int((x_2180 - POLAND_BOUNDS["min_x"]) // TILE_SIZE_M)
    grid_y = int((y_2180 - POLAND_BOUNDS["min_y"]) // TILE_SIZE_M)

    # Calculate tile bounds in EPSG:2180
    min_x = POLAND_BOUNDS["min_x"] + grid_x * TILE_SIZE_M
    min_y = POLAND_BOUNDS["min_y"] + grid_y * TILE_SIZE_M
    max_x = min_x + TILE_SIZE_M
    max_y = min_y + TILE_SIZE_M

    # Generate tile ID (simplified - actual GUGiK uses complex naming)
    # Format: row_col based on grid position
    tile_id = f"tile_{grid_x:04d}_{grid_y:04d}"

    # Generate download URL (using WCS GetCoverage)
    download_url = _generate_wcs_url(min_x, min_y, max_x, max_y)

    return LidarTile(
        tile_id=tile_id,
        grid_x=grid_x,
        grid_y=grid_y,
        bbox_2180=(min_x, min_y, max_x, max_y),
        center_wgs84=(lat, lon),
        download_url=download_url,
    )


def get_tile_for_bbox(
    min_lat: float, min_lon: float,
    max_lat: float, max_lon: float
) -> list[LidarTile]:
    """
    Get all LiDAR tiles covering a bounding box.

    Args:
        min_lat, min_lon: SW corner in WGS84
        max_lat, max_lon: NE corner in WGS84

    Returns:
        List of LidarTile objects covering the bbox
    """
    # Convert corners to EPSG:2180
    min_x, min_y = wgs84_to_2180(min_lat, min_lon)
    max_x, max_y = wgs84_to_2180(max_lat, max_lon)

    # Calculate grid range
    start_grid_x = int((min_x - POLAND_BOUNDS["min_x"]) // TILE_SIZE_M)
    end_grid_x = int((max_x - POLAND_BOUNDS["min_x"]) // TILE_SIZE_M)
    start_grid_y = int((min_y - POLAND_BOUNDS["min_y"]) // TILE_SIZE_M)
    end_grid_y = int((max_y - POLAND_BOUNDS["min_y"]) // TILE_SIZE_M)

    tiles = []
    for gx in range(start_grid_x, end_grid_x + 1):
        for gy in range(start_grid_y, end_grid_y + 1):
            tile_min_x = POLAND_BOUNDS["min_x"] + gx * TILE_SIZE_M
            tile_min_y = POLAND_BOUNDS["min_y"] + gy * TILE_SIZE_M
            tile_max_x = tile_min_x + TILE_SIZE_M
            tile_max_y = tile_min_y + TILE_SIZE_M

            # Center in WGS84
            center_x = (tile_min_x + tile_max_x) / 2
            center_y = (tile_min_y + tile_max_y) / 2
            center_lat, center_lon = epsg2180_to_wgs84(center_x, center_y)

            tile_id = f"tile_{gx:04d}_{gy:04d}"
            download_url = _generate_wcs_url(tile_min_x, tile_min_y, tile_max_x, tile_max_y)

            tiles.append(LidarTile(
                tile_id=tile_id,
                grid_x=gx,
                grid_y=gy,
                bbox_2180=(tile_min_x, tile_min_y, tile_max_x, tile_max_y),
                center_wgs84=(center_lat, center_lon),
                download_url=download_url,
            ))

    return tiles


def _generate_wcs_url(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    """Generate WCS GetCoverage URL for a tile."""
    # WCS 2.0.1 GetCoverage request
    params = {
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": "DTM_EVRF2007",
        "FORMAT": "application/x-laz",
        "SUBSET": f"x({min_x},{max_x})",
        "SUBSETY": f"y({min_y},{max_y})",
        "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/2180",
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GUGIK_WCS_URL}?{query}"


def wgs84_to_2180(lat: float, lon: float) -> tuple[float, float]:
    """
    Convert WGS84 coordinates to EPSG:2180 (PUWG 1992).

    This is a simplified approximation for Poland region.
    For production, use pyproj for accurate transformation.
    """
    # Simplified transformation (approximate for Pomerania region)
    # These coefficients work well for lat ~54, lon ~18
    x = (lon - 19.0) * 111320 * math.cos(math.radians(lat)) + 500000
    y = (lat - 52.0) * 111320 + 312000

    # More accurate: use pyproj
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
        x, y = transformer.transform(lon, lat)
    except ImportError:
        pass

    return x, y


def epsg2180_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """
    Convert EPSG:2180 coordinates to WGS84.
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(x, y)
        return lat, lon
    except ImportError:
        # Simplified inverse (approximate)
        lat = (y - 312000) / 111320 + 52.0
        lon = (x - 500000) / (111320 * math.cos(math.radians(lat))) + 19.0
        return lat, lon


async def download_laz(
    tile: LidarTile,
    output_path: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    timeout: float = 300.0,
) -> Path:
    """
    Download LAZ file for a tile.

    Args:
        tile: LidarTile to download
        output_path: Directory to save the file
        progress_callback: Optional callback(progress: 0-100, message: str)
        timeout: Download timeout in seconds

    Returns:
        Path to downloaded LAZ file

    Raises:
        httpx.HTTPError: On download failure
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    laz_file = output_path / f"{tile.tile_id}.laz"

    # Check if already downloaded
    if laz_file.exists() and laz_file.stat().st_size > 0:
        logger.info(f"LAZ file already exists: {laz_file}")
        if progress_callback:
            progress_callback(100.0, "Plik LAZ już istnieje w cache")
        return laz_file

    logger.info(f"Downloading LAZ for tile {tile.tile_id}")
    if progress_callback:
        progress_callback(0.0, "Rozpoczynam pobieranie danych LiDAR...")

    async with httpx.AsyncClient(timeout=timeout) as client:
        # First, try direct WCS download
        try:
            response = await _download_with_progress(
                client, tile.download_url, laz_file, progress_callback
            )
            return laz_file
        except httpx.HTTPError as e:
            logger.warning(f"WCS download failed: {e}, trying alternative...")

        # Fallback: try ISOK direct download
        # ISOK uses different URL pattern
        isok_url = _get_isok_url(tile)
        if isok_url:
            try:
                response = await _download_with_progress(
                    client, isok_url, laz_file, progress_callback
                )
                return laz_file
            except httpx.HTTPError as e:
                logger.error(f"ISOK download also failed: {e}")
                raise

        raise httpx.HTTPError(f"Failed to download tile {tile.tile_id}")


async def _download_with_progress(
    client: httpx.AsyncClient,
    url: str,
    output_file: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> None:
    """Download file with progress tracking."""
    async with client.stream("GET", url) as response:
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(output_file, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)

                if progress_callback and total_size > 0:
                    progress = (downloaded / total_size) * 70  # 0-70% for download
                    size_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    progress_callback(
                        progress,
                        f"Pobieranie: {size_mb:.1f} / {total_mb:.1f} MB"
                    )

        logger.info(f"Downloaded {downloaded / (1024*1024):.1f} MB to {output_file}")


def _get_isok_url(tile: LidarTile) -> Optional[str]:
    """
    Get alternative ISOK download URL for a tile.

    ISOK (Informatyczny System Osłony Kraju) data is available at:
    https://opendata.geoportal.gov.pl/

    Returns None if tile naming conversion fails.
    """
    # ISOK uses different tile naming convention
    # This is a simplified mapping - real implementation needs
    # proper grid conversion to ISOK naming scheme
    return None  # TODO: Implement ISOK URL generation


def get_cache_key(tile: LidarTile) -> str:
    """Generate cache key for a tile."""
    return f"lidar:tile:{tile.tile_id}"


def hash_bbox(bbox: tuple) -> str:
    """Generate hash for bbox (for cache keys)."""
    bbox_str = "_".join(str(int(x)) for x in bbox)
    return hashlib.md5(bbox_str.encode()).hexdigest()[:12]
