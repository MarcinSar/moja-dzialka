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

    # NEO4J V2: Ownership (NEW 2026-01-25)
    ownership_type: Optional[str] = None  # "prywatna", "publiczna", "spoldzielcza", "koscielna", "inna"

    # NEO4J V2: Build status (NEW 2026-01-25)
    build_status: Optional[str] = None  # "zabudowana", "niezabudowana"

    # NEO4J V2: Size category via relation (NEW 2026-01-25)
    size_category: Optional[List[str]] = None  # ["pod_dom", "duza"]

    # NEO4J V2: POG residential (NEW 2026-01-25)
    pog_residential: Optional[bool] = None  # Only residential POG zones

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

        # NEO4J V2: Ownership filter via HAS_OWNERSHIP relation
        if criteria.ownership_type:
            match_clauses.append("MATCH (p)-[:HAS_OWNERSHIP]->(ot:OwnershipType)")
            where_conditions.append("ot.id = $ownership_type")
            params["ownership_type"] = criteria.ownership_type

        # NEO4J V2: Build status filter via HAS_BUILD_STATUS relation
        if criteria.build_status:
            match_clauses.append("MATCH (p)-[:HAS_BUILD_STATUS]->(bs:BuildStatus)")
            where_conditions.append("bs.id = $build_status")
            params["build_status"] = criteria.build_status

        # NEO4J V2: Size category filter via HAS_SIZE relation
        if criteria.size_category:
            match_clauses.append("MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory)")
            where_conditions.append("sz.id IN $size_categories")
            params["size_categories"] = criteria.size_category

        # NEO4J V2: POG residential filter via HAS_POG relation
        if criteria.pog_residential:
            match_clauses.append("MATCH (p)-[:HAS_POG]->(pz:POGZone)")
            where_conditions.append("pz.is_residential = true")

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
        # NOTE: has_public_road_access doesn't exist - use dist_to_main_road < 50 as proxy
        query = f"""
            MATCH (p:Parcel)
            {where_clause}
            WITH count(p) as total,
                 sum(CASE WHEN p.pog_symbol IS NOT NULL THEN 1 ELSE 0 END) as with_mpzp,
                 sum(CASE WHEN p.is_residential_zone = true THEN 1 ELSE 0 END) as residential,
                 sum(CASE WHEN p.dist_to_main_road IS NOT NULL AND p.dist_to_main_road < 50 THEN 1 ELSE 0 END) as with_road_access,
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

        # Build WHERE conditions (all parameterized to prevent SQL injection)
        conditions = [f"p.{dist_field} IS NOT NULL", f"p.{dist_field} <= $max_distance"]

        if city:
            conditions.append("p.gmina = $city")
        if min_area:
            conditions.append("p.area_m2 >= $min_area")
        if max_area:
            conditions.append("p.area_m2 <= $max_area")
        if is_built is not None:
            conditions.append("p.is_built = $is_built")
        if is_residential_zone is not None:
            conditions.append("p.is_residential_zone = $is_residential")

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
            # Build params dict with all values (parameterized to prevent injection)
            params = {
                "max_distance": max_distance,
                "city": city,
                "min_area": min_area,
                "max_area": max_area,
                "limit": limit,
            }
            # Add boolean params only if set (prevents None comparison issues)
            if is_built is not None:
                params["is_built"] = is_built
            if is_residential_zone is not None:
                params["is_residential"] = is_residential_zone

            results = await neo4j.run(query, params)
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

    # =========================================================================
    # DYNAMIC LOCATION METHODS (New - 2026-01-25)
    # Agent dynamically queries these instead of hardcoded lists
    # =========================================================================

    async def get_available_locations(self) -> Dict[str, Any]:
        """
        Get available locations dynamically from the database.

        Agent uses this at conversation start or when user gives ambiguous location.
        Returns miejscowości and gminy separately (in MVP they're the same).

        Returns:
            Dict with miejscowosci, gminy, total_parcels, by_miejscowosc
        """
        query = """
            MATCH (c:City)
            OPTIONAL MATCH (p:Parcel) WHERE p.gmina = c.name
            WITH c.name as miejscowosc, count(p) as parcel_count
            RETURN miejscowosc, parcel_count
            ORDER BY parcel_count DESC
        """

        try:
            results = await neo4j.run(query)
            miejscowosci = [r["miejscowosc"] for r in results if r["miejscowosc"]]
            by_miejscowosc = {r["miejscowosc"]: r["parcel_count"] for r in results if r["miejscowosc"]}
            total = sum(by_miejscowosc.values())

            return {
                "miejscowosci": miejscowosci,
                "gminy": miejscowosci,  # In MVP they're the same, later separate query
                "total_parcels": total,
                "by_miejscowosc": by_miejscowosc,
                "hint": "Obecnie obsługujemy Trójmiasto (Gdańsk, Gdynia, Sopot). Podaj miejscowość lub dzielnicę."
            }
        except Exception as e:
            logger.error(f"Get available locations error: {e}")
            return {"error": str(e), "miejscowosci": [], "gminy": [], "total_parcels": 0}

    async def get_districts_in_miejscowosc(self, miejscowosc: str) -> Dict[str, Any]:
        """
        Get districts in a given MIEJSCOWOŚĆ (not gmina!).

        Dzielnica belongs to MIEJSCOWOŚĆ, not to gmina directly.
        In MVP: gmina = miejscowość (Trójmiasto cities).

        Args:
            miejscowosc: Name of the miejscowość (e.g., "Gdańsk")

        Returns:
            Dict with districts list, counts, and gmina context
        """
        query = """
            MATCH (d:District)-[:BELONGS_TO]->(c:City {name: $miejscowosc})
            OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
            WITH d.name as dzielnica, count(p) as parcel_count
            RETURN dzielnica, parcel_count
            ORDER BY parcel_count DESC
        """

        try:
            results = await neo4j.run(query, {"miejscowosc": miejscowosc})
            districts = [r["dzielnica"] for r in results if r["dzielnica"]]
            by_district = {r["dzielnica"]: r["parcel_count"] for r in results if r["dzielnica"]}

            # In MVP: gmina = miejscowość
            gmina = await self._get_gmina_for_miejscowosc(miejscowosc)

            total_parcels = sum(by_district.values())

            return {
                "miejscowosc": miejscowosc,
                "gmina": gmina,
                "districts": districts,
                "district_count": len(districts),
                "parcel_count": total_parcels,
                "by_district": by_district
            }
        except Exception as e:
            logger.error(f"Get districts in miejscowość error: {e}")
            return {"error": str(e), "miejscowosc": miejscowosc, "districts": []}

    # Districts that exist in price data but NOT in cadastral (EGiB) data
    # Maps to nearest cadastral district or None (search whole city)
    DISTRICT_ALIASES: Dict[str, Dict[str, Any]] = {
        # Matemblewo is a known area but parcels are categorized under Matarnia or "Gdańsk (inne)"
        "matemblewo": {"gmina": "Gdańsk", "search_in": ["Matarnia", "Osowa"], "note": "obszar przy TPK"},
        "vii dwór": {"gmina": "Gdańsk", "search_in": ["Oliwa", "Wrzeszcz"], "note": "część Oliwy"},
        "śródmieście": {"gmina": "Gdańsk", "search_in": ["Stare Miasto", "Dolne Miasto"], "note": "centrum"},
        "ujeścisko-łostowice": {"gmina": "Gdańsk", "search_in": ["Łostowice", "Ujeścisko"], "note": "nowa dzielnica"},
        # Gdynia aliases
        "chwarzno-wiczlino": {"gmina": "Gdynia", "search_in": ["Wiczlino", "Chwarzno"], "note": "nowa dzielnica"},
        "działki leśne": {"gmina": "Gdynia", "search_in": ["Redłowo", "Mały Kack"], "note": "obszar leśny"},
        # Sopot aliases
        "dolny sopot": {"gmina": "Sopot", "search_in": None, "note": "centrum Sopotu"},
        "górny sopot": {"gmina": "Sopot", "search_in": None, "note": "wyższa część"},
        "karlikowo": {"gmina": "Sopot", "search_in": None, "note": "luksusowa część"},
        "kamienny potok": {"gmina": "Sopot", "search_in": None, "note": "spokojna część"},
        "brodwino": {"gmina": "Sopot", "search_in": None, "note": "zachodnia część"},
    }

    async def resolve_location(self, location_text: str) -> Dict[str, Any]:
        """
        Resolve user's location text to gmina + miejscowosc + dzielnica.

        Uses Neo4j Fulltext Search for fuzzy matching:
        - Handles typos: "mateblewo" → "Matemblewo"
        - Handles missing Polish chars: "Gdansk" → "Gdańsk"
        - Handles declensions: "w Osowej" → "Osowa"
        - Handles districts in price data but not in cadastral (DISTRICT_ALIASES)

        IMPORTANT: Dzielnica belongs to MIEJSCOWOŚĆ, not directly to gmina!

        Args:
            location_text: Raw text from user (e.g., "okolice Osowej", "Orłowo", "Gdańsk")

        Returns:
            Dict with resolved: bool, gmina, miejscowosc, dzielnica, parcel_count, fuzzy
            or error if not found
        """
        # Clean input text
        clean_text = location_text.lower().strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "okolice ", "okolica ", "gmina ", "miasto ", "m. ", "dzielnica ",
            "rejon ", "w ", "na ", "blisko ", "centrum "
        ]
        for prefix in prefixes_to_remove:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()

        # Handle genitive forms (Polish grammar)
        # Gdańska -> Gdańsk, Gdyni -> Gdynia, Sopotu -> Sopot
        search_variants = [clean_text]
        if clean_text.endswith("a"):
            search_variants.append(clean_text[:-1])  # Gdańska -> Gdańsk
        if clean_text.endswith("i"):
            search_variants.append(clean_text[:-1] + "a")  # Gdyni -> Gdynia
        if clean_text.endswith("u"):
            search_variants.append(clean_text[:-1])  # Sopotu -> Sopot
        if clean_text.endswith("ej"):
            search_variants.append(clean_text[:-2] + "a")  # Osowej -> Osowa

        try:
            # 1. Try fulltext search on District names (fuzzy with ~)
            # This handles typos and missing Polish characters
            for search_term in search_variants:
                query = """
                CALL db.index.fulltext.queryNodes('district_names_ft', $search_term)
                YIELD node as district, score
                WHERE score > 0.5
                MATCH (district)-[:BELONGS_TO]->(city:City)
                OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(district)
                WITH district, city, score, count(p) as parcel_count
                RETURN
                    district.name as dzielnica,
                    city.name as miejscowosc,
                    city.name as gmina,
                    score,
                    parcel_count
                ORDER BY score DESC
                LIMIT 3
                """

                results = await neo4j.run(query, {"search_term": f"{search_term}~"})

                if results and len(results) > 0:
                    best = results[0]
                    return {
                        "resolved": True,
                        "gmina": best["gmina"],
                        "miejscowosc": best["miejscowosc"],
                        "dzielnica": best["dzielnica"],
                        "parcel_count": best["parcel_count"] or 0,
                        "fuzzy": best["score"] < 1.0,
                        "confidence": best["score"],
                        "alternatives": [r["dzielnica"] for r in results[1:]] if len(results) > 1 else []
                    }

            # 2. Fallback - try City (miejscowość) match with CONTAINS
            for search_term in search_variants:
                query = """
                MATCH (c:City)
                WHERE toLower(c.name) CONTAINS toLower($search_term)
                   OR toLower($search_term) CONTAINS toLower(c.name)
                OPTIONAL MATCH (p:Parcel) WHERE p.gmina = c.name
                WITH c, count(p) as parcel_count
                RETURN c.name as miasto, parcel_count
                LIMIT 1
                """

                city_results = await neo4j.run(query, {"search_term": search_term})

                if city_results and len(city_results) > 0:
                    return {
                        "resolved": True,
                        "gmina": city_results[0]["miasto"],
                        "miejscowosc": city_results[0]["miasto"],
                        "dzielnica": None,
                        "parcel_count": city_results[0]["parcel_count"] or 0,
                        "fuzzy": False
                    }

            # 3. Try direct parcel dzielnica property match (fallback for districts without nodes)
            for search_term in search_variants:
                query = """
                MATCH (p:Parcel)
                WHERE toLower(p.dzielnica) CONTAINS toLower($search_term)
                WITH p.dzielnica as dzielnica, p.gmina as gmina, count(p) as cnt
                RETURN dzielnica, gmina, cnt
                ORDER BY cnt DESC
                LIMIT 1
                """

                parcel_results = await neo4j.run(query, {"search_term": search_term})

                if parcel_results and len(parcel_results) > 0:
                    r = parcel_results[0]
                    return {
                        "resolved": True,
                        "gmina": r["gmina"],
                        "miejscowosc": r["gmina"],
                        "dzielnica": r["dzielnica"],
                        "parcel_count": r["cnt"] or 0,
                        "fuzzy": False
                    }

            # 4. Not found - get available options
            locations = await self.get_available_locations()
            return {
                "resolved": False,
                "error": f"Lokalizacja '{location_text}' nie została rozpoznana.",
                "available_miejscowosci": locations.get("miejscowosci", []),
                "hint": "Podaj nazwę miasta (Gdańsk, Gdynia, Sopot) lub dzielnicy."
            }

        except Exception as e:
            logger.error(f"Resolve location error: {e}")
            return {"resolved": False, "error": str(e)}

    async def validate_location_combination(
        self,
        miejscowosc: Optional[str] = None,
        dzielnica: Optional[str] = None,
        gmina: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate if miejscowość + dzielnica combination is correct.

        Uses ONE Cypher query instead of N+1 queries (Python loops removed).

        IMPORTANT: Dzielnica belongs to MIEJSCOWOŚĆ, not to gmina!

        Args:
            miejscowosc: City/miejscowość name
            dzielnica: District name
            gmina: Optional gmina for additional validation

        Returns:
            Dict with valid: bool, error if invalid, suggestion if available
        """
        if not dzielnica:
            # No dzielnica to validate
            return {"valid": True, "message": "Brak dzielnicy do walidacji"}

        try:
            # Single query - find dzielnica and its parent city
            query = """
            MATCH (d:District)-[:BELONGS_TO]->(c:City)
            WHERE toLower(d.name) = toLower($dzielnica)
            OPTIONAL MATCH (p:Parcel)-[:LOCATED_IN]->(d)
            WITH d, c, count(p) as parcel_count
            RETURN d.name as dzielnica, c.name as miasto, parcel_count
            LIMIT 1
            """

            results = await neo4j.run(query, {"dzielnica": dzielnica})

            if not results or len(results) == 0:
                # Dzielnica not found - try to suggest similar ones
                suggest_query = """
                MATCH (d:District)-[:BELONGS_TO]->(c:City)
                WHERE d.name CONTAINS $partial OR toLower(d.name) CONTAINS toLower($partial)
                RETURN d.name as dzielnica, c.name as miasto
                LIMIT 3
                """
                suggestions = await neo4j.run(suggest_query, {"partial": dzielnica[:3]})

                return {
                    "valid": False,
                    "error": f"Dzielnica '{dzielnica}' nie istnieje w bazie.",
                    "suggestions": [s["dzielnica"] for s in suggestions] if suggestions else []
                }

            actual_city = results[0]["miasto"]
            actual_dzielnica = results[0]["dzielnica"]
            parcel_count = results[0]["parcel_count"] or 0

            # Check if miejscowość matches
            if miejscowosc and miejscowosc.lower() != actual_city.lower():
                return {
                    "valid": False,
                    "error": f"Dzielnica '{actual_dzielnica}' należy do {actual_city}, nie {miejscowosc}.",
                    "suggestion": {
                        "miejscowosc": actual_city,
                        "dzielnica": actual_dzielnica,
                        "gmina": actual_city  # In MVP gmina = miejscowość
                    }
                }

            # Valid combination
            return {
                "valid": True,
                "dzielnica": actual_dzielnica,
                "miejscowosc": actual_city,
                "gmina": actual_city,  # In MVP gmina = miejscowość
                "parcel_count": parcel_count
            }

        except Exception as e:
            logger.error(f"Validate location combination error: {e}")
            return {"valid": False, "error": str(e)}

    async def _get_gmina_for_miejscowosc(self, miejscowosc: str) -> str:
        """
        Get gmina for a given miejscowość.

        In MVP: gmina = miejscowość (Trójmiasto cities).
        In future: query database for gminy with multiple miejscowości (e.g., Żukowo).

        Args:
            miejscowosc: Name of the miejscowość

        Returns:
            Gmina name
        """
        # In MVP, gmina = miejscowość for Trójmiasto
        # TODO: When adding gminy wiejskie, query:
        # MATCH (m:Miejscowosc {name: $miejscowosc})-[:PART_OF]->(g:Gmina)
        # RETURN g.name
        return miejscowosc

    # =========================================================================
    # SEMANTIC ENTITY RESOLUTION (V2 - 2026-01-25)
    # Uses 512-dim embeddings and vector search for fuzzy matching
    # =========================================================================

    async def resolve_location_v2(
        self,
        location_text: str,
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> Dict[str, Any]:
        """
        Resolve location using vector similarity search on LocationName nodes.

        This is the V2 implementation that uses semantic embeddings to handle:
        - "Matemblewo" → Matarnia (location exists in price data but not cadastral)
        - "VII Dwór" → search in [Oliwa, Wrzeszcz]
        - "spokojna okolica Gdańska" → semantic matching

        Steps:
        1. Encode user input with sentence-transformers (512-dim)
        2. Query LocationName vector index
        3. Return best match with confidence

        Args:
            location_text: User's location description (e.g., "Matemblewo", "okolice Osowej")
            top_k: Number of candidates to retrieve
            min_similarity: Minimum cosine similarity threshold

        Returns:
            Dict with:
            - resolved: bool
            - canonical_name: Display name
            - type: "city" | "district" | "area"
            - maps_to_district: EGiB district name or None
            - maps_to_gmina: City/gmina name
            - search_in_districts: List of districts to search in
            - price_segment: Price segment if known
            - similarity: Match score
            - confidence: HIGH/MEDIUM/LOW
            - alternatives: Other possible matches
        """
        try:
            # Import embedding service
            from app.services.embedding_service import EmbeddingService

            # Clean input
            clean_text = location_text.lower().strip()
            prefixes = ["okolice ", "okolica ", "gmina ", "miasto ", "m. ", "dzielnica ",
                       "rejon ", "w ", "na ", "blisko ", "centrum "]
            for prefix in prefixes:
                if clean_text.startswith(prefix):
                    clean_text = clean_text[len(prefix):].strip()

            # Generate embedding for user input
            query_embedding = EmbeddingService.encode(clean_text)

            # Vector search on LocationName nodes
            query = """
            CALL db.index.vector.queryNodes('location_name_embedding_idx', $top_k, $embedding)
            YIELD node, score
            WHERE score >= $min_similarity
            RETURN
                node.id as id,
                node.canonical_name as canonical_name,
                node.type as type,
                node.maps_to_district as maps_to_district,
                node.maps_to_gmina as maps_to_gmina,
                node.search_in_districts as search_in_districts,
                node.price_segment as price_segment,
                node.price_min as price_min,
                node.price_max as price_max,
                node.note as note,
                score as similarity
            ORDER BY score DESC
            """

            results = await neo4j.run(query, {
                "embedding": query_embedding,
                "top_k": top_k,
                "min_similarity": min_similarity
            })

            if not results or len(results) == 0:
                # Fallback to original resolve_location for districts not in LocationName
                logger.info(f"No vector match for '{location_text}', falling back to fulltext")
                return await self.resolve_location(location_text)

            best = results[0]

            # Determine confidence based on similarity
            similarity = best["similarity"]
            if similarity > 0.9:
                confidence = "HIGH"
            elif similarity > 0.8:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Build search_in_districts - fallback to maps_to_district if not specified
            search_in_districts = best.get("search_in_districts") or []
            if not search_in_districts and best.get("maps_to_district"):
                search_in_districts = [best["maps_to_district"]]

            return {
                "resolved": True,
                "canonical_name": best["canonical_name"],
                "type": best["type"],
                "maps_to_district": best["maps_to_district"],
                "maps_to_gmina": best["maps_to_gmina"],
                "search_in_districts": search_in_districts,
                "price_segment": best.get("price_segment"),
                "price_min": best.get("price_min"),
                "price_max": best.get("price_max"),
                "note": best.get("note"),
                "similarity": similarity,
                "confidence": confidence,
                "alternatives": [r["canonical_name"] for r in results[1:]] if len(results) > 1 else [],
                # Compatibility with existing code
                "gmina": best["maps_to_gmina"],
                "dzielnica": best["maps_to_district"],
                "miejscowosc": best["maps_to_gmina"],
            }

        except Exception as e:
            logger.warning(f"resolve_location_v2 error: {e}, falling back to v1")
            # Fallback to original implementation
            return await self.resolve_location(location_text)

    async def resolve_semantic_category(
        self,
        user_text: str,
        category_type: str
    ) -> Dict[str, Any]:
        """
        Resolve user's description to graph category values using vector search.

        Maps natural language descriptions to category enum values:
        - "spokojna okolica" → ["bardzo_cicha", "cicha"]
        - "blisko lasu" → ["bardzo_zielona", "zielona"]
        - "dobry dojazd" → ["doskonała", "dobra"]

        Args:
            user_text: User's description (e.g., "spokojna", "zielona okolica")
            category_type: One of "quietness", "nature", "accessibility", "density"

        Returns:
            Dict with:
            - resolved: bool
            - matched_name: Canonical name of matched category
            - values: List of graph category IDs to use in query
            - similarity: Match score
        """
        try:
            from app.services.embedding_service import EmbeddingService

            query_embedding = EmbeddingService.encode(user_text.lower().strip())

            query = """
            CALL db.index.vector.queryNodes('semantic_category_embedding_idx', 3, $embedding)
            YIELD node, score
            WHERE node.type = $category_type AND score >= 0.6
            RETURN
                node.id as id,
                node.canonical_name as name,
                node.maps_to_values as values,
                score as similarity
            ORDER BY score DESC
            LIMIT 1
            """

            results = await neo4j.run(query, {
                "embedding": query_embedding,
                "category_type": category_type
            })

            if not results or len(results) == 0:
                return {
                    "resolved": False,
                    "error": f"No matching {category_type} category for '{user_text}'"
                }

            best = results[0]
            return {
                "resolved": True,
                "matched_name": best["name"],
                "values": best["values"],
                "similarity": best["similarity"]
            }

        except Exception as e:
            logger.error(f"resolve_semantic_category error: {e}")
            return {"resolved": False, "error": str(e)}

    async def resolve_water_type(
        self,
        user_text: str
    ) -> Dict[str, Any]:
        """
        Resolve user's water description to water type.

        Maps natural language to water type enum:
        - "nad morzem" → "morze"
        - "przy jeziorze" → "jezioro"
        - "blisko wody" → "jezioro" (default)

        Args:
            user_text: User's water description (e.g., "nad morzem", "przy jeziorze")

        Returns:
            Dict with:
            - resolved: bool
            - water_type: Water type ID
            - canonical_name: Display name
            - premium_factor: Price multiplier for this water type
            - similarity: Match score
        """
        try:
            from app.services.embedding_service import EmbeddingService

            query_embedding = EmbeddingService.encode(user_text.lower().strip())

            query = """
            CALL db.index.vector.queryNodes('water_type_name_embedding_idx', 3, $embedding)
            YIELD node, score
            WHERE score >= 0.5
            RETURN
                node.id as id,
                node.canonical_name as canonical_name,
                node.maps_to_water_type as water_type,
                node.premium_factor as premium_factor,
                score as similarity
            ORDER BY score DESC
            LIMIT 1
            """

            results = await neo4j.run(query, {"embedding": query_embedding})

            if not results or len(results) == 0:
                return {
                    "resolved": False,
                    "error": f"No matching water type for '{user_text}'",
                    "hint": "Available: morze, jezioro, rzeka, kanał, staw"
                }

            best = results[0]
            return {
                "resolved": True,
                "water_type": best["water_type"],
                "canonical_name": best["canonical_name"],
                "premium_factor": best["premium_factor"],
                "similarity": best["similarity"]
            }

        except Exception as e:
            logger.error(f"resolve_water_type error: {e}")
            return {"resolved": False, "error": str(e)}

    async def resolve_poi_type(
        self,
        user_text: str
    ) -> Dict[str, Any]:
        """
        Resolve user's POI description to POI types.

        Maps natural language to POI type IDs:
        - "szkoła" → ["school", "kindergarten"]
        - "sklep" → ["shop", "supermarket"]
        - "przystanek" → ["bus_stop"]

        Args:
            user_text: User's POI description (e.g., "szkoła", "sklep w pobliżu")

        Returns:
            Dict with:
            - resolved: bool
            - poi_types: List of POI type IDs
            - canonical_name: Display name
            - similarity: Match score
        """
        try:
            from app.services.embedding_service import EmbeddingService

            query_embedding = EmbeddingService.encode(user_text.lower().strip())

            query = """
            CALL db.index.vector.queryNodes('poi_type_name_embedding_idx', 3, $embedding)
            YIELD node, score
            WHERE score >= 0.5
            RETURN
                node.id as id,
                node.canonical_name as canonical_name,
                node.maps_to_poi_types as poi_types,
                score as similarity
            ORDER BY score DESC
            LIMIT 1
            """

            results = await neo4j.run(query, {"embedding": query_embedding})

            if not results or len(results) == 0:
                return {
                    "resolved": False,
                    "error": f"No matching POI type for '{user_text}'"
                }

            best = results[0]
            return {
                "resolved": True,
                "poi_types": best["poi_types"],
                "canonical_name": best["canonical_name"],
                "similarity": best["similarity"]
            }

        except Exception as e:
            logger.error(f"resolve_poi_type error: {e}")
            return {"resolved": False, "error": str(e)}

    # =========================================================================
    # NEO4J NATIVE VECTOR SEARCH (replacing Milvus for simplicity)
    # =========================================================================

    async def search_similar_parcels_vector(
        self,
        reference_parcel_id: str,
        top_k: int = 10,
        gmina: Optional[str] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar parcels using Neo4j's native Vector Index.

        Uses 32-dimensional embeddings stored on Parcel.embedding property.
        This replaces the need for separate Milvus database.

        Args:
            reference_parcel_id: ID of the parcel to find similar ones to
            top_k: Number of results to return
            gmina: Optional city filter
            min_area: Optional minimum area filter
            max_area: Optional maximum area filter

        Returns:
            List of similar parcels with similarity scores
        """
        # Build WHERE conditions for post-filtering
        conditions = ["similar.id_dzialki <> $parcel_id"]
        params = {"parcel_id": reference_parcel_id, "top_k": top_k * 2}  # Fetch more to account for filters

        if gmina:
            conditions.append("similar.gmina = $gmina")
            params["gmina"] = gmina
        if min_area:
            conditions.append("similar.area_m2 >= $min_area")
            params["min_area"] = min_area
        if max_area:
            conditions.append("similar.area_m2 <= $max_area")
            params["max_area"] = max_area

        where_clause = " AND ".join(conditions)

        query = f"""
        // Get embedding from reference parcel
        MATCH (ref:Parcel {{id_dzialki: $parcel_id}})
        WHERE ref.embedding IS NOT NULL

        // Search for similar parcels using vector index
        CALL db.index.vector.queryNodes('parcel_embedding_index', $top_k, ref.embedding)
        YIELD node as similar, score

        // Apply post-filters
        WHERE {where_clause}

        RETURN
            similar.id_dzialki as id,
            similar.gmina as gmina,
            similar.dzielnica as dzielnica,
            similar.area_m2 as area_m2,
            similar.quietness_score as quietness_score,
            similar.nature_score as nature_score,
            similar.accessibility_score as accessibility_score,
            similar.centroid_lat as lat,
            similar.centroid_lon as lon,
            similar.pog_symbol as mpzp_symbol,
            similar.is_built as is_built,
            score as similarity
        ORDER BY score DESC
        LIMIT {top_k}
        """

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Vector similarity search error: {e}")
            return []

    async def search_by_preferences_vector(
        self,
        preferences: Dict[str, float],
        top_k: int = 20,
        gmina: Optional[str] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for parcels using a preference vector.

        Creates a synthetic embedding from user preferences and searches
        for similar parcels in the vector space.

        Args:
            preferences: Dict with keys like 'quietness', 'nature', 'accessibility'
                        and float values 0.0-1.0 representing importance
            top_k: Number of results
            gmina: Optional city filter
            min_area: Optional minimum area
            max_area: Optional maximum area

        Returns:
            List of matching parcels with similarity scores
        """
        # Build preference embedding (32 dimensions matching SRAI)
        pref_embedding = self._build_preference_embedding(preferences)

        # Build WHERE conditions
        conditions = []
        params = {"embedding": pref_embedding, "top_k": top_k * 2}

        if gmina:
            conditions.append("p.gmina = $gmina")
            params["gmina"] = gmina
        if min_area:
            conditions.append("p.area_m2 >= $min_area")
            params["min_area"] = min_area
        if max_area:
            conditions.append("p.area_m2 <= $max_area")
            params["max_area"] = max_area

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        CALL db.index.vector.queryNodes('parcel_embedding_index', $top_k, $embedding)
        YIELD node as p, score
        {where_clause}
        RETURN
            p.id_dzialki as id,
            p.gmina as gmina,
            p.dzielnica as dzielnica,
            p.area_m2 as area_m2,
            p.quietness_score as quietness_score,
            p.nature_score as nature_score,
            p.accessibility_score as accessibility_score,
            p.centroid_lat as lat,
            p.centroid_lon as lon,
            p.pog_symbol as mpzp_symbol,
            p.is_built as is_built,
            score as similarity
        ORDER BY score DESC
        LIMIT {top_k}
        """

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Preference vector search error: {e}")
            return []

    def _build_preference_embedding(self, preferences: Dict[str, float]) -> List[float]:
        """
        Build a 32-dimensional embedding from user preferences.

        Maps preference weights to embedding dimensions based on how
        SRAI embeddings were generated (matching 18_generate_embeddings.py structure).

        Args:
            preferences: Dict with keys like:
                - quietness: 0.0-1.0
                - nature: 0.0-1.0
                - accessibility: 0.0-1.0
                - area_preference: 0.0 (small) to 1.0 (large)

        Returns:
            32-dimensional embedding vector
        """
        import numpy as np

        # 32-dimensional embedding
        dim = 32
        vector = np.zeros(dim)

        # Preference mapping to embedding dimensions
        # These indices should align with SRAI embedding structure
        preference_mapping = {
            "quietness": (0, 8),       # Dimensions 0-7: quietness-related features
            "nature": (8, 16),         # Dimensions 8-15: nature-related features
            "accessibility": (16, 24), # Dimensions 16-23: accessibility features
            "area_preference": (24, 32), # Dimensions 24-31: area/density features
        }

        for pref_name, weight in preferences.items():
            if pref_name in preference_mapping and weight is not None:
                start, end = preference_mapping[pref_name]
                # Spread the weight across dimensions with some variation
                for i in range(start, end):
                    # Alternate signs to create realistic embedding pattern
                    sign = 1 if (i - start) % 2 == 0 else -1
                    vector[i] = sign * weight * (1.0 - 0.1 * ((i - start) % 4))

        # Normalize to unit vector
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    async def get_quiet_districts(
        self,
        gmina: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get districts with the most quiet parcels.

        Used for dynamic suggestions instead of hardcoded lists.

        Args:
            gmina: Optional city filter
            limit: Number of districts to return

        Returns:
            List of districts with quiet parcel counts
        """
        gmina_filter = "AND p.gmina = $gmina" if gmina else ""

        query = f"""
        MATCH (p:Parcel)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
        WHERE qc.id IN ['bardzo_cicha', 'cicha']
              AND p.dzielnica IS NOT NULL
              {gmina_filter}
        WITH p.dzielnica as district, p.gmina as gmina, count(p) as quiet_count
        RETURN district as name, gmina, quiet_count
        ORDER BY quiet_count DESC
        LIMIT $limit
        """

        try:
            results = await neo4j.run(query, {"gmina": gmina, "limit": limit})
            return [dict(r) for r in results if r.get("name")]
        except Exception as e:
            logger.error(f"Get quiet districts error: {e}")
            return []

    async def get_green_districts(
        self,
        gmina: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get districts with the most green/natural parcels.

        Used for dynamic suggestions instead of hardcoded lists.

        Args:
            gmina: Optional city filter
            limit: Number of districts to return

        Returns:
            List of districts with green parcel counts
        """
        gmina_filter = "AND p.gmina = $gmina" if gmina else ""

        query = f"""
        MATCH (p:Parcel)-[:HAS_NATURE]->(nc:NatureCategory)
        WHERE nc.id IN ['bardzo_zielona', 'zielona']
              AND p.dzielnica IS NOT NULL
              {gmina_filter}
        WITH p.dzielnica as district, p.gmina as gmina, count(p) as green_count
        RETURN district as name, gmina, green_count
        ORDER BY green_count DESC
        LIMIT $limit
        """

        try:
            results = await neo4j.run(query, {"gmina": gmina, "limit": limit})
            return [dict(r) for r in results if r.get("name")]
        except Exception as e:
            logger.error(f"Get green districts error: {e}")
            return []

    async def search_parcels_randomized(
        self,
        criteria: ParcelSearchCriteria,
        exclude_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search parcels with randomization for repeated searches.

        Uses rand() ordering to return different results each time.
        Excludes already shown parcel IDs.

        Args:
            criteria: Search criteria
            exclude_ids: List of parcel IDs to exclude (already shown)

        Returns:
            List of parcel dictionaries
        """
        # Build base query similar to search_parcels
        match_clauses = ["MATCH (p:Parcel)"]
        where_conditions = []
        params = {"limit": criteria.limit}

        # Exclude already shown parcels
        if exclude_ids:
            where_conditions.append("NOT p.id_dzialki IN $exclude_ids")
            params["exclude_ids"] = exclude_ids

        # Location filters
        if criteria.gmina:
            where_conditions.append("p.gmina = $gmina")
            params["gmina"] = criteria.gmina

        if criteria.miejscowosc:
            where_conditions.append("p.dzielnica = $dzielnica")
            params["dzielnica"] = criteria.miejscowosc

        # Area filters
        if criteria.min_area_m2:
            where_conditions.append("p.area_m2 >= $min_area")
            params["min_area"] = criteria.min_area_m2

        if criteria.max_area_m2:
            where_conditions.append("p.area_m2 <= $max_area")
            params["max_area"] = criteria.max_area_m2

        # Category filters via relationships
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

        if criteria.accessibility_categories:
            match_clauses.append("MATCH (p)-[:HAS_ACCESS]->(ac:AccessCategory)")
            where_conditions.append("ac.id IN $access_cats")
            params["access_cats"] = criteria.accessibility_categories

        # POI proximity filters
        if criteria.max_dist_to_forest_m:
            where_conditions.append("p.dist_to_forest <= $max_forest_dist")
            params["max_forest_dist"] = criteria.max_dist_to_forest_m

        if criteria.max_dist_to_water_m:
            where_conditions.append("p.dist_to_water <= $max_water_dist")
            params["max_water_dist"] = criteria.max_dist_to_water_m

        # MPZP filters
        if criteria.has_mpzp is not None:
            if criteria.has_mpzp:
                where_conditions.append("p.pog_symbol IS NOT NULL")
            else:
                where_conditions.append("p.pog_symbol IS NULL")

        if criteria.mpzp_buildable:
            where_conditions.append("p.is_residential_zone = true")

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # RANDOM ordering for different results each time
        query = f"""
            {chr(10).join(match_clauses)}
            {where_clause}
            WITH p, rand() as r
            ORDER BY r
            LIMIT $limit
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
                p.pct_forest_500m as pct_forest_500m,
                p.kategoria_ciszy as kategoria_ciszy,
                p.kategoria_natury as kategoria_natury
        """

        logger.info(f"Randomized search with {len(where_conditions)} conditions, excluding {len(exclude_ids or [])} parcels")

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Randomized search error: {e}")
            return []

    # =========================================================================
    # NEO4J V2: ADJACENCY, NEAR POI, GRAPH EMBEDDINGS (2026-01-25)
    # Multi-hop traversals using ADJACENT_TO and NEAR_* relations
    # =========================================================================

    async def find_adjacent_parcels(
        self,
        parcel_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find parcels adjacent to the given parcel using ADJACENT_TO relation.

        Uses 407,825 ADJACENT_TO relations with shared_border_m property.

        Args:
            parcel_id: ID of the reference parcel
            limit: Maximum number of neighbors to return

        Returns:
            List of neighboring parcels with shared border length
        """
        query = """
        MATCH (p:Parcel {id_dzialki: $parcel_id})-[r:ADJACENT_TO]-(neighbor:Parcel)
        OPTIONAL MATCH (neighbor)-[:LOCATED_IN]->(d:District)
        RETURN
            neighbor.id_dzialki AS id,
            neighbor.dzielnica AS dzielnica,
            neighbor.gmina AS gmina,
            neighbor.area_m2 AS area_m2,
            neighbor.quietness_score AS quietness_score,
            neighbor.nature_score AS nature_score,
            neighbor.is_built AS is_built,
            neighbor.centroid_lat AS lat,
            neighbor.centroid_lon AS lon,
            r.shared_border_m AS shared_border_m
        ORDER BY r.shared_border_m DESC
        LIMIT $limit
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id, "limit": limit})
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Find adjacent parcels error: {e}")
            return []

    async def search_near_poi(
        self,
        poi_type: str,
        poi_name: Optional[str] = None,
        max_distance_m: int = 1000,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search parcels near a specific POI using NEAR_* relations.

        Uses pre-computed NEAR_SCHOOL, NEAR_SHOP, NEAR_BUS_STOP, etc. relations
        with distance_m property.

        Args:
            poi_type: Type of POI (school, shop, bus_stop, forest, water)
            poi_name: Optional name filter (e.g., "SP nr 45")
            max_distance_m: Maximum distance in meters
            limit: Maximum results

        Returns:
            List of parcels near the specified POI
        """
        # Map poi_type to relation and node type
        poi_config = {
            "school": {"relation": "NEAR_SCHOOL", "node": "School"},
            "shop": {"relation": "NEAR_SHOP", "node": "Shop"},
            "bus_stop": {"relation": "NEAR_BUS_STOP", "node": "BusStop"},
            "forest": {"relation": "NEAR_FOREST", "node": "Forest"},
            "water": {"relation": "NEAR_WATER", "node": "Water"},
        }

        if poi_type not in poi_config:
            logger.warning(f"Unknown POI type: {poi_type}")
            return []

        rel_type = poi_config[poi_type]["relation"]
        node_type = poi_config[poi_type]["node"]

        # Build query with optional name filter
        name_filter = "AND toLower(poi.name) CONTAINS toLower($poi_name)" if poi_name else ""

        query = f"""
        MATCH (p:Parcel)-[r:{rel_type}]->(poi:{node_type})
        WHERE r.distance_m <= $max_distance
              {name_filter}
        RETURN
            p.id_dzialki AS id,
            p.dzielnica AS dzielnica,
            p.gmina AS gmina,
            p.area_m2 AS area_m2,
            p.quietness_score AS quietness_score,
            p.nature_score AS nature_score,
            p.centroid_lat AS lat,
            p.centroid_lon AS lon,
            poi.name AS poi_name,
            r.distance_m AS distance_m
        ORDER BY r.distance_m ASC
        LIMIT $limit
        """

        params = {
            "max_distance": max_distance_m,
            "limit": limit
        }
        if poi_name:
            params["poi_name"] = poi_name

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Search near POI error: {e}")
            return []

    async def find_similar_by_graph_embedding(
        self,
        parcel_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find structurally similar parcels using graph embeddings (256-dim FastRP).

        Uses Neo4j GDS FastRP embeddings that capture graph structure:
        - Same neighborhood (district)
        - Similar category assignments (quietness, nature, etc.)
        - Similar ownership and build status

        Different from text embeddings which capture semantic description.

        Args:
            parcel_id: ID of the reference parcel
            limit: Number of similar parcels to return

        Returns:
            List of structurally similar parcels with similarity scores
        """
        query = """
        MATCH (ref:Parcel {id_dzialki: $parcel_id})
        WHERE ref.graph_embedding IS NOT NULL

        CALL db.index.vector.queryNodes('parcel_graph_embedding_idx', $limit_plus, ref.graph_embedding)
        YIELD node AS similar, score

        WHERE similar.id_dzialki <> $parcel_id

        RETURN
            similar.id_dzialki AS id,
            similar.dzielnica AS dzielnica,
            similar.gmina AS gmina,
            similar.area_m2 AS area_m2,
            similar.quietness_score AS quietness_score,
            similar.nature_score AS nature_score,
            similar.accessibility_score AS accessibility_score,
            similar.is_built AS is_built,
            similar.centroid_lat AS lat,
            similar.centroid_lon AS lon,
            score AS similarity
        ORDER BY score DESC
        LIMIT $limit
        """

        try:
            results = await neo4j.run(query, {
                "parcel_id": parcel_id,
                "limit": limit,
                "limit_plus": limit + 1  # Fetch extra to exclude self
            })
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Find similar by graph embedding error: {e}")
            return []

    async def graphrag_search(
        self,
        query_embedding: List[float],
        ownership_type: Optional[str] = None,
        build_status: Optional[str] = None,
        size_category: Optional[List[str]] = None,
        gmina: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        GraphRAG: Combine vector search with graph constraints.

        1. Vector search finds semantically similar parcels (text_embedding 512-dim)
        2. Graph constraints filter by ownership, build status, size, location
        3. Returns hybrid-ranked results

        Args:
            query_embedding: 512-dim text embedding from user query
            ownership_type: Filter by ownership (prywatna, publiczna, etc.)
            build_status: Filter by build status (zabudowana, niezabudowana)
            size_category: Filter by size categories
            gmina: Filter by city
            limit: Maximum results

        Returns:
            List of parcels ranked by vector similarity with graph filters applied
        """
        # Build optional MATCH clauses for graph constraints
        graph_matches = []
        where_conditions = []
        params = {
            "embedding": query_embedding,
            "vector_limit": limit * 3,  # Fetch more candidates for filtering
            "limit": limit
        }

        if ownership_type:
            graph_matches.append("MATCH (candidate)-[:HAS_OWNERSHIP]->(o:OwnershipType)")
            where_conditions.append("o.id = $ownership_type")
            params["ownership_type"] = ownership_type

        if build_status:
            graph_matches.append("MATCH (candidate)-[:HAS_BUILD_STATUS]->(bs:BuildStatus)")
            where_conditions.append("bs.id = $build_status")
            params["build_status"] = build_status

        if size_category:
            graph_matches.append("MATCH (candidate)-[:HAS_SIZE]->(sz:SizeCategory)")
            where_conditions.append("sz.id IN $size_categories")
            params["size_categories"] = size_category

        if gmina:
            where_conditions.append("candidate.gmina = $gmina")
            params["gmina"] = gmina

        graph_match_clause = "\n".join(graph_matches) if graph_matches else ""
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        query = f"""
        // Step 1: Vector search for semantic similarity
        CALL db.index.vector.queryNodes('parcel_text_embedding_idx', $vector_limit, $embedding)
        YIELD node AS candidate, score AS vector_score

        // Step 2: Graph constraints
        {graph_match_clause}
        MATCH (candidate)-[:LOCATED_IN]->(d:District)
        {where_clause}

        // Step 3: Return with context
        OPTIONAL MATCH (candidate)-[r:NEAR_SCHOOL]->(s:School)
        WITH candidate, d, vector_score,
             COUNT(DISTINCT s) AS schools_nearby,
             MIN(r.distance_m) AS nearest_school_m

        RETURN
            candidate.id_dzialki AS id,
            candidate.dzielnica AS dzielnica,
            d.name AS district_name,
            candidate.gmina AS gmina,
            candidate.area_m2 AS area_m2,
            candidate.quietness_score AS quietness_score,
            candidate.nature_score AS nature_score,
            candidate.accessibility_score AS accessibility_score,
            candidate.is_built AS is_built,
            candidate.centroid_lat AS lat,
            candidate.centroid_lon AS lon,
            vector_score,
            schools_nearby,
            nearest_school_m
        ORDER BY vector_score DESC
        LIMIT $limit
        """

        try:
            results = await neo4j.run(query, params)
            return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"GraphRAG search error: {e}")
            return []


# Global instance
graph_service = GraphService()
