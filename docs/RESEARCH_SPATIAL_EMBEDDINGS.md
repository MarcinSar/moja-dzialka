# Research: SRAI i Embeddingi Przestrzenne

**Data:** 2026-01-22
**Cel:** Zrozumienie jak wykorzystać embeddingi przestrzenne w systemie rekomendacji działek

---

## Executive Summary

Embeddingi przestrzenne transformują lokalizację i jej kontekst w wektory numeryczne, umożliwiając:
- **Similarity search** - "znajdź działki podobne do tej"
- **Profile matching** - "znajdź działki pasujące do preferencji"
- **Semantic understanding** - "cicha okolica" → wektor → wyszukiwanie

**Kluczowe wnioski z researchu:**
1. **Kontekst przestrzenny** jest ważniejszy niż sama lokalizacja (X, Y)
2. **Feature engineering** z domain knowledge (POG, BDOT10k) > generic embeddings
3. **Hybrid approach** (feature-based + contextual) daje najlepsze wyniki
4. **Wymiar 32-64** jest optymalny dla ~225k działek

---

## 1. SRAI (Spatial Representations for AI)

### 1.1 Architektura biblioteki

SRAI implementuje 4-komponentowy pipeline:

```
Loader (dane) → Regionalizer (regiony) → Joiner (mapping) → Embedder (wektory)
```

### 1.2 Dostępne embeddery

| Embedder | Opis | Wymiar | Kiedy używać |
|----------|------|--------|--------------|
| **CountEmbedder** | Liczy features w regionie | ~kategorii | Baseline, szybki |
| **ContextualCountEmbedder** | + sąsiedztwo | ~kategorii | Gdy sąsiedztwo ważne |
| **Hex2VecEmbedder** | Pre-trained na OSM | 64-128 | Generic, szybki start |
| **GTFS2VecEmbedder** | Transport publiczny | 64 | Gdy GTFS dostępne |
| **Highway2VecEmbedder** | Sieci drogowe | 64 | Analiza dostępności |

### 1.3 Regiony

| Typ | Opis | Dla projektu |
|-----|------|--------------|
| **H3 hexagons** | Hierarchiczne sześciokąty Ubera | Uniwersalne, ale tracą kształt działki |
| **Custom regions** | Własne geometrie (działki!) | **REKOMENDOWANE** - zachowuje granice |
| **Administrative** | Granice admin (gminy) | Do agregacji |

**Kluczowe:** Można użyć działek jako "natural regions" zamiast H3!

```python
from srai.utils import convert_to_regions_gdf
regions = convert_to_regions_gdf(dzialki)  # działki jako regiony
```

### 1.4 Sąsiedztwo (Neighbourhood)

**AdjacencyNeighbourhood** - sąsiedztwo oparte na styku geometrii.

Dla działek: sąsiedzi = działki dzielące granicę.

```python
from srai.neighbourhoods import AdjacencyNeighbourhood
neighbourhood = AdjacencyNeighbourhood(dzialki)
# Automatycznie znajduje sąsiadów
```

---

## 2. Porównanie podejść do embeddingów

### 2.1 Feature-based (dotychczasowe podejście)

**Metoda:** Znormalizowane cechy numeryczne → wektor

```python
features = [
    area_m2,           # powierzchnia
    dist_to_forest,    # odległość do lasu
    dist_to_school,    # odległość do szkoły
    quietness_score,   # wskaźnik ciszy
    ...                # ~20 cech
]
embedding = normalize(features)  # 20-64 dim
```

**Zalety:**
- Pełna kontrola nad cechami
- Interpretowalność (wiemy co oznacza każdy wymiar)
- Szybkie obliczenia

**Wady:**
- Wymaga ręcznego feature engineering
- Nie uwzględnia kontekstu przestrzennego automatycznie

### 2.2 SRAI Contextual (ContextualCountEmbedder)

**Metoda:** Agregacja features z BDOT10k + kontekst sąsiedztwa

