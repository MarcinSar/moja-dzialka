"""
Search API endpoints.

Direct search endpoints (bypassing agent) for programmatic access.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.parcel_search import hybrid_search, SearchPreferences, SearchResult
from app.services.spatial_service import spatial_service
from app.services.graph_service import graph_service
from app.models.schemas import (
    SearchPreferencesRequest,
    SearchResponse,
    SearchResultItem,
    ParcelDetails,
    MapDataRequest,
    MapDataResponse,
    GminaInfo,
    GminaListResponse,
    MpzpSymbol,
    MpzpSymbolsResponse,
    ErrorResponse,
    # v3.0 Neighborhood
    NeighborhoodResponse,
    NeighborhoodCharacter,
    NeighborhoodDensity,
    NeighborhoodEnvironment,
    NeighborhoodScores,
    NeighborhoodNeighbors,
    NeighborhoodPOI,
    NeighborhoodAssessment,
)
from app.services.neighborhood_service import get_neighborhood_service


router = APIRouter(prefix="/search", tags=["search"])


# =============================================================================
# SEARCH ENDPOINTS
# =============================================================================

@router.post("/", response_model=SearchResponse)
async def search_parcels(
    preferences: SearchPreferencesRequest,
    limit: int = Query(20, ge=1, le=100),
    include_details: bool = Query(False),
):
    """
    Search for parcels based on preferences.

    Returns up to `limit` parcels matching the criteria.
    First 3 results are always free (freemium model).
    """
    try:
        # Convert request to SearchPreferences
        search_prefs = SearchPreferences(
            lat=preferences.lat,
            lon=preferences.lon,
            radius_m=preferences.radius_m,
            gmina=preferences.gmina,
            min_area=preferences.min_area_m2,
            max_area=preferences.max_area_m2,
            has_mpzp=preferences.has_mpzp,
            mpzp_budowlane=preferences.mpzp_budowlane,
            mpzp_symbols=[preferences.mpzp_symbol] if preferences.mpzp_symbol else None,
            quietness_weight=preferences.quietness_weight,
            nature_weight=preferences.nature_weight,
            accessibility_weight=preferences.accessibility_weight,
        )

        # Execute search
        results = await hybrid_search.search(
            preferences=search_prefs,
            limit=limit,
            include_details=include_details,
        )

        # Convert to response items
        items = [
            SearchResultItem(
                parcel_id=r.parcel_id,
                rrf_score=r.rrf_score,
                sources=r.sources,
                gmina=r.gmina,
                miejscowosc=r.miejscowosc,
                area_m2=r.area_m2,
                quietness_score=r.quietness_score,
                nature_score=r.nature_score,
                accessibility_score=r.accessibility_score,
                has_mpzp=r.has_mpzp,
                mpzp_symbol=r.mpzp_symbol,
                centroid_lat=r.centroid_lat,
                centroid_lon=r.centroid_lon,
                distance_m=r.distance_m,
            )
            for r in results
        ]

        # Count total matching (for UI)
        total_matching = await hybrid_search.count_matching(search_prefs)

        return SearchResponse(
            count=len(items),
            total_matching=total_matching,
            results=items,
            free_results=3,
            requires_payment=len(items) > 3,
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar/{parcel_id:path}", response_model=SearchResponse)
async def find_similar(
    parcel_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """
    Find parcels similar to the given parcel.

    Uses vector similarity search based on SRAI embeddings.
    """
    try:
        # Search with reference parcel
        search_prefs = SearchPreferences(
            reference_parcel_id=parcel_id,
        )

        results = await hybrid_search.search(
            preferences=search_prefs,
            limit=limit,
            include_details=True,
        )

        items = [
            SearchResultItem(
                parcel_id=r.parcel_id,
                rrf_score=r.rrf_score,
                sources=r.sources,
                gmina=r.gmina,
                miejscowosc=r.miejscowosc,
                area_m2=r.area_m2,
                quietness_score=r.quietness_score,
                nature_score=r.nature_score,
                accessibility_score=r.accessibility_score,
                has_mpzp=r.has_mpzp,
                mpzp_symbol=r.mpzp_symbol,
                centroid_lat=r.centroid_lat,
                centroid_lon=r.centroid_lon,
                distance_m=r.distance_m,
            )
            for r in results
        ]

        return SearchResponse(
            count=len(items),
            results=items,
            free_results=3,
            requires_payment=len(items) > 3,
        )

    except Exception as e:
        logger.error(f"Similar search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PARCEL DETAILS
# =============================================================================

@router.get("/parcel/{parcel_id:path}", response_model=ParcelDetails)
async def get_parcel_details(
    parcel_id: str,
    include_geometry: bool = Query(True),
):
    """
    Get full details for a specific parcel.

    Note: This endpoint requires payment in production (freemium).
    """
    try:
        details = await hybrid_search.get_parcel_full_details(parcel_id)

        if not details:
            raise HTTPException(status_code=404, detail="Parcel not found")

        return ParcelDetails(
            id_dzialki=details.get("id_dzialki"),
            teryt_powiat=details.get("powiat"),
            gmina=details.get("gmina"),
            dzielnica=details.get("dzielnica"),
            miejscowosc=details.get("miejscowosc"),
            centroid_lat=details.get("centroid_lat"),
            centroid_lon=details.get("centroid_lon"),
            area_m2=details.get("area_m2"),
            compactness=details.get("compactness"),
            forest_ratio=details.get("forest_ratio"),
            water_ratio=details.get("water_ratio"),
            builtup_ratio=details.get("builtup_ratio"),
            dist_to_school=details.get("dist_to_school"),
            dist_to_shop=details.get("dist_to_shop"),
            dist_to_hospital=details.get("dist_to_hospital"),
            dist_to_bus_stop=details.get("dist_to_bus_stop"),
            dist_to_public_road=details.get("dist_to_main_road"),
            dist_to_forest=details.get("dist_to_forest"),
            dist_to_water=details.get("dist_to_water"),
            dist_to_pharmacy=details.get("dist_to_pharmacy"),
            pct_forest_500m=details.get("pct_forest_500m"),
            pct_water_500m=details.get("pct_water_500m"),
            count_buildings_500m=details.get("count_buildings_500m"),
            # POG fields (all)
            has_pog=details.get("has_pog"),
            pog_symbol=details.get("pog_symbol"),
            pog_nazwa=details.get("pog_nazwa"),
            pog_oznaczenie=details.get("pog_oznaczenie"),
            pog_profil_podstawowy=details.get("pog_profil_podstawowy"),
            pog_profil_podstawowy_nazwy=details.get("pog_profil_podstawowy_nazwy"),
            pog_profil_dodatkowy=details.get("pog_profil_dodatkowy"),
            pog_profil_dodatkowy_nazwy=details.get("pog_profil_dodatkowy_nazwy"),
            pog_maks_intensywnosc=details.get("pog_maks_intensywnosc"),
            pog_maks_wysokosc_m=details.get("pog_maks_wysokosc_m"),
            pog_maks_zabudowa_pct=details.get("pog_maks_zabudowa_pct"),
            pog_min_bio_pct=details.get("pog_min_bio_pct"),
            is_residential_zone=details.get("is_residential_zone"),
            # Scores
            quietness_score=details.get("quietness_score"),
            nature_score=details.get("nature_score"),
            accessibility_score=details.get("accessibility_score"),
            has_public_road_access=details.get("has_public_road_access"),
            # Building info
            is_built=details.get("is_built"),
            building_count=details.get("building_count"),
            building_coverage_pct=details.get("building_coverage_pct"),
            # Categories
            kategoria_ciszy=details.get("kategoria_ciszy"),
            kategoria_natury=details.get("kategoria_natury"),
            kategoria_dostepu=details.get("kategoria_dostepu"),
            gestosc_zabudowy=details.get("gestosc_zabudowy"),
            # Geometry
            geometry_wgs84=details.get("geometry_wgs84") if include_geometry else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get parcel details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MAP DATA
# =============================================================================

@router.post("/map", response_model=MapDataResponse)
async def generate_map_data(request: MapDataRequest):
    """
    Generate GeoJSON map data for the given parcel IDs.

    Returns GeoJSON FeatureCollection suitable for Leaflet/MapLibre.
    """
    try:
        result = await spatial_service.generate_geojson(
            parcel_ids=request.parcel_ids,
            include_geometry=request.include_geometry,
        )

        if not result:
            raise HTTPException(status_code=404, detail="No parcels found")

        return MapDataResponse(
            geojson=result.get("geojson", {}),
            bounds=result.get("bounds"),
            center=result.get("center"),
            parcel_count=result.get("parcel_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate map data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GMINA INFO
# =============================================================================

@router.get("/gminy", response_model=GminaListResponse)
async def list_gminy():
    """List all gminy with parcels in the database."""
    try:
        gminy = await spatial_service.list_gminy()
        return GminaListResponse(
            count=len(gminy),
            gminy=gminy,
        )

    except Exception as e:
        logger.error(f"List gminy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmina/{gmina_name}", response_model=GminaInfo)
async def get_gmina_info(gmina_name: str):
    """Get information about a specific gmina."""
    try:
        info = await spatial_service.get_gmina_statistics(gmina_name)

        if not info:
            raise HTTPException(status_code=404, detail="Gmina not found")

        return GminaInfo(
            name=info.get("gmina", gmina_name),
            teryt=info.get("teryt"),
            parcel_count=info.get("parcel_count", 0),
            avg_area_m2=info.get("avg_area_m2"),
            mpzp_coverage_pct=info.get("mpzp_coverage_pct"),
            miejscowosci=info.get("miejscowosci", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get gmina info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MPZP SYMBOLS
# =============================================================================

@router.get("/mpzp-symbols", response_model=MpzpSymbolsResponse)
async def get_mpzp_symbols():
    """Get list of MPZP symbols and their meanings."""
    try:
        symbols_data = await graph_service.get_mpzp_symbols()

        symbols = [
            MpzpSymbol(
                symbol=s.get("symbol", ""),
                name=s.get("name", ""),
                description=s.get("description", ""),
                is_budowlane=s.get("is_budowlane", False),
            )
            for s in symbols_data
        ]

        return MpzpSymbolsResponse(
            count=len(symbols),
            symbols=symbols,
        )

    except Exception as e:
        logger.error(f"Get MPZP symbols error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NEIGHBORHOOD ANALYSIS (v3.0)
# =============================================================================

@router.get("/neighborhood/{parcel_id:path}", response_model=NeighborhoodResponse)
async def get_neighborhood_analysis(
    parcel_id: str,
    radius_m: int = Query(500, ge=100, le=2000),
):
    """
    Get comprehensive neighborhood analysis for a parcel.

    PREMIUM FEATURE: Returns detailed assessment of:
    - Character (urban/suburban/rural)
    - Density metrics
    - Transport and amenities scores
    - Nearby POI
    - Strengths and weaknesses
    - Ideal use cases

    Args:
        parcel_id: The parcel ID to analyze
        radius_m: Analysis radius in meters (default 500)

    Returns:
        NeighborhoodResponse with full analysis
    """
    try:
        service = get_neighborhood_service()
        analysis = await service.analyze_neighborhood(parcel_id, radius_m)

        if "error" in analysis:
            raise HTTPException(status_code=404, detail=analysis["error"])

        # Map to response schema
        return NeighborhoodResponse(
            parcel_id=analysis.get("parcel_id", parcel_id),
            district=analysis.get("district"),
            city=analysis.get("city"),
            character=NeighborhoodCharacter(
                type=analysis.get("character", {}).get("type", "unknown"),
                description=analysis.get("character", {}).get("description", ""),
            ),
            density=NeighborhoodDensity(
                building_pct=analysis.get("density", {}).get("building_pct", 0),
                residential_pct=analysis.get("density", {}).get("residential_pct", 0),
                avg_parcel_size_m2=analysis.get("density", {}).get("avg_parcel_size_m2"),
            ),
            environment=NeighborhoodEnvironment(
                quietness_score=analysis.get("environment", {}).get("quietness_score", 50),
                nature_score=analysis.get("environment", {}).get("nature_score", 50),
                accessibility_score=analysis.get("environment", {}).get("accessibility_score", 50),
            ),
            scores=NeighborhoodScores(
                transport=analysis.get("scores", {}).get("transport", 50),
                amenities=analysis.get("scores", {}).get("amenities", 50),
                overall_livability=analysis.get("scores", {}).get("overall_livability", 50),
            ),
            neighbors=NeighborhoodNeighbors(
                adjacent_count=analysis.get("neighbors", {}).get("adjacent_count", 0),
                adjacent_parcels=analysis.get("neighbors", {}).get("adjacent_parcels", []),
                nearby_poi_count=analysis.get("neighbors", {}).get("nearby_poi_count", 0),
            ),
            poi=[
                NeighborhoodPOI(
                    type=p.get("type", "unknown"),
                    name=p.get("name"),
                    distance_m=p.get("distance_m", 0),
                )
                for p in analysis.get("poi", [])
            ],
            assessment=NeighborhoodAssessment(
                strengths=analysis.get("assessment", {}).get("strengths", []),
                weaknesses=analysis.get("assessment", {}).get("weaknesses", []),
                ideal_for=analysis.get("assessment", {}).get("ideal_for", []),
            ),
            summary=analysis.get("summary", ""),
            is_premium=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Neighborhood analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats")
async def get_search_stats():
    """Get overall search statistics."""
    try:
        total_parcels = await spatial_service.count_parcels()
        gminy = await spatial_service.list_gminy()

        return {
            "total_parcels": total_parcels,
            "total_gminy": len(gminy),
            "data_version": "dev-sample-v1.0.0",
        }

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
