# CLAUDE.md - Projekt moja-dzialka

## Status: NEO4J KNOWLEDGE GRAPH REDESIGN ZAIMPLEMENTOWANY (2026-01-24)

Agent z 7-warstwowym modelem pamięci, skills registry i state machine routing.
**NOWE:** Pełna klasyfikacja wód (6 typów), 68 kolumn działek, narzędzia wodne.
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
| `parcels_enriched.gpkg` | 154,959 | Działki z **68 cechami** (było 59) |
| `pog_trojmiasto.gpkg` | 7,523 | Strefy planistyczne |
| `poi_trojmiasto.gpkg` | 15,421 | Punkty zainteresowania |
| `water_classified.gpkg` | 2,307 | **NOWE:** Sklasyfikowane obiekty wodne |

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

### Działki ✅ WZBOGACONE (68 kolumn)
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

**Odległości do wód (NOWE):**
- `dist_to_sea` - do morza (7,561 działek ≤500m)
- `dist_to_river` - do rzeki (8,502 działek ≤200m)
- `dist_to_lake` - do jeziora (5,975 działek ≤300m)
- `dist_to_canal` - do kanału
- `dist_to_pond` - do stawu
- `nearest_water_type` - najbliższy typ wody (morze/rzeka/jezioro/kanal/staw)

**Wskaźniki kompozytowe:** quietness_score, nature_score, accessibility_score

**Kategorie binned (NOWE):**
- `kategoria_ciszy` - bardzo_cicha (39), cicha (2,661), umiarkowana (10,576), glosna (141,683)
- `kategoria_natury` - bardzo_zielona (76,609), zielona (78,324), umiarkowana (21), zurbanizowana (5)
- `kategoria_dostepu` - doskonala (136,796), dobra (11,686), umiarkowana (5,087), ograniczona (1,390)
- `gestosc_zabudowy` - gesta (147,502), umiarkowana (4,201), rzadka (1,993), bardzo_rzadka (1,263)

### Wody ✅ SKLASYFIKOWANE (2026-01-24)

Klasyfikacja 2,307 obiektów wodnych z BDOT10k do 6 typów:

| Typ | Liczba | Premium | Przykłady |
|-----|--------|---------|-----------|
| morze | 20 | +50-100% | Morze Bałtyckie, Zatoka Gdańska |
| jezioro | 99 | +20-40% | Osowskie, Jasień, Wysockie, Straszyńskie |
| rzeka | 96 | +10-20% | Radunia, Motława, Strzyża, Wisła |
| kanal | 49 | +5-10% | Kanał Raduni, Czarna Łacha |
| staw | 2,043 | +5% | Małe zbiorniki, oczka wodne |

**Kluczowe wody Trójmiasta:**
- **Morze:** Brzeźno, Jelitkowo, Sopot, Orłowo (linia brzegowa)
- **Jeziora:** Osowskie (Osowa), Jasień, Wysockie (Gdynia), Straszyńskie
- **Rzeki:** Radunia (główna), Motława (historyczna), Strzyża (zachodnie dzielnice)

**Plik źródłowy:** `egib/data/processed/water_classified.gpkg`
**Skrypt:** `egib/scripts/pipeline/11_classify_water.py`

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
| SYSTEM_PROMPT | `backend/app/agent/orchestrator.py` | Pełna wiedza agenta (68 cech, ceny, wody, strategia) |
| Narzędzia agenta | `backend/app/agent/tools.py` | **29 narzędzi** (było 26) + narzędzia wodne |
| Graph service | `backend/app/services/graph_service.py` | Neo4j queries + **nowe metody wodne** |
| Diversity service | `backend/app/services/diversity.py` | Wybór 3 różnorodnych propozycji |
| Ceny dzielnic | `egib/scripts/pipeline/07a_district_prices.py` | Dane cenowe z raportu |

### Nowe narzędzia wodne (2026-01-24)

