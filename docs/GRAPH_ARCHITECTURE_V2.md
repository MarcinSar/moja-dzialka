# Architektura Grafowa V2 - moja-dzialka

**Data:** 2026-01-22
**Status:** Zaprojektowana, do implementacji

---

## 1. Podsumowanie analizy

### 1.1 Co było dobrze w poprzedniej implementacji

- Dobry schemat podstawowy (14 typów węzłów, 17+ relacji)
- Hierarchiczna struktura administracyjna (Gmina → Dzielnica → Działka)
- Pattern Human-in-the-Loop w niektórych narzędziach
- Oddzielenie warstw (PostGIS dla spatial, Neo4j dla grafu)

### 1.2 Co brakowało / było problematyczne

1. **Brak pełnej integracji MPZP/POG** - tylko linki, bez parametrów
2. **Relacje do POI z NULL** - `BLISKO_LASU {distance: null}` dla odległych działek
3. **Brak zapytań przestrzennych w Cypher** - poleganie na PostGIS
4. **Niejasna strategia hybrid search** - jak łączyć graf + vector + spatial
5. **Brak Lexical Graph** - dokumenty POG nie były indeksowane
6. **Brak Entity Resolution** - encje z różnych źródeł nie były łączone

### 1.3 Kluczowe wzorce z kursu Agentic KG Construction

| Wzorzec | Opis | Zastosowanie w projekcie |
|---------|------|--------------------------|
| **Three-Graph Architecture** | Domain + Lexical + Subject graphs | POG strukturalne + dokumenty + ekstrakcja |
| **Neuro-Symbolic** | LLM planuje, rules wykonują | Agent → Cypher queries |
| **Human-in-the-Loop** | set_perceived → approve_perceived | Preferencje użytkownika |
| **Guard Patterns** | Walidacja przed operacją | Zabezpieczenie przed halucynacjami LLM |
| **Critic Pattern** | Proposer ↔ Critic iteration | Opcjonalnie dla refinement |
| **Entity Resolution** | Fuzzy matching + CORRESPONDS_TO | Łączenie nazw z dokumentów z danymi |

---

## 2. Nowa architektura: Three-Graph dla moja-dzialka

### 2.1 Przegląd

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE GRAPH - MOJA-DZIALKA                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        DOMAIN GRAPH                                      │    │
│  │                 (Dane strukturalne - PostGIS/CSV)                        │    │
│  │                                                                          │    │
│  │   (Gmina)──► (Dzielnica)──► (Dzialka)──► (StrefaPOG)──► (ProfilFunkcji) │    │
│  │                               │                                          │    │
│  │                               └──► (KategoriaCiszy, KategoriaNatury...)  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                              ▲                                                   │
│                              │ CORRESPONDS_TO                                    │
│                              │                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        SUBJECT GRAPH                                     │    │
│  │                 (Encje wyekstrahowane przez LLM)                         │    │
│  │                                                                          │    │
│  │   (Miejscowosc:__Entity__)──► (Dzielnica)  [Entity Resolution]          │    │
│  │   (Strefa:__Entity__)──► (StrefaPOG)       [Fuzzy matching]             │    │
│  │   (Parametr:__Entity__)──► parametry zabudowy                           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                              ▲                                                   │
│                              │ FROM_CHUNK                                        │
│                              │                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        LEXICAL GRAPH                                     │    │
│  │                 (Dokumenty POG → Chunks z embeddingami)                  │    │
│  │                                                                          │    │
│  │   (Document)──FIRST_CHUNK──►(Chunk)──NEXT_CHUNK──►(Chunk)──► ...        │    │
│  │      │                         │                     │                   │    │
│  │   path: pog/gdansk/...       embedding: [...]      embedding: [...]      │    │
│  │   title: "POG Gdańsk"                                                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Rola każdego grafu

| Graf | Źródło danych | Cel | Query pattern |
|------|---------------|-----|---------------|
| **Domain Graph** | CSV/GeoPackage (strukturalne) | Deterministyczne wyszukiwanie | Cypher patterns |
| **Lexical Graph** | Dokumenty POG (GML + PDF) | Semantic search + RAG | Vector similarity |
| **Subject Graph** | LLM extraction z dokumentów | Łączenie tekstu z danymi | Entity resolution |

---

## 3. Domain Graph - Szczegółowy schemat

### 3.1 Węzły (12 typów)

