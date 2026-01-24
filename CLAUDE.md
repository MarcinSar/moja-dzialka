# CLAUDE.md - Projekt moja-dzialka

## Status: ARCHITEKTURA SOFTWARE 3.0 ZAIMPLEMENTOWANA (2026-01-24)

Agent z 7-warstwowym modelem pamięci, skills registry i state machine routing.
Pełna wiedza o 155k działkach. API v1 (legacy) + API v2 (nowa architektura).
Szczegółowy plan: `docs/PLAN_V2.md`, `docs/PLAN_V3_CONSOLIDATED.md`

---

## Cel projektu

**moja-dzialka** - inteligentny agent do wyszukiwania działek budowlanych w Trójmieście (Gdańsk, Gdynia, Sopot).

### Problem
- Rozproszenie danych (kataster, POG, BDOT10k)
- Brak narzędzi do wyszukiwania po kryteriach jakościowych ("cicha okolica", "blisko lasu")
- Skomplikowane przepisy planistyczne

### Rozwiązanie
Web app z konwersacyjnym agentem AI który:
1. **Zbiera wymagania** - naturalny dialog o preferencjach
2. **Wyszukuje** - hybrydowe wyszukiwanie (graf + wektor + przestrzenne)
3. **Prezentuje** - zorganizowana prezentacja działek (opis, mapa, opcjonalnie 3D na życzenie)
4. **Zbiera feedback** - iteracyjne doprecyzowanie
5. **Generuje leady** - zachęca do zakupu pakietu lub pozostawienia kontaktu

### Model biznesowy
- **FREE:** 3 działki w trybie prezentacji
- **Pakiety:** 10 działek = 20 PLN, 50 działek = 40 PLN (do ustalenia)
- **Lead generation:** zbieranie danych kontaktowych zainteresowanych zakupem

---

## Dane

### Dane gotowe do importu (488 MB)

Czyste, przetworzone dane w `data/ready-for-import/`:

| Katalog | Rozmiar | Zawartość |
|---------|---------|-----------|
| `postgis/` | 294 MB | 11 plików GPKG (działki, POG, POI, BDOT10k) |
| `neo4j/` | 162 MB | 3 pliki GPKG (działki, POG, POI) |
| `milvus/` | 33 MB | CSV do embeddingów |

### Przetworzone dane źródłowe

| Plik | Rekordów | Opis |
|------|----------|------|
| `parcels_enriched.gpkg` | 154,959 | Działki z 59 cechami |
| `pog_trojmiasto.gpkg` | 7,523 | Strefy planistyczne |
| `poi_trojmiasto.gpkg` | 15,421 | Punkty zainteresowania |

### Archiwum surowych danych (4.3 GB)

Oryginalne dane w `archive/raw-data/`:

| Typ | Lokalizacja | Dokumentacja |
|-----|-------------|--------------|
| **POG** (GML) | `archive/raw-data/pog/` | `docs/DATA_POG.md` |
| **BDOT10k** (72 warstwy) | `archive/raw-data/bdot10k/` | `docs/DATA_BDOT10K.md` |
| **Działki** (całe Pomorskie) | `archive/raw-data/dzialki/` | `docs/DATA_PARCELS.md` |
| **Raporty cenowe** | `archive/raw-data/dane-grunty-analityka/` | `docs/RAPORT_CENY_*.md` |

### POG (Plany Ogólne Gmin) ✅ SPARSOWANE
- **Gdańsk:** 3,710 stref planistycznych
- **Gdynia:** 3,195 stref planistycznych
- **Sopot:** 618 stref planistycznych
- **RAZEM:** 7,523 stref w `egib/data/processed/pog_trojmiasto.gpkg`
- Format źródłowy: GML 3.2, EPSG:2177
- Skrypt: `egib/scripts/pipeline/01_parse_pog.py`
- Parametry: symbol, profile funkcji, max wysokość, max % zabudowy, min % bio

