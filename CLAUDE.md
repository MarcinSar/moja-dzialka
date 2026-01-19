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

## Status projektu (2026-01-19)

### UKOŃCZONE: Pipeline danych

| Etap | Skrypt | Wynik |
|------|--------|-------|
| 1. Walidacja | `01_validate.py` | Wszystkie dane źródłowe poprawne |
| 2. BDOT10k | `02_clean_bdot10k.py` | 7 warstw skonsolidowanych |
| 3. MPZP | `02_clean_mpzp.py` | 14,473 stref planistycznych |
| 4. Działki | `02_clean_parcels.py` | 1,300,779 działek z land cover |
| 5. Features | `03_feature_engineering.py` | **36 cech obliczonych** |
| 6. Admin data | `03b_enrich_admin_data.py` | Wzbogacenie o gminy/powiaty z BDOT10k |
| 7. Dev sample | `04_create_dev_sample.py` | 10,471 działek testowych |

### UKOŃCZONE: Import danych do baz (dev sample)

| Skrypt | Baza | Status | Wynik |
|--------|------|--------|-------|
| `05_import_postgis.py` | PostGIS | ✅ Zaimportowane | 10,471 działek z geometrią |
| `06_import_neo4j.py` | Neo4j | ✅ Zaimportowane | 10,886 węzłów, 138,672 relacji |
| `07_generate_srai.py` | Parquet | ✅ Wygenerowane | 10,471 embeddingów (64-dim) |
| `08_import_milvus.py` | Milvus | ✅ Zaimportowane | 10,471 wektorów |

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

### UKOŃCZONE: Frontend (Discovery Phase + Parcel Reveal)

| Komponent | Plik | Funkcja |
|-----------|------|---------|
| Discovery Phase | `components/phases/DiscoveryPhase.tsx` | Główna faza z awatarem i chatem |
| Avatar | `components/avatar/AvatarFull.tsx` | Animowany awatar (Rive) |
| Chat | `components/chat/DiscoveryChat.tsx` | Interfejs czatu |
| **Parcel Reveal** | `components/reveal/ParcelRevealCard.tsx` | **Płynne pokazywanie działek** |
| Mini Map | `components/reveal/ParcelMiniMap.tsx` | Mapa satelitarna z działką |
| Map Layers | `components/reveal/MapLayerSwitcher.tsx` | Przełącznik warstw mapy |

### NOWE (2026-01-19): Search Architecture Redesign

**Problem:** Agent nie wykorzystywał pełnych możliwości bazy danych (36 cech, 15 typów węzłów).

**Rozwiązanie:**
1. **Graph as PRIMARY** - Neo4j search ZAWSZE się wykonuje (nawet bez explicit criteria)
2. **Nowe wagi RRF:** Graph 50% + Spatial 30% + Vector 20%
3. **25+ pól preferencji** - kategorie ciszy, natury, dostępności, gęstości zabudowy
4. **Rich System Prompt** - agent zna wszystkie wymiary danych i mapowanie "user mówi" → "szukaj po"

**Kluczowe zmiany:**
- `parcel_search.py` - Graph ALWAYS runs, new SearchPreferences fields
- `graph_service.py` - comprehensive `search_parcels()` with all criteria
- `tools.py` - 25+ new input fields, improved highlights generation
- `orchestrator.py` - Rich data context in SYSTEM_PROMPT

### NOWE (2026-01-19): Parcel Reveal Flow

**Problem:** Wcześniej wyniki wyszukiwania powodowały skok do 3-panelowego layoutu (brzydkie przejście).

