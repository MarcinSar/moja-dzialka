"""
Agent tools for parcel search.

Implements patterns from Neo4j Knowledge Graph courses:
- Human-in-the-Loop: propose_* → user confirms → approve_*
- Guard Patterns: validate state before operations
- Critic Pattern: iterative refinement of results

Each tool has a schema (for Claude) and an implementation.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json

from loguru import logger

from app.services import (
    spatial_service,
    vector_service,
    graph_service,
    hybrid_search,
    SearchPreferences,
    SpatialSearchParams,
)


# =============================================================================
# AGENT STATE (session-scoped)
# =============================================================================

@dataclass
class AgentState:
    """
    Agent state for Human-in-the-Loop pattern.

    Follows perceived → approved flow from Agentic KG Construction course.
    """
    # Perceived (proposed, not yet approved)
    perceived_search_preferences: Optional[Dict[str, Any]] = None

    # Approved (confirmed by user)
    approved_search_preferences: Optional[Dict[str, Any]] = None

    # Search results for critic pattern
    current_search_results: List[Dict[str, Any]] = field(default_factory=list)
    search_feedback: Optional[str] = None
    search_iteration: int = 0

    # Credits (monetization)
    free_parcels_shown: int = 0
    credits_available: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "perceived_search_preferences": self.perceived_search_preferences,
            "approved_search_preferences": self.approved_search_preferences,
            "search_results_count": len(self.current_search_results),
            "search_feedback": self.search_feedback,
            "search_iteration": self.search_iteration,
            "free_parcels_shown": self.free_parcels_shown,
            "credits_available": self.credits_available,
        }


# Global state (in production: use Redis/session store)
_agent_state = AgentState()


def get_state() -> AgentState:
    """Get current agent state."""
    return _agent_state


def reset_state():
    """Reset agent state for new conversation."""
    global _agent_state
    _agent_state = AgentState()


# =============================================================================
# TOOL DEFINITIONS (Claude API format)
# =============================================================================

AGENT_TOOLS = [
    # =============== HUMAN-IN-THE-LOOP: PREFERENCES ===============
    {
        "name": "propose_search_preferences",
        "description": """
Zaproponuj preferencje wyszukiwania na podstawie rozmowy z użytkownikiem.
To jest PIERWSZY KROK - propozycja wymaga potwierdzenia użytkownika.

