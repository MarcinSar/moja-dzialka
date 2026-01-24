# moja-dzialka - Skonsolidowany Plan V3

**Data:** 2026-01-22
**Status:** Faza planowania, przed implementacją pipeline danych

---

## 1. Podsumowanie projektu

### Cel
**moja-dzialka** - inteligentny agent AI do wyszukiwania działek budowlanych w Trójmieście, który:
1. Prowadzi naturalny dialog o preferencjach
2. Wyszukuje hybrydowo (graf + wektor + przestrzenne)
3. Prezentuje działki z bogatym opisem kontekstowym
4. Zbiera feedback i iteruje
5. Generuje leady (monetyzacja)

### Model biznesowy
- 3 działki za darmo (preview)
- 20 PLN za pełne wyniki
- Lead generation do właścicieli

---

## 2. Stan dokumentacji

### Dokumenty ukończone

| Dokument | Opis | Status |
|----------|------|--------|
| `KNOWLEDGE_BASE_POG.md` | Baza wiedzy o POG - 13 stref, profile, parametry | ✅ Kompletny |
| `GRAPH_ARCHITECTURE_V2.md` | Three-Graph Architecture, Neo4j jako Unified Store | ✅ Kompletny |
| `ARCHITECTURE_SCALABILITY.md` | Plan skalowania od 225k do 30M działek | ✅ Kompletny |
| `RESEARCH_SPATIAL_EMBEDDINGS.md` | Universal embedding schema 32-dim | ✅ Kompletny |
| `RESEARCH_3D_TERRAIN_VISUALIZATION.md` | Potree + COPC dla wizualizacji terenu | ✅ Kompletny |
| `DESIGN_PARCEL_PRESENTATION.md` | Mechanizm bogatych opisów działek | ✅ Kompletny |
| `DATA_POG.md` | Struktura danych POG z GML | ✅ Kompletny |
| `DATA_PARCELS.md` | Struktura działek, schemat wzbogacenia | ✅ Kompletny |
| `DATA_BDOT10K.md` | 72 warstwy BDOT10k, priorytety | ✅ Kompletny |

### Dokumenty do aktualizacji

| Dokument | Co wymaga zmiany |
|----------|------------------|
| `CLAUDE.md` | Zaktualizować o nowe odkrycia |
| `AI_AGENT.md` | Przeprojektować wg Software 3.0 |

---

## 3. Dane źródłowe - podsumowanie

### 3.1 Działki (ULDK/GUGiK)

| Metryka | Wartość |
|---------|---------|
| Plik | `dzialki/dzialki_pomorskie.gpkg` |
| Rozmiar | 429 MB |
| Liczba | 1,300,779 (całe pomorskie) |
| Trójmiasto | ~225,000 działek |
| Format | GeoPackage, EPSG:2180 |
| Kolumny | fid, ID_DZIALKI, TERYT_POWIAT, geom |

### 3.2 POG (Plany Ogólne Gmin)

| Gmina | Plik | Stref | Format |
|-------|------|-------|--------|
| Gdańsk | `pog-gdansk-proj-uzg-042025.gml` | ~3,710 | GML 3.2 |
| Gdynia | `POG_Gdynia_projekt_uzg_032025_podpisany.gml` | ~6,390 | GML 3.2 |
| Sopot | `POG_SOPOT_12092025.gml` | ~1,236 | GML 3.2 |
| **RAZEM** | | **~11,336** | EPSG:2177 |

**Kluczowe dane POG:**
- 13 symboli stref (SW, SJ, SN, SU, SK, SH, SC, SO, SP, SR, SI, SZ, SG)
- 28 profili podstawowych, 23 dodatkowe
- Parametry: intensywność, max zabudowa %, max wysokość, min bio %

### 3.3 BDOT10k

| Kategoria | Warstwy | Obiektów | Użycie |
|-----------|---------|----------|--------|
| Budynki | BUBD_A | 695,642 | Gęstość, typ |
| Drogi | SKDR_L | 411,575 | Dostępność |
| Lasy | PTLZ_A | 75,577 | Natura |
| Wody | PTWP_A | 49,670 | Natura |
| Przystanki | OIKM_P | 10,554 | Transport |
| Szkoły | KUOS_A | 1,092 | POI |
| Przemysł | KUPG_A | 3,795 | Cisza |
| Miejscowości | ADMS_A/P | 4,094 | Lokalizacja |