```cypher
// ═══════════════════════════════════════════════════════════════════════════
// LOKALIZACJA (3 typy)
// ═══════════════════════════════════════════════════════════════════════════

(:Gmina {
  nazwa: "Gdańsk",
  teryt: "2261",
  wojewodztwo: "pomorskie"
})

(:Dzielnica {
  nazwa: "Oliwa",
  gmina: "Gdańsk"
})

(:Miejscowosc {
  nazwa: "Kolbudy",
  typ: "wieś",  // miasto, wieś, osada
  gmina: "Kolbudy"
})

// ═══════════════════════════════════════════════════════════════════════════
// DZIAŁKA (główny obiekt)
// ═══════════════════════════════════════════════════════════════════════════

(:Dzialka {
  id: "226301_1.0012.152/5",  // PRIMARY KEY
  area_m2: 1718.52,
  centroid_lat: 54.3542,
  centroid_lon: 18.6423,

  // Wskaźniki kompozytowe (0-100)
  quietness_score: 85,
  nature_score: 72,
  accessibility_score: 68
})

// ═══════════════════════════════════════════════════════════════════════════
// POG - STREFY PLANISTYCZNE (2 typy)
// ═══════════════════════════════════════════════════════════════════════════

(:StrefaPOG {
  id: "1POG-838SW",
  symbol: "SW",
  nazwa: "strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną",

  // Parametry zabudowy
  max_intensywnosc: 1.5,
  max_zabudowa_pct: 40.0,
  max_wysokosc: 19.0,
  min_bio_pct: 30.0
})

(:ProfilFunkcji {
  kod: "MN",
  nazwa: "teren zabudowy mieszkaniowej jednorodzinnej",
  typ: "podstawowy"  // podstawowy | dodatkowy
})

// ═══════════════════════════════════════════════════════════════════════════
// KATEGORIE JAKOŚCIOWE (4 typy)
// ═══════════════════════════════════════════════════════════════════════════

(:KategoriaCiszy {
  poziom: "bardzo_cicha",  // bardzo_cicha, cicha, umiarkowana, glosna
  opis: "Daleko od ruchu i przemysłu (>2km)"
})

(:KategoriaNatury {
  poziom: "zielona",  // bardzo_zielona, zielona, umiarkowana, zurbanizowana
  opis: "Las lub woda w zasięgu 500m"
})

(:KategoriaDostepnosci {
  poziom: "doskonala",  // doskonala, dobra, umiarkowana, ograniczona
  opis: "Szkoła i przystanek w zasięgu 1km"
})

(:KlasaPowierzchni {
  klasa: "pod_dom",  // mala(<500), pod_dom(500-1500), duza(1500-5000), bardzo_duza(>5000)
  zakres: "500-1500 m²"
})

// ═══════════════════════════════════════════════════════════════════════════
// TYP ZABUDOWY (dla filtrowania)
// ═══════════════════════════════════════════════════════════════════════════

(:TypZabudowy {
  typ: "jednorodzinna",  // jednorodzinna, wielorodzinna, uslugowa, mieszana, brak
  opis: "Budynek mieszkalny jednorodzinny"
})
```

### 3.2 Relacje (11 typów)

```cypher
// ═══════════════════════════════════════════════════════════════════════════
// LOKALIZACJA
// ═══════════════════════════════════════════════════════════════════════════

(:Dzialka)-[:W_GMINIE]->(:Gmina)
(:Dzialka)-[:W_DZIELNICY]->(:Dzielnica)
(:Dzialka)-[:W_MIEJSCOWOSCI]->(:Miejscowosc)
(:Dzielnica)-[:NALEZY_DO]->(:Gmina)
(:Miejscowosc)-[:NALEZY_DO]->(:Gmina)

// ═══════════════════════════════════════════════════════════════════════════
// POG
// ═══════════════════════════════════════════════════════════════════════════

(:Dzialka)-[:W_STREFIE_POG {
  pct_overlap: 100.0  // % działki pokrytej przez strefę
}]->(:StrefaPOG)

(:StrefaPOG)-[:DOZWALA {
  typ: "podstawowy"  // podstawowy | dodatkowy
}]->(:ProfilFunkcji)

// ═══════════════════════════════════════════════════════════════════════════
// KATEGORIE
// ═══════════════════════════════════════════════════════════════════════════

(:Dzialka)-[:MA_CISZE]->(:KategoriaCiszy)
(:Dzialka)-[:MA_NATURE]->(:KategoriaNatury)
(:Dzialka)-[:MA_DOSTEPNOSC]->(:KategoriaDostepnosci)
(:Dzialka)-[:MA_POWIERZCHNIE]->(:KlasaPowierzchni)
(:Dzialka)-[:MOZNA_ZABUDOWAC]->(:TypZabudowy)
```

### 3.3 Dlaczego NIE przechowujemy odległości w relacjach

**Problem w poprzedniej implementacji:**
```cypher
// ZŁE - generuje miliony relacji z NULL dla odległych obiektów
(:Dzialka)-[:BLISKO_LASU {distance_m: 150}]->(:Las)
(:Dzialka)-[:BLISKO_LASU {distance_m: null}]->(:Las)  // dla odległych!
```

**Rozwiązanie:**
1. Odległości przechowujemy w **PostGIS** jako atrybuty działki
2. Kategorie jakościowe (ciszy, natury) w **Neo4j** jako relacje do węzłów kategorii
3. Agent używa **Cypher do filtrowania kategorii**, **PostGIS do precyzyjnych odległości**

```cypher
// DOBRE - tylko relacje które mają sens
(:Dzialka)-[:MA_NATURE]->(:KategoriaNatury {poziom: "bardzo_zielona"})
// Oznacza: las < 200m LUB woda < 300m (zdefiniowane przy kategoryzacji)
```

---

## 4. Lexical Graph - Dokumenty POG

### 4.1 Cel

Dokumenty POG (GML + uzasadnienia PDF) zawierają informacje których nie ma w danych strukturalnych:
- Uzasadnienia decyzji planistycznych
- Opis wizji rozwoju obszaru
- Wyjaśnienia ograniczeń
- Kontekst historyczny

### 4.2 Struktura

```cypher
// ═══════════════════════════════════════════════════════════════════════════
// WĘZŁY LEXICAL GRAPH
// ═══════════════════════════════════════════════════════════════════════════

(:Document {
  path: "pog/gdansk/pog-gdansk-uzasadnienie.pdf",
  title: "Uzasadnienie POG Gdańsk",
  gmina: "Gdańsk",
  type: "uzasadnienie"  // uzasadnienie, uchwala, prognoza
})

(:Chunk {
  index: 0,
  text: "Strefa SW-838 została wyznaczona z uwzględnieniem...",
  embedding: [0.023, -0.145, ...],  // 1536 dim
  document_path: "pog/gdansk/..."
})

// ═══════════════════════════════════════════════════════════════════════════
// RELACJE LEXICAL GRAPH
// ═══════════════════════════════════════════════════════════════════════════

(:Document)-[:FIRST_CHUNK]->(:Chunk)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:FROM_DOCUMENT]->(:Document)
```

