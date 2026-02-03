# CLAUDE.md - Projekt moja-dzialka

## Status: AGENT SYSTEM v3.0 ✅ UKOŃCZONY (2026-02-02)

**MAJOR UPDATE:** Pełna przebudowa systemu agentowego inspirowana wzorcami OpenClaw.

**Nowa architektura v3.0:**
- **Multi-Agent System** - 6 wyspecjalizowanych sub-agentów (Discovery, Search, Analyst, Narrator, Feedback, Lead)
- **Hybrid Memory** - 5-tier (Immediate/Redis/PostgreSQL/Files/Neo4j) + Memory Flush
- **SKILL.md Format** - deklaratywne definicje skills z YAML frontmatter i gates
- **Tool Schema V3** - reliability scores, cost indicators, composition hints
- **Premium Services** - Neighborhood Analysis, 3D Terrain (LiDAR skeleton)
- **Feedback Learning** - re-ranking based on favorites/rejections

**Poprzednie updaty:**
- **2026-01-25:** Neo4j v2 Pipeline - 171k węzłów, 5.94M relacji, dual embeddings
- **Skrypty pipeline:** `egib/scripts/pipeline/21-27_*.py`

---

## Agent System v3.0 Architecture ✅ NOWE (2026-02-02)

### Multi-Agent System

```
                              USER MESSAGE
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ROOT ORCHESTRATOR AGENT                               │
│                     Model: Sonnet 4 (configurable)                          │
│                                                                              │
│  - Parse intent, routing, synthesis                                         │
│  - Maintain conversation personality                                        │
│  - Tools: spawn_agent, await_agent, synthesize_response                     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│   DISCOVERY    │    │    SEARCH      │    │    ANALYST     │
│  Model: Haiku  │    │   Model: Haiku │    │  Model: Sonnet │
│   7 tools      │    │   12 tools     │    │   8 tools      │
└────────────────┘    └────────────────┘    └────────────────┘

┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│   NARRATOR     │    │   FEEDBACK     │    │     LEAD       │
│  Model: Sonnet │    │  Model: Haiku  │    │   Model: Haiku │
│   4 tools      │    │   6 tools      │    │   3 tools      │
└────────────────┘    └────────────────┘    └────────────────┘
```

**Kluczowe pliki:**
| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| SubAgentSpawner | `backend/app/engine/sub_agents.py` | Spawner + AgentRouter |
| PropertyAdvisorAgent | `backend/app/engine/property_advisor_agent.py` | Root Orchestrator |
| AgentCoordinator | `backend/app/engine/agent_coordinator.py` | Session management |

### Memory Architecture (5-Tier)

```
TIER 1: Immediate (in-memory)     │ Working state, current session
TIER 2: Hot (Redis, <10ms)        │ Active sessions, user profiles
TIER 3: Warm (PostgreSQL, <100ms) │ Full state, analytics, leads
TIER 4: Cold (Files, <500ms)      │ Session archives, patterns, logs
TIER 5: Knowledge (Neo4j+SQLite)  │ 155k parcels, embeddings
```

**Memory Flush Flow:**
```
Token count > 80% limit
        │
        ▼
Silent Haiku turn (extract facts)
        │
        ├─► Write to users/{id}/profile.md
        ├─► Append to memory/{date}.md
        └─► Update Redis cache
        │
        ▼
Continue or hard compact
```

**Kluczowe pliki:**
| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| MemoryFlushManager | `backend/app/memory/logic/flush.py` | LLM-powered extraction |
| WorkspaceManager | `backend/app/memory/workspace.py` | File-based storage (~/.parcela/) |
| 7-Layer Memory | `backend/app/memory/schemas/*.py` | Core, Working, Semantic, etc. |

### Skills v3 (SKILL.md Format)

Skills definiowane są w plikach markdown z YAML frontmatter:

```yaml
---
name: discovery
description: Zbieranie preferencji użytkownika
version: "1.0"

gates:
  requires: []
  requires_any:
    - phase:DISCOVERY
    - intent:discovery
  blocks:
    - has:payment_required

tools:
  always_available:
    - resolve_location
    - get_available_locations
  context_available:
    - propose_search_preferences
  restricted:
    - execute_search

transitions:
  on_success: search
  on_failure: null
  on_user_request:
    - search
    - evaluation

model:
  default: haiku
  upgrade_on_complexity: true
---

# Discovery Skill Instructions
[Markdown body with detailed instructions...]
```

**Dostępne skills:**
| Skill | Opis | Model |
|-------|------|-------|
| discovery | Zbieranie preferencji | Haiku |
| search | Wykonywanie wyszukiwań | Haiku |
| evaluation | Analiza i porównania | Sonnet |
| narrator | Opisy i narracje | Sonnet |
| market_analysis | Analiza rynku | Sonnet |
| lead_capture | Zbieranie kontaktów | Haiku |

**Kluczowe pliki:**
| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| SkillLoader | `backend/app/skills/loader.py` | Parser SKILL.md |
| GateEvaluator | `backend/app/skills/loader.py` | Validation gates |
| Skill definitions | `backend/app/skills/definitions/*.md` | 6 SKILL.md files |

### Tool Schema V3

```python
class ToolDefinitionV3:
    name: str
    description: str
    input_schema: Dict[str, Any]
    reliability: ReliabilityScore  # HIGH, MEDIUM, LOW
    cost: CostIndicator           # FREE, CHEAP, MODERATE, EXPENSIVE, PREMIUM
    policies: List[PolicyTag]     # FREEMIUM, PREMIUM_ONLY, PHASE_*
    natural_triggers: List[str]   # "szukam działki", "znajdź działkę"
    composition: CompositionHint  # before, after, combines_with
```