### 3.4 LiDAR (GUGiK)

| Typ | Format | Gęstość | Użycie |
|-----|--------|---------|--------|
| NMT | GeoTIFF | Grid | Elevation stats |
| NMPT | GeoTIFF | Grid | Surface model |
| Pomiarowe | LAZ 1.4 | 4-20 pkt/m² | 3D Potree |

---

## 4. Architektura techniczna

### 4.1 Bazy danych

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                       │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────┐  │
│  │      PostGIS        │  │              Neo4j                       │  │
│  │   (Spatial Store)   │  │     (Unified Graph + Vector Store)      │  │
│  │                     │  │                                          │  │
│  │  • parcels          │  │  DOMAIN GRAPH:                          │  │
│  │  • pog_zones        │  │  • Dzialka, Gmina, Dzielnica            │  │
│  │  • poi              │  │  • StrefaPOG, ProfilFunkcji             │  │
│  │  • GIST indexes     │  │  • Kategorie jakościowe                 │  │
│  │                     │  │                                          │  │
│  │  Użycie:            │  │  VECTOR INDEX:                          │  │
│  │  • Spatial queries  │  │  • 32-dim embeddings na Dzialka         │  │
│  │  • GeoJSON export   │  │  • Unified search (graph+vector)        │  │
│  │  • Wizualizacja     │  │                                          │  │
│  └─────────────────────┘  └─────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────┐                                                │
│  │  Object Storage     │  Potree COPC dla wizualizacji 3D terenu       │
│  │  (S3/Hetzner)       │  ~5-10 GB dla Trójmiasta                      │
│  └─────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Kluczowa decyzja:** Neo4j jako Unified Store (Graph + Vector) - bez zewnętrznego Milvus.

### 4.2 Schemat wzbogaconych działek

```python
parcels_enriched = {
    # Identyfikacja
    'id_dzialki': str,
    'teryt_powiat': str,
    'wojewodztwo': str,          # dla partycjonowania

    # Geometria
    'geom': Polygon,             # EPSG:2180
    'area_m2': float,
    'centroid_lat': float,
    'centroid_lon': float,

    # Lokalizacja (z BDOT10k ADMS)
    'gmina': str,
    'dzielnica': str,

    # POG (spatial join)
    'pog_strefa_id': str,
    'pog_symbol': str,
    'pog_profil_podstawowy': list[str],
    'pog_max_intensywnosc': float,
    'pog_max_zabudowa_pct': float,
    'pog_max_wysokosc': float,
    'pog_min_bio_pct': float,

    # Odległości (metry)
    'dist_to_forest': int,
    'dist_to_water': int,
    'dist_to_school': int,
    'dist_to_bus_stop': int,
    'dist_to_main_road': int,
    'dist_to_industrial': int,

    # Bufory 500m
    'pct_forest_500m': float,
    'pct_water_500m': float,
    'count_buildings_500m': int,

    # Wskaźniki (0-100)
    'quietness_score': int,
    'nature_score': int,
    'accessibility_score': int,

    # Kategorie (dla Neo4j)
    'cisza_kategoria': str,      # bardzo_cicha, cicha, umiarkowana, głośna
    'natura_kategoria': str,     # bardzo_zielona, zielona, umiarkowana, zurbanizowana
    'dostepnosc_kategoria': str, # doskonała, dobra, umiarkowana, ograniczona
    'powierzchnia_klasa': str,   # mala, pod_dom, duza, bardzo_duza

    # Teren (z LiDAR/NMT)
    'elevation_min': float,
    'elevation_max': float,
    'slope_avg_pct': float,
    'slope_category': str,       # płaska, łagodna, umiarkowana, stroma

    # Flagi
    'is_buildable': bool,
    'typ_zabudowy': str,         # jednorodzinna, wielorodzinna, usługowa, brak
}
```

### 4.3 Graf Neo4j - schemat