| Narzędzie | Opis |
|-----------|------|
| `search_by_water_type` | Wyszukaj działki blisko morza/jeziora/rzeki |
| `get_water_info` | Odległości do wszystkich typów wód dla działki |
| `get_parcel_full_context` | Pełny kontekst działki (woda + ceny + POG) |

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

### Neo4j ✅ NOWY SCHEMAT (2026-01-24)

**Węzły (15 typów):**
| Typ | Liczba | Opis |
|-----|--------|------|
| Parcel | 154,959 | Działki z 68 właściwościami |
| District | 109 | Dzielnice |
| City | 3 | Gdańsk, Gdynia, Sopot |
| School | 300 | Szkoły |
| BusStop | 2,533 | Przystanki |
| Forest | 3,410 | Tereny leśne |
| Water | 2,307 | Obiekty wodne (sklasyfikowane) |
| Shop | 8,332 | Sklepy |
| Road | 1,918 | Drogi główne |
| QuietnessCategory | 4 | bardzo_cicha, cicha, umiarkowana, glosna |
| NatureCategory | 4 | bardzo_zielona, zielona, umiarkowana, zurbanizowana |
| AccessCategory | 4 | doskonala, dobra, umiarkowana, ograniczona |
| DensityCategory | 4 | gesta, umiarkowana, rzadka, bardzo_rzadka |
| WaterType | 6 | morze, zatoka, rzeka, jezioro, kanal, staw |
| PriceSegment | 6 | ULTRA_PREMIUM → ECONOMY |

**Relacje (15 typów):**
- Hierarchiczne: `LOCATED_IN`, `BELONGS_TO`, `HAS_POG`
- Kategorialne: `HAS_QUIETNESS`, `HAS_NATURE`, `HAS_ACCESS`, `HAS_DENSITY`
- Wodne: `NEAREST_WATER_TYPE`, `WATER_IS_TYPE`
- Cenowe: `IN_PRICE_SEGMENT`

### Milvus (opcjonalnie)
- Embeddingi 32-dim
- Wyszukiwanie podobieństwa
- Można zastąpić Neo4j Vector Index

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

### Neo4j Knowledge Graph Pipeline ✅ NOWE (2026-01-24)
| Krok | Skrypt | Output |
|------|--------|--------|
| 11 | `11_classify_water.py` | 2,307 wód sklasyfikowanych → 6 typów |
| 12 | `12_calculate_water_distances.py` | dist_to_sea/river/lake/canal/pond |
| 13 | `13_export_full_csv.py` | `parcels_full.csv` (103 MB, 68 kolumn) |
| 14 | `14_export_poi_csv.py` | 13 plików CSV dla Neo4j (104 MB) |
| 15 | `15_create_neo4j_schema.py` | Indeksy, constraints, węzły kategorii |
| 16 | `16_import_neo4j_full.py` | Import wszystkich danych do Neo4j |
| 17 | `17_create_spatial_relations.py` | Relacje NEAR_*, segmenty cenowe |

Lokalizacja skryptów: `egib/scripts/pipeline/`