**Policy Stack (future freemium):**
```
Request → GuardPolicy → PhasePolicy → FreemiumPolicy → RateLimit → EXECUTE
```

**Kluczowe pliki:**
| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| ToolDefinitionV3 | `backend/app/engine/tool_schema_v3.py` | V3 schema |
| PolicyStack | `backend/app/engine/tool_policies.py` | Policy engine |
| ToolRegistryV3 | `backend/app/engine/tool_schema_v3.py` | V3 registry |

### Premium Services

**Neighborhood Analysis:**
```python
# backend/app/services/neighborhood_service.py
async def analyze_neighborhood(parcel_id: str, radius_m: int = 500):
    """Comprehensive neighborhood assessment including:
    - Character (urban/suburban/rural)
    - Density metrics
    - Transport/amenities scores
    - Strengths/weaknesses
    - Ideal use cases
    """
```

**3D Terrain (skeleton):**
```python
# backend/app/services/terrain_3d_service.py
async def get_terrain_for_parcel(parcel_id: str, quality: TerrainQuality):
    """LiDAR-based terrain visualization:
    - Elevation grid from GUGiK NMT
    - Slope/aspect analysis
    - Building suitability assessment
    Note: Requires GUGiK API integration for production
    """
```

### Feedback Learning

```python
# backend/app/services/feedback_learning.py
class FeedbackLearningService:
    def rerank_results(self, results, state, boost_factor=1.5, penalty_factor=0.6):
        """Re-rank based on similarity to favorites/rejections"""

    def extract_preference_patterns(self, state):
        """Extract patterns from user feedback"""

    def save_feedback_to_workspace(self, state):
        """Persist patterns to user workspace"""
```

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

## Neo4j v2 Architecture ✅ NOWE (2026-01-25)

### Statystyki grafu

```
WĘZŁY: ~171,000 (25 typów)
├── Parcel:           154,959  (główne dane)
├── POGZone:            4,399  (strefy planistyczne)
├── District:             161  (dzielnice + warianty nazw)
├── BuildingType:         129  (typy budynków)
├── OwnershipGroup:        15  (grupy właścicieli)
├── School:                60  (szkoły)
├── BusStop:              339  (przystanki)
├── Shop:               8,332  (sklepy)
├── Water:                521  (wody)
├── Forest:             1,411  (lasy)
├── Road:                 512  (drogi główne)
├── POGProfile:            29  (profile funkcji)
├── City:                   3  (miasta)
├── Kategorie:            ~30  (Quietness, Nature, Access, Density, Size, etc.)
└── Semantic entities:   ~150  (LocationName, SemanticCategory, etc.)

RELACJE: ~5.94M (26 typów)
├── NEAR_SHOP:        747,483  (distance_m property)
├── ADJACENT_TO:      407,825  (shared_border_m, avg 33.8m) ✅ UKOŃCZONE
├── NEAR_BUS_STOP:    248,086
├── LOCATED_IN:       244,033  (Parcel → District)
├── NEAR_SCHOOL:      226,069
├── NEAR_FOREST:      168,554
├── HAS_QUIETNESS:    154,959
├── HAS_NATURE:       154,959
├── HAS_ACCESS:       154,959
├── HAS_DENSITY:      154,959
├── HAS_SIZE:         154,959
├── NEAREST_WATER_TYPE: 154,959
├── HAS_BUILD_STATUS: 154,959
├── HAS_OWNERSHIP:    153,763
├── HAS_OWNER_GROUP:  153,763
├── NEAR_WATER:       106,917
├── HAS_POG:           78,525  (Parcel → POGZone)
├── HAS_BUILDING_*:   122,212  (FUNCTION + TYPE)
├── NEAR_ROAD:         41,271
├── ALLOWS_PROFILE:    34,549  (POGZone → POGProfile)
├── IN_CITY:            4,399  (POGZone → City)
└── inne:               ~1,000  (BELONGS_TO, MAPS_TO, etc.)

EMBEDDINGI:
├── text_embedding:    154,959 × 512-dim (semantic search)
└── graph_embedding:   154,959 × 256-dim (similarity via FastRP)
```

