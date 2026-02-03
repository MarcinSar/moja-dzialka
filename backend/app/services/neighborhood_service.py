"""
Neighborhood Analysis Service - Comprehensive neighborhood assessment.

Provides detailed analysis of a parcel's neighborhood including:
- Character assessment (urban, suburban, rural)
- Safety indicators
- Community profile
- Development trends
- Quality of life metrics
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class NeighborhoodCharacter(str, Enum):
    """Classification of neighborhood character."""
    URBAN = "urban"              # Dense, city-like
    SUBURBAN = "suburban"        # Mixed, residential
    RURAL = "rural"              # Sparse, countryside
    TRANSITIONAL = "transitional"  # Mixed/changing


@dataclass
class NeighborhoodProfile:
    """Comprehensive neighborhood profile."""

    # Basic info
    parcel_id: str
    district: str
    city: str

    # Character
    character: NeighborhoodCharacter
    character_score: float  # 0-1, 1 = very urban

    # Density metrics
    building_density: float  # buildings per hectare
    residential_pct: float   # % residential buildings
    green_space_pct: float   # % green space in 500m

    # Accessibility
    transport_score: float   # 0-100
    amenities_score: float   # 0-100

    # Environment
    quietness_score: float   # 0-100
    nature_score: float      # 0-100
    air_quality: Optional[str]  # good/moderate/poor

    # Community
    avg_parcel_size: float   # m²
    building_age_category: str  # new/mixed/old
    property_type: str       # jednorodzinne/wielorodzinne/mixed

    # Neighbors
    adjacent_count: int
    nearby_poi: List[Dict[str, Any]]

    # Summary
    strengths: List[str]
    weaknesses: List[str]
    ideal_for: List[str]


class NeighborhoodService:
    """Service for comprehensive neighborhood analysis."""

    def __init__(self, graph_service=None):
        """Initialize service.

        Args:
            graph_service: Neo4j graph service (optional, will import if needed)
        """
        self._graph_service = graph_service

    @property
    def graph_service(self):
        """Lazy load graph service."""
        if self._graph_service is None:
            from app.services.graph_service import GraphService
            self._graph_service = GraphService()
        return self._graph_service

    async def analyze_neighborhood(
        self,
        parcel_id: str,
        radius_m: int = 500,
    ) -> Dict[str, Any]:
        """Perform comprehensive neighborhood analysis.

        Args:
            parcel_id: ID of the parcel to analyze
            radius_m: Analysis radius in meters

        Returns:
            Comprehensive neighborhood analysis
        """
        logger.info(f"Analyzing neighborhood for parcel {parcel_id}")

        # Get parcel data
        parcel = await self._get_parcel_data(parcel_id)
        if not parcel:
            return {"error": f"Parcel {parcel_id} not found"}

        # Get neighborhood context
        neighborhood = await self._get_neighborhood_context(parcel_id, radius_m)

        # Get adjacent parcels
        adjacent = await self._get_adjacent_parcels(parcel_id)

        # Get nearby POI
        poi = await self._get_nearby_poi(parcel_id)

        # Build analysis
        analysis = self._build_analysis(parcel, neighborhood, adjacent, poi)

        return analysis

    async def _get_parcel_data(self, parcel_id: str) -> Optional[Dict[str, Any]]:
        """Get parcel data from Neo4j."""
        try:
            query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)
            OPTIONAL MATCH (d)-[:BELONGS_TO]->(c:City)
            RETURN p {
                .*,
                district: d.name,
                city: c.name
            } as parcel
            """
            result = await self.graph_service.run_query(query, {"parcel_id": parcel_id})
            if result:
                return result[0]["parcel"]
            return None
        except Exception as e:
            logger.error(f"Error getting parcel data: {e}")
            return None

    async def _get_neighborhood_context(
        self,
        parcel_id: str,
        radius_m: int,
    ) -> Dict[str, Any]:
        """Get neighborhood context from Neo4j."""
        try:
            query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})

            // Count nearby buildings
            OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)<-[:LOCATED_IN]-(neighbor:Parcel)
            WHERE neighbor.id_dzialki <> p.id_dzialki

            WITH p, d, collect(neighbor) as neighbors

            RETURN {
                parcel_count_in_district: size(neighbors),
                avg_area_m2: avg([n in neighbors | n.area_m2]),
                avg_quietness: avg([n in neighbors | n.quietness_score]),
                pct_built: toFloat(size([n in neighbors WHERE n.is_built])) / size(neighbors),
                pct_residential: toFloat(size([n in neighbors WHERE n.has_residential])) / size(neighbors)
            } as context
            """
            result = await self.graph_service.run_query(query, {"parcel_id": parcel_id})
            if result:
                return result[0]["context"]
            return {}
        except Exception as e:
            logger.error(f"Error getting neighborhood context: {e}")
            return {}

    async def _get_adjacent_parcels(self, parcel_id: str) -> List[Dict[str, Any]]:
        """Get adjacent parcels from Neo4j."""
        try:
            query = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})-[r:ADJACENT_TO]-(neighbor:Parcel)
            RETURN neighbor {
                .id_dzialki,
                .area_m2,
                .is_built,
                .typ_wlasnosci,
                shared_border_m: r.shared_border_m
            } as adjacent
            ORDER BY r.shared_border_m DESC
            LIMIT 10
            """
            result = await self.graph_service.run_query(query, {"parcel_id": parcel_id})
            return [r["adjacent"] for r in result]
        except Exception as e:
            logger.error(f"Error getting adjacent parcels: {e}")
            return []

    async def _get_nearby_poi(self, parcel_id: str) -> List[Dict[str, Any]]:
        """Get nearby POI from Neo4j."""
        try:
            poi_list = []

            # Schools
            query_schools = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})-[r:NEAR_SCHOOL]->(s:School)
            RETURN {type: 'school', name: s.name, distance_m: r.distance_m} as poi
            ORDER BY r.distance_m LIMIT 3
            """
            schools = await self.graph_service.run_query(query_schools, {"parcel_id": parcel_id})
            poi_list.extend([r["poi"] for r in schools])

            # Bus stops
            query_bus = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})-[r:NEAR_BUS_STOP]->(b:BusStop)
            RETURN {type: 'bus_stop', name: b.name, distance_m: r.distance_m} as poi
            ORDER BY r.distance_m LIMIT 3
            """
            bus = await self.graph_service.run_query(query_bus, {"parcel_id": parcel_id})
            poi_list.extend([r["poi"] for r in bus])

            # Shops
            query_shops = """
            MATCH (p:Parcel {id_dzialki: $parcel_id})-[r:NEAR_SHOP]->(sh:Shop)
            RETURN {type: 'shop', name: sh.name, distance_m: r.distance_m} as poi
            ORDER BY r.distance_m LIMIT 3
            """
            shops = await self.graph_service.run_query(query_shops, {"parcel_id": parcel_id})
            poi_list.extend([r["poi"] for r in shops])

            return poi_list
        except Exception as e:
            logger.error(f"Error getting nearby POI: {e}")
            return []

    def _build_analysis(
        self,
        parcel: Dict[str, Any],
        neighborhood: Dict[str, Any],
        adjacent: List[Dict[str, Any]],
        poi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build comprehensive neighborhood analysis."""

        # Determine character
        character = self._determine_character(parcel, neighborhood)

        # Calculate scores
        transport_score = self._calc_transport_score(poi, parcel)
        amenities_score = self._calc_amenities_score(poi, parcel)

        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(parcel, neighborhood, poi)

        # Determine ideal use cases
        ideal_for = self._determine_ideal_for(parcel, character, strengths)

        return {
            "parcel_id": parcel.get("id_dzialki"),
            "district": parcel.get("district", parcel.get("dzielnica")),
            "city": parcel.get("city", parcel.get("gmina")),

            "character": {
                "type": character.value,
                "description": self._character_description(character),
            },

            "density": {
                "building_pct": neighborhood.get("pct_built", 0) * 100,
                "residential_pct": neighborhood.get("pct_residential", 0) * 100,
                "avg_parcel_size_m2": neighborhood.get("avg_area_m2", 0),
            },

            "environment": {
                "quietness_score": parcel.get("quietness_score", 50),
                "nature_score": parcel.get("nature_score", 50),
                "accessibility_score": parcel.get("accessibility_score", 50),
            },

            "scores": {
                "transport": transport_score,
                "amenities": amenities_score,
                "overall_livability": (transport_score + amenities_score +
                                       parcel.get("quietness_score", 50)) / 3,
            },

            "neighbors": {
                "adjacent_count": len(adjacent),
                "adjacent_parcels": adjacent[:5],  # Top 5
                "nearby_poi_count": len(poi),
            },

            "poi": poi,

            "assessment": {
                "strengths": strengths,
                "weaknesses": weaknesses,
                "ideal_for": ideal_for,
            },

            "summary": self._generate_summary(parcel, character, strengths, weaknesses),
        }

    def _determine_character(
        self,
        parcel: Dict[str, Any],
        neighborhood: Dict[str, Any],
    ) -> NeighborhoodCharacter:
        """Determine neighborhood character."""
        pct_built = neighborhood.get("pct_built", 0)
        avg_quietness = neighborhood.get("avg_quietness", 50)

        if pct_built > 0.7:
            return NeighborhoodCharacter.URBAN
        elif pct_built > 0.4:
            return NeighborhoodCharacter.SUBURBAN
        elif pct_built > 0.2:
            return NeighborhoodCharacter.TRANSITIONAL
        else:
            return NeighborhoodCharacter.RURAL

    def _character_description(self, character: NeighborhoodCharacter) -> str:
        """Get character description."""
        descriptions = {
            NeighborhoodCharacter.URBAN: "Gęsta zabudowa miejska, typowy charakter osiedlowy",
            NeighborhoodCharacter.SUBURBAN: "Zabudowa podmiejska, głównie domy jednorodzinne",
            NeighborhoodCharacter.RURAL: "Rzadka zabudowa, charakter wiejski",
            NeighborhoodCharacter.TRANSITIONAL: "Okolica w trakcie rozwoju, mieszany charakter",
        }
        return descriptions.get(character, "Nieokreślony charakter")

    def _calc_transport_score(
        self,
        poi: List[Dict[str, Any]],
        parcel: Dict[str, Any],
    ) -> float:
        """Calculate transport accessibility score."""
        # Get bus stop distance
        bus_stops = [p for p in poi if p.get("type") == "bus_stop"]
        if bus_stops:
            min_bus_dist = min(b.get("distance_m", 9999) for b in bus_stops)
        else:
            min_bus_dist = parcel.get("dist_to_bus_stop", 1000)

        # Score based on distance
        if min_bus_dist < 200:
            return 95
        elif min_bus_dist < 500:
            return 80
        elif min_bus_dist < 800:
            return 60
        elif min_bus_dist < 1200:
            return 40
        else:
            return 20

    def _calc_amenities_score(
        self,
        poi: List[Dict[str, Any]],
        parcel: Dict[str, Any],
    ) -> float:
        """Calculate amenities score."""
        score = 50  # Base score

        # Shops
        shops = [p for p in poi if p.get("type") == "shop"]
        if shops:
            min_shop_dist = min(s.get("distance_m", 9999) for s in shops)
            if min_shop_dist < 500:
                score += 20
            elif min_shop_dist < 1000:
                score += 10

        # Schools
        schools = [p for p in poi if p.get("type") == "school"]
        if schools:
            min_school_dist = min(s.get("distance_m", 9999) for s in schools)
            if min_school_dist < 1000:
                score += 20
            elif min_school_dist < 2000:
                score += 10

        return min(score, 100)

    def _identify_strengths_weaknesses(
        self,
        parcel: Dict[str, Any],
        neighborhood: Dict[str, Any],
        poi: List[Dict[str, Any]],
    ) -> tuple[List[str], List[str]]:
        """Identify neighborhood strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # Quietness
        quietness = parcel.get("quietness_score", 50)
        if quietness > 80:
            strengths.append("Bardzo cicha okolica")
        elif quietness < 40:
            weaknesses.append("Głośna okolica")

        # Nature
        nature = parcel.get("nature_score", 50)
        if nature > 70:
            strengths.append("Blisko natury (las, woda)")
        elif nature < 30:
            weaknesses.append("Brak terenów zielonych w okolicy")

        # Schools
        schools = [p for p in poi if p.get("type") == "school"]
        if schools and min(s.get("distance_m", 9999) for s in schools) < 1000:
            strengths.append("Szkoła w pobliżu")
        elif not schools or min(s.get("distance_m", 9999) for s in schools) > 2000:
            weaknesses.append("Daleko do szkoły")

        # Transport
        bus_stops = [p for p in poi if p.get("type") == "bus_stop"]
        if bus_stops and min(b.get("distance_m", 9999) for b in bus_stops) < 500:
            strengths.append("Dobra komunikacja publiczna")
        elif not bus_stops or min(b.get("distance_m", 9999) for b in bus_stops) > 1000:
            weaknesses.append("Słaba komunikacja publiczna")

        # Shops
        shops = [p for p in poi if p.get("type") == "shop"]
        if shops and min(s.get("distance_m", 9999) for s in shops) < 500:
            strengths.append("Sklepy na miejscu")
        elif not shops or min(s.get("distance_m", 9999) for s in shops) > 1500:
            weaknesses.append("Brak sklepów w okolicy")

        return strengths, weaknesses

    def _determine_ideal_for(
        self,
        parcel: Dict[str, Any],
        character: NeighborhoodCharacter,
        strengths: List[str],
    ) -> List[str]:
        """Determine ideal use cases for this location."""
        ideal = []

        # Based on character
        if character == NeighborhoodCharacter.RURAL:
            ideal.append("Miłośnicy ciszy i spokoju")
        elif character == NeighborhoodCharacter.SUBURBAN:
            ideal.append("Rodziny z dziećmi")

        # Based on strengths
        if "Szkoła w pobliżu" in strengths:
            ideal.append("Rodziny z dziećmi w wieku szkolnym")
        if "Blisko natury" in strengths:
            ideal.append("Miłośnicy natury i aktywnego wypoczynku")
        if "Dobra komunikacja publiczna" in strengths:
            ideal.append("Osoby dojeżdżające do pracy")
        if "Bardzo cicha okolica" in strengths:
            ideal.append("Osoby pracujące zdalnie")

        return ideal or ["Wszyscy szukający działki w tej okolicy"]

    def _generate_summary(
        self,
        parcel: Dict[str, Any],
        character: NeighborhoodCharacter,
        strengths: List[str],
        weaknesses: List[str],
    ) -> str:
        """Generate human-readable summary."""
        district = parcel.get("dzielnica", parcel.get("district", ""))

        parts = []
        parts.append(f"Okolica {district} ma charakter {self._character_description(character).lower()}.")

        if strengths:
            parts.append(f"Główne atuty to: {', '.join(strengths[:3]).lower()}.")

        if weaknesses:
            parts.append(f"Do rozważenia: {', '.join(weaknesses[:2]).lower()}.")

        return " ".join(parts)


# Singleton
_neighborhood_service: Optional[NeighborhoodService] = None


def get_neighborhood_service() -> NeighborhoodService:
    """Get the global neighborhood service instance."""
    global _neighborhood_service
    if _neighborhood_service is None:
        _neighborhood_service = NeighborhoodService()
    return _neighborhood_service
