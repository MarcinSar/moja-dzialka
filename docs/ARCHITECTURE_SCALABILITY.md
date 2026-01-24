# Architektura skalowalności - od MVP do całej Polski

**Data:** 2026-01-22
**Cel:** Zaprojektować system który skaluje się od Trójmiasta (225k) do Polski (~30M działek)

---

## 1. Skala problemu

| Faza | Region | Działki | POG strefy | BDOT10k obiektów |
|------|--------|---------|------------|------------------|
| **MVP** | Trójmiasto | ~225k | ~11k | ~500k |
| **Faza 2** | Pomorskie | ~1.3M | ~50k | ~3.7M |
| **Faza 3** | 3-4 województwa | ~5M | ~200k | ~15M |
| **Docelowo** | Polska | ~30M | ~1M+ | ~100M+ |

---

## 2. Analiza komponentów pod kątem skali

### 2.1 Milvus (Vector DB)

| Skala | Wektory | RAM potrzebny | Czas query | Status |
|-------|---------|---------------|------------|--------|
| 225k | 225k × 32 × 4B = 28 MB | ~500 MB | <10ms | OK |
| 1.3M | 1.3M × 32 × 4B = 166 MB | ~2 GB | <20ms | OK |
| 30M | 30M × 32 × 4B = 3.8 GB | ~20 GB | <50ms | **Wymaga shardingu** |

**Wniosek:** Milvus skaluje się dobrze do ~10M wektorów na jednym serwerze. Powyżej potrzebny sharding.

**Rozwiązanie dla skali:**
```
Milvus Cluster:
├── Shard 1: Pomorskie (1.3M)
├── Shard 2: Mazowieckie (3M)
├── Shard 3: Śląskie (2M)
└── ... (16 shardów = 16 województw)
```

### 2.2 Neo4j (Graph DB)

| Skala | Węzły | Relacje | RAM | Status |
|-------|-------|---------|-----|--------|
| 225k działek | ~250k | ~2M | 4 GB | OK |
| 1.3M działek | ~1.5M | ~15M | 16 GB | OK |
| 30M działek | ~35M | ~300M | **100+ GB** | **Wymaga shardingu** |

**Wniosek:** Neo4j Community Edition ma limit. Enterprise lub sharding wymagany.

**Rozwiązanie dla skali:**
- **Neo4j Fabric** - federacja wielu baz
- **Lub:** Osobna baza per województwo + routing

### 2.3 PostGIS

| Skala | Rekordy | Storage | Query time | Status |
|-------|---------|---------|------------|--------|
| 225k | 225k | ~500 MB | <100ms | OK |
| 1.3M | 1.3M | ~3 GB | <200ms | OK |
| 30M | 30M | ~70 GB | <500ms | OK z indeksami |

**Wniosek:** PostGIS skaluje się najlepiej. Spatial indeksy (GIST) są bardzo wydajne.

**Optymalizacje dla skali:**
- Partycjonowanie po województwie
- Materialized views dla często używanych zapytań
- Connection pooling (PgBouncer)

---

## 3. Architektura multi-region

### 3.1 Podejście 1: Sharded databases (rekomendowane)

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│  "Użytkownik szuka w Gdańsku" → route to Pomorskie shard    │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  POMORSKIE  │  │ MAZOWIECKIE │  │   ŚLĄSKIE   │
│  ─────────  │  │  ─────────  │  │  ─────────  │
│  PostGIS    │  │  PostGIS    │  │  PostGIS    │
│  Neo4j      │  │  Neo4j      │  │  Neo4j      │
│  Milvus     │  │  Milvus     │  │  Milvus     │
│  1.3M dział.│  │  3M dział.  │  │  2M dział.  │
└─────────────┘  └─────────────┘  └─────────────┘
```

**Zalety:**
- Niezależne skalowanie regionów
- Izolacja błędów
- Łatwe dodawanie nowych regionów

**Wady:**
- Złożoność operacyjna
- Cross-region queries trudne

### 3.2 Podejście 2: Single DB z partycjonowaniem

```
┌─────────────────────────────────────────────────────────────┐
│                      SINGLE CLUSTER                          │
│  ─────────────────────────────────────────────────────────  │
│  PostGIS: parcels PARTITION BY LIST (wojewodztwo)           │
│  Milvus: collection per województwo                          │
│  Neo4j: labels per województwo                               │
└─────────────────────────────────────────────────────────────┘
```

**Zalety:**
- Prostsza architektura
- Cross-region queries łatwe

**Wady:**
- Single point of failure
- Trudniejsze skalowanie

### 3.3 Podejście 3: Multi-agent (dla bardzo dużej skali)

```
┌─────────────────────────────────────────────────────────────┐
│                   MASTER ORCHESTRATOR                        │
│  1. Zrozum intencję użytkownika                             │
│  2. Określ region(y) do przeszukania                        │
│  3. Deleguj do regional agents                              │
│  4. Agreguj wyniki                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   AGENT     │  │   AGENT     │  │   AGENT     │
│  POMORSKIE  │  │ MAZOWIECKIE │  │   ŚLĄSKIE   │
│  ─────────  │  │  ─────────  │  │  ─────────  │
│  Własne     │  │  Własne     │  │  Własne     │
│  narzędzia  │  │  narzędzia  │  │  narzędzia  │
│  Własna     │  │  Własna     │  │  Własna     │
│  wiedza     │  │  wiedza     │  │  wiedza     │
└─────────────┘  └─────────────┘  └─────────────┘
```

**Kiedy multi-agent ma sens:**
- Różne regiony mają różne dane (np. POG vs MPZP)
- Potrzebna specjalizacja (agent "zna" lokalny rynek)
- Równoległe przetwarzanie zapytań

**Kiedy multi-agent to overkill:**
- Dane są jednolite
- Query routing wystarczy
- Prostota > wydajność

---

## 4. Rekomendowana architektura

### Faza MVP (teraz): Single instance, partitioned by design

```python
# Już teraz projektujemy z myślą o partycjonowaniu