### BDOT10k ✅ PRZETWORZONE
Wyekstrahowane warstwy dla Trójmiasta w `egib/data/bdot10k_trojmiasto/`:
- **budynki.gpkg:** 82,368 budynków (mieszkalne 63%, gospodarcze 15%, inne 22%)
- **lasy.gpkg:** tereny leśne
- **wody.gpkg:** zbiorniki i cieki wodne
- **drogi_glowne.gpkg:** drogi główne (do obliczania quietness)
- **drogi_wszystkie.gpkg:** pełna sieć drogowa
- **szkoly.gpkg:** placówki edukacyjne
- **przystanki.gpkg:** transport publiczny
- **przemysl.gpkg:** tereny przemysłowe

Atrybuty budynków (kompletność 97-100%):
- `FUNKCJAOGOLNABUDYNKU` - 10 kategorii (mieszkalne, gospodarcze, przemysłowe, ...)
- `PRZEWAZAJACAFUNKCJABUDYNKU` - typ szczegółowy (jednorodzinny, wielorodzinny, garaż, ...)
- `LICZBAKONDYGNACJI` - liczba pięter (1-39, mediana 2)
- `KATEGORIAISTNIENIA` - status (eksploatowany 99%, w budowie 0.9%)

### Działki ✅ WZBOGACONE (59 kolumn)
- **Gdańsk:** 92,781 działek
- **Gdynia:** 53,907 działek
- **Sopot:** 8,271 działek
- **RAZEM:** 154,959 działek w `egib/data/processed/parcels_enriched.gpkg`
- Format: GeoPackage, EPSG:2180

**Cechy podstawowe:** id_dzialki, gmina, dzielnica, grupa_rej, typ_wlasnosci, area_m2

**Cechy POG:** pog_symbol, pog_profil_podstawowy, pog_max_wysokosc, pog_max_zabudowa_pct, pog_min_bio_pct, is_residential_zone

**Cechy zabudowy (z BDOT10k):**
- `is_built` - czy zabudowana (61,107 = 39.4%)
- `building_count` - liczba budynków (1: 50k, 2-5: 11k, >5: 665)
- `building_area_m2` - suma powierzchni zabudowy
- `building_coverage_pct` - % pokrycia (mediana 27%)
- `building_main_function` - dominująca funkcja (mieszkalne 78%, gospodarcze 8%)
- `building_type` - typ szczegółowy (jednorodzinny, wielorodzinny, ...)
- `building_max_floors` - max kondygnacji
- `has_residential` / `has_industrial` - flagi
- `under_construction` - budynki w budowie (416 na 268 działkach)

**Odległości:** dist_to_school, dist_to_bus_stop, dist_to_forest, dist_to_water, dist_to_shop, dist_to_main_road

**Wskaźniki kompozytowe:** quietness_score, nature_score, accessibility_score

### Ceny gruntów ✅ RAPORT 2025
Zewnętrzne dane o cenach działek w Trójmieście: `docs/RAPORT_CENY_GRUNTOW_TROJMIASTO_2025.md`

**Kluczowe dane:**
- **Gdańsk:** 794-1021 zł/m² (transakcyjne vs ofertowe)
- **Gdynia:** 1323-1430 zł/m² (średnia), Orłowo do 2031 zł/m²
- **Sopot:** 2301-3310 zł/m² (najdroższy rynek)
- **Okolice:** Chwaszczyno 471 zł/m², Pruszcz Gd. 301 zł/m², Żukowo 172 zł/m²

**Segmentacja cenowa:**
| Segment | Zakres cen/m² | Lokalizacje |
|---------|---------------|-------------|
| ULTRA-PREMIUM | >3000 zł | Sopot Dolny, Kamienna Góra, Orłowo |
| PREMIUM | 1500-3000 zł | Jelitkowo, Śródmieścia |
| WYSOKI | 800-1500 zł | Oliwa, Wrzeszcz, Redłowo |
| ŚREDNI | 500-800 zł | Kokoszki, Osowa, Jasień |
| BUDŻETOWY | 300-500 zł | Łostowice, Chełm, Pruszcz Gd. |
| EKONOMICZNY | <300 zł | Żukowo, Kolbudy, Reda |

**Prognoza 2026-2027:** wzrost 3-7% rocznie (reforma planistyczna, deficyt gruntów)

---

## Agent-Doradca ✅ ZAIMPLEMENTOWANY

