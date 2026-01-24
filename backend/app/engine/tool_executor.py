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
            gminy = await graph_service.get_gminy()
            gminy_names = [g.name for g in gminy]
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

                # Try miejscowość (dzielnica) only if no gmina match
                if not miejscowosc_param and not gmina_param:
                    miejscowosci = await spatial_service.get_miejscowosci()
                    for m in miejscowosci:
                        if m.lower() == clean_loc:
                            miejscowosc_param = m
                            break

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
            "charakter_terenu": params.get("charakter_terenu"),
            "lat": params.get("lat"),
            "lon": params.get("lon"),
            "radius_m": params.get("radius_m", 5000),
            "min_area_m2": params.get("min_area_m2", 500),
            "max_area_m2": params.get("max_area_m2", 3000),
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
            "quietness_weight": params.get("quietness_weight", 0.5),
            "nature_weight": params.get("nature_weight", 0.3),
            "accessibility_weight": params.get("accessibility_weight", 0.2),
        }

        # Build human-readable summary
        summary = {
            "lokalizacja": preferences["location_description"],
            "gmina": preferences["gmina"] or "dowolna",
        }
        if preferences["miejscowosc"]:
            summary["miejscowosc"] = preferences["miejscowosc"]
        if preferences["charakter_terenu"]:
            summary["charakter"] = ", ".join(preferences["charakter_terenu"])
        if preferences.get("lat") and preferences.get("lon"):
            radius = preferences.get("radius_m", 5000)
            summary["wyszukiwanie_przestrzenne"] = f"w promieniu {radius/1000:.1f}km od punktu"
        summary["powierzchnia"] = f"{preferences['min_area_m2']}-{preferences['max_area_m2']} m²"

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
            charakter_terenu=prefs.get("charakter_terenu"),
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
            quietness_weight=prefs.get("quietness_weight", 0.5),
            nature_weight=prefs.get("nature_weight", 0.3),
            accessibility_weight=prefs.get("accessibility_weight", 0.2),
        )

        results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

        # If no results, run diagnostics to find the blocking filter
        diagnostics = None
        if not results:
            diagnostics = await self._diagnose_empty_results(prefs)

        current_results = []
        for r in results:
            parcel_dict = {
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

            # Test each filter incrementally
            filters_to_test = [
                ("area", f"p.area_m2 >= {prefs.get('min_area_m2', 0)} AND p.area_m2 <= {prefs.get('max_area_m2', 999999)}",
                 f"powierzchnia {prefs.get('min_area_m2')}-{prefs.get('max_area_m2')} m²"),

                ("quietness", "EXISTS((p)-[:HAS_QUIETNESS]->(:QuietnessCategory {id: q})) WHERE q IN $quietness_cats" if prefs.get("quietness_categories") else None,
                 f"cisza: {prefs.get('quietness_categories')}"),

                ("density", None, f"zabudowa: {prefs.get('building_density')}"),
            ]

            # Simplified: just check quietness category distribution
            if prefs.get("quietness_categories"):
                query = f"""
                    MATCH (p:Parcel)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
                    WHERE {where_clause}
                    RETURN qc.id as category, count(p) as cnt
                    ORDER BY cnt DESC
                """
                records = await neo4j.run(query, params)
                available_categories = {r["category"]: r["cnt"] for r in records}
                requested = prefs.get("quietness_categories", [])
                matching = sum(available_categories.get(cat, 0) for cat in requested)

                diagnostics["quietness_analysis"] = {
                    "requested": requested,
                    "available_in_location": available_categories,
                    "matching_count": matching
                }

                if matching == 0:
                    dominant = max(available_categories.items(), key=lambda x: x[1]) if available_categories else ("brak", 0)
                    diagnostics["blocking_filter"] = "quietness_categories"
                    diagnostics["message"] = f"W '{location}' nie ma działek o ciszy {requested}. Dominuje: '{dominant[0]}' ({dominant[1]} działek)."

                    # Suggest alternative
                    if dominant[0] == "glosna":
                        diagnostics["suggestion"] = f"'{location}' to głośna okolica. Rozważ: 1) usuń filtr ciszy, 2) lub szukaj w cichszych dzielnicach (np. Matemblewo, VII Dwór, Osowa)."
                    else:
                        diagnostics["suggestion"] = f"Zmień kryterium ciszy na '{dominant[0]}' lub usuń ten filtr."
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
                    return diagnostics

            # Generic fallback - combination of filters is too restrictive
            diagnostics["blocking_filter"] = "combination"
            diagnostics["message"] = "Kombinacja wszystkich filtrów jest zbyt restrykcyjna."
            diagnostics["suggestion"] = "Poluzuj niektóre kryteria: cisza, zabudowa, lub odległości do POI."

            return diagnostics

        except Exception as e:
            logger.error(f"Diagnostics error: {e}")
            return {"error": str(e), "suggestion": "Spróbuj poluzować kryteria wyszukiwania."}

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

        min_area = prefs.get("min_area_m2", 500)
        max_area = prefs.get("max_area_m2", 3000)

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

        if prefs.get("quietness_weight", 0) >= 0.5 and quietness and quietness >= 80:
            if not any("Cisza" in h for h in highlights):
                highlights.append("Cicha okolica")

        if prefs.get("nature_weight", 0) >= 0.5 and nature and nature >= 70:
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
        parcel_id = params["parcel_id"]
        limit = params.get("limit", 5)

        results = await vector_service.search_similar(parcel_id=parcel_id, top_k=limit)

        return {
            "reference_parcel": parcel_id,
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
        parcel_id = params["parcel_id"]
        details = await spatial_service.get_parcel_details(parcel_id, include_geometry=False)

        if details:
            return {"parcel": details}
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
        parcel_id = params["parcel_id"]
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
        parcel_ids = params["parcel_ids"]

        if not parcel_ids:
            return {"error": "No parcel IDs provided"}

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
        parcel_id = params.get("parcel_id")
        if not parcel_id:
            return {"error": "Podaj ID działki (parcel_id)"}

        result = await graph_service.get_water_near_parcel(parcel_id)

        if "error" in result:
            return result

        return result

    async def _get_parcel_full_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get full context for a parcel including all features."""
        parcel_id = params.get("parcel_id")
        if not parcel_id:
            return {"error": "Podaj ID działki (parcel_id)"}

        result = await graph_service.get_parcel_full_context(parcel_id)

        if "error" in result:
            return result

        return result


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