```python
# Joiner mapuje BDOT10k features na działki
joint = joiner.transform(dzialki, bdot10k_features)

# Embedder liczy + dodaje kontekst sąsiadów
embedder = ContextualCountEmbedder(neighbourhood=neighbourhood)
embeddings = embedder.transform(dzialki, bdot10k, joint)
# ~260 wymiarów (1 na kategorię BDOT10k)
```

**Zalety:**
- Automatycznie uwzględnia sąsiedztwo
- Bogaty kontekst z BDOT10k (70+ kategorii)
- Semantic understanding (typ terenu)

**Wady:**
- Duży wymiar (wymaga PCA)
- Mniej interpretowalne
- Wolniejsze obliczenia

### 2.3 Hex2Vec (pre-trained)

**Metoda:** Transfer learning z modelu trenowanego na OSM

```python
from srai.embedders import Hex2VecEmbedder
embedder = Hex2VecEmbedder()
embeddings = embedder.transform(h3_regions, osm_features, joint)
# 64-128 wymiarów
```

**Zalety:**
- Gotowy model, szybki start
- Semantic knowledge z OSM
- Działa globalnie

**Wady:**
- Nie zna POG (domain-specific)
- Wymaga H3 regionów (nie działek)
- Black box

### 2.4 Hybrid (rekomendowane)

**Metoda:** Kombinacja feature-based + contextual

```python
feature_emb = create_feature_embedding(parcel)  # 32 dim
context_emb = create_contextual_embedding(parcel)  # 32 dim

# Weighted combination
combined = concat([
    0.6 * feature_emb,  # domain knowledge (POG, wskaźniki)
    0.4 * context_emb   # spatial context (BDOT10k)
])
# 64 dim total
```

**Zalety:**
- Domain knowledge + spatial context
- Balans między interpretowalnością a bogactwem
- Elastyczność w wagach

---

## 3. Jakie dane do jakich zastosowań

### 3.1 Similarity search ("znajdź podobne")

**Cel:** Użytkownik wskazuje działkę → system znajduje podobne

**Kluczowe cechy:**
- Powierzchnia (area_m2)
- Typ terenu (charakter: wiejski/miejski)
- Otoczenie (% lasu, wody, zabudowy w bufferze)
- Parametry POG (symbol, intensywność, wysokość)

**Wagi:** Wszystkie równe, cosine similarity

### 3.2 Profile matching ("znajdź pasujące do preferencji")

**Cel:** Użytkownik opisuje preferencje → system tworzy "idealny" wektor

**Kluczowe cechy dla różnych profili:**

| Profil użytkownika | Kluczowe cechy | Waga |
|-------------------|----------------|------|
| "Cicha okolica" | dist_to_industrial, quietness_score | HIGH |
| "Blisko natury" | dist_to_forest, dist_to_water, nature_score | HIGH |
| "Dobra komunikacja" | dist_to_bus_stop, dist_to_main_road | HIGH |
| "Pod dom jednorodzinny" | area_m2 (800-1500), pog_symbol (SJ) | HIGH |
| "Blisko szkoły" | dist_to_school | HIGH |

**Implementacja:** Query embedding z preferencji

```python
def create_query_embedding(preferences):
    # Bazowy wektor (średnie wartości)
    query = default_embedding.copy()

    # Modyfikuj na podstawie preferencji
    if preferences.get('quiet'):
        query['quietness_score'] = 1.0  # max
        query['dist_to_industrial'] = 1.0  # daleko = dobrze

    if preferences.get('near_forest'):
        query['dist_to_forest'] = 0.0  # blisko = dobrze (inverse)
        query['nature_score'] = 1.0

    return normalize(query)
```

### 3.3 Ranking z wyjaśnieniem

**Cel:** Nie tylko znaleźć, ale wyjaśnić DLACZEGO

**Kluczowe:** Interpretowalne cechy

```python
def explain_match(parcel, preferences):
    explanations = []

    if preferences.get('quiet') and parcel['quietness_score'] > 80:
        explanations.append(f"Cisza: {parcel['quietness_score']}/100")

    if preferences.get('near_forest') and parcel['dist_to_forest'] < 300:
        explanations.append(f"Las w {parcel['dist_to_forest']}m")

    return explanations
```