### Hierarchia węzłów

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOKALIZACJA                                  │
├─────────────────────────────────────────────────────────────────────┤
│  City (3)  ←──BELONGS_TO──  District (161) ←──LOCATED_IN──  Parcel  │
│  Gdańsk                      Osowa                         154,959   │
│  Gdynia                      Kokoszki                                │
│  Sopot                       Orłowo                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         WŁASNOŚĆ                                     │
├─────────────────────────────────────────────────────────────────────┤
│  OwnershipType (5)  ←──HAS_OWNERSHIP──  Parcel                      │
│   • prywatna (78,249 działek) ← MOŻNA KUPIĆ!                        │
│   • publiczna (73,478)                                              │
│   • spółdzielcza (1,008)                                            │
│   • kościelna (501)                                                 │
│   • inna (527)                                                      │
│                                                                      │
│  OwnershipGroup (15)  ←──HAS_OWNER_GROUP──  Parcel                  │
│   • Osoby fizyczne (78,249)                                         │
│   • Gminy własność (40,900)                                         │
│   • Skarb Państwa (8,548)                                           │
│   • ... (12 innych grup)                                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         ZABUDOWA                                     │
├─────────────────────────────────────────────────────────────────────┤
│  BuildStatus (2)  ←──HAS_BUILD_STATUS──  Parcel                     │
│   • zabudowana (61,107 = 39.4%)                                     │
│   • niezabudowana (93,852 = 60.6%)                                  │
│                                                                      │
│  BuildingFunction (10)  ←──HAS_BUILDING_FUNCTION──  Parcel          │
│   • mieszkalne (47,852)                                             │
│   • gospodarcze (5,071)                                             │
│   • handlowo-usługowe, biurowe, przemysłowe...                      │
│                                                                      │
│  BuildingType (129)  ←──HAS_BUILDING_TYPE──  Parcel                 │
│   • budynek jednorodzinny (35,556)                                  │
│   • budynek wielorodzinny (11,882)                                  │
│   • budynek gospodarczy, garaż, magazyn...                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      PLANOWANIE (POG)                                │
├─────────────────────────────────────────────────────────────────────┤
│  POGZone (4,399)  ←──HAS_POG──  Parcel                              │
│   Właściwości:                                                       │
│   • symbol: SW, SJ, SU, SN, SO, SK, SI, SP, SZ, SH                  │
│   • is_residential: true/false                                      │
│   • max_height_m, max_coverage_pct, min_bio_pct                     │
│                                                                      │
│  POGProfile (29)  ←──ALLOWS_PROFILE──  POGZone                      │
│   • MN (zabudowa jednorodzinna) - 2,394 stref                       │
│   • MW (zabudowa wielorodzinna) - 1,975 stref                       │
│   • U (usługi) - 3,302 stref                                        │
│   • ZP/ZD/ZB (zieleń) - 4,399 stref                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                           ROZMIAR                                    │
├─────────────────────────────────────────────────────────────────────┤
│  SizeCategory (4)  ←──HAS_SIZE──  Parcel                            │
│   • mala (<500m²) - 83,827 działek                                  │
│   • pod_dom (500-2000m²) - 41,915 ← IDEALNE POD DOM!               │
│   • duza (2000-5000m²) - 17,772                                     │
│   • bardzo_duza (>5000m²) - 11,445                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      POI Z ODLEGŁOŚCIAMI                             │
├─────────────────────────────────────────────────────────────────────┤
│  (p:Parcel)-[:NEAR_SCHOOL {distance_m: 450}]->(s:School)            │
│  (p:Parcel)-[:NEAR_BUS_STOP {distance_m: 180}]->(b:BusStop)         │
│  (p:Parcel)-[:NEAR_SHOP {distance_m: 320}]->(sh:Shop)               │
│  (p:Parcel)-[:NEAR_WATER {distance_m: 150}]->(w:Water)              │
│  (p:Parcel)-[:NEAR_FOREST {distance_m: 200}]->(f:Forest)            │
│  (p:Parcel)-[:NEAR_ROAD {distance_m: 50}]->(r:Road)                 │
│                                                                      │
│  Thresholds: School 2000m, BusStop 1000m, Shop 1500m,               │
│              Water 500m, Forest 500m, Road 200m                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Dual Embeddings

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TEXT EMBEDDINGS (512-dim)                         │
├─────────────────────────────────────────────────────────────────────┤
│  Model: distiluse-base-multilingual-cased-v1                        │
│  Użycie: Semantic search (user queries → similar parcels)           │
│                                                                      │
│  Przykładowy opis:                                                   │
│  "Działka w Osowa, Gdańsk. Powierzchnia 1200 m² (idealna pod dom).  │
│   Własność prywatna - można kupić. Niezabudowana. Strefa budowlana  │
│   MN. Cicha okolica, blisko lasu i jeziora."                        │
│                                                                      │
│  Test query: "cicha zielona działka blisko lasu pod dom"            │
│  → Top results: Osowa, Chwarzno-Wiczlino (score 0.72+)              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    GRAPH EMBEDDINGS (256-dim)                        │
├─────────────────────────────────────────────────────────────────────┤
│  Algorithm: FastRP (Neo4j GDS 2.5.6)                                │
│  Użycie: Similarity search (find similar parcels by structure)      │
│                                                                      │
│  Graph projection includes:                                          │
│  - Parcel, District, QuietnessCategory, NatureCategory              │
│  - SizeCategory, OwnershipType, BuildStatus                         │
│  - Relations: LOCATED_IN, HAS_QUIETNESS, HAS_NATURE, etc.           │
│                                                                      │
│  Test: Parcel in Wyspa Sobieszewska                                 │
│  → Similar: other parcels in Wyspa Sobieszewska (score 1.0)         │
└─────────────────────────────────────────────────────────────────────┘
```

### Przykładowe zapytania Multi-Hop

```cypher
-- 2-hop: Prywatna działka w Osowej
MATCH (p:Parcel)-[:LOCATED_IN]->(d:District {name: 'Osowa'})
MATCH (p)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: 'prywatna'})
RETURN p.id_dzialki, p.area_m2, p.quietness_score
LIMIT 50

-- 3-hop: Niezabudowana działka pod dom w cichej okolicy blisko szkoły
MATCH (p:Parcel)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: 'niezabudowana'})
MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory {id: 'pod_dom'})
MATCH (p)-[:HAS_QUIETNESS]->(qc:QuietnessCategory)
WHERE qc.id IN ['bardzo_cicha', 'cicha']
MATCH (p)-[r:NEAR_SCHOOL]->(s:School)
WHERE r.distance_m < 1000
RETURN p.id_dzialki, p.area_m2, p.dzielnica, r.distance_m AS dist_school
ORDER BY p.quietness_score DESC
LIMIT 20

