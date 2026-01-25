"""
Graph service using Neo4j.

Handles knowledge graph queries for:
- Administrative hierarchy
- MPZP zoning relationships
- Neighborhood exploration
- PRIMARY parcel search using rich relationships
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from loguru import logger

from app.services.database import neo4j


# =============================================================================
# DATA MODEL DOCUMENTATION (for agent context)
# =============================================================================

# Available categories in Neo4j graph
KATEGORIE_CISZY = ["bardzo_cicha", "cicha", "umiarkowana", "głośna"]
KATEGORIE_NATURY = ["bardzo_zielona", "zielona", "umiarkowana", "zurbanizowana"]
KATEGORIE_DOSTEPU = ["doskonały", "dobry", "umiarkowany", "ograniczony"]
KATEGORIE_POWIERZCHNI = ["mala", "srednia", "duza", "bardzo_duza"]  # <800, 800-1500, 1500-3000, >3000
GESTOSC_ZABUDOWY = ["bardzo_gesta", "gesta", "umiarkowana", "rzadka", "bardzo_rzadka"]
CHARAKTER_TERENU = ["wiejski", "podmiejski", "miejski", "leśny", "mieszany"]

# POI types available for proximity queries
POI_TYPES = ["school", "shop", "hospital", "bus_stop", "industrial"]

# MPZP symbols with descriptions
MPZP_BUDOWLANE = ["MN", "MN/U", "MW", "MW/U", "U", "U/MN"]  # residential/commercial
MPZP_NIEBUDOWLANE = ["R", "ZL", "ZP", "ZZ", "W", "WS"]  # agricultural, forest, green, water

# Water types for Trójmiasto (priority order, premium factor)
WATER_TYPES = {
    "morze": {"name_pl": "Morze", "priority": 1, "premium_factor": 2.0, "threshold_m": 1000},
    "zatoka": {"name_pl": "Zatoka", "priority": 2, "premium_factor": 1.8, "threshold_m": 1000},
    "rzeka": {"name_pl": "Rzeka", "priority": 3, "premium_factor": 1.3, "threshold_m": 300},
    "jezioro": {"name_pl": "Jezioro", "priority": 4, "premium_factor": 1.5, "threshold_m": 500},
    "kanal": {"name_pl": "Kanał", "priority": 5, "premium_factor": 1.1, "threshold_m": 200},
    "staw": {"name_pl": "Staw", "priority": 6, "premium_factor": 1.05, "threshold_m": 100},
}

# Price segments for districts
PRICE_SEGMENTS = ["ULTRA_PREMIUM", "PREMIUM", "HIGH", "MEDIUM", "BUDGET", "ECONOMY"]


@dataclass
class ParcelSearchCriteria:
    """
    Comprehensive criteria for parcel search.

    Represents all dimensions user can specify for finding ideal parcel.
    """
    # Location
    gmina: Optional[str] = None
    miejscowosc: Optional[str] = None
    powiat: Optional[str] = None

    # Area
    min_area_m2: Optional[float] = None
    max_area_m2: Optional[float] = None
    area_category: Optional[List[str]] = None  # ["srednia", "duza"]

    # Character & environment
    charakter_terenu: Optional[List[str]] = None  # ["wiejski", "podmiejski"]
    quietness_categories: Optional[List[str]] = None  # ["bardzo_cicha", "cicha"]
    nature_categories: Optional[List[str]] = None  # ["bardzo_zielona", "zielona"]
    building_density: Optional[List[str]] = None  # ["rzadka", "bardzo_rzadka"]

    # Accessibility
    accessibility_categories: Optional[List[str]] = None  # ["doskonały", "dobry"]
    max_dist_to_school_m: Optional[int] = None
    max_dist_to_shop_m: Optional[int] = None
    max_dist_to_bus_stop_m: Optional[int] = None
    max_dist_to_hospital_m: Optional[int] = None  # Medical accessibility
    has_road_access: Optional[bool] = None

    # Nature proximity
    max_dist_to_forest_m: Optional[int] = None
    max_dist_to_water_m: Optional[int] = None
    min_forest_pct_500m: Optional[float] = None  # e.g., 0.2 = 20% forest in 500m buffer

    # Water type preferences (NEW for Neo4j redesign)
    water_type: Optional[str] = None  # "morze", "jezioro", "rzeka", "kanal", "staw"
    max_dist_to_sea_m: Optional[int] = None
    max_dist_to_lake_m: Optional[int] = None
    max_dist_to_river_m: Optional[int] = None
    near_water_required: Optional[bool] = None  # True = must be near any water

    # MPZP (zoning)
    has_mpzp: Optional[bool] = None
    mpzp_buildable: Optional[bool] = None
    mpzp_symbols: Optional[List[str]] = None  # ["MN", "MN/U"]

    # Industrial distance (for quiet areas)
    min_dist_to_industrial_m: Optional[int] = None

    # Sorting preferences
    sort_by: str = "quietness_score"  # or "nature_score", "accessibility_score", "area_m2"
    sort_desc: bool = True

    # Limit
    limit: int = 50


@dataclass
class GminaInfo:
    """Information about a gmina (municipality)."""
    name: str
    powiat: Optional[str] = None
    parcel_count: int = 0
    avg_area: Optional[float] = None
    pct_with_mpzp: Optional[float] = None


@dataclass
class MPZPInfo:
    """MPZP zoning information."""
    symbol: str
    nazwa: str
    budowlany: bool
    parcel_count: int = 0


class GraphService:
    """Service for Neo4j knowledge graph queries."""

    async def get_gmina_info(self, gmina_name: str) -> Optional[GminaInfo]:
        """
        Get information about a gmina (city) including statistics.

        NEW schema: gmina is a property on Parcel, not a separate node.

        Args:
            gmina_name: Name of the gmina (Gdańsk, Gdynia, or Sopot)

        Returns:
            GminaInfo or None
        """
        query = """
            MATCH (p:Parcel)
            WHERE p.gmina = $gmina
            WITH p.gmina as name,
                 count(p) as parcel_count,
                 avg(p.area_m2) as avg_area,
                 toFloat(sum(CASE WHEN p.pog_symbol IS NOT NULL THEN 1 ELSE 0 END)) / count(p) * 100 as pct_with_mpzp
            RETURN name, parcel_count, avg_area, pct_with_mpzp
        """

        try:
            results = await neo4j.run(query, {"gmina": gmina_name})
            if results:
                r = results[0]
                return GminaInfo(
                    name=r["name"],
                    powiat="Trójmiasto",  # Fixed for this region
                    parcel_count=r.get("parcel_count", 0),
                    avg_area=r.get("avg_area"),
                    pct_with_mpzp=r.get("pct_with_mpzp"),
                )
            return None
        except Exception as e:
            logger.error(f"Get gmina info error: {e}")
            return None

    async def get_all_gminy(self) -> List[str]:
        """Get list of all gminy (cities) names.

        NEW schema: gmina is a property on Parcel, use DISTINCT.
        """
        query = """
            MATCH (p:Parcel)
            RETURN DISTINCT p.gmina as name
            ORDER BY name
        """
        try:
            results = await neo4j.run(query)
            return [r["name"] for r in results if r["name"]]
        except Exception as e:
            logger.error(f"Get all gminy error: {e}")
            return []

    async def get_miejscowosci_in_gmina(self, gmina_name: str) -> List[Dict[str, Any]]:
        """Get all districts (dzielnice) in a gmina (city).

        NEW schema: District nodes connected to City via BELONGS_TO.
        District has: name, city, gmina
        """
        query = """
            MATCH (d:District)-[:BELONGS_TO]->(c:City {name: $gmina})
            OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
            WITH d, count(p) as parcel_count
            RETURN
                d.name as name,
                d.city as city,
                parcel_count
            ORDER BY parcel_count DESC
        """
        try:
            results = await neo4j.run(query, {"gmina": gmina_name})
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Get miejscowosci error: {e}")
            return []

    async def get_mpzp_symbols(self) -> List[MPZPInfo]:
        """Get all POG zoning symbols with statistics.

        NEW schema: pog_symbol is a property on Parcel.
        """
        query = """
            MATCH (p:Parcel)
            WHERE p.pog_symbol IS NOT NULL
            WITH p.pog_symbol as symbol,
                 p.pog_nazwa as nazwa,
                 p.is_residential_zone as is_residential,
                 count(p) as parcel_count
            RETURN symbol, head(collect(nazwa)) as nazwa,
                   any(x IN collect(is_residential) WHERE x = true) as budowlany,
                   sum(parcel_count) as parcel_count
            ORDER BY parcel_count DESC
        """
        try:
            results = await neo4j.run(query)
            return [
                MPZPInfo(
                    symbol=r["symbol"],
                    nazwa=r.get("nazwa", ""),
                    budowlany=r.get("budowlany", False),
                    parcel_count=r.get("parcel_count", 0),
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Get MPZP symbols error: {e}")
            return []

    async def get_parcel_context(self, parcel_id: str) -> Dict[str, Any]:
        """
        Get contextual information about a parcel from the graph.

        NEW schema: Properties on Parcel, District via LOCATED_IN.
        """
        query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)
            OPTIONAL MATCH (d)-[:BELONGS_TO]->(c:City)
            RETURN
                p.id_dzialki as id,
                p.area_m2 as area_m2,
                p.quietness_score as quietness,
                p.nature_score as nature,
                p.accessibility_score as accessibility,
                p.pog_symbol IS NOT NULL as has_mpzp,
                p.gmina as gmina,
                p.dzielnica as miejscowosc,
                'Trójmiasto' as powiat,
                p.pog_symbol as mpzp_symbol,
                p.pog_nazwa as mpzp_nazwa,
                p.is_residential_zone as mpzp_budowlany
        """
        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                return dict(results[0])
            return {}
        except Exception as e:
            logger.error(f"Get parcel context error: {e}")
            return {}

    async def find_parcels_by_mpzp(
        self,
        symbol: str,
        gmina: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find parcels with specific POG zoning symbol.

        NEW schema: pog_symbol is a property on Parcel.

        Args:
            symbol: POG symbol (e.g., "MN", "U")
            gmina: Optional gmina filter
            limit: Max results

        Returns:
            List of parcel dictionaries
        """
        conditions = ["p.pog_symbol = $symbol"]
        params = {"symbol": symbol, "limit": limit}

        if gmina:
            conditions.append("p.gmina = $gmina")
            params["gmina"] = gmina

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (p:Parcel)
            WHERE {where_clause}
            RETURN
                p.id_dzialki as id,
                p.area_m2 as area_m2,
                p.gmina as gmina,
                p.dzielnica as dzielnica,
                p.quietness_score as quietness,
                p.centroid_lat as lat,
                p.centroid_lon as lon,
                p.is_residential_zone as is_residential_zone
            ORDER BY p.quietness_score DESC
            LIMIT $limit
        """

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Find parcels by MPZP error: {e}")
            return []

    async def find_buildable_parcels(
        self,
        gmina: Optional[str] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find parcels with buildable (residential) zoning.

        NEW schema: is_residential_zone is a property on Parcel.

        Args:
            gmina: Optional gmina filter
            min_area: Minimum area
            max_area: Maximum area
            limit: Max results

        Returns:
            List of parcel dictionaries
        """
        conditions = ["p.is_residential_zone = true"]
        params = {"limit": limit}

        if gmina:
            conditions.append("p.gmina = $gmina")
            params["gmina"] = gmina

        if min_area:
            conditions.append("p.area_m2 >= $min_area")
            params["min_area"] = min_area

        if max_area:
            conditions.append("p.area_m2 <= $max_area")
            params["max_area"] = max_area

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (p:Parcel)
            WHERE {where_clause}
            RETURN
                p.id_dzialki as id,
                p.area_m2 as area_m2,
                p.gmina as gmina,
                p.dzielnica as miejscowosc,
                p.quietness_score as quietness,
                p.nature_score as nature,
                p.pog_symbol as mpzp_symbol,
                p.centroid_lat as lat,
                p.centroid_lon as lon,
                p.is_built as is_built
            ORDER BY p.quietness_score DESC
            LIMIT $limit
        """

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Find buildable parcels error: {e}")
            return []

    async def get_administrative_tree(self) -> Dict[str, Any]:
        """
        Get administrative hierarchy tree.

        NEW schema: City -> Districts (via BELONGS_TO relation).
        Returns: {cities: [{name, districts: [{name, parcel_count}]}]}
        """
        query = """
            MATCH (c:City)
            OPTIONAL MATCH (d:District)-[:BELONGS_TO]->(c)
            OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
            WITH c, d, count(p) as parcel_count
            WITH c, collect({name: d.name, parcel_count: parcel_count}) as districts
            RETURN c.name as city, districts
            ORDER BY c.name
        """
        try:
            results = await neo4j.run(query)
            if results:
                return {
                    "region": "Trójmiasto",
                    "cities": [
                        {"name": r["city"], "districts": r["districts"]}
                        for r in results
                    ]
                }
            return {}
        except Exception as e:
            logger.error(f"Get administrative tree error: {e}")
            return {}

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph.

        NEW schema: Parcel, City, District, Water, POI nodes.
        """
        query = """
            MATCH (p:Parcel) WITH count(p) as parcels
            MATCH (c:City) WITH parcels, count(c) as cities
            MATCH (d:District) WITH parcels, cities, count(d) as districts
            MATCH (w:Water) WITH parcels, cities, districts, count(w) as waters
            MATCH (s:School) WITH parcels, cities, districts, waters, count(s) as schools
            MATCH (bs:BusStop) WITH parcels, cities, districts, waters, schools, count(bs) as bus_stops
            RETURN parcels, cities, districts, waters, schools, bus_stops
        """
        try:
            results = await neo4j.run(query)
            if results:
                r = results[0]
                return {
                    "parcels": r.get("parcels", 0),
                    "cities": r.get("cities", 0),
                    "districts": r.get("districts", 0),
                    "waters": r.get("waters", 0),
                    "schools": r.get("schools", 0),
                    "bus_stops": r.get("bus_stops", 0),
                }
            return {}
        except Exception as e:
            logger.error(f"Get graph stats error: {e}")
            return {}


    # =========================================================================
    # PRIMARY SEARCH - Comprehensive parcel search using graph relationships
    # =========================================================================

    async def search_parcels(
        self,
        criteria: ParcelSearchCriteria
    ) -> List[Dict[str, Any]]:
        """
        PRIMARY search function using Neo4j graph relationships.

        Uses the NEW schema (2026-01-24):
        - Parcel nodes with properties (gmina, dzielnica, etc.)
        - Category relations: HAS_QUIETNESS, HAS_NATURE, HAS_ACCESS, HAS_DENSITY
        - Distance properties directly on Parcel nodes

        Args:
            criteria: ParcelSearchCriteria with all search dimensions

        Returns:
            List of parcel dictionaries with full details
        """
        # Build dynamic Cypher query based on criteria
        match_clauses = ["MATCH (p:Parcel)"]
        where_conditions = []
        params = {"limit": criteria.limit}

        # Location filters - now properties on Parcel
        if criteria.gmina:
            where_conditions.append("p.gmina = $gmina")
            params["gmina"] = criteria.gmina

        if criteria.miejscowosc:
            # miejscowosc is now 'dzielnica' in new schema
            where_conditions.append("p.dzielnica = $dzielnica")
            params["dzielnica"] = criteria.miejscowosc

        # powiat is no longer stored - Trójmiasto is single area, skip this filter

        # Area filters (direct properties)
        if criteria.min_area_m2:
            where_conditions.append("p.area_m2 >= $min_area")
            params["min_area"] = criteria.min_area_m2

        if criteria.max_area_m2:
            where_conditions.append("p.area_m2 <= $max_area")
            params["max_area"] = criteria.max_area_m2

        if criteria.area_category:
            # Area category is now size_category property
            where_conditions.append("p.size_category IN $area_categories")
            params["area_categories"] = criteria.area_category

        # NOTE: charakter_terenu filter removed - data is NULL for all parcels

        # Category filters via relationships (NEW schema)
        if criteria.quietness_categories:
            match_clauses.append("MATCH (p)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)")
            where_conditions.append("qc.id IN $quietness_cats")
            params["quietness_cats"] = criteria.quietness_categories

        if criteria.nature_categories:
            match_clauses.append("MATCH (p)-[:HAS_NATURE]->(nc:NatureCategory)")
            where_conditions.append("nc.id IN $nature_cats")
            params["nature_cats"] = criteria.nature_categories

        if criteria.building_density:
            match_clauses.append("MATCH (p)-[:HAS_DENSITY]->(dc:DensityCategory)")
            where_conditions.append("dc.id IN $density")
            params["density"] = criteria.building_density

        # Accessibility filters
        if criteria.accessibility_categories:
            match_clauses.append("MATCH (p)-[:HAS_ACCESS]->(ac:AccessCategory)")
            where_conditions.append("ac.id IN $access_cats")
            params["access_cats"] = criteria.accessibility_categories

        # has_road_access property not available in current schema
        # Could use dist_to_main_road < threshold as proxy if needed
        if criteria.has_road_access is not None:
            # Using dist_to_main_road < 50m as proxy for road access
            if criteria.has_road_access:
                where_conditions.append("p.dist_to_main_road < 50")
            else:
                where_conditions.append("p.dist_to_main_road >= 50")

        # POI proximity filters - now properties on Parcel
        if criteria.max_dist_to_school_m:
            where_conditions.append("p.dist_to_school <= $max_school_dist")
            params["max_school_dist"] = criteria.max_dist_to_school_m

        if criteria.max_dist_to_shop_m:
            where_conditions.append("p.dist_to_supermarket <= $max_shop_dist")
            params["max_shop_dist"] = criteria.max_dist_to_shop_m

        if criteria.max_dist_to_bus_stop_m:
            where_conditions.append("p.dist_to_bus_stop <= $max_bus_dist")
            params["max_bus_dist"] = criteria.max_dist_to_bus_stop_m

        if criteria.max_dist_to_hospital_m:
            where_conditions.append("p.dist_to_doctors <= $max_hospital_dist")
            params["max_hospital_dist"] = criteria.max_dist_to_hospital_m

        # Nature proximity filters - now properties
        if criteria.max_dist_to_forest_m:
            where_conditions.append("p.dist_to_forest <= $max_forest_dist")
            params["max_forest_dist"] = criteria.max_dist_to_forest_m

        if criteria.max_dist_to_water_m:
            where_conditions.append("p.dist_to_water <= $max_water_dist")
            params["max_water_dist"] = criteria.max_dist_to_water_m

        if criteria.min_forest_pct_500m:
            where_conditions.append("p.pct_forest_500m >= $min_forest_pct")
            params["min_forest_pct"] = criteria.min_forest_pct_500m

        # Industrial distance - property
        if criteria.min_dist_to_industrial_m:
            where_conditions.append("p.dist_to_industrial >= $min_industrial_dist")
            params["min_industrial_dist"] = criteria.min_dist_to_industrial_m

        # Water type filters (NEW)
        if criteria.water_type:
            dist_field_map = {
                "morze": "dist_to_sea",
                "zatoka": "dist_to_sea",
                "rzeka": "dist_to_river",
                "jezioro": "dist_to_lake",
                "kanal": "dist_to_canal",
                "staw": "dist_to_pond",
            }
            dist_field = dist_field_map.get(criteria.water_type, "dist_to_water")
            threshold = WATER_TYPES.get(criteria.water_type, {}).get("threshold_m", 500)
            where_conditions.append(f"p.{dist_field} <= $water_threshold")
            params["water_threshold"] = threshold

        if criteria.max_dist_to_sea_m:
            where_conditions.append("p.dist_to_sea <= $max_sea_dist")
            params["max_sea_dist"] = criteria.max_dist_to_sea_m

        if criteria.max_dist_to_lake_m:
            where_conditions.append("p.dist_to_lake <= $max_lake_dist")
            params["max_lake_dist"] = criteria.max_dist_to_lake_m

        if criteria.max_dist_to_river_m:
            where_conditions.append("p.dist_to_river <= $max_river_dist")
            params["max_river_dist"] = criteria.max_dist_to_river_m

        if criteria.near_water_required:
            where_conditions.append("p.dist_to_water <= 500")

        # POG/MPZP filters - now properties on Parcel
        if criteria.has_mpzp is not None:
            # has_mpzp is now represented by pog_symbol being NOT NULL
            if criteria.has_mpzp:
                where_conditions.append("p.pog_symbol IS NOT NULL")
            else:
                where_conditions.append("p.pog_symbol IS NULL")

        if criteria.mpzp_buildable:
            where_conditions.append("p.is_residential_zone = true")

        if criteria.mpzp_symbols:
            where_conditions.append("p.pog_symbol IN $pog_symbols")
            params["pog_symbols"] = criteria.mpzp_symbols

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Sorting
        sort_field = f"p.{criteria.sort_by}" if criteria.sort_by else "p.quietness_score"
        sort_dir = "DESC" if criteria.sort_desc else "ASC"

        # Build full query
        query = f"""
            {chr(10).join(match_clauses)}
            {where_clause}
            RETURN DISTINCT
                p.id_dzialki as id,
                p.gmina as gmina,
                p.dzielnica as miejscowosc,
                p.area_m2 as area_m2,
                p.quietness_score as quietness_score,
                p.nature_score as nature_score,
                p.accessibility_score as accessibility_score,
                p.pog_symbol IS NOT NULL as has_mpzp,
                p.pog_symbol as mpzp_symbol,
                p.centroid_lat as lat,
                p.centroid_lon as lon,
                p.dist_to_forest as dist_to_forest,
                p.dist_to_water as dist_to_water,
                p.dist_to_school as dist_to_school,
                p.dist_to_supermarket as dist_to_shop,
                p.dist_to_bus_stop as dist_to_bus_stop,
                p.pct_forest_500m as pct_forest_500m,
                p.count_buildings_500m as count_buildings_500m,
                p.is_built as is_built,
                p.is_residential_zone as is_residential_zone,
                p.nearest_water_type as nearest_water_type,
                p.dist_to_sea as dist_to_sea,
                p.kategoria_ciszy as kategoria_ciszy,
                p.kategoria_natury as kategoria_natury,
                p.gestosc_zabudowy as gestosc_zabudowy
            ORDER BY {sort_field} {sort_dir}
            LIMIT $limit
        """

        logger.info(f"Graph search with {len(where_conditions)} conditions, sorting by {criteria.sort_by}")
        logger.debug(f"Query: {query}")
        logger.debug(f"Params: {params}")

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Graph search error: {e}")
            return []

    async def search_parcels_simple(
        self,
        gmina: Optional[str] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        has_mpzp: Optional[bool] = None,
        quiet: bool = False,  # prefer quiet areas
        green: bool = False,  # prefer green/natural areas
        accessible: bool = False,  # prefer good accessibility
        near_forest: bool = False,  # want to be near forest
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Simplified search with boolean preferences.

        Converts simple preferences to graph criteria.
        """
        criteria = ParcelSearchCriteria(
            gmina=gmina,
            min_area_m2=min_area,
            max_area_m2=max_area,
            has_mpzp=has_mpzp,
            limit=limit,
        )

        if quiet:
            criteria.quietness_categories = ["bardzo_cicha", "cicha"]

        if green:
            criteria.nature_categories = ["bardzo_zielona", "zielona"]

        if accessible:
            criteria.accessibility_categories = ["doskonały", "dobry"]

        if near_forest:
            criteria.max_dist_to_forest_m = 300

        return await self.search_parcels(criteria)

    async def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of available data for agent context.

        NEW schema: Uses HAS_QUIETNESS, HAS_NATURE, etc. relations.
        Returns statistics and available options for each dimension.
        """
        query = """
            // Count parcels by quietness category
            MATCH (p:Parcel)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
            WITH qc.id as category, count(p) as count
            WITH collect({category: category, count: count}) as quietness_stats

            // Count parcels by nature category
            MATCH (p:Parcel)-[:HAS_NATURE]->(nc:NatureCategory)
            WITH quietness_stats, nc.id as category, count(p) as count
            WITH quietness_stats, collect({category: category, count: count}) as nature_stats

            // Count parcels by density category
            MATCH (p:Parcel)-[:HAS_DENSITY]->(dc:DensityCategory)
            WITH quietness_stats, nature_stats, dc.id as category, count(p) as count
            WITH quietness_stats, nature_stats, collect({category: category, count: count}) as density_stats

            // Count by gmina (city)
            MATCH (p:Parcel)
            WITH quietness_stats, nature_stats, density_stats,
                 p.gmina as gmina, count(p) as count
            WITH quietness_stats, nature_stats, density_stats,
                 collect({gmina: gmina, count: count}) as gmina_stats

            // POG/MPZP stats
            MATCH (p:Parcel)
            WITH quietness_stats, nature_stats, density_stats, gmina_stats,
                 sum(CASE WHEN p.pog_symbol IS NOT NULL THEN 1 ELSE 0 END) as with_mpzp,
                 sum(CASE WHEN p.is_residential_zone = true THEN 1 ELSE 0 END) as residential_zone,
                 count(p) as total

            RETURN
                quietness_stats,
                nature_stats,
                density_stats,
                gmina_stats,
                with_mpzp,
                residential_zone,
                total
        """

        try:
            results = await neo4j.run(query)
            if results:
                r = results[0]
                return {
                    "total_parcels": r.get("total", 0),
                    "with_mpzp": r.get("with_mpzp", 0),
                    "residential_zone": r.get("residential_zone", 0),
                    "quietness_distribution": r.get("quietness_stats", []),
                    "nature_distribution": r.get("nature_stats", []),
                    "density_distribution": r.get("density_stats", []),
                    "gmina_distribution": r.get("gmina_stats", []),
                    "available_categories": {
                        "quietness": KATEGORIE_CISZY,
                        "nature": KATEGORIE_NATURY,
                        "accessibility": KATEGORIE_DOSTEPU,
                        "area": KATEGORIE_POWIERZCHNI,
                        "density": GESTOSC_ZABUDOWY,
                    },
                    "mpzp_info": {
                        "buildable_symbols": MPZP_BUDOWLANE,
                        "non_buildable_symbols": MPZP_NIEBUDOWLANE,
                    },
                    "water_types": list(WATER_TYPES.keys()),
                    "price_segments": PRICE_SEGMENTS,
                }
            return {}
        except Exception as e:
            logger.error(f"Get data summary error: {e}")
            return {}

    # =========================================================================
    # ADMINISTRATIVE HIERARCHY EXPLORATION
    # =========================================================================

    async def get_children_in_hierarchy(
        self,
        level: str,
        parent_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get children in administrative hierarchy.

        NEW schema: City -> District (via BELONGS_TO).

        Args:
            level: "region" → returns cities (Gdańsk, Gdynia, Sopot)
                   "city" → returns districts in city
            parent_name: Name of parent unit (required for city level)

        Returns:
            List of children with counts
        """
        try:
            if level == "region":
                # Return all cities in Trójmiasto
                query = """
                    MATCH (c:City)
                    OPTIONAL MATCH (d:District)-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
                    WITH c, count(DISTINCT d) as district_count, count(DISTINCT p) as parcel_count
                    RETURN
                        c.name as name,
                        district_count,
                        parcel_count
                    ORDER BY c.name
                """
                results = await neo4j.run(query)
                return [dict(r) for r in results]

            elif level == "city" and parent_name:
                # Return districts in given city
                query = """
                    MATCH (d:District)-[:BELONGS_TO]->(c:City {name: $parent})
                    OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
                    WITH d, count(p) as parcel_count
                    RETURN
                        d.name as name,
                        parcel_count
                    ORDER BY parcel_count DESC, d.name
                """
                results = await neo4j.run(query, {"parent": parent_name})
                return [dict(r) for r in results]

            # Legacy support: gmina = city
            elif level == "gmina" and parent_name:
                return await self.get_children_in_hierarchy("city", parent_name)

            else:
                return []

        except Exception as e:
            logger.error(f"Get children in hierarchy error: {e}")
            return []

    async def get_all_cities(self) -> List[str]:
        """Get list of all city names.

        NEW schema: City nodes instead of Powiat.
        """
        query = """
            MATCH (c:City)
            RETURN c.name as name
            ORDER BY c.name
        """
        try:
            results = await neo4j.run(query)
            return [r["name"] for r in results]
        except Exception as e:
            logger.error(f"Get all cities error: {e}")
            return []

    async def get_all_powiaty(self) -> List[str]:
        """Legacy method - returns cities instead of powiaty."""
        return await self.get_all_cities()

    async def get_area_category_stats(
        self,
        gmina: Optional[str] = None,
        dzielnica: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get distribution of parcels by category in given area.

        NEW schema: Uses HAS_QUIETNESS, HAS_NATURE, HAS_DENSITY relations.

        Args:
            gmina: Optional city filter (Gdańsk, Gdynia, Sopot)
            dzielnica: Optional district filter

        Returns:
            Dictionary with category distributions
        """
        # Build location filter
        conditions = []
        params = {}

        if gmina:
            conditions.append("p.gmina = $gmina")
            params["gmina"] = gmina
        if dzielnica:
            conditions.append("p.dzielnica = $dzielnica")
            params["dzielnica"] = dzielnica

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Simpler query - aggregate directly
        query = f"""
            MATCH (p:Parcel)
            {where_clause}
            WITH count(p) as total,
                 sum(CASE WHEN p.pog_symbol IS NOT NULL THEN 1 ELSE 0 END) as with_mpzp,
                 sum(CASE WHEN p.is_residential_zone = true THEN 1 ELSE 0 END) as residential,
                 sum(CASE WHEN p.has_public_road_access = true THEN 1 ELSE 0 END) as with_road_access,
                 sum(CASE WHEN p.is_built = true THEN 1 ELSE 0 END) as built

            // Get category distributions
            MATCH (p2:Parcel)
            {where_clause.replace('p.', 'p2.')}
            OPTIONAL MATCH (p2)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
            WITH total, with_mpzp, residential, with_road_access, built,
                 qc.id as q_cat, count(p2) as q_count
            WITH total, with_mpzp, residential, with_road_access, built,
                 collect({{category: q_cat, count: q_count}}) as quietness_stats

            MATCH (p3:Parcel)
            {where_clause.replace('p.', 'p3.')}
            OPTIONAL MATCH (p3)-[:HAS_NATURE]->(nc:NatureCategory)
            WITH total, with_mpzp, residential, with_road_access, built, quietness_stats,
                 nc.id as n_cat, count(p3) as n_count
            WITH total, with_mpzp, residential, with_road_access, built, quietness_stats,
                 collect({{category: n_cat, count: n_count}}) as nature_stats

            RETURN total, with_mpzp, residential, with_road_access, built,
                   quietness_stats, nature_stats
        """

        try:
            results = await neo4j.run(query, params)
            if results:
                r = results[0]
                total = r.get("total", 0)
                with_mpzp = r.get("with_mpzp", 0)
                with_road = r.get("with_road_access", 0)

                return {
                    "total_parcels": total,
                    "with_mpzp": with_mpzp,
                    "pct_mpzp": round((with_mpzp / total * 100), 1) if total > 0 else 0,
                    "residential_zone": r.get("residential", 0),
                    "with_road_access": with_road,
                    "pct_road_access": round((with_road / total * 100), 1) if total > 0 else 0,
                    "built": r.get("built", 0),
                    "quietness_distribution": r.get("quietness_stats", []),
                    "nature_distribution": r.get("nature_stats", []),
                    "location_filter": {"gmina": gmina, "dzielnica": dzielnica},
                }
            return {"error": "No data found"}
        except Exception as e:
            logger.error(f"Get area category stats error: {e}")
            return {"error": str(e)}

    async def get_parcel_neighborhood(self, parcel_id: str) -> Dict[str, Any]:
        """
        Get detailed neighborhood context for a parcel.

        NEW schema: All data is on Parcel properties. Categories stored as properties.

        Args:
            parcel_id: ID of the parcel

        Returns:
            Dictionary with full neighborhood context
        """
        query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})

            RETURN
                p.id_dzialki as id,
                p.area_m2 as area_m2,
                p.centroid_lat as lat,
                p.centroid_lon as lon,

                // Location
                p.gmina as gmina,
                p.dzielnica as miejscowosc,
                'Trójmiasto' as powiat,

                // Categories (properties on Parcel)
                p.kategoria_ciszy as kategoria_ciszy,
                p.kategoria_natury as kategoria_natury,
                p.kategoria_dostepu as kategoria_dostepu,
                p.gestosc_zabudowy as gestosc_zabudowy,

                // Scores (properties)
                p.quietness_score as quietness_score,
                p.nature_score as nature_score,
                p.accessibility_score as accessibility_score,

                // POG/MPZP (properties)
                p.has_pog as has_mpzp,
                p.pog_symbol as mpzp_symbol,
                p.pog_nazwa as mpzp_nazwa,
                p.is_residential_zone as mpzp_budowlany,
                p.pog_maks_wysokosc_m as pog_max_wysokosc,
                p.pog_maks_zabudowa_pct as pog_max_zabudowa,

                // POI distances (properties)
                p.dist_to_school as dist_to_school,
                p.dist_to_supermarket as dist_to_shop,
                p.dist_to_doctors as dist_to_hospital,
                p.dist_to_bus_stop as dist_to_bus_stop,
                p.dist_to_industrial as dist_to_industrial,

                // Nature distances (properties)
                p.dist_to_forest as dist_to_forest,
                p.dist_to_water as dist_to_water,

                // Water-specific distances
                p.dist_to_sea as dist_to_sea,
                p.dist_to_river as dist_to_river,
                p.dist_to_lake as dist_to_lake,
                p.dist_to_canal as dist_to_canal,
                p.dist_to_pond as dist_to_pond,
                p.nearest_water_type as nearest_water_type,

                // Buffer analysis (properties)
                p.pct_forest_500m as pct_forest_500m,
                p.pct_water_500m as pct_water_500m,
                p.count_buildings_500m as count_buildings_500m,

                // Building info
                p.is_built as is_built,
                p.building_count as building_count,
                p.building_coverage_pct as building_coverage_pct,
                p.building_max_floors as building_max_floors
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                r = dict(results[0])

                # Map water type to Polish name
                water_type_pl = {
                    "morze": "Morze",
                    "jezioro": "Jezioro",
                    "rzeka": "Rzeka",
                    "kanal": "Kanał",
                    "staw": "Staw"
                }

                # Build human-readable summary
                summary = []

                # Location
                if r.get("miejscowosc"):
                    summary.append(f"Lokalizacja: {r['miejscowosc']}, {r.get('gmina', '')}")
                elif r.get("gmina"):
                    summary.append(f"Lokalizacja: {r['gmina']}")

                # Area
                if r.get("area_m2"):
                    summary.append(f"Powierzchnia: {r['area_m2']:,.0f} m²")

                # Built status
                is_built = r.get("is_built")
                if is_built and str(is_built).lower() == 'true':
                    building_info = "Zabudowana"
                    if r.get("building_count"):
                        building_info += f" ({r['building_count']} bud.)"
                    summary.append(building_info)
                else:
                    summary.append("Niezabudowana")

                # Quietness
                if r.get("quietness_score") is not None:
                    kat = r.get('kategoria_ciszy', '')
                    summary.append(f"Cisza: {int(r['quietness_score'])}/100 ({kat})")

                # Nature
                if r.get("nature_score") is not None:
                    kat = r.get('kategoria_natury', '')
                    summary.append(f"Natura: {int(r['nature_score'])}/100 ({kat})")

                # Accessibility
                if r.get("accessibility_score") is not None:
                    kat = r.get('kategoria_dostepu', '')
                    summary.append(f"Dostępność: {int(r['accessibility_score'])}/100 ({kat})")

                # Water proximity
                if r.get("nearest_water_type"):
                    wt = r["nearest_water_type"]
                    water_pl = water_type_pl.get(wt, wt)
                    # Get the specific distance for this water type
                    dist_key = f"dist_to_{wt}" if wt != "morze" else "dist_to_sea"
                    water_dist = r.get(dist_key, r.get("dist_to_water"))
                    if water_dist:
                        summary.append(f"Woda: {water_pl} ({int(water_dist)}m)")

                r["summary"] = summary
                return r
            return {"error": f"Parcel not found: {parcel_id}"}
        except Exception as e:
            logger.error(f"Get parcel neighborhood error: {e}")
            return {"error": str(e)}

    # =========================================================================
    # WATER-RELATED METHODS (NEW - Neo4j Redesign)
    # =========================================================================

    async def search_parcels_by_water_type(
        self,
        water_type: str,
        max_distance: int = 500,
        city: Optional[str] = None,
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
        is_built: Optional[bool] = None,
        is_residential_zone: Optional[bool] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for parcels near a specific type of water.

        Args:
            water_type: Type of water (morze, jezioro, rzeka, kanal, staw)
            max_distance: Maximum distance in meters
            city: Optional city filter (Gdańsk, Gdynia, Sopot)
            min_area: Minimum parcel area in m2
            max_area: Maximum parcel area in m2
            is_built: Filter by built status
            is_residential_zone: Filter by residential zoning
            limit: Maximum results

        Returns:
            List of matching parcels with water info
        """
        # Map water_type to distance field
        dist_field_map = {
            "morze": "dist_to_sea",
            "zatoka": "dist_to_sea",  # Same as sea
            "rzeka": "dist_to_river",
            "jezioro": "dist_to_lake",
            "kanal": "dist_to_canal",
            "staw": "dist_to_pond",
        }

        dist_field = dist_field_map.get(water_type, "dist_to_water")

        # Build WHERE conditions
        conditions = [f"p.{dist_field} IS NOT NULL", f"p.{dist_field} <= $max_distance"]

        if city:
            conditions.append("p.gmina = $city")
        if min_area:
            conditions.append("p.area_m2 >= $min_area")
        if max_area:
            conditions.append("p.area_m2 <= $max_area")
        if is_built is not None:
            conditions.append(f"p.is_built = {str(is_built).lower()}")
        if is_residential_zone is not None:
            conditions.append(f"p.is_residential_zone = {str(is_residential_zone).lower()}")

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (p:Parcel)
            WHERE {where_clause}
            RETURN
                p.id_dzialki as id_dzialki,
                p.gmina as gmina,
                p.dzielnica as dzielnica,
                p.area_m2 as area_m2,
                p.{dist_field} as distance_to_water,
                p.nearest_water_type as nearest_water_type,
                p.is_built as is_built,
                p.is_residential_zone as is_residential_zone,
                p.quietness_score as quietness_score,
                p.nature_score as nature_score,
                p.centroid_lat as lat,
                p.centroid_lon as lon,
                p.pog_symbol as pog_symbol,
                p.price_segment as price_segment
            ORDER BY p.{dist_field} ASC
            LIMIT $limit
        """

        try:
            results = await neo4j.run(query, {
                "max_distance": max_distance,
                "city": city,
                "min_area": min_area,
                "max_area": max_area,
                "limit": limit,
            })
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Search parcels by water type error: {e}")
            return []

    async def get_water_near_parcel(self, parcel_id: str) -> Dict[str, Any]:
        """
        Get information about all water bodies near a parcel.

        Args:
            parcel_id: ID of the parcel

        Returns:
            Dictionary with water distances and types
        """
        query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})
            RETURN
                p.id_dzialki as id_dzialki,
                p.dzielnica as dzielnica,

                // All water distances
                p.dist_to_sea as dist_to_sea,
                p.dist_to_river as dist_to_river,
                p.dist_to_lake as dist_to_lake,
                p.dist_to_canal as dist_to_canal,
                p.dist_to_pond as dist_to_pond,
                p.dist_to_water as dist_to_water,

                // Nearest water info
                p.nearest_water_type as nearest_water_type
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                r = dict(results[0])

                # Build water summary
                water_info = []
                if r.get("dist_to_sea") and r["dist_to_sea"] <= 5000:
                    water_info.append(f"Morze: {r['dist_to_sea']}m")
                if r.get("dist_to_lake") and r["dist_to_lake"] <= 3000:
                    water_info.append(f"Jezioro: {r['dist_to_lake']}m")
                if r.get("dist_to_river") and r["dist_to_river"] <= 2000:
                    water_info.append(f"Rzeka: {r['dist_to_river']}m")
                if r.get("dist_to_canal") and r["dist_to_canal"] <= 1000:
                    water_info.append(f"Kanał: {r['dist_to_canal']}m")

                r["water_summary"] = water_info if water_info else ["Brak wody w pobliżu"]
                r["has_water_nearby"] = len(water_info) > 0

                return r
            return {"error": f"Parcel not found: {parcel_id}"}
        except Exception as e:
            logger.error(f"Get water near parcel error: {e}")
            return {"error": str(e)}

    async def get_parcel_full_context(self, parcel_id: str) -> Dict[str, Any]:
        """
        Get complete context for a parcel including all features.

        All data from Parcel properties - no relations needed.

        Args:
            parcel_id: ID of the parcel

        Returns:
            Comprehensive parcel context for agent
        """
        query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})

            RETURN
                // Basic info
                p.id_dzialki as id_dzialki,
                p.gmina as gmina,
                p.dzielnica as dzielnica,
                p.area_m2 as area_m2,
                p.centroid_lat as lat,
                p.centroid_lon as lon,

                // Categories (properties on Parcel)
                p.kategoria_ciszy as kategoria_ciszy,
                p.kategoria_natury as kategoria_natury,
                p.kategoria_dostepu as kategoria_dostepu,
                p.gestosc_zabudowy as gestosc_zabudowy,

                // Scores
                p.quietness_score as quietness_score,
                p.nature_score as nature_score,
                p.accessibility_score as accessibility_score,

                // Building info
                p.is_built as is_built,
                p.building_count as building_count,
                p.building_coverage_pct as building_coverage_pct,
                p.building_max_floors as building_max_floors,

                // POG (zoning)
                p.pog_symbol as pog_symbol,
                p.pog_nazwa as pog_nazwa,
                p.pog_profil_podstawowy as pog_profil,
                p.pog_maks_wysokosc_m as pog_max_wysokosc,
                p.pog_maks_zabudowa_pct as pog_max_zabudowa,
                p.is_residential_zone as is_residential_zone,

                // Water info
                p.nearest_water_type as nearest_water_type,
                p.dist_to_sea as dist_to_sea,
                p.dist_to_lake as dist_to_lake,
                p.dist_to_river as dist_to_river,
                p.dist_to_canal as dist_to_canal,
                p.dist_to_pond as dist_to_pond,
                p.dist_to_water as dist_to_water,

                // Distances
                p.dist_to_school as dist_to_school,
                p.dist_to_bus_stop as dist_to_bus_stop,
                p.dist_to_forest as dist_to_forest,
                p.dist_to_supermarket as dist_to_supermarket,
                p.dist_to_main_road as dist_to_main_road,

                // Context
                p.pct_forest_500m as pct_forest_500m,
                p.count_buildings_500m as count_buildings_500m
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                r = dict(results[0])

                # Map water type to Polish name
                water_type_pl = {
                    "morze": "Morze",
                    "jezioro": "Jezioro",
                    "rzeka": "Rzeka",
                    "kanal": "Kanał",
                    "staw": "Staw"
                }

                # Build comprehensive summary
                is_built = r.get("is_built")
                is_built_bool = is_built and str(is_built).lower() == 'true'
                is_res = r.get("is_residential_zone")
                is_res_bool = is_res and str(is_res).lower() == 'true'

                summary = {
                    "lokalizacja": f"{r.get('dzielnica', '')}, {r.get('gmina', '')}",
                    "powierzchnia": f"{r.get('area_m2', 0):,.0f} m²",
                    "zabudowana": "Tak" if is_built_bool else "Nie",
                    "strefa_mieszkaniowa": "Tak" if is_res_bool else "Nie",
                    "cisza": f"{r.get('quietness_score', 0)}/100 ({r.get('kategoria_ciszy', '')})",
                    "natura": f"{r.get('nature_score', 0)}/100 ({r.get('kategoria_natury', '')})",
                    "dostepnosc": f"{r.get('accessibility_score', 0)}/100 ({r.get('kategoria_dostepu', '')})",
                }

                # Water summary
                if r.get("nearest_water_type"):
                    wt = r["nearest_water_type"]
                    water_pl = water_type_pl.get(wt, wt)
                    dist_key = f"dist_to_{wt}" if wt != "morze" else "dist_to_sea"
                    water_dist = r.get(dist_key, r.get("dist_to_water"))
                    if water_dist:
                        summary["najblizsa_woda"] = f"{water_pl} ({int(water_dist)}m)"

                r["summary"] = summary
                return r
            return {"error": f"Parcel not found: {parcel_id}"}
        except Exception as e:
            logger.error(f"Get parcel full context error: {e}")
            return {"error": str(e)}

    async def get_water_statistics(self, city: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about water proximity for parcels.

        Args:
            city: Optional city filter

        Returns:
            Statistics about water proximity
        """
        city_filter = "WHERE p.gmina = $city" if city else ""

        query = f"""
            MATCH (p:Parcel)
            {city_filter}
            WITH p
            RETURN
                count(p) as total_parcels,

                // Near sea
                sum(CASE WHEN p.dist_to_sea <= 1000 THEN 1 ELSE 0 END) as near_sea_1km,
                sum(CASE WHEN p.dist_to_sea <= 500 THEN 1 ELSE 0 END) as near_sea_500m,

                // Near lake
                sum(CASE WHEN p.dist_to_lake <= 500 THEN 1 ELSE 0 END) as near_lake_500m,
                sum(CASE WHEN p.dist_to_lake <= 300 THEN 1 ELSE 0 END) as near_lake_300m,

                // Near river
                sum(CASE WHEN p.dist_to_river <= 300 THEN 1 ELSE 0 END) as near_river_300m,
                sum(CASE WHEN p.dist_to_river <= 200 THEN 1 ELSE 0 END) as near_river_200m,

                // By nearest water type
                sum(CASE WHEN p.nearest_water_type = 'morze' THEN 1 ELSE 0 END) as nearest_sea,
                sum(CASE WHEN p.nearest_water_type = 'jezioro' THEN 1 ELSE 0 END) as nearest_lake,
                sum(CASE WHEN p.nearest_water_type = 'rzeka' THEN 1 ELSE 0 END) as nearest_river,
                sum(CASE WHEN p.nearest_water_type = 'staw' THEN 1 ELSE 0 END) as nearest_pond
        """

        try:
            results = await neo4j.run(query, {"city": city})
            if results:
                return dict(results[0])
            return {}
        except Exception as e:
            logger.error(f"Get water statistics error: {e}")
            return {"error": str(e)}


# Global instance
graph_service = GraphService()
