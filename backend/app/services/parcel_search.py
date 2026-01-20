"""
Hybrid parcel search service.

Architecture:
- Neo4j (graph) = PRIMARY source for filtering and finding parcels
- PostGIS = Spatial queries for geometry-based searches + GeoJSON generation
- Milvus = Vector similarity for "find similar to X" and preference-based re-ranking

Uses Reciprocal Rank Fusion (RRF) to combine rankings when multiple sources used.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from loguru import logger

from app.services.spatial_service import spatial_service, SpatialSearchParams
from app.services.vector_service import vector_service, VectorSearchResult
from app.services.graph_service import graph_service, ParcelSearchCriteria


@dataclass
class SearchPreferences:
    """
    User preferences for parcel search.

    Maps to graph_service.ParcelSearchCriteria for PRIMARY search.
    Includes additional fields for spatial/vector searches when needed.
    """
    # === LOCATION ===
    gmina: Optional[str] = None
    miejscowosc: Optional[str] = None
    powiat: Optional[str] = None
    # Spatial search (optional - for radius-based search around a point)
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: float = 5000

    # === AREA ===
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    area_category: Optional[List[str]] = None  # ["srednia", "duza"]

    # === CHARACTER & ENVIRONMENT ===
    charakter_terenu: Optional[List[str]] = None  # ["wiejski", "podmiejski", "leśny"]
    quietness_categories: Optional[List[str]] = None  # ["bardzo_cicha", "cicha"]
    nature_categories: Optional[List[str]] = None  # ["bardzo_zielona", "zielona"]
    building_density: Optional[List[str]] = None  # ["rzadka", "bardzo_rzadka"]

    # === ACCESSIBILITY ===
    accessibility_categories: Optional[List[str]] = None  # ["doskonały", "dobry"]
    max_dist_to_school_m: Optional[int] = None
    max_dist_to_shop_m: Optional[int] = None
    max_dist_to_bus_stop_m: Optional[int] = None
    max_dist_to_hospital_m: Optional[int] = None  # Medical accessibility
    has_road_access: Optional[bool] = None

    # === NATURE PROXIMITY ===
    max_dist_to_forest_m: Optional[int] = None
    max_dist_to_water_m: Optional[int] = None
    min_forest_pct_500m: Optional[float] = None  # e.g., 0.2 = 20% forest in 500m buffer

    # === MPZP (ZONING) ===
    has_mpzp: Optional[bool] = None
    mpzp_budowlane: Optional[bool] = None
    mpzp_symbols: Optional[List[str]] = None  # ["MN", "MN/U"]

    # === INDUSTRIAL DISTANCE ===
    min_dist_to_industrial_m: Optional[int] = None  # want to be FAR from industry

    # === SORTING ===
    sort_by: str = "quietness_score"  # or "nature_score", "accessibility_score", "area_m2"
    sort_desc: bool = True

    # === SIMILARITY SEARCH ===
    reference_parcel_id: Optional[str] = None  # For "find similar to X" queries

    # === LEGACY WEIGHTS (for backwards compatibility) ===
    quietness_weight: float = 0.5
    nature_weight: float = 0.3
    accessibility_weight: float = 0.2

    def to_graph_criteria(self, limit: int = 50) -> ParcelSearchCriteria:
        """Convert to ParcelSearchCriteria for graph search."""
        return ParcelSearchCriteria(
            gmina=self.gmina,
            miejscowosc=self.miejscowosc,
            powiat=self.powiat,
            min_area_m2=self.min_area,
            max_area_m2=self.max_area,
            area_category=self.area_category,
            charakter_terenu=self.charakter_terenu,
            quietness_categories=self.quietness_categories,
            nature_categories=self.nature_categories,
            building_density=self.building_density,
            accessibility_categories=self.accessibility_categories,
            max_dist_to_school_m=self.max_dist_to_school_m,
            max_dist_to_shop_m=self.max_dist_to_shop_m,
            max_dist_to_bus_stop_m=self.max_dist_to_bus_stop_m,
            max_dist_to_hospital_m=self.max_dist_to_hospital_m,
            has_road_access=self.has_road_access,
            max_dist_to_forest_m=self.max_dist_to_forest_m,
            max_dist_to_water_m=self.max_dist_to_water_m,
            min_forest_pct_500m=self.min_forest_pct_500m,
            has_mpzp=self.has_mpzp,
            mpzp_buildable=self.mpzp_budowlane,
            mpzp_symbols=self.mpzp_symbols,
            min_dist_to_industrial_m=self.min_dist_to_industrial_m,
            sort_by=self.sort_by,
            sort_desc=self.sort_desc,
            limit=limit,
        )


@dataclass
class SearchResult:
    """Combined search result with all available data."""
    parcel_id: str
    rrf_score: float  # Combined ranking score
    sources: List[str] = field(default_factory=list)  # Which sources returned this

    # Basic info
    gmina: Optional[str] = None
    miejscowosc: Optional[str] = None
    area_m2: Optional[float] = None

    # Composite scores (0-100)
    quietness_score: Optional[float] = None
    nature_score: Optional[float] = None
    accessibility_score: Optional[float] = None

    # MPZP
    has_mpzp: Optional[bool] = None
    mpzp_symbol: Optional[str] = None
    mpzp_budowlane: Optional[bool] = None

    # Location
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    distance_m: Optional[float] = None  # For spatial search (distance from point)

    # Distance to nature (meters)
    dist_to_forest: Optional[float] = None
    dist_to_water: Optional[float] = None

    # Distance to amenities (meters)
    dist_to_school: Optional[float] = None
    dist_to_shop: Optional[float] = None
    dist_to_bus_stop: Optional[float] = None

    # Buffer analysis (500m radius)
    pct_forest_500m: Optional[float] = None
    count_buildings_500m: Optional[int] = None

    # Access
    has_road_access: Optional[bool] = None

    # Vector similarity (if applicable)
    similarity_score: Optional[float] = None


class HybridSearchService:
    """
    Hybrid search combining graph, spatial, and vector queries.

    Architecture:
    - Graph (Neo4j) = PRIMARY - always runs, uses rich relationships
    - Spatial (PostGIS) = For geometry-based searches (radius from point)
    - Vector (Milvus) = For "find similar" and preference-based re-ranking

    Uses Reciprocal Rank Fusion (RRF) to combine results when multiple sources used.
    """

    # RRF constant (typically 60)
    RRF_K = 60

    # Weights for each source (Graph is PRIMARY)
    GRAPH_WEIGHT = 0.5   # PRIMARY source
    SPATIAL_WEIGHT = 0.3  # Geometry-based when location provided
    VECTOR_WEIGHT = 0.2   # Re-ranking/similarity

    async def search(
        self,
        preferences: SearchPreferences,
        limit: int = 20,
        include_details: bool = False,
    ) -> List[SearchResult]:
        """
        Perform hybrid search based on user preferences.

        Graph search is ALWAYS executed as the primary source.
        Spatial/vector are used to augment when relevant.

        Args:
            preferences: Search preferences
            limit: Maximum results to return
            include_details: Whether to fetch full details

        Returns:
            List of SearchResult ordered by RRF score
        """
        logger.info(f"Hybrid search: gmina={preferences.gmina}, "
                   f"area={preferences.min_area}-{preferences.max_area}, "
                   f"quietness={preferences.quietness_categories}, "
                   f"nature={preferences.nature_categories}, "
                   f"reference={preferences.reference_parcel_id}")

        # Collect results from each source in parallel
        tasks = []

        # Helper for empty async result
        async def empty_result():
            return []

        # 1. GRAPH SEARCH - PRIMARY (ALWAYS RUNS)
        tasks.append(self._graph_search(preferences, limit * 3))

        # 2. Spatial search (only if location coordinates provided)
        if preferences.lat and preferences.lon:
            tasks.append(self._spatial_search(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # 3. Vector similarity search (for "find similar" or preference re-ranking)
        if preferences.reference_parcel_id:
            tasks.append(self._vector_search_similar(preferences, limit * 2))
        else:
            # Skip vector search if no reference - graph handles preferences better
            tasks.append(empty_result())

        # Execute all searches
        results = await asyncio.gather(*tasks, return_exceptions=True)

        graph_results = results[0] if not isinstance(results[0], Exception) else []
        spatial_results = results[1] if not isinstance(results[1], Exception) else []
        vector_results = results[2] if not isinstance(results[2], Exception) else []

        # Log any errors
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                source_name = ["graph", "spatial", "vector"][i]
                logger.error(f"Search task {source_name} failed: {r}")

        # If only graph results, return them directly without RRF
        if not spatial_results and not vector_results:
            combined = self._convert_graph_to_results(graph_results)
        else:
            # Combine using RRF when multiple sources
            combined = self._combine_with_rrf(
                spatial_results, vector_results, graph_results
            )

        # Take top results
        combined = combined[:limit]

        # Optionally fetch full details (geometry) from PostGIS
        if include_details and combined:
            combined = await self._enrich_results(combined)

        logger.info(f"Hybrid search returned {len(combined)} results "
                   f"(graph={len(graph_results)}, spatial={len(spatial_results)}, vector={len(vector_results)})")
        return combined

    def _convert_graph_to_results(self, graph_results: List[Dict]) -> List[SearchResult]:
        """Convert graph results directly to SearchResult when no RRF needed."""
        results = []
        for i, r in enumerate(graph_results):
            result = SearchResult(
                parcel_id=r.get("id", ""),
                rrf_score=1.0 / (i + 1),  # Simple rank-based score
                sources=["graph"],
                gmina=r.get("gmina"),
                miejscowosc=r.get("miejscowosc"),
                area_m2=r.get("area_m2"),
                quietness_score=r.get("quietness_score"),
                nature_score=r.get("nature_score"),
                accessibility_score=r.get("accessibility_score"),
                has_mpzp=r.get("has_mpzp"),
                mpzp_symbol=r.get("mpzp_symbol"),
                centroid_lat=r.get("lat"),
                centroid_lon=r.get("lon"),
                # Additional fields from graph
                dist_to_forest=r.get("dist_to_forest"),
                dist_to_water=r.get("dist_to_water"),
                dist_to_school=r.get("dist_to_school"),
                dist_to_shop=r.get("dist_to_shop"),
                pct_forest_500m=r.get("pct_forest_500m"),
                has_road_access=r.get("has_road_access"),
            )
            results.append(result)
        return results

    async def _spatial_search(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute spatial search."""
        params = SpatialSearchParams(
            lat=preferences.lat,
            lon=preferences.lon,
            radius_m=preferences.radius_m,
            min_area=preferences.min_area,
            max_area=preferences.max_area,
            gmina=preferences.gmina,
            has_mpzp=preferences.has_mpzp,
            mpzp_budowlane=preferences.mpzp_budowlane,
            limit=limit,
        )

        results = await spatial_service.search_by_radius(params)

        # Add source tag
        for r in results:
            r["_source"] = "spatial"
            r["_rank"] = results.index(r) + 1

        return results

    async def _vector_search_similar(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute vector similarity search."""
        results = await vector_service.search_similar(
            parcel_id=preferences.reference_parcel_id,
            top_k=limit,
            min_area=preferences.min_area,
            max_area=preferences.max_area,
            gmina=preferences.gmina,
            has_mpzp=preferences.has_mpzp,
        )

        # Convert to dict format
        return [
            {
                "id_dzialki": r.parcel_id,
                "similarity_score": r.similarity_score,
                "gmina": r.gmina,
                "area_m2": r.area_m2,
                "quietness_score": r.quietness_score,
                "nature_score": r.nature_score,
                "accessibility_score": r.accessibility_score,
                "_source": "vector",
                "_rank": i + 1,
            }
            for i, r in enumerate(results)
        ]

    async def _vector_search_preferences(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute vector search based on preference weights."""
        pref_dict = {
            "quietness": preferences.quietness_weight,
            "nature": preferences.nature_weight,
            "accessibility": preferences.accessibility_weight,
        }

        results = await vector_service.search_by_preferences(
            preferences=pref_dict,
            top_k=limit,
            min_area=preferences.min_area,
            max_area=preferences.max_area,
            gmina=preferences.gmina,
        )

        return [
            {
                "id_dzialki": r.parcel_id,
                "similarity_score": r.similarity_score,
                "gmina": r.gmina,
                "area_m2": r.area_m2,
                "quietness_score": r.quietness_score,
                "nature_score": r.nature_score,
                "accessibility_score": r.accessibility_score,
                "_source": "vector",
                "_rank": i + 1,
            }
            for i, r in enumerate(results)
        ]

    async def _graph_search(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Execute graph-based search using comprehensive criteria.

        This is the PRIMARY search - always runs with all available filters.
        """
        # Convert preferences to graph criteria
        criteria = preferences.to_graph_criteria(limit=limit)

        # Execute comprehensive graph search
        results = await graph_service.search_parcels(criteria)

        # Convert to standard format with rank
        return [
            {
                "id_dzialki": r.get("id"),
                "gmina": r.get("gmina"),
                "miejscowosc": r.get("miejscowosc"),
                "area_m2": r.get("area_m2"),
                "quietness_score": r.get("quietness_score"),
                "nature_score": r.get("nature_score"),
                "accessibility_score": r.get("accessibility_score"),
                "has_mpzp": r.get("has_mpzp"),
                "mpzp_symbol": r.get("mpzp_symbol"),
                "centroid_lat": r.get("lat"),
                "centroid_lon": r.get("lon"),
                "dist_to_forest": r.get("dist_to_forest"),
                "dist_to_water": r.get("dist_to_water"),
                "dist_to_school": r.get("dist_to_school"),
                "dist_to_shop": r.get("dist_to_shop"),
                "dist_to_bus_stop": r.get("dist_to_bus_stop"),
                "pct_forest_500m": r.get("pct_forest_500m"),
                "count_buildings_500m": r.get("count_buildings_500m"),
                "has_road_access": r.get("has_road_access"),
                "_source": "graph",
                "_rank": i + 1,
            }
            for i, r in enumerate(results)
        ]

    def _combine_with_rrf(
        self,
        spatial_results: List[Dict],
        vector_results: List[Dict],
        graph_results: List[Dict],
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = sum(weight / (k + rank)) across all sources
        Graph is PRIMARY so it contributes most to the score.
        """
        # Collect all parcel IDs with their ranks
        parcel_scores = defaultdict(lambda: {"score": 0.0, "sources": [], "data": {}})

        # Process GRAPH results FIRST (PRIMARY source - provides most data)
        for r in graph_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(graph_results))
                parcel_scores[pid]["score"] += self.GRAPH_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("graph")
                # Graph provides comprehensive data - use it as base
                parcel_scores[pid]["data"].update(r)

        # Process spatial results (supplements with location-based data)
        for r in spatial_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(spatial_results))
                parcel_scores[pid]["score"] += self.SPATIAL_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("spatial")
                # Only add spatial-specific data that graph doesn't have
                existing_data = parcel_scores[pid]["data"]
                if "distance_m" in r and r["distance_m"] is not None:
                    existing_data["distance_m"] = r["distance_m"]
                # Fill in any missing basic fields
                for key in ["gmina", "miejscowosc", "area_m2", "centroid_lat", "centroid_lon"]:
                    if key in r and r[key] is not None and existing_data.get(key) is None:
                        existing_data[key] = r[key]

        # Process vector results (for similarity scores)
        for r in vector_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(vector_results))
                parcel_scores[pid]["score"] += self.VECTOR_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("vector")
                # Add similarity score from vector search
                if "similarity_score" in r and r["similarity_score"] is not None:
                    parcel_scores[pid]["data"]["similarity_score"] = r["similarity_score"]

        # Convert to SearchResult objects
        results = []
        for pid, info in parcel_scores.items():
            data = info["data"]
            result = SearchResult(
                parcel_id=pid,
                rrf_score=info["score"],
                sources=list(set(info["sources"])),
                gmina=data.get("gmina"),
                miejscowosc=data.get("miejscowosc"),
                area_m2=data.get("area_m2"),
                quietness_score=data.get("quietness_score"),
                nature_score=data.get("nature_score"),
                accessibility_score=data.get("accessibility_score"),
                has_mpzp=data.get("has_mpzp"),
                mpzp_symbol=data.get("mpzp_symbol"),
                mpzp_budowlane=data.get("mpzp_czy_budowlane"),
                centroid_lat=data.get("centroid_lat"),
                centroid_lon=data.get("centroid_lon"),
                distance_m=data.get("distance_m"),
                # New fields from graph
                dist_to_forest=data.get("dist_to_forest"),
                dist_to_water=data.get("dist_to_water"),
                dist_to_school=data.get("dist_to_school"),
                dist_to_shop=data.get("dist_to_shop"),
                dist_to_bus_stop=data.get("dist_to_bus_stop"),
                pct_forest_500m=data.get("pct_forest_500m"),
                count_buildings_500m=data.get("count_buildings_500m"),
                has_road_access=data.get("has_road_access"),
                similarity_score=data.get("similarity_score"),
            )
            results.append(result)

        # Sort by RRF score
        results.sort(key=lambda x: x.rrf_score, reverse=True)

        return results

    async def _enrich_results(
        self,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """Enrich results with geometry details from PostGIS (for map display)."""
        parcel_ids = [r.parcel_id for r in results]
        details = await spatial_service.get_parcels_by_ids(parcel_ids)

        # Create lookup
        details_map = {d["id_dzialki"]: d for d in details}

        # Update results - fill in any missing fields from PostGIS
        for result in results:
            if result.parcel_id in details_map:
                d = details_map[result.parcel_id]
                # Only fill in if not already set (graph data takes precedence)
                if result.gmina is None:
                    result.gmina = d.get("gmina")
                if result.miejscowosc is None:
                    result.miejscowosc = d.get("miejscowosc")
                if result.area_m2 is None:
                    result.area_m2 = d.get("area_m2")
                if result.quietness_score is None:
                    result.quietness_score = d.get("quietness_score")
                if result.nature_score is None:
                    result.nature_score = d.get("nature_score")
                if result.accessibility_score is None:
                    result.accessibility_score = d.get("accessibility_score")
                if result.has_mpzp is None:
                    result.has_mpzp = d.get("has_mpzp")
                if result.mpzp_symbol is None:
                    result.mpzp_symbol = d.get("mpzp_symbol")
                if result.mpzp_budowlane is None:
                    result.mpzp_budowlane = d.get("mpzp_czy_budowlane")
                if result.centroid_lat is None:
                    result.centroid_lat = d.get("centroid_lat")
                if result.centroid_lon is None:
                    result.centroid_lon = d.get("centroid_lon")
                # Distance fields from PostGIS
                if result.dist_to_forest is None:
                    result.dist_to_forest = d.get("dist_to_forest")
                if result.dist_to_water is None:
                    result.dist_to_water = d.get("dist_to_water")
                if result.dist_to_school is None:
                    result.dist_to_school = d.get("dist_to_school")
                if result.dist_to_shop is None:
                    result.dist_to_shop = d.get("dist_to_shop")
                if result.dist_to_bus_stop is None:
                    result.dist_to_bus_stop = d.get("dist_to_bus_stop")
                if result.pct_forest_500m is None:
                    result.pct_forest_500m = d.get("pct_forest_500m")
                if result.has_road_access is None:
                    result.has_road_access = d.get("has_public_road_access")

        return results

    async def get_parcel_full_details(self, parcel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete details for a single parcel.

        Combines data from PostGIS and Neo4j.
        """
        # Get spatial details (with geometry)
        spatial_details = await spatial_service.get_parcel_details(
            parcel_id, include_geometry=True
        )

        if not spatial_details:
            return None

        # Get graph context
        graph_context = await graph_service.get_parcel_context(parcel_id)

        # Merge
        result = {**spatial_details}
        if graph_context:
            result["graph_context"] = graph_context

        return result

    async def count_matching(self, preferences: SearchPreferences) -> int:
        """Count parcels matching preferences (for preview)."""
        return await spatial_service.count_parcels(
            gmina=preferences.gmina,
            has_mpzp=preferences.has_mpzp,
        )


# Global instance
hybrid_search = HybridSearchService()