Agent moja-dzialka to **wyspecjalizowany doradca nieruchomości**, który:
- Rozmawia naturalnie, jak kompetentny znajomy z branży
- Zna dogłębnie 155k działek i 59 cech każdej z nich
- Wie kiedy użyć której bazy danych i dlaczego
- Doradza, rekomenduje, wyjaśnia trade-offy
- Dostosowuje formę do użytkownika

### Kluczowe komponenty

| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| SYSTEM_PROMPT | `backend/app/agent/orchestrator.py` | Pełna wiedza agenta (59 cech, ceny, strategia) |
| Narzędzia agenta | `backend/app/agent/tools.py` | 26 narzędzi + get_district_prices, estimate_parcel_value |
| Diversity service | `backend/app/services/diversity.py` | Wybór 3 różnorodnych propozycji |
| Ceny dzielnic | `egib/scripts/pipeline/07a_district_prices.py` | Dane cenowe z raportu |

### Wiedza agenta

**59 cech działek w 8 kategoriach:**
1. Lokalizacja (7 cech) - gmina, dzielnica, współrzędne
2. Własność (3 cechy) - typ, grupa rejestrowa
3. Powierzchnia (5 cech) - area_m2, size_category, shape_index
4. Zabudowa (11 cech) - is_built, building_count, building_type
5. Planowanie POG (11 cech) - symbol, profil, parametry zabudowy
6. Odległości (13 cech) - do szkoły, lasu, wody, przystanku
7. Wskaźniki (3 cechy) - quietness, nature, accessibility (0-100)
8. Kontekst okolicy (3 cechy) - pct_forest_500m, count_buildings_500m

**Kategorie binned (do Neo4j):**
- `kategoria_ciszy`: bardzo_cicha, cicha, umiarkowana, glosna
- `kategoria_natury`: bardzo_zielona, zielona, umiarkowana, zurbanizowana
- `kategoria_dostepu`: doskonala, dobra, umiarkowana, ograniczona
- `gestosc_zabudowy`: gesta, umiarkowana, rzadka, bardzo_rzadka

**Ceny dzielnic:**
- 50+ dzielnic z cenami min/max/segment
- Segmenty: ULTRA_PREMIUM, PREMIUM, HIGH, MEDIUM, BUDGET, ECONOMY
- Funkcje: get_district_prices(), estimate_parcel_value()

### Styl rozmowy

Agent:
- NIE zadaje listy pytań (jak ankieter)
- PROAKTYWNIE dzieli się wiedzą o cenach i dzielnicach
- WYJAŚNIA trade-offy między opcjami
- PREZENTUJE 3 RÓŻNE propozycje (lokalizacja lub profil)
- REAGUJE na kontekst (np. "mam dzieci" → szkoły)

---

## Architektura Software 3.0 ✅ ZAIMPLEMENTOWANA (2026-01-24)

Refaktoryzacja agenta wg. wzorców Software 3.0 z `/home/marcin/ai-edu/software3.0/`.

### 7-Warstwowy Model Pamięci

| Warstwa | Plik | Opis |
|---------|------|------|
| **Core (Constitutional)** | `memory/schemas/core.py` | DNA agenta - immutable identity, expertise, price knowledge |
| **Working** | `memory/schemas/working.py` | Stan sesji, sliding window 20 wiadomości, FunnelPhase |
| **Semantic** | `memory/schemas/semantic.py` | Profil kupującego, preferencje, budżet (long-term) |
| **Episodic** | `memory/schemas/episodic.py` | Skompresowana historia sesji, patterns |
| **Workflow** | `memory/schemas/workflow.py` | State machine lejka sprzedażowego |
| **Preferences** | `memory/schemas/preferences.py` | Styl doradztwa dostosowany do usera |
| **Procedural** | `skills/` | Registry umiejętności agenta |

### Skills Registry

| Skill | Faza | Opis |
|-------|------|------|
| `discovery` | DISCOVERY | Zbieranie wymagań przez naturalną rozmowę |
| `search` | SEARCH | Propose → approve → execute search flow |
| `evaluation` | EVALUATION | Porównanie działek, trade-offy |
| `market_analysis` | * | Ceny dzielnic, wyceny działek |
| `lead_capture` | LEAD_CAPTURE | Zbieranie kontaktu, pakiety |

