"""
Hybrid parcel search service.

Combines results from:
- PostGIS (spatial queries)
- Milvus (vector similarity)
- Neo4j (graph relationships)

Uses Reciprocal Rank Fusion (RRF) to combine rankings.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from loguru import logger

from app.services.spatial_service import spatial_service, SpatialSearchParams
from app.services.vector_service import vector_service, VectorSearchResult
from app.services.graph_service import graph_service


@dataclass
class SearchPreferences:
    """User preferences for parcel search."""
    # Location
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: float = 5000
    gmina: Optional[str] = None

    # Area
    min_area: Optional[float] = None
    max_area: Optional[float] = None

    # MPZP
    has_mpzp: Optional[bool] = None
    mpzp_budowlane: Optional[bool] = None
    mpzp_symbol: Optional[str] = None

    # Preference weights (0-1)
    quietness_weight: float = 0.5
    nature_weight: float = 0.3
    accessibility_weight: float = 0.2

    # Reference parcel for similarity
    reference_parcel_id: Optional[str] = None


@dataclass
class SearchResult:
    """Combined search result."""
    parcel_id: str
    rrf_score: float  # Combined ranking score
    sources: List[str] = field(default_factory=list)  # Which sources returned this

    # Basic info
    gmina: Optional[str] = None
    miejscowosc: Optional[str] = None
    area_m2: Optional[float] = None

    # Scores
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
    distance_m: Optional[float] = None

    # Vector similarity (if applicable)
    similarity_score: Optional[float] = None


class HybridSearchService:
    """
    Hybrid search combining spatial, vector, and graph queries.

    Uses Reciprocal Rank Fusion (RRF) to combine results from different sources.
    """

    # RRF constant (typically 60)
    RRF_K = 60

    # Default weights for each source
    SPATIAL_WEIGHT = 0.4
    VECTOR_WEIGHT = 0.3
    GRAPH_WEIGHT = 0.3

    async def search(
        self,
        preferences: SearchPreferences,
        limit: int = 20,
        include_details: bool = False,
    ) -> List[SearchResult]:
        """
        Perform hybrid search based on user preferences.

        Args:
            preferences: Search preferences
            limit: Maximum results to return
            include_details: Whether to fetch full details

        Returns:
            List of SearchResult ordered by RRF score
        """
        logger.info(f"Hybrid search: gmina={preferences.gmina}, "
                   f"area={preferences.min_area}-{preferences.max_area}, "
                   f"reference={preferences.reference_parcel_id}")

        # Collect results from each source in parallel
        tasks = []

        # Helper for empty async result
        async def empty_result():
            return []

        # 1. Spatial search (if location provided)
        if preferences.lat and preferences.lon:
            tasks.append(self._spatial_search(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # 2. Vector similarity search (if reference parcel or preferences)
        if preferences.reference_parcel_id:
            tasks.append(self._vector_search_similar(preferences, limit * 2))
        elif preferences.quietness_weight or preferences.nature_weight:
            tasks.append(self._vector_search_preferences(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # 3. Graph search (for MPZP filtering)
        if preferences.mpzp_symbol or preferences.mpzp_budowlane:
            tasks.append(self._graph_search(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # Execute all searches
        results = await asyncio.gather(*tasks, return_exceptions=True)

        spatial_results = results[0] if not isinstance(results[0], Exception) else []
        vector_results = results[1] if not isinstance(results[1], Exception) else []
        graph_results = results[2] if not isinstance(results[2], Exception) else []

        # Log any errors
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"Search task {i} failed: {r}")

        # Combine using RRF
        combined = self._combine_with_rrf(
            spatial_results, vector_results, graph_results
        )

        # Take top results
        combined = combined[:limit]

        # Optionally fetch full details
        if include_details and combined:
            combined = await self._enrich_results(combined)

        logger.info(f"Hybrid search returned {len(combined)} results")
        return combined

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
        """Execute graph-based search."""
        if preferences.mpzp_symbol:
            results = await graph_service.find_parcels_by_mpzp(
                symbol=preferences.mpzp_symbol,
                gmina=preferences.gmina,
                limit=limit,
            )
        elif preferences.mpzp_budowlane:
            results = await graph_service.find_buildable_parcels(
                gmina=preferences.gmina,
                min_area=preferences.min_area,
                max_area=preferences.max_area,
                limit=limit,
            )
        else:
            return []

        # Convert to standard format
        return [
            {
                "id_dzialki": r.get("id"),
                "gmina": r.get("gmina"),
                "area_m2": r.get("area_m2"),
                "quietness_score": r.get("quietness"),
                "nature_score": r.get("nature"),
                "mpzp_symbol": r.get("mpzp_symbol"),
                "centroid_lat": r.get("lat"),
                "centroid_lon": r.get("lon"),
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

        RRF score = sum(1 / (k + rank)) across all sources
        """
        # Collect all parcel IDs with their ranks
        parcel_scores = defaultdict(lambda: {"score": 0.0, "sources": [], "data": {}})

        # Process spatial results
        for r in spatial_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(spatial_results))
                parcel_scores[pid]["score"] += self.SPATIAL_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("spatial")
                parcel_scores[pid]["data"].update(r)

        # Process vector results
        for r in vector_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(vector_results))
                parcel_scores[pid]["score"] += self.VECTOR_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("vector")
                # Don't overwrite spatial data, just add vector-specific
                if "similarity_score" in r:
                    parcel_scores[pid]["data"]["similarity_score"] = r["similarity_score"]

        # Process graph results
        for r in graph_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(graph_results))
                parcel_scores[pid]["score"] += self.GRAPH_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("graph")
                # Add graph-specific data
                if "mpzp_symbol" in r and r["mpzp_symbol"]:
                    parcel_scores[pid]["data"]["mpzp_symbol"] = r["mpzp_symbol"]

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
        """Enrich results with full details from PostGIS."""
        parcel_ids = [r.parcel_id for r in results]
        details = await spatial_service.get_parcels_by_ids(parcel_ids)

        # Create lookup
        details_map = {d["id_dzialki"]: d for d in details}

        # Update results
        for result in results:
            if result.parcel_id in details_map:
                d = details_map[result.parcel_id]
                result.gmina = d.get("gmina")
                result.miejscowosc = d.get("miejscowosc")
                result.area_m2 = d.get("area_m2")
                result.quietness_score = d.get("quietness_score")
                result.nature_score = d.get("nature_score")
                result.accessibility_score = d.get("accessibility_score")
                result.has_mpzp = d.get("has_mpzp")
                result.mpzp_symbol = d.get("mpzp_symbol")
                result.mpzp_budowlane = d.get("mpzp_czy_budowlane")
                result.centroid_lat = d.get("centroid_lat")
                result.centroid_lon = d.get("centroid_lon")

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