# PostGIS
CREATE TABLE parcels (
    id_dzialki TEXT PRIMARY KEY,
    wojewodztwo TEXT NOT NULL,  # <-- klucz partycjonowania
    ...
) PARTITION BY LIST (wojewodztwo);

CREATE TABLE parcels_pomorskie PARTITION OF parcels
    FOR VALUES IN ('pomorskie');

# Milvus
# Osobna kolekcja per województwo
collection_pomorskie = Collection("parcels_pomorskie")
collection_mazowieckie = Collection("parcels_mazowieckie")

# Neo4j
# Label per województwo
(:Dzialka:Pomorskie {id: "..."})
(:Dzialka:Mazowieckie {id: "..."})
```

### Faza 2-3: Dodawanie regionów

```python
# Router w backend
def route_query(query):
    region = extract_region(query)  # "Szukam w Gdańsku" → "pomorskie"

    if region:
        return query_single_region(region, query)
    else:
        # Cross-region search
        return query_all_regions(query)
```

### Faza docelowa: Sharding lub multi-agent

```python
# Decyzja na podstawie:
# 1. Czy dane są jednolite? → Sharding
# 2. Czy regiony mają różną logikę? → Multi-agent
# 3. Czy potrzebne cross-region? → Fabric/Federation
```

---

## 5. Embedding strategy dla skali

### 5.1 Problem: Różne regiony, różne embeddingi?

**Pytanie:** Czy embedding wytrenowany na Trójmieście będzie działał w Warszawie?

**Odpowiedź:** TAK, jeśli:
- Cechy są znormalizowane (0-1)
- Semantyka jest ta sama (dist_to_forest znaczy to samo wszędzie)
- Nie używamy region-specific features (one-hot gmina → problem!)

### 5.2 Rozwiązanie: Universal embedding schema

```python
# NIE RÓB TEGO (nie skaluje się):
embedding = [
    ...,
    one_hot_gmina(gmina, all_gminy_in_poland),  # 2500 gmin = 2500 dim!
]

# RÓB TO (skaluje się):
embedding = [
    ...,
    # Zamiast one-hot gminy, użyj cech gminy:
    gmina_population_density,  # 0-1
    gmina_urbanization_level,  # 0-1
    gmina_avg_parcel_price,    # 0-1 (jeśli dostępne)
]
```

### 5.3 Hierarchical embeddings (dla bardzo dużej skali)

```
Poziom 1: Region embedding (województwo) - 8 dim
Poziom 2: Subregion embedding (powiat) - 8 dim
Poziom 3: Parcel embedding - 32 dim

Query:
1. Znajdź podobne regiony (fast, 16 województw)
2. W tych regionach znajdź podobne powiaty (fast, ~50 powiatów)
3. W tych powiatach znajdź podobne działki (slower, ~100k działek)
```

---

## 6. Agent architecture dla skali

### 6.1 Single agent z region-aware tools (MVP → Faza 2)

```python
# Agent ma dostęp do wszystkich regionów przez tools

tools = [
    search_parcels(region=None),  # Jeśli region=None, pytaj użytkownika
    get_region_info(region),      # Info o dostępnych danych w regionie
    ...
]

