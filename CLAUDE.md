# CLAUDE.md - Projekt moja-dzialka

## Cel projektu

**moja-dzialka** to inteligentny system rekomendacji działek budowlanych w województwie pomorskim, łączący:
- Konwersacyjnego agenta AI z interaktywnym awatarem
- Embeddingi przestrzenne SRAI do wyszukiwania podobieństwa
- Bazę grafową Neo4j z relacjami przestrzennymi i administracyjnymi
- Model monetyzacji freemium (20 PLN za pełne wyniki)

### Problem do rozwiązania

Znalezienie odpowiedniej działki budowlanej jest trudne:
- Rozproszenie danych (kataster, MPZP, BDOT10k)
- Brak narzędzi do wyszukiwania po kryteriach jakościowych ("cicha okolica", "blisko lasu")
- Skomplikowane przepisy planistyczne (MPZP)

### Rozwiązanie

Interaktywny agent AI (z awatarem/postacią) który:
1. Prowadzi naturalną rozmowę o preferencjach użytkownika
2. Przeszukuje 1.3M działek z wykorzystaniem hybrydowego search (vector + graph)
3. Generuje interaktywne mapy z wynikami
4. Pokazuje 3 działki za darmo, za resztę prosi o 20 PLN

---

## Status projektu (2026-01-18)

### UKOŃCZONE: Pipeline danych

| Etap | Skrypt | Wynik |
|------|--------|-------|
| 1. Walidacja | `01_validate.py` | Wszystkie dane źródłowe poprawne |
| 2. BDOT10k | `02_clean_bdot10k.py` | 7 warstw skonsolidowanych |
| 3. MPZP | `02_clean_mpzp.py` | 14,473 stref planistycznych |
| 4. Działki | `02_clean_parcels.py` | 1,300,779 działek z land cover |
| 5. Features | `03_feature_engineering.py` | **36 cech obliczonych** |
| 6. Dev sample | `04_create_dev_sample.py` | 10,471 działek testowych |

### UKOŃCZONE: Backend Services

| Komponent | Plik | Funkcja |
|-----------|------|---------|
| Database Connections | `services/database.py` | PostGIS, Neo4j, Milvus, Redis managers |
| Spatial Service | `services/spatial_service.py` | PostGIS queries, GeoJSON generation |
| Vector Service | `services/vector_service.py` | Milvus similarity search |
| Graph Service | `services/graph_service.py` | Neo4j Cypher queries |
| Hybrid Search | `services/parcel_search.py` | RRF-based multi-source fusion |

### UKOŃCZONE: Agent z KG Course Patterns

| Pattern | Implementacja |
|---------|---------------|
| Human-in-the-Loop | `propose_*` → user confirms → `approve_*` |
| Guard Patterns | State validation before `execute_search` |
| Critic Pattern | `critique_search_results` → `refine_search` |
| Few-Shot Prompting | Examples in system prompt |