**Rozwiązanie:** Płynna karta z mapą w Discovery layout:
- Wyniki pojawiają się jako pływająca karta po prawej stronie
- Animacje slide-in/out (framer-motion)
- Mapa satelitarna (Esri - darmowa, bez API key)
- Przełącznik warstw: Satelita / Teren / Mapa
- Nawigacja Poprz./Nast. dla wielu działek
- Karta znika gdy user kontynuuje rozmowę

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCOVERY LAYOUT                          │
│                                                              │
│     [AWATAR]              ┌──────────────────────────┐      │
│       ~~~                 │ [MAPA SATELITARNA]       │      │
│                           │     📍 działka           │      │
│    "Znalazłem coś        │                          │      │
│     dla Ciebie!"         ├──────────────────────────┤      │
│                           │ Kolbudy, 1,234 m²        │      │
│    [Chat history]         │                          │      │
│                           │ DLACZEGO:                │      │
│    [___input___]          │ • Cisza: 92/100         │      │
│                           │ • Natura: 85/100        │      │
│                           │ • MPZP: MN              │      │
│                           │                          │      │
│                           │ [← Poprz] 1/5 [Nast →]  │      │
│                           └──────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Architektura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                     │
│   React + Leaflet + Chat UI + Avatar + ParcelReveal                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket / REST
┌────────────────────────────▼────────────────────────────────────────┐
│                      AGENT LAYER (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │ ParcelAgent │  │ Tools       │  │ EventStream │                  │
│  │ (Claude API)│  │ (13 tools)  │  │ (WebSocket) │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
│                           │                                          │
│  Patterns: Human-in-the-Loop | Guard | Critic | Few-Shot            │
│  System Prompt: Rich data context with all available dimensions     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                     SEARCH LAYER (Graph as PRIMARY)                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              HybridSearchService (RRF Fusion)                 │   │
│  │   graph (50%) = PRIMARY + spatial (30%) + vector (20%)        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Graph ALWAYS runs → Spatial (if lat/lon) → Vector (if similarity)  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                       DATA LAYER (dev sample)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   PostGIS    │  │    Neo4j     │  │   Milvus     │               │
│  │  (geometrie) │  │   (graf)     │  │  (wektory)   │               │
│  │ 10,471 dział.│  │ 10,886 nodes │  │ 10,471 vec.  │               │
│  │ 38 kolumn    │  │ 138,672 rels │  │ 64-dim SRAI  │               │
│  │              │  │ = PRIMARY!   │  │              │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Zawartość baz danych (dev sample)

### PostGIS - Dane przestrzenne

**Tabela `parcels`**: 10,471 działek z pełną geometrią (EPSG:2180)

| Kategoria | Kolumny | Opis |
|-----------|---------|------|
| Identyfikacja | `id_dzialki`, `teryt_powiat` | Unikalne ID działki |
| Geometria | `geom`, `centroid_lat`, `centroid_lon`, `area_m2` | Polygon + centroid WGS84 |
| Lokalizacja | `gmina`, `gmina_teryt`, `powiat`, `powiat_teryt`, `miejscowosc` | Hierarchia administracyjna |
| Pokrycie terenu | `forest_ratio`, `water_ratio`, `builtup_ratio` | Procent powierzchni |
| Odległości | `dist_to_school`, `dist_to_shop`, `dist_to_hospital`, `dist_to_bus_stop`, `dist_to_public_road`, `dist_to_main_road`, `dist_to_forest`, `dist_to_water`, `dist_to_industrial` | Metry do najbliższego POI |
| Bufory 500m | `pct_forest_500m`, `pct_water_500m`, `count_buildings_500m` | Analiza otoczenia |
| MPZP | `has_mpzp`, `mpzp_symbol`, `mpzp_przeznaczenie` | Plan zagospodarowania |
| Wskaźniki | `quietness_score`, `nature_score`, `accessibility_score`, `compactness` | Cechy kompozytowe (0-100) |
| Dostęp | `has_public_road_access` | Boolean - dostęp do drogi |

**Statystyki:**
- Gminy: 15 (Gdańsk, Pruszcz Gdański, Kolbudy, Żukowo, Somonino...)
- Powiaty: 3 (gdański, kartuski, Gdańsk miasto)
- Z MPZP: 6,180 (59%)
- Z dostępem do drogi: 8,913 (85%)

### Neo4j - Graf wiedzy

**Węzły (15 typów, 10,886 łącznie):**

| Typ węzła | Liczba | Opis |
|-----------|--------|------|
| `Dzialka` | 10,471 | Działki z kluczowymi atrybutami |
| `Miejscowosc` | 337 | Miejscowości (wsie, dzielnice) |
| `SymbolMPZP` | 19 | Symbole planu (MN, MW, R, ZL...) |
| `Gmina` | 15 | Gminy pomorskie |
| `RodzajMiejscowosci` | 7 | Typy: wieś, część wsi, przysiółek, osada... |
| `CharakterTerenu` | 5 | wiejski, podmiejski, miejski, leśny, mieszany |
| `POIType` | 5 | school, shop, hospital, bus_stop, industrial |
| `GestoscZabudowy` | 5 | bardzo_gesta, gesta, umiarkowana, rzadka, bardzo_rzadka |
| `KategoriaCiszy` | 4 | bardzo_cicha, cicha, umiarkowana, głośna |
| `KategoriaNatury` | 4 | bardzo_zielona, zielona, umiarkowana, zurbanizowana |
| `KategoriaDostepu` | 4 | doskonały, dobry, umiarkowany, ograniczony |
| `KategoriaPowierzchni` | 4 | mala, srednia, duza, bardzo_duza |
| `Powiat` | 3 | gdański, kartuski, Gdańsk |
| `LandCoverType` | 2 | forest, water |
| `Wojewodztwo` | 1 | pomorskie |

**Relacje (19 typów, 138,672 łącznie):**

| Relacja | Liczba | Opis |
|---------|--------|------|
| `W_GMINIE` | 10,808 | Dzialka/Miejscowosc → Gmina |
| `MA_DOSTEP` | 10,471 | Dzialka → KategoriaDostepu |
| `MA_POWIERZCHNIE` | 10,471 | Dzialka → KategoriaPowierzchni |
| `MA_ZABUDOWE` | 10,471 | Dzialka → GestoscZabudowy |
| `MA_CHARAKTER` | 10,471 | Dzialka → CharakterTerenu |
| `MA_CISZE` | 10,471 | Dzialka → KategoriaCiszy |
| `W_MIEJSCOWOSCI` | 10,471 | Dzialka → Miejscowosc |
| `MA_NATURE` | 10,471 | Dzialka → KategoriaNatury |
| `BLISKO_LASU` | 9,607 | Dzialka → LandCoverType {distance_m} |
| `BLISKO_WODY` | 9,487 | Dzialka → LandCoverType {distance_m} |
| `MA_PRZEZNACZENIE` | 6,180 | Dzialka → SymbolMPZP |
| `BLISKO_SZKOLY` | 10,471 | Dzialka → POIType {distance_m, rank} |
| `BLISKO_SKLEPU` | 10,471 | Dzialka → POIType {distance_m, rank} |
| `BLISKO_SZPITALA` | 10,471 | Dzialka → POIType {distance_m, rank} |
| `BLISKO_PRZYSTANKU` | 10,471 | Dzialka → POIType {distance_m, rank} |
| `BLISKO_PRZEMYSLU` | 10,471 | Dzialka → POIType {distance_m, rank} |
| `W_POWIECIE` | 15 | Gmina → Powiat |
| `W_WOJEWODZTWIE` | 3 | Powiat → Wojewodztwo |
| `MA_RODZAJ` | 337 | Miejscowosc → RodzajMiejscowosci |

**Hierarchia administracyjna:**
```
pomorskie (Wojewodztwo)
├── gdański (Powiat) - 9 gmin
│   ├── Pruszcz Gdański - 123 miejscowości
│   ├── Kolbudy - 45 miejscowości
│   ├── Żukowo - 67 miejscowości
│   └── ...
├── kartuski (Powiat) - 5 gmin
│   ├── Somonino - 34 miejscowości
│   └── ...
└── Gdańsk (Powiat/Miasto) - 1 gmina
    └── Gdańsk - dzielnice
```

### Milvus - Embeddingi wektorowe

**Kolekcja `parcels`**: 10,471 wektorów

| Parametr | Wartość |
|----------|---------|
| Wymiar wektora | 64 |
| Metoda | Feature-based (nie SRAI contextual) |
| Metryka | COSINE |
| Index | IVF_FLAT (nlist=128) |

**Cechy użyte do embeddingu (20):**

```
area_m2, forest_ratio, water_ratio, builtup_ratio,
dist_to_school, dist_to_shop, dist_to_hospital, dist_to_bus_stop,
dist_to_public_road, dist_to_main_road, dist_to_forest, dist_to_water,
dist_to_industrial, pct_forest_500m, pct_water_500m, count_buildings_500m,
quietness_score, nature_score, accessibility_score, compactness
```

**Metadata w Milvus:**
- `id` (primary key) - id_dzialki
- `gmina` - nazwa gminy
- `area_m2` - powierzchnia
- `has_mpzp` - boolean
- `quietness_score` - wskaźnik ciszy
- `nature_score` - wskaźnik natury

**Przykładowe zapytanie similarity search:**
```python
# Znajdź działki podobne do podanej
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"nprobe": 10}},
    limit=20,
    expr="area_m2 >= 800 AND area_m2 <= 1500 AND has_mpzp == true"
)
```

---

## Agent Tools (15 narzędzi)

### Human-in-the-Loop: Preferencje

| Narzędzie | Opis |
|-----------|------|
| `propose_search_preferences` | Zaproponuj preferencje (25+ pól - patrz niżej) |
| `approve_search_preferences` | Zatwierdź po potwierdzeniu użytkownika |
| `modify_search_preferences` | Zmień pojedynczą preferencję |

**Dostępne pola preferencji (propose_search_preferences):**

| Kategoria | Pola |
|-----------|------|
| **Lokalizacja** | `gmina`, `miejscowosc`, `powiat`, `charakter_terenu` (wiejski/podmiejski/miejski/leśny/mieszany) |
| **Powierzchnia** | `min_area`, `max_area`, `area_category` (mala/srednia/duza/bardzo_duza) |
| **Cisza** | `quietness_categories` (bardzo_cicha/cicha/umiarkowana/głośna), `max_dist_to_industrial_m` |
| **Natura** | `nature_categories`, `max_dist_to_forest_m`, `max_dist_to_water_m`, `min_forest_pct_500m` |
| **Gęstość** | `building_density` (bardzo_gesta/gesta/umiarkowana/rzadka/bardzo_rzadka) |
| **Dostępność** | `accessibility_categories`, `max_dist_to_school_m`, `max_dist_to_shop_m`, `max_dist_to_bus_stop_m`, `has_road_access` |
| **MPZP** | `has_mpzp`, `mpzp_budowlane`, `mpzp_symbols` (MN/MN_U/MW/U/R/ZL...) |

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
1. User: "Szukam działki blisko Gdańska, ok 1000 m², cicho i blisko lasu"

2. Agent → propose_search_preferences({
     gmina: "Gdańsk",
     charakter_terenu: ["podmiejski"],
     min_area: 800, max_area: 1200,
     area_category: ["srednia"],
     quietness_categories: ["bardzo_cicha", "cicha"],
     nature_categories: ["bardzo_zielona", "zielona"],
     max_dist_to_forest_m: 300
   })
   Agent: "Szukam średnich (800-1200 m²), cichych działek w podmiejskich
           rejonach Gdańska, blisko lasu. Pasuje?"

3. User: "Tak, ale chcę z planem miejscowym, żeby łatwiej budować"

4. Agent → modify_search_preferences({
     field: "has_mpzp", new_value: true
   })
   Agent → modify_search_preferences({
     field: "mpzp_budowlane", new_value: true
   })
   Agent: "Dodam działki z MPZP budowlanym. Zatwierdzamy?"

5. User: "Tak, szukaj"

6. Agent → approve_search_preferences()
   Agent → execute_search({limit: 5})
   Agent: "Znalazłem 47 działek, oto 5 najlepszych..."
   [Karta z mapą pojawia się płynnie]

7. User: "Ta jest za mała, pokaż większe"

8. Agent → critique_search_results({feedback: "za małe działki"})
   Agent → refine_search({adjustment: "increase_area"})
   Agent: "Szukam większych działek..."
```

---

## Frontend: Parcel Reveal System (2026-01-19)

### Store: parcelRevealStore.ts

```typescript
interface ParcelRevealState {
  parcels: ParcelWithExplanation[];  // Wszystkie działki z wyszukiwania
  currentIndex: number;               // Aktualnie wyświetlana działka
  isVisible: boolean;                 // Czy karta jest widoczna
  mapLayer: 'satellite' | 'terrain' | 'streets';

  // Actions
  setParcels(parcels): void;
  showReveal(): void;
  hideReveal(): void;
  nextParcel(): void;
  prevParcel(): void;
  setMapLayer(layer): void;
  clear(): void;
}

interface ParcelWithExplanation {
  parcel: SearchResultItem;
  explanation: string;      // "Kolbudy, 1 234 m²"
  highlights: string[];     // ["Cisza: 92/100", "Las: 150m", ...]
}
```

### Komponenty reveal/

| Komponent | Opis |
|-----------|------|
| `ParcelRevealCard.tsx` | Główna pływająca karta z animacjami (framer-motion) |
| `ParcelMiniMap.tsx` | Leaflet map z tile layers (Esri satellite - darmowe) |
| `MapLayerSwitcher.tsx` | Przyciski do przełączania warstw mapy |

### Tile Layers (bez API key)

```typescript
const TILE_LAYERS = {
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  terrain: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
  streets: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
};
```

### Data Flow

```
1. User: "Szukam działki blisko lasu"
   ↓
2. Agent → execute_search()
   ↓
3. Backend: tools.py
   - Wykonuje hybrid search
   - Generuje highlights dla każdej działki
   - Generuje explanation (lokalizacja + powierzchnia)
   ↓
4. WebSocket → tool_result {tool: "execute_search", result: {parcels: [...]}}
   ↓
5. App.tsx: handleToolResult()
   - Parsuje parcels z highlights/explanation
   - parcelRevealStore.setParcels(parcels)
   - parcelRevealStore.showReveal()
   ↓
6. DiscoveryPhase.tsx
   - AnimatePresence renderuje ParcelRevealCard
   - Karta slide-in z prawej strony
   ↓
7. User: wysyła nową wiadomość
   ↓
8. useChat.ts: handleSubmit()
   - parcelRevealStore.hideReveal()
   - Karta slide-out
```

### Backend: Highlights Generation

```python
# backend/app/agent/tools.py

def _generate_highlights(parcel: dict, prefs: dict) -> list[str]:
    highlights = []

    # Cisza (quietness)
    if parcel.get("quietness_score", 0) >= 85:
        highlights.append(f"Cisza: {parcel['quietness_score']}/100")

    # Natura
    if parcel.get("nature_score", 0) >= 70:
        highlights.append(f"Natura: {parcel['nature_score']}/100")

    # MPZP
    if parcel.get("has_mpzp"):
        highlights.append(f"MPZP: {parcel.get('mpzp_symbol', '')}")

    return highlights[:4]  # Max 4 highlights
```

### Zmiany w istniejących plikach

| Plik | Zmiana |
|------|--------|
| `searchStore.ts` | Usunięto auto-transition do Results po setMapData() |
| `useChat.ts` | Dodano hideReveal() przy wysyłaniu wiadomości |
| `App.tsx` | Obsługa execute_search tool_result → parcelRevealStore |
| `index.css` | Usunięto dark filter na mapie (dla satelity) |
| `tools.py` | Dodano _generate_highlights() i _generate_explanation() |

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
│           ├── tools.py               # 15 agent tools + state + highlights
│           └── orchestrator.py        # ParcelAgent + streaming
├── frontend/
│   └── src/
│       ├── App.tsx                    # Root + WebSocket event handling
│       ├── index.css                  # Tailwind + Leaflet styles
│       ├── components/
│       │   ├── phases/
│       │   │   ├── DiscoveryPhase.tsx     # Główna faza (awatar + chat)
│       │   │   ├── ResultsPhase.tsx       # Faza wyników (3-panelowa)
│       │   │   └── PhaseTransition.tsx    # Menedżer faz
│       │   ├── chat/
│       │   │   ├── DiscoveryChat.tsx      # Chat w Discovery
│       │   │   └── ResultsChat.tsx        # Chat w Results
│       │   ├── avatar/
│       │   │   ├── AvatarFull.tsx         # Pełny awatar (Rive)
│       │   │   └── AvatarCompact.tsx      # Kompaktowy awatar
│       │   ├── reveal/                    # ✨ NOWE (2026-01-19)
│       │   │   ├── ParcelRevealCard.tsx   # Pływająca karta z działką
│       │   │   ├── ParcelMiniMap.tsx      # Mini mapa Leaflet
│       │   │   ├── MapLayerSwitcher.tsx   # Przełącznik warstw
│       │   │   └── index.ts               # Barrel export
│       │   ├── MapPanel.tsx               # Panel mapy (Results)
│       │   └── effects/
│       │       └── ParticleBackground.tsx # Efekt cząsteczek
│       ├── stores/
│       │   ├── chatStore.ts               # Stan czatu (Zustand)
│       │   ├── searchStore.ts             # Stan wyszukiwania
│       │   ├── uiPhaseStore.ts            # Stan fazy UI
│       │   └── parcelRevealStore.ts       # ✨ NOWY: Stan reveal flow
│       ├── hooks/
│       │   └── useChat.ts                 # Hook czatu + quick actions
│       ├── services/
│       │   ├── websocket.ts               # WebSocket client
│       │   └── api.ts                     # REST API client
│       └── types/
│           └── index.ts                   # TypeScript interfaces
├── scripts/
│   ├── init-db.sql                    # PostGIS schema
│   └── pipeline/
│       ├── 01_validate.py             # Walidacja danych źródłowych
│       ├── 02_clean_bdot10k.py        # Czyszczenie BDOT10k (7 warstw)
│       ├── 02_clean_mpzp.py           # Czyszczenie MPZP (14k stref)
│       ├── 02_clean_parcels.py        # Czyszczenie działek (1.3M)
│       ├── 03_feature_engineering.py  # 36 cech obliczonych
│       ├── 03b_enrich_admin_data.py   # Wzbogacenie o gminy/powiaty z BDOT10k
│       ├── 04_create_dev_sample.py    # Dev sample (10,471 działek)
│       ├── 05_import_postgis.py       # Import do PostGIS (--sample)
│       ├── 06_import_neo4j.py         # Import do Neo4j (--sample)
│       ├── 07_generate_srai.py        # Generowanie embeddingów (--sample)
│       └── 08_import_milvus.py        # Import do Milvus (--sample)
├── data/
│   ├── processed/v1.0.0/
│   │   ├── parcel_features.parquet    # 324 MB, 36 features
│   │   └── parcel_features.gpkg       # 722 MB, with geometry
│   └── dev/
│       ├── parcels_dev.gpkg           # 10,471 działek (wzbogacone o admin data)
│       ├── bdot10k_dev.gpkg           # BDOT10k dla dev area
│       ├── mpzp_dev.gpkg              # MPZP dla dev area
│       └── embeddings/
│           ├── parcel_embeddings.npy      # 10,471 × 64 float32
│           ├── parcel_embeddings.parquet  # Z metadanymi
│           ├── parcel_ids.txt             # Lista ID działek
│           └── embedding_metadata.json    # Konfiguracja embeddingu
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

## Hybrid Search (RRF Fusion) - Graph as PRIMARY

```python
# Reciprocal Rank Fusion with Graph as PRIMARY source
# Graph ALWAYS runs, provides main filtering by categories
GRAPH_WEIGHT = 0.5     # Neo4j (PRIMARY - categories, MPZP, relationships)
SPATIAL_WEIGHT = 0.3   # PostGIS (distance, area, geometry)
VECTOR_WEIGHT = 0.2    # Milvus (similarity to reference parcel)

# RRF Score = Σ(weight / (K + rank))
# K = 60 (standard constant)

# Search strategy:
# 1. Graph search ALWAYS runs (even without explicit criteria)
# 2. Spatial search runs if lat/lon provided
# 3. Vector search runs if similarity_to_parcel_id provided
```

---

## Uruchomienie

### 1. Bazy danych

```bash
docker-compose up -d postgres neo4j milvus redis
```

**Konfiguracja połączeń (docker-compose.yml):**

| Baza | Host:Port | User | Password | Database/Collection |
|------|-----------|------|----------|---------------------|
| PostGIS | localhost:5432 | app | secret | moja_dzialka |
| Neo4j | localhost:7687 | neo4j | secretpassword | neo4j |
| Neo4j Browser | localhost:7474 | - | - | - |
| Milvus | localhost:19530 | - | - | parcels |
| Redis | localhost:6379 | - | - | - |

### 2. Import dev sample

```bash
cd scripts/pipeline

# 1. Wzbogacenie danych administracyjnych (jeśli nie wykonano)
python 03b_enrich_admin_data.py --sample

# 2. Import do baz danych
python 05_import_postgis.py --sample    # ~7s
python 06_import_neo4j.py --sample      # ~30s
python 07_generate_srai.py --sample     # ~5s
python 08_import_milvus.py --sample     # ~3s
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev      # Development server (port 5173)
npm run build    # Production build
```

### 5. Test API

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

*Ostatnia aktualizacja: 2026-01-19 (Graph as PRIMARY + 25+ preference fields)*