```cypher
// WĘZŁY (12 typów)
(:Gmina {nazwa, teryt, wojewodztwo})
(:Dzielnica {nazwa, gmina})
(:Dzialka {id, area_m2, centroid_lat, centroid_lon, embedding[32]})
(:StrefaPOG {id, symbol, nazwa, max_intensywnosc, max_zabudowa_pct, max_wysokosc, min_bio_pct})
(:ProfilFunkcji {kod, nazwa, typ})
(:KategoriaCiszy {poziom})
(:KategoriaNatury {poziom})
(:KategoriaDostepnosci {poziom})
(:KlasaPowierzchni {klasa})
(:TypZabudowy {typ})

// RELACJE (11 typów)
(:Dzialka)-[:W_GMINIE]->(:Gmina)
(:Dzialka)-[:W_DZIELNICY]->(:Dzielnica)
(:Dzielnica)-[:NALEZY_DO]->(:Gmina)
(:Dzialka)-[:W_STREFIE_POG]->(:StrefaPOG)
(:StrefaPOG)-[:DOZWALA_PODSTAWOWY]->(:ProfilFunkcji)
(:StrefaPOG)-[:DOZWALA_DODATKOWY]->(:ProfilFunkcji)
(:Dzialka)-[:MA_CISZE]->(:KategoriaCiszy)
(:Dzialka)-[:MA_NATURE]->(:KategoriaNatury)
(:Dzialka)-[:MA_DOSTEPNOSC]->(:KategoriaDostepnosci)
(:Dzialka)-[:MA_POWIERZCHNIE]->(:KlasaPowierzchni)
(:Dzialka)-[:MOZE_ZABUDOWAC]->(:TypZabudowy)

// VECTOR INDEX
CREATE VECTOR INDEX parcel_embeddings FOR (d:Dzialka) ON (d.embedding)
OPTIONS { indexConfig: { `vector.dimensions`: 32, `vector.similarity_function`: 'cosine' }}
```

---

## 5. Architektura agenta (Software 3.0)

### 5.1 Spektrum autonomii
**Poziom 4** - Managed Memory Agent z elementami Poziom 5 (planowanie)

### 5.2 Warstwy pamięci (DataWorkshop Blueprint)

| Warstwa | Implementacja w moja-dzialka |
|---------|------------------------------|
| **Constitutional** | Guardrails: nie podawaj cen, nie wartościuj, bądź obiektywny |
| **Working** | Bieżąca sesja: ostatnie 10 wiadomości, aktualny widok działki |
| **Workflow** | State Machine: DISCOVERY → SEARCH → PRESENTATION → REFINEMENT → LEAD |
| **Episodic** | Historia: feedback na działki, poprzednie wyszukiwania |
| **Semantic** | RAG z KNOWLEDGE_BASE_POG + District Knowledge Base |
| **Procedural** | Narzędzia (Tools): search, present, compare, terrain_view |
| **Resource** | Stan: czy DB online, ile działek w wynikach |

### 5.3 Workflow State Machine

```
┌──────────────────────────────────────────────────────────────────┐
│                     WORKFLOW STATES                               │
│                                                                   │
│  ┌────────────┐     ┌────────────┐     ┌────────────────────┐   │
│  │ DISCOVERY  │────►│  SEARCH    │────►│   PRESENTATION     │   │
│  │            │     │            │     │                    │   │
│  │ Zbieranie  │     │ Wykonanie  │     │ Pokazywanie        │   │
│  │ preferencji│     │ hybrid     │     │ działek z opisem   │   │
│  └────────────┘     │ search     │     └─────────┬──────────┘   │
│        ▲            └────────────┘               │              │
│        │                                         ▼              │
│        │            ┌────────────┐     ┌────────────────────┐   │
│        └────────────│ REFINEMENT │◄────│   FEEDBACK         │   │
│                     │            │     │                    │   │
│                     │ Modyfikacja│     │ 👍/👎 na działki   │   │
│                     │ preferencji│     └────────────────────┘   │
│                     └─────┬──────┘                              │
│                           │                                      │
│                           ▼                                      │
│                     ┌────────────┐                               │
│                     │   LEAD     │                               │
│                     │            │                               │
│                     │ Zbieranie  │                               │
│                     │ kontaktu   │                               │
│                     └────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 Narzędzia agenta (MCP-style)

```python
# TOOLS (aktywne akcje)
@tool search_parcels(criteria: SearchCriteria) -> SearchResults
@tool present_parcel(parcel_id: str, style: str) -> ParcelPresentation
@tool compare_parcels(parcel_ids: list[str]) -> ComparisonView
@tool get_terrain_view(parcel_id: str) -> TerrainViewer
@tool save_lead(contact: ContactInfo, parcel_id: str) -> LeadConfirmation

