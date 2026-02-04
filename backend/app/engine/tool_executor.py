"""
Tool Executor - Execute tools with V2 state management.

This module provides the ToolExecutor class that:
1. Accepts V2 AgentState as argument
2. Synchronizes V2 state with tool execution context
3. Returns (result, state_updates) for stateful tools

Replaces the global state pattern from agent/tools.py.
"""

from typing import Dict, Any, List, Optional, Tuple
import json

from loguru import logger

from app.memory import AgentState, SearchState
from app.services import (
    spatial_service,
    vector_service,
    graph_service,
    hybrid_search,
    SearchPreferences,
    SpatialSearchParams,
    BBoxSearchParams,
)
from app.services.database import neo4j


# Type alias for tool execution results
ToolResult = Tuple[Dict[str, Any], Dict[str, Any]]  # (result, state_updates)


class ToolExecutor:
    """Execute tools with V2 state management.

    This class manages tool execution while maintaining state updates
    that should be applied to the AgentState after execution.

    Usage:
        executor = ToolExecutor(state)
        result, state_updates = await executor.execute("tool_name", params)
        # Apply state_updates to state
    """

    def __init__(self, state: AgentState):
        """Initialize executor with agent state.

        Args:
            state: Current V2 AgentState from which to read/write search state
        """
        self.state = state
        self._search_state = state.working.search_state

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given parameters.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters

        Returns:
            Tuple of (result_dict, state_updates_dict)
            state_updates contains keys that should be updated in AgentState
        """
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool params: {params}")

        try:
            # Stateful tools (modify search state)
            if tool_name == "propose_search_preferences":
                return await self._propose_search_preferences(params)
            elif tool_name == "approve_search_preferences":
                return await self._approve_search_preferences(params)
            elif tool_name == "modify_search_preferences":
                return await self._modify_search_preferences(params)
            elif tool_name == "execute_search":
                return await self._execute_search(params)
            elif tool_name == "critique_search_results":
                return await self._critique_search_results(params)
            elif tool_name == "refine_search":
                return await self._refine_search(params)

            # Stateless tools (delegate to services)
            elif tool_name == "find_similar_parcels":
                result = await self._find_similar_parcels(params)
                return result, {}
            elif tool_name == "get_parcel_details":
                result = await self._get_parcel_details(params)
                return result, {}
            elif tool_name == "get_gmina_info":
                result = await self._get_gmina_info(params)
                return result, {}
            elif tool_name == "list_gminy":
                result = await self._list_gminy(params)
                return result, {}
            elif tool_name == "count_matching_parcels":
                result = await self._count_matching_parcels(params)
                return result, {}
            elif tool_name == "count_matching_parcels_quick":
                result = await self._count_matching_parcels_quick(params)
                return result, {}
            elif tool_name == "get_mpzp_symbols":
                result = await self._get_mpzp_symbols(params)
                return result, {}
            elif tool_name == "explore_administrative_hierarchy":
                result = await self._explore_administrative_hierarchy(params)
                return result, {}
            elif tool_name == "get_parcel_neighborhood":
                result = await self._get_parcel_neighborhood(params)
                return result, {}
            elif tool_name == "get_area_statistics":
                result = await self._get_area_statistics(params)
                return result, {}
            elif tool_name == "find_by_mpzp_symbol":
                result = await self._find_by_mpzp_symbol(params)
                return result, {}
            elif tool_name == "search_around_point":
                result = await self._search_around_point(params)
                return result, {}
            elif tool_name == "search_in_bbox":
                result = await self._search_in_bbox(params)
                return result, {}
            elif tool_name == "generate_map_data":
                result = await self._generate_map_data(params)
                return result, {}
            elif tool_name == "get_district_prices":
                result = await self._get_district_prices(params)
                return result, {}
            elif tool_name == "estimate_parcel_value":
                result = await self._estimate_parcel_value(params)
                return result, {}
            elif tool_name == "search_by_water_type":
                result = await self._search_by_water_type(params)
                return result, {}
            elif tool_name == "get_water_info":
                result = await self._get_water_info(params)
                return result, {}
            elif tool_name == "get_parcel_full_context":
                result = await self._get_parcel_full_context(params)
                return result, {}
            # Dynamic location tools (2026-01-25)
            elif tool_name == "get_available_locations":
                result = await self._get_available_locations(params)
                return result, {}
            elif tool_name == "get_districts_in_miejscowosc":
                result = await self._get_districts_in_miejscowosc(params)
                return result, {}
            elif tool_name == "resolve_location":
                result = await self._resolve_location(params)
                return result, {}
            elif tool_name == "validate_location_combination":
                result = await self._validate_location_combination(params)
                return result, {}
            # Semantic entity resolution (2026-01-25)
            elif tool_name == "resolve_entity":
                result = await self._resolve_entity(params, state)
                return result, {}
            # NEO4J V2 tools (2026-01-25)
            elif tool_name == "find_adjacent_parcels":
                result = await self._find_adjacent_parcels(params)
                return result, {}
            elif tool_name == "search_near_specific_poi":
                result = await self._search_near_specific_poi(params)
                return result, {}
            elif tool_name == "find_similar_by_graph":
                result = await self._find_similar_by_graph(params)
                return result, {}
            # V3 Sub-Agent Tools (2026-02-03)
            elif tool_name == "search_by_criteria":
                result = await self._search_by_criteria(params)
                return result, {}
            elif tool_name == "refine_search_preferences":
                return await self._refine_search_preferences(params)
            elif tool_name == "compare_parcels":
                result = await self._compare_parcels(params)
                return result, {}
            elif tool_name == "get_zoning_info":
                result = await self._get_zoning_info(params)
                return result, {}
            elif tool_name == "market_analysis":
                result = await self._market_analysis(params)
                return result, {}
            elif tool_name == "propose_filter_refinement":
                result = await self._propose_filter_refinement(params)
                return result, {}
            elif tool_name == "capture_contact_info":
                return await self._capture_contact_info(params)
            else:
                return {"error": f"Unknown tool: {tool_name}"}, {}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}, {}

    # =========================================================================
    # STATEFUL TOOLS (modify search state)
    # =========================================================================

    async def _propose_search_preferences(self, params: Dict[str, Any]) -> ToolResult:
        """Propose search preferences (perceived state)."""
        location_desc = params.get("location_description", "województwo pomorskie")
        gmina_param = params.get("gmina")
        miejscowosc_param = params.get("miejscowosc")
        powiat_param = params.get("powiat")

        # Smart location parsing
        try:
            gminy_names = await graph_service.get_all_gminy()
            gminy_lower = {g.lower(): g for g in gminy_names}

            # Fix: if miejscowosc is actually a gmina name, move it to gmina
            if miejscowosc_param and not gmina_param:
                miejscowosc_lower = miejscowosc_param.lower()
                if miejscowosc_lower in gminy_lower:
                    gmina_param = gminy_lower[miejscowosc_lower]
                    miejscowosc_param = None  # Clear - it was a gmina, not dzielnica

            # Parse location_description if needed
            if location_desc and not (gmina_param and miejscowosc_param and powiat_param):
                clean_loc = location_desc.lower()
                clean_loc = clean_loc.replace("okolice ", "").replace("gmina ", "").replace("powiat ", "")
                clean_loc = clean_loc.replace("miasto ", "").replace("m. ", "").replace("centrum ", "").strip()
                # Handle genitive forms (Gdyni -> Gdynia, Gdańska -> Gdańsk)
                if clean_loc.endswith("i"):
                    clean_loc_base = clean_loc[:-1] + "a"  # Gdyni -> Gdynia
                elif clean_loc.endswith("a"):
                    clean_loc_base = clean_loc[:-1]  # Gdańska -> Gdańsk
                else:
                    clean_loc_base = clean_loc

                # Try gmina first (more common)
                if not gmina_param:
                    for gmina_name in gminy_names:
                        clean_gmina = gmina_name.lower().replace("m. ", "")
                        if clean_loc == clean_gmina or clean_loc_base == clean_gmina:
                            gmina_param = gmina_name
                            break

                # Try dzielnica (district) - use resolve_location_v2 for semantic matching
                # UPDATED 2026-01-25: Use resolve_location_v2 with vector embeddings
                # This handles Matemblewo → Matarnia, VII Dwór → Oliwa/Wrzeszcz, etc.
                if not miejscowosc_param:
                    # Use resolve_location_v2 which uses semantic embeddings
                    resolved = await graph_service.resolve_location_v2(location_desc)
                    if resolved.get("resolved"):
                        # V2 returns richer information
                        confidence = resolved.get("confidence", "MEDIUM")

                        if resolved.get("maps_to_district"):
                            # It's a district - set both dzielnica and its parent gmina
                            miejscowosc_param = resolved["maps_to_district"]
                            if not gmina_param and resolved.get("maps_to_gmina"):
                                gmina_param = resolved["maps_to_gmina"]
                            logger.info(f"Resolved '{location_desc}' to district: {miejscowosc_param} in {gmina_param} (confidence: {confidence})")
                        elif resolved.get("search_in_districts") and len(resolved["search_in_districts"]) > 0:
                            # Location maps to multiple districts (e.g., VII Dwór → Oliwa, Wrzeszcz)
                            # Use first as primary, others as fallback
                            miejscowosc_param = resolved["search_in_districts"][0]
                            if not gmina_param and resolved.get("maps_to_gmina"):
                                gmina_param = resolved["maps_to_gmina"]
                            logger.info(f"Resolved '{location_desc}' to districts: {resolved['search_in_districts']} in {gmina_param}")
                        elif resolved.get("maps_to_gmina") and not gmina_param:
                            # It's a city/miejscowość - set as gmina
                            gmina_param = resolved["maps_to_gmina"]
                            logger.info(f"Resolved '{location_desc}' to city/gmina: {gmina_param}")

                # Try powiat as last resort
                if not powiat_param and not gmina_param and not miejscowosc_param:
                    powiaty = await spatial_service.get_powiaty()
                    for p in powiaty:
                        clean_powiat = p.lower().replace("m. ", "")
                        if clean_loc == clean_powiat or clean_powiat in clean_loc:
                            powiat_param = p
                            break
        except Exception:
            pass

        preferences = {
            "location_description": location_desc,
            "gmina": gmina_param,
            "miejscowosc": miejscowosc_param,
            "powiat": powiat_param,
            # NOTE: charakter_terenu removed - data is NULL for all parcels in Neo4j
            "lat": params.get("lat"),
            "lon": params.get("lon"),
            "radius_m": params.get("radius_m", 5000),
            # CHANGED 2026-01-25: No default area filters! Only use what user explicitly provided
            "min_area_m2": params.get("min_area_m2"),  # None if not provided
            "max_area_m2": params.get("max_area_m2"),  # None if not provided
            "area_category": params.get("area_category"),
            "quietness_categories": params.get("quietness_categories"),
            "building_density": params.get("building_density"),
            "min_dist_to_industrial_m": params.get("min_dist_to_industrial_m"),
            "nature_categories": params.get("nature_categories"),
            "max_dist_to_forest_m": params.get("max_dist_to_forest_m"),
            "max_dist_to_water_m": params.get("max_dist_to_water_m"),
            "min_forest_pct_500m": params.get("min_forest_pct_500m"),
            "accessibility_categories": params.get("accessibility_categories"),
            "max_dist_to_school_m": params.get("max_dist_to_school_m"),
            "max_dist_to_shop_m": params.get("max_dist_to_shop_m"),
            "max_dist_to_bus_stop_m": params.get("max_dist_to_bus_stop_m"),
            "max_dist_to_hospital_m": params.get("max_dist_to_hospital_m"),
            "has_road_access": params.get("has_road_access"),
            "requires_mpzp": params.get("requires_mpzp"),  # None = don't filter by MPZP
            "mpzp_buildable": params.get("mpzp_buildable"),
            "mpzp_symbols": params.get("mpzp_symbols"),
            "sort_by": params.get("sort_by", "quietness_score"),
            # Weights only when user mentioned the category (no defaults!)
            "quietness_weight": params.get("quietness_weight") if params.get("quietness_categories") else None,
            "nature_weight": params.get("nature_weight") if params.get("nature_categories") else None,
            "accessibility_weight": params.get("accessibility_weight") if params.get("accessibility_categories") else None,
            # NEO4J V2: New filters (2026-01-25)
            "ownership_type": params.get("ownership_type"),  # prywatna, publiczna, etc.
            "build_status": params.get("build_status"),  # zabudowana, niezabudowana
            "size_category": params.get("size_category"),  # mala, pod_dom, duza, bardzo_duza
            "pog_residential": params.get("pog_residential"),  # Only residential POG zones
        }

        # Build human-readable summary
        summary = {
            "lokalizacja": preferences["location_description"],
            "gmina": preferences["gmina"] or "dowolna",
        }
        if preferences["miejscowosc"]:
            summary["miejscowosc"] = preferences["miejscowosc"]
        # NOTE: charakter_terenu removed - data not available
        if preferences.get("lat") and preferences.get("lon"):
            radius = preferences.get("radius_m", 5000)
            summary["wyszukiwanie_przestrzenne"] = f"w promieniu {radius/1000:.1f}km od punktu"
        # CHANGED 2026-01-25: Only show area if explicitly provided
        if preferences.get("min_area_m2") or preferences.get("max_area_m2"):
            min_a = preferences.get("min_area_m2", 0)
            max_a = preferences.get("max_area_m2", "∞")
            summary["powierzchnia"] = f"{min_a}-{max_a} m²"

        # Environment preferences
        env_prefs = []
        if preferences["quietness_categories"]:
            env_prefs.append(f"cisza: {', '.join(preferences['quietness_categories'])}")
        if preferences["nature_categories"]:
            env_prefs.append(f"natura: {', '.join(preferences['nature_categories'])}")
        if preferences["building_density"]:
            env_prefs.append(f"zabudowa: {', '.join(preferences['building_density'])}")
        if env_prefs:
            summary["preferencje_środowiska"] = env_prefs

        # NEO4J V2: New filter summaries (2026-01-25)
        if preferences.get("ownership_type"):
            ownership_labels = {
                "prywatna": "prywatna (można kupić)",
                "publiczna": "publiczna",
                "spoldzielcza": "spółdzielcza",
                "koscielna": "kościelna",
                "inna": "inna"
            }
            summary["własność"] = ownership_labels.get(preferences["ownership_type"], preferences["ownership_type"])
        if preferences.get("build_status"):
            status_labels = {
                "niezabudowana": "niezabudowana (pod budowę)",
                "zabudowana": "zabudowana"
            }
            summary["status_zabudowy"] = status_labels.get(preferences["build_status"], preferences["build_status"])
        if preferences.get("size_category"):
            summary["kategoria_rozmiaru"] = ", ".join(preferences["size_category"])
        if preferences.get("pog_residential"):
            summary["tylko_mieszkaniowe_POG"] = "tak"

        result = {
            "status": "proposed",
            "message": "Preferencje zaproponowane. Poproś użytkownika o potwierdzenie.",
            "preferences": summary,
            "raw_preferences": preferences,
            "next_step": "Zapytaj: 'Czy te preferencje są poprawne?' i użyj approve_search_preferences po potwierdzeniu.",
        }

        state_updates = {
            "search_state.perceived_preferences": preferences,
            "search_state.preferences_proposed": True,
        }

        return result, state_updates

    async def _approve_search_preferences(self, params: Dict[str, Any]) -> ToolResult:
        """Approve proposed preferences (guard pattern)."""
        perceived = self._search_state.perceived_preferences

        if perceived is None:
            return {
                "error": "Brak zaproponowanych preferencji",
                "message": "Najpierw użyj propose_search_preferences aby zaproponować preferencje.",
                "hint": "Zapytaj użytkownika o lokalizację, powierzchnię i preferencje.",
            }, {}

        result = {
            "status": "approved",
            "message": "Preferencje zatwierdzone! Możesz teraz wykonać wyszukiwanie.",
            "approved_preferences": perceived,
            "next_step": "Użyj execute_search() aby wyszukać działki.",
        }

        state_updates = {
            "search_state.approved_preferences": perceived.copy(),
            "search_state.preferences_approved": True,
            "search_state.search_iteration": 0,
            "search_state.current_results": [],
        }

        return result, state_updates

    async def _modify_search_preferences(self, params: Dict[str, Any]) -> ToolResult:
        """Modify a specific field in perceived AND approved preferences."""
        perceived = self._search_state.perceived_preferences
        approved = self._search_state.approved_preferences

        if perceived is None and approved is None:
            return {
                "error": "Brak preferencji do modyfikacji",
                "message": "Najpierw użyj propose_search_preferences.",
            }, {}

        field = params["field"]
        new_value = params["new_value"]

        if new_value == 'null' or new_value == 'None':
            new_value = None

        state_updates = {}

        if perceived is not None:
            if field not in perceived:
                return {"error": f"Nieznane pole: {field}"}, {}
            perceived[field] = new_value
            state_updates["search_state.perceived_preferences"] = perceived

        if approved is not None:
            approved[field] = new_value
            state_updates["search_state.approved_preferences"] = approved
            return {
                "status": "modified_and_approved",
                "field": field,
                "new_value": new_value,
                "message": f"Zmieniono {field} na {new_value}. Preferencje są już zatwierdzone - możesz od razu wywołać execute_search.",
            }, state_updates

        return {
            "status": "modified",
            "field": field,
            "new_value": new_value,
            "message": f"Zmieniono {field} na {new_value}. Zapytaj o ponowne potwierdzenie.",
        }, state_updates

    async def _execute_search(self, params: Dict[str, Any]) -> ToolResult:
        """Execute search with approved preferences (guard pattern)."""
        approved = self._search_state.approved_preferences

        if approved is None:
            return {
                "error": "Brak zatwierdzonych preferencji",
                "message": "Najpierw zatwierdź preferencje używając approve_search_preferences.",
                "hint": "Flow: propose_search_preferences → user confirms → approve_search_preferences → execute_search",
            }, {}

        prefs = approved
        limit = params.get("limit", 10)

        search_prefs = SearchPreferences(
            gmina=prefs.get("gmina"),
            miejscowosc=prefs.get("miejscowosc"),
            powiat=prefs.get("powiat"),
            lat=prefs.get("lat"),
            lon=prefs.get("lon"),
            radius_m=prefs.get("radius_m", 5000),
            min_area=prefs.get("min_area_m2"),
            max_area=prefs.get("max_area_m2"),
            area_category=prefs.get("area_category"),
            # NOTE: charakter_terenu removed - data not available in Neo4j
            quietness_categories=prefs.get("quietness_categories"),
            building_density=prefs.get("building_density"),
            min_dist_to_industrial_m=prefs.get("min_dist_to_industrial_m"),
            nature_categories=prefs.get("nature_categories"),
            max_dist_to_forest_m=prefs.get("max_dist_to_forest_m"),
            max_dist_to_water_m=prefs.get("max_dist_to_water_m"),
            min_forest_pct_500m=prefs.get("min_forest_pct_500m"),
            accessibility_categories=prefs.get("accessibility_categories"),
            max_dist_to_school_m=prefs.get("max_dist_to_school_m"),
            max_dist_to_shop_m=prefs.get("max_dist_to_shop_m"),
            max_dist_to_bus_stop_m=prefs.get("max_dist_to_bus_stop_m"),
            max_dist_to_hospital_m=prefs.get("max_dist_to_hospital_m"),
            has_road_access=prefs.get("has_road_access"),
            has_mpzp=prefs.get("requires_mpzp"),
            mpzp_budowlane=prefs.get("mpzp_buildable"),
            mpzp_symbols=prefs.get("mpzp_symbols"),
            sort_by=prefs.get("sort_by", "quietness_score"),
            # Weights are None if user didn't mention the category
            quietness_weight=prefs.get("quietness_weight"),
            nature_weight=prefs.get("nature_weight"),
            accessibility_weight=prefs.get("accessibility_weight"),
            # NEO4J V2 filters (2026-01-25)
            ownership_type=prefs.get("ownership_type"),
            build_status=prefs.get("build_status"),
            size_category=prefs.get("size_category"),
            pog_residential=prefs.get("pog_residential"),
        )

        results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

        # If no results, run diagnostics and try auto-fallback
        diagnostics = None
        fallback_info = None
        if not results:
            diagnostics = await self._diagnose_empty_results(prefs)

            # Try auto-fallback if diagnostics suggest a relaxation
            if diagnostics.get("relaxation"):
                fallback_results, fallback_info = await self._auto_fallback_search(prefs, diagnostics, limit)
                if fallback_results:
                    # Use fallback results instead
                    iteration = self._search_state.search_iteration + 1

                    result = {
                        "status": "results_with_fallback",
                        "iteration": iteration,
                        "count": len(fallback_results),
                        "parcels": fallback_results,
                        "fallback_info": fallback_info,
                        "message": f"Nie znalazłem działek z oryginalnymi kryteriami. {fallback_info['change_description'].capitalize()}. Znalazłem {len(fallback_results)} działek.",
                        "original_diagnostics": diagnostics,
                    }

                    state_updates = {
                        "search_state.current_results": fallback_results,
                        "search_state.search_executed": True,
                        "search_state.results_shown": len(fallback_results),
                        "search_state.search_iteration": iteration,
                        "search_state.parcel_index_map": fallback_info.get("parcel_index_map", {}),
                    }

                    return result, state_updates

        current_results = []
        parcel_index_map = {}
        for idx, r in enumerate(results, 1):
            parcel_dict = {
                "index": idx,  # Position number for user reference
                "id": r.parcel_id,
                "gmina": r.gmina,
                "miejscowosc": r.miejscowosc,
                "area_m2": r.area_m2,
                "quietness_score": r.quietness_score,
                "nature_score": r.nature_score,
                "accessibility_score": r.accessibility_score,
                "has_mpzp": r.has_mpzp,
                "mpzp_symbol": r.mpzp_symbol,
                "centroid_lat": r.centroid_lat,
                "centroid_lon": r.centroid_lon,
                "dist_to_forest": r.dist_to_forest,
                "dist_to_water": r.dist_to_water,
                "dist_to_school": r.dist_to_school,
                "dist_to_shop": r.dist_to_shop,
                "pct_forest_500m": r.pct_forest_500m,
                "has_road_access": r.has_road_access,
            }
            parcel_dict["highlights"] = self._generate_highlights(parcel_dict, prefs)
            parcel_dict["explanation"] = self._generate_explanation(parcel_dict)
            current_results.append(parcel_dict)
            parcel_index_map[idx] = r.parcel_id

        iteration = self._search_state.search_iteration + 1

        result = {
            "status": "success",
            "iteration": iteration,
            "count": len(results),
            "parcels": current_results,
        }

        if diagnostics:
            result["diagnostics"] = diagnostics
            result["suggestion"] = diagnostics.get("suggestion", "Spróbuj poluzować kryteria wyszukiwania.")
        else:
            result["note"] = "Jeśli użytkownik nie jest zadowolony, użyj critique_search_results i refine_search."

        state_updates = {
            "search_state.current_results": current_results,
            "search_state.search_executed": True,
            "search_state.results_shown": len(current_results),
            "search_state.search_iteration": iteration,
            "search_state.parcel_index_map": parcel_index_map,
        }

        return result, state_updates

    async def _diagnose_empty_results(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Diagnose why search returned 0 results by testing filters incrementally."""
        try:
            location = prefs.get("miejscowosc") or prefs.get("gmina") or "Trójmiasto"
            diagnostics = {"location": location, "filters_tested": []}

            # Build base query conditions
            base_where = []
            params = {}

            if prefs.get("miejscowosc"):
                base_where.append("p.dzielnica = $dzielnica")
                params["dzielnica"] = prefs["miejscowosc"]
            elif prefs.get("gmina"):
                base_where.append("p.gmina = $gmina")
                params["gmina"] = prefs["gmina"]

            # Count total in location
            where_clause = " AND ".join(base_where) if base_where else "1=1"
            query = f"MATCH (p:Parcel) WHERE {where_clause} RETURN count(p) as cnt"

            results = await neo4j.run(query, params)
            total_in_location = results[0]["cnt"] if results else 0

            diagnostics["total_in_location"] = total_in_location

            if total_in_location == 0:
                diagnostics["blocking_filter"] = "location"
                diagnostics["message"] = f"Brak działek w lokalizacji '{location}'"
                diagnostics["suggestion"] = "Sprawdź nazwę dzielnicy lub wybierz inną lokalizację."
                return diagnostics

            # Test category filters with their distribution
            category_filters = [
                ("quietness_categories", "HAS_QUIETNESS", "QuietnessCategory", "cisza"),
                ("nature_categories", "HAS_NATURE", "NatureCategory", "natura"),
                ("building_density", "HAS_DENSITY", "DensityCategory", "gęstość zabudowy"),
                ("accessibility_categories", "HAS_ACCESS", "AccessCategory", "dostępność"),
            ]

            for filter_name, rel_name, node_type, polish_name in category_filters:
                if prefs.get(filter_name):
                    query = f"""
                        MATCH (p:Parcel)-[:{rel_name}]->(c:{node_type})
                        WHERE {where_clause}
                        RETURN c.id as category, count(p) as cnt
                        ORDER BY cnt DESC
                    """
                    records = await neo4j.run(query, params)
                    available_categories = {r["category"]: r["cnt"] for r in records}
                    requested = prefs.get(filter_name, [])
                    matching = sum(available_categories.get(cat, 0) for cat in requested)

                    diagnostics[f"{filter_name}_analysis"] = {
                        "requested": requested,
                        "available_in_location": available_categories,
                        "matching_count": matching
                    }

                    if matching == 0:
                        dominant = max(available_categories.items(), key=lambda x: x[1]) if available_categories else ("brak", 0)
                        diagnostics["blocking_filter"] = filter_name
                        diagnostics["message"] = f"W '{location}' nie ma działek z {polish_name}: {requested}. Dominuje: '{dominant[0]}' ({dominant[1]} działek)."

                        # Relaxation suggestions with DYNAMIC district names from database
                        if filter_name == "quietness_categories" and dominant[0] == "głośna":
                            # Get quiet districts dynamically instead of hardcoding
                            try:
                                quiet_districts = await graph_service.get_quiet_districts(
                                    gmina=prefs.get("gmina"),
                                    limit=3
                                )
                                if quiet_districts:
                                    district_names = ", ".join([d["name"] for d in quiet_districts])
                                    diagnostics["suggestion"] = f"'{location}' to głośna okolica. Rozważ cichsze dzielnice ({district_names})."
                                else:
                                    diagnostics["suggestion"] = f"'{location}' to głośna okolica. Spróbuj innej lokalizacji."
                            except Exception:
                                diagnostics["suggestion"] = f"'{location}' to głośna okolica. Spróbuj innej lokalizacji."
                            diagnostics["relaxation"] = {"quietness_categories": None}
                        else:
                            diagnostics["suggestion"] = f"Zmień kryterium {polish_name} na '{dominant[0]}' lub usuń filtr."
                            diagnostics["relaxation"] = {filter_name: [dominant[0]] if dominant[0] != "brak" else None}
                        return diagnostics

            # Check area filter
            if prefs.get("min_area_m2") or prefs.get("max_area_m2"):
                min_a = prefs.get("min_area_m2", 0)
                max_a = prefs.get("max_area_m2", 999999)
                query = f"""
                    MATCH (p:Parcel)
                    WHERE {where_clause} AND p.area_m2 >= $min_a AND p.area_m2 <= $max_a
                    RETURN count(p) as cnt
                """
                params["min_a"] = min_a
                params["max_a"] = max_a

                results = await neo4j.run(query, params)
                area_count = results[0]["cnt"] if results else 0

                diagnostics["area_filter_count"] = area_count

                if area_count == 0:
                    diagnostics["blocking_filter"] = "area"
                    diagnostics["message"] = f"Brak działek {min_a}-{max_a} m² w '{location}'."
                    diagnostics["suggestion"] = "Rozszerz zakres powierzchni."
                    # Relax by ±50%
                    diagnostics["relaxation"] = {
                        "min_area_m2": int(min_a * 0.5),
                        "max_area_m2": int(max_a * 1.5)
                    }
                    return diagnostics

            # Check distance filters
            distance_filters = [
                ("max_dist_to_forest_m", "dist_to_forest", "las"),
                ("max_dist_to_water_m", "dist_to_water", "woda"),
                ("max_dist_to_school_m", "dist_to_school", "szkoła"),
                ("max_dist_to_shop_m", "dist_to_supermarket", "sklep"),
            ]

            for filter_name, db_field, polish_name in distance_filters:
                if prefs.get(filter_name):
                    max_dist = prefs[filter_name]
                    query = f"""
                        MATCH (p:Parcel)
                        WHERE {where_clause} AND p.{db_field} <= $max_dist
                        RETURN count(p) as cnt
                    """
                    params["max_dist"] = max_dist

                    results = await neo4j.run(query, params)
                    dist_count = results[0]["cnt"] if results else 0

                    if dist_count == 0:
                        diagnostics["blocking_filter"] = filter_name
                        diagnostics["message"] = f"Brak działek w odległości {max_dist}m od {polish_name} w '{location}'."
                        diagnostics["suggestion"] = f"Zwiększ odległość do {polish_name} lub usuń filtr."
                        diagnostics["relaxation"] = {filter_name: max_dist * 2}
                        return diagnostics

            # Generic fallback - combination of filters is too restrictive
            diagnostics["blocking_filter"] = "combination"
            diagnostics["message"] = "Kombinacja wszystkich filtrów jest zbyt restrykcyjna."
            diagnostics["suggestion"] = "Poluzuj niektóre kryteria: cisza, zabudowa, lub odległości do POI."
            diagnostics["relaxation"] = None

            return diagnostics

        except Exception as e:
            logger.error(f"Diagnostics error: {e}")
            return {"error": str(e), "suggestion": "Spróbuj poluzować kryteria wyszukiwania."}

    async def _auto_fallback_search(
        self,
        prefs: Dict[str, Any],
        diagnostics: Dict[str, Any],
        limit: int = 10
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Auto-relax blocking filter and retry search.

        Args:
            prefs: Original preferences
            diagnostics: Diagnostics from _diagnose_empty_results
            limit: Max results

        Returns:
            Tuple of (results_list, fallback_info)
        """
        blocking = diagnostics.get("blocking_filter")
        relaxation = diagnostics.get("relaxation")

        if not blocking or blocking == "location" or not relaxation:
            # Can't auto-fallback for location issues or unknown blocks
            return [], {"auto_fallback_applied": False, "reason": "Cannot auto-relax this filter"}

        # Create new preferences with relaxed filter
        new_prefs = prefs.copy()
        change_descriptions = []

        for field, new_value in relaxation.items():
            old_value = prefs.get(field)
            new_prefs[field] = new_value

            if new_value is None:
                change_descriptions.append(f"usunięto filtr {field}")
            elif isinstance(new_value, list):
                change_descriptions.append(f"zmieniono {field} z {old_value} na {new_value}")
            else:
                change_descriptions.append(f"rozszerzono {field} z {old_value} do {new_value}")

        change_description = ", ".join(change_descriptions)

        # Build new SearchPreferences and execute
        search_prefs = SearchPreferences(
            gmina=new_prefs.get("gmina"),
            miejscowosc=new_prefs.get("miejscowosc"),
            powiat=new_prefs.get("powiat"),
            lat=new_prefs.get("lat"),
            lon=new_prefs.get("lon"),
            radius_m=new_prefs.get("radius_m", 5000),
            min_area=new_prefs.get("min_area_m2"),
            max_area=new_prefs.get("max_area_m2"),
            area_category=new_prefs.get("area_category"),
            quietness_categories=new_prefs.get("quietness_categories"),
            building_density=new_prefs.get("building_density"),
            min_dist_to_industrial_m=new_prefs.get("min_dist_to_industrial_m"),
            nature_categories=new_prefs.get("nature_categories"),
            max_dist_to_forest_m=new_prefs.get("max_dist_to_forest_m"),
            max_dist_to_water_m=new_prefs.get("max_dist_to_water_m"),
            min_forest_pct_500m=new_prefs.get("min_forest_pct_500m"),
            accessibility_categories=new_prefs.get("accessibility_categories"),
            max_dist_to_school_m=new_prefs.get("max_dist_to_school_m"),
            max_dist_to_shop_m=new_prefs.get("max_dist_to_shop_m"),
            max_dist_to_bus_stop_m=new_prefs.get("max_dist_to_bus_stop_m"),
            max_dist_to_hospital_m=new_prefs.get("max_dist_to_hospital_m"),
            has_road_access=new_prefs.get("has_road_access"),
            has_mpzp=new_prefs.get("requires_mpzp"),
            mpzp_budowlane=new_prefs.get("mpzp_buildable"),
            mpzp_symbols=new_prefs.get("mpzp_symbols"),
            sort_by=new_prefs.get("sort_by", "quietness_score"),
            quietness_weight=new_prefs.get("quietness_weight"),
            nature_weight=new_prefs.get("nature_weight"),
            accessibility_weight=new_prefs.get("accessibility_weight"),
        )

        results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

        fallback_info = {
            "auto_fallback_applied": True,
            "original_filter": blocking,
            "change_description": change_description,
            "original_prefs": {k: v for k, v in prefs.items() if k in relaxation},
            "new_prefs": {k: v for k, v in new_prefs.items() if k in relaxation},
            "results_count": len(results),
        }

        # Convert results to dicts with indexes
        result_dicts = []
        index_map = {}
        for idx, r in enumerate(results, 1):
            parcel_dict = {
                "index": idx,
                "id": r.parcel_id,
                "gmina": r.gmina,
                "miejscowosc": r.miejscowosc,
                "area_m2": r.area_m2,
                "quietness_score": r.quietness_score,
                "nature_score": r.nature_score,
                "accessibility_score": r.accessibility_score,
                "has_mpzp": r.has_mpzp,
                "mpzp_symbol": r.mpzp_symbol,
                "centroid_lat": r.centroid_lat,
                "centroid_lon": r.centroid_lon,
                "dist_to_forest": r.dist_to_forest,
                "dist_to_water": r.dist_to_water,
                "dist_to_school": r.dist_to_school,
                "dist_to_shop": r.dist_to_shop,
                "pct_forest_500m": r.pct_forest_500m,
                "has_road_access": r.has_road_access,
            }
            parcel_dict["highlights"] = self._generate_highlights(parcel_dict, new_prefs)
            parcel_dict["explanation"] = self._generate_explanation(parcel_dict)
            result_dicts.append(parcel_dict)
            index_map[idx] = r.parcel_id

        fallback_info["parcel_index_map"] = index_map
        return result_dicts, fallback_info

    async def _critique_search_results(self, params: Dict[str, Any]) -> ToolResult:
        """Record feedback about search results (Critic pattern)."""
        if not self._search_state.current_results:
            return {
                "error": "Brak wyników do oceny",
                "message": "Najpierw wykonaj wyszukiwanie (execute_search).",
            }, {}

        feedback = params["feedback"]
        problem_parcels = params.get("problem_parcels", [])

        result = {
            "status": "feedback_recorded",
            "feedback": feedback,
            "problem_parcels": problem_parcels,
            "current_iteration": self._search_state.search_iteration,
            "message": "Feedback zapisany. Użyj refine_search() aby poprawić wyniki.",
        }

        state_updates = {
            "search_state.search_feedback": feedback,
        }

        return result, state_updates

    async def _refine_search(self, params: Dict[str, Any]) -> ToolResult:
        """Refine search based on feedback (Critic pattern)."""
        if self._search_state.search_feedback is None:
            return {
                "error": "Brak feedbacku",
                "message": "Najpierw użyj critique_search_results aby zapisać feedback użytkownika.",
            }, {}

        approved = self._search_state.approved_preferences
        if approved is None:
            return {
                "error": "Brak zatwierdzonych preferencji",
                "message": "Brak podstawy do refinementu.",
            }, {}

        adjustment = params["adjustment"]
        prefs = approved.copy()
        adjustment_lower = adjustment.lower()

        # CHANGED 2026-01-25: Don't assume default area values
        min_area = prefs.get("min_area_m2") or 0
        max_area = prefs.get("max_area_m2") or 10000

        # Area adjustments
        if "większ" in adjustment_lower or "duż" in adjustment_lower:
            new_min = min_area * 1.5
            prefs["min_area_m2"] = new_min
            if new_min >= max_area:
                prefs["max_area_m2"] = new_min * 1.5

        if "mniejsz" in adjustment_lower or "mał" in adjustment_lower:
            new_max = max_area * 0.7
            prefs["max_area_m2"] = new_max
            if min_area >= new_max:
                prefs["min_area_m2"] = new_max * 0.5

        # Quietness adjustments
        if "cich" in adjustment_lower or "spok" in adjustment_lower:
            prefs["quietness_categories"] = ["bardzo_cicha", "cicha"]
            prefs["building_density"] = ["rzadka", "bardzo_rzadka"]

        # Nature adjustments
        if "natur" in adjustment_lower or "las" in adjustment_lower or "zielen" in adjustment_lower:
            prefs["nature_categories"] = ["bardzo_zielona", "zielona"]
            if not prefs.get("max_dist_to_forest_m"):
                prefs["max_dist_to_forest_m"] = 500

        # Accessibility adjustments
        if "dojazd" in adjustment_lower or "sklep" in adjustment_lower or "szkol" in adjustment_lower:
            prefs["accessibility_categories"] = ["doskonały", "dobry"]

        # Industrial distance
        if "przemysł" in adjustment_lower or "fabryk" in adjustment_lower or "hałas" in adjustment_lower:
            prefs["min_dist_to_industrial_m"] = (prefs.get("min_dist_to_industrial_m") or 500) + 500

        # MPZP adjustments
        if "mpzp" in adjustment_lower or "plan" in adjustment_lower:
            prefs["requires_mpzp"] = True

        # Safety check
        if prefs.get("min_area_m2", 0) > prefs.get("max_area_m2", 10000):
            prefs["min_area_m2"], prefs["max_area_m2"] = prefs["max_area_m2"], prefs["min_area_m2"]

        # Update state with refined preferences
        self._search_state.approved_preferences = prefs
        self._search_state.search_feedback = None

        # Re-run search with updated preferences
        search_result, search_updates = await self._execute_search({"limit": 10})

        # Merge state updates
        state_updates = {
            "search_state.approved_preferences": prefs,
            "search_state.search_feedback": None,
            **search_updates,
        }

        return search_result, state_updates

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _resolve_parcel_reference(self, ref: str) -> Optional[str]:
        """Resolve a parcel reference to actual parcel ID.

        Accepts:
        - Numeric string: "1", "2", "3" → looks up in parcel_index_map
        - Polish ordinal words: "pierwsza", "druga", "trzecia"
        - Already a parcel ID (contains "_") → returns as-is

        Args:
            ref: User's parcel reference

        Returns:
            Actual parcel ID or None if not found
        """
        if not ref:
            return None

        ref = ref.strip()

        # Already a parcel ID (contains underscore like "220611_2.0001.1234")
        if "_" in ref:
            return ref

        # Polish ordinal words
        ordinal_map = {
            "pierwsza": 1, "pierwszą": 1, "pierwszy": 1, "1.": 1,
            "druga": 2, "drugą": 2, "drugi": 2, "2.": 2,
            "trzecia": 3, "trzecią": 3, "trzeci": 3, "3.": 3,
            "czwarta": 4, "czwartą": 4, "czwarty": 4, "4.": 4,
            "piąta": 5, "piątą": 5, "piąty": 5, "5.": 5,
            "szósta": 6, "szóstą": 6, "szósty": 6, "6.": 6,
            "siódma": 7, "siódmą": 7, "siódmy": 7, "7.": 7,
            "ósma": 8, "ósmą": 8, "ósmy": 8, "8.": 8,
            "dziewiąta": 9, "dziewiątą": 9, "dziewiąty": 9, "9.": 9,
            "dziesiąta": 10, "dziesiątą": 10, "dziesiąty": 10, "10.": 10,
        }

        ref_lower = ref.lower()
        if ref_lower in ordinal_map:
            idx = ordinal_map[ref_lower]
            return self._search_state.parcel_index_map.get(idx)

        # Numeric string
        if ref.isdigit():
            idx = int(ref)
            return self._search_state.parcel_index_map.get(idx)

        # Not recognized - return as-is (might be a valid ID without underscore)
        return ref

    def _generate_highlights(self, parcel: Dict[str, Any], prefs: Dict[str, Any]) -> List[str]:
        """Generate highlight strings explaining why this parcel matches preferences."""
        highlights = []

        quietness = parcel.get("quietness_score", 0)
        if quietness and quietness >= 85:
            highlights.append(f"Cisza: {int(quietness)}/100")
        elif prefs.get("quietness_categories") and quietness and quietness >= 75:
            highlights.append(f"Cisza: {int(quietness)}/100")

        nature = parcel.get("nature_score", 0)
        if nature and nature >= 70:
            highlights.append(f"Natura: {int(nature)}/100")
        elif prefs.get("nature_categories") and nature and nature >= 60:
            highlights.append(f"Natura: {int(nature)}/100")

        dist_forest = parcel.get("dist_to_forest")
        if dist_forest is not None and dist_forest < 300:
            highlights.append(f"Las: {int(dist_forest)}m")
        elif prefs.get("max_dist_to_forest_m") and dist_forest and dist_forest <= prefs["max_dist_to_forest_m"]:
            highlights.append(f"Las: {int(dist_forest)}m")

        dist_water = parcel.get("dist_to_water")
        if prefs.get("max_dist_to_water_m") and dist_water and dist_water <= prefs["max_dist_to_water_m"]:
            highlights.append(f"Woda: {int(dist_water)}m")

        accessibility = parcel.get("accessibility_score", 0)
        if accessibility and accessibility >= 80:
            highlights.append(f"Dostępność: {int(accessibility)}/100")
        elif prefs.get("accessibility_categories") and accessibility and accessibility >= 70:
            highlights.append(f"Dostępność: {int(accessibility)}/100")

        dist_school = parcel.get("dist_to_school")
        if prefs.get("max_dist_to_school_m") and dist_school and dist_school <= prefs["max_dist_to_school_m"]:
            highlights.append(f"Szkoła: {int(dist_school)}m")

        dist_shop = parcel.get("dist_to_shop")
        if prefs.get("max_dist_to_shop_m") and dist_shop and dist_shop <= prefs["max_dist_to_shop_m"]:
            highlights.append(f"Sklep: {int(dist_shop)}m")

        if prefs.get("has_road_access") and parcel.get("has_road_access"):
            if len(highlights) < 3:
                highlights.append("Dostęp do drogi")

        if parcel.get("has_mpzp"):
            symbol = parcel.get("mpzp_symbol", "")
            if symbol:
                highlights.append(f"MPZP: {symbol}")
            else:
                highlights.append("Ma MPZP")

        # Only show weighted highlights if user explicitly set the weight
        if (prefs.get("quietness_weight") or 0) >= 0.5 and quietness and quietness >= 80:
            if not any("Cisza" in h for h in highlights):
                highlights.append("Cicha okolica")

        if (prefs.get("nature_weight") or 0) >= 0.5 and nature and nature >= 70:
            if not any("Natura" in h for h in highlights):
                highlights.append("Blisko natury")

        return highlights[:2]

    def _generate_explanation(self, parcel: Dict[str, Any]) -> str:
        """Generate a short explanation for the parcel."""
        parts = []
        miejscowosc = parcel.get("miejscowosc")
        gmina = parcel.get("gmina")
        area = parcel.get("area_m2")

        if miejscowosc:
            parts.append(miejscowosc)
        elif gmina:
            parts.append(gmina)

        if area:
            parts.append(f"{int(area):,} m²".replace(",", " "))

        return ", ".join(parts)

    # =========================================================================
    # STATELESS TOOLS (delegate to services)
    # =========================================================================

    async def _find_similar_parcels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find parcels similar to a reference parcel."""
        raw_ref = params["parcel_id"]
        parcel_id = self._resolve_parcel_reference(raw_ref)

        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        limit = params.get("limit", 5)

        results = await vector_service.search_similar(parcel_id=parcel_id, top_k=limit)

        return {
            "reference_parcel": parcel_id,
            "resolved_from": raw_ref if raw_ref != parcel_id else None,
            "count": len(results),
            "similar_parcels": [
                {
                    "id": r.parcel_id,
                    "similarity_score": round(r.similarity_score, 3),
                    "gmina": r.gmina,
                    "area_m2": r.area_m2,
                    "quietness_score": r.quietness_score,
                }
                for r in results
            ]
        }

    async def _get_parcel_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed info about a parcel."""
        raw_ref = params["parcel_id"]
        parcel_id = self._resolve_parcel_reference(raw_ref)

        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        details = await spatial_service.get_parcel_details(parcel_id, include_geometry=False)

        if details:
            return {"parcel": details, "resolved_from": raw_ref if raw_ref != parcel_id else None}
        else:
            return {"error": f"Działka nie znaleziona: {parcel_id}"}

    async def _get_gmina_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get info about a gmina."""
        gmina_name = params["gmina_name"]
        info = await graph_service.get_gmina_info(gmina_name)

        if info:
            miejscowosci = await graph_service.get_miejscowosci_in_gmina(gmina_name)
            return {
                "gmina": info.name,
                "powiat": info.powiat,
                "parcel_count": info.parcel_count,
                "avg_area_m2": round(info.avg_area, 1) if info.avg_area else None,
                "pct_with_mpzp": round(info.pct_with_mpzp, 1) if info.pct_with_mpzp else None,
                "miejscowosci": [m["name"] for m in miejscowosci[:15]],
            }
        else:
            return {"error": f"Gmina nie znaleziona: {gmina_name}"}

    async def _list_gminy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all gminy."""
        gminy = await graph_service.get_all_gminy()
        return {"count": len(gminy), "gminy": gminy}

    async def _count_matching_parcels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Count parcels matching criteria."""
        count = await spatial_service.count_parcels(
            gmina=params.get("gmina"),
            has_mpzp=params.get("has_mpzp"),
        )
        return {"count": count, "filters": params}

    async def _count_matching_parcels_quick(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Quick count based on current perceived preferences - for checkpoint searches.

        Uses perceived_preferences from state if no params provided.
        Useful for showing users how many parcels match their evolving criteria.
        """
        # Merge state preferences with any additional params
        prefs = {}
        if self._search_state.perceived_preferences:
            prefs = self._search_state.perceived_preferences.copy()
        prefs.update(params)

        # Build query conditions
        conditions = []
        query_params = {}

        if prefs.get("gmina"):
            conditions.append("p.gmina = $gmina")
            query_params["gmina"] = prefs["gmina"]

        if prefs.get("miejscowosc"):
            conditions.append("p.dzielnica = $dzielnica")
            query_params["dzielnica"] = prefs["miejscowosc"]

        if prefs.get("min_area_m2"):
            conditions.append("p.area_m2 >= $min_area")
            query_params["min_area"] = prefs["min_area_m2"]

        if prefs.get("max_area_m2"):
            conditions.append("p.area_m2 <= $max_area")
            query_params["max_area"] = prefs["max_area_m2"]

        if prefs.get("requires_mpzp"):
            conditions.append("p.pog_symbol IS NOT NULL")

        if prefs.get("mpzp_buildable"):
            conditions.append("p.is_residential_zone = true")

        # Build simple count query (no category joins for speed)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"MATCH (p:Parcel) WHERE {where_clause} RETURN count(p) as cnt"

        try:
            results = await neo4j.run(query, query_params)
            count = results[0]["cnt"] if results else 0

            # Build human-readable criteria summary
            criteria_summary = []
            if prefs.get("gmina"):
                criteria_summary.append(f"gmina: {prefs['gmina']}")
            if prefs.get("miejscowosc"):
                criteria_summary.append(f"dzielnica: {prefs['miejscowosc']}")
            if prefs.get("min_area_m2") or prefs.get("max_area_m2"):
                min_a = prefs.get("min_area_m2", 0)
                max_a = prefs.get("max_area_m2", "∞")
                criteria_summary.append(f"powierzchnia: {min_a}-{max_a} m²")
            if prefs.get("quietness_categories"):
                criteria_summary.append(f"cisza: {', '.join(prefs['quietness_categories'])}")
            if prefs.get("nature_categories"):
                criteria_summary.append(f"natura: {', '.join(prefs['nature_categories'])}")

            return {
                "matching_count": count,
                "criteria_used": prefs,
                "criteria_summary": criteria_summary,
                "message": f"Na podstawie aktualnych kryteriów: **{count:,}** pasujących działek.".replace(",", " "),
                "note": "To szybkie zliczenie - pełne wyszukiwanie może uwzględnić więcej filtrów.",
            }
        except Exception as e:
            logger.error(f"Quick count error: {e}")
            return {"error": str(e), "matching_count": 0}

    async def _get_mpzp_symbols(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get MPZP symbol definitions."""
        symbols = await graph_service.get_mpzp_symbols()
        return {
            "count": len(symbols),
            "symbols": [
                {
                    "kod": s.symbol,
                    "nazwa": s.nazwa,
                    "budowlany": s.budowlany,
                    "parcel_count": s.parcel_count,
                }
                for s in symbols
            ]
        }

    async def _explore_administrative_hierarchy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Explore administrative hierarchy."""
        level = params["level"]
        parent_name = params.get("parent_name")

        results = await graph_service.get_children_in_hierarchy(level, parent_name)

        if not results:
            if level == "powiat" and not parent_name:
                return {"error": "Podaj nazwę powiatu (parent_name) aby zobaczyć gminy"}
            if level == "gmina" and not parent_name:
                return {"error": "Podaj nazwę gminy (parent_name) aby zobaczyć miejscowości"}
            return {"error": f"Nie znaleziono danych dla level={level}, parent={parent_name}"}

        if level == "wojewodztwo":
            summary = f"W województwie pomorskim jest {len(results)} powiatów"
            items = [
                f"{r['name']} ({r.get('gminy_count', 0)} gmin, {r.get('parcel_count', 0):,} działek)"
                for r in results
            ]
        elif level == "powiat":
            summary = f"W powiecie {parent_name} jest {len(results)} gmin"
            items = [f"{r['name']} ({r.get('parcel_count', 0):,} działek)" for r in results]
        else:
            summary = f"W gminie {parent_name} jest {len(results)} miejscowości"
            items = [
                f"{r['name']} ({r.get('rodzaj', 'wieś')}, {r.get('parcel_count', 0):,} działek)"
                for r in results[:20]
            ]
            if len(results) > 20:
                items.append(f"... i {len(results) - 20} więcej")

        return {
            "level": level,
            "parent": parent_name,
            "count": len(results),
            "summary": summary,
            "items": items,
            "raw_data": results[:30],
        }

    async def _get_parcel_neighborhood(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed neighborhood context for a parcel."""
        raw_ref = params["parcel_id"]
        parcel_id = self._resolve_parcel_reference(raw_ref)

        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        result = await graph_service.get_parcel_neighborhood(parcel_id)

        if "error" in result:
            return result

        poi_summary = []
        if result.get("dist_to_school"):
            poi_summary.append(f"Szkoła: {int(result['dist_to_school'])}m")
        if result.get("dist_to_shop"):
            poi_summary.append(f"Sklep: {int(result['dist_to_shop'])}m")
        if result.get("dist_to_hospital"):
            poi_summary.append(f"Szpital: {int(result['dist_to_hospital'])}m")
        if result.get("dist_to_bus_stop"):
            poi_summary.append(f"Przystanek: {int(result['dist_to_bus_stop'])}m")

        nature_summary = []
        if result.get("dist_to_forest"):
            nature_summary.append(f"Las: {int(result['dist_to_forest'])}m")
        if result.get("dist_to_water"):
            nature_summary.append(f"Woda: {int(result['dist_to_water'])}m")
        if result.get("pct_forest_500m"):
            nature_summary.append(f"Las w 500m: {round(result['pct_forest_500m'] * 100, 1)}%")

        environment = []
        if result.get("dist_to_industrial"):
            environment.append(f"Przemysł: {int(result['dist_to_industrial'])}m")
        if result.get("count_buildings_500m"):
            environment.append(f"Budynki w 500m: {result['count_buildings_500m']}")

        return {
            "parcel_id": parcel_id,
            "area_m2": result.get("area_m2"),
            "location": {
                "gmina": result.get("gmina"),
                "miejscowosc": result.get("miejscowosc"),
                "powiat": result.get("powiat"),
                "charakter": result.get("charakter_terenu"),
            },
            "scores": {
                "quietness": result.get("quietness_score"),
                "nature": result.get("nature_score"),
                "accessibility": result.get("accessibility_score"),
            },
            "categories": {
                "cisza": result.get("kategoria_ciszy"),
                "natura": result.get("kategoria_natury"),
                "dostep": result.get("kategoria_dostepu"),
                "zabudowa": result.get("gestosc_zabudowy"),
            },
            "mpzp": {
                "has_mpzp": result.get("has_mpzp"),
                "symbol": result.get("mpzp_symbol"),
                "nazwa": result.get("mpzp_nazwa"),
                "budowlany": result.get("mpzp_budowlany"),
            },
            "poi_distances": poi_summary,
            "nature_distances": nature_summary,
            "environment": environment,
            "summary": result.get("summary", []),
            "coordinates": {"lat": result.get("lat"), "lon": result.get("lon")},
        }

    async def _get_area_statistics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics for a gmina or powiat."""
        gmina = params.get("gmina")
        powiat = params.get("powiat")

        result = await graph_service.get_area_category_stats(gmina=gmina, powiat=powiat)

        if "error" in result:
            return result

        quietness_summary = []
        for item in result.get("quietness_distribution", []):
            if item.get("category") and item.get("count"):
                quietness_summary.append(f"{item['category']}: {item['count']:,}")

        nature_summary = []
        for item in result.get("nature_distribution", []):
            if item.get("category") and item.get("count"):
                nature_summary.append(f"{item['category']}: {item['count']:,}")

        character_summary = []
        for item in result.get("character_distribution", []):
            if item.get("category") and item.get("count"):
                character_summary.append(f"{item['category']}: {item['count']:,}")

        location_desc = gmina or powiat or "całe województwo"

        return {
            "location": location_desc,
            "total_parcels": result.get("total_parcels", 0),
            "with_mpzp": result.get("with_mpzp", 0),
            "pct_mpzp": result.get("pct_mpzp", 0),
            "with_road_access": result.get("with_road_access", 0),
            "pct_road_access": result.get("pct_road_access", 0),
            "quietness_distribution": quietness_summary,
            "nature_distribution": nature_summary,
            "character_distribution": character_summary,
            "summary": f"W {location_desc}: {result.get('total_parcels', 0):,} działek, "
                       f"{result.get('pct_mpzp', 0)}% z MPZP, "
                       f"{result.get('pct_road_access', 0)}% z dostępem do drogi",
        }

    async def _find_by_mpzp_symbol(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find parcels by MPZP symbol."""
        symbol = params["symbol"]
        gmina = params.get("gmina")
        limit = params.get("limit", 20)

        results = await graph_service.find_parcels_by_mpzp(symbol, gmina=gmina, limit=limit)

        if not results:
            location_info = f" w gminie {gmina}" if gmina else ""
            return {
                "symbol": symbol,
                "count": 0,
                "message": f"Nie znaleziono działek z symbolem {symbol}{location_info}",
            }

        parcels = []
        for r in results:
            parcels.append({
                "id": r.get("id"),
                "area_m2": r.get("area_m2"),
                "gmina": r.get("gmina"),
                "quietness": r.get("quietness"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
            })

        location_info = f" w gminie {gmina}" if gmina else ""

        return {
            "symbol": symbol,
            "count": len(results),
            "message": f"Znaleziono {len(results)} działek z symbolem {symbol}{location_info}",
            "parcels": parcels,
        }

    async def _search_around_point(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search parcels within radius of a point using PostGIS."""
        lat = params["lat"]
        lon = params["lon"]
        radius_m = min(params.get("radius_m", 5000), 20000)
        limit = params.get("limit", 20)

        if not (49.0 <= lat <= 55.0 and 14.0 <= lon <= 24.0):
            return {"error": f"Współrzędne poza Polską: ({lat}, {lon})"}

        search_params = SpatialSearchParams(
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            min_area=params.get("min_area"),
            max_area=params.get("max_area"),
            has_mpzp=params.get("has_mpzp"),
            limit=limit,
        )

        results = await spatial_service.search_by_radius(search_params)

        if not results:
            return {
                "count": 0,
                "message": f"Nie znaleziono działek w promieniu {radius_m/1000:.1f}km od punktu ({lat:.4f}, {lon:.4f})",
                "search_params": {"lat": lat, "lon": lon, "radius_m": radius_m},
            }

        parcels = []
        for r in results:
            parcels.append({
                "id": r.get("id_dzialki"),
                "gmina": r.get("gmina"),
                "miejscowosc": r.get("miejscowosc"),
                "area_m2": r.get("area_m2"),
                "distance_m": round(r.get("distance_m", 0)),
                "quietness_score": r.get("quietness_score"),
                "nature_score": r.get("nature_score"),
                "has_mpzp": r.get("has_mpzp"),
                "mpzp_symbol": r.get("mpzp_symbol"),
                "lat": r.get("centroid_lat"),
                "lon": r.get("centroid_lon"),
            })

        return {
            "count": len(results),
            "message": f"Znaleziono {len(results)} działek w promieniu {radius_m/1000:.1f}km",
            "search_center": {"lat": lat, "lon": lon},
            "radius_m": radius_m,
            "parcels": parcels,
        }

    async def _search_in_bbox(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search parcels in bounding box using PostGIS."""
        min_lat = params["min_lat"]
        min_lon = params["min_lon"]
        max_lat = params["max_lat"]
        max_lon = params["max_lon"]
        limit = params.get("limit", 50)

        if min_lat >= max_lat or min_lon >= max_lon:
            return {"error": "Nieprawidłowy bounding box: min musi być mniejsze od max"}

        if not (49.0 <= min_lat <= 55.0 and 14.0 <= min_lon <= 24.0):
            return {"error": "Bounding box poza Polską"}

        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon
        if lat_diff > 0.5 or lon_diff > 0.7:
            return {"error": "Bounding box za duży. Maksymalnie ~50km x 50km."}

        search_params = BBoxSearchParams(
            min_lat=min_lat,
            min_lon=min_lon,
            max_lat=max_lat,
            max_lon=max_lon,
            limit=limit,
        )

        results = await spatial_service.search_by_bbox(search_params)

        if not results:
            return {
                "count": 0,
                "message": "Nie znaleziono działek w zaznaczonym obszarze",
                "bbox": {"min_lat": min_lat, "min_lon": min_lon, "max_lat": max_lat, "max_lon": max_lon},
            }

        parcels = []
        for r in results:
            parcels.append({
                "id": r.get("id_dzialki"),
                "gmina": r.get("gmina"),
                "miejscowosc": r.get("miejscowosc"),
                "area_m2": r.get("area_m2"),
                "quietness_score": r.get("quietness_score"),
                "nature_score": r.get("nature_score"),
                "has_mpzp": r.get("has_mpzp"),
                "mpzp_symbol": r.get("mpzp_symbol"),
                "lat": r.get("centroid_lat"),
                "lon": r.get("centroid_lon"),
            })

        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        return {
            "count": len(results),
            "message": f"Znaleziono {len(results)} działek w zaznaczonym obszarze",
            "bbox": {"min_lat": min_lat, "min_lon": min_lon, "max_lat": max_lat, "max_lon": max_lon},
            "center": {"lat": center_lat, "lon": center_lon},
            "parcels": parcels,
        }

    async def _generate_map_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate GeoJSON for map display."""
        raw_ids = params["parcel_ids"]

        if not raw_ids:
            return {"error": "No parcel IDs provided"}

        # Resolve all references to actual IDs
        parcel_ids = []
        for raw_ref in raw_ids:
            resolved = self._resolve_parcel_reference(str(raw_ref))
            if resolved:
                parcel_ids.append(resolved)

        if not parcel_ids:
            return {"error": "Nie udało się rozwiązać żadnego ID działki"}

        parcels = await spatial_service.get_parcels_by_ids(parcel_ids, include_geometry=True)

        if not parcels:
            return {"error": "No parcels found"}

        features = []
        for p in parcels:
            if p.get("geojson"):
                feature = {
                    "type": "Feature",
                    "geometry": json.loads(p["geojson"]),
                    "properties": {
                        "id": p["id_dzialki"],
                        "gmina": p.get("gmina"),
                        "area_m2": p.get("area_m2"),
                        "quietness_score": p.get("quietness_score"),
                        "has_mpzp": p.get("has_mpzp"),
                    }
                }
                features.append(feature)

        lats = [p.get("centroid_lat") for p in parcels if p.get("centroid_lat")]
        lons = [p.get("centroid_lon") for p in parcels if p.get("centroid_lon")]
        center_lat = sum(lats) / len(lats) if lats else None
        center_lon = sum(lons) / len(lons) if lons else None

        return {
            "geojson": {"type": "FeatureCollection", "features": features},
            "center": {"lat": center_lat, "lon": center_lon},
            "parcel_count": len(features),
        }

    async def _get_district_prices(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get price information for a district."""
        from app.engine.price_data import DISTRICT_PRICES, SEGMENT_DESCRIPTIONS

        city = params.get("city", "").strip()
        district = params.get("district")

        if not city:
            return {"error": "Podaj miasto (Gdańsk, Gdynia, Sopot)"}

        city_normalized = city.title()
        if city_normalized.startswith("M. "):
            city_normalized = city_normalized[3:]

        key = (city_normalized, district)
        if key not in DISTRICT_PRICES:
            key = (city_normalized, None)

        if key not in DISTRICT_PRICES:
            for (c, d), data in DISTRICT_PRICES.items():
                if c.lower() == city_normalized.lower():
                    if district and d and d.lower() == district.lower():
                        key = (c, d)
                        break

        if key not in DISTRICT_PRICES:
            return {
                "error": f"Brak danych cenowych dla {city}/{district or 'średnia'}",
                "available_cities": ["Gdańsk", "Gdynia", "Sopot"],
                "hint": "Podaj nazwę dzielnicy lub pomiń aby uzyskać średnią dla miasta",
            }

        data = DISTRICT_PRICES[key]
        segment = data["segment"]

        return {
            "city": key[0],
            "district": key[1] or "średnia dla miasta",
            "price_per_m2_min": data["min"],
            "price_per_m2_max": data["max"],
            "price_range": f"{data['min']}-{data['max']} zł/m²",
            "segment": segment,
            "segment_description": SEGMENT_DESCRIPTIONS.get(segment, ""),
            "description": data["desc"],
            "example_1000m2": f"{data['min'] * 1000 // 1000}k-{data['max'] * 1000 // 1000}k zł",
            "note": "To są orientacyjne ceny rynkowe, nie ceny konkretnych ofert.",
        }

    async def _estimate_parcel_value(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate parcel value based on location and area."""
        from app.engine.price_data import DISTRICT_PRICES, SEGMENT_DESCRIPTIONS

        city = params.get("city", "").strip()
        district = params.get("district")
        area_m2 = params.get("area_m2")

        if not city:
            return {"error": "Podaj miasto (Gdańsk, Gdynia, Sopot)"}
        if not area_m2 or area_m2 <= 0:
            return {"error": "Podaj powierzchnię działki w m²"}

        city_normalized = city.title()
        if city_normalized.startswith("M. "):
            city_normalized = city_normalized[3:]

        key = (city_normalized, district)
        if key not in DISTRICT_PRICES:
            key = (city_normalized, None)

        if key not in DISTRICT_PRICES:
            for (c, d), data in DISTRICT_PRICES.items():
                if c.lower() == city_normalized.lower():
                    if district and d and d.lower() == district.lower():
                        key = (c, d)
                        break

        if key not in DISTRICT_PRICES:
            return {
                "error": f"Brak danych cenowych dla {city}/{district or 'średnia'}",
                "hint": "Podaj nazwę dzielnicy lub pomiń aby uzyskać średnią dla miasta",
            }

        data = DISTRICT_PRICES[key]
        price_min = int(area_m2 * data["min"])
        price_max = int(area_m2 * data["max"])
        segment = data["segment"]

        def format_price(p):
            if p >= 1_000_000:
                return f"{p / 1_000_000:.2f} mln zł"
            else:
                return f"{p // 1000}k zł"

        confidence = "HIGH" if key[1] else "MEDIUM"

        return {
            "city": key[0],
            "district": key[1] or "średnia dla miasta",
            "area_m2": area_m2,
            "price_per_m2_min": data["min"],
            "price_per_m2_max": data["max"],
            "estimated_value_min": price_min,
            "estimated_value_max": price_max,
            "estimated_range": f"{format_price(price_min)} - {format_price(price_max)}",
            "segment": segment,
            "segment_description": SEGMENT_DESCRIPTIONS.get(segment, ""),
            "confidence": confidence,
            "note": "To jest ORIENTACYJNA wycena na podstawie średnich cen w dzielnicy. "
                    "Faktyczna cena zależy od: kształtu działki, uzbrojenia, MPZP, dostępu do drogi.",
        }

    async def _search_by_water_type(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for parcels near a specific type of water."""
        water_type = params.get("water_type")
        if not water_type:
            return {"error": "Podaj typ wody (morze, jezioro, rzeka, kanal, staw)"}

        valid_types = ["morze", "jezioro", "rzeka", "kanal", "staw"]
        if water_type not in valid_types:
            return {"error": f"Nieznany typ wody. Dostępne: {', '.join(valid_types)}"}

        max_distance = params.get("max_distance", 500)
        city = params.get("city")
        min_area = params.get("min_area")
        max_area = params.get("max_area")
        is_built = params.get("is_built")
        is_residential_zone = params.get("is_residential_zone")
        limit = params.get("limit", 10)

        results = await graph_service.search_parcels_by_water_type(
            water_type=water_type,
            max_distance=max_distance,
            city=city,
            min_area=min_area,
            max_area=max_area,
            is_built=is_built,
            is_residential_zone=is_residential_zone,
            limit=limit
        )

        if not results:
            return {
                "count": 0,
                "results": [],
                "message": f"Nie znaleziono działek blisko {water_type} (max {max_distance}m)" +
                          (f" w {city}" if city else ""),
                "hint": "Spróbuj zwiększyć max_distance lub zmienić kryteria"
            }

        water_info = {
            "morze": {"name_pl": "Morza Bałtyckiego", "premium": "+50-100%"},
            "jezioro": {"name_pl": "jeziora", "premium": "+20-40%"},
            "rzeka": {"name_pl": "rzeki", "premium": "+10-20%"},
            "kanal": {"name_pl": "kanału", "premium": "+5-10%"},
            "staw": {"name_pl": "stawu/oczka", "premium": "+5%"},
        }

        return {
            "water_type": water_type,
            "water_type_info": water_info.get(water_type, {}),
            "max_distance": max_distance,
            "city": city,
            "count": len(results),
            "results": results,
            "note": f"Działki w odległości do {max_distance}m od {water_info.get(water_type, {}).get('name_pl', water_type)}. "
                   f"Bliskość wody dodaje {water_info.get(water_type, {}).get('premium', '')} do wartości."
        }

    async def _get_water_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about water bodies near a parcel."""
        raw_ref = params.get("parcel_id")
        if not raw_ref:
            return {"error": "Podaj ID działki (parcel_id)"}

        parcel_id = self._resolve_parcel_reference(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        result = await graph_service.get_water_near_parcel(parcel_id)

        if "error" in result:
            return result

        return result

    async def _get_parcel_full_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get full context for a parcel including all features."""
        raw_ref = params.get("parcel_id")
        if not raw_ref:
            return {"error": "Podaj ID działki (parcel_id)"}

        parcel_id = self._resolve_parcel_reference(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        result = await graph_service.get_parcel_full_context(parcel_id)

        if "error" in result:
            return result

        return result

    # =========================================================================
    # DYNAMIC LOCATION TOOLS (2026-01-25)
    # Agent dynamically queries these instead of hardcoded lists
    # =========================================================================

    async def _get_available_locations(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get available locations dynamically from the database.

        Agent uses this at conversation start or when user gives ambiguous location.
        Returns miejscowości and gminy separately (in MVP they're the same).
        """
        try:
            result = await graph_service.get_available_locations()
            if "error" in result:
                return result

            return {
                "miejscowosci": result.get("miejscowosci", []),
                "gminy": result.get("gminy", []),
                "total_parcels": result.get("total_parcels", 0),
                "by_miejscowosc": result.get("by_miejscowosc", {}),
                "hint": result.get("hint", "Podaj miejscowość lub dzielnicę."),
                "note": "Użyj resolve_location() aby zwalidować tekst lokalizacji od użytkownika.",
            }
        except Exception as e:
            logger.error(f"Get available locations error: {e}")
            return {"error": str(e)}

    async def _get_districts_in_miejscowosc(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get districts in a given MIEJSCOWOŚĆ (not gmina!).

        IMPORTANT: Dzielnica belongs to MIEJSCOWOŚĆ, not to gmina!
        In Trójmiasto MVP: gmina = miejscowość.
        """
        miejscowosc = params.get("miejscowosc")
        if not miejscowosc:
            return {"error": "Podaj miejscowość (np. 'Gdańsk', 'Gdynia', 'Sopot')"}

        try:
            result = await graph_service.get_districts_in_miejscowosc(miejscowosc)
            if "error" in result:
                return result

            return {
                "miejscowosc": result.get("miejscowosc"),
                "gmina": result.get("gmina"),
                "district_count": result.get("district_count", 0),
                "parcel_count": result.get("parcel_count", 0),
                "districts": result.get("districts", []),
                "by_district": result.get("by_district", {}),
                "note": "Dzielnica należy do MIEJSCOWOŚCI, nie do gminy!",
            }
        except Exception as e:
            logger.error(f"Get districts in miejscowosc error: {e}")
            return {"error": str(e)}

    async def _resolve_location(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve user's location text to gmina + miejscowosc + dzielnica.

        CRITICAL: Agent MUST use this before propose_search_preferences!
        Automatically detects whether input is miejscowość or dzielnica.
        """
        location_text = params.get("location_text")
        if not location_text:
            return {"error": "Podaj tekst lokalizacji (location_text)"}

        try:
            result = await graph_service.resolve_location(location_text)

            if result.get("resolved"):
                return {
                    "resolved": True,
                    "gmina": result.get("gmina"),
                    "miejscowosc": result.get("miejscowosc"),
                    "dzielnica": result.get("dzielnica"),
                    "parcel_count": result.get("parcel_count", 0),
                    "original_input": location_text,
                    "note": "Użyj tych wartości w propose_search_preferences.",
                }
            else:
                return {
                    "resolved": False,
                    "error": result.get("error", f"Nie rozpoznano lokalizacji: {location_text}"),
                    "available_miejscowosci": result.get("available_miejscowosci", []),
                    "hint": result.get("hint", "Podaj nazwę miasta lub dzielnicy."),
                    "original_input": location_text,
                }
        except Exception as e:
            logger.error(f"Resolve location error: {e}")
            return {"resolved": False, "error": str(e)}

    async def _validate_location_combination(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if miejscowość + dzielnica combination is correct.

        IMPORTANT: Dzielnica belongs to MIEJSCOWOŚĆ, not to gmina!
        Use this when user provides miasto and dzielnica separately.
        """
        miejscowosc = params.get("miejscowosc")
        dzielnica = params.get("dzielnica")
        gmina = params.get("gmina")

        if not dzielnica:
            return {"error": "Podaj dzielnicę do walidacji"}

        try:
            result = await graph_service.validate_location_combination(
                miejscowosc=miejscowosc,
                dzielnica=dzielnica,
                gmina=gmina
            )

            if result.get("valid"):
                return {
                    "valid": True,
                    "miejscowosc": result.get("miejscowosc"),
                    "dzielnica": result.get("dzielnica"),
                    "gmina": result.get("gmina"),
                    "parcel_count": result.get("parcel_count", 0),
                    "message": f"Kombinacja poprawna: {result.get('dzielnica')} w {result.get('miejscowosc')}",
                }
            else:
                return {
                    "valid": False,
                    "error": result.get("error"),
                    "suggestion": result.get("suggestion"),
                    "note": "Dzielnica należy do MIEJSCOWOŚCI, nie do gminy!",
                }
        except Exception as e:
            logger.error(f"Validate location combination error: {e}")
            return {"valid": False, "error": str(e)}

    async def _resolve_entity(self, params: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Universal entity resolution using semantic vector search.

        Resolves user text to graph entities:
        - location: "Matemblewo" → dzielnica Matarnia in Gdańsk
        - quietness: "spokojna okolica" → ["bardzo_cicha", "cicha"]
        - nature: "blisko lasu" → ["bardzo_zielona", "zielona"]
        - water: "nad morzem" → water_type="morze"

        Args:
            params: {
                "entity_type": "location" | "quietness" | "nature" | "accessibility" | "density" | "water" | "poi",
                "user_text": Text to resolve
            }
            state: Agent state (not used currently but available for context)

        Returns:
            Dict with resolved entity information
        """
        entity_type = params.get("entity_type")
        user_text = params.get("user_text")

        if not entity_type or not user_text:
            return {"error": "Wymagane parametry: entity_type, user_text"}

        try:
            if entity_type == "location":
                result = await graph_service.resolve_location_v2(user_text)
                if result.get("resolved"):
                    return {
                        "resolved": True,
                        "type": "location",
                        "canonical_name": result.get("canonical_name"),
                        "maps_to_district": result.get("maps_to_district"),
                        "maps_to_gmina": result.get("maps_to_gmina"),
                        "search_in_districts": result.get("search_in_districts"),
                        "price_segment": result.get("price_segment"),
                        "confidence": result.get("confidence"),
                        "similarity": result.get("similarity"),
                        "alternatives": result.get("alternatives", []),
                        "note": result.get("note"),
                    }
                else:
                    return result

            elif entity_type in ["quietness", "nature", "accessibility", "density"]:
                result = await graph_service.resolve_semantic_category(user_text, entity_type)
                if result.get("resolved"):
                    return {
                        "resolved": True,
                        "type": entity_type,
                        "matched_name": result.get("matched_name"),
                        "values": result.get("values"),
                        "similarity": result.get("similarity"),
                        "hint": f"Użyj wartości {result.get('values')} w kryteriach wyszukiwania.",
                    }
                else:
                    return result

            elif entity_type == "water":
                result = await graph_service.resolve_water_type(user_text)
                if result.get("resolved"):
                    return {
                        "resolved": True,
                        "type": "water",
                        "water_type": result.get("water_type"),
                        "canonical_name": result.get("canonical_name"),
                        "premium_factor": result.get("premium_factor"),
                        "similarity": result.get("similarity"),
                        "hint": f"Bliskość {result.get('canonical_name')} zwiększa wartość działki o {(result.get('premium_factor', 1) - 1) * 100:.0f}%",
                    }
                else:
                    return result

            elif entity_type == "poi":
                result = await graph_service.resolve_poi_type(user_text)
                if result.get("resolved"):
                    return {
                        "resolved": True,
                        "type": "poi",
                        "poi_types": result.get("poi_types"),
                        "canonical_name": result.get("canonical_name"),
                        "similarity": result.get("similarity"),
                    }
                else:
                    return result

            else:
                return {
                    "error": f"Nieznany typ encji: {entity_type}",
                    "valid_types": ["location", "quietness", "nature", "accessibility", "density", "water", "poi"]
                }

        except Exception as e:
            logger.error(f"Resolve entity error: {e}")
            return {"resolved": False, "error": str(e)}

    # =========================================================================
    # NEO4J V2: GRAPH TOOLS (2026-01-25)
    # Adjacency, NEAR_* relations, graph embeddings
    # =========================================================================

    async def _find_adjacent_parcels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find parcels adjacent to the given parcel using ADJACENT_TO relation.

        Uses 407,825 ADJACENT_TO relations with shared_border_m property.
        """
        raw_ref = params.get("parcel_id")
        if not raw_ref:
            return {"error": "Podaj parcel_id"}

        parcel_id = self._resolve_parcel_reference(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        limit = params.get("limit", 10)

        try:
            neighbors = await graph_service.find_adjacent_parcels(parcel_id, limit)

            if not neighbors:
                return {
                    "parcel_id": parcel_id,
                    "count": 0,
                    "neighbors": [],
                    "message": f"Nie znaleziono sąsiadów dla działki {parcel_id}",
                    "hint": "Ta działka może być na granicy zbioru danych lub nie mieć relacji ADJACENT_TO."
                }

            # Format results
            formatted = []
            for n in neighbors:
                formatted.append({
                    "id": n.get("id"),
                    "dzielnica": n.get("dzielnica"),
                    "gmina": n.get("gmina"),
                    "area_m2": n.get("area_m2"),
                    "quietness_score": n.get("quietness_score"),
                    "shared_border_m": round(n.get("shared_border_m", 0), 1),
                    "is_built": n.get("is_built"),
                })

            total_border = sum(n.get("shared_border_m", 0) for n in neighbors)

            return {
                "parcel_id": parcel_id,
                "count": len(neighbors),
                "neighbors": formatted,
                "total_shared_border_m": round(total_border, 1),
                "message": f"Znaleziono {len(neighbors)} sąsiadujących działek (łączna granica: {total_border:.0f}m)",
            }

        except Exception as e:
            logger.error(f"Find adjacent parcels error: {e}")
            return {"error": str(e)}

    async def _search_near_specific_poi(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search parcels near a specific POI using NEAR_* relations.

        Uses pre-computed NEAR_SCHOOL, NEAR_SHOP, NEAR_BUS_STOP, etc. relations.
        """
        poi_type = params.get("poi_type")
        if not poi_type:
            return {"error": "Podaj poi_type (school, shop, bus_stop, forest, water)"}

        valid_types = ["school", "shop", "bus_stop", "forest", "water"]
        if poi_type not in valid_types:
            return {"error": f"Nieznany typ POI. Dostępne: {', '.join(valid_types)}"}

        poi_name = params.get("poi_name")
        max_distance_m = params.get("max_distance_m", 1000)
        limit = params.get("limit", 20)

        try:
            results = await graph_service.search_near_poi(
                poi_type=poi_type,
                poi_name=poi_name,
                max_distance_m=max_distance_m,
                limit=limit
            )

            if not results:
                msg = f"Nie znaleziono działek blisko {poi_type}"
                if poi_name:
                    msg += f" o nazwie '{poi_name}'"
                msg += f" (max {max_distance_m}m)"
                return {
                    "poi_type": poi_type,
                    "poi_name": poi_name,
                    "count": 0,
                    "results": [],
                    "message": msg,
                    "hint": "Spróbuj zwiększyć max_distance_m lub pominąć filtr nazwy."
                }

            formatted = []
            for r in results:
                formatted.append({
                    "id": r.get("id"),
                    "dzielnica": r.get("dzielnica"),
                    "gmina": r.get("gmina"),
                    "area_m2": r.get("area_m2"),
                    "distance_m": round(r.get("distance_m", 0), 0),
                    "poi_name": r.get("poi_name"),
                    "quietness_score": r.get("quietness_score"),
                })

            poi_label = {"school": "szkoły", "shop": "sklepu", "bus_stop": "przystanku",
                        "forest": "lasu", "water": "wody"}

            return {
                "poi_type": poi_type,
                "poi_name": poi_name,
                "max_distance_m": max_distance_m,
                "count": len(results),
                "results": formatted,
                "message": f"Znaleziono {len(results)} działek blisko {poi_label.get(poi_type, poi_type)}" +
                          (f" '{poi_name}'" if poi_name else ""),
            }

        except Exception as e:
            logger.error(f"Search near POI error: {e}")
            return {"error": str(e)}

    async def _find_similar_by_graph(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find structurally similar parcels using graph embeddings (256-dim FastRP).

        Different from text similarity - captures graph structure (relations, neighborhood).
        """
        raw_ref = params.get("parcel_id")
        if not raw_ref:
            return {"error": "Podaj parcel_id"}

        parcel_id = self._resolve_parcel_reference(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano odniesienia do działki: {raw_ref}"}

        limit = params.get("limit", 10)

        try:
            similar = await graph_service.find_similar_by_graph_embedding(parcel_id, limit)

            if not similar:
                return {
                    "parcel_id": parcel_id,
                    "count": 0,
                    "similar_parcels": [],
                    "message": f"Nie znaleziono podobnych działek dla {parcel_id}",
                    "hint": "Ta działka może nie mieć graph_embedding lub brak podobnych w bazie."
                }

            formatted = []
            for s in similar:
                formatted.append({
                    "id": s.get("id"),
                    "dzielnica": s.get("dzielnica"),
                    "gmina": s.get("gmina"),
                    "area_m2": s.get("area_m2"),
                    "quietness_score": s.get("quietness_score"),
                    "nature_score": s.get("nature_score"),
                    "similarity": round(s.get("similarity", 0), 3),
                    "is_built": s.get("is_built"),
                })

            return {
                "parcel_id": parcel_id,
                "count": len(similar),
                "similar_parcels": formatted,
                "message": f"Znaleziono {len(similar)} strukturalnie podobnych działek",
                "note": "Podobieństwo oparte na strukturze grafu (relacje, sąsiedztwo), nie opisie tekstowym.",
            }

        except Exception as e:
            logger.error(f"Find similar by graph error: {e}")
            return {"error": str(e)}

    # =========================================================================
    # V3 SUB-AGENT TOOLS (2026-02-03)
    # =========================================================================

    async def _search_by_criteria(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search parcels by advanced Neo4j graph criteria."""
        try:
            criteria = {}
            if params.get("ownership_type"):
                criteria["ownership_type"] = params["ownership_type"]
            if params.get("build_status"):
                criteria["build_status"] = params["build_status"]
            if params.get("size_category"):
                criteria["size_category"] = params["size_category"]
            if params.get("district"):
                criteria["district"] = params["district"]
            if params.get("city"):
                criteria["city"] = params["city"]

            limit = params.get("limit", 20)

            # Build Cypher query dynamically
            match_clauses = ["MATCH (p:Parcel)"]
            where_clauses = []
            query_params: Dict[str, Any] = {"limit": limit}

            if criteria.get("ownership_type"):
                match_clauses.append("MATCH (p)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: $ownership})")
                query_params["ownership"] = criteria["ownership_type"]
            if criteria.get("build_status"):
                match_clauses.append("MATCH (p)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: $build_status})")
                query_params["build_status"] = criteria["build_status"]
            if criteria.get("size_category"):
                match_clauses.append("MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory)")
                where_clauses.append("sz.id IN $size_cats")
                query_params["size_cats"] = criteria["size_category"]
            if criteria.get("district"):
                match_clauses.append("MATCH (p)-[:LOCATED_IN]->(d:District)")
                where_clauses.append("d.name CONTAINS $district")
                query_params["district"] = criteria["district"]
            if criteria.get("city"):
                where_clauses.append("p.gmina = $city")
                query_params["city"] = criteria["city"]

            where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            query = "\n".join(match_clauses) + where_str + """
                RETURN p.id_dzialki as id, p.gmina as gmina, p.dzielnica as dzielnica,
                       p.area_m2 as area_m2, p.quietness_score as quietness_score,
                       p.nature_score as nature_score, p.centroid_lat as lat, p.centroid_lon as lon
                ORDER BY p.quietness_score DESC
                LIMIT $limit
            """

            results = await graph_service.run_query(query, query_params)
            return {
                "count": len(results),
                "parcels": results,
                "criteria_used": criteria,
            }
        except Exception as e:
            logger.error(f"Search by criteria error: {e}")
            return {"error": str(e)}

    async def _refine_search_preferences(self, params: Dict[str, Any]) -> ToolResult:
        """Refine existing search preferences with updates."""
        updates = params.get("updates", {})
        reason = params.get("reason", "")

        perceived = self._search_state.perceived_preferences
        if perceived is None:
            return {"error": "Brak preferencji do modyfikacji"}, {}

        # Modify perceived in-place and return the full dict as a 2-level update
        for key, value in updates.items():
            perceived[key] = value

        state_updates = {
            "search_state.perceived_preferences": perceived,
        }

        return {
            "status": "preferences_refined",
            "updates_applied": list(updates.keys()),
            "reason": reason,
            "message": f"Zaktualizowano {len(updates)} parametrów wyszukiwania",
        }, state_updates

    async def _compare_parcels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare multiple parcels side-by-side."""
        parcel_ids = params.get("parcel_ids", [])
        if len(parcel_ids) < 2:
            return {"error": "Potrzebuję minimum 2 działek do porównania"}

        try:
            parcels = []
            for pid in parcel_ids[:5]:  # Max 5
                resolved = self._resolve_parcel_reference(pid)
                if not resolved:
                    continue
                details = await spatial_service.get_parcel_details(resolved, include_geometry=False)
                if details:
                    parcels.append(details)

            if len(parcels) < 2:
                return {"error": "Nie udało się pobrać danych dla wystarczającej liczby działek"}

            return {
                "count": len(parcels),
                "parcels": parcels,
                "comparison_ready": True,
                "message": f"Porównanie {len(parcels)} działek",
            }
        except Exception as e:
            logger.error(f"Compare parcels error: {e}")
            return {"error": str(e)}

    async def _get_zoning_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed zoning/POG information for a parcel."""
        raw_ref = params.get("parcel_id", "")
        parcel_id = self._resolve_parcel_reference(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano działki: {raw_ref}"}

        try:
            query = """
                MATCH (p:Parcel {id_dzialki: $pid})
                OPTIONAL MATCH (p)-[:HAS_POG]->(z:POGZone)
                OPTIONAL MATCH (z)-[:ALLOWS_PROFILE]->(pr:POGProfile)
                RETURN p.id_dzialki as id, p.pog_symbol as pog_symbol,
                       z.symbol as zone_symbol, z.name as zone_name,
                       z.is_residential as is_residential,
                       z.max_height_m as max_height,
                       z.max_coverage_pct as max_coverage,
                       z.min_bio_pct as min_bio,
                       collect(DISTINCT pr.name) as allowed_profiles
            """
            results = await graph_service.run_query(query, {"pid": parcel_id})
            if not results:
                return {"parcel_id": parcel_id, "has_zoning": False, "message": "Brak danych planistycznych"}

            r = results[0]
            return {
                "parcel_id": parcel_id,
                "has_zoning": r.get("zone_symbol") is not None,
                "pog_symbol": r.get("pog_symbol"),
                "zone_symbol": r.get("zone_symbol"),
                "zone_name": r.get("zone_name"),
                "is_residential": r.get("is_residential"),
                "max_height_m": r.get("max_height"),
                "max_coverage_pct": r.get("max_coverage"),
                "min_bio_pct": r.get("min_bio"),
                "allowed_profiles": r.get("allowed_profiles", []),
            }
        except Exception as e:
            logger.error(f"Get zoning info error: {e}")
            return {"error": str(e)}

    async def _market_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Market analysis for a location or parcel."""
        location = params.get("location", "")
        parcel_id = params.get("parcel_id")
        area_m2 = params.get("area_m2")

        try:
            # Use hardcoded price data (keys are (city, district) tuples)
            from app.engine.price_data import DISTRICT_PRICES
            price_info = None
            matched_key = None

            # Try direct lookup with common cities
            for city in ["Gdańsk", "Gdynia", "Sopot"]:
                key = (city, location)
                if key in DISTRICT_PRICES:
                    price_info = DISTRICT_PRICES[key]
                    matched_key = key
                    break

            # Fuzzy match if not found
            if not price_info:
                loc_lower = location.lower()
                for (city, district), info in DISTRICT_PRICES.items():
                    if district and loc_lower in district.lower():
                        price_info = info
                        matched_key = (city, district)
                        break

            result: Dict[str, Any] = {
                "location": location,
                "matched": f"{matched_key[0]}, {matched_key[1]}" if matched_key else None,
                "price_range": price_info if price_info else "Brak danych cenowych dla tej lokalizacji",
            }

            if area_m2 and price_info:
                min_price = price_info.get("min", 0) * area_m2
                max_price = price_info.get("max", 0) * area_m2
                result["estimated_value"] = {
                    "min_pln": round(min_price),
                    "max_pln": round(max_price),
                    "area_m2": area_m2,
                }

            return result
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
            return {"error": str(e)}

    async def _propose_filter_refinement(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Propose filter refinements based on user feedback patterns."""
        favorited = params.get("favorited_ids", [])
        rejected = params.get("rejected_ids", [])

        if not favorited and not rejected:
            return {"message": "Brak danych o preferencjach do analizy", "suggestions": []}

        try:
            suggestions = []

            # Analyze favorited parcels for common patterns
            if favorited:
                fav_query = """
                    MATCH (p:Parcel) WHERE p.id_dzialki IN $ids
                    RETURN avg(p.area_m2) as avg_area,
                           avg(p.quietness_score) as avg_quiet,
                           avg(p.nature_score) as avg_nature,
                           collect(DISTINCT p.dzielnica) as districts
                """
                fav_results = await graph_service.run_query(fav_query, {"ids": favorited})
                if fav_results:
                    r = fav_results[0]
                    if r.get("avg_area"):
                        suggestions.append({
                            "field": "area_m2",
                            "suggestion": f"Preferowana powierzchnia ok. {round(r['avg_area'])} m²",
                            "value": round(r["avg_area"]),
                        })
                    if r.get("districts"):
                        suggestions.append({
                            "field": "districts",
                            "suggestion": f"Preferowane dzielnice: {', '.join(r['districts'])}",
                            "value": r["districts"],
                        })

            return {
                "suggestions": suggestions,
                "based_on": {"favorited": len(favorited), "rejected": len(rejected)},
            }
        except Exception as e:
            logger.error(f"Propose filter refinement error: {e}")
            return {"error": str(e)}

    async def _capture_contact_info(self, params: Dict[str, Any]) -> ToolResult:
        """Capture user contact information as a lead."""
        email = params.get("email")
        phone = params.get("phone")
        interest = params.get("interest_description", "")
        parcel_ids = params.get("parcel_ids", [])

        if not email and not phone:
            return {"error": "Potrzebuję przynajmniej email lub telefon"}, {}

        lead_data = {
            "email": email,
            "phone": phone,
            "interest": interest,
            "parcel_ids": parcel_ids,
            "captured": True,
        }

        logger.info(f"Lead captured: email={email}, phone={phone}, parcels={len(parcel_ids)}")

        return {
            "status": "lead_captured",
            "message": "Dziękuję! Dane kontaktowe zapisane.",
            "lead": lead_data,
        }, {"contact_captured": True}


# =============================================================================
# Legacy compatibility function
# =============================================================================

async def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy execute_tool function for backwards compatibility.

    This creates a temporary state and executes the tool.
    For V2 architecture, use ToolExecutor directly with proper state.

    WARNING: This function does not persist state changes!
    """
    from app.memory import AgentState
    import uuid

    # Create temporary state
    state = AgentState(
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
    )

    executor = ToolExecutor(state)
    result, _ = await executor.execute(tool_name, params)

    return result
