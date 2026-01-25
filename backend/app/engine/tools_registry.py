"""
Tools Registry - Tool Schemas for Claude API.

Contains only the tool definitions (schemas) used by Claude for tool calling.
Actual implementations are in tool_executor.py.
"""

from typing import List, Dict, Any


# =============================================================================
# TOOL DEFINITIONS (Claude API format)
# =============================================================================

AGENT_TOOLS: List[Dict[str, Any]] = [
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

                # NOTE: charakter_terenu removed - data not available in Neo4j

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

                # === WŁASNOŚĆ (NOWE - Neo4j v2) ===
                "ownership_type": {
                    "type": "string",
                    "enum": ["prywatna", "publiczna", "spoldzielcza", "koscielna", "inna"],
                    "description": "Typ własności. 'prywatna' = działki do kupienia (78k dostępnych)"
                },

                # === STATUS ZABUDOWY (NOWE - Neo4j v2) ===
                "build_status": {
                    "type": "string",
                    "enum": ["zabudowana", "niezabudowana"],
                    "description": "Status zabudowy. 'niezabudowana' = idealna pod budowę (93k dostępnych)"
                },

                # === KATEGORIA ROZMIARU (NOWE - Neo4j v2) ===
                "size_category": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mala", "pod_dom", "duza", "bardzo_duza"]},
                    "description": "Kategorie rozmiaru: mala (<500m²), pod_dom (500-2000m² - idealne!), duza (2000-5000m²), bardzo_duza (>5000m²)"
                },

                # === POG (NOWE - Neo4j v2) ===
                "pog_residential": {
                    "type": "boolean",
                    "description": "Tylko działki w strefach mieszkaniowych POG (MN, MW)"
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
                        "gmina", "miejscowosc", "powiat",
                        "lat", "lon", "radius_m",
                        "min_area_m2", "max_area_m2", "area_category", "size_category",
                        "ownership_type", "build_status", "pog_residential",
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
        "name": "count_matching_parcels_quick",
        "description": """
CHECKPOINT SEARCH: Szybkie sprawdzenie ile działek pasuje do AKTUALNYCH kryteriów.

KIEDY UŻYWAĆ:
- W trakcie zbierania preferencji (discovery), żeby informować usera o postępie
- Po zebraniu 2-3 preferencji, pokaż: "Na tym etapie mam już X działek pasujących"
- Pomaga userowi zrozumieć wpływ każdego kryterium

Używa preferencji z pamięci stanu (perceived_preferences).
Możesz dodać parametry żeby nadpisać lub rozszerzyć.

PRZYKŁAD:
User: "Szukam w Gdańsku" → count_matching_parcels_quick()
→ "Na podstawie aktualnych kryteriów: 45,000 pasujących działek."
User: "Blisko lasu" → count_matching_parcels_quick()
→ "Na podstawie aktualnych kryteriów: 12,300 pasujących działek."
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmina": {
                    "type": "string",
                    "description": "Opcjonalnie nadpisz gminę"
                },
                "miejscowosc": {
                    "type": "string",
                    "description": "Opcjonalnie nadpisz dzielnicę"
                },
                "min_area_m2": {
                    "type": "number",
                    "description": "Opcjonalnie nadpisz min powierzchnię"
                },
                "max_area_m2": {
                    "type": "number",
                    "description": "Opcjonalnie nadpisz max powierzchnię"
                }
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

    # =========================================================================
    # WATER-RELATED TOOLS (Neo4j Redesign)
    # =========================================================================
    {
        "name": "search_by_water_type",
        "description": """
Wyszukaj działki blisko określonego typu wody.

TYPY WÓD (Trójmiasto):
- morze: Morze Bałtyckie, linia brzegowa (Brzeźno, Jelitkowo, Sopot, Orłowo)
- jezioro: Osowskie, Jasień, Wysockie, Straszyńskie - idealne dla rodzin
- rzeka: Radunia, Motława, Strzyża - walor krajobrazowy
- kanal: Kanał Raduni - historyczne kanały
- staw: Małe zbiorniki wodne, oczka

WPŁYW NA CENĘ:
- Morze <500m: +50-100% wartości
- Jezioro <300m: +20-40%
- Rzeka <200m: +10-20%

UŻYWAJ gdy:
- User mówi "blisko morza", "nad jeziorem", "przy wodzie"
- PYTAJ o typ wody gdy user mówi ogólnie "blisko wody"!

EXAMPLE: User: "Działka nad morzem w Sopocie"
→ search_by_water_type(water_type="morze", city="Sopot", max_distance=500)
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "water_type": {
                    "type": "string",
                    "enum": ["morze", "jezioro", "rzeka", "kanal", "staw"],
                    "description": "Typ wody do wyszukania"
                },
                "max_distance": {
                    "type": "integer",
                    "description": "Maksymalna odległość w metrach (domyślnie 500)"
                },
                "city": {
                    "type": "string",
                    "description": "Miasto (Gdańsk, Gdynia, Sopot) - opcjonalne"
                },
                "min_area": {
                    "type": "integer",
                    "description": "Minimalna powierzchnia w m²"
                },
                "max_area": {
                    "type": "integer",
                    "description": "Maksymalna powierzchnia w m²"
                },
                "is_built": {
                    "type": "boolean",
                    "description": "Filtr zabudowania (true=zabudowane, false=niezabudowane)"
                },
                "is_residential_zone": {
                    "type": "boolean",
                    "description": "Tylko strefy mieszkaniowe"
                },
                "limit": {
                    "type": "integer",
                    "description": "Liczba wyników (domyślnie 10)"
                }
            },
            "required": ["water_type"]
        }
    },
    {
        "name": "get_water_info",
        "description": """
Pobierz informacje o wodach w pobliżu działki.

Zwraca:
- Odległości do wszystkich typów wód (morze, jezioro, rzeka, kanał, staw)
- Najbliższy typ wody
- Podsumowanie tekstowe

UŻYWAJ gdy:
- Prezentujesz szczegóły działki i chcesz dodać info o wodzie
- User pyta "co jest w pobliżu tej działki?"
- Chcesz wyjaśnić wartość lokalizacji (bliskość wody = premium)
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki (np. '220101_1.0001.24/1')"
                }
            },
            "required": ["parcel_id"]
        }
    },
    {
        "name": "get_parcel_full_context",
        "description": """
Pobierz PEŁNY kontekst działki dla kompleksowej prezentacji.

Zwraca WSZYSTKO:
- Lokalizacja (dzielnica, gmina)
- Kategorie (cisza, natura, dostęp, gęstość zabudowy)
- Odległości do POI (szkoła, przystanek, las, woda)
- Informacje o wodzie (typ, odległość, premium factor)
- POG/MPZP (strefa, parametry zabudowy)
- Segment cenowy i szacowana wartość
- Podsumowanie tekstowe

UŻYWAJ gdy:
- Prezentujesz wybraną działkę szczegółowo
- User pyta "opowiedz mi więcej o tej działce"
- Chcesz dać pełny obraz przed podjęciem decyzji
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki (np. '220101_1.0001.24/1')"
                }
            },
            "required": ["parcel_id"]
        }
    },

    # =========================================================================
    # DYNAMIC LOCATION TOOLS (2026-01-25)
    # Agent dynamically queries these instead of hardcoded lists
    # =========================================================================
    {
        "name": "get_available_locations",
        "description": """
Pobierz dostępne lokalizacje DYNAMICZNIE z bazy danych.

KIEDY UŻYWAĆ:
- Na początku rozmowy, aby wiedzieć jakie lokalizacje są dostępne
- Gdy user poda niejednoznaczną lokalizację
- Zamiast zgadywać - ZAWSZE odpytuj bazę!

Zwraca:
- Lista miejscowości (Gdańsk, Gdynia, Sopot)
- Lista gmin (w MVP = miejscowości)
- Łączna liczba działek
- Liczba działek per miejscowość

WAŻNE: Nie używaj hardkodowanych list! System jest skalowalny.
""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_districts_in_miejscowosc",
        "description": """
Pobierz dzielnice w danej MIEJSCOWOŚCI (nie gminie!).

HIERARCHIA ADMINISTRACYJNA:
- Gmina = jednostka administracyjna
- Miejscowość = osada/miasto (gdzie ludzie mieszkają)
- Dzielnica = część MIEJSCOWOŚCI!

WAŻNE: Dzielnica należy do MIEJSCOWOŚCI, nie do gminy!
- Osowa należy do miejscowości Gdańsk
- Orłowo należy do miejscowości Gdynia
- W Trójmieście: gmina = miejscowość (to samo)

KIEDY UŻYWAĆ:
- User podał miasto, chcesz pokazać dzielnice
- User mówi "jakie dzielnice są w Gdańsku?"
- Przed propose_search_preferences - sprawdź czy dzielnica istnieje

Zwraca:
- Lista dzielnic z liczbą działek
- Gmina (dla kontekstu)
- Miejscowość
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "miejscowosc": {
                    "type": "string",
                    "description": "Nazwa miejscowości (np. 'Gdańsk', 'Gdynia', 'Sopot')"
                }
            },
            "required": ["miejscowosc"]
        }
    },
    {
        "name": "resolve_location",
        "description": """
KLUCZOWE NARZĘDZIE! Rozwiąż tekst lokalizacji do gmina + miejscowość + dzielnica.

KIEDY UŻYWAĆ:
- User podaje lokalizację tekstem (np. "okolice Osowej", "Orłowo", "Gdańsk")
- ZAWSZE użyj tego przed propose_search_preferences!
- Automatycznie wykrywa czy to miejscowość czy dzielnica

ZWRACA:
- resolved: true/false
- gmina: np. "Gdańsk"
- miejscowosc: np. "Gdańsk" (dzielnica należy do miejscowości!)
- dzielnica: np. "Osowa" lub null
- parcel_count: ile działek w tej lokalizacji

PRZYKŁADY:
- "Osowa" → {gmina: "Gdańsk", miejscowosc: "Gdańsk", dzielnica: "Osowa"}
- "Orłowo" → {gmina: "Gdynia", miejscowosc: "Gdynia", dzielnica: "Orłowo"}
- "Gdańsk" → {gmina: "Gdańsk", miejscowosc: "Gdańsk", dzielnica: null}
- "Kartuzy" → {resolved: false, error: "nie w obsługiwanym obszarze"}

WAŻNE: Dzielnica jest wykrywana automatycznie z bazy - nie trzeba znać miasta!
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "location_text": {
                    "type": "string",
                    "description": "Tekst lokalizacji od użytkownika (np. 'okolice Osowej', 'Orłowo', 'w Gdańsku')"
                }
            },
            "required": ["location_text"]
        }
    },
    {
        "name": "validate_location_combination",
        "description": """
Sprawdź czy kombinacja miejscowość + dzielnica jest poprawna.

HIERARCHIA:
- Dzielnica należy do MIEJSCOWOŚCI, nie do gminy!
- Osowa należy do Gdańska
- Orłowo należy do Gdyni
- Niepoprawne: miejscowość="Gdańsk", dzielnica="Orłowo"

KIEDY UŻYWAĆ:
- User podał miasto i dzielnicę osobno
- Weryfikacja przed wyszukiwaniem
- Naprawa błędnych kombinacji

Zwraca:
- valid: true/false
- error: jeśli niepoprawne, z wyjaśnieniem
- suggestion: poprawna kombinacja

PRZYKŁAD:
validate_location_combination(miejscowosc="Gdańsk", dzielnica="Orłowo")
→ {valid: false, error: "Orłowo należy do Gdyni, nie Gdańska",
   suggestion: {miejscowosc: "Gdynia", dzielnica: "Orłowo"}}
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "miejscowosc": {
                    "type": "string",
                    "description": "Miejscowość do walidacji"
                },
                "dzielnica": {
                    "type": "string",
                    "description": "Dzielnica do walidacji"
                },
                "gmina": {
                    "type": "string",
                    "description": "Gmina (opcjonalna, dla dodatkowej walidacji)"
                }
            },
            "required": ["dzielnica"]
        }
    },

    # =========================================================================
    # SEMANTIC ENTITY RESOLUTION (2026-01-25)
    # Uses 384-dim embeddings for fuzzy matching
    # =========================================================================
    {
        "name": "resolve_entity",
        "description": """
Rozwiąż tekst użytkownika na encję w grafie używając semantycznego dopasowania (embeddingi).

TYPY ENCJI:
- location: "Matemblewo" → dzielnica Matarnia w Gdańsku (lokalizacje nieistniejące w katastrze)
- quietness: "spokojna okolica" → kategorie ciszy ["bardzo_cicha", "cicha"]
- nature: "blisko lasu" → kategorie natury ["bardzo_zielona", "zielona"]
- accessibility: "dobry dojazd" → kategorie dostępności
- density: "rzadka zabudowa" → kategorie gęstości
- water: "nad morzem" → typ wody "morze"
- poi: "szkoła" → typy POI ["school", "kindergarten"]

KIEDY UŻYWAĆ:
- Gdy użytkownik używa niestandardowych nazw lub opisów
- Gdy "Matemblewo" lub "VII Dwór" nie są rozpoznane przez resolve_location
- Gdy chcesz zrozumieć intencję użytkownika (np. "spokojna" = kategoria ciszy)

PRZYKŁADY:
1. resolve_entity(entity_type="location", user_text="Matemblewo")
   → {maps_to_district: "Matarnia", maps_to_gmina: "Gdańsk", confidence: "HIGH"}

2. resolve_entity(entity_type="quietness", user_text="spokojna okolica")
   → {values: ["bardzo_cicha", "cicha"]}

3. resolve_entity(entity_type="water", user_text="nad morzem")
   → {water_type: "morze", premium_factor: 2.0}
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["location", "quietness", "nature", "accessibility", "density", "water", "poi"],
                    "description": "Typ encji do rozwiązania"
                },
                "user_text": {
                    "type": "string",
                    "description": "Tekst użytkownika do rozwiązania (np. 'Matemblewo', 'spokojna okolica', 'nad morzem')"
                }
            },
            "required": ["entity_type", "user_text"]
        }
    },

    # =========================================================================
    # NEO4J V2 GRAPH TOOLS (2026-01-25)
    # Multi-hop traversals, adjacency, graph embeddings
    # =========================================================================
    {
        "name": "find_adjacent_parcels",
        "description": """
Znajdź działki sąsiadujące z wybraną działką.
Używa relacji ADJACENT_TO z informacją o długości wspólnej granicy.

KIEDY UŻYWAĆ:
- User pyta "jakie działki sąsiadują z X?"
- User chce kupić działkę obok już posiadanej
- User pyta o potencjał scalenia działek
- User interesuje się sąsiedztwem konkretnej działki

ZWRACA:
- Lista sąsiadów z długością wspólnej granicy (shared_border_m)
- Podstawowe info o każdym sąsiedzie (area, quietness, dzielnica)

PRZYKŁAD:
find_adjacent_parcels(parcel_id="220601_1.0001.123/4", limit=10)
→ [{id: "220601_1.0001.123/5", shared_border_m: 45.2, area_m2: 1100}, ...]
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
                    "description": "Max liczba sąsiadów (domyślnie 10)"
                }
            },
            "required": ["parcel_id"]
        }
    },
    {
        "name": "search_near_specific_poi",
        "description": """
Znajdź działki blisko KONKRETNEGO POI (szkoły, sklepu, przystanku).
Używa relacji NEAR_* z dokładną odległością w metrach.

KIEDY UŻYWAĆ:
- User pyta "działki blisko szkoły SP nr 45"
- User chce być blisko konkretnego obiektu (np. konkretny przystanek)
- User wymienia konkretną nazwę POI

TYPY POI:
- school: szkoły (226k relacji, threshold 2000m)
- shop: sklepy (747k relacji, threshold 1500m)
- bus_stop: przystanki (248k relacji, threshold 1000m)
- forest: lasy (168k relacji, threshold 500m)
- water: wody (106k relacji, threshold 500m)

PRZYKŁAD:
search_near_specific_poi(poi_type="school", poi_name="SP nr 45", max_distance_m=500)
→ [{id: "...", dzielnica: "Osowa", poi_name: "SP nr 45", distance_m: 320}, ...]
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "poi_type": {
                    "type": "string",
                    "enum": ["school", "shop", "bus_stop", "forest", "water"],
                    "description": "Typ POI"
                },
                "poi_name": {
                    "type": "string",
                    "description": "Nazwa POI (np. 'SP nr 45', 'Biedronka', 'Osowa PKM')"
                },
                "max_distance_m": {
                    "type": "integer",
                    "description": "Max odległość w metrach (domyślnie 1000)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max wyników (domyślnie 20)"
                }
            },
            "required": ["poi_type"]
        }
    },
    {
        "name": "find_similar_by_graph",
        "description": """
Znajdź działki STRUKTURALNIE podobne używając graph embeddings (256-dim FastRP).
Różni się od similarity semantycznego - tu liczy się struktura grafu (relacje, sąsiedztwo).

KIEDY UŻYWAĆ:
- User wskazał działkę i chce "podobne pod względem lokalizacji/okolicy"
- User szuka działek o podobnym profilu sąsiedztwa
- User chce znaleźć działki w podobnej "konfiguracji" (np. podobna odległość do POI)

RÓŻNICA OD find_similar_parcels:
- find_similar_parcels: similarity po tekście (opis, cechy)
- find_similar_by_graph: similarity po strukturze grafu (relacje, kontekst)

PRZYKŁAD:
User wskazał działkę na Wyspie Sobieszewskiej.
find_similar_by_graph(parcel_id="220611_2.0001.1234")
→ Znajdzie inne działki na Wyspie Sobieszewskiej o podobnej strukturze relacji
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
                    "description": "Liczba podobnych (domyślnie 10)"
                }
            },
            "required": ["parcel_id"]
        }
    },
]


def get_tools_by_names(names: list[str]) -> list[dict]:
    """Get tool definitions by their names."""
    return [tool for tool in AGENT_TOOLS if tool["name"] in names]


def get_all_tool_names() -> list[str]:
    """Get all available tool names."""
    return [tool["name"] for tool in AGENT_TOOLS]