### Nowe Komponenty

| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| Memory schemas | `backend/app/memory/schemas/` | Pydantic modele 7 warstw |
| MemoryManager | `backend/app/memory/logic/manager.py` | Zarządzanie stanem, ekstrakcja info |
| SessionCompressor | `backend/app/memory/logic/compressor.py` | ETL sesji → episodic |
| Jinja2 templates | `backend/app/memory/templates/` | Komponowalne prompty |
| Skills | `backend/app/skills/` | Deklaratywne umiejętności |
| AgentCoordinator | `backend/app/engine/agent_coordinator.py` | State machine routing |
| PropertyAdvisorAgent | `backend/app/engine/property_advisor_agent.py` | Skill executor |
| Persistence | `backend/app/persistence/` | InMemory, Redis, Redis+Postgres |

### API Endpoints (v2)

| Endpoint | Opis |
|----------|------|
| `WS /api/v2/conversation/ws` | WebSocket z nową architekturą |
| `POST /api/v2/conversation/chat` | REST chat (non-streaming) |
| `GET /api/v2/conversation/user/{id}/state` | Pełny stan użytkownika |
| `GET /api/v2/conversation/user/{id}/funnel` | Postęp w lejku |

### State Machine (FunnelPhase)

```
DISCOVERY → SEARCH → EVALUATION → NEGOTIATION → LEAD_CAPTURE
     ↑         ↓
  RETENTION ←──┘  (powracający użytkownicy)
```

### Konfiguracja

| Zmienna | Default | Opis |
|---------|---------|------|
| `PERSISTENCE_BACKEND` | `memory` | `memory`, `redis`, `redis_postgres` |
| `REDIS_URL` | `redis://localhost:6379` | Redis dla hot cache |

---

## Architektura baz danych

### PostGIS
- Szybkie zapytania przestrzenne
- Wizualizacja, GeoJSON
- Tabele: `parcels`, `pog_zones`, `poi`

### Neo4j
- Graf wiedzy z relacjami
- 10 typów węzłów, 12 typów relacji
- Wyszukiwanie przez traversal

### Milvus
- Embeddingi 32-dim
- Wyszukiwanie podobieństwa

Szczegóły: `docs/PLAN_V2.md` sekcja 3.

---

## Pipeline danych

### Wykonane ✅
| Krok | Skrypt | Output |
|------|--------|--------|
| 1 | `01_parse_pog.py` | 7,523 stref POG → GeoPackage |
| 2 | `02_merge_parcels.py` | 154,959 działek + własność |
| 3 | `03_add_districts.py` | Przypisanie dzielnic |
| 3b | `03b_clip_bdot10k.py` | 8 warstw BDOT10k |
| 3e | `03e_overpass_download.py` | 17k obiektów OSM |
| 4 | `04_merge_poi.py` | 15,421 POI |
| 5 | `05_feature_engineering.py` | POG join + odległości + wskaźniki + kategorie binned |
| 6 | `06_add_buildings.py` | Cechy zabudowy z BDOT10k |
| 7a | `07a_district_prices.py` | Ceny dzielnic z raportu |

Lokalizacja skryptów: `egib/scripts/pipeline/`

### Do wykonania
| Krok | Skrypt | Output |
|------|--------|--------|
| 7 | `07_import_postgis.py` | Import do PostgreSQL |
| 8 | `08_import_neo4j.py` | Import do Neo4j |
| 9 | `09_generate_embeddings.py` | Embeddingi 32-dim |
| 10 | `10_import_milvus.py` | Import do Milvus |

---

## Struktura projektu