-- 4-hop: Prywatna działka budowlana w Gdańsku z dobrym dostępem
MATCH (c:City {name: 'Gdańsk'})<-[:BELONGS_TO]-(d:District)<-[:LOCATED_IN]-(p:Parcel)
MATCH (p)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: 'prywatna'})
MATCH (p)-[:HAS_POG]->(z:POGZone {is_residential: true})
MATCH (p)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: 'niezabudowana'})
OPTIONAL MATCH (p)-[r1:NEAR_SCHOOL]->(s:School)
OPTIONAL MATCH (p)-[r2:NEAR_BUS_STOP]->(b:BusStop)
WITH p, d, z,
     COUNT(DISTINCT s) AS schools_nearby,
     COUNT(DISTINCT b) AS bus_stops_nearby,
     MIN(r1.distance_m) AS nearest_school
WHERE schools_nearby >= 1 AND bus_stops_nearby >= 1
RETURN p.id_dzialki, d.name AS dzielnica, p.area_m2,
       schools_nearby, nearest_school
ORDER BY (schools_nearby + bus_stops_nearby) DESC
LIMIT 30

-- GraphRAG: Vector + Graph hybrid
CALL db.index.vector.queryNodes('parcel_text_embedding_idx', 100, $userQueryVector)
YIELD node AS candidate, score AS vector_score
MATCH (candidate)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: 'prywatna'})
MATCH (candidate)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: 'niezabudowana'})
MATCH (candidate)-[:LOCATED_IN]->(d:District)
RETURN candidate.id_dzialki, d.name, vector_score
ORDER BY vector_score DESC
LIMIT 20
```

---

## Neo4j v2 Pipeline ✅ UKOŃCZONY

### Skrypty

| # | Skrypt | Status | Output |
|---|--------|--------|--------|
| 21 | `21_create_neo4j_schema_v2.py` | ✅ | Constraints, indexes, category nodes, vector indexes |
| 22 | `22_import_category_nodes.py` | ✅ | 208 węzłów kategorii (BuildingType: 129) |
| 23 | `23_import_pog_zones.py` | ✅ | 4,399 POGZone nodes, 34,549 ALLOWS_PROFILE |
| 24 | `24_import_parcels_v2.py` | ✅ | 154,959 Parcel nodes, 1.87M relacji |
| 25 | `25_create_poi_relations.py` | ✅ | 1,538,380 NEAR_* relacji z distance_m |
| 26 | `26_generate_parcel_embeddings.py` | ✅ | Text 512-dim + Graph 256-dim |
| 27 | `27_create_adjacency_relations.py` | ✅ | 407,825 ADJACENT_TO (avg 33.8m border) |

### Uruchomienie

```bash
# Pełny pipeline (wszystkie skrypty)
./egib/scripts/pipeline/run_neo4j_v2_pipeline.sh

# Tylko pojedynczy skrypt
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="moja-dzialka-neo4j-2026"
python3 egib/scripts/pipeline/24_import_parcels_v2.py

# Tylko graph embeddings (po zainstalowaniu GDS)
python3 egib/scripts/pipeline/26_generate_parcel_embeddings.py --graph-only
```

### Neo4j GDS Plugin

Zainstalowany dla graph analytics (FastRP, community detection):

```yaml
# docker-compose.yml
neo4j:
  image: neo4j:5.15-community
  volumes:
    - ./neo4j-plugins:/var/lib/neo4j/plugins  # GDS jar tutaj
  environment:
    NEO4J_dbms_security_procedures_unrestricted: "apoc.*,gds.*"
    NEO4J_dbms_security_procedures_allowlist: "apoc.*,gds.*"
```

**Weryfikacja:**
```cypher
RETURN gds.version()  -- "2.5.6"
```

---

## Dane

### Dane gotowe do importu (488 MB)

Czyste, przetworzone dane w `data/ready-for-import/`:

| Katalog | Rozmiar | Zawartość |
|---------|---------|-----------|
| `postgis/` | 294 MB | 11 plików GPKG (działki, POG, POI, BDOT10k) |
| `neo4j/csv/` | 162 MB | 13+ plików CSV dla Neo4j |
| `milvus/` | 33 MB | CSV do embeddingów |

### Przetworzone dane źródłowe

| Plik | Rekordów | Opis |
|------|----------|------|
| `parcels_enriched.gpkg` | 154,959 | Działki z **68 cechami** |
| `pog_trojmiasto.gpkg` | 7,523 | Strefy planistyczne |
| `poi_trojmiasto.gpkg` | 15,421 | Punkty zainteresowania |
| `water_classified.gpkg` | 2,307 | Sklasyfikowane obiekty wodne |
| `parcels_full.csv` | 154,959 | Export do Neo4j (103 MB, 69 kolumn) |

### Działki (154,959)

**Podział terytorialny:**
- **Gdańsk:** 92,781 działek
- **Gdynia:** 53,907 działek
- **Sopot:** 8,271 działek

**Właściwości Parcel (68+ kolumn):**
```
# Identyfikacja
id_dzialki, gmina, dzielnica, miejscowosc, powiat, wojewodztwo

# Geometria
area_m2, bbox_height, bbox_width, shape_index, size_category
centroid_lat, centroid_lon, centroid_x, centroid_y