**Wniosek:** Feature-based embeddingi są lepsze do wyjaśnień niż black-box SRAI

---

## 4. Rekomendowana architektura embeddingów

### 4.1 Struktura wektora (32 dim) - SKALOWALNA

**UWAGA:** Struktura musi być uniwersalna dla całej Polski, bez region-specific one-hot!

```
Embedding (32 wymiary):
├── [0-5]   Cechy podstawowe (6 dim)
│   ├── area_m2 (log-normalized)
│   ├── compactness
│   ├── urbanization_level (0-1, z gęstości zabudowy)
│   ├── terrain_diversity (Shannon entropy pokrycia terenu)
│   ├── elevation_normalized (jeśli dostępne, 0-1)
│   └── parcel_shape_regularity (0-1)
│
├── [6-13]  Odległości (8 dim, inverse log)
│   ├── dist_to_forest
│   ├── dist_to_water
│   ├── dist_to_school
│   ├── dist_to_bus_stop
│   ├── dist_to_shop
│   ├── dist_to_hospital
│   ├── dist_to_main_road
│   └── dist_to_industrial
│
├── [14-19] Bufory 500m (6 dim)
│   ├── pct_forest_500m
│   ├── pct_water_500m
│   ├── pct_builtup_500m
│   ├── count_buildings_500m (log)
│   ├── building_density_500m (budynki/ha)
│   └── poi_diversity_500m (Shannon entropy typów POI)
│
├── [20-27] POG/Planowanie parametry (8 dim)
│   ├── pog_max_intensywnosc (0-1, scaled 0-4)
│   ├── pog_max_zabudowa_pct (0-1)
│   ├── pog_max_wysokosc (log, 0-1)
│   ├── pog_min_bio_pct (0-1)
│   ├── is_buildable (0/1)
│   ├── is_residential_allowed (0/1)
│   ├── is_commercial_allowed (0/1)
│   └── planning_restrictiveness (composite 0-1)
│
└── [28-31] Wskaźniki kompozytowe (4 dim)
    ├── quietness_score (0-1)
    ├── nature_score (0-1)
    ├── accessibility_score (0-1)
    └── infrastructure_score (0-1)
```

**Kluczowe dla skalowalności:**
- ❌ NIE używamy one-hot dla gminy/powiatu/województwa
- ✅ Używamy cech OPISUJĄCYCH lokalizację (urbanization, density)
- ✅ Wszystkie wartości znormalizowane 0-1
- ✅ Semantyka identyczna w każdym regionie Polski

### 4.2 Normalizacja

```python
def normalize_feature(value, feature_type):
    if feature_type == 'distance':
        # Inverse log: bliżej = wyższa wartość
        # 0m → 1.0, 5000m → 0.0
        return 1 - min(log(value + 1) / log(5001), 1.0)

    elif feature_type == 'area':
        # Log scale: 100m² → 0.0, 10000m² → 1.0
        return min(log(value) / log(10000), 1.0)

    elif feature_type == 'percentage':
        # Already 0-100, just scale
        return value / 100

    elif feature_type == 'count':
        # Log scale
        return min(log(value + 1) / log(1000), 1.0)

    elif feature_type == 'score':
        # Already 0-100
        return value / 100
```

### 4.3 Dlaczego 32 a nie 64?

- **225k działek** → optymalne d = 10 * log10(225000) ≈ 54
- **32 jest wystarczające** dla naszych ~25 cech
- **Szybsze** zapytania w Milvus
- **Mniej overfitting** przy mniejszej ilości danych

---

## 5. Wykorzystanie SRAI Contextual jako dodatek

### 5.1 Kiedy SRAI contextual jest wartościowe

1. **Gdy brakuje explicit features** - SRAI automatycznie wyciąga
2. **Dla sąsiedztwa** - "co jest obok" (nie tylko odległość)
3. **Dla typu terenu** - urban/rural/mixed z BDOT10k kategorii