# RESOURCES (pasywny dostęp)
@resource user_preferences() -> UserContext
@resource search_results() -> list[ParcelSummary]
@resource district_info(name: str) -> DistrictKnowledge
@resource pog_explanation(symbol: str) -> POGExplanation
```

### 5.5 Schema-Guided Reasoning (SGR)

**Pattern: Cascade dla oceny działki**

```python
class ParcelEvaluation(BaseModel):
    """Kaskadowa ocena dopasowania działki do preferencji."""

    # KROK 1: Podsumowanie preferencji
    user_requirements_summary: str = Field(
        description="Co użytkownik chce? (cisza, las, szkoła...)"
    )

    # KROK 2: Ocena dopasowania
    preference_matches: list[PreferenceMatch] = Field(
        description="Dla każdej preferencji: czy spełniona i dlaczego"
    )

    match_score: Annotated[int, Ge(1), Le(10)] = Field(
        description="Ogólna ocena dopasowania 1-10"
    )

    # KROK 3: Decyzja
    presentation_priority: Literal["high", "medium", "low"] = Field(
        description="Czy pokazać tę działkę jako pierwszą?"
    )

    narrative_focus: str = Field(
        description="Na czym skupić się w opisie?"
    )
```

**Pattern: Routing dla intencji użytkownika**

```python
class UserIntent(BaseModel):
    """Router intencji użytkownika."""

    thought_process: str = Field(description="Analiza intencji")

    intent: Union[
        SearchIntent,        # "Szukam działki..."
        FeedbackIntent,      # "Ta mi się podoba / nie podoba"
        QuestionIntent,      # "Co oznacza SJ?"
        NavigationIntent,    # "Pokaż następną"
        LeadIntent,          # "Jestem zainteresowany"
    ]
```

### 5.6 CopilotKit - Generative UI Framework (DO SZCZEGÓŁOWEGO ZAPLANOWANIA)

**Status:** Wybrane jako framework dla warstwy prezentacji i interakcji z agentem.

**Co to jest:**
CopilotKit to open-source (MIT) framework do budowania Agentic UI, gdzie agent AI dynamicznie generuje komponenty React zamiast tylko tekstu.

| Aspekt | Wartość |
|--------|---------|
| Licencja | MIT (open source) |
| GitHub | 28.1k stars, aktywnie rozwijany |
| Framework | React, Next.js, kompatybilny z LangGraph |

**Typy Generative UI:**

| Typ | Opis | Użycie w projekcie |
|-----|------|-------------------|
| **Static** | Agent wybiera z predefiniowanych komponentów | Karty działek, mapa, wykresy |
| **Declarative** | Agent zwraca strukturę JSON, frontend renderuje | Listy wyników, filtry, porównania |

**Kluczowe funkcje dla moja-dzialka:**

1. **Tool Rendering** - `useCopilotAction` renderuje UI gdy agent wywołuje narzędzie
2. **State Synchronization** - `useCoAgent` sync preferencji między UI a agentem
3. **Human-in-the-Loop** - wbudowane approval workflows (lead capture, feedback)
4. **MCP Integration** - narzędzia mogą być MCP servers

**Przykład integracji:**

```tsx
// Gdy agent wywołuje search_parcels → renderuj grid wyników
useCopilotAction({
  name: "search_parcels",
  render: ({ status, result }) => {
    if (status === "executing") return <SearchingSpinner />;
    return (
      <ParcelResultsGrid>
        {result.parcels.map(parcel => (
          <ParcelCard
            key={parcel.id}
            parcel={parcel}
            onFeedback={(type) => agent.feedback(type, parcel.id)}
          />
        ))}
      </ParcelResultsGrid>
    );
  }
});