# Własność
grupa_rej, grupa_rej_nazwa, typ_wlasnosci

# Zabudowa
is_built, building_count, building_area_m2, building_coverage_pct
building_max_floors, building_main_function, building_type
has_residential, has_industrial, under_construction

# POG (planowanie)
has_pog, pog_symbol, pog_nazwa, pog_oznaczenie
pog_profil_podstawowy, pog_profil_dodatkowy
pog_maks_wysokosc_m, pog_maks_zabudowa_pct, pog_min_bio_pct
is_residential_zone

# Odległości do POI
dist_to_school, dist_to_bus_stop, dist_to_supermarket
dist_to_doctors, dist_to_pharmacy, dist_to_kindergarten
dist_to_restaurant, dist_to_industrial, dist_to_main_road

# Odległości do natury
dist_to_forest, dist_to_water
dist_to_sea, dist_to_river, dist_to_lake, dist_to_canal, dist_to_pond
nearest_water_type

# Wskaźniki kompozytowe (0-100)
quietness_score, nature_score, accessibility_score

# Kategorie binned
kategoria_ciszy, kategoria_natury, kategoria_dostepu, gestosc_zabudowy

# Kontekst okolicy (500m buffer)
pct_forest_500m, pct_water_500m, count_buildings_500m

# Embeddingi (NOWE)
text_embedding (512-dim), graph_embedding (256-dim)
```

### POG - Plany Ogólne Gmin

| Miasto | Strefy | W Neo4j |
|--------|--------|---------|
| Gdańsk | 3,710 | 1,203 |
| Gdynia | 3,195 | 2,578 |
| Sopot | 618 | 618 |
| **RAZEM** | **7,523** | **4,399** |

**Profile funkcji (top 10):**
| Profil | Nazwa | Strefy |
|--------|-------|--------|
| ZD | Zieleń działkowa | 4,399 |
| I | Infrastruktura | 4,399 |
| W | Wody | 4,399 |
| L | Las | 4,399 |
| ZP | Zieleń parkowa | 4,378 |
| K | Komunikacja | 4,234 |
| U | Usługi | 3,302 |
| MN | Zabudowa jednorodzinna | 2,394 |
| MW | Zabudowa wielorodzinna | 1,975 |
| ZB | Zieleń biologicznie czynna | 418 |

### Wody sklasyfikowane

| Typ | Liczba | Premium | Przykłady |
|-----|--------|---------|-----------|
| morze | 20 | +50-100% | Morze Bałtyckie, Zatoka Gdańska |
| jezioro | 99 | +20-40% | Osowskie, Jasień, Wysockie, Straszyńskie |
| rzeka | 96 | +10-20% | Radunia, Motława, Strzyża, Wisła |
| kanal | 49 | +5-10% | Kanał Raduni, Czarna Łacha |
| staw | 2,043 | +5% | Małe zbiorniki, oczka wodne |

### Ceny gruntów (raport 2025)

| Segment | Zakres cen/m² | Lokalizacje |
|---------|---------------|-------------|
| ULTRA-PREMIUM | >3000 zł | Sopot Dolny, Kamienna Góra, Orłowo |
| PREMIUM | 1500-3000 zł | Jelitkowo, Śródmieścia |
| WYSOKI | 800-1500 zł | Oliwa, Wrzeszcz, Redłowo |
| ŚREDNI | 500-800 zł | Kokoszki, Osowa, Jasień |
| BUDŻETOWY | 300-500 zł | Łostowice, Chełm, Pruszcz Gd. |
| EKONOMICZNY | <300 zł | Żukowo, Kolbudy, Reda |

---

## Agent-Doradca ✅ ZAKTUALIZOWANY (2026-01-25)

Agent moja-dzialka to **wyspecjalizowany doradca nieruchomości**, który:
- Rozmawia naturalnie, jak kompetentny znajomy z branży
- Zna dogłębnie 155k działek i **68+ cech** każdej z nich
- Używa hybrydowego wyszukiwania (graph + vector + spatial)
- **NOWOŚĆ:** Filtruje po własności, statusie zabudowy, rozmiarze
- **NOWOŚĆ:** Znajduje sąsiadów i działki blisko konkretnych POI
- Doradza, rekomenduje, wyjaśnia trade-offy

### Kluczowe komponenty

| Komponent | Lokalizacja | Opis |
|-----------|-------------|------|
| Core Memory | `backend/app/memory/schemas/core.py` | DNA agenta + wiedza Neo4j v2 |
| Core Template | `backend/app/memory/templates/core.j2` | Prompt z wiedzą domenową |
| Tools Registry | `backend/app/engine/tools_registry.py` | 32+ narzędzi |
| Tool Executor | `backend/app/engine/tool_executor.py` | Implementacje narzędzi |
| Graph service | `backend/app/services/graph_service.py` | Neo4j queries (multi-hop) |
| Parcel search | `backend/app/services/parcel_search.py` | Hybrid search (graph+vector) |
| Embedding service | `backend/app/services/embedding_service.py` | sentence-transformers |

### Narzędzia agenta

**Wyszukiwanie (główne):**
- `propose_search_preferences` - propozycja preferencji z filtrami v2
- `approve_search_preferences` - zatwierdzenie preferencji
- `execute_search` - wykonanie wyszukiwania hybrydowego
- `search_by_water_type` - działki blisko morza/jeziora/rzeki
- `count_matching_parcels_quick` - checkpoint searches

**Filtry Neo4j v2 (NOWE):**
- `ownership_type` - prywatna (78k!), publiczna, spółdzielcza, kościelna, inna
- `build_status` - zabudowana, niezabudowana (93k pod budowę!)
- `size_category` - mala, pod_dom (41k idealnych!), duza, bardzo_duza
- `pog_residential` - tylko strefy mieszkaniowe POG

**Graph Tools (NOWE - Neo4j v2):**
- `find_adjacent_parcels` - sąsiedzi przez ADJACENT_TO (407k relacji)
- `search_near_specific_poi` - działki blisko konkretnego POI po nazwie
- `find_similar_by_graph` - podobne strukturalnie (graph embeddings 256-dim)

**Kontekst:**
- `get_parcel_full_context` - pełne dane działki
- `get_parcel_neighborhood` - okolica i sąsiedzi
- `get_water_info` - odległości do wód

**Lokalizacja:**
- `resolve_location` - nazwa → dzielnica (fuzzy match)
- `resolve_entity` - semantic entity resolution (512-dim embeddings)
- `get_available_locations`, `get_districts_in_miejscowosc`

### Przykłady użycia nowych filtrów

```
User: "Szukam działki do kupienia w Osowej"
Agent: ownership_type="prywatna" + miejscowosc="Osowa"
→ Używa: MATCH (p)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: 'prywatna'})