### 4.3 Pipeline budowy Lexical Graph

```python
# Pseudo-kod pipeline

def build_lexical_graph(document_path: str):
    # 1. Load document
    if document_path.endswith('.pdf'):
        text = extract_text_from_pdf(document_path)
    elif document_path.endswith('.gml'):
        text = extract_descriptions_from_gml(document_path)

    # 2. Chunk text
    chunks = text_splitter.split(text, chunk_size=500, overlap=50)

    # 3. Generate embeddings
    embeddings = embedding_model.encode(chunks)

    # 4. Create graph nodes
    create_document_node(document_path)
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        create_chunk_node(chunk, embedding, i)
        if i == 0:
            create_first_chunk_relationship(document_path, chunk)
        else:
            create_next_chunk_relationship(prev_chunk, chunk)
```

---

## 5. Subject Graph - Entity Extraction

### 5.1 Cel

Wyekstrahować z dokumentów encje które można połączyć z Domain Graph:
- Nazwy dzielnic, ulic, miejscowości
- Numery stref POG
- Opisy parametrów zabudowy
- Nazwy obiektów (szkoły, parki, etc.)

### 5.2 Schemat encji do ekstrakcji

```python
approved_entities = [
    'Miejscowosc',      # "Oliwa", "Wrzeszcz", "Kolbudy"
    'Strefa',           # "SW-838", "SJ-123"
    'Obiekt',           # "Park Oliwski", "SP nr 47"
    'Parametr',         # "maksymalna wysokość 12m"
    'Ograniczenie',     # "zakaz zabudowy wielorodzinnej"
]

approved_fact_types = {
    'DOTYCZY_STREFY': {
        'subject_label': 'Chunk',
        'predicate_label': 'DOTYCZY_STREFY',
        'object_label': 'Strefa'
    },
    'WSPOMINA_MIEJSCOWOSC': {
        'subject_label': 'Chunk',
        'predicate_label': 'WSPOMINA_MIEJSCOWOSC',
        'object_label': 'Miejscowosc'
    },
    'DEFINIUJE_PARAMETR': {
        'subject_label': 'Strefa',
        'predicate_label': 'DEFINIUJE_PARAMETR',
        'object_label': 'Parametr'
    }
}
```

### 5.3 Entity Resolution

Łączenie encji z Subject Graph z węzłami Domain Graph:

```cypher
// Znajdź strefy z Subject Graph które pasują do Domain Graph
MATCH (entity:Strefa:`__Entity__`), (domain:StrefaPOG)
WHERE domain.id CONTAINS entity.name
   OR apoc.text.jaroWinklerDistance(entity.name, domain.oznaczenie) < 0.3
MERGE (entity)-[:CORRESPONDS_TO]->(domain)
```

---

## 6. Query Patterns - Jak agent używa grafów

### 6.1 Strategia Neuro-Symbolic

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NEURO-SYMBOLIC QUERY STRATEGY                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER QUERY                                                                 │
│   "Szukam cichej działki pod dom blisko lasu w Gdańsku"                     │
│                                                                              │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    LLM (NEURAL)                                      │   │
│   │                                                                      │   │
│   │   Rozumie intencję, generuje structured query:                       │   │
│   │   {                                                                  │   │
│   │     "gmina": "Gdańsk",                                               │   │
│   │     "typ_zabudowy": "jednorodzinna",                                 │   │
│   │     "cisza": "cicha",          // lub lepiej                         │   │
│   │     "natura": "zielona",       // lub lepiej (blisko lasu)          │   │
│   │     "powierzchnia": "pod_dom"                                        │   │
│   │   }                                                                  │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    RULES (SYMBOLIC)                                  │   │
│   │                                                                      │   │
│   │   Cypher query z parameters:                                         │   │
│   │                                                                      │   │
│   │   MATCH (d:Dzialka)-[:W_GMINIE]->(g:Gmina {nazwa: $gmina})          │   │
│   │   MATCH (d)-[:MOZNA_ZABUDOWAC]->(t:TypZabudowy {typ: $typ})         │   │
│   │   MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)                         │   │
│   │     WHERE c.poziom IN ['bardzo_cicha', 'cicha']                     │   │
│   │   MATCH (d)-[:MA_NATURE]->(n:KategoriaNatury)                       │   │
│   │     WHERE n.poziom IN ['bardzo_zielona', 'zielona']                 │   │
│   │   MATCH (d)-[:MA_POWIERZCHNIE]->(p:KlasaPowierzchni {klasa: $pow}) │   │
│   │   RETURN d.id, d.area_m2, d.quietness_score, d.nature_score         │   │
│   │   ORDER BY d.nature_score DESC, d.quietness_score DESC              │   │
│   │   LIMIT 20                                                           │   │
│   │                                                                      │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│                           [Deterministyczne wyniki]                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Neo4j jako Unified Store (Graph + Vector)

**Kluczowa decyzja:** Zamiast osobnego Milvus, używamy **wbudowanego Vector Index w Neo4j**.

#### Zalety tego podejścia

| Aspekt | Osobny Vector Store (Milvus) | Neo4j + Vectors |
|--------|------------------------------|-----------------|
| Similarity search | ✅ | ✅ |
| Relacje między danymi | ❌ | ✅ |
| Graph traversal | ❌ | ✅ |
| **Jedno zapytanie** | ❌ (2 systemy) | ✅ Vector + Graph |
| Złożoność operacyjna | Wysoka | Niska |
| Skalowalność >10M | ✅ Lepsza | ⚠️ Wymaga testów |