UŻYJ gdy zrozumiałeś czego szuka użytkownik i chcesz potwierdzić.
Po użyciu ZAPYTAJ użytkownika: "Czy te preferencje są poprawne?"
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "location_description": {
                    "type": "string",
                    "description": "Opis lokalizacji (np. 'okolice Gdańska', 'gmina Żukowo')"
                },
                "gmina": {
                    "type": "string",
                    "description": "Konkretna gmina (jeśli znana)"
                },
                "min_area_m2": {
                    "type": "number",
                    "description": "Minimalna powierzchnia w m²"
                },
                "max_area_m2": {
                    "type": "number",
                    "description": "Maksymalna powierzchnia w m²"
                },
                "quietness_weight": {
                    "type": "number",
                    "description": "Waga cichej okolicy (0-1, domyślnie 0.5)"
                },
                "nature_weight": {
                    "type": "number",
                    "description": "Waga bliskości natury/lasu (0-1, domyślnie 0.3)"
                },
                "accessibility_weight": {
                    "type": "number",
                    "description": "Waga dostępności komunikacyjnej (0-1, domyślnie 0.2)"
                },
                "requires_mpzp": {
                    "type": "boolean",
                    "description": "Czy działka musi mieć MPZP"
                },
                "mpzp_buildable": {
                    "type": "boolean",
                    "description": "Czy MPZP musi być budowlane"
                }
            },
            "required": ["location_description"]
        }
    },
    {
        "name": "approve_search_preferences",
        "description": """
Zatwierdź zaproponowane preferencje wyszukiwania po potwierdzeniu przez użytkownika.

GUARD PATTERN: To narzędzie WYMAGA wcześniejszego użycia propose_search_preferences.
Użyj TYLKO gdy użytkownik potwierdził preferencje.
""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "modify_search_preferences",
        "description": """
Zmodyfikuj konkretny aspekt zaproponowanych preferencji.
Użyj gdy użytkownik chce zmienić tylko jedną rzecz w propozycji.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": ["gmina", "min_area_m2", "max_area_m2", "quietness_weight",
                             "nature_weight", "accessibility_weight", "requires_mpzp"],
                    "description": "Pole do zmiany"
                },
                "new_value": {
                    "type": ["string", "number", "boolean"],
                    "description": "Nowa wartość"
                }
            },
            "required": ["field", "new_value"]
        }
    },

    # =============== SEARCH TOOLS ===============
    {
        "name": "execute_search",
        "description": """
Wykonaj wyszukiwanie działek na podstawie ZATWIERDZONYCH preferencji.

GUARD PATTERN: Wymaga zatwierdzonego stanu (approve_search_preferences).
Zwraca do 10 najlepszych działek.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maksymalna liczba wyników (domyślnie 10)"
                }
            },
            "required": []
        }
    },
    {
        "name": "find_similar_parcels",
        "description": """
Znajdź działki podobne do wskazanej.
Użyj gdy użytkownik wskaże działkę i chce znaleźć podobne.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki referencyjnej"
                },
                "limit": {
                    "type": "integer",
                    "description": "Liczba podobnych działek (domyślnie 5)"
                }
            },
            "required": ["parcel_id"]
        }
    },

    # =============== CRITIC PATTERN: REFINEMENT ===============
    {
        "name": "critique_search_results",
        "description": """
CRITIC PATTERN: Oceń wyniki wyszukiwania z perspektywy użytkownika.

Użyj gdy użytkownik wyraził niezadowolenie z wyników lub chce je ulepszyć.
Zapisuje feedback który zostanie użyty do refinementu.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "feedback": {
                    "type": "string",
                    "description": "Feedback użytkownika (np. 'za blisko drogi', 'za małe działki')"
                },
                "problem_parcels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ID działek które nie pasują (opcjonalne)"
                }
            },
            "required": ["feedback"]
        }
    },
    {
        "name": "refine_search",
        "description": """
CRITIC PATTERN: Popraw wyszukiwanie na podstawie feedbacku.

Automatycznie modyfikuje preferencje i wykonuje nowe wyszukiwanie.
Użyj PO critique_search_results.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "adjustment": {
                    "type": "string",
                    "description": "Opis zmiany (np. 'zwiększ minimalną powierzchnię', 'wyklucz okolice autostrad')"
                }
            },
            "required": ["adjustment"]
        }
    },

    # =============== INFO TOOLS ===============
    {
        "name": "get_parcel_details",
        "description": """
Pobierz szczegółowe informacje o konkretnej działce.
Zwraca wszystkie atrybuty włącznie z MPZP i odległościami.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki"
                }
            },
            "required": ["parcel_id"]
        }
    },
    {
        "name": "get_gmina_info",
        "description": """
Pobierz informacje o gminie - ile działek, średnia powierzchnia, % z MPZP.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmina_name": {
                    "type": "string",
                    "description": "Nazwa gminy"
                }
            },
            "required": ["gmina_name"]
        }
    },
    {
        "name": "list_gminy",
        "description": """
Pobierz listę wszystkich gmin w województwie pomorskim.
""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "count_matching_parcels",
        "description": """
Szybkie policzenie działek spełniających kryteria (bez pobierania szczegółów).
Użyj do podglądu ile wyników będzie przed pełnym wyszukiwaniem.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmina": {"type": "string"},
                "has_mpzp": {"type": "boolean"}
            },
            "required": []
        }
    },
    {
        "name": "get_mpzp_symbols",
        "description": """
Pobierz listę symboli MPZP z opisami.
MN = mieszkaniowa jednorodzinna, U = usługowa, ZL = leśna, itp.
""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # =============== MAP TOOLS ===============
    {
        "name": "generate_map_data",
        "description": """
Wygeneruj dane do wyświetlenia na mapie (GeoJSON).
Użyj gdy chcesz pokazać użytkownikowi lokalizacje działek na mapie.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista ID działek do pokazania"
                }
            },
            "required": ["parcel_ids"]
        }
    },
]


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with given parameters."""
    logger.info(f"Executing tool: {tool_name}")
    logger.debug(f"Tool params: {params}")

    try:
        # Human-in-the-Loop tools
        if tool_name == "propose_search_preferences":
            return await _propose_search_preferences(params)
        elif tool_name == "approve_search_preferences":
            return await _approve_search_preferences(params)
        elif tool_name == "modify_search_preferences":
            return await _modify_search_preferences(params)

        # Search tools
        elif tool_name == "execute_search":
            return await _execute_search(params)
        elif tool_name == "find_similar_parcels":
            return await _find_similar_parcels(params)

        # Critic pattern tools
        elif tool_name == "critique_search_results":
            return await _critique_search_results(params)
        elif tool_name == "refine_search":
            return await _refine_search(params)

        # Info tools
        elif tool_name == "get_parcel_details":
            return await _get_parcel_details(params)
        elif tool_name == "get_gmina_info":
            return await _get_gmina_info(params)
        elif tool_name == "list_gminy":
            return await _list_gminy(params)
        elif tool_name == "count_matching_parcels":
            return await _count_matching_parcels(params)
        elif tool_name == "get_mpzp_symbols":
            return await _get_mpzp_symbols(params)

        # Map tools
        elif tool_name == "generate_map_data":
            return await _generate_map_data(params)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {"error": str(e)}


# --------------- HUMAN-IN-THE-LOOP IMPLEMENTATIONS ---------------

async def _propose_search_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    """Propose search preferences (perceived state)."""
    state = get_state()

    preferences = {
        "location_description": params.get("location_description", "województwo pomorskie"),
        "gmina": params.get("gmina"),
        "min_area_m2": params.get("min_area_m2", 500),
        "max_area_m2": params.get("max_area_m2", 3000),
        "quietness_weight": params.get("quietness_weight", 0.5),
        "nature_weight": params.get("nature_weight", 0.3),
        "accessibility_weight": params.get("accessibility_weight", 0.2),
        "requires_mpzp": params.get("requires_mpzp", False),
        "mpzp_buildable": params.get("mpzp_buildable"),
    }

    state.perceived_search_preferences = preferences

    # Return formatted summary for user confirmation
    return {
        "status": "proposed",
        "message": "Preferencje zaproponowane. Poproś użytkownika o potwierdzenie.",
        "preferences": {
            "lokalizacja": preferences["location_description"],
            "gmina": preferences["gmina"] or "dowolna",
            "powierzchnia": f"{preferences['min_area_m2']}-{preferences['max_area_m2']} m²",
            "preferencje": {
                "cisza": f"{int(preferences['quietness_weight'] * 100)}%",
                "natura": f"{int(preferences['nature_weight'] * 100)}%",
                "dostępność": f"{int(preferences['accessibility_weight'] * 100)}%",
            },
            "mpzp": "wymagane" if preferences["requires_mpzp"] else "opcjonalne",
        },
        "next_step": "Zapytaj: 'Czy te preferencje są poprawne?' i użyj approve_search_preferences po potwierdzeniu.",
    }


async def _approve_search_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    """Approve proposed preferences (guard pattern)."""
    state = get_state()

    # GUARD PATTERN: Check if perceived state exists
    if state.perceived_search_preferences is None:
        return {
            "error": "Brak zaproponowanych preferencji",
            "message": "Najpierw użyj propose_search_preferences aby zaproponować preferencje.",
            "hint": "Zapytaj użytkownika o lokalizację, powierzchnię i preferencje.",
        }

    # Move perceived → approved
    state.approved_search_preferences = state.perceived_search_preferences.copy()
    state.search_iteration = 0
    state.current_search_results = []

    return {
        "status": "approved",
        "message": "Preferencje zatwierdzone! Możesz teraz wykonać wyszukiwanie.",
        "approved_preferences": state.approved_search_preferences,
        "next_step": "Użyj execute_search() aby wyszukać działki.",
    }


async def _modify_search_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    """Modify a specific field in perceived preferences."""
    state = get_state()

    if state.perceived_search_preferences is None:
        return {
            "error": "Brak preferencji do modyfikacji",
            "message": "Najpierw użyj propose_search_preferences.",
        }

    field = params["field"]
    new_value = params["new_value"]

    if field not in state.perceived_search_preferences:
        return {"error": f"Nieznane pole: {field}"}

    state.perceived_search_preferences[field] = new_value

    return {
        "status": "modified",
        "field": field,
        "new_value": new_value,
        "message": f"Zmieniono {field} na {new_value}. Zapytaj o ponowne potwierdzenie.",
    }


# --------------- SEARCH IMPLEMENTATIONS ---------------

async def _execute_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute search with approved preferences (guard pattern)."""
    state = get_state()

    # GUARD PATTERN: Check if approved state exists
    if state.approved_search_preferences is None:
        return {
            "error": "Brak zatwierdzonych preferencji",
            "message": "Najpierw zatwierdź preferencje używając approve_search_preferences.",
            "hint": "Flow: propose_search_preferences → user confirms → approve_search_preferences → execute_search",
        }

    prefs = state.approved_search_preferences
    limit = params.get("limit", 10)

    # Build search preferences
    search_prefs = SearchPreferences(
        gmina=prefs.get("gmina"),
        min_area=prefs.get("min_area_m2"),
        max_area=prefs.get("max_area_m2"),
        has_mpzp=prefs.get("requires_mpzp"),
        mpzp_budowlane=prefs.get("mpzp_buildable"),
        quietness_weight=prefs.get("quietness_weight", 0.5),
        nature_weight=prefs.get("nature_weight", 0.3),
        accessibility_weight=prefs.get("accessibility_weight", 0.2),
    )

    # Execute hybrid search
    results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

    # Store results for critic pattern
    state.current_search_results = [
        {
            "id": r.parcel_id,
            "gmina": r.gmina,
            "miejscowosc": r.miejscowosc,
            "area_m2": r.area_m2,
            "quietness_score": r.quietness_score,
            "nature_score": r.nature_score,
            "accessibility_score": r.accessibility_score,
            "has_mpzp": r.has_mpzp,
            "mpzp_symbol": r.mpzp_symbol,
            "lat": r.centroid_lat,
            "lon": r.centroid_lon,
        }
        for r in results
    ]
    state.search_iteration += 1

    return {
        "status": "success",
        "iteration": state.search_iteration,
        "count": len(results),
        "parcels": state.current_search_results,
        "note": "Jeśli użytkownik nie jest zadowolony, użyj critique_search_results i refine_search.",
    }