User: "Niezabudowana działka pod dom"
Agent: build_status="niezabudowana" + size_category=["pod_dom"]
→ Używa: MATCH (p)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: 'niezabudowana'})
         MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory) WHERE sz.id IN ['pod_dom']

User: "Jakie działki sąsiadują z tą?"
Agent: find_adjacent_parcels(parcel_id="220611_2.0001.1234")
→ Używa: MATCH (p)-[r:ADJACENT_TO]-(neighbor) RETURN neighbor, r.shared_border_m

User: "Działki blisko szkoły SP nr 45"
Agent: search_near_specific_poi(poi_type="school", poi_name="SP nr 45")
→ Używa: MATCH (p)-[r:NEAR_SCHOOL]->(s:School) WHERE s.name CONTAINS 'SP nr 45'
```

### Architektura Software 3.0

**7-Warstwowy Model Pamięci:**
| Warstwa | Opis |
|---------|------|
| Core | DNA agenta - immutable identity |
| Working | Stan sesji, sliding window |
| Semantic | Profil kupującego, preferencje |
| Episodic | Historia sesji |
| Workflow | State machine lejka |
| Preferences | Styl doradztwa |
| Procedural | Skills registry |

**State Machine:**
```
DISCOVERY → SEARCH → EVALUATION → NEGOTIATION → LEAD_CAPTURE
     ↑         ↓
  RETENTION ←──┘
```

---

## Pipeline danych

### Pipeline v1 (dane źródłowe)
| Krok | Skrypt | Output |
|------|--------|--------|
| 1 | `01_parse_pog.py` | 7,523 stref POG |
| 2 | `02_merge_parcels.py` | 154,959 działek |
| 3 | `03_add_districts.py` | Przypisanie dzielnic |
| 3b | `03b_clip_bdot10k.py` | 8 warstw BDOT10k |
| 4 | `04_merge_poi.py` | 15,421 POI |
| 5 | `05_feature_engineering.py` | Wskaźniki, kategorie |
| 6 | `06_add_buildings.py` | Cechy zabudowy |
| 7a | `07a_district_prices.py` | Ceny dzielnic |
| 11 | `11_classify_water.py` | 2,307 wód → 6 typów |
| 12 | `12_calculate_water_distances.py` | dist_to_sea/river/lake |

### Pipeline v2 (Neo4j) ✅ NOWY
| Krok | Skrypt | Output |
|------|--------|--------|
| 21 | `21_create_neo4j_schema_v2.py` | Schema + indexes |
| 22 | `22_import_category_nodes.py` | 208 kategorii |
| 23 | `23_import_pog_zones.py` | 4,399 POGZone |
| 24 | `24_import_parcels_v2.py` | 154,959 Parcel + 1.87M relacji |
| 25 | `25_create_poi_relations.py` | 1.54M NEAR_* relacji |
| 26 | `26_generate_parcel_embeddings.py` | Text + Graph embeddings |
| 27 | `27_create_adjacency_relations.py` | 407,825 ADJACENT_TO |

### Semantic Entity Resolution
| Krok | Skrypt | Output |
|------|--------|--------|
| 15 | `15_create_neo4j_schema.py` | Vector indexes 512-dim |
| 19 | `19_generate_entity_embeddings.py` | LocationName, SemanticCategory nodes |

---

## Struktura projektu

```
moja-dzialka/
├── backend/                    # FastAPI backend
│   └── app/
│       ├── api/                # REST + WebSocket
│       ├── engine/             # v3.0 Agent System
│       │   ├── agent_coordinator.py    # Session management
│       │   ├── property_advisor_agent.py # Root Orchestrator
│       │   ├── sub_agents.py           # SubAgentSpawner + Router
│       │   ├── tool_schema_v3.py       # V3 tool definitions
│       │   ├── tool_policies.py        # Policy stack
│       │   ├── tools_registry.py       # 33+ tools
│       │   └── tool_executor.py        # Tool implementations
│       ├── memory/             # 7-warstwowy model pamięci
│       │   ├── schemas/        # Core, Working, Semantic, etc.
│       │   ├── logic/          # Manager, flush.py (NEW)
│       │   ├── templates/      # Jinja2 prompts
│       │   └── workspace.py    # File-based storage (NEW)
│       ├── persistence/        # Redis + PostgreSQL
│       ├── services/           # Domain services
│       │   ├── graph_service.py        # Neo4j queries
│       │   ├── embedding_service.py    # sentence-transformers
│       │   ├── neighborhood_service.py # Neighborhood analysis (NEW)
│       │   ├── terrain_3d_service.py   # 3D terrain (NEW)
│       │   └── feedback_learning.py    # Re-ranking (NEW)
│       └── skills/             # Skills v3
│           ├── loader.py       # SkillLoader + GateEvaluator
│           ├── _base.py        # Base classes
│           └── definitions/    # SKILL.md files
│               ├── discovery.md
│               ├── search.md
│               ├── evaluation.md
│               ├── narrator.md
│               ├── market_analysis.md
│               └── lead_capture.md
├── frontend/                   # React + Vite + Tailwind
├── data/
│   └── ready-for-import/       # Dane do importu (488 MB)
│       ├── postgis/            # GeoPackage files
│       ├── neo4j/csv/          # CSV dla Neo4j
│       └── milvus/             # Embeddings CSV
├── egib/
│   ├── data/processed/         # Przetworzone dane
│   └── scripts/pipeline/       # Pipeline scripts (27+)
├── neo4j-plugins/              # GDS plugin JAR
├── docker-compose.yml          # Dev config
├── docker-compose.prod.yml     # Prod overrides
└── CLAUDE.md                   # Ten plik
```

---

## Docker & Deployment

### Docker Compose

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_max__size: 4G
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*,gds.*"
    volumes:
      - neo4j_data:/data
      - ./neo4j-plugins:/var/lib/neo4j/plugins  # GDS
      - ./data/ready-for-import/neo4j/csv:/var/lib/neo4j/import
```