#### Tworzenie Vector Index

```cypher
-- Indeks dla embeddingów działek (cechy przestrzenne)
CREATE VECTOR INDEX parcel_embeddings IF NOT EXISTS
FOR (d:Dzialka) ON (d.embedding)
OPTIONS { indexConfig: {
    `vector.dimensions`: 32,
    `vector.similarity_function`: 'cosine'
}}

-- Indeks dla embeddingów dokumentów (RAG)
CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS { indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
}}
```

### 6.3 Unified Search - Vector + Graph w jednym zapytaniu

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED SEARCH (Neo4j Vector + Graph)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER PREFERENCES → Embedding (32-dim)                                      │
│                              │                                               │
│                              ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   1. VECTOR SEARCH - znajdź podobne działki                          │   │
│   │      db.index.vector.queryNodes('parcel_embeddings', 100, $pref)    │   │
│   │      → 100 kandydatów posortowanych wg similarity                    │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   2. GRAPH FILTER - filtruj przez relacje                            │   │
│   │      MATCH (d)-[:W_GMINIE]->(g:Gmina {nazwa: $gmina})               │   │
│   │      MATCH (d)-[:MA_CISZE]->(c) WHERE c.poziom IN [...]             │   │
│   │      → ~20-50 działek spełniających twarde kryteria                  │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   3. CONTEXT ENRICHMENT - dodaj kontekst z grafu                     │   │
│   │      MATCH (d)-[:W_STREFIE_POG]->(s)-[:DOZWALA]->(p)                │   │
│   │      → Pełne info o POG, dozwolonych funkcjach                       │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │   4. SEMANTIC RAG (opcjonalnie) - dokumenty o strefie                │   │
│   │      db.index.vector.queryNodes('chunk_embeddings', 5, $query)      │   │
│   │      → Relevantne fragmenty uzasadnień POG                           │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   OUTPUT: 20 działek z kontekstem i wyjaśnieniem                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Przykładowe zapytania - Vector + Graph

```cypher
// ═══════════════════════════════════════════════════════════════════════════
// VECTOR + GRAPH: Główne wyszukiwanie hybrydowe
// ═══════════════════════════════════════════════════════════════════════════

// 1. HYBRID SEARCH - Vector similarity + Graph filtering
//    Najważniejsze zapytanie - łączy embedding preferencji z filtrami grafowymi
CALL db.index.vector.queryNodes('parcel_embeddings', 100, $preference_embedding)
YIELD node AS d, score AS similarity

// Filtruj przez relacje grafowe
MATCH (d)-[:W_GMINIE]->(g:Gmina {nazwa: $gmina})
MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)
  WHERE c.poziom IN ['bardzo_cicha', 'cicha']
MATCH (d)-[:MOZNA_ZABUDOWAC]->(:TypZabudowy {typ: "jednorodzinna"})

// Wzbogać o kontekst POG
MATCH (d)-[:W_STREFIE_POG]->(s:StrefaPOG)

RETURN d.id, d.area_m2, similarity,
       s.symbol, s.max_wysokosc, s.nazwa,
       c.poziom AS cisza
ORDER BY similarity DESC
LIMIT 20

// ═══════════════════════════════════════════════════════════════════════════
// PURE GRAPH: Wyszukiwanie deterministyczne (bez wektorów)
// ═══════════════════════════════════════════════════════════════════════════

// 2. Podstawowe wyszukiwanie po kategoriach
MATCH (d:Dzialka)-[:W_GMINIE]->(g:Gmina {nazwa: "Gdańsk"})
MATCH (d)-[:MOZNA_ZABUDOWAC]->(t:TypZabudowy {typ: "jednorodzinna"})
MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)
  WHERE c.poziom IN ['bardzo_cicha', 'cicha']
MATCH (d)-[:MA_POWIERZCHNIE]->(p:KlasaPowierzchni {klasa: "pod_dom"})
RETURN d.id, d.area_m2, d.quietness_score
ORDER BY d.quietness_score DESC
LIMIT 20

// 3. Wyszukiwanie po parametrach POG
MATCH (d:Dzialka)-[:W_STREFIE_POG]->(s:StrefaPOG)
WHERE s.symbol = "SJ"
  AND s.max_wysokosc <= 12
  AND s.min_bio_pct >= 40
MATCH (s)-[:DOZWALA {typ: "podstawowy"}]->(p:ProfilFunkcji)
RETURN d.id, s.nazwa, collect(p.nazwa) AS dozwolone_funkcje

// ═══════════════════════════════════════════════════════════════════════════
// FIND SIMILAR: Użyj embeddingu istniejącej działki
// ═══════════════════════════════════════════════════════════════════════════

// 4. Znajdź działki podobne do referencyjnej (przez embedding)
MATCH (ref:Dzialka {id: $reference_id})
CALL db.index.vector.queryNodes('parcel_embeddings', 50, ref.embedding)
YIELD node AS d, score

WHERE d.id <> ref.id
// Opcjonalnie: ogranicz do tej samej gminy
MATCH (d)-[:W_GMINIE]->(g:Gmina)
MATCH (ref)-[:W_GMINIE]->(g)

RETURN d.id, d.area_m2, score AS similarity
LIMIT 20

// ═══════════════════════════════════════════════════════════════════════════
// RAG: Semantic search na dokumentach POG
// ═══════════════════════════════════════════════════════════════════════════

// 5. RAG query - znajdź relevantne chunki o strefie
CALL db.index.vector.queryNodes('chunk_embeddings', 10, $question_embedding)
YIELD node AS chunk, score

// Połącz z kontekstem dokumentu
MATCH (chunk)-[:FROM_DOCUMENT]->(doc:Document)

// Opcjonalnie: rozszerz kontekst o sąsiednie chunki (window)
OPTIONAL MATCH (chunk)-[:NEXT_CHUNK]->(next:Chunk)
OPTIONAL MATCH (prev:Chunk)-[:NEXT_CHUNK]->(chunk)

RETURN chunk.text,
       prev.text AS prev_context,
       next.text AS next_context,
       doc.title,
       score
LIMIT 5

// 6. RAG + Graf: Znajdź dokumenty o konkretnej strefie POG
MATCH (s:StrefaPOG {id: $strefa_id})
MATCH (chunk:Chunk)
WHERE chunk.text CONTAINS s.oznaczenie OR chunk.text CONTAINS s.symbol

// Dodaj vector scoring dla relevantności
WITH chunk, s
CALL db.index.vector.queryNodes('chunk_embeddings', 5, $question_embedding)
YIELD node, score
WHERE node = chunk

MATCH (chunk)-[:FROM_DOCUMENT]->(doc:Document)
RETURN chunk.text, doc.title, score
ORDER BY score DESC
```