async def _find_similar_parcels(params: Dict[str, Any]) -> Dict[str, Any]:
    """Find parcels similar to a reference parcel."""
    parcel_id = params["parcel_id"]
    limit = params.get("limit", 5)

    results = await vector_service.search_similar(
        parcel_id=parcel_id,
        top_k=limit,
    )

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


# --------------- CRITIC PATTERN IMPLEMENTATIONS ---------------

async def _critique_search_results(params: Dict[str, Any]) -> Dict[str, Any]:
    """Record feedback about search results (Critic pattern)."""
    state = get_state()

    if not state.current_search_results:
        return {
            "error": "Brak wyników do oceny",
            "message": "Najpierw wykonaj wyszukiwanie (execute_search).",
        }

    feedback = params["feedback"]
    problem_parcels = params.get("problem_parcels", [])

    state.search_feedback = feedback

    return {
        "status": "feedback_recorded",
        "feedback": feedback,
        "problem_parcels": problem_parcels,
        "current_iteration": state.search_iteration,
        "message": "Feedback zapisany. Użyj refine_search() aby poprawić wyniki.",
    }


async def _refine_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """Refine search based on feedback (Critic pattern)."""
    state = get_state()

    if state.search_feedback is None:
        return {
            "error": "Brak feedbacku",
            "message": "Najpierw użyj critique_search_results aby zapisać feedback użytkownika.",
        }

    if state.approved_search_preferences is None:
        return {
            "error": "Brak zatwierdzonych preferencji",
            "message": "Brak podstawy do refinementu.",
        }

    adjustment = params["adjustment"]
    prefs = state.approved_search_preferences

    # Apply adjustment based on description
    # This is simplified - in production, could use LLM to parse adjustment
    adjustment_lower = adjustment.lower()

    if "większ" in adjustment_lower or "duż" in adjustment_lower:
        prefs["min_area_m2"] = prefs.get("min_area_m2", 500) * 1.5
    if "mniejsz" in adjustment_lower or "mał" in adjustment_lower:
        prefs["max_area_m2"] = prefs.get("max_area_m2", 3000) * 0.7
    if "cich" in adjustment_lower:
        prefs["quietness_weight"] = min(1.0, prefs.get("quietness_weight", 0.5) + 0.2)
    if "natur" in adjustment_lower or "las" in adjustment_lower:
        prefs["nature_weight"] = min(1.0, prefs.get("nature_weight", 0.3) + 0.2)

    # Clear feedback, increment iteration
    state.search_feedback = None
    state.approved_search_preferences = prefs

    # Re-run search
    return await _execute_search({"limit": 10})


# --------------- INFO IMPLEMENTATIONS ---------------

async def _get_parcel_details(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed info about a parcel."""
    parcel_id = params["parcel_id"]

    details = await spatial_service.get_parcel_details(parcel_id, include_geometry=False)

    if details:
        return {"parcel": details}
    else:
        return {"error": f"Działka nie znaleziona: {parcel_id}"}


async def _get_gmina_info(params: Dict[str, Any]) -> Dict[str, Any]:
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


async def _list_gminy(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all gminy."""
    gminy = await graph_service.get_all_gminy()
    return {"count": len(gminy), "gminy": gminy}


async def _count_matching_parcels(params: Dict[str, Any]) -> Dict[str, Any]:
    """Count parcels matching criteria."""
    count = await spatial_service.count_parcels(
        gmina=params.get("gmina"),
        has_mpzp=params.get("has_mpzp"),
    )
    return {"count": count, "filters": params}


async def _get_mpzp_symbols(params: Dict[str, Any]) -> Dict[str, Any]:
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


# --------------- MAP IMPLEMENTATIONS ---------------

async def _generate_map_data(params: Dict[str, Any]) -> Dict[str, Any]:
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