### Serwer produkcyjny

| Parametr | Wartość |
|----------|---------|
| Provider | Hetzner CX53 |
| CPU | 16 vCPU |
| RAM | 32 GB |
| Storage | 305 GB NVMe |
| OS | Ubuntu 24.04 |
| IP | 77.42.86.222 |

### Alokacja RAM (32 GB)

| Usługa | Limit | Uzasadnienie |
|--------|-------|--------------|
| Neo4j | 10 GB | Graf 155k + embeddings |
| PostgreSQL | 6 GB | Spatial queries |
| Backend | 4 GB | API + Claude |
| Redis | 2 GB | Session cache |
| MongoDB | 2 GB | Leads |
| Celery | 2 GB | Background |
| System | ~6 GB | OS + nginx |

---

## Changelog

### 2026-02-02: Agent System v3.0 ✅ MAJOR

**Cel:** Przebudowa systemu agentowego inspirowana wzorcami OpenClaw.

**Nowe komponenty:**

1. **Multi-Agent System (`backend/app/engine/sub_agents.py`):**
   - SubAgentSpawner - spawnowanie wyspecjalizowanych agentów
   - AgentRouter - routing intencji do właściwego agenta
   - 6 typów agentów: Discovery, Search, Analyst, Narrator, Feedback, Lead
   - Konfigurowalny model (Haiku/Sonnet) per agent

2. **Memory Flush (`backend/app/memory/logic/flush.py`):**
   - MemoryFlushManager z LLM-powered extraction (Haiku)
   - Automatyczne zapisywanie faktów przed kompakcją kontekstu
   - Rule-based fallback dla prostych wzorców

3. **Workspace Manager (`backend/app/memory/workspace.py`):**
   - File-based storage w ~/.parcela/users/{id}/
   - Profile.md (profil kupującego)
   - Sessions/ (historia sesji)
   - Memory/ (wyekstrahowane fakty)

4. **Skills v3 (`backend/app/skills/`):**
   - SKILL.md format z YAML frontmatter
   - SkillLoader parser
   - GateEvaluator dla walidacji aktywacji
   - 6 deklaratywnych definicji skills

5. **Tool Schema V3 (`backend/app/engine/tool_schema_v3.py`):**
   - ToolDefinitionV3 z reliability, cost, policies
   - Natural language triggers
   - Composition hints (before/after/combines_with)
   - ToolRegistryV3 z policy-based filtering

6. **Premium Services:**
   - NeighborhoodService - analiza okolicy
   - Terrain3DService - wizualizacja 3D (skeleton)
   - FeedbackLearningService - re-ranking

**Usunięte (legacy cleanup):**
- `backend/app/agent/` - backwards compat shim
- `backend/app/skills/discovery.py` etc. - Python skill classes
- `backend/app/skills/templates/` - Jinja templates
- `backend/app/engine/tools_registry_v2.py` - unused

---

### 2026-01-25: Neo4j v2 Pipeline ✅ MAJOR

**Cel:** Pełne wykorzystanie multi-hop traversals i GraphRAG.

**Zmiany:**
1. **Nowe węzły kategorii:**
   - OwnershipType (5): prywatna, publiczna, spółdzielcza, kościelna, inna
   - OwnershipGroup (15): Osoby fizyczne, Gminy, Skarb Państwa, etc.
   - BuildStatus (2): zabudowana, niezabudowana
   - BuildingFunction (10): mieszkalne, gospodarcze, biurowe, etc.
   - BuildingType (129): jednorodzinny, wielorodzinny, etc.
   - SizeCategory (4): mala, pod_dom, duza, bardzo_duza