### 5.2 Jak połączyć z feature-based

**Opcja 1: Concatenation (rekomendowane)**
```python
feature_emb = create_feature_embedding(parcel)  # 24 dim
srai_emb = create_srai_embedding(parcel)  # 8 dim (PCA z ~260)
combined = concat([feature_emb, srai_emb])  # 32 dim
```

**Opcja 2: Weighted sum**
```python
combined = 0.7 * feature_emb + 0.3 * srai_emb
```

**Opcja 3: Late fusion (search time)**
```python
feature_results = milvus.search(feature_query, top_k=50)
srai_results = milvus.search(srai_query, top_k=50)
final = rrf_fusion(feature_results, srai_results)
```

### 5.3 SRAI features do wykorzystania

Z BDOT10k możemy wyciągnąć automatycznie:
- Liczba budynków mieszkalnych (BUBD_A, funkcja=mieszkalne)
- Liczba budynków przemysłowych
- Długość dróg w bufferze
- Liczba przystanków
- Powierzchnia lasów/wód

Te features są już częściowo w naszym feature engineering, ale SRAI doda:
- **Proporcje typów** (% mieszkalnych vs gospodarczych)
- **Diversyfikację** (Shannon entropy kategorii)
- **Kontekst sąsiedztwa** (co mają sąsiednie działki)

---

## 6. Implementacja dla projektu

### 6.1 Pipeline generowania embeddingów

```python
# scripts/pipeline/07_generate_embeddings.py

def generate_embeddings(parcels_gdf, bdot10k_layers, pog_gdf):
    """
    Generuje 32-dim embeddingi dla działek.
    """
    embeddings = []

    for parcel in parcels_gdf.itertuples():
        emb = []

        # 1. Cechy podstawowe (8 dim)
        emb.extend(encode_basic_features(parcel))

        # 2. Odległości (8 dim)
        emb.extend(encode_distances(parcel))

        # 3. Bufory (6 dim)
        emb.extend(encode_buffers(parcel))

        # 4. POG (6 dim)
        emb.extend(encode_pog(parcel))

        # 5. Wskaźniki (4 dim)
        emb.extend(encode_scores(parcel))

        embeddings.append(emb)

    embeddings = np.array(embeddings, dtype=np.float32)

    # Normalizacja na unit vectors
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    return embeddings
```

### 6.2 Opcjonalny SRAI contextual

```python
def add_srai_context(parcels_gdf, bdot10k_features):
    """
    Dodaje 8-dim SRAI contextual features do embeddingu.
    """
    from srai.joiners import IntersectionJoiner
    from srai.embedders import CountEmbedder
    from srai.neighbourhoods import AdjacencyNeighbourhood

    # Join BDOT10k z działkami
    joiner = IntersectionJoiner()
    joint = joiner.transform(parcels_gdf, bdot10k_features)

    # Neighbourhood dla kontekstu
    neighbourhood = AdjacencyNeighbourhood(parcels_gdf)

    # Count embeddings z kontekstem
    embedder = ContextualCountEmbedder(
        neighbourhood=neighbourhood,
        concatenate_vectors=True
    )
    srai_emb = embedder.transform(parcels_gdf, bdot10k_features, joint)

    # PCA do 8 wymiarów
    pca = PCA(n_components=8)
    srai_emb_reduced = pca.fit_transform(srai_emb)

    return srai_emb_reduced
```

### 6.3 Indeks Milvus

```python
# Konfiguracja dla 32-dim embeddingów
collection_schema = {
    "fields": [
        {"name": "id", "type": "VARCHAR", "max_length": 50, "is_primary": True},
        {"name": "embedding", "type": "FLOAT_VECTOR", "dim": 32},
        # Metadata dla filtrowania
        {"name": "gmina", "type": "VARCHAR", "max_length": 50},
        {"name": "area_m2", "type": "FLOAT"},
        {"name": "pog_symbol", "type": "VARCHAR", "max_length": 10},
        {"name": "quietness_score", "type": "FLOAT"},
        {"name": "nature_score", "type": "FLOAT"},
    ]
}

index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",  # Szybsze dla małych wymiarów
    "params": {"M": 16, "efConstruction": 256}
}
```