### UKOŃCZONE: API Endpoints

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/v1/conversation/ws` | WebSocket | Streaming agent chat |
| `/api/v1/conversation/chat` | POST | Non-streaming chat |
| `/api/v1/search/` | POST | Hybrid parcel search |
| `/api/v1/search/similar/{id}` | GET | Vector similarity search |
| `/api/v1/search/parcel/{id}` | GET | Full parcel details |
| `/api/v1/search/map` | POST | GeoJSON map data |
| `/api/v1/search/gminy` | GET | List of gminy |
| `/api/v1/search/mpzp-symbols` | GET | MPZP symbol definitions |

### PENDING: Import danych do baz

| Skrypt | Baza | Status |
|--------|------|--------|
| `05_import_postgis.py` | PostGIS | Gotowy (--sample) |
| `06_import_neo4j.py` | Neo4j | Gotowy (--sample) |
| `07_generate_srai.py` | Parquet | Gotowy (--sample) |
| `08_import_milvus.py` | Milvus | Gotowy (--sample) |

### PENDING: Frontend

- React + TypeScript + Tailwind
- Split-screen layout (Chat | Map | Activity)
- assistant-ui dla chat
- Leaflet dla map

---

## Architektura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                     │
│   React + Leaflet + Chat UI + Avatar                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket / REST
┌────────────────────────────▼────────────────────────────────────────┐
│                      AGENT LAYER (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │ ParcelAgent │  │ Tools       │  │ EventStream │                  │
│  │ (Claude API)│  │ (15 tools)  │  │ (WebSocket) │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
│                           │                                          │
│  Patterns: Human-in-the-Loop | Guard | Critic | Few-Shot            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                     SEARCH LAYER                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              HybridSearchService (RRF Fusion)                 │   │
│  │   spatial_results (40%) + vector_results (30%) + graph (30%) │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                       DATA LAYER                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   PostGIS    │  │    Neo4j     │  │   Milvus     │               │
│  │  (geometrie) │  │   (graf)     │  │  (wektory)   │               │
│  │  888k działek│  │  relacje     │  │  embeddings  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Agent Tools (15 narzędzi)

### Human-in-the-Loop: Preferencje

| Narzędzie | Opis |
|-----------|------|
| `propose_search_preferences` | Zaproponuj preferencje (perceived state) |
| `approve_search_preferences` | Zatwierdź po potwierdzeniu użytkownika |
| `modify_search_preferences` | Zmień pojedynczą preferencję |

### Wyszukiwanie (Guard Pattern)

| Narzędzie | Opis |
|-----------|------|
| `execute_search` | Wyszukaj działki (wymaga approved!) |
| `find_similar_parcels` | Znajdź podobne do wskazanej |

### Critic Pattern: Ulepszanie

| Narzędzie | Opis |
|-----------|------|
| `critique_search_results` | Zapisz feedback użytkownika |
| `refine_search` | Popraw wyniki na podstawie feedbacku |

### Informacje

| Narzędzie | Opis |
|-----------|------|
| `get_parcel_details` | Szczegóły działki |
| `get_gmina_info` | Informacje o gminie |
| `list_gminy` | Lista gmin |
| `count_matching_parcels` | Liczba działek |
| `get_mpzp_symbols` | Symbole MPZP |

### Mapa

| Narzędzie | Opis |
|-----------|------|
| `generate_map_data` | GeoJSON do wyświetlenia |

---

## Conversation Flow (Few-Shot Pattern)

```
1. User: "Szukam działki blisko Gdańska, ok 1000 m²"

2. Agent → propose_search_preferences({
     location_description: "okolice Gdańska",
     min_area_m2: 800, max_area_m2: 1200
   })
   Agent: "Czy te preferencje są poprawne?"

3. User: "Tak, ale chcę bliżej lasu"

4. Agent → modify_search_preferences({
     field: "nature_weight", new_value: 0.7
   })
   Agent: "Zatwierdzamy?"

5. User: "Tak, szukaj"

6. Agent → approve_search_preferences()
   Agent → execute_search({limit: 5})
   Agent: "Znalazłem 47 działek, oto 5 najlepszych..."

7. User: "Te są za blisko drogi"

8. Agent → critique_search_results({feedback: "za blisko drogi"})
   Agent → refine_search({adjustment: "zwiększ wagę ciszy"})
   Agent: "Szukam cichszych lokalizacji..."