// Gdy agent wywołuje present_parcel → renderuj pełną prezentację
useCopilotAction({
  name: "present_parcel",
  render: ({ result }) => (
    <ParcelPresentation
      headline={result.headline}
      sections={result.sections}
      map={<LeafletMap parcel={result.parcel} />}
      terrain3D={<PotreeViewer url={result.terrain_url} />}
    />
  )
});
```

**Dokumentacja:**
- [CopilotKit GitHub](https://github.com/CopilotKit/CopilotKit)
- [Generative UI Overview](https://www.copilotkit.ai/generative-ui)
- [MCP Apps Integration](https://docs.copilotkit.ai/generative-ui-specs/mcp-apps)
- [LangGraph Integration](https://docs.copilotkit.ai/coagents/langgraph)
- [useCopilotAction Hook](https://docs.copilotkit.ai/reference/hooks/useCopilotAction)
- [Human-in-the-Loop](https://docs.copilotkit.ai/coagents/human-in-the-loop)

**Do zaplanowania szczegółowo:**
- [ ] Architektura komponentów (ParcelCard, ParcelPresentation, MapView, TerrainViewer)
- [ ] Mapowanie tools → renderers
- [ ] State management (preferencje, wyniki, feedback)
- [ ] Integracja z LangGraph jako orchestratorem
- [ ] Human-in-the-Loop flow dla lead capture

---

## 6. Pipeline danych - konkretny plan

### 6.1 Struktura katalogów

```
data/
├── raw/
│   ├── dzialki/
│   │   └── dzialki_pomorskie.gpkg
│   ├── pog/
│   │   ├── gdansk/
│   │   ├── gdynia/
│   │   └── sopot/
│   ├── bdot10k/
│   │   └── *.gpkg (72 pliki)
│   └── lidar/
│       └── trojmiasto/
│           └── *.laz
│
├── processed/
│   ├── parcels_trojmiasto.gpkg          # Filtrowane działki
│   ├── pog_trojmiasto.gpkg              # Połączone POG
│   ├── parcels_enriched.parquet         # Wzbogacone dane
│   └── embeddings.npy                   # 32-dim embeddings
│
└── copc/
    └── trojmiasto.copc.laz              # Dla Potree
```

### 6.2 Skrypty pipeline

| # | Skrypt | Input | Output | Czas |
|---|--------|-------|--------|------|
| 1 | `01_convert_pog.py` | POG GML × 3 | `pog_trojmiasto.gpkg` | ~30 min |
| 2 | `02_filter_parcels.py` | `dzialki_pomorskie.gpkg` | `parcels_trojmiasto.gpkg` | ~20 min |
| 3 | `03_filter_bdot10k.py` | BDOT10k × 72 | `bdot10k_trojmiasto/` | ~1h |
| 4 | `04_spatial_join_pog.py` | parcels + pog | parcels z POG | ~30 min |
| 5 | `05_compute_distances.py` | parcels + BDOT10k | parcels z odległościami | ~2h |
| 6 | `06_compute_scores.py` | parcels | parcels z wskaźnikami | ~30 min |
| 7 | `07_generate_embeddings.py` | parcels | `embeddings.npy` | ~30 min |
| 8 | `08_import_postgis.py` | parcels | PostGIS tables | ~30 min |
| 9 | `09_import_neo4j.py` | parcels | Neo4j graph | ~1h |
| 10 | `10_prepare_lidar.py` | LAZ files | `trojmiasto.copc.laz` | ~2h |

**Łączny czas:** ~8-10 godzin (jednorazowo)

### 6.3 Obliczanie wskaźników

```python
def calculate_quietness_score(parcel: dict) -> int:
    """
    Wskaźnik ciszy 0-100.
    Wysoki = daleko od hałasu.
    """
    score = 100

    # Negatywne (bliskość = złe)
    if parcel['dist_to_industrial'] < 500:
        score -= 40
    elif parcel['dist_to_industrial'] < 1000:
        score -= 20

    if parcel['dist_to_main_road'] < 100:
        score -= 30
    elif parcel['dist_to_main_road'] < 300:
        score -= 15

    # Pozytywne (wysoka gęstość budynków = mniej ciszy)
    if parcel['count_buildings_500m'] > 100:
        score -= 20
    elif parcel['count_buildings_500m'] > 50:
        score -= 10

    return max(0, min(100, score))


def calculate_nature_score(parcel: dict) -> int:
    """
    Wskaźnik natury 0-100.
    Wysoki = blisko lasów, wód, dużo zieleni.
    """
    score = 0

    # Las
    if parcel['dist_to_forest'] < 200:
        score += 35
    elif parcel['dist_to_forest'] < 500:
        score += 25
    elif parcel['dist_to_forest'] < 1000:
        score += 15

    # Woda
    if parcel['dist_to_water'] < 300:
        score += 25
    elif parcel['dist_to_water'] < 1000:
        score += 15

    # % zieleni w bufferze
    score += int(parcel['pct_forest_500m'] * 40)

    return max(0, min(100, score))