2. **POGZone jako węzły:**
   - 4,399 stref planistycznych jako osobne węzły
   - Relacja HAS_POG (Parcel → POGZone)
   - Relacja ALLOWS_PROFILE (POGZone → POGProfile)

3. **NEAR_* relacje z distance_m:**
   - 1.54M relacji przestrzennych
   - Każda relacja ma `distance_m` property
   - Thresholds: School 2000m, BusStop 1000m, Shop 1500m, etc.

4. **Dual embeddings:**
   - Text embedding (512-dim): distiluse-base-multilingual
   - Graph embedding (256-dim): FastRP via Neo4j GDS

5. **Neo4j GDS 2.5.6:**
   - Zainstalowany dla FastRP i community detection
   - Konfiguracja w docker-compose.yml

**Nowe skrypty:** 21-27 w `egib/scripts/pipeline/`

---

### 2026-01-25: Semantic Entity Resolution

**Problem:** Lokalizacje spoza EGiB (np. "Matemblewo") nie były rozpoznawane.

**Rozwiązanie:** Embeddingi semantyczne 512-dim dla entity resolution:
- LocationName: "Matemblewo" → Matarnia
- SemanticCategory: "spokojna" → [bardzo_cicha, cicha]
- WaterTypeName: "nad morzem" → morze

---

### 2026-01-25: Agent Neo4j v2 Integration ✅

**Cel:** Pełna integracja agenta z Neo4j v2 (nowe węzły, relacje, embeddingi).

**Zmodyfikowane pliki:**

| Plik | Zmiany |
|------|--------|
| `memory/schemas/core.py` | Rozszerzone domain_expertise, binned_categories, nowy neo4j_knowledge |
| `memory/templates/core.j2` | Nowa sekcja `<neo4j_knowledge>` z wiedzą o własności/zabudowie/rozmiarze |
| `engine/tools_registry.py` | 4 nowe filtry + 3 nowe narzędzia grafowe |
| `services/graph_service.py` | Rozszerzony ParcelSearchCriteria + 4 nowe metody |
| `services/parcel_search.py` | Rozszerzony SearchPreferences z v2 filtrami |
| `engine/tool_executor.py` | Implementacje 3 nowych narzędzi grafowych |

**Nowe filtry wyszukiwania:**
- `ownership_type` - filtr przez HAS_OWNERSHIP (78k prywatnych = można kupić!)
- `build_status` - filtr przez HAS_BUILD_STATUS (93k niezabudowanych)
- `size_category` - filtr przez HAS_SIZE (41k idealnych pod dom)
- `pog_residential` - filtr przez HAS_POG (tylko strefy mieszkaniowe)

**Nowe narzędzia agenta:**
- `find_adjacent_parcels` - sąsiedzi przez ADJACENT_TO (407k relacji)
- `search_near_specific_poi` - działki blisko POI po nazwie (NEAR_* relacje)
- `find_similar_by_graph` - podobieństwo strukturalne (graph embeddings 256-dim)

**Nowe metody graph_service:**
- `find_adjacent_parcels()` - sąsiedzi z shared_border_m
- `search_near_poi()` - wyszukiwanie przez NEAR_* relacje
- `find_similar_by_graph_embedding()` - FastRP vector search
- `graphrag_search()` - hybrid vector + graph search

---

### 2026-01-24: graph_service.py refactor

**Problem:** Stary schemat Neo4j (Dzialka, MA_CISZE) nie istniał.

**Rozwiązanie:** Przepisano wszystkie metody dla nowego schematu (Parcel, HAS_QUIETNESS).

---

## Następne kroki

### Ukończone ✅
1. [x] Pipeline danych v1 (154,959 działek, 68 cech)
2. [x] Agent-Doradca v1 (SYSTEM_PROMPT, narzędzia)
3. [x] Architektura Software 3.0 (7-warstw pamięci, skills)
4. [x] Neo4j Knowledge Graph v1 (basic schema)
5. [x] Semantic Entity Resolution (embeddings 512-dim)
6. [x] **Neo4j v2 Pipeline** (multi-hop, NEAR_*, embeddings)
7. [x] **Neo4j GDS installation** (FastRP graph embeddings)
8. [x] **Adjacency relations** (407,825 ADJACENT_TO, avg 33.8m border)
9. [x] **Agent Neo4j v2 Integration** (nowe filtry, narzędzia grafowe)
10. [x] **Agent System v3.0** - Multi-agent, Memory Flush, Skills v3, Tool Schema v3
11. [x] **Premium Services** - Neighborhood Analysis, 3D Terrain skeleton, Feedback Learning
12. [x] **Legacy Cleanup** - usunięcie nieużywanych komponentów

### Do zrobienia 📋
13. [ ] **Frontend v3** - aktualizacja UI do obsługi wszystkich funkcji agenta
    - Multi-agent responses display
    - Feedback controls (favorites/rejections)
    - Premium feature indicators
    - Neighborhood analysis visualization
14. [ ] Testy E2E wyszukiwania przez agenta
15. [ ] Deploy na serwer produkcyjny (Hetzner)
16. [ ] Integracja płatności (Stripe)
17. [ ] Lead capture UI + analytics
18. [ ] Community detection (Louvain) dla rekomendacji
19. [ ] Monitoring (Grafana + Prometheus)

---

*Ostatnia aktualizacja: 2026-02-02 17:10 UTC*
