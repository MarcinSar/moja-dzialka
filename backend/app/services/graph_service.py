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
    has_road_access: Optional[bool] = None

    # Nature proximity
    max_dist_to_forest_m: Optional[int] = None
    max_dist_to_water_m: Optional[int] = None
    min_forest_pct_500m: Optional[float] = None  # e.g., 0.2 = 20% forest in 500m buffer

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


# Global instance
graph_service = GraphService()