def calculate_accessibility_score(parcel: dict) -> int:
    """
    Wskaźnik dostępności 0-100.
    Wysoki = dobry transport, usługi.
    """
    score = 0

    # Przystanek
    if parcel['dist_to_bus_stop'] < 300:
        score += 30
    elif parcel['dist_to_bus_stop'] < 600:
        score += 20
    elif parcel['dist_to_bus_stop'] < 1000:
        score += 10

    # Szkoła
    if parcel['dist_to_school'] < 800:
        score += 25
    elif parcel['dist_to_school'] < 1500:
        score += 15

    # Droga (dostęp drogowy)
    if parcel['dist_to_main_road'] < 500:
        score += 20
    elif parcel['dist_to_main_road'] < 1000:
        score += 10

    # Sklep (jeśli mamy dane)
    # ...

    return max(0, min(100, score))
```

### 6.4 Kategoryzacja

```python
def categorize_quietness(score: int) -> str:
    if score >= 80: return "bardzo_cicha"
    if score >= 60: return "cicha"
    if score >= 40: return "umiarkowana"
    return "głośna"

def categorize_nature(score: int) -> str:
    if score >= 70: return "bardzo_zielona"
    if score >= 50: return "zielona"
    if score >= 30: return "umiarkowana"
    return "zurbanizowana"

def categorize_accessibility(score: int) -> str:
    if score >= 70: return "doskonała"
    if score >= 50: return "dobra"
    if score >= 30: return "umiarkowana"
    return "ograniczona"

def categorize_area(area_m2: float) -> str:
    if area_m2 < 500: return "mala"
    if area_m2 < 1500: return "pod_dom"
    if area_m2 < 5000: return "duza"
    return "bardzo_duza"

def determine_building_type(pog_symbol: str, profiles: list[str]) -> str:
    """Określa typ dozwolonej zabudowy."""
    if pog_symbol in ['SJ']:
        return "jednorodzinna"
    if pog_symbol in ['SW']:
        if 'teren zabudowy mieszkaniowej jednorodzinnej' in profiles:
            return "mieszana"
        return "wielorodzinna"
    if pog_symbol in ['SU', 'SH']:
        return "usługowa"
    if pog_symbol in ['SZ', 'SN', 'SR']:
        return "brak"
    return "inna"
```

---

## 7. Skalowalność - by design

### 7.1 Partycjonowanie od początku

```python
# Każdy rekord ma kolumnę wojewodztwo
parcels['wojewodztwo'] = 'pomorskie'

# PostGIS - partycjonowanie
CREATE TABLE parcels (...) PARTITION BY LIST (wojewodztwo);
CREATE TABLE parcels_pomorskie PARTITION OF parcels FOR VALUES IN ('pomorskie');

# Neo4j - label per region
(:Dzialka:Pomorskie {...})

# Embeddings - collection per region
collection_pomorskie = Collection("parcels_pomorskie")
```

### 7.2 Routing w aplikacji

```python
def route_query(query: SearchQuery) -> str:
    """Określa region na podstawie zapytania."""
    if query.location:
        return detect_region(query.location)
    return "pomorskie"  # default
