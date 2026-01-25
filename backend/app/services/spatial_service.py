"""
Spatial search service using PostGIS.

Handles geometry-based queries like:
- Search parcels within radius
- Search parcels in bounding box
- Get parcel details with geometry
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from app.services.database import postgis


@dataclass
class SpatialSearchParams:
    """Parameters for spatial search."""
    lat: float  # WGS84 latitude
    lon: float  # WGS84 longitude
    radius_m: float = 5000  # Search radius in meters
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    gmina: Optional[str] = None
    has_mpzp: Optional[bool] = None
    mpzp_budowlane: Optional[bool] = None
    limit: int = 100


@dataclass
class BBoxSearchParams:
    """Parameters for bounding box search."""
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    limit: int = 100


class SpatialService:
    """Service for spatial queries on PostGIS."""

    # Target CRS: EPSG:2180 (Polish national CRS)
    TARGET_CRS = 2180
    # Source CRS for frontend: WGS84
    WGS84_CRS = 4326

    async def search_by_radius(
        self,
        params: SpatialSearchParams
    ) -> List[Dict[str, Any]]:
        """
        Search parcels within radius of a point.

        Args:
            params: Search parameters

        Returns:
            List of parcel dictionaries
        """
        # Build WHERE conditions
        conditions = ["ST_DWithin(p.geom, center_point.geom, :radius)"]
        query_params = {
            "lat": params.lat,
            "lon": params.lon,
            "radius": params.radius_m,
            "limit": params.limit,
        }

        if params.min_area:
            conditions.append("area_m2 >= :min_area")
            query_params["min_area"] = params.min_area

        if params.max_area:
            conditions.append("area_m2 <= :max_area")
            query_params["max_area"] = params.max_area

        if params.gmina:
            conditions.append("gmina = :gmina")
            query_params["gmina"] = params.gmina

        if params.has_mpzp is not None:
            conditions.append("has_pog = :has_mpzp")
            query_params["has_mpzp"] = params.has_mpzp

        if params.mpzp_budowlane is not None:
            conditions.append("is_residential_zone = :mpzp_budowlane")
            query_params["mpzp_budowlane"] = params.mpzp_budowlane

        where_clause = " AND ".join(conditions)

        query = f"""
            WITH center_point AS (
                SELECT ST_Transform(
                    ST_SetSRID(ST_MakePoint(:lon, :lat), {self.WGS84_CRS}),
                    {self.TARGET_CRS}
                ) as geom
            )
            SELECT
                p.id_dzialki,
                p.gmina,
                p.miejscowosc,
                p.area_m2,
                p.has_pog as has_mpzp,
                p.pog_symbol as mpzp_symbol,
                p.is_residential_zone as mpzp_czy_budowlane,
                p.quietness_score,
                p.nature_score,
                p.accessibility_score,
                p.centroid_lat,
                p.centroid_lon,
                ST_Distance(p.geom, center_point.geom) as distance_m,
                ST_AsGeoJSON(ST_Transform(p.geom, {self.WGS84_CRS})) as geojson
            FROM parcels p, center_point
            WHERE {where_clause}
            ORDER BY distance_m
            LIMIT :limit
        """

        try:
            results = await postgis.execute(query, query_params)
            return [dict(row._mapping) for row in results]
        except Exception as e:
            logger.error(f"Spatial search error: {e}")
            return []

    async def search_by_bbox(
        self,
        params: BBoxSearchParams
    ) -> List[Dict[str, Any]]:
        """
        Search parcels within bounding box.

        Args:
            params: Bounding box parameters

        Returns:
            List of parcel dictionaries
        """
        query = f"""
            WITH bbox AS (
                SELECT ST_Transform(
                    ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, {self.WGS84_CRS}),
                    {self.TARGET_CRS}
                ) as geom
            )
            SELECT
                p.id_dzialki,
                p.gmina,
                p.miejscowosc,
                p.area_m2,
                p.has_pog as has_mpzp,
                p.pog_symbol as mpzp_symbol,
                p.is_residential_zone as mpzp_czy_budowlane,
                p.quietness_score,
                p.nature_score,
                p.accessibility_score,
                p.centroid_lat,
                p.centroid_lon
            FROM parcels p, bbox
            WHERE ST_Intersects(p.geom, bbox.geom)
            LIMIT :limit
        """

        query_params = {
            "min_lat": params.min_lat,
            "min_lon": params.min_lon,
            "max_lat": params.max_lat,
            "max_lon": params.max_lon,
            "limit": params.limit,
        }

        try:
            results = await postgis.execute(query, query_params)
            return [dict(row._mapping) for row in results]
        except Exception as e:
            logger.error(f"BBox search error: {e}")
            return []

    async def get_parcel_details(
        self,
        parcel_id: str,
        include_geometry: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get full details for a single parcel.

        Args:
            parcel_id: Parcel ID (ID_DZIALKI)
            include_geometry: Whether to include GeoJSON geometry

        Returns:
            Parcel details dictionary or None
        """
        geom_select = f", ST_AsGeoJSON(ST_Transform(geom, {self.WGS84_CRS})) as geometry_wgs84" if include_geometry else ""

        query = f"""
            SELECT
                id_dzialki,
                gmina,
                powiat,
                dzielnica,
                miejscowosc,
                area_m2,
                centroid_lat,
                centroid_lon,
                dist_to_school,
                dist_to_supermarket as dist_to_shop,
                dist_to_doctors as dist_to_hospital,
                dist_to_bus_stop,
                dist_to_main_road,
                dist_to_forest,
                dist_to_water,
                dist_to_industrial,
                dist_to_pharmacy,
                pct_forest_500m,
                pct_water_500m,
                count_buildings_500m,
                -- POG fields (all)
                has_pog,
                pog_symbol,
                pog_nazwa,
                pog_oznaczenie,
                pog_profil_podstawowy,
                pog_profil_podstawowy_nazwy,
                pog_profil_dodatkowy,
                pog_profil_dodatkowy_nazwy,
                pog_maks_intensywnosc,
                pog_maks_wysokosc_m,
                pog_maks_zabudowa_pct,
                pog_min_bio_pct,
                is_residential_zone,
                -- Scores
                quietness_score,
                nature_score,
                accessibility_score,
                (dist_to_main_road < 50) as has_public_road_access,
                -- Building info
                is_built,
                building_count,
                building_coverage_pct,
                -- Categories
                kategoria_ciszy,
                kategoria_natury,
                kategoria_dostepu,
                gestosc_zabudowy
                {geom_select}
            FROM parcels
            WHERE id_dzialki = :parcel_id
        """

        try:
            results = await postgis.execute(query, {"parcel_id": parcel_id})
            if results:
                row = dict(results[0]._mapping)
                # Parse geometry_wgs84 from JSON string if present
                if row.get("geometry_wgs84") and isinstance(row["geometry_wgs84"], str):
                    import json
                    row["geometry_wgs84"] = json.loads(row["geometry_wgs84"])
                return row
            return None
        except Exception as e:
            logger.error(f"Get parcel details error: {e}")
            return None

    async def get_parcels_by_ids(
        self,
        parcel_ids: List[str],
        include_geometry: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get details for multiple parcels by ID.

        Args:
            parcel_ids: List of parcel IDs
            include_geometry: Whether to include GeoJSON geometry

        Returns:
            List of parcel dictionaries
        """
        if not parcel_ids:
            return []

        geom_select = f", ST_AsGeoJSON(ST_Transform(geom, {self.WGS84_CRS})) as geojson" if include_geometry else ""

        # Use ANY() for array parameter
        query = f"""
            SELECT
                id_dzialki,
                gmina,
                miejscowosc,
                dzielnica,
                area_m2,
                has_pog as has_mpzp,
                pog_symbol as mpzp_symbol,
                is_residential_zone as mpzp_czy_budowlane,
                quietness_score,
                nature_score,
                accessibility_score,
                centroid_lat,
                centroid_lon,
                (dist_to_main_road < 50) as has_public_road_access
                {geom_select}
            FROM parcels
            WHERE id_dzialki = ANY(:parcel_ids)
        """

        try:
            results = await postgis.execute(query, {"parcel_ids": parcel_ids})
            return [dict(row._mapping) for row in results]
        except Exception as e:
            logger.error(f"Get parcels by IDs error: {e}")
            return []

    async def search_by_criteria(
        self,
        gmina: Optional[str] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        has_mpzp: Optional[bool] = None,
        mpzp_budowlane: Optional[bool] = None,
        min_quietness: Optional[float] = None,
        min_nature: Optional[float] = None,
        min_accessibility: Optional[float] = None,
        order_by: str = "quietness_score",
        order_desc: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search parcels by attribute criteria.

        Args:
            Various filter criteria
            order_by: Column to sort by
            order_desc: Sort descending
            limit: Max results

        Returns:
            List of parcel dictionaries
        """
        conditions = ["1=1"]  # Always true base
        query_params = {"limit": limit}

        if gmina:
            conditions.append("gmina = :gmina")
            query_params["gmina"] = gmina

        if min_area:
            conditions.append("area_m2 >= :min_area")
            query_params["min_area"] = min_area

        if max_area:
            conditions.append("area_m2 <= :max_area")
            query_params["max_area"] = max_area

        if has_mpzp is not None:
            conditions.append("has_pog = :has_mpzp")
            query_params["has_mpzp"] = has_mpzp

        if mpzp_budowlane is not None:
            conditions.append("is_residential_zone = :mpzp_budowlane")
            query_params["mpzp_budowlane"] = mpzp_budowlane

        if min_quietness:
            conditions.append("quietness_score >= :min_quietness")
            query_params["min_quietness"] = min_quietness

        if min_nature:
            conditions.append("nature_score >= :min_nature")
            query_params["min_nature"] = min_nature

        if min_accessibility:
            conditions.append("accessibility_score >= :min_accessibility")
            query_params["min_accessibility"] = min_accessibility

        where_clause = " AND ".join(conditions)
        order_direction = "DESC" if order_desc else "ASC"

        # Validate order_by column
        valid_columns = ["quietness_score", "nature_score", "accessibility_score", "area_m2"]
        if order_by not in valid_columns:
            order_by = "quietness_score"

        query = f"""
            SELECT
                id_dzialki,
                gmina,
                miejscowosc,
                dzielnica,
                area_m2,
                has_pog as has_mpzp,
                pog_symbol as mpzp_symbol,
                is_residential_zone as mpzp_czy_budowlane,
                quietness_score,
                nature_score,
                accessibility_score,
                centroid_lat,
                centroid_lon
            FROM parcels
            WHERE {where_clause}
            ORDER BY {order_by} {order_direction} NULLS LAST
            LIMIT :limit
        """

        try:
            results = await postgis.execute(query, query_params)
            return [dict(row._mapping) for row in results]
        except Exception as e:
            logger.error(f"Search by criteria error: {e}")
            return []

    async def count_parcels(
        self,
        gmina: Optional[str] = None,
        has_mpzp: Optional[bool] = None,
    ) -> int:
        """Count parcels matching criteria."""
        conditions = ["1=1"]
        query_params = {}

        if gmina:
            conditions.append("gmina = :gmina")
            query_params["gmina"] = gmina

        if has_mpzp is not None:
            conditions.append("has_pog = :has_mpzp")
            query_params["has_mpzp"] = has_mpzp

        where_clause = " AND ".join(conditions)
        query = f"SELECT COUNT(*) FROM parcels WHERE {where_clause}"

        try:
            results = await postgis.execute(query, query_params)
            return results[0][0]
        except Exception as e:
            logger.error(f"Count parcels error: {e}")
            return 0

    async def get_gminy_list(self) -> List[str]:
        """Get list of all gminy."""
        query = "SELECT DISTINCT gmina FROM parcels WHERE gmina IS NOT NULL ORDER BY gmina"
        try:
            results = await postgis.execute(query)
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Get gminy error: {e}")
            return []

    async def list_gminy(self) -> List[str]:
        """Alias for get_gminy_list."""
        return await self.get_gminy_list()

    async def get_gmina_statistics(self, gmina_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific gmina."""
        query = """
            SELECT
                gmina,
                COUNT(*) as parcel_count,
                AVG(area_m2) as avg_area_m2,
                100.0 * SUM(CASE WHEN has_pog THEN 1 ELSE 0 END) / COUNT(*) as mpzp_coverage_pct,
                ARRAY_AGG(DISTINCT miejscowosc) FILTER (WHERE miejscowosc IS NOT NULL) as miejscowosci
            FROM parcels
            WHERE gmina = :gmina_name
            GROUP BY gmina
        """
        try:
            results = await postgis.execute(query, {"gmina_name": gmina_name})
            if results:
                row = results[0]._mapping
                return {
                    "gmina": row["gmina"],
                    "parcel_count": row["parcel_count"],
                    "avg_area_m2": float(row["avg_area_m2"]) if row["avg_area_m2"] else None,
                    "mpzp_coverage_pct": float(row["mpzp_coverage_pct"]) if row["mpzp_coverage_pct"] else 0,
                    "miejscowosci": row["miejscowosci"] or [],
                }
            return None
        except Exception as e:
            logger.error(f"Get gmina statistics error: {e}")
            return None

    async def get_miejscowosci(self) -> List[str]:
        """Get list of all miejscowości."""
        query = "SELECT DISTINCT miejscowosc FROM parcels WHERE miejscowosc IS NOT NULL ORDER BY miejscowosc"
        try:
            results = await postgis.execute(query)
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Get miejscowosci error: {e}")
            return []

    async def get_powiaty(self) -> List[str]:
        """Get list of all powiaty."""
        query = "SELECT DISTINCT powiat FROM parcels WHERE powiat IS NOT NULL ORDER BY powiat"
        try:
            results = await postgis.execute(query)
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Get powiaty error: {e}")
            return []

    async def generate_geojson(
        self,
        parcel_ids: List[str],
        include_geometry: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Generate GeoJSON FeatureCollection for parcels."""
        if not parcel_ids:
            return None

        query = f"""
            SELECT
                id_dzialki,
                gmina,
                miejscowosc,
                dzielnica,
                area_m2,
                quietness_score,
                nature_score,
                accessibility_score,
                has_pog as has_mpzp,
                pog_symbol as mpzp_symbol,
                centroid_lat,
                centroid_lon,
                ST_AsGeoJSON(ST_Transform(geom, {self.WGS84_CRS}))::json as geometry
            FROM parcels
            WHERE id_dzialki = ANY(:parcel_ids)
        """

        try:
            results = await postgis.execute(query, {"parcel_ids": parcel_ids})

            features = []
            min_lat, max_lat = float('inf'), float('-inf')
            min_lon, max_lon = float('inf'), float('-inf')

            for row in results:
                r = row._mapping
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id_dzialki": r["id_dzialki"],
                        "gmina": r["gmina"],
                        "miejscowosc": r["miejscowosc"],
                        "area_m2": r["area_m2"],
                        "quietness_score": r["quietness_score"],
                        "nature_score": r["nature_score"],
                        "accessibility_score": r["accessibility_score"],
                        "has_mpzp": r["has_mpzp"],
                        "mpzp_symbol": r["mpzp_symbol"],
                    },
                    "geometry": r["geometry"] if include_geometry else None,
                }
                features.append(feature)

                # Track bounds
                if r["centroid_lat"] and r["centroid_lon"]:
                    min_lat = min(min_lat, r["centroid_lat"])
                    max_lat = max(max_lat, r["centroid_lat"])
                    min_lon = min(min_lon, r["centroid_lon"])
                    max_lon = max(max_lon, r["centroid_lon"])

            geojson = {
                "type": "FeatureCollection",
                "features": features,
            }

            # Calculate center
            center_lat = (min_lat + max_lat) / 2 if features else None
            center_lon = (min_lon + max_lon) / 2 if features else None

            return {
                "geojson": geojson,
                "bounds": [[min_lat, min_lon], [max_lat, max_lon]] if features else None,
                "center": [center_lat, center_lon] if features else None,
                "parcel_count": len(features),
            }

        except Exception as e:
            logger.error(f"Generate GeoJSON error: {e}")
            return None


# Global instance
spatial_service = SpatialService()
