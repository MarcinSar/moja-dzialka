"""
3D Terrain Service - LiDAR-based terrain visualization.

Provides 3D terrain data for parcels using LiDAR data from GUGiK.
This is a PREMIUM feature.

Data sources:
- GUGiK NMT (Numeryczny Model Terenu) - terrain elevation
- GUGiK NMPT (Numeryczny Model Pokrycia Terenu) - surface elevation (with buildings/trees)
- Orthophotos for texture

Note: This is a skeleton implementation. Full implementation requires:
1. GUGiK API integration or downloaded LiDAR data
2. Point cloud processing (e.g., PDAL, CloudCompare)
3. 3D mesh generation (e.g., Cesium terrain tiles)
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

from loguru import logger


class TerrainQuality(str, Enum):
    """Quality level for terrain data."""
    LOW = "low"         # 10m resolution, fast
    MEDIUM = "medium"   # 1m resolution
    HIGH = "high"       # 0.5m resolution, slow


@dataclass
class TerrainPoint:
    """Single point in terrain model."""
    x: float  # EPSG:2180
    y: float  # EPSG:2180
    z: float  # Elevation in meters
    classification: Optional[str] = None  # ground, vegetation, building


@dataclass
class TerrainBounds:
    """Bounding box for terrain data."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    min_z: float
    max_z: float


@dataclass
class TerrainStats:
    """Statistics about terrain."""
    min_elevation: float
    max_elevation: float
    avg_elevation: float
    slope_avg_deg: float
    slope_max_deg: float
    aspect: str  # N, S, E, W, NE, NW, SE, SW, flat