# System prompt
"""
Masz dostęp do danych z następujących regionów:
- Pomorskie (1.3M działek, pełne dane POG)
- Mazowieckie (3M działek, częściowe dane POG)
- ...

Zawsze najpierw ustal w jakim regionie użytkownik szuka.
"""
```

### 6.2 Multi-agent orchestration (Faza docelowa, jeśli potrzebne)

```python
# Master orchestrator
class MasterOrchestrator:
    def __init__(self):
        self.regional_agents = {
            'pomorskie': PomorskieAgent(),
            'mazowieckie': MazowieckieAgent(),
            ...
        }

    def process(self, user_query):
        # 1. Intent classification
        intent = classify_intent(user_query)

        # 2. Region detection
        regions = detect_regions(user_query)

        if len(regions) == 1:
            # Single region - delegate
            return self.regional_agents[regions[0]].process(user_query)
        elif len(regions) > 1:
            # Multi-region - parallel + aggregate
            results = parallel([
                agent.process(user_query)
                for region, agent in self.regional_agents.items()
                if region in regions
            ])
            return aggregate_results(results)
        else:
            # No region specified - ask user
            return "W jakim regionie szukasz działki?"
```

### 6.3 Kiedy multi-agent się opłaca

| Scenariusz | Single agent | Multi-agent |
|------------|--------------|-------------|
| 1-3 regiony | ✅ | Overkill |
| 5-10 regionów | ✅ (z routingiem) | Opcjonalne |
| 16 województw | ⚠️ (długi context) | ✅ |
| Różne dane per region | ⚠️ | ✅ |
| Różna logika per region | ❌ | ✅ |

---

## 7. Data pipeline dla skali

### 7.1 Modularny pipeline

```
data/
├── raw/
│   ├── pomorskie/
│   │   ├── pog/
│   │   ├── bdot10k/
│   │   └── dzialki/
│   ├── mazowieckie/
│   │   └── ...
│   └── ...
├── processed/
│   ├── pomorskie/
│   │   ├── parcels_features.parquet
│   │   └── embeddings.npy
│   └── ...
└── scripts/
    └── pipeline/
        ├── process_region.py  # Uniwersalny skrypt
        └── config/
            ├── pomorskie.yaml
            └── mazowieckie.yaml
```

### 7.2 Uniwersalny skrypt per region

```python
# scripts/pipeline/process_region.py

def process_region(config_path):
    config = load_config(config_path)

    # 1. Load raw data
    parcels = load_parcels(config['parcels_path'])
    pog = load_pog(config['pog_path'])
    bdot10k = load_bdot10k(config['bdot10k_path'])

    # 2. Feature engineering (identyczny dla wszystkich regionów)
    parcels = compute_features(parcels, pog, bdot10k)

    # 3. Generate embeddings (identyczny schemat)
    embeddings = generate_embeddings(parcels)

    # 4. Save
    save_processed(parcels, embeddings, config['output_path'])

    # 5. Import to DBs
    import_to_postgis(parcels, region=config['region_name'])
    import_to_neo4j(parcels, region=config['region_name'])
    import_to_milvus(embeddings, collection=f"parcels_{config['region_name']}")

# Uruchomienie:
# python process_region.py --config config/pomorskie.yaml
# python process_region.py --config config/mazowieckie.yaml
```

---

## 8. Checklist: Co projektować od początku

### Musi być od MVP:

- [x] **Partycjonowanie** - kolumna `wojewodztwo` wszędzie
- [x] **Universal embedding schema** - bez region-specific one-hot
- [x] **Modularny pipeline** - jeden skrypt per region
- [x] **Region-aware API** - `region` parametr w endpointach

### Można dodać później:

- [ ] Sharding baz danych
- [ ] Multi-agent orchestration
- [ ] Cross-region search
- [ ] Region-specific agents

### NIE rób teraz (premature optimization):

- ❌ Kubernetes cluster
- ❌ Multi-datacenter deployment
- ❌ Real-time embeddings update
- ❌ Complex caching layer

---

## 9. Podsumowanie

| Aspekt | MVP (teraz) | Skala (później) |
|--------|-------------|-----------------|
| **Bazy** | Single instance, partycjonowane | Sharded lub federated |
| **Agent** | Single agent z region tools | Multi-agent jeśli potrzebne |
| **Embeddings** | 32-dim universal schema | Bez zmian |
| **Pipeline** | Modularny per region | Bez zmian |
| **Routing** | W kodzie aplikacji | Load balancer + routing |

**Kluczowa zasada:** Projektuj struktury danych i embeddingi tak, żeby były universal. Skalowanie infrastruktury można zrobić później.
