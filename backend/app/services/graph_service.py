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
        Get information about a gmina including statistics.

        Args:
            gmina_name: Name of the gmina

        Returns:
            GminaInfo or None
        """
        query = """
            MATCH (g:Gmina {name: $gmina})
            OPTIONAL MATCH (g)-[:W_POWIECIE]->(p:Powiat)
            OPTIONAL MATCH (d:Dzialka)-[:W_GMINIE]->(g)
            WITH g, p.name as powiat, collect(d) as dzialki
            RETURN
                g.name as name,
                powiat,
                size(dzialki) as parcel_count,
                CASE WHEN size(dzialki) > 0
                    THEN reduce(s = 0.0, d IN dzialki | s + coalesce(d.area_m2, 0.0)) / size(dzialki)
                    ELSE null END as avg_area,
                CASE WHEN size(dzialki) > 0
                    THEN toFloat(size([d IN dzialki WHERE d.has_mpzp = true])) / size(dzialki) * 100
                    ELSE null END as pct_with_mpzp
        """

        try:
            results = await neo4j.run(query, {"gmina": gmina_name})
            if results:
                r = results[0]
                return GminaInfo(
                    name=r["name"],
                    powiat=r.get("powiat"),
                    parcel_count=r.get("parcel_count", 0),
                    avg_area=r.get("avg_area"),
                    pct_with_mpzp=r.get("pct_with_mpzp"),
                )
            return None
        except Exception as e:
            logger.error(f"Get gmina info error: {e}")
            return None

    async def get_all_gminy(self) -> List[str]:
        """Get list of all gminy names."""
        query = """
            MATCH (g:Gmina)
            RETURN g.name as name
            ORDER BY g.name
        """
        try:
            results = await neo4j.run(query)
            return [r["name"] for r in results]
        except Exception as e:
            logger.error(f"Get all gminy error: {e}")
            return []

    async def get_miejscowosci_in_gmina(self, gmina_name: str) -> List[Dict[str, Any]]:
        """Get all miejscowosci (localities) in a gmina."""
        query = """
            MATCH (m:Miejscowosc)-[:W_GMINIE]->(g:Gmina {name: $gmina})
            OPTIONAL MATCH (d:Dzialka)-[:W_MIEJSCOWOSCI]->(m)
            WITH m, count(d) as parcel_count
            RETURN
                m.name as name,
                m.rodzaj as rodzaj,
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
        """Get all MPZP zoning symbols with statistics."""
        query = """
            MATCH (s:SymbolMPZP)
            OPTIONAL MATCH (d:Dzialka)-[:MA_PRZEZNACZENIE]->(s)
            WITH s, count(d) as parcel_count
            RETURN
                s.kod as symbol,
                s.nazwa as nazwa,
                s.budowlany as budowlany,
                parcel_count
            ORDER BY parcel_count DESC
        """
        try:
            results = await neo4j.run(query)
            return [
                MPZPInfo(
                    symbol=r["symbol"],
                    nazwa=r["nazwa"],
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

        Includes administrative hierarchy, MPZP info, and neighborhood.
        """
        query = """
            MATCH (d:Dzialka {id_dzialki: $parcel_id})
            OPTIONAL MATCH (d)-[:W_GMINIE]->(g:Gmina)
            OPTIONAL MATCH (d)-[:W_MIEJSCOWOSCI]->(m:Miejscowosc)
            OPTIONAL MATCH (d)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)
            OPTIONAL MATCH (g)-[:W_POWIECIE]->(p:Powiat)
            RETURN
                d.id_dzialki as id,
                d.area_m2 as area_m2,
                d.quietness_score as quietness,
                d.nature_score as nature,
                d.accessibility_score as accessibility,
                d.has_mpzp as has_mpzp,
                g.name as gmina,
                m.name as miejscowosc,
                p.name as powiat,
                s.kod as mpzp_symbol,
                s.nazwa as mpzp_nazwa,
                s.budowlany as mpzp_budowlany
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
        Find parcels with specific MPZP zoning.

        Args:
            symbol: MPZP symbol (e.g., "MN", "U")
            gmina: Optional gmina filter
            limit: Max results

        Returns:
            List of parcel dictionaries
        """
        if gmina:
            query = """
                MATCH (d:Dzialka)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP {kod: $symbol})
                WHERE d.gmina = $gmina
                RETURN
                    d.id_dzialki as id,
                    d.area_m2 as area_m2,
                    d.gmina as gmina,
                    d.quietness_score as quietness,
                    d.centroid_lat as lat,
                    d.centroid_lon as lon
                ORDER BY d.quietness_score DESC
                LIMIT $limit
            """
            params = {"symbol": symbol, "gmina": gmina, "limit": limit}
        else:
            query = """
                MATCH (d:Dzialka)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP {kod: $symbol})
                RETURN
                    d.id_dzialki as id,
                    d.area_m2 as area_m2,
                    d.gmina as gmina,
                    d.quietness_score as quietness,
                    d.centroid_lat as lat,
                    d.centroid_lon as lon
                ORDER BY d.quietness_score DESC
                LIMIT $limit
            """
            params = {"symbol": symbol, "limit": limit}

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
        Find parcels with buildable MPZP zoning.

        Args:
            gmina: Optional gmina filter
            min_area: Minimum area
            max_area: Maximum area
            limit: Max results

        Returns:
            List of parcel dictionaries
        """
        conditions = ["s.budowlany = true"]
        params = {"limit": limit}

        if gmina:
            conditions.append("d.gmina = $gmina")
            params["gmina"] = gmina

        if min_area:
            conditions.append("d.area_m2 >= $min_area")
            params["min_area"] = min_area

        if max_area:
            conditions.append("d.area_m2 <= $max_area")
            params["max_area"] = max_area

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (d:Dzialka)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)
            WHERE {where_clause}
            RETURN
                d.id_dzialki as id,
                d.area_m2 as area_m2,
                d.gmina as gmina,
                d.miejscowosc as miejscowosc,
                d.quietness_score as quietness,
                d.nature_score as nature,
                s.kod as mpzp_symbol,
                d.centroid_lat as lat,
                d.centroid_lon as lon
            ORDER BY d.quietness_score DESC
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
        Get full administrative hierarchy tree.

        Returns nested structure: Wojewodztwo -> Powiaty -> Gminy
        """
        query = """
            MATCH (w:Wojewodztwo)<-[:W_WOJEWODZTWIE]-(p:Powiat)<-[:W_POWIECIE]-(g:Gmina)
            WITH w, p, collect(g.name) as gminy
            WITH w, collect({powiat: p.name, gminy: gminy}) as powiaty
            RETURN w.name as wojewodztwo, powiaty
        """
        try:
            results = await neo4j.run(query)
            if results:
                return dict(results[0])
            return {}
        except Exception as e:
            logger.error(f"Get administrative tree error: {e}")
            return {}

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        query = """
            MATCH (d:Dzialka) WITH count(d) as dzialki
            MATCH (g:Gmina) WITH dzialki, count(g) as gminy
            MATCH (m:Miejscowosc) WITH dzialki, gminy, count(m) as miejscowosci
            MATCH (s:SymbolMPZP) WITH dzialki, gminy, miejscowosci, count(s) as symbole
            RETURN dzialki, gminy, miejscowosci, symbole
        """
        try:
            results = await neo4j.run(query)
            if results:
                return dict(results[0])
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

        This should be the main source of truth for finding parcels.
        Uses rich relationships to filter by all available criteria.

        Args:
            criteria: ParcelSearchCriteria with all search dimensions

        Returns:
            List of parcel dictionaries with full details
        """
        # Build dynamic Cypher query based on criteria
        match_clauses = ["MATCH (d:Dzialka)"]
        where_conditions = []
        params = {"limit": criteria.limit}

        # Location filters
        if criteria.gmina:
            match_clauses.append("MATCH (d)-[:W_GMINIE]->(g:Gmina {name: $gmina})")
            params["gmina"] = criteria.gmina

        if criteria.miejscowosc:
            match_clauses.append("MATCH (d)-[:W_MIEJSCOWOSCI]->(m:Miejscowosc {name: $miejscowosc})")
            params["miejscowosc"] = criteria.miejscowosc

        if criteria.powiat:
            match_clauses.append("""
                MATCH (d)-[:W_GMINIE]->(g:Gmina)-[:W_POWIECIE]->(p:Powiat {name: $powiat})
            """)
            params["powiat"] = criteria.powiat

        # Area filters (direct property or via category relationship)
        if criteria.min_area_m2:
            where_conditions.append("d.area_m2 >= $min_area")
            params["min_area"] = criteria.min_area_m2

        if criteria.max_area_m2:
            where_conditions.append("d.area_m2 <= $max_area")
            params["max_area"] = criteria.max_area_m2

        if criteria.area_category:
            match_clauses.append("MATCH (d)-[:MA_POWIERZCHNIE]->(ap:KategoriaPowierzchni)")
            where_conditions.append("ap.name IN $area_categories")
            params["area_categories"] = criteria.area_category

        # Character & Environment filters (via relationships)
        if criteria.charakter_terenu:
            match_clauses.append("MATCH (d)-[:MA_CHARAKTER]->(ch:CharakterTerenu)")
            where_conditions.append("ch.name IN $charakter")
            params["charakter"] = criteria.charakter_terenu

        if criteria.quietness_categories:
            match_clauses.append("MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)")
            where_conditions.append("c.name IN $quietness_cats")
            params["quietness_cats"] = criteria.quietness_categories

        if criteria.nature_categories:
            match_clauses.append("MATCH (d)-[:MA_NATURE]->(n:KategoriaNatury)")
            where_conditions.append("n.name IN $nature_cats")
            params["nature_cats"] = criteria.nature_categories

        if criteria.building_density:
            match_clauses.append("MATCH (d)-[:MA_ZABUDOWE]->(z:GestoscZabudowy)")
            where_conditions.append("z.name IN $density")
            params["density"] = criteria.building_density

        # Accessibility filters
        if criteria.accessibility_categories:
            match_clauses.append("MATCH (d)-[:MA_DOSTEP]->(acc:KategoriaDostepu)")
            where_conditions.append("acc.name IN $access_cats")
            params["access_cats"] = criteria.accessibility_categories

        if criteria.has_road_access is not None:
            where_conditions.append("d.has_public_road_access = $has_road")
            params["has_road"] = criteria.has_road_access

        # POI proximity filters (using relationship properties)
        if criteria.max_dist_to_school_m:
            match_clauses.append("""
                MATCH (d)-[rs:BLISKO_SZKOLY]->(poi_school:POIType {name: 'school'})
            """)
            where_conditions.append("rs.distance_m <= $max_school_dist")
            params["max_school_dist"] = criteria.max_dist_to_school_m

        if criteria.max_dist_to_shop_m:
            match_clauses.append("""
                MATCH (d)-[rsh:BLISKO_SKLEPU]->(poi_shop:POIType {name: 'shop'})
            """)
            where_conditions.append("rsh.distance_m <= $max_shop_dist")
            params["max_shop_dist"] = criteria.max_dist_to_shop_m

        if criteria.max_dist_to_bus_stop_m:
            match_clauses.append("""
                MATCH (d)-[rb:BLISKO_PRZYSTANKU]->(poi_bus:POIType {name: 'bus_stop'})
            """)
            where_conditions.append("rb.distance_m <= $max_bus_dist")
            params["max_bus_dist"] = criteria.max_dist_to_bus_stop_m

        if criteria.max_dist_to_hospital_m:
            match_clauses.append("""
                MATCH (d)-[rh:BLISKO_SZPITALA]->(poi_hosp:POIType {name: 'hospital'})
            """)
            where_conditions.append("rh.distance_m <= $max_hospital_dist")
            params["max_hospital_dist"] = criteria.max_dist_to_hospital_m

        # Nature proximity filters
        if criteria.max_dist_to_forest_m:
            match_clauses.append("""
                MATCH (d)-[rf:BLISKO_LASU]->(lc_forest:LandCoverType {name: 'forest'})
            """)
            where_conditions.append("rf.distance_m <= $max_forest_dist")
            params["max_forest_dist"] = criteria.max_dist_to_forest_m

        if criteria.max_dist_to_water_m:
            match_clauses.append("""
                MATCH (d)-[rw:BLISKO_WODY]->(lc_water:LandCoverType {name: 'water'})
            """)
            where_conditions.append("rw.distance_m <= $max_water_dist")
            params["max_water_dist"] = criteria.max_dist_to_water_m

        if criteria.min_forest_pct_500m:
            where_conditions.append("d.pct_forest_500m >= $min_forest_pct")
            params["min_forest_pct"] = criteria.min_forest_pct_500m

        # Industrial distance (for quiet areas - want to be FAR from industrial)
        if criteria.min_dist_to_industrial_m:
            match_clauses.append("""
                MATCH (d)-[ri:BLISKO_PRZEMYSLU]->(poi_ind:POIType {name: 'industrial'})
            """)
            where_conditions.append("ri.distance_m >= $min_industrial_dist")
            params["min_industrial_dist"] = criteria.min_dist_to_industrial_m

        # MPZP filters
        if criteria.has_mpzp is not None:
            where_conditions.append("d.has_mpzp = $has_mpzp")
            params["has_mpzp"] = criteria.has_mpzp

        # Only check buildable if we're not explicitly filtering out MPZP
        if criteria.mpzp_buildable and criteria.has_mpzp is not False:
            match_clauses.append("MATCH (d)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)")
            where_conditions.append("s.budowlany = true")

        if criteria.mpzp_symbols:
            if "MATCH (d)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)" not in "\n".join(match_clauses):
                match_clauses.append("MATCH (d)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)")
            where_conditions.append("s.kod IN $mpzp_symbols")
            params["mpzp_symbols"] = criteria.mpzp_symbols

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Sorting
        sort_field = f"d.{criteria.sort_by}" if criteria.sort_by else "d.quietness_score"
        sort_dir = "DESC" if criteria.sort_desc else "ASC"

        # Build full query
        query = f"""
            {chr(10).join(match_clauses)}
            {where_clause}
            RETURN DISTINCT
                d.id_dzialki as id,
                d.gmina as gmina,
                d.miejscowosc as miejscowosc,
                d.area_m2 as area_m2,
                d.quietness_score as quietness_score,
                d.nature_score as nature_score,
                d.accessibility_score as accessibility_score,
                d.has_mpzp as has_mpzp,
                d.mpzp_symbol as mpzp_symbol,
                d.centroid_lat as lat,
                d.centroid_lon as lon,
                d.dist_to_forest as dist_to_forest,
                d.dist_to_water as dist_to_water,
                d.dist_to_school as dist_to_school,
                d.dist_to_shop as dist_to_shop,
                d.dist_to_bus_stop as dist_to_bus_stop,
                d.pct_forest_500m as pct_forest_500m,
                d.count_buildings_500m as count_buildings_500m,
                d.has_public_road_access as has_road_access
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

        Returns statistics and available options for each dimension.
        """
        query = """
            // Count parcels by quietness category
            MATCH (d:Dzialka)-[:MA_CISZE]->(c:KategoriaCiszy)
            WITH c.name as category, count(d) as count
            WITH collect({category: category, count: count}) as quietness_stats

            // Count parcels by nature category
            MATCH (d:Dzialka)-[:MA_NATURE]->(n:KategoriaNatury)
            WITH quietness_stats, n.name as category, count(d) as count
            WITH quietness_stats, collect({category: category, count: count}) as nature_stats

            // Count parcels by character
            MATCH (d:Dzialka)-[:MA_CHARAKTER]->(ch:CharakterTerenu)
            WITH quietness_stats, nature_stats, ch.name as category, count(d) as count
            WITH quietness_stats, nature_stats, collect({category: category, count: count}) as charakter_stats

            // Count by gmina
            MATCH (d:Dzialka)-[:W_GMINIE]->(g:Gmina)
            WITH quietness_stats, nature_stats, charakter_stats, g.name as gmina, count(d) as count
            WITH quietness_stats, nature_stats, charakter_stats, collect({gmina: gmina, count: count}) as gmina_stats

            // MPZP stats
            MATCH (d:Dzialka)
            WITH quietness_stats, nature_stats, charakter_stats, gmina_stats,
                 sum(CASE WHEN d.has_mpzp = true THEN 1 ELSE 0 END) as with_mpzp,
                 count(d) as total

            RETURN
                quietness_stats,
                nature_stats,
                charakter_stats,
                gmina_stats,
                with_mpzp,
                total
        """

        try:
            results = await neo4j.run(query)
            if results:
                r = results[0]
                return {
                    "total_parcels": r.get("total", 0),
                    "with_mpzp": r.get("with_mpzp", 0),
                    "quietness_distribution": r.get("quietness_stats", []),
                    "nature_distribution": r.get("nature_stats", []),
                    "character_distribution": r.get("charakter_stats", []),
                    "gmina_distribution": r.get("gmina_stats", []),
                    "available_categories": {
                        "quietness": KATEGORIE_CISZY,
                        "nature": KATEGORIE_NATURY,
                        "accessibility": KATEGORIE_DOSTEPU,
                        "area": KATEGORIE_POWIERZCHNI,
                        "density": GESTOSC_ZABUDOWY,
                        "character": CHARAKTER_TERENU,
                    },
                    "mpzp_info": {
                        "buildable_symbols": MPZP_BUDOWLANE,
                        "non_buildable_symbols": MPZP_NIEBUDOWLANE,
                    }
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

        Args:
            level: "wojewodztwo" → returns powiaty
                   "powiat" → returns gminy in powiat
                   "gmina" → returns miejscowości in gmina
            parent_name: Optional name of parent unit (required for powiat/gmina level)

        Returns:
            List of children with counts
        """
        try:
            if level == "wojewodztwo":
                # Return all powiaty in pomorskie
                query = """
                    MATCH (p:Powiat)-[:W_WOJEWODZTWIE]->(w:Wojewodztwo)
                    OPTIONAL MATCH (g:Gmina)-[:W_POWIECIE]->(p)
                    OPTIONAL MATCH (d:Dzialka)-[:W_GMINIE]->(g)
                    WITH p, count(DISTINCT g) as gminy_count, count(DISTINCT d) as parcel_count
                    RETURN
                        p.name as name,
                        gminy_count,
                        parcel_count
                    ORDER BY p.name
                """
                results = await neo4j.run(query)
                return [dict(r) for r in results]

            elif level == "powiat" and parent_name:
                # Return gminy in given powiat
                query = """
                    MATCH (g:Gmina)-[:W_POWIECIE]->(p:Powiat {name: $parent})
                    OPTIONAL MATCH (d:Dzialka)-[:W_GMINIE]->(g)
                    WITH g, count(d) as parcel_count
                    RETURN
                        g.name as name,
                        parcel_count
                    ORDER BY g.name
                """
                results = await neo4j.run(query, {"parent": parent_name})
                return [dict(r) for r in results]

            elif level == "gmina" and parent_name:
                # Return miejscowości in given gmina
                query = """
                    MATCH (m:Miejscowosc)-[:W_GMINIE]->(g:Gmina {name: $parent})
                    OPTIONAL MATCH (d:Dzialka)-[:W_MIEJSCOWOSCI]->(m)
                    OPTIONAL MATCH (m)-[:MA_RODZAJ]->(r:RodzajMiejscowosci)
                    WITH m, r, count(d) as parcel_count
                    RETURN
                        m.name as name,
                        r.name as rodzaj,
                        parcel_count
                    ORDER BY parcel_count DESC, m.name
                """
                results = await neo4j.run(query, {"parent": parent_name})
                return [dict(r) for r in results]

            else:
                return []

        except Exception as e:
            logger.error(f"Get children in hierarchy error: {e}")
            return []

    async def get_all_powiaty(self) -> List[str]:
        """Get list of all powiat names."""
        query = """
            MATCH (p:Powiat)
            RETURN p.name as name
            ORDER BY p.name
        """
        try:
            results = await neo4j.run(query)
            return [r["name"] for r in results]
        except Exception as e:
            logger.error(f"Get all powiaty error: {e}")
            return []

    async def get_area_category_stats(
        self,
        gmina: Optional[str] = None,
        powiat: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get distribution of parcels by category in given area.

        Returns counts for: quietness, nature, accessibility, MPZP, etc.

        Args:
            gmina: Optional gmina filter
            powiat: Optional powiat filter

        Returns:
            Dictionary with category distributions
        """
        # Build location filter
        location_filter = ""
        params = {}

        if gmina:
            location_filter = "MATCH (d)-[:W_GMINIE]->(g:Gmina {name: $gmina})"
            params["gmina"] = gmina
        elif powiat:
            location_filter = """
                MATCH (d)-[:W_GMINIE]->(g:Gmina)-[:W_POWIECIE]->(p:Powiat {name: $powiat})
            """
            params["powiat"] = powiat

        # Complex query to get all category distributions
        query = f"""
            MATCH (d:Dzialka)
            {location_filter}
            WITH d

            // Total count
            WITH count(d) as total, collect(d) as all_parcels

            // Quietness distribution
            UNWIND all_parcels as d1
            OPTIONAL MATCH (d1)-[:MA_CISZE]->(c:KategoriaCiszy)
            WITH total, all_parcels, c.name as cisza_cat, count(d1) as cisza_count
            WITH total, all_parcels, collect({{category: cisza_cat, count: cisza_count}}) as quietness_stats

            // Nature distribution
            UNWIND all_parcels as d2
            OPTIONAL MATCH (d2)-[:MA_NATURE]->(n:KategoriaNatury)
            WITH total, all_parcels, quietness_stats, n.name as natura_cat, count(d2) as natura_count
            WITH total, all_parcels, quietness_stats, collect({{category: natura_cat, count: natura_count}}) as nature_stats

            // Character distribution
            UNWIND all_parcels as d3
            OPTIONAL MATCH (d3)-[:MA_CHARAKTER]->(ch:CharakterTerenu)
            WITH total, all_parcels, quietness_stats, nature_stats, ch.name as char_cat, count(d3) as char_count
            WITH total, all_parcels, quietness_stats, nature_stats, collect({{category: char_cat, count: char_count}}) as character_stats

            // MPZP stats
            UNWIND all_parcels as d4
            WITH total, quietness_stats, nature_stats, character_stats,
                 sum(CASE WHEN d4.has_mpzp = true THEN 1 ELSE 0 END) as with_mpzp,
                 sum(CASE WHEN d4.has_public_road_access = true THEN 1 ELSE 0 END) as with_road_access

            RETURN
                total,
                with_mpzp,
                with_road_access,
                quietness_stats,
                nature_stats,
                character_stats
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
                    "with_road_access": with_road,
                    "pct_road_access": round((with_road / total * 100), 1) if total > 0 else 0,
                    "quietness_distribution": r.get("quietness_stats", []),
                    "nature_distribution": r.get("nature_stats", []),
                    "character_distribution": r.get("character_stats", []),
                    "location_filter": {"gmina": gmina, "powiat": powiat},
                }
            return {"error": "No data found"}
        except Exception as e:
            logger.error(f"Get area category stats error: {e}")
            return {"error": str(e)}

    async def get_parcel_neighborhood(self, parcel_id: str) -> Dict[str, Any]:
        """
        Get detailed neighborhood context for a parcel.

        Returns all POI distances, land cover percentages, and character.

        Args:
            parcel_id: ID of the parcel

        Returns:
            Dictionary with full neighborhood context
        """
        query = """
            MATCH (d:Dzialka {id_dzialki: $parcel_id})

            // Basic info
            OPTIONAL MATCH (d)-[:W_GMINIE]->(g:Gmina)
            OPTIONAL MATCH (d)-[:W_MIEJSCOWOSCI]->(m:Miejscowosc)
            OPTIONAL MATCH (g)-[:W_POWIECIE]->(p:Powiat)
            OPTIONAL MATCH (d)-[:MA_PRZEZNACZENIE]->(s:SymbolMPZP)
            OPTIONAL MATCH (d)-[:MA_CHARAKTER]->(ch:CharakterTerenu)
            OPTIONAL MATCH (d)-[:MA_CISZE]->(ci:KategoriaCiszy)
            OPTIONAL MATCH (d)-[:MA_NATURE]->(na:KategoriaNatury)
            OPTIONAL MATCH (d)-[:MA_DOSTEP]->(ac:KategoriaDostepu)
            OPTIONAL MATCH (d)-[:MA_ZABUDOWE]->(za:GestoscZabudowy)

            // POI distances
            OPTIONAL MATCH (d)-[rs:BLISKO_SZKOLY]->(:POIType {name: 'school'})
            OPTIONAL MATCH (d)-[rsh:BLISKO_SKLEPU]->(:POIType {name: 'shop'})
            OPTIONAL MATCH (d)-[rh:BLISKO_SZPITALA]->(:POIType {name: 'hospital'})
            OPTIONAL MATCH (d)-[rb:BLISKO_PRZYSTANKU]->(:POIType {name: 'bus_stop'})
            OPTIONAL MATCH (d)-[ri:BLISKO_PRZEMYSLU]->(:POIType {name: 'industrial'})

            // Nature distances
            OPTIONAL MATCH (d)-[rf:BLISKO_LASU]->(:LandCoverType {name: 'forest'})
            OPTIONAL MATCH (d)-[rw:BLISKO_WODY]->(:LandCoverType {name: 'water'})

            RETURN
                d.id_dzialki as id,
                d.area_m2 as area_m2,
                d.centroid_lat as lat,
                d.centroid_lon as lon,

                // Location
                g.name as gmina,
                m.name as miejscowosc,
                p.name as powiat,

                // Categories
                ch.name as charakter_terenu,
                ci.name as kategoria_ciszy,
                na.name as kategoria_natury,
                ac.name as kategoria_dostepu,
                za.name as gestosc_zabudowy,

                // Scores
                d.quietness_score as quietness_score,
                d.nature_score as nature_score,
                d.accessibility_score as accessibility_score,

                // MPZP
                d.has_mpzp as has_mpzp,
                s.kod as mpzp_symbol,
                s.nazwa as mpzp_nazwa,
                s.budowlany as mpzp_budowlany,

                // POI distances
                rs.distance_m as dist_to_school,
                rsh.distance_m as dist_to_shop,
                rh.distance_m as dist_to_hospital,
                rb.distance_m as dist_to_bus_stop,
                ri.distance_m as dist_to_industrial,

                // Nature distances
                rf.distance_m as dist_to_forest,
                rw.distance_m as dist_to_water,

                // Buffer analysis
                d.pct_forest_500m as pct_forest_500m,
                d.pct_water_500m as pct_water_500m,
                d.count_buildings_500m as count_buildings_500m,

                // Road access
                d.has_public_road_access as has_road_access
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                r = dict(results[0])

                # Build human-readable summary
                summary = []

                # Location
                if r.get("miejscowosc"):
                    summary.append(f"Lokalizacja: {r['miejscowosc']}, gm. {r.get('gmina', '')}")
                elif r.get("gmina"):
                    summary.append(f"Lokalizacja: {r['gmina']}")

                # Character
                if r.get("charakter_terenu"):
                    summary.append(f"Charakter: {r['charakter_terenu']}")

                # Quietness
                if r.get("quietness_score"):
                    summary.append(f"Cisza: {int(r['quietness_score'])}/100 ({r.get('kategoria_ciszy', '')})")

                # Nature
                if r.get("nature_score"):
                    summary.append(f"Natura: {int(r['nature_score'])}/100 ({r.get('kategoria_natury', '')})")

                # Accessibility
                if r.get("accessibility_score"):
                    summary.append(f"Dostępność: {int(r['accessibility_score'])}/100 ({r.get('kategoria_dostepu', '')})")

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
                p.nearest_water_type as nearest_water_type,

                // Proximity flags
                p.near_morze as near_sea,
                p.near_jezioro as near_lake,
                p.near_rzeka as near_river
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

        Combines neighborhood, water, pricing, and POG information.

        Args:
            parcel_id: ID of the parcel

        Returns:
            Comprehensive parcel context for agent
        """
        query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})

            // Get category relations
            OPTIONAL MATCH (p)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
            OPTIONAL MATCH (p)-[:HAS_NATURE]->(nc:NatureCategory)
            OPTIONAL MATCH (p)-[:HAS_ACCESS]->(ac:AccessCategory)
            OPTIONAL MATCH (p)-[:HAS_DENSITY]->(dc:DensityCategory)
            OPTIONAL MATCH (p)-[:NEAREST_WATER_TYPE]->(wt:WaterType)
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)
            OPTIONAL MATCH (d)-[:IN_PRICE_SEGMENT]->(ps:PriceSegment)

            RETURN
                // Basic info
                p.id_dzialki as id_dzialki,
                p.gmina as gmina,
                p.dzielnica as dzielnica,
                p.area_m2 as area_m2,
                p.centroid_lat as lat,
                p.centroid_lon as lon,

                // Categories
                qc.id as kategoria_ciszy,
                qc.name_pl as kategoria_ciszy_pl,
                nc.id as kategoria_natury,
                nc.name_pl as kategoria_natury_pl,
                ac.id as kategoria_dostepu,
                ac.name_pl as kategoria_dostepu_pl,
                dc.id as gestosc_zabudowy,
                dc.name_pl as gestosc_zabudowy_pl,

                // Scores
                p.quietness_score as quietness_score,
                p.nature_score as nature_score,
                p.accessibility_score as accessibility_score,

                // Building info
                p.is_built as is_built,
                p.building_count as building_count,
                p.building_type as building_type,
                p.building_coverage_pct as building_coverage_pct,

                // POG (zoning)
                p.pog_symbol as pog_symbol,
                p.pog_nazwa as pog_nazwa,
                p.pog_profil_podstawowy as pog_profil,
                p.pog_maks_wysokosc_m as pog_max_wysokosc,
                p.pog_maks_zabudowa_pct as pog_max_zabudowa,
                p.is_residential_zone as is_residential_zone,

                // Water info
                p.nearest_water_type as nearest_water_type,
                wt.name_pl as nearest_water_type_pl,
                wt.premium_factor as water_premium_factor,
                p.dist_to_sea as dist_to_sea,
                p.dist_to_lake as dist_to_lake,
                p.dist_to_river as dist_to_river,
                p.dist_to_water as dist_to_water,

                // Distances
                p.dist_to_school as dist_to_school,
                p.dist_to_bus_stop as dist_to_bus_stop,
                p.dist_to_forest as dist_to_forest,
                p.dist_to_supermarket as dist_to_supermarket,
                p.dist_to_main_road as dist_to_main_road,

                // Context
                p.pct_forest_500m as pct_forest_500m,
                p.count_buildings_500m as count_buildings_500m,

                // Pricing
                p.price_segment as price_segment,
                ps.name_pl as price_segment_pl,
                ps.price_min as price_min,
                ps.price_max as price_max
        """

        try:
            results = await neo4j.run(query, {"parcel_id": parcel_id})
            if results:
                r = dict(results[0])

                # Build comprehensive summary
                summary = {
                    "lokalizacja": f"{r.get('dzielnica', '')}, {r.get('gmina', '')}",
                    "powierzchnia": f"{r.get('area_m2', 0):,.0f} m²",
                    "zabudowana": "Tak" if r.get("is_built") else "Nie",
                    "strefa_mieszkaniowa": "Tak" if r.get("is_residential_zone") else "Nie",
                    "cisza": f"{r.get('quietness_score', 0)}/100 ({r.get('kategoria_ciszy_pl', '')})",
                    "natura": f"{r.get('nature_score', 0)}/100 ({r.get('kategoria_natury_pl', '')})",
                    "dostepnosc": f"{r.get('accessibility_score', 0)}/100 ({r.get('kategoria_dostepu_pl', '')})",
                }

                # Water summary
                if r.get("nearest_water_type"):
                    water_dist = r.get(f"dist_to_{r['nearest_water_type']}", r.get("dist_to_water"))
                    summary["najblizsa_woda"] = f"{r.get('nearest_water_type_pl', '')} ({water_dist}m)"

                # Price estimate
                if r.get("price_min") and r.get("price_max"):
                    area = r.get("area_m2", 0)
                    est_min = area * r["price_min"]
                    est_max = area * r["price_max"]
                    summary["szacunkowa_wartosc"] = f"{est_min/1000:.0f}k - {est_max/1000:.0f}k PLN"
                    summary["segment_cenowy"] = r.get("price_segment_pl", "")

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