class Terrain3DService:
    """Service for 3D terrain visualization.

    PREMIUM FEATURE: Requires paid tier.
    """

    # GUGiK data endpoints (would need API key in production)
    GUGIK_NMT_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WCS/DigitalTerrainModelFormatTIFF"

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize service.

        Args:
            cache_dir: Directory for caching terrain data
        """
        self.cache_dir = cache_dir

    async def get_terrain_for_parcel(
        self,
        parcel_id: str,
        quality: TerrainQuality = TerrainQuality.MEDIUM,
        buffer_m: int = 50,
    ) -> Dict[str, Any]:
        """Get 3D terrain data for a parcel.

        Args:
            parcel_id: ID of the parcel
            quality: Desired quality level
            buffer_m: Buffer around parcel in meters

        Returns:
            Terrain data including mesh, stats, and visualization URLs
        """
        logger.info(f"Getting terrain for parcel {parcel_id} (quality: {quality.value})")

        # Get parcel geometry
        geometry = await self._get_parcel_geometry(parcel_id)
        if not geometry:
            return {"error": f"Parcel {parcel_id} not found"}

        # Get bounding box with buffer
        bounds = self._calculate_bounds(geometry, buffer_m)

        # Get terrain data (would fetch from GUGiK in production)
        terrain_data = await self._fetch_terrain_data(bounds, quality)

        # Calculate statistics
        stats = self._calculate_stats(terrain_data)

        # Generate visualization data
        visualization = self._generate_visualization(terrain_data, geometry)

        return {
            "parcel_id": parcel_id,
            "quality": quality.value,
            "bounds": {
                "min_x": bounds.min_x,
                "min_y": bounds.min_y,
                "max_x": bounds.max_x,
                "max_y": bounds.max_y,
            },
            "stats": {
                "min_elevation_m": stats.min_elevation,
                "max_elevation_m": stats.max_elevation,
                "avg_elevation_m": stats.avg_elevation,
                "elevation_range_m": stats.max_elevation - stats.min_elevation,
                "slope_avg_deg": stats.slope_avg_deg,
                "slope_max_deg": stats.slope_max_deg,
                "aspect": stats.aspect,
            },
            "terrain_assessment": self._assess_terrain(stats),
            "visualization": visualization,
            "note": "3D terrain visualization is a premium feature",
        }

    async def _get_parcel_geometry(self, parcel_id: str) -> Optional[Dict[str, Any]]:
        """Get parcel geometry from database."""
        try:
            from app.services.database import neo4j

            results = await neo4j.run("""
                MATCH (p:Parcel {id_dzialki: $parcel_id})
                RETURN p.centroid_x as cx, p.centroid_y as cy,
                       p.bbox_height as h, p.bbox_width as w
            """, {"parcel_id": parcel_id})
            if results:
                record = results[0]
                return {
                    "centroid_x": record["cx"],
                    "centroid_y": record["cy"],
                    "height": record["h"] or 100,
                    "width": record["w"] or 100,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting parcel geometry: {e}")
            # Return mock data for development
            return {
                "centroid_x": 6545000,
                "centroid_y": 6068000,
                "height": 50,
                "width": 40,
            }

    def _calculate_bounds(
        self,
        geometry: Dict[str, Any],
        buffer_m: int,
    ) -> TerrainBounds:
        """Calculate bounding box with buffer."""
        cx = geometry["centroid_x"]
        cy = geometry["centroid_y"]
        half_h = geometry["height"] / 2 + buffer_m
        half_w = geometry["width"] / 2 + buffer_m

        return TerrainBounds(
            min_x=cx - half_w,
            min_y=cy - half_h,
            max_x=cx + half_w,
            max_y=cy + half_h,
            min_z=0,  # Will be updated with real data
            max_z=0,
        )

    async def _fetch_terrain_data(
        self,
        bounds: TerrainBounds,
        quality: TerrainQuality,
    ) -> List[TerrainPoint]:
        """Fetch terrain data from GUGiK.

        This is a MOCK implementation. Real implementation would:
        1. Call GUGiK WCS service for NMT/NMPT data
        2. Parse TIFF response
        3. Extract elevation grid
        """
        logger.info(f"Fetching terrain data (mock) for bounds {bounds}")

        # Generate mock terrain data
        resolution = {
            TerrainQuality.LOW: 10.0,
            TerrainQuality.MEDIUM: 1.0,
            TerrainQuality.HIGH: 0.5,
        }[quality]

        points = []
        x = bounds.min_x
        while x <= bounds.max_x:
            y = bounds.min_y
            while y <= bounds.max_y:
                # Mock elevation (sinusoidal for demonstration)
                z = 10 + 5 * math.sin(x / 100) + 3 * math.cos(y / 100)
                points.append(TerrainPoint(x=x, y=y, z=z))
                y += resolution
            x += resolution

        return points

    def _calculate_stats(self, terrain_data: List[TerrainPoint]) -> TerrainStats:
        """Calculate terrain statistics."""
        if not terrain_data:
            return TerrainStats(
                min_elevation=0,
                max_elevation=0,
                avg_elevation=0,
                slope_avg_deg=0,
                slope_max_deg=0,
                aspect="flat",
            )

        elevations = [p.z for p in terrain_data]
        min_elev = min(elevations)
        max_elev = max(elevations)
        avg_elev = sum(elevations) / len(elevations)

        # Calculate slope (simplified - would use proper slope calculation)
        slopes = []
        for i in range(1, len(terrain_data)):
            dx = terrain_data[i].x - terrain_data[i-1].x
            dy = terrain_data[i].y - terrain_data[i-1].y
            dz = terrain_data[i].z - terrain_data[i-1].z
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                slope = math.degrees(math.atan(dz / dist))
                slopes.append(abs(slope))

        avg_slope = sum(slopes) / len(slopes) if slopes else 0
        max_slope = max(slopes) if slopes else 0

        # Determine aspect (simplified)
        aspect = "flat"
        if len(terrain_data) > 1:
            dz = terrain_data[-1].z - terrain_data[0].z
            if abs(dz) > 0.5:
                aspect = "N" if dz > 0 else "S"

        return TerrainStats(
            min_elevation=min_elev,
            max_elevation=max_elev,
            avg_elevation=avg_elev,
            slope_avg_deg=avg_slope,
            slope_max_deg=max_slope,
            aspect=aspect,
        )

    def _assess_terrain(self, stats: TerrainStats) -> Dict[str, Any]:
        """Assess terrain for building suitability."""
        assessment = {
            "flat_enough_for_building": stats.slope_avg_deg < 15,
            "drainage_concern": stats.slope_avg_deg < 2,
            "view_potential": stats.slope_avg_deg > 5,
            "earthwork_estimated": "minimal" if stats.slope_avg_deg < 5 else "moderate" if stats.slope_avg_deg < 15 else "significant",
        }

        # Generate recommendation
        if stats.slope_avg_deg < 5:
            assessment["recommendation"] = "Teren płaski, łatwy do zabudowy. Uwaga na odprowadzanie wody."
        elif stats.slope_avg_deg < 15:
            assessment["recommendation"] = "Teren lekko nachylony, dobre warunki pod budowę z potencjałem widokowym."
        else:
            assessment["recommendation"] = "Teren stromy, wymaga znacznych prac ziemnych. Możliwy atrakcyjny widok."

        return assessment

    def _generate_visualization(
        self,
        terrain_data: List[TerrainPoint],
        geometry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate visualization URLs and data.

        In production, this would:
        1. Generate 3D mesh from point cloud
        2. Create Cesium terrain tiles
        3. Upload to CDN
        4. Return viewer URLs
        """
        return {
            "viewer_url": None,  # Would be Cesium/Potree viewer URL
            "thumbnail_url": None,  # 2D preview
            "download_url": None,  # .obj/.glb file
            "format": "mock",
            "point_count": len(terrain_data),
            "note": "Full 3D visualization requires production setup with GUGiK integration",
        }

    async def get_cross_section(
        self,
        parcel_id: str,
        start_point: Tuple[float, float],
        end_point: Tuple[float, float],
    ) -> Dict[str, Any]:
        """Get terrain cross-section between two points.

        Args:
            parcel_id: ID of the parcel (for context)
            start_point: (x, y) start coordinates
            end_point: (x, y) end coordinates

        Returns:
            Cross-section profile data
        """
        logger.info(f"Getting cross-section for parcel {parcel_id}")

        # Calculate line
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        length = math.sqrt(dx**2 + dy**2)
        num_points = int(length)

        # Generate profile (mock)
        profile = []
        for i in range(num_points):
            t = i / num_points
            x = start_point[0] + t * dx
            y = start_point[1] + t * dy
            z = 10 + 5 * math.sin(x / 100) + 3 * math.cos(y / 100)  # Mock
            distance = i
            profile.append({
                "distance_m": distance,
                "elevation_m": z,
                "x": x,
                "y": y,
            })

        return {
            "parcel_id": parcel_id,
            "start": start_point,
            "end": end_point,
            "length_m": length,
            "profile": profile,
            "min_elevation_m": min(p["elevation_m"] for p in profile) if profile else 0,
            "max_elevation_m": max(p["elevation_m"] for p in profile) if profile else 0,
        }


# Singleton
_terrain_service: Optional[Terrain3DService] = None


def get_terrain_3d_service() -> Terrain3DService:
    """Get the global terrain 3D service instance."""
    global _terrain_service
    if _terrain_service is None:
        _terrain_service = Terrain3DService()
    return _terrain_service
