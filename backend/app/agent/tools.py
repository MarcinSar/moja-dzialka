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
    BBoxSearchParams,
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

UŻYWAJ WSZYSTKICH DOSTĘPNYCH KRYTERIÓW! Masz bogatą bazę danych.
Po użyciu ZAPYTAJ użytkownika: "Czy te preferencje są poprawne?"
""",
        "input_schema": {
            "type": "object",
            "properties": {
                # === LOKALIZACJA ===
                "location_description": {
                    "type": "string",
                    "description": "Opis lokalizacji (np. 'okolice Gdańska', 'gmina Żukowo')"
                },
                "gmina": {
                    "type": "string",
                    "description": "Konkretna gmina"
                },
                "miejscowosc": {
                    "type": "string",
                    "description": "Konkretna miejscowość"
                },
                "powiat": {
                    "type": "string",
                    "description": "Powiat (gdański, kartuski, Gdańsk)"
                },

                # === LOKALIZACJA PRZESTRZENNA (PostGIS) ===
                "lat": {
                    "type": "number",
                    "description": "Szerokość geograficzna punktu centralnego (WGS84). Używaj razem z lon i radius_m dla wyszukiwania w promieniu od punktu."
                },
                "lon": {
                    "type": "number",
                    "description": "Długość geograficzna punktu centralnego (WGS84). Używaj razem z lat i radius_m."
                },
                "radius_m": {
                    "type": "number",
                    "description": "Promień wyszukiwania w metrach od punktu (lat, lon). Domyślnie 5000m. Max 20000m."
                },

                "charakter_terenu": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["wiejski", "podmiejski", "miejski", "leśny", "mieszany"]},
                    "description": "Charakter terenu"
                },

                # === POWIERZCHNIA ===
                "min_area_m2": {
                    "type": "number",
                    "description": "Minimalna powierzchnia w m²"
                },
                "max_area_m2": {
                    "type": "number",
                    "description": "Maksymalna powierzchnia w m²"
                },
                "area_category": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mala", "srednia", "duza", "bardzo_duza"]},
                    "description": "Kategorie powierzchni: mala (<800), srednia (800-1500), duza (1500-3000), bardzo_duza (>3000)"
                },

                # === CISZA I OTOCZENIE ===
                "quietness_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["bardzo_cicha", "cicha", "umiarkowana", "głośna"]},
                    "description": "Kategorie ciszy (preferowane)"
                },
                "building_density": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["bardzo_gesta", "gesta", "umiarkowana", "rzadka", "bardzo_rzadka"]},
                    "description": "Gęstość zabudowy w okolicy"
                },
                "min_dist_to_industrial_m": {
                    "type": "integer",
                    "description": "Min. odległość od przemysłu w metrach"
                },

                # === NATURA ===
                "nature_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["bardzo_zielona", "zielona", "umiarkowana", "zurbanizowana"]},
                    "description": "Kategorie natury (preferowane)"
                },
                "max_dist_to_forest_m": {
                    "type": "integer",
                    "description": "Max. odległość do lasu w metrach"
                },
                "max_dist_to_water_m": {
                    "type": "integer",
                    "description": "Max. odległość do wody w metrach"
                },
                "min_forest_pct_500m": {
                    "type": "number",
                    "description": "Min. procent lasu w promieniu 500m (0-1)"
                },

                # === DOSTĘPNOŚĆ ===
                "accessibility_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["doskonały", "dobry", "umiarkowany", "ograniczony"]},
                    "description": "Kategorie dostępności"
                },
                "max_dist_to_school_m": {
                    "type": "integer",
                    "description": "Max. odległość do szkoły w metrach"
                },
                "max_dist_to_shop_m": {
                    "type": "integer",
                    "description": "Max. odległość do sklepu w metrach"
                },
                "max_dist_to_bus_stop_m": {
                    "type": "integer",
                    "description": "Max. odległość do przystanku w metrach"
                },
                "max_dist_to_hospital_m": {
                    "type": "integer",
                    "description": "Max. odległość do szpitala/przychodni w metrach"
                },
                "has_road_access": {
                    "type": "boolean",
                    "description": "Czy działka musi mieć dostęp do drogi publicznej"
                },

                # === MPZP ===
                "requires_mpzp": {
                    "type": "boolean",
                    "description": "Czy działka musi mieć MPZP"
                },
                "mpzp_buildable": {
                    "type": "boolean",
                    "description": "Czy MPZP musi być budowlane"
                },
                "mpzp_symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Konkretne symbole MPZP (MN, MN/U, U, itd.)"
                },

                # === SORTOWANIE ===
                "sort_by": {
                    "type": "string",
                    "enum": ["quietness_score", "nature_score", "accessibility_score", "area_m2"],
                    "description": "Po czym sortować wyniki"
                },

                # === LEGACY (backwards compatibility) ===
                "quietness_weight": {
                    "type": "number",
                    "description": "[LEGACY] Waga cichej okolicy (0-1) - użyj quietness_categories"
                },
                "nature_weight": {
                    "type": "number",
                    "description": "[LEGACY] Waga bliskości natury (0-1) - użyj nature_categories"
                },
                "accessibility_weight": {
                    "type": "number",
                    "description": "[LEGACY] Waga dostępności (0-1) - użyj accessibility_categories"
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
                    "enum": [
                        "gmina", "miejscowosc", "powiat", "charakter_terenu",
                        "lat", "lon", "radius_m",
                        "min_area_m2", "max_area_m2", "area_category",
                        "quietness_categories", "building_density", "min_dist_to_industrial_m",
                        "nature_categories", "max_dist_to_forest_m", "max_dist_to_water_m", "min_forest_pct_500m",
                        "accessibility_categories", "max_dist_to_school_m", "max_dist_to_shop_m", "max_dist_to_bus_stop_m", "max_dist_to_hospital_m", "has_road_access",
                        "requires_mpzp", "mpzp_buildable", "mpzp_symbols", "sort_by",
                        "quietness_weight", "nature_weight", "accessibility_weight"
                    ],
                    "description": "Pole do zmiany"
                },
                "new_value": {
                    "type": ["string", "number", "boolean", "array"],
                    "description": "Nowa wartość (string, number, boolean, lub array dla list)"
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

    # =============== NAVIGATION & EXPLORATION TOOLS ===============
    {
        "name": "explore_administrative_hierarchy",
        "description": """