---

## 7. Przypadki użycia i query patterns

### 7.1 "Znajdź działki podobne do tej"

```python
def find_similar(parcel_id, top_k=10):
    # Pobierz embedding działki
    parcel_emb = milvus.get(parcel_id)

    # Vector search
    results = milvus.search(
        parcel_emb,
        top_k=top_k,
        metric="COSINE"
    )

    return results
```

### 7.2 "Znajdź działki dla preferencji"

```python
def find_by_preferences(preferences, top_k=10):
    # Stwórz query embedding z preferencji
    query_emb = create_query_embedding(preferences)

    # Vector search z filtrami
    filter_expr = build_filter(preferences)  # np. "area_m2 >= 800"

    results = milvus.search(
        query_emb,
        top_k=top_k,
        filter=filter_expr,
        metric="COSINE"
    )

    return results
```

### 7.3 "Hybrydowe wyszukiwanie"

```python
def hybrid_search(preferences, location=None, top_k=10):
    # 1. Vector search (Milvus)
    query_emb = create_query_embedding(preferences)
    vector_results = milvus.search(query_emb, top_k=50)

    # 2. Graph search (Neo4j) - jeśli są kryteria kategoryczne
    if preferences.get('pog_symbol'):
        graph_results = neo4j.search_by_pog(preferences['pog_symbol'])

    # 3. Spatial search (PostGIS) - jeśli jest lokalizacja
    if location:
        spatial_results = postgis.search_nearby(location, radius=5000)

    # 4. RRF Fusion
    final = rrf_fusion([vector_results, graph_results, spatial_results])

    return final[:top_k]
```

---

## 8. Metryki jakości embeddingów

### 8.1 Intrinsic metrics

```python
def evaluate_embeddings(embeddings, labels):
    # Silhouette score - czy podobne są blisko siebie
    silhouette = silhouette_score(embeddings, labels)

    # Nearest neighbor accuracy
    nn_accuracy = evaluate_nn_accuracy(embeddings, labels)

    return {
        "silhouette": silhouette,  # -1 to 1, higher better
        "nn_accuracy": nn_accuracy  # 0 to 1
    }
```

### 8.2 Extrinsic metrics (z użytkownikami)

- **Click-through rate** na "podobne działki"
- **Mean Reciprocal Rank** dla search results
- **User satisfaction** (surveys)

---

## 9. Rekomendacje końcowe

### Co zrobić teraz:

1. **Użyć 32-dim feature-based embeddingów** jako bazę
   - Pełna kontrola
   - Interpretowalność
   - Szybkie obliczenia

2. **Dodać SRAI contextual jako opcję** (8 dim)
   - Dla "sąsiedztwa" i "charakteru terenu"
   - PCA z CountEmbedder na BDOT10k

3. **Zaimplementować query embedding z preferencji**
   - Mapping: "cicha okolica" → wysokie quietness_score
   - Normalizacja do unit vector

4. **HNSW index w Milvus** dla 32-dim
   - Szybsze niż IVF_FLAT dla małych wymiarów

### Co odłożyć na później:

1. **Hex2Vec** - wymaga H3, tracimy kształt działki
2. **User behavior signals** - potrzebujemy danych z użycia
3. **Image embeddings** - wymaga satellite imagery

---

## 10. Źródła

1. SRAI Documentation: https://kraina-ai.github.io/srai/latest/
2. SRAI GitHub: https://github.com/kraina-ai/srai
3. Hex2Vec Paper: https://dl.acm.org/doi/10.1145/3486635.3491076
4. Multi-Resolution Geo-Embeddings: arXiv:2510.01196
5. NoBroker Property Embeddings: Medium engineering blog
6. Geographic Data Science: https://geographicdata.science/