```
moja-dzialka/
├── backend/                    # FastAPI backend (52 pliki Python)
│   └── app/
│       ├── agent/              # Legacy agent (v1)
│       ├── api/                # REST + WebSocket endpoints
│       ├── engine/             # AgentCoordinator, PropertyAdvisorAgent
│       ├── memory/             # 7-warstwowy model pamięci
│       ├── persistence/        # Redis + PostgreSQL backends
│       ├── services/           # Database, diversity service
│       └── skills/             # Skills registry
├── frontend/                   # React + Vite + Tailwind
├── data/
│   └── ready-for-import/       # ✅ Dane gotowe do importu (488 MB)
│       ├── postgis/            # 11 plików GPKG
│       ├── neo4j/              # 3 pliki GPKG
│       └── milvus/             # CSV do embeddingów
├── egib/
│   ├── data/processed/         # Przetworzone dane źródłowe
│   ├── data/bdot10k_trojmiasto/# Wycięte warstwy BDOT10k
│   └── scripts/pipeline/       # Aktualny pipeline (12 skryptów)
├── docs/                       # Aktualna dokumentacja (14 plików)
├── archive/                    # Archiwum (4.4 GB)
│   ├── raw-data/               # Surowe dane źródłowe
│   ├── docs-legacy/            # Przestarzała dokumentacja
│   ├── scripts-legacy/         # Stare skrypty pipeline
│   └── cache/                  # Pliki tymczasowe (można usunąć)
└── CLAUDE.md                   # Ten plik
```

---

## Kluczowe decyzje

| Decyzja | Wybór |
|---------|-------|
| Region | Trójmiasto (Gdańsk, Gdynia, Sopot) |
| 3D terrain | Na życzenie użytkownika przez rozmowę |
| Lead capture | Zachęta do zapłaty LUB pozostawienia kontaktu |
| Płatność | Model do zbadania (Stripe? Przelewy24? BLIK?) |

---

## Knowledge Resources

### Lokalne kursy
- `/home/marcin/ai-edu/` - kursy AI (grafy, RAG, agenci)
- `grafy/kurs1-knowledge-graphs-for-rag/` - Graph RAG
- `grafy/kurs2-agentic-kg-construction/` - Agentic KG

### Kluczowe materiały
- `ai-edu/grafy/research-agentic-rag-2025.md` - Agentic RAG patterns
- `ai-edu/grafy/deep-dive-graph-rag-vs-vector-rag.md` - RAG comparison
- `ai-edu/deepagents/MAPA_DOKUMENTACJI_AGENTOW.md` - Framework comparison

### DeepAgents - Architektura systemów agentowych
Lokalizacja: `/home/marcin/deepagents/`

| Dokument | Opis | Kluczowe koncepcje |
|----------|------|-------------------|
| `mcp/BAZA_WIEDZY_MCP.md` | MCP Knowledge Base (2100 lines) | MCP jako "USB-C dla AI", Tools/Resources/Prompts, OAuth 2.1, JSON-RPC 2.0, Code Execution (98.7% token reduction) |
| `context-engineering/weaviate-context-engineering-documentation.md` | Context Engineering (1447 lines) | Context Rot (n² problem), Chunking strategies, Memory types (Short/Long/Working), "Smallest set of high-signal tokens" |
| `deepagents-anthropic/dokumentacja-deep-agents-anthropic.md` | Anthropic Deep Agents (965 lines) | Agent Loop (Gather→Act→Verify), Long-horizon techniques (Compaction, NOTES.md, Sub-agents), Tool capabilities |

**Kluczowe wzorce do zastosowania:**
- **MCP Tools**: Narzędzia agenta jako standardowe MCP tools
- **Context Engineering**: Zarządzanie kontekstem przy dużej skali danych (155k działek)
- **Long-horizon**: Sub-agent architecture dla złożonych wyszukiwań multi-region

---

## Następne kroki

1. [x] ~~Pipeline danych - przetwarzanie~~ (154,959 działek z 59 cechami)
2. [x] ~~Agent-Doradca v1~~ (SYSTEM_PROMPT, narzędzia, diversity service)
3. [x] ~~Architektura Software 3.0~~ (7-warstw pamięci, skills, state machine)
4. [x] ~~Organizacja projektu~~ (dane w `data/ready-for-import/`, archiwum w `archive/`)
5. [ ] Import do baz danych (`data/ready-for-import/` → PostGIS, Neo4j, Milvus)
6. [ ] Testy E2E nowej architektury (API v2)
7. [ ] Migracja frontendu na API v2
8. [ ] Integracja płatności (Stripe/Przelewy24)
9. [ ] Lead capture UI + analytics