```

---

## 8. Źródła wiedzy dla implementacji agenta

### Software 3.0 (priorytet)

| Moduł | Temat | Zastosowanie |
|-------|-------|--------------|
| **Moduł 2** | Memory Engineering | 7 warstw pamięci agenta |
| **Moduł 3** | MCP & Narzędzia | Architektura Tools/Resources |
| **Moduł 4** | Reasoning | Schema-Guided Reasoning patterns |
| **Moduł 5** | Ewaluacja | Testowanie jakości agenta |

**Kluczowe pliki:**
- `ai-edu/_synthesis/software3.0/modul2/essence-01-memory-engineering.md`
- `ai-edu/_synthesis/software3.0/modul3/essence-01-mcp-narzedzia.md`
- `ai-edu/_synthesis/software3.0/modul4/essence-01-reasoning.md`

### Kursy o grafach

| Kurs | Temat | Zastosowanie |
|------|-------|--------------|
| `grafy/kurs1-knowledge-graphs-for-rag/` | KG for RAG | Hybrid search |
| `grafy/kurs2-agentic-kg-construction/` | Agentic KG | Entity resolution |
| `grafy/research-agentic-rag-2025.md` | Agentic RAG | Patterns |

### CopilotKit (Generative UI)

| Zasób | URL | Temat |
|-------|-----|-------|
| GitHub | https://github.com/CopilotKit/CopilotKit | Source code, examples |
| Docs | https://docs.copilotkit.ai/ | Pełna dokumentacja |
| Generative UI | https://www.copilotkit.ai/generative-ui | Typy UI, patterns |
| MCP Apps | https://docs.copilotkit.ai/generative-ui-specs/mcp-apps | Integracja MCP |
| LangGraph | https://docs.copilotkit.ai/coagents/langgraph | Agent orchestration |
| Hooks Reference | https://docs.copilotkit.ai/reference/hooks/useCopilotAction | Tool rendering |

---

## 9. Kolejne kroki (priorytetyzowane)

### Faza 1: Pipeline danych (TERAZ)
- [ ] `01_convert_pog.py` - POG GML → GeoPackage
- [ ] `02_filter_parcels.py` - 225k działek Trójmiasta
- [ ] `03_filter_bdot10k.py` - priorytetowe warstwy
- [ ] `04_spatial_join_pog.py` - działki + POG
- [ ] `05_compute_distances.py` - odległości do POI
- [ ] `06_compute_scores.py` - wskaźniki jakościowe
- [ ] `07_generate_embeddings.py` - 32-dim universal
- [ ] `08_import_postgis.py` - PostGIS z indeksami
- [ ] `09_import_neo4j.py` - Graf + Vector Index
- [ ] `10_prepare_lidar.py` - COPC dla Potree

### Faza 2: Agent MVP
- [ ] Struktura projektu (wg Software 3.0 lesson 2.4)
- [ ] Memory schemas (7 warstw)
- [ ] Workflow State Machine
- [ ] Tools implementation
- [ ] SGR patterns (Cascade, Routing)
- [ ] Tech UI (Gradio)

### Faza 3: Frontend + Generative UI (CopilotKit)
- [ ] Integracja CopilotKit (Generative UI framework)
- [ ] Tool renderers dla search_parcels, present_parcel
- [ ] Komponent prezentacji działki (ParcelCard, ParcelPresentation)
- [ ] Integracja Potree 3D jako komponent
- [ ] Mapa Leaflet z warstwami
- [ ] Human-in-the-Loop dla feedbacku i lead capture

### Faza 4: Monetyzacja
- [ ] Lead capture flow
- [ ] Stripe integration
- [ ] Credit system

---

## 10. Weryfikacja sukcesu

### Po pipeline danych

```bash
# PostGIS
psql -d moja_dzialka -c "SELECT COUNT(*) FROM parcels;"
# Oczekiwane: ~225,000

psql -d moja_dzialka -c "SELECT COUNT(*) FROM parcels WHERE pog_symbol IS NOT NULL;"
# Oczekiwane: >200,000 (większość ma POG)

# Neo4j
MATCH (d:Dzialka) RETURN COUNT(d);
# Oczekiwane: ~225,000

MATCH (d:Dzialka)-[:MA_CISZE]->(:KategoriaCiszy {poziom: 'bardzo_cicha'}) RETURN COUNT(d);
# Oczekiwane: ~20,000-40,000
```

### Po agencie MVP

```bash
# Test konwersacji
User: "Szukam działki pod dom w Gdańsku, ważna cisza i las"
Agent: [poprawnie identyfikuje preferencje, wykonuje search, prezentuje z opisem]

# Test feedbacku
User: "Ta jest za mała"
Agent: [zapisuje feedback, modyfikuje kryteria, szuka dalej]
```

---

## 11. Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|--------|-----------|
| POG GML parsing | Testy na małym samplu, fallback do ogr2ogr |
| Wydajność spatial join | Indeksy GIST, chunking |
| Jakość embeddingów | A/B testing z różnymi wagami |
| LLM halucynacje | SGR + walidacja odpowiedzi |
| Koszty LLM | Cache, mniejszy model dla prostych zadań |