### 6.5 Generowanie embeddingu preferencji

```python
def build_preference_embedding(preferences: dict) -> list[float]:
    """Buduje embedding 32-dim z preferencji użytkownika.

    Mapuje wartości kategoryczne na numeryczne i normalizuje.
    Ten sam schemat co dla działek - umożliwia similarity search.
    """
    embedding = []

    # Powierzchnia (0-1, log scale)
    area_map = {'mala': 0.2, 'pod_dom': 0.5, 'duza': 0.75, 'bardzo_duza': 1.0}
    embedding.append(area_map.get(preferences['powierzchnia'], 0.5))

    # Cisza (0-1, wyższa = ciszej)
    cisza_map = {'glosna': 0.1, 'umiarkowana': 0.4, 'cicha': 0.7, 'bardzo_cicha': 1.0, 'dowolna': 0.5}
    embedding.append(cisza_map.get(preferences['cisza'], 0.5))

    # Natura (0-1, wyższa = bardziej zielona)
    natura_map = {'zurbanizowana': 0.1, 'umiarkowana': 0.4, 'zielona': 0.7, 'bardzo_zielona': 1.0, 'dowolna': 0.5}
    embedding.append(natura_map.get(preferences['natura'], 0.5))

    # Dostępność (0-1)
    dostepnosc_map = {'ograniczona': 0.1, 'umiarkowana': 0.4, 'dobra': 0.7, 'doskonala': 1.0, 'dowolna': 0.5}
    embedding.append(dostepnosc_map.get(preferences['dostepnosc'], 0.5))

    # ... pozostałe wymiary (do 32)
    # Wypełnij neutralnymi wartościami dla wymiarów których user nie określił
    while len(embedding) < 32:
        embedding.append(0.5)  # neutral

    return embedding
```

---

## 7. Narzędzia agenta - Human-in-the-Loop

### 7.1 Pattern: set_perceived → approve

```python
# ═══════════════════════════════════════════════════════════════════════════
# NARZĘDZIA DO ZBIERANIA PREFERENCJI
# ═══════════════════════════════════════════════════════════════════════════

PERCEIVED_PREFERENCES = "perceived_preferences"
APPROVED_PREFERENCES = "approved_preferences"

def set_perceived_preferences(
    gmina: str | None,
    dzielnica: str | None,
    typ_zabudowy: str,        # jednorodzinna, wielorodzinna, uslugowa
    cisza: str,               # bardzo_cicha, cicha, umiarkowana, glosna, dowolna
    natura: str,              # bardzo_zielona, zielona, umiarkowana, zurbanizowana, dowolna
    dostepnosc: str,          # doskonala, dobra, umiarkowana, ograniczona, dowolna
    powierzchnia: str,        # mala, pod_dom, duza, bardzo_duza
    tool_context: ToolContext
) -> dict:
    """Zapisuje postrzegane preferencje użytkownika.

    Użyj tego narzędzia po rozmowie z użytkownikiem, gdy rozumiesz
    jego wymagania. Następnie przedstaw mu podsumowanie i poproś
    o zatwierdzenie.

    Args:
        gmina: Nazwa gminy (Gdańsk, Gdynia, Sopot) lub None jeśli dowolna
        dzielnica: Nazwa dzielnicy lub None jeśli dowolna
        typ_zabudowy: Rodzaj zabudowy do której szuka działki
        cisza: Preferencja ciszy (dalej od ruchu = ciszej)
        natura: Preferencja bliskości natury (las, woda)
        dostepnosc: Preferencja dostępności (szkoły, transport)
        powierzchnia: Klasa powierzchni działki

    Returns:
        Status operacji i zapisane preferencje
    """
    preferences = {
        "gmina": gmina,
        "dzielnica": dzielnica,
        "typ_zabudowy": typ_zabudowy,
        "cisza": cisza,
        "natura": natura,
        "dostepnosc": dostepnosc,
        "powierzchnia": powierzchnia
    }

    # Walidacja wartości
    valid_cisza = ['bardzo_cicha', 'cicha', 'umiarkowana', 'glosna', 'dowolna']
    if cisza not in valid_cisza:
        return tool_error(f"Nieprawidłowa wartość cisza. Dozwolone: {valid_cisza}")

    # ... podobna walidacja dla innych pól

    tool_context.state[PERCEIVED_PREFERENCES] = preferences
    return tool_success(PERCEIVED_PREFERENCES, preferences)


def approve_perceived_preferences(tool_context: ToolContext) -> dict:
    """Zatwierdza postrzegane preferencje po akceptacji użytkownika.

    Użyj tego narzędzia TYLKO gdy użytkownik explicite zaakceptował
    przedstawione preferencje. Nie używaj bez potwierdzenia!
    """
    # Guard pattern
    if PERCEIVED_PREFERENCES not in tool_context.state:
        return tool_error(
            "Brak postrzeganych preferencji. Najpierw użyj set_perceived_preferences "
            "aby zapisać preferencje, a następnie przedstaw je użytkownikowi."
        )

    tool_context.state[APPROVED_PREFERENCES] = tool_context.state[PERCEIVED_PREFERENCES]
    return tool_success(APPROVED_PREFERENCES, tool_context.state[APPROVED_PREFERENCES])
```

