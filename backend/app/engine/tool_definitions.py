"""
Tool Definitions - 16 consolidated tools in Claude API format.

Each tool definition includes name, description, and input_schema.
These replace the previous 38+ tools with a clean, consolidated set.
"""

from typing import List, Dict, Any


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return all 16 tool definitions in Claude API format."""
    return [
        # =====================================================================
        # LOCATION (2 tools)
        # =====================================================================
        {
            "name": "location_search",
            "description": (
                "Wyszukaj lokalizację w bazie danych. Podaj nazwę w mianowniku. "
                "Przeszukuje: dzielnice, gminy, powiaty, miejscowości. "
                "Wspiera fuzzy matching i wyszukiwanie wektorowe. "
                "Zastępuje: search_locations, resolve_entity, get_available_locations, get_districts_in_miejscowosc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nazwa lokalizacji w mianowniku (np. 'Osowa', 'Gdańsk', 'Wrzeszcz')"
                    },
                    "parent_name": {
                        "type": "string",
                        "description": "Opcjonalna nazwa nadrzędna dla zawężenia (np. 'Gdańsk' gdy szukamy dzielnicy)"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["dzielnica", "gmina", "powiat", "miejscowosc", "any"],
                        "description": "Poziom hierarchii do wyszukania. Domyślnie 'any' (wszystkie)."
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "location_confirm",
            "description": (
                "Potwierdź i zapisz lokalizację po walidacji z użytkownikiem. "
                "Używaj DOKŁADNYCH wartości z wyników location_search. "
                "Zapisuje lokalizację w notepad — kolejne narzędzia używają jej automatycznie."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "gmina": {"type": "string", "description": "Gmina/miasto (np. 'Gdańsk')"},
                    "dzielnica": {"type": "string", "description": "Dzielnica (np. 'Osowa')"},
                    "miejscowosc": {"type": "string", "description": "Miejscowość"},
                    "powiat": {"type": "string", "description": "Powiat"},
                },
                "required": ["gmina"],
            },
        },

        # =====================================================================
        # SEARCH (5 tools)
        # =====================================================================
        {
            "name": "search_count",
            "description": (
                "Szybki COUNT działek pasujących do filtrów. Używaj jako checkpoint. "
                "Lokalizacja pobierana automatycznie z notepad.location."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ownership_type": {"type": "string", "description": "Typ własności: prywatna, publiczna, spółdzielcza, kościelna, inna"},
                    "build_status": {"type": "string", "description": "Status: zabudowana, niezabudowana"},
                    "size_category": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie rozmiaru: mala, pod_dom, duza, bardzo_duza"
                    },
                    "quietness_categories": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie ciszy: bardzo_cicha, cicha, umiarkowana, głośna"
                    },
                    "nature_categories": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie natury: bardzo_zielona, zielona, umiarkowana, zurbanizowana"
                    },
                },
                "required": [],
            },
        },
        {
            "name": "search_execute",
            "description": (
                "Wykonaj hybrydowe wyszukiwanie działek (graph + vector + spatial). "
                "Wymaga zwalidowanej lokalizacji (notepad.location.validated=true). "
                "Wyniki zapisywane do pliku JSONL. Użyj results_load_page do paginacji. "
                "Zastępuje: execute_search, search_by_criteria, propose/approve preferences."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ownership_type": {"type": "string", "description": "Typ własności: prywatna (domyślne), publiczna, spółdzielcza, kościelna, inna"},
                    "build_status": {"type": "string", "description": "Status: niezabudowana (domyślne), zabudowana"},
                    "size_category": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie: mala(<500), pod_dom(500-2000), duza(2-5k), bardzo_duza(>5k)"
                    },
                    "min_area_m2": {"type": "number", "description": "Minimalna powierzchnia w m²"},
                    "max_area_m2": {"type": "number", "description": "Maksymalna powierzchnia w m²"},
                    "quietness_categories": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie ciszy: bardzo_cicha, cicha, umiarkowana, głośna"
                    },
                    "nature_categories": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Kategorie natury: bardzo_zielona, zielona, umiarkowana, zurbanizowana"
                    },
                    "building_density": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Gęstość zabudowy: bardzo_gesta, gesta, umiarkowana, rzadka, bardzo_rzadka"
                    },
                    "accessibility_categories": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Dostępność: doskonała, dobra, umiarkowana, ograniczona"
                    },
                    "water_type": {"type": "string", "description": "Typ wody: morze, zatoka, rzeka, jezioro, kanal, staw"},
                    "max_dist_to_forest_m": {"type": "integer", "description": "Max odległość do lasu w metrach"},
                    "max_dist_to_water_m": {"type": "integer", "description": "Max odległość do wody w metrach"},
                    "max_dist_to_school_m": {"type": "integer", "description": "Max odległość do szkoły w metrach"},
                    "max_dist_to_shop_m": {"type": "integer", "description": "Max odległość do sklepu w metrach"},
                    "max_dist_to_bus_stop_m": {"type": "integer", "description": "Max odległość do przystanku"},
                    "pog_residential": {"type": "boolean", "description": "Tylko strefy mieszkaniowe POG"},
                    "sort_by": {
                        "type": "string",
                        "enum": ["quietness_score", "nature_score", "accessibility_score", "area_m2"],
                        "description": "Sortowanie wyników (domyślnie quietness_score)"
                    },
                    "query_text": {"type": "string", "description": "Tekst do wyszukiwania semantycznego (opcjonalny, auto-generowany z filtrów)"},
                    "limit": {"type": "integer", "description": "Max wyników (domyślnie 30, max 50)"},
                },
                "required": [],
            },
        },
        {
            "name": "search_refine",
            "description": (
                "Doprecyzuj wyniki wyszukiwania zmieniając parametry. "
                "Podaj TYLKO parametry które chcesz zmienić — reszta z poprzedniego searcha."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "object",
                        "description": "Mapa zmian: {nazwa_parametru: nowa_wartość}. Np. {'max_dist_to_school_m': 1000, 'quietness_categories': ['bardzo_cicha']}"
                    },
                },
                "required": ["changes"],
            },
        },
        {
            "name": "search_similar",
            "description": (
                "Znajdź działki podobne do podanej (graph embeddings 256-dim). "
                "Używaj gdy user lubi konkretną działkę i chce podobne."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string", "description": "ID działki referencyjnej (np. '220611_2.0001.1234')"},
                    "limit": {"type": "integer", "description": "Max wyników (domyślnie 10)"},
                },
                "required": ["parcel_id"],
            },
        },
        {
            "name": "search_adjacent",
            "description": (
                "Znajdź działki sąsiadujące z podaną (relacja ADJACENT_TO, 407k relacji). "
                "Używaj gdy user chce kupić sąsiednie działki lub potrzebuje większej powierzchni."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string", "description": "ID działki (np. '220611_2.0001.1234')"},
                    "limit": {"type": "integer", "description": "Max sąsiadów (domyślnie 20)"},
                },
                "required": ["parcel_id"],
            },
        },

        # =====================================================================
        # PARCEL INFO (2 tools)
        # =====================================================================
        {
            "name": "parcel_details",
            "description": (
                "Pełne szczegóły działki: 49 atrybutów + GeoJSON geometry + relacje Neo4j. "
                "Zastępuje: get_parcel_full_context, get_parcel_details, get_parcel_neighborhood, get_water_info, get_zoning_info."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string", "description": "ID działki lub numer referencyjny (1, 2, 3) z wyników"},
                },
                "required": ["parcel_id"],
            },
        },
        {
            "name": "parcel_compare",
            "description": (
                "Porównaj 2-5 działek obok siebie. Tworzy tabelę porównawczą z rekomendacją."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "parcel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                        "description": "Lista ID działek lub numerów referencyjnych do porównania"
                    },
                },
                "required": ["parcel_ids"],
            },
        },

        # =====================================================================
        # MARKET (2 tools)
        # =====================================================================
        {
            "name": "market_prices",
            "description": (
                "Średnie ceny działek w dzielnicach/gminach. Zastępuje: get_district_prices, estimate_parcel_value, market_analysis."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "gmina": {"type": "string", "description": "Gmina/miasto (opcjonalne, domyślnie z notepad.location)"},
                    "dzielnica": {"type": "string", "description": "Dzielnica (opcjonalne)"},
                    "parcel_id": {"type": "string", "description": "ID działki do wyceny (opcjonalne)"},
                },
                "required": [],
            },
        },
        {
            "name": "market_map",
            "description": (
                "Generuj dane mapy GeoJSON dla wyników wyszukiwania lub konkretnych działek."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "parcel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista ID działek do wyświetlenia na mapie"
                    },
                    "include_geometry": {"type": "boolean", "description": "Czy dołączyć pełne polygony (domyślnie true)"},
                },
                "required": [],
            },
        },

        # =====================================================================
        # PAGINATION & NOTEPAD (2 tools)
        # =====================================================================
        {
            "name": "results_load_page",
            "description": (
                "Załaduj stronę wyników z pliku JSONL. Używaj po search_execute do paginacji."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "description": "Numer strony (0-based, domyślnie 0)"},
                    "page_size": {"type": "integer", "description": "Wyników na stronę (domyślnie 10)"},
                },
                "required": [],
            },
        },
        {
            "name": "notepad_update",
            "description": (
                "Aktualizuj pola notepad zarządzane przez agenta: user_goal, preferences, next_step, notes."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_goal": {"type": "string", "description": "Cel użytkownika (np. 'Szuka cichej działki pod dom')"},
                    "preferences": {
                        "type": "object",
                        "description": "Kryteria wyszukiwania budowane iteracyjnie"
                    },
                    "next_step": {"type": "string", "description": "Co zrobić dalej (np. 'Dopytać o rozmiar')"},
                    "notes": {
                        "type": "string",
                        "description": "Notatka do dodania (string dodaje, tablica nadpisuje)"
                    },
                },
                "required": [],
            },
        },

        # =====================================================================
        # LEAD (2 tools)
        # =====================================================================
        {
            "name": "lead_capture",
            "description": (
                "Zapisz dane kontaktowe użytkownika. Wymagany email lub telefon."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Adres email"},
                    "phone": {"type": "string", "description": "Numer telefonu"},
                    "name": {"type": "string", "description": "Imię (opcjonalne)"},
                    "notes": {"type": "string", "description": "Dodatkowe notatki"},
                },
                "required": [],
            },
        },
        {
            "name": "lead_summary",
            "description": (
                "Generuj podsumowanie sesji dla użytkownika. Zawiera znalezione działki, preferencje, ulubione."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["text", "email"],
                        "description": "Format podsumowania (domyślnie text)"
                    },
                },
                "required": [],
            },
        },
    ]


# Precomputed set of tool names for validation
TOOL_NAMES = {t["name"] for t in get_tool_definitions()}