### Do wykonania
| Krok | Skrypt | Output |
|------|--------|--------|
| 7 | `07_import_postgis.py` | Import do PostgreSQL |
| 18 | `18_generate_embeddings.py` | Embeddingi 32-dim |

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
│   └── scripts/pipeline/       # Aktualny pipeline (19 skryptów)
├── scripts/
│   └── deploy/                 # Skrypty produkcyjne
│       ├── deploy.sh           # Deployment
│       ├── backup.sh           # Backup baz danych
│       ├── restore.sh          # Przywracanie z backupu
│       └── import-data.sh      # Import danych do baz
├── nginx/
│   └── moja-dzialka.conf       # Konfiguracja Nginx + SSL
├── docs/                       # Aktualna dokumentacja (15 plików)
├── docker-compose.yml          # Konfiguracja deweloperska
├── docker-compose.prod.yml     # Overrides produkcyjne
├── archive/                    # Archiwum (4.4 GB) - nie w git
└── CLAUDE.md                   # Ten plik
```

---

## Deployment produkcyjny ✅ ZAPLANOWANY (2026-01-24)

Pełna dokumentacja: `docs/DEPLOYMENT.md`

### Serwer docelowy

| Parametr | Wartość |
|----------|---------|
| Provider | Hetzner CX53 |
| CPU | 16 vCPU (AMD EPYC-Rome) |
| RAM | 32 GB |
| Storage | 305 GB NVMe SSD |
| OS | Ubuntu 24.04 LTS |
| IP | 77.42.86.222 |

### Architektura kontenerów

```
┌─────────────────────────────────────────────────────────────┐
│  Cloudflare (DNS + SSL) → moja-dzialka.pl                   │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Nginx (:80/:443) → reverse proxy                           │
├─────────────────────────────────────────────────────────────┤
│  Docker Network                                             │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ Backend │ │Frontend │ │ Celery │ │ Redis  │ │ Mongo  │   │
│  │ :8000   │ │ :3000   │ │ Worker │ │ :6379  │ │ :27017 │   │
│  └─────────┘ └─────────┘ └────────┘ └────────┘ └────────┘   │
│  ┌─────────┐ ┌─────────┐ ┌────────┐                         │
│  │PostGIS  │ │ Neo4j   │ │ Milvus │                         │
│  │ :5432   │ │ :7687   │ │ :19530 │                         │
│  └─────────┘ └─────────┘ └────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Alokacja RAM (32 GB)

| Usługa | RAM | Uzasadnienie |
|--------|-----|--------------|
| Neo4j | 8-10 GB | Graf 155k działek |
| PostgreSQL | 4-6 GB | Spatial queries |
| Milvus | 4-6 GB | Vector search |
| Backend | 2-4 GB | API + Claude calls |
| Redis | 1-2 GB | Session cache |
| MongoDB | 1-2 GB | Leads |
| System | 4-6 GB | OS + Nginx |

### Skrypty operacyjne

| Skrypt | Opis |
|--------|------|
| `scripts/deploy/deploy.sh` | Deployment (git pull + rebuild + restart) |
| `scripts/deploy/backup.sh` | Backup wszystkich baz (cron: 3:00 daily) |
| `scripts/deploy/restore.sh` | Przywracanie z backupu |
| `scripts/deploy/import-data.sh` | Początkowy import danych |

### Konfiguracja

| Plik | Opis |
|------|------|
| `docker-compose.prod.yml` | Limity RAM, gunicorn, restart policy |
| `nginx/moja-dzialka.conf` | Reverse proxy, SSL, rate limiting |
| `.env.example` | Template zmiennych środowiskowych |

---

## Kluczowe decyzje

| Decyzja | Wybór |
|---------|-------|
| Region | Trójmiasto (Gdańsk, Gdynia, Sopot) |
| Hosting | Hetzner CX53 (77.42.86.222) |
| SSL | Cloudflare Origin Certificate |
| 3D terrain | Na życzenie użytkownika przez rozmowę |
| Lead capture | Zachęta do zapłaty LUB pozostawienia kontaktu |
| Płatność | Stripe (do skonfigurowania) |
| Backup | Automatyczny, codzienny o 3:00 |

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
5. [x] ~~Architektura deployment~~ (docker-compose.prod.yml, nginx, skrypty backup/restore)
6. [x] ~~Neo4j Knowledge Graph Redesign~~ (klasyfikacja wód, 68 kolumn, nowe narzędzia)
7. [ ] **TERAZ:** Deploy na serwer + import danych (uruchom skrypty 15, 16, 17)
8. [ ] Testy E2E nowej architektury (API v2)
9. [ ] Migracja frontendu na API v2
10. [ ] Integracja płatności (Stripe)
11. [ ] Lead capture UI + analytics
12. [ ] Monitoring (Grafana + Prometheus)