### 7.2 Narzędzie wyszukiwania (Unified Neo4j)

```python
def search_parcels(tool_context: ToolContext) -> dict:
    """Wyszukuje działki na podstawie zatwierdzonych preferencji.

    Używa UNIFIED SEARCH - Vector + Graph w jednym zapytaniu Neo4j.
    Wymaga wcześniejszego zatwierdzenia preferencji przez approve_perceived_preferences.
    """
    # Guard pattern
    if APPROVED_PREFERENCES not in tool_context.state:
        return tool_error(
            "Brak zatwierdzonych preferencji. Najpierw zbierz i zatwierdź preferencje "
            "używając set_perceived_preferences i approve_perceived_preferences."
        )

    prefs = tool_context.state[APPROVED_PREFERENCES]

    # 1. Zbuduj embedding z preferencji (32-dim)
    pref_embedding = build_preference_embedding(prefs)

    # 2. UNIFIED QUERY: Vector similarity + Graph filtering w jednym zapytaniu
    cypher_query = """
    // Vector search - znajdź 100 najbardziej podobnych
    CALL db.index.vector.queryNodes('parcel_embeddings', 100, $pref_embedding)
    YIELD node AS d, score AS similarity

    // Graph filtering - zastosuj twarde kryteria
    MATCH (d)-[:W_GMINIE]->(g:Gmina)
    WHERE $gmina IS NULL OR g.nazwa = $gmina

    MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)
    WHERE $cisza = 'dowolna' OR c.poziom IN $cisza_levels

    MATCH (d)-[:MA_NATURE]->(n:KategoriaNatury)
    WHERE $natura = 'dowolna' OR n.poziom IN $natura_levels

    MATCH (d)-[:MOZNA_ZABUDOWAC]->(t:TypZabudowy {typ: $typ_zabudowy})

    // Wzbogać o kontekst POG
    MATCH (d)-[:W_STREFIE_POG]->(s:StrefaPOG)
    OPTIONAL MATCH (s)-[:DOZWALA {typ: 'podstawowy'}]->(p:ProfilFunkcji)

    RETURN d.id, d.area_m2, d.centroid_lat, d.centroid_lon,
           similarity,
           c.poziom AS cisza, n.poziom AS natura,
           s.symbol AS pog_symbol, s.nazwa AS pog_nazwa,
           s.max_wysokosc, s.max_zabudowa_pct,
           collect(DISTINCT p.nazwa) AS dozwolone_funkcje
    ORDER BY similarity DESC
    LIMIT 20
    """

    # 3. Wykonaj unified query
    params = {
        "pref_embedding": pref_embedding,
        "gmina": prefs.get("gmina"),
        "cisza": prefs.get("cisza", "dowolna"),
        "cisza_levels": get_cisza_levels(prefs.get("cisza")),
        "natura": prefs.get("natura", "dowolna"),
        "natura_levels": get_natura_levels(prefs.get("natura")),
        "typ_zabudowy": prefs.get("typ_zabudowy", "jednorodzinna")
    }

    parcels = neo4j_service.execute(cypher_query, params)

    # 4. Opcjonalnie: pobierz geometrie z PostGIS dla mapy
    parcel_ids = [p["d.id"] for p in parcels]
    geometries = postgis_service.get_geometries(parcel_ids)

    # Merge results
    for parcel in parcels:
        parcel["geometry"] = geometries.get(parcel["d.id"])

    tool_context.state["search_results"] = parcels
    return tool_success("search_results", {
        "count": len(parcels),
        "parcels": parcels
    })


def get_cisza_levels(cisza_pref: str) -> list[str]:
    """Mapuje preferencję ciszy na akceptowalne poziomy."""
    mapping = {
        "bardzo_cicha": ["bardzo_cicha"],
        "cicha": ["bardzo_cicha", "cicha"],
        "umiarkowana": ["bardzo_cicha", "cicha", "umiarkowana"],
        "glosna": ["bardzo_cicha", "cicha", "umiarkowana", "glosna"],
        "dowolna": ["bardzo_cicha", "cicha", "umiarkowana", "glosna"]
    }
    return mapping.get(cisza_pref, mapping["dowolna"])
```

---

## 8. Pipeline budowy grafu

### 8.1 Two-Phase Construction (z kursu)