```

---

## Pliki projektu

```
moja-dzialka/
├── backend/
│   └── app/
│       ├── main.py                    # FastAPI entry + lifespan
│       ├── config.py                  # Settings from env
│       ├── api/
│       │   ├── __init__.py
│       │   ├── conversation.py        # WebSocket + REST chat
│       │   └── search.py              # REST search endpoints
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py             # Pydantic models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── database.py            # Connection managers
│       │   ├── spatial_service.py     # PostGIS queries
│       │   ├── vector_service.py      # Milvus queries
│       │   ├── graph_service.py       # Neo4j queries
│       │   └── parcel_search.py       # Hybrid search (RRF)
│       └── agent/
│           ├── __init__.py
│           ├── tools.py               # 15 agent tools + state
│           └── orchestrator.py        # ParcelAgent + streaming
├── scripts/
│   ├── init-db.sql                    # PostGIS schema
│   └── pipeline/
│       ├── 01_validate.py
│       ├── 02_clean_*.py
│       ├── 03_feature_engineering.py
│       ├── 04_create_dev_sample.py
│       ├── 05_import_postgis.py       # --sample flag
│       ├── 06_import_neo4j.py         # --sample flag
│       ├── 07_generate_srai.py        # --sample flag
│       └── 08_import_milvus.py        # --sample flag
├── data/
│   ├── processed/v1.0.0/
│   │   ├── parcel_features.parquet    # 324 MB, 36 features
│   │   └── parcel_features.gpkg       # 722 MB, with geometry
│   └── dev/
│       ├── parcels_dev.gpkg           # ~10k parcels
│       ├── bdot10k_dev.gpkg
│       └── mpzp_dev.gpkg
├── docker-compose.yml
└── CLAUDE.md
```

---

## Obliczone cechy (36 kolumn)

### Odległości (KD-tree optimized)

| Cecha | Źródło | Średnia |
|-------|--------|---------|
| dist_to_school | 2,626 szkół | 1,845m |
| dist_to_shop | 12,449 sklepów | 965m |
| dist_to_hospital | 1,283 placówek | 2,995m |
| dist_to_bus_stop | 10,554 przystanków | 619m |
| dist_to_public_road | 830k dróg | 66m |
| dist_to_forest | 75k lasów | 215m |
| dist_to_water | 49k zbiorników | 303m |
| dist_to_industrial | 3,795 stref | 1,144m |

### Bufory (500m radius)

| Cecha | Średnia |
|-------|---------|
| pct_forest_500m | 18.99% |
| pct_water_500m | 3.02% |
| count_buildings_500m | 163.6 |

### Kompozytowe

| Cecha | Średnia | Opis |
|-------|---------|------|
| quietness_score | 90.5 | Wskaźnik ciszy (0-100) |
| nature_score | 56.8 | Bliskość natury (0-100) |
| accessibility_score | 74.5 | Dostępność komunikacyjna |
| has_public_road_access | 82.9% | Dostęp do drogi publicznej |

---

## Hybrid Search (RRF Fusion)

```python
# Reciprocal Rank Fusion combining 3 sources
SPATIAL_WEIGHT = 0.4   # PostGIS (distance, area filters)
VECTOR_WEIGHT = 0.3    # Milvus (SRAI similarity)
GRAPH_WEIGHT = 0.3     # Neo4j (MPZP, relationships)

# RRF Score = Σ(weight / (K + rank))
# K = 60 (standard constant)
```

---

## Uruchomienie

### 1. Bazy danych

```bash
docker-compose up -d postgres neo4j milvus redis
```

### 2. Import dev sample

```bash
cd scripts/pipeline
python 05_import_postgis.py --sample
python 06_import_neo4j.py --sample
python 07_generate_srai.py --sample
python 08_import_milvus.py --sample
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Test API

```bash
# Health check
curl http://localhost:8000/health

# WebSocket test (wscat)
wscat -c ws://localhost:8000/api/v1/conversation/ws
> {"type": "init"}
> {"type": "message", "content": "Szukam działki blisko Gdańska"}
```

---

## Serwer produkcyjny

| Parametr | Wartość |
|----------|---------|
| Provider | Hetzner Cloud |
| Plan | CX53 |
| vCPU | 16 |
| RAM | 32 GB |
| Storage | 320 GB NVMe |
| OS | Ubuntu 24.04 LTS |
| IP | 77.42.86.222 |

---

## Knowledge Resources

### Neo4j KG Courses (APPLIED)

Location: `/root/moja-dzialka/grafy/`

| Course | Key Patterns |
|--------|--------------|
| kurs1-knowledge-graphs-for-rag | Graph RAG, semantic layer |
| kurs2-agentic-kg-construction | **Human-in-the-Loop, Guard, Critic** |

### AI Education Base

Location: `/home/marcin/ai-edu/`

| Topic | Resource |
|-------|----------|
| MCP & Tools | `_synthesis/software3.0/modul3/` |
| Agent Architecture | `deepagents/MAPA_DOKUMENTACJI_AGENTOW.md` |
| Graph RAG | `grafy/05-graph-rag/` |

---

*Ostatnia aktualizacja: 2026-01-18 21:30 UTC*
