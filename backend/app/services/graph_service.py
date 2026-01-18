"""
Graph service using Neo4j.

Handles knowledge graph queries for:
- Administrative hierarchy
- MPZP zoning relationships
- Neighborhood exploration
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from loguru import logger

from app.services.database import neo4j


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


# Global instance
graph_service = GraphService()