```python
# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: DOMAIN GRAPH (Rule-based, no LLM)
# ═══════════════════════════════════════════════════════════════════════════

def construct_domain_graph(construction_plan: dict):
    """Buduje Domain Graph z planu konstrukcji.

    Plan zawiera:
    - node_constructions: definicje węzłów z CSV/GeoPackage
    - relationship_constructions: definicje relacji

    Kolejność: najpierw WSZYSTKIE węzły, potem relacje!
    """
    # Phase 1a: Create nodes
    for node_def in construction_plan['node_constructions']:
        create_uniqueness_constraint(node_def['label'], node_def['unique_key'])
        load_nodes_from_source(node_def)

    # Phase 1b: Create relationships (nodes must exist!)
    for rel_def in construction_plan['relationship_constructions']:
        import_relationships(rel_def)

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: LEXICAL GRAPH (Uses SimpleKGPipeline pattern)
# ═══════════════════════════════════════════════════════════════════════════

async def construct_lexical_graph(document_paths: list[str]):
    """Buduje Lexical Graph z dokumentów POG."""

    for doc_path in document_paths:
        # Load and chunk
        text = load_document(doc_path)
        chunks = text_splitter.split(text)

        # Generate embeddings
        embeddings = embedding_model.encode(chunks)

        # Create Document node
        create_document_node(doc_path)

        # Create Chunk nodes with embeddings
        prev_chunk_id = None
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = create_chunk_node(chunk, embedding, i, doc_path)

            if i == 0:
                create_first_chunk_relationship(doc_path, chunk_id)
            else:
                create_next_chunk_relationship(prev_chunk_id, chunk_id)

            prev_chunk_id = chunk_id

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: SUBJECT GRAPH + ENTITY RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════

async def construct_subject_graph_and_resolve():
    """Ekstrahuje encje z chunków i łączy z Domain Graph."""

    # Extract entities from chunks
    chunks = get_all_chunks()
    for chunk in chunks:
        entities = extract_entities_with_llm(chunk.text, approved_entities)
        for entity in entities:
            create_entity_node(entity)
            create_from_chunk_relationship(chunk.id, entity.id)

    # Entity Resolution
    resolve_entities('Strefa', 'StrefaPOG', 'name', 'oznaczenie')
    resolve_entities('Miejscowosc', 'Dzielnica', 'name', 'nazwa')
```

### 8.2 Construction Plan dla moja-dzialka

```python
domain_graph_construction_plan = {
    # ═══════════════════════════════════════════════════════════════
    # NODE CONSTRUCTIONS
    # ═══════════════════════════════════════════════════════════════

    "Gmina": {
        "construction_type": "node",
        "source": "static",  # hardcoded dla Trójmiasta
        "label": "Gmina",
        "unique_key": "teryt",
        "data": [
            {"nazwa": "Gdańsk", "teryt": "2261", "wojewodztwo": "pomorskie"},
            {"nazwa": "Gdynia", "teryt": "2263", "wojewodztwo": "pomorskie"},
            {"nazwa": "Sopot", "teryt": "2264", "wojewodztwo": "pomorskie"},
        ]
    },

    "Dzielnica": {
        "construction_type": "node",
        "source": "bdot10k",
        "source_file": "ADMS_A.gpkg",
        "label": "Dzielnica",
        "unique_key": "nazwa",
        "filter": "RODZAJ = 'część miasta'"
    },

    "StrefaPOG": {
        "construction_type": "node",
        "source": "geopackage",
        "source_file": "data/processed/pog_trojmiasto.gpkg",
        "label": "StrefaPOG",
        "unique_key": "id",
        "properties": ["symbol", "nazwa", "max_intensywnosc", "max_zabudowa_pct",
                       "max_wysokosc", "min_bio_pct"]
    },

    "ProfilFunkcji": {
        "construction_type": "node",
        "source": "static",
        "label": "ProfilFunkcji",
        "unique_key": "kod",
        "data": [
            {"kod": "MN", "nazwa": "teren zabudowy mieszkaniowej jednorodzinnej", "typ": "podstawowy"},
            {"kod": "MW", "nazwa": "teren zabudowy mieszkaniowej wielorodzinnej", "typ": "podstawowy"},
            # ... wszystkie profile z POG
        ]
    },

    "KategoriaCiszy": {
        "construction_type": "node",
        "source": "static",
        "label": "KategoriaCiszy",
        "unique_key": "poziom",
        "data": [
            {"poziom": "bardzo_cicha", "opis": "Daleko od ruchu i przemysłu (>2km)"},
            {"poziom": "cicha", "opis": "Umiarkowana odległość od ruchu (1-2km)"},
            {"poziom": "umiarkowana", "opis": "Blisko ruchu (500m-1km)"},
            {"poziom": "glosna", "opis": "Bardzo blisko ruchu (<500m)"},
        ]
    },

    # ... podobnie dla KategoriaNatury, KategoriaDostepnosci, KlasaPowierzchni, TypZabudowy

    "Dzialka": {
        "construction_type": "node",
        "source": "geopackage",
        "source_file": "data/processed/parcels_features.gpkg",
        "label": "Dzialka",
        "unique_key": "id_dzialki",
        "properties": ["area_m2", "centroid_lat", "centroid_lon",
                       "quietness_score", "nature_score", "accessibility_score"]
    },

    # ═══════════════════════════════════════════════════════════════
    # RELATIONSHIP CONSTRUCTIONS
    # ═══════════════════════════════════════════════════════════════

    "W_GMINIE": {
        "construction_type": "relationship",
        "source_file": "data/processed/parcels_features.gpkg",
        "relationship_type": "W_GMINIE",
        "from_node_label": "Dzialka",
        "from_node_column": "id_dzialki",
        "to_node_label": "Gmina",
        "to_node_column": "gmina",
        "to_node_match_column": "nazwa"
    },

    "W_STREFIE_POG": {
        "construction_type": "relationship",
        "source_file": "data/processed/parcels_pog_join.csv",
        "relationship_type": "W_STREFIE_POG",
        "from_node_label": "Dzialka",
        "from_node_column": "id_dzialki",
        "to_node_label": "StrefaPOG",
        "to_node_column": "pog_strefa_id",
        "properties": ["pct_overlap"]
    },

    "DOZWALA": {
        "construction_type": "relationship",
        "source_file": "data/processed/pog_profiles.csv",
        "relationship_type": "DOZWALA",
        "from_node_label": "StrefaPOG",
        "from_node_column": "strefa_id",
        "to_node_label": "ProfilFunkcji",
        "to_node_column": "profil_kod",
        "properties": ["typ"]  # podstawowy | dodatkowy
    },

    "MA_CISZE": {
        "construction_type": "relationship",
        "source_file": "data/processed/parcels_features.gpkg",
        "relationship_type": "MA_CISZE",
        "from_node_label": "Dzialka",
        "from_node_column": "id_dzialki",
        "to_node_label": "KategoriaCiszy",
        "to_node_column": "cisza_kategoria",
        "to_node_match_column": "poziom"
    },

    # ... podobnie dla MA_NATURE, MA_DOSTEPNOSC, MA_POWIERZCHNIE, MOZNA_ZABUDOWAC
}
```