Przeglądaj strukturę administracyjną: województwo → powiat → gmina → miejscowość.

KIEDY UŻYWAĆ:
- User pyta "jakie powiaty są w pomorskim?" → level="wojewodztwo"
- User pyta "jakie gminy są w powiecie gdańskim?" → level="powiat", parent_name="gdański"
- User pyta "jakie wsie są w gminie Żukowo?" → level="gmina", parent_name="Żukowo"

Zwraca listę jednostek z liczbą działek.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["wojewodztwo", "powiat", "gmina"],
                    "description": "Na jakim poziomie szukać: wojewodztwo → powiaty, powiat → gminy, gmina → miejscowości"
                },
                "parent_name": {
                    "type": "string",
                    "description": "Nazwa nadrzędnej jednostki (wymagana dla powiat i gmina)"
                }
            },
            "required": ["level"]
        }
    },
    {
        "name": "get_parcel_neighborhood",
        "description": """
Pokaż PEŁNY kontekst przestrzenny działki - wszystko co jest w pobliżu.

Zwraca:
- Odległości do: szkoły, sklepu, szpitala, przystanku, przemysłu
- Odległości do: lasu, wody
- Procent lasu/wody w promieniu 500m
- Liczba budynków w 500m
- Charakter terenu, kategorie ciszy/natury/dostępności
- MPZP (symbol, nazwa, czy budowlane)

UŻYWAJ gdy user wybrał działkę i pyta "co jest w pobliżu?" lub "opowiedz o tej działce".
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
        "name": "get_area_statistics",
        "description": """
Pokaż statystyki dla gminy lub powiatu - rozkład działek po kategoriach.

Zwraca:
- Łączna liczba działek
- % z MPZP
- % z dostępem do drogi
- Rozkład po kategoriach ciszy (ile bardzo_cichych, cichych, itd.)
- Rozkład po kategoriach natury
- Rozkład po charakterze terenu

UŻYWAJ gdy user pyta "ile jest działek w X?" lub "jakie działki są w gminie Y?".
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmina": {
                    "type": "string",
                    "description": "Nazwa gminy (opcjonalna)"
                },
                "powiat": {
                    "type": "string",
                    "description": "Nazwa powiatu (opcjonalna, używaj gdy nie podano gminy)"
                }
            },
            "required": []
        }
    },
    {
        "name": "find_by_mpzp_symbol",
        "description": """
Szybkie wyszukiwanie działek z konkretnym symbolem MPZP.

Symbole budowlane: MN, MN/U, MW, MW/U, U, U/MN
Symbole niebudowlane: R (rolne), ZL (leśne), ZP (zieleń), ZZ (zagrożenie), W (wody)

UŻYWAJ gdy user mówi "szukam działki MN" lub "pokaż działki z planem pod zabudowę jednorodzinną".
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol MPZP (np. MN, MN/U, U, R, ZL)"
                },
                "gmina": {
                    "type": "string",
                    "description": "Opcjonalna gmina do filtrowania"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksymalna liczba wyników (domyślnie 20)"
                }
            },
            "required": ["symbol"]
        }
    },

    # =============== SPATIAL TOOLS (PostGIS) ===============
    {
        "name": "search_around_point",
        "description": """
SZYBKIE wyszukiwanie przestrzenne - znajdź działki w promieniu od punktu.

KIEDY UŻYWAĆ:
- User podał konkretne współrzędne lub adres
- User wskazał punkt na mapie
- Potrzebujesz szybkiego wyszukiwania bez pełnego flow propose/approve

Używa PostGIS do efektywnego wyszukiwania przestrzennego.
Zwraca działki posortowane wg odległości od punktu.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Szerokość geograficzna (WGS84)"
                },
                "lon": {
                    "type": "number",
                    "description": "Długość geograficzna (WGS84)"
                },
                "radius_m": {
                    "type": "number",
                    "description": "Promień wyszukiwania w metrach (domyślnie 5000, max 20000)"
                },
                "min_area": {
                    "type": "number",
                    "description": "Minimalna powierzchnia w m²"
                },
                "max_area": {
                    "type": "number",
                    "description": "Maksymalna powierzchnia w m²"
                },
                "has_mpzp": {
                    "type": "boolean",
                    "description": "Czy wymagać MPZP"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksymalna liczba wyników (domyślnie 20)"
                }
            },
            "required": ["lat", "lon"]
        }
    },
    {
        "name": "search_in_bbox",
        "description": """
Wyszukaj działki w prostokątnym obszarze (bounding box).

KIEDY UŻYWAĆ:
- User zaznaczył obszar na mapie
- Potrzebujesz działek z określonego regionu (nie okręgu)
- Eksplorujesz konkretny kwadrat mapy

Przydatne do eksploracji mapy - zwraca działki z widocznego obszaru.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_lat": {
                    "type": "number",
                    "description": "Minimalna szerokość geograficzna (południe)"
                },
                "min_lon": {
                    "type": "number",
                    "description": "Minimalna długość geograficzna (zachód)"
                },
                "max_lat": {
                    "type": "number",
                    "description": "Maksymalna szerokość geograficzna (północ)"
                },
                "max_lon": {
                    "type": "number",
                    "description": "Maksymalna długość geograficzna (wschód)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksymalna liczba wyników (domyślnie 50)"
                }
            },
            "required": ["min_lat", "min_lon", "max_lat", "max_lon"]
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

    # =============== PRICE TOOLS ===============
    {
        "name": "get_district_prices",
        "description": """
Pobierz informacje o cenach działek w dzielnicy.

Zwraca:
- Przedział cenowy (min-max zł/m²)
- Segment cenowy (ULTRA_PREMIUM, PREMIUM, HIGH, MEDIUM, BUDGET, ECONOMY)
- Opis charakterystyki dzielnicy

UŻYWAJ gdy:
- User pyta "ile kosztują działki w X?"
- Chcesz doradzić userowi o budżecie
- Porównujesz dzielnice cenowo

Przykład: "Osowa to segment MEDIUM, 600-740 zł/m². Za działkę 1000m² zapłacisz 600-740k zł."
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Miasto (Gdańsk, Gdynia, Sopot)"
                },
                "district": {
                    "type": "string",
                    "description": "Dzielnica (opcjonalna - jeśli nie podana, zwraca średnią dla miasta)"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "estimate_parcel_value",
        "description": """
Oszacuj wartość działki na podstawie lokalizacji i powierzchni.

Zwraca:
- Szacowany przedział cenowy (min-max zł)
- Cenę za m²
- Segment cenowy
- Poziom pewności oszacowania

UŻYWAJ gdy:
- User pyta "ile może kosztować ta działka?"
- Prezentujesz wyniki wyszukiwania z cenami
- Porównujesz wartości działek

WAŻNE: To są ORIENTACYJNE ceny rynkowe, nie ceny ofertowe. Zawsze zaznacz to userowi.
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Miasto (Gdańsk, Gdynia, Sopot)"
                },
                "district": {
                    "type": "string",
                    "description": "Dzielnica (opcjonalna)"
                },
                "area_m2": {
                    "type": "number",
                    "description": "Powierzchnia działki w m²"
                }
            },
            "required": ["city", "area_m2"]
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

        # Navigation & Exploration tools
        elif tool_name == "explore_administrative_hierarchy":
            return await _explore_administrative_hierarchy(params)
        elif tool_name == "get_parcel_neighborhood":
            return await _get_parcel_neighborhood(params)
        elif tool_name == "get_area_statistics":
            return await _get_area_statistics(params)
        elif tool_name == "find_by_mpzp_symbol":
            return await _find_by_mpzp_symbol(params)

        # Spatial tools (PostGIS)
        elif tool_name == "search_around_point":
            return await _search_around_point(params)
        elif tool_name == "search_in_bbox":
            return await _search_in_bbox(params)

        # Map tools
        elif tool_name == "generate_map_data":
            return await _generate_map_data(params)

        # Price tools
        elif tool_name == "get_district_prices":
            return await _get_district_prices(params)
        elif tool_name == "estimate_parcel_value":
            return await _estimate_parcel_value(params)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {"error": str(e)}


# --------------- HUMAN-IN-THE-LOOP IMPLEMENTATIONS ---------------

async def _propose_search_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    """Propose search preferences (perceived state) with all available dimensions."""
    state = get_state()

    # Build comprehensive preferences from all available parameters
    location_desc = params.get("location_description", "województwo pomorskie")
    gmina_param = params.get("gmina")

    # Smart location parsing: miejscowość → gmina → powiat (most specific to least)
    # This handles cases like:
    #   "Osowa" → miejscowosc=Osowa
    #   "Gdynia" or "M. Gdynia" → gmina=M. Gdynia
    #   "powiat gdański" → powiat=gdański
    miejscowosc_param = params.get("miejscowosc")
    powiat_param = params.get("powiat")

    if location_desc and not (gmina_param and miejscowosc_param and powiat_param):
        from app.services.graph_service import graph_service
        from app.services.spatial_service import spatial_service
        try:
            # Clean the location string
            clean_loc = location_desc.lower()
            clean_loc = clean_loc.replace("okolice ", "").replace("gmina ", "").replace("powiat ", "")
            clean_loc = clean_loc.replace("miasto ", "").replace("m. ", "")
            clean_loc = clean_loc.strip()

            # 1. Try miejscowość first (most specific)
            if not miejscowosc_param:
                miejscowosci = await spatial_service.get_miejscowosci()
                for m in miejscowosci:
                    if m.lower() == clean_loc:
                        miejscowosc_param = m
                        break

            # 2. Try gmina
            if not gmina_param:
                gminy = await graph_service.get_gminy()
                gminy_names = [g.name for g in gminy]
                # Direct match
                if location_desc in gminy_names:
                    gmina_param = location_desc
                else:
                    for gmina_name in gminy_names:
                        clean_gmina = gmina_name.lower().replace("m. ", "")
                        if clean_loc == clean_gmina or clean_gmina == clean_loc:
                            gmina_param = gmina_name
                            break

            # 3. Try powiat (most general)
            if not powiat_param and not gmina_param and not miejscowosc_param:
                powiaty = await spatial_service.get_powiaty()
                for p in powiaty:
                    clean_powiat = p.lower().replace("m. ", "")
                    if clean_loc == clean_powiat or clean_powiat in clean_loc:
                        powiat_param = p
                        break

        except Exception as e:
            pass  # If service not available, continue without location filters

    preferences = {
        # Location
        "location_description": location_desc,
        "gmina": gmina_param,
        "miejscowosc": miejscowosc_param,
        "powiat": powiat_param,
        "charakter_terenu": params.get("charakter_terenu"),

        # Spatial search (PostGIS)
        "lat": params.get("lat"),
        "lon": params.get("lon"),
        "radius_m": params.get("radius_m", 5000),

        # Area
        "min_area_m2": params.get("min_area_m2", 500),
        "max_area_m2": params.get("max_area_m2", 3000),
        "area_category": params.get("area_category"),

        # Quietness & Environment
        "quietness_categories": params.get("quietness_categories"),
        "building_density": params.get("building_density"),
        "min_dist_to_industrial_m": params.get("min_dist_to_industrial_m"),

        # Nature
        "nature_categories": params.get("nature_categories"),
        "max_dist_to_forest_m": params.get("max_dist_to_forest_m"),
        "max_dist_to_water_m": params.get("max_dist_to_water_m"),
        "min_forest_pct_500m": params.get("min_forest_pct_500m"),

        # Accessibility
        "accessibility_categories": params.get("accessibility_categories"),
        "max_dist_to_school_m": params.get("max_dist_to_school_m"),
        "max_dist_to_shop_m": params.get("max_dist_to_shop_m"),
        "max_dist_to_bus_stop_m": params.get("max_dist_to_bus_stop_m"),
        "max_dist_to_hospital_m": params.get("max_dist_to_hospital_m"),
        "has_road_access": params.get("has_road_access"),

        # MPZP
        "requires_mpzp": params.get("requires_mpzp", False),
        "mpzp_buildable": params.get("mpzp_buildable"),
        "mpzp_symbols": params.get("mpzp_symbols"),

        # Sorting
        "sort_by": params.get("sort_by", "quietness_score"),

        # Legacy weights (for backwards compatibility)
        "quietness_weight": params.get("quietness_weight", 0.5),
        "nature_weight": params.get("nature_weight", 0.3),
        "accessibility_weight": params.get("accessibility_weight", 0.2),
    }

    state.perceived_search_preferences = preferences

    # Build human-readable summary
    summary = {
        "lokalizacja": preferences["location_description"],
        "gmina": preferences["gmina"] or "dowolna",
    }

    if preferences["miejscowosc"]:
        summary["miejscowosc"] = preferences["miejscowosc"]
    if preferences["charakter_terenu"]:
        summary["charakter"] = ", ".join(preferences["charakter_terenu"])

    # Spatial search info
    if preferences.get("lat") and preferences.get("lon"):
        radius = preferences.get("radius_m", 5000)
        summary["wyszukiwanie_przestrzenne"] = f"w promieniu {radius/1000:.1f}km od punktu ({preferences['lat']:.4f}, {preferences['lon']:.4f})"

    summary["powierzchnia"] = f"{preferences['min_area_m2']}-{preferences['max_area_m2']} m²"

    # Environment preferences
    env_prefs = []
    if preferences["quietness_categories"]:
        env_prefs.append(f"cisza: {', '.join(preferences['quietness_categories'])}")
    if preferences["nature_categories"]:
        env_prefs.append(f"natura: {', '.join(preferences['nature_categories'])}")
    if preferences["building_density"]:
        env_prefs.append(f"zabudowa: {', '.join(preferences['building_density'])}")
    if preferences["accessibility_categories"]:
        env_prefs.append(f"dostęp: {', '.join(preferences['accessibility_categories'])}")
    if env_prefs:
        summary["preferencje_środowiska"] = env_prefs

    # Distance constraints
    dist_constraints = []
    if preferences["max_dist_to_forest_m"]:
        dist_constraints.append(f"las do {preferences['max_dist_to_forest_m']}m")
    if preferences["max_dist_to_water_m"]:
        dist_constraints.append(f"woda do {preferences['max_dist_to_water_m']}m")
    if preferences["max_dist_to_school_m"]:
        dist_constraints.append(f"szkoła do {preferences['max_dist_to_school_m']}m")
    if preferences["max_dist_to_shop_m"]:
        dist_constraints.append(f"sklep do {preferences['max_dist_to_shop_m']}m")
    if preferences.get("max_dist_to_hospital_m"):
        dist_constraints.append(f"szpital do {preferences['max_dist_to_hospital_m']}m")
    if dist_constraints:
        summary["ograniczenia_odległości"] = dist_constraints

    # MPZP
    if preferences["requires_mpzp"]:
        summary["mpzp"] = "wymagane"
        if preferences["mpzp_buildable"]:
            summary["mpzp"] += " (budowlane)"
        if preferences["mpzp_symbols"]:
            summary["mpzp"] += f" ({', '.join(preferences['mpzp_symbols'])})"
    else:
        summary["mpzp"] = "opcjonalne"

    return {
        "status": "proposed",
        "message": "Preferencje zaproponowane. Poproś użytkownika o potwierdzenie.",
        "preferences": summary,
        "raw_preferences": preferences,
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
    """Modify a specific field in perceived AND approved preferences."""
    state = get_state()

    # Check if we have any preferences to modify
    if state.perceived_search_preferences is None and state.approved_search_preferences is None:
        return {
            "error": "Brak preferencji do modyfikacji",
            "message": "Najpierw użyj propose_search_preferences.",
        }

    field = params["field"]
    new_value = params["new_value"]

    # Convert 'null' string to None (agent sometimes sends 'null' as string)
    if new_value == 'null' or new_value == 'None':
        new_value = None

    # Modify perceived preferences if they exist
    if state.perceived_search_preferences is not None:
        if field not in state.perceived_search_preferences:
            return {"error": f"Nieznane pole: {field}"}
        state.perceived_search_preferences[field] = new_value

    # ALSO modify approved preferences if they exist (so execute_search uses new value)
    if state.approved_search_preferences is not None:
        state.approved_search_preferences[field] = new_value
        return {
            "status": "modified_and_approved",
            "field": field,
            "new_value": new_value,
            "message": f"Zmieniono {field} na {new_value}. Preferencje są już zatwierdzone - możesz od razu wywołać execute_search.",
        }

    return {
        "status": "modified",
        "field": field,
        "new_value": new_value,
        "message": f"Zmieniono {field} na {new_value}. Zapytaj o ponowne potwierdzenie.",
    }


# --------------- HELPER FUNCTIONS ---------------

def _generate_highlights(parcel: Dict[str, Any], prefs: Dict[str, Any]) -> List[str]:
    """Generate highlight strings explaining why this parcel matches preferences."""
    highlights = []

    # Cisza (quietness)
    quietness = parcel.get("quietness_score", 0)
    if quietness and quietness >= 85:
        highlights.append(f"Cisza: {int(quietness)}/100")
    elif prefs.get("quietness_categories") and quietness and quietness >= 75:
        highlights.append(f"Cisza: {int(quietness)}/100")

    # Natura (nature)
    nature = parcel.get("nature_score", 0)
    if nature and nature >= 70:
        highlights.append(f"Natura: {int(nature)}/100")
    elif prefs.get("nature_categories") and nature and nature >= 60:
        highlights.append(f"Natura: {int(nature)}/100")

    # Bliskość lasu
    dist_forest = parcel.get("dist_to_forest")
    if dist_forest is not None and dist_forest < 300:
        highlights.append(f"Las: {int(dist_forest)}m")
    elif prefs.get("max_dist_to_forest_m") and dist_forest and dist_forest <= prefs["max_dist_to_forest_m"]:
        highlights.append(f"Las: {int(dist_forest)}m")

    # Bliskość wody
    dist_water = parcel.get("dist_to_water")
    if prefs.get("max_dist_to_water_m") and dist_water and dist_water <= prefs["max_dist_to_water_m"]:
        highlights.append(f"Woda: {int(dist_water)}m")

    # Dostępność (accessibility)
    accessibility = parcel.get("accessibility_score", 0)
    if accessibility and accessibility >= 80:
        highlights.append(f"Dostępność: {int(accessibility)}/100")
    elif prefs.get("accessibility_categories") and accessibility and accessibility >= 70:
        highlights.append(f"Dostępność: {int(accessibility)}/100")

    # Bliskość szkoły
    dist_school = parcel.get("dist_to_school")
    if prefs.get("max_dist_to_school_m") and dist_school and dist_school <= prefs["max_dist_to_school_m"]:
        highlights.append(f"Szkoła: {int(dist_school)}m")

    # Bliskość sklepu
    dist_shop = parcel.get("dist_to_shop")
    if prefs.get("max_dist_to_shop_m") and dist_shop and dist_shop <= prefs["max_dist_to_shop_m"]:
        highlights.append(f"Sklep: {int(dist_shop)}m")

    # Dostęp do drogi
    if prefs.get("has_road_access") and parcel.get("has_road_access"):
        if len(highlights) < 3:  # Only if we have room
            highlights.append("Dostęp do drogi")

    # MPZP
    if parcel.get("has_mpzp"):
        symbol = parcel.get("mpzp_symbol", "")
        if symbol:
            highlights.append(f"MPZP: {symbol}")
        else:
            highlights.append("Ma MPZP")

    # If user prioritized quietness via weight and parcel is quiet (legacy support)
    if prefs.get("quietness_weight", 0) >= 0.5 and quietness and quietness >= 80:
        if not any("Cisza" in h for h in highlights):
            highlights.append("Cicha okolica")

    # If user prioritized nature via weight and parcel is green (legacy support)
    if prefs.get("nature_weight", 0) >= 0.5 and nature and nature >= 70:
        if not any("Natura" in h for h in highlights):
            highlights.append("Blisko natury")

    return highlights[:4]  # Max 4 highlights


def _generate_explanation(parcel: Dict[str, Any]) -> str:
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

    # Build comprehensive search preferences using all available fields
    search_prefs = SearchPreferences(
        # Location (agent should explicitly set gmina if user specified one)
        gmina=prefs.get("gmina"),
        miejscowosc=prefs.get("miejscowosc"),
        powiat=prefs.get("powiat"),

        # Spatial search (PostGIS) - if lat/lon provided, use radius search
        lat=prefs.get("lat"),
        lon=prefs.get("lon"),
        radius_m=prefs.get("radius_m", 5000),

        # Area
        min_area=prefs.get("min_area_m2"),
        max_area=prefs.get("max_area_m2"),
        area_category=prefs.get("area_category"),

        # Character & Environment
        charakter_terenu=prefs.get("charakter_terenu"),
        quietness_categories=prefs.get("quietness_categories"),
        building_density=prefs.get("building_density"),
        min_dist_to_industrial_m=prefs.get("min_dist_to_industrial_m"),

        # Nature
        nature_categories=prefs.get("nature_categories"),
        max_dist_to_forest_m=prefs.get("max_dist_to_forest_m"),
        max_dist_to_water_m=prefs.get("max_dist_to_water_m"),
        min_forest_pct_500m=prefs.get("min_forest_pct_500m"),

        # Accessibility
        accessibility_categories=prefs.get("accessibility_categories"),
        max_dist_to_school_m=prefs.get("max_dist_to_school_m"),
        max_dist_to_shop_m=prefs.get("max_dist_to_shop_m"),
        max_dist_to_bus_stop_m=prefs.get("max_dist_to_bus_stop_m"),
        max_dist_to_hospital_m=prefs.get("max_dist_to_hospital_m"),
        has_road_access=prefs.get("has_road_access"),

        # MPZP
        has_mpzp=prefs.get("requires_mpzp"),
        mpzp_budowlane=prefs.get("mpzp_buildable"),
        mpzp_symbols=prefs.get("mpzp_symbols"),

        # Sorting
        sort_by=prefs.get("sort_by", "quietness_score"),

        # Legacy weights (for backwards compatibility)
        quietness_weight=prefs.get("quietness_weight", 0.5),
        nature_weight=prefs.get("nature_weight", 0.3),
        accessibility_weight=prefs.get("accessibility_weight", 0.2),
    )

    # Execute hybrid search (Graph as PRIMARY)
    results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

    # Store results for critic pattern, including highlights and explanations
    state.current_search_results = []
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
            # New fields from graph search
            "dist_to_forest": r.dist_to_forest,
            "dist_to_water": r.dist_to_water,
            "dist_to_school": r.dist_to_school,
            "dist_to_shop": r.dist_to_shop,
            "pct_forest_500m": r.pct_forest_500m,
            "has_road_access": r.has_road_access,
        }
        # Add highlights and explanation for the reveal card
        parcel_dict["highlights"] = _generate_highlights(parcel_dict, prefs)
        parcel_dict["explanation"] = _generate_explanation(parcel_dict)
        state.current_search_results.append(parcel_dict)

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

    # Quietness adjustments - use categories when available
    if "cich" in adjustment_lower or "spok" in adjustment_lower:
        # If we have quietness_categories, make them stricter
        if prefs.get("quietness_categories"):
            prefs["quietness_categories"] = ["bardzo_cicha", "cicha"]
        else:
            # Set categories for the first time
            prefs["quietness_categories"] = ["bardzo_cicha", "cicha"]
        # Also reduce building density
        prefs["building_density"] = ["rzadka", "bardzo_rzadka"]

    # Nature adjustments
    if "natur" in adjustment_lower or "las" in adjustment_lower or "zielen" in adjustment_lower:
        if prefs.get("nature_categories"):
            prefs["nature_categories"] = ["bardzo_zielona", "zielona"]
        else:
            prefs["nature_categories"] = ["bardzo_zielona", "zielona"]
        # Also add forest proximity constraint
        if not prefs.get("max_dist_to_forest_m"):
            prefs["max_dist_to_forest_m"] = 500

    # Accessibility adjustments
    if "dojazd" in adjustment_lower or "sklep" in adjustment_lower or "szkol" in adjustment_lower:
        prefs["accessibility_categories"] = ["doskonały", "dobry"]

    # Industrial distance (for quieter areas)
    if "przemysł" in adjustment_lower or "fabryk" in adjustment_lower or "hałas" in adjustment_lower:
        prefs["min_dist_to_industrial_m"] = (prefs.get("min_dist_to_industrial_m") or 500) + 500

    # MPZP adjustments
    if "mpzp" in adjustment_lower or "plan" in adjustment_lower:
        prefs["requires_mpzp"] = True

    # Ensure min <= max (safety check)
    if prefs.get("min_area_m2", 0) > prefs.get("max_area_m2", 10000):
        prefs["min_area_m2"], prefs["max_area_m2"] = prefs["max_area_m2"], prefs["min_area_m2"]

    # Clear feedback, increment iteration
    state.search_feedback = None
    state.approved_search_preferences = prefs

    logger.info(f"Refined preferences: area={prefs.get('min_area_m2')}-{prefs.get('max_area_m2')}, "
               f"quietness={prefs.get('quietness_categories')}, nature={prefs.get('nature_categories')}")

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


# --------------- NAVIGATION & EXPLORATION IMPLEMENTATIONS ---------------

async def _explore_administrative_hierarchy(params: Dict[str, Any]) -> Dict[str, Any]:
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

    # Generate human-readable summary
    if level == "wojewodztwo":
        summary = f"W województwie pomorskim jest {len(results)} powiatów"
        items = [
            f"{r['name']} ({r.get('gminy_count', 0)} gmin, {r.get('parcel_count', 0):,} działek)"
            for r in results
        ]
    elif level == "powiat":
        summary = f"W powiecie {parent_name} jest {len(results)} gmin"
        items = [
            f"{r['name']} ({r.get('parcel_count', 0):,} działek)"
            for r in results
        ]
    else:  # gmina
        summary = f"W gminie {parent_name} jest {len(results)} miejscowości"
        items = [
            f"{r['name']} ({r.get('rodzaj', 'wieś')}, {r.get('parcel_count', 0):,} działek)"
            for r in results[:20]  # Limit to 20 for readability
        ]
        if len(results) > 20:
            items.append(f"... i {len(results) - 20} więcej")

    return {
        "level": level,
        "parent": parent_name,
        "count": len(results),
        "summary": summary,
        "items": items,
        "raw_data": results[:30],  # Limit raw data to 30 items
    }


async def _get_parcel_neighborhood(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed neighborhood context for a parcel."""
    parcel_id = params["parcel_id"]

    result = await graph_service.get_parcel_neighborhood(parcel_id)

    if "error" in result:
        return result

    # Format distances for human readability
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


async def _get_area_statistics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get statistics for a gmina or powiat."""
    gmina = params.get("gmina")
    powiat = params.get("powiat")

    result = await graph_service.get_area_category_stats(gmina=gmina, powiat=powiat)

    if "error" in result:
        return result

    # Format distributions for human readability
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


async def _find_by_mpzp_symbol(params: Dict[str, Any]) -> Dict[str, Any]:
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

    # Format results
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


# --------------- SPATIAL (PostGIS) IMPLEMENTATIONS ---------------

async def _search_around_point(params: Dict[str, Any]) -> Dict[str, Any]:
    """Search parcels within radius of a point using PostGIS."""
    lat = params["lat"]
    lon = params["lon"]
    radius_m = min(params.get("radius_m", 5000), 20000)  # Cap at 20km
    limit = params.get("limit", 20)

    # Validate coordinates (roughly Poland)
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

    # Format results with distance info
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


async def _search_in_bbox(params: Dict[str, Any]) -> Dict[str, Any]:
    """Search parcels in bounding box using PostGIS."""
    min_lat = params["min_lat"]
    min_lon = params["min_lon"]
    max_lat = params["max_lat"]
    max_lon = params["max_lon"]
    limit = params.get("limit", 50)

    # Validate bounding box
    if min_lat >= max_lat or min_lon >= max_lon:
        return {"error": "Nieprawidłowy bounding box: min musi być mniejsze od max"}

    # Check if bbox is within Poland (roughly)
    if not (49.0 <= min_lat <= 55.0 and 14.0 <= min_lon <= 24.0):
        return {"error": "Bounding box poza Polską"}

    # Check bbox size (max ~50km x 50km)
    lat_diff = max_lat - min_lat
    lon_diff = max_lon - min_lon
    if lat_diff > 0.5 or lon_diff > 0.7:  # Roughly 50km
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

    # Format results
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

    # Calculate center
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    return {
        "count": len(results),
        "message": f"Znaleziono {len(results)} działek w zaznaczonym obszarze",
        "bbox": {"min_lat": min_lat, "min_lon": min_lon, "max_lat": max_lat, "max_lon": max_lon},
        "center": {"lat": center_lat, "lon": center_lon},
        "parcels": parcels,
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


# --------------- PRICE IMPLEMENTATIONS ---------------

# District price data (from egib/scripts/pipeline/07a_district_prices.py)
DISTRICT_PRICES = {
    # Gdańsk - Premium
    ("Gdańsk", "Jelitkowo"): {"min": 1500, "max": 2000, "segment": "PREMIUM", "desc": "Najdroższa dzielnica, blisko morza"},
    ("Gdańsk", "Śródmieście"): {"min": 1200, "max": 2000, "segment": "PREMIUM", "desc": "Centrum miasta"},
    ("Gdańsk", "Oliwa"): {"min": 1000, "max": 1500, "segment": "HIGH", "desc": "Prestiżowa dzielnica, las"},
    ("Gdańsk", "Brzeźno"): {"min": 1000, "max": 1500, "segment": "HIGH", "desc": "Blisko plaży"},
    # Gdańsk - Medium
    ("Gdańsk", "Wrzeszcz"): {"min": 600, "max": 750, "segment": "MEDIUM", "desc": "Centrum komunikacyjne"},
    ("Gdańsk", "Zaspa"): {"min": 650, "max": 900, "segment": "MEDIUM", "desc": "Dobra komunikacja"},
    ("Gdańsk", "Przymorze"): {"min": 700, "max": 1000, "segment": "HIGH", "desc": "Blisko morza"},
    ("Gdańsk", "Kokoszki"): {"min": 600, "max": 700, "segment": "MEDIUM", "desc": "Rozwijająca się, popularna"},
    ("Gdańsk", "Osowa"): {"min": 600, "max": 740, "segment": "MEDIUM", "desc": "Przy TPK, spokojna"},
    ("Gdańsk", "Jasień"): {"min": 600, "max": 800, "segment": "MEDIUM", "desc": "Popularna, dużo ofert"},
    ("Gdańsk", "Olszynka"): {"min": 500, "max": 650, "segment": "MEDIUM", "desc": "Dostępna cenowo"},
    ("Gdańsk", "VII Dwór"): {"min": 550, "max": 700, "segment": "MEDIUM", "desc": "Cicha, zielona"},
    ("Gdańsk", "Matemblewo"): {"min": 500, "max": 700, "segment": "MEDIUM", "desc": "Przy TPK, spokój"},
    # Gdańsk - Budget
    ("Gdańsk", "Łostowice"): {"min": 370, "max": 500, "segment": "BUDGET", "desc": "Szybko rozwijająca się"},
    ("Gdańsk", "Ujeścisko-Łostowice"): {"min": 370, "max": 500, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdańsk", "Chełm"): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "Tańsza alternatywa"},
    ("Gdańsk", "Orunia"): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "Niższe ceny"},
    ("Gdańsk", "Matarnia"): {"min": 450, "max": 600, "segment": "BUDGET", "desc": "Przy lotnisku"},
    # Gdańsk fallback
    ("Gdańsk", None): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Średnia dla Gdańska"},

    # Gdynia - Premium
    ("Gdynia", "Kamienna Góra"): {"min": 5000, "max": 15000, "segment": "ULTRA_PREMIUM", "desc": "Najbardziej prestiżowa"},
    ("Gdynia", "Orłowo"): {"min": 1800, "max": 2500, "segment": "PREMIUM", "desc": "Klif, wille, plaża"},
    ("Gdynia", "Śródmieście"): {"min": 1500, "max": 3000, "segment": "PREMIUM", "desc": "Centrum, bulwar"},
    ("Gdynia", "Redłowo"): {"min": 1500, "max": 2500, "segment": "PREMIUM", "desc": "Prestiżowa dzielnica"},
    # Gdynia - High
    ("Gdynia", "Mały Kack"): {"min": 900, "max": 1400, "segment": "HIGH", "desc": "Dobra komunikacja"},
    ("Gdynia", "Działki Leśne"): {"min": 900, "max": 1200, "segment": "HIGH", "desc": "Zieleń, spokój"},
    ("Gdynia", "Grabówek"): {"min": 800, "max": 1200, "segment": "HIGH", "desc": "Blisko centrum"},
    # Gdynia - Medium/Budget
    ("Gdynia", "Wielki Kack"): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Tańsza alternatywa"},
    ("Gdynia", "Wiczlino"): {"min": 400, "max": 800, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdynia", "Chwarzno-Wiczlino"): {"min": 400, "max": 800, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdynia", "Chylonia"): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Zróżnicowana"},
    ("Gdynia", "Obłuże"): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Tańsza opcja"},
    ("Gdynia", "Pogórze"): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Najtańsze w Gdyni"},
    # Gdynia fallback
    ("Gdynia", None): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Średnia dla Gdyni"},

    # Sopot
    ("Sopot", "Dolny Sopot"): {"min": 4000, "max": 8000, "segment": "ULTRA_PREMIUM", "desc": "Przy Monte Cassino"},
    ("Sopot", "Karlikowo"): {"min": 3000, "max": 5000, "segment": "ULTRA_PREMIUM", "desc": "Luksusowa, wille"},
    ("Sopot", "Kamienny Potok"): {"min": 2500, "max": 4000, "segment": "PREMIUM", "desc": "Spokojna lokalizacja"},
    ("Sopot", "Górny Sopot"): {"min": 2000, "max": 3500, "segment": "PREMIUM", "desc": "Rodzinna, zieleń"},
    ("Sopot", "Brodwino"): {"min": 1500, "max": 2500, "segment": "PREMIUM", "desc": "Najtańsza w Sopocie"},
    # Sopot fallback
    ("Sopot", None): {"min": 2000, "max": 3500, "segment": "PREMIUM", "desc": "Średnia dla Sopotu"},

    # Okolice
    ("Chwaszczyno", None): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "14km od Gdyni"},
    ("Pruszcz Gdański", None): {"min": 300, "max": 400, "segment": "BUDGET", "desc": "10km od Gdańska"},
    ("Żukowo", None): {"min": 170, "max": 300, "segment": "ECONOMY", "desc": "20km od Gdyni"},
    ("Rumia", None): {"min": 300, "max": 600, "segment": "BUDGET", "desc": "15km od Gdyni"},
    ("Kolbudy", None): {"min": 150, "max": 350, "segment": "ECONOMY", "desc": "15km od Gdańska"},
}

SEGMENT_DESCRIPTIONS = {
    "ULTRA_PREMIUM": ">3000 zł/m² - najbardziej prestiżowe lokalizacje",
    "PREMIUM": "1500-3000 zł/m² - dzielnice premium",
    "HIGH": "800-1500 zł/m² - drogie dzielnice",
    "MEDIUM": "500-800 zł/m² - średnia półka",
    "BUDGET": "300-500 zł/m² - przystępne ceny",
    "ECONOMY": "<300 zł/m² - najtańsze lokalizacje",
}


async def _get_district_prices(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get price information for a district."""
    city = params.get("city", "").strip()
    district = params.get("district")

    if not city:
        return {"error": "Podaj miasto (Gdańsk, Gdynia, Sopot)"}

    # Normalize city name
    city_normalized = city.title()
    if city_normalized.startswith("M. "):
        city_normalized = city_normalized[3:]

    # Try exact match first
    key = (city_normalized, district)
    if key not in DISTRICT_PRICES:
        # Try without district (city average)
        key = (city_normalized, None)

    if key not in DISTRICT_PRICES:
        # Try case-insensitive district search
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


async def _estimate_parcel_value(params: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate parcel value based on location and area."""
    city = params.get("city", "").strip()
    district = params.get("district")
    area_m2 = params.get("area_m2")

    if not city:
        return {"error": "Podaj miasto (Gdańsk, Gdynia, Sopot)"}
    if not area_m2 or area_m2 <= 0:
        return {"error": "Podaj powierzchnię działki w m²"}

    # Normalize city name
    city_normalized = city.title()
    if city_normalized.startswith("M. "):
        city_normalized = city_normalized[3:]

    # Find price data
    key = (city_normalized, district)
    if key not in DISTRICT_PRICES:
        key = (city_normalized, None)

    # Try case-insensitive search
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

    # Format prices nicely
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
