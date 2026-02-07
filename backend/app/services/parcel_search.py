"""
Hybrid parcel search service.

Architecture:
- Neo4j (graph) = PRIMARY source for filtering and finding parcels via relationships
- PostGIS = Spatial queries for geometry-based searches (radius from point)
- Neo4j GraphRAG = Semantic search via text embeddings (512-dim) + graph constraints

Uses Reciprocal Rank Fusion (RRF) to combine rankings when multiple sources used.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from loguru import logger

from app.services.spatial_service import spatial_service, SpatialSearchParams
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

    # === NEO4J V2: OWNERSHIP (2026-01-25) ===
    ownership_type: Optional[str] = None  # "prywatna", "publiczna", "spoldzielcza", "koscielna", "inna"

    # === NEO4J V2: BUILD STATUS (2026-01-25) ===
    build_status: Optional[str] = None  # "zabudowana", "niezabudowana"

    # === NEO4J V2: SIZE CATEGORY (2026-01-25) ===
    size_category: Optional[List[str]] = None  # ["mala", "pod_dom", "duza", "bardzo_duza"]

    # === NEO4J V2: POG RESIDENTIAL (2026-01-25) ===
    pog_residential: Optional[bool] = None  # Only residential POG zones

    # === SHAPE QUALITY (2026-02-07) ===
    include_infrastructure: bool = False  # Include SK/SI POG zones (default: exclude)

    # === SORTING ===
    sort_by: str = "quietness_score"  # or "nature_score", "accessibility_score", "area_m2"
    sort_desc: bool = True

    # === SIMILARITY SEARCH ===
    reference_parcel_id: Optional[str] = None  # For "find similar to X" queries

    # === SEMANTIC SEARCH (GraphRAG via Neo4j text embeddings) ===
    query_text: Optional[str] = None  # Natural language description for embedding search

    # === DIMENSION WEIGHTS (agent sets from user emphasis) ===
    w_quietness: float = 0.0
    w_nature: float = 0.0
    w_forest: float = 0.0
    w_water: float = 0.0
    w_school: float = 0.0
    w_shop: float = 0.0
    w_transport: float = 0.0
    w_accessibility: float = 0.0

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
            # NEO4J V2 filters (2026-01-25)
            ownership_type=self.ownership_type,
            build_status=self.build_status,
            size_category=self.size_category,
            pog_residential=self.pog_residential,
            # Shape quality (2026-02-07)
            include_infrastructure=self.include_infrastructure,
            sort_by=self.sort_by,
            sort_desc=self.sort_desc,
            # Dimension weights
            w_quietness=self.w_quietness,
            w_nature=self.w_nature,
            w_forest=self.w_forest,
            w_water=self.w_water,
            w_school=self.w_school,
            w_shop=self.w_shop,
            w_transport=self.w_transport,
            w_accessibility=self.w_accessibility,
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

    # Shape quality
    shape_index: Optional[float] = None
    aspect_ratio: Optional[float] = None

    # Vector similarity (if applicable)
    similarity_score: Optional[float] = None


class HybridSearchService:
    """
    Hybrid search combining graph, spatial, and semantic queries.

    Architecture:
    - Graph (Neo4j) = PRIMARY - always runs, uses rich relationships
    - Spatial (PostGIS) = Geometry-based searches (radius from point)
    - Semantic (Neo4j GraphRAG) = Text embedding similarity + graph constraints

    Uses Reciprocal Rank Fusion (RRF) to combine results when multiple sources used.
    """

    # RRF constant (typically 60)
    RRF_K = 60

    # Weights for each source
    GRAPH_WEIGHT = 0.45    # PRIMARY: Neo4j property + relationship matching
    SPATIAL_WEIGHT = 0.20  # PostGIS distance-ordered by centroid proximity
    SEMANTIC_WEIGHT = 0.35 # GraphRAG text embedding similarity

    # Minimum acceptable results before triggering relaxation
    MIN_RESULTS = 5

    async def search(
        self,
        preferences: SearchPreferences,
        limit: int = 20,
        include_details: bool = False,
    ) -> List[SearchResult]:
        """
        Perform hybrid search with progressive relaxation.

        Strategy:
        1. Full criteria (graph + spatial + semantic)
        2. If <5 results: relax distance thresholds 2x
        3. If still <5: drop soft criteria, keep hard filters
        4. If still 0: pure semantic search (vector only)

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

        # Strategy 1: Full criteria
        combined = await self._execute_search_pipeline(preferences, limit)

        if len(combined) >= self.MIN_RESULTS:
            if include_details and combined:
                combined = await self._enrich_results(combined[:limit])
            return combined[:limit]

        # Strategy 2: Relax distance thresholds 2x
        logger.info(f"Only {len(combined)} results, relaxing distance thresholds 2x")
        relaxed = self._relax_distances(preferences)
        combined_relaxed = await self._execute_search_pipeline(relaxed, limit)

        if len(combined_relaxed) >= self.MIN_RESULTS:
            if include_details and combined_relaxed:
                combined_relaxed = await self._enrich_results(combined_relaxed[:limit])
            return combined_relaxed[:limit]

        # Strategy 3: Drop soft criteria, keep hard filters only
        logger.info(f"Only {len(combined_relaxed)} results, dropping soft criteria")
        minimal = self._drop_soft_criteria(preferences)
        combined_minimal = await self._execute_search_pipeline(minimal, limit)

        if combined_minimal:
            if include_details:
                combined_minimal = await self._enrich_results(combined_minimal[:limit])
            return combined_minimal[:limit]

        # Strategy 4: Pure semantic fallback
        logger.info("No graph results, falling back to pure semantic search")
        semantic_results = await self._graphrag_search(preferences, limit * 2)
        if semantic_results:
            combined_semantic = self._convert_semantic_to_results(semantic_results)
            if include_details:
                combined_semantic = await self._enrich_results(combined_semantic[:limit])
            return combined_semantic[:limit]

        return []

    @staticmethod
    def _relax_distances(prefs: SearchPreferences) -> SearchPreferences:
        """Create a copy with distance thresholds doubled."""
        import copy
        relaxed = copy.copy(prefs)
        if relaxed.max_dist_to_forest_m:
            relaxed.max_dist_to_forest_m = int(relaxed.max_dist_to_forest_m * 2)
        if relaxed.max_dist_to_water_m:
            relaxed.max_dist_to_water_m = int(relaxed.max_dist_to_water_m * 2)
        if relaxed.max_dist_to_school_m:
            relaxed.max_dist_to_school_m = int(relaxed.max_dist_to_school_m * 2)
        if relaxed.max_dist_to_shop_m:
            relaxed.max_dist_to_shop_m = int(relaxed.max_dist_to_shop_m * 2)
        if relaxed.max_dist_to_bus_stop_m:
            relaxed.max_dist_to_bus_stop_m = int(relaxed.max_dist_to_bus_stop_m * 2)
        if relaxed.max_dist_to_hospital_m:
            relaxed.max_dist_to_hospital_m = int(relaxed.max_dist_to_hospital_m * 2)
        # Also relax all weights slightly (move toward center)
        for attr in ["w_quietness", "w_nature", "w_forest", "w_water",
                      "w_school", "w_shop", "w_transport", "w_accessibility"]:
            val = getattr(relaxed, attr, 0.0)
            if val > 0:
                setattr(relaxed, attr, val * 0.7)
        return relaxed

    @staticmethod
    def _drop_soft_criteria(prefs: SearchPreferences) -> SearchPreferences:
        """Create a copy with only hard filters (location, area, ownership, build_status)."""
        return SearchPreferences(
            gmina=prefs.gmina,
            miejscowosc=prefs.miejscowosc,
            powiat=prefs.powiat,
            lat=prefs.lat,
            lon=prefs.lon,
            radius_m=prefs.radius_m,
            min_area=prefs.min_area,
            max_area=prefs.max_area,
            ownership_type=prefs.ownership_type,
            build_status=prefs.build_status,
            size_category=prefs.size_category,
            pog_residential=prefs.pog_residential,
            query_text=prefs.query_text,
        )

    async def _execute_search_pipeline(
        self,
        preferences: SearchPreferences,
        limit: int,
    ) -> List[SearchResult]:
        """Execute the full search pipeline and combine results."""
        tasks = []

        async def empty_result():
            return []

        # 1. GRAPH SEARCH - PRIMARY (ALWAYS RUNS)
        tasks.append(self._graph_search(preferences, limit * 3))

        # 2. Spatial search (only if location coordinates provided)
        if preferences.lat and preferences.lon:
            tasks.append(self._spatial_search(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # 3. Semantic search (Neo4j GraphRAG - text embeddings + graph constraints)
        has_semantic_input = (preferences.query_text or preferences.quietness_categories
                             or preferences.nature_categories or preferences.miejscowosc
                             or preferences.gmina)
        if has_semantic_input:
            tasks.append(self._graphrag_search(preferences, limit * 2))
        elif preferences.reference_parcel_id:
            tasks.append(self._graph_embedding_similar(preferences, limit * 2))
        else:
            tasks.append(empty_result())

        # Execute all searches
        results = await asyncio.gather(*tasks, return_exceptions=True)

        graph_results = results[0] if not isinstance(results[0], Exception) else []
        spatial_results = results[1] if not isinstance(results[1], Exception) else []
        semantic_results = results[2] if not isinstance(results[2], Exception) else []

        # Log any errors
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                source_name = ["graph", "spatial", "semantic"][i]
                logger.error(f"Search task {source_name} failed: {r}")

        # Combine results based on what's available
        active_sources = sum([
            bool(graph_results), bool(spatial_results), bool(semantic_results)
        ])

        if active_sources == 0:
            combined = []
        elif active_sources == 1 and graph_results:
            combined = self._convert_graph_to_results(graph_results)
        elif active_sources == 1 and semantic_results:
            combined = self._convert_semantic_to_results(semantic_results)
        else:
            combined = self._combine_with_rrf(
                spatial_results, semantic_results, graph_results
            )

        # Post-filter: enforce hard constraints on combined results
        # Spatial/semantic sources don't apply all graph hard filters,
        # so we filter here to ensure consistency
        before_filter = len(combined)
        combined = self._apply_hard_filters(combined, preferences)
        if before_filter != len(combined):
            logger.info(f"Post-filter removed {before_filter - len(combined)} results "
                       f"not matching hard criteria")

        logger.info(f"Search pipeline: {len(combined)} results "
                   f"(graph={len(graph_results)}, spatial={len(spatial_results)}, "
                   f"semantic={len(semantic_results)})")
        return combined

    @staticmethod
    def _apply_hard_filters(
        results: List[SearchResult],
        preferences: SearchPreferences,
    ) -> List[SearchResult]:
        """Enforce hard constraints on combined results.

        Spatial and semantic searches don't apply all graph hard filters
        (area range, shape quality, POG exclusion). This post-filter
        ensures consistency across all sources.
        """
        filtered = []
        for r in results:
            # Area range (if specified)
            if r.area_m2 is not None:
                if preferences.min_area and r.area_m2 < preferences.min_area:
                    continue
                if preferences.max_area and r.area_m2 > preferences.max_area:
                    continue

            # Shape quality: exclude extreme elongation
            if r.aspect_ratio is not None and r.aspect_ratio > 6.0:
                continue

            # Shape quality: exclude very irregular shapes
            if r.shape_index is not None and r.shape_index < 0.15:
                continue

            filtered.append(r)
        return filtered

    def _convert_graph_to_results(self, graph_results: List[Dict]) -> List[SearchResult]:
        """Convert graph results directly to SearchResult when no RRF needed."""
        results = []
        for i, r in enumerate(graph_results):
            result = SearchResult(
                parcel_id=r.get("id_dzialki", ""),
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
                centroid_lat=r.get("centroid_lat"),
                centroid_lon=r.get("centroid_lon"),
                # Additional fields from graph
                dist_to_forest=r.get("dist_to_forest"),
                dist_to_water=r.get("dist_to_water"),
                dist_to_school=r.get("dist_to_school"),
                dist_to_shop=r.get("dist_to_shop"),
                pct_forest_500m=r.get("pct_forest_500m"),
                has_road_access=r.get("has_road_access"),
                shape_index=r.get("shape_index"),
                aspect_ratio=r.get("aspect_ratio"),
            )
            results.append(result)
        return results

    def _convert_semantic_to_results(self, semantic_results: List[Dict]) -> List[SearchResult]:
        """Convert semantic/GraphRAG results directly to SearchResult when no RRF needed."""
        results = []
        for i, r in enumerate(semantic_results):
            result = SearchResult(
                parcel_id=r.get("id_dzialki", ""),
                rrf_score=r.get("similarity_score", 1.0 / (i + 1)),
                sources=["semantic"],
                gmina=r.get("gmina"),
                miejscowosc=r.get("miejscowosc"),
                area_m2=r.get("area_m2"),
                quietness_score=r.get("quietness_score"),
                nature_score=r.get("nature_score"),
                accessibility_score=r.get("accessibility_score"),
                has_mpzp=r.get("has_mpzp"),
                mpzp_symbol=r.get("mpzp_symbol"),
                centroid_lat=r.get("centroid_lat"),
                centroid_lon=r.get("centroid_lon"),
                similarity_score=r.get("similarity_score"),
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

    async def _graphrag_search(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """GraphRAG: text embedding similarity (512-dim) + graph constraints via Neo4j."""
        from app.services.embedding_service import EmbeddingService

        query_text = preferences.query_text
        if not query_text:
            # Synthesize from preference fields
            parts = []
            if preferences.miejscowosc:
                parts.append(f"Działka w {preferences.miejscowosc}")
            elif preferences.gmina:
                parts.append(f"Działka w {preferences.gmina}")
            if preferences.quietness_categories:
                if any(c in preferences.quietness_categories for c in ["bardzo_cicha", "cicha"]):
                    parts.append("cicha spokojna okolica")
            if preferences.nature_categories:
                if any(c in preferences.nature_categories for c in ["bardzo_zielona", "zielona"]):
                    parts.append("blisko natury lasu zieleni")
            if preferences.build_status == "niezabudowana":
                parts.append("niezabudowana pod budowę domu")
            if preferences.ownership_type == "prywatna":
                parts.append("prywatna do kupienia")
            query_text = ". ".join(parts) if parts else "działka budowlana pod dom"

        query_embedding = EmbeddingService.encode(query_text)

        results = await graph_service.graphrag_search(
            query_embedding=query_embedding,
            ownership_type=preferences.ownership_type,
            build_status=preferences.build_status,
            size_category=preferences.size_category,
            gmina=preferences.gmina,
            dzielnica=preferences.miejscowosc,
            limit=limit,
        )

        for i, r in enumerate(results):
            r["_source"] = "graphrag"
            r["_rank"] = i + 1
            r["id_dzialki"] = r.get("id")
            r["miejscowosc"] = r.get("dzielnica") or r.get("district_name")
            r["centroid_lat"] = r.get("lat")
            r["centroid_lon"] = r.get("lon")
            r["similarity_score"] = r.get("vector_score")
        return results

    async def _graph_embedding_similar(
        self,
        preferences: SearchPreferences,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Find similar parcels using FastRP graph embeddings (256-dim) via Neo4j."""
        results = await graph_service.find_similar_by_graph_embedding(
            parcel_id=preferences.reference_parcel_id,
            limit=limit,
        )
        for i, r in enumerate(results):
            r["_source"] = "graphrag"
            r["_rank"] = i + 1
            r["id_dzialki"] = r.get("id")
            r["centroid_lat"] = r.get("lat")
            r["centroid_lon"] = r.get("lon")
            r["similarity_score"] = r.get("similarity")
        return results

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
                "shape_index": r.get("shape_index"),
                "aspect_ratio": r.get("aspect_ratio"),
                "_source": "graph",
                "_rank": i + 1,
            }
            for i, r in enumerate(results)
        ]

    def _combine_with_rrf(
        self,
        spatial_results: List[Dict],
        semantic_results: List[Dict],
        graph_results: List[Dict],
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = sum(weight / (k + rank)) across all sources.
        Multi-source bonus: parcels found by 2+ sources get a score boost.
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

        # Process semantic results (GraphRAG text embeddings + graph constraints)
        for r in semantic_results:
            pid = r.get("id_dzialki")
            if pid:
                rank = r.get("_rank", len(semantic_results))
                parcel_scores[pid]["score"] += self.SEMANTIC_WEIGHT / (self.RRF_K + rank)
                parcel_scores[pid]["sources"].append("semantic")
                existing_data = parcel_scores[pid]["data"]
                # Add similarity score from semantic search
                if "similarity_score" in r and r["similarity_score"] is not None:
                    existing_data["similarity_score"] = r["similarity_score"]
                # Fill in any missing fields
                for key in ["gmina", "miejscowosc", "area_m2", "centroid_lat", "centroid_lon",
                            "quietness_score", "nature_score", "accessibility_score"]:
                    if key in r and r[key] is not None and existing_data.get(key) is None:
                        existing_data[key] = r[key]

        # Multi-source bonus: parcels confirmed by multiple sources rank higher
        for pid, info in parcel_scores.items():
            source_count = len(set(info["sources"]))
            if source_count >= 3:
                info["score"] *= 1.3  # 30% bonus for confirmation from all 3 sources
            elif source_count >= 2:
                info["score"] *= 1.1  # 10% bonus for 2 sources

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
                shape_index=data.get("shape_index"),
                aspect_ratio=data.get("aspect_ratio"),
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
                # Shape quality fields
                if result.shape_index is None:
                    result.shape_index = d.get("shape_index")
                if result.aspect_ratio is None:
                    result.aspect_ratio = d.get("aspect_ratio")

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