---

## 9. Skalowalność - Partycjonowanie

### 9.1 Strategia dla całej Polski

```cypher
// Obecna struktura (MVP - Trójmiasto)
(:Dzialka {id: "226301_1.0012.152/5"})

// Przyszła struktura (Polska)
(:Dzialka {id: "226301_1.0012.152/5", wojewodztwo: "pomorskie"})

// Label per województwo dla szybszego filtrowania
(:Dzialka:Pomorskie {id: "..."})
(:Dzialka:Mazowieckie {id: "..."})
```

### 9.2 Sharding Neo4j

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NEO4J FABRIC (Federacja)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Query Router                                                               │
│   └── "Szukaj w Gdańsku" → Pomorskie shard                                  │
│   └── "Szukaj w Polsce" → All shards (parallel)                             │
│                                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│   │  POMORSKIE  │  │ MAZOWIECKIE │  │   ŚLĄSKIE   │                         │
│   │  1.3M dział │  │  3M działek │  │  2M działek │                         │
│   └─────────────┘  └─────────────┘  └─────────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Co projektujemy od początku

- [x] `wojewodztwo` jako atrybut na każdym węźle Działka
- [x] Label `(:Dzialka:Pomorskie)` dla przyszłego partycjonowania
- [x] Construction plan per region
- [x] Query router w backendzie

---

## 10. Podsumowanie

### 10.1 Kluczowe zmiany vs V1

| Aspekt | V1 | V2 |
|--------|----|----|
| **Architektura** | Single graph | Three-Graph (Domain + Lexical + Subject) |
| **Vector Store** | Zewnętrzny Milvus | **Wbudowany Neo4j Vector Index** |
| **Hybrid Search** | 2 systemy, skomplikowane | **Jedno zapytanie Cypher** |
| **POI distances** | Relacje z NULL | Kategorie jakościowe (węzły) |
| **Dokumenty** | Nie indeksowane | Lexical Graph z embeddingami |
| **Entity Resolution** | Brak | Fuzzy matching + CORRESPONDS_TO |
| **Agent tools** | Proste | Human-in-the-Loop pattern |
| **Scalability** | Ad-hoc | Partycjonowanie by design |

### 10.2 Unified Store: Neo4j = Graph + Vector

**Kluczowa decyzja architektoniczna:** Używamy Neo4j jako jedynego store dla:
- **Domain Graph** - relacje, kategorie, POG
- **Vector Index** - embeddingi działek (32-dim) i dokumentów (1536-dim)
- **Fulltext Index** - wyszukiwanie tekstowe

**Zalety:**
- Jedno zapytanie łączy vector similarity + graph traversal
- Brak synchronizacji między systemami
- Prostsza architektura operacyjna

**Kiedy rozważyć Milvus:**
- Skala > 10M wektorów (benchmark potrzebny)
- Wymagana sub-10ms latencja na samym vector search

### 10.3 Kolejność implementacji

1. **Teraz:** Domain Graph + Vector Index (embeddingi działek)
2. **Potem:** Agent tools z Human-in-the-Loop
3. **Opcjonalnie:** Lexical Graph + Subject Graph (RAG na dokumentach POG)

### 10.4 Korzyści nowej architektury

1. **Unified Search** - Vector + Graph w jednym zapytaniu Cypher
2. **Deterministyczne filtrowanie** - Cypher patterns zamiast LLM guessing
3. **Semantic enrichment** - RAG z dokumentów POG (opcjonalnie)
4. **Skalowalność** - partycjonowanie od początku
5. **Bezpieczeństwo** - Guard patterns chronią przed halucynacjami
6. **Traceability** - Human-in-the-Loop z zapisem stanu
7. **Prostota** - jeden system zamiast trzech (Neo4j + Milvus + sync)

### 10.5 Kluczowe zapytania do zapamiętania

```cypher
-- Główne wyszukiwanie: Vector + Graph
CALL db.index.vector.queryNodes('parcel_embeddings', 100, $pref_embedding)
YIELD node AS d, score
MATCH (d)-[:W_GMINIE]->(:Gmina {nazwa: $gmina})
MATCH (d)-[:MA_CISZE]->(c) WHERE c.poziom IN ['bardzo_cicha', 'cicha']
RETURN d.id, score

-- RAG na dokumentach
CALL db.index.vector.queryNodes('chunk_embeddings', 5, $question_embedding)
YIELD node AS chunk, score
MATCH (chunk)-[:FROM_DOCUMENT]->(doc)
RETURN chunk.text, doc.title
```
