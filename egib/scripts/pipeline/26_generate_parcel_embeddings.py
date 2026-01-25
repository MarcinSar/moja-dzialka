#!/usr/bin/env python3
"""
26_generate_parcel_embeddings.py - Generowanie embeddingów dla działek

Generuje DWA typy embeddingów dla każdej działki:

1. TEKSTOWY EMBEDDING (512-dim) - semantic search
   - Model: distiluse-base-multilingual-cased (PL+EN)
   - Źródło: wygenerowany opis tekstowy działki
   - Właściwość: p.text_embedding
   - Użycie: "szukam cichej działki blisko lasu" → vector search

2. GRAFOWY EMBEDDING (256-dim) - similarity search
   - Algorytm: FastRP (Neo4j GDS)
   - Źródło: topologia grafu + właściwości węzłów
   - Właściwość: p.graph_embedding
   - Użycie: "znajdź działki podobne do tej" → kNN

Wymagania:
- Neo4j z GDS (Graph Data Science) plugin
- sentence-transformers>=2.2.0
- Graf z relacjami (po uruchomieniu 24_import_parcels_v2.py)

Użycie:
    python 26_generate_parcel_embeddings.py              # oba embeddingi
    python 26_generate_parcel_embeddings.py --text-only  # tylko tekstowe
    python 26_generate_parcel_embeddings.py --graph-only # tylko grafowe
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Embedding configuration
TEXT_EMBEDDING_DIM = 512
GRAPH_EMBEDDING_DIM = 256
TEXT_MODEL = "distiluse-base-multilingual-cased-v1"  # 512-dim, PL+EN
BATCH_SIZE = 500

# Lazy load sentence-transformers (heavy import)
_embedder = None


def get_embedder():
    """Lazy load sentence-transformers model."""
    global _embedder
    if _embedder is None:
        logger.info(f"Loading sentence-transformers model: {TEXT_MODEL}")
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(TEXT_MODEL)
        logger.info(f"  Model loaded. Embedding dimension: {_embedder.get_sentence_embedding_dimension()}")
    return _embedder


# =============================================================================
# CZĘŚĆ 1: TEKSTOWE EMBEDDINGI (512-dim)
# =============================================================================

def generate_parcel_description(parcel: Dict) -> str:
    """
    Generuje tekstowy opis działki dla embeddingu.

    Opis zawiera kluczowe cechy w naturalnym języku polskim,
    co umożliwia semantic search po zapytaniach użytkownika.
    """
    parts = []

    # Lokalizacja
    dzielnica = parcel.get('dzielnica') or 'nieznana dzielnica'
    gmina = parcel.get('gmina') or ''
    parts.append(f"Działka w {dzielnica}, {gmina}.")

    # Rozmiar
    area = parcel.get('area_m2')
    size_cat = parcel.get('size_category')
    if area:
        size_desc = {
            'mala': 'mała',
            'pod_dom': 'idealna pod dom',
            'duza': 'duża',
            'bardzo_duza': 'bardzo duża'
        }.get(size_cat, '')
        parts.append(f"Powierzchnia {int(area)} m² ({size_desc}).")

    # Własność
    typ_wl = parcel.get('typ_wlasnosci')
    if typ_wl:
        wl_desc = {
            'prywatna': 'Własność prywatna - można kupić.',
            'publiczna': 'Własność publiczna.',
            'spoldzielcza': 'Własność spółdzielcza.',
            'koscielna': 'Własność kościelna.',
        }.get(typ_wl, '')
        if wl_desc:
            parts.append(wl_desc)

    # Zabudowa
    is_built = parcel.get('is_built')
    if is_built:
        building_type = parcel.get('building_type') or 'budynek'
        parts.append(f"Zabudowana - {building_type}.")
    else:
        parts.append("Niezabudowana - wolna pod budowę.")

    # Cisza
    quietness = parcel.get('quietness_score')
    kat_ciszy = parcel.get('kategoria_ciszy')
    if quietness is not None:
        if kat_ciszy == 'bardzo_cicha':
            parts.append(f"Bardzo cicha okolica (cisza {int(quietness)}/100).")
        elif kat_ciszy == 'cicha':
            parts.append(f"Cicha okolica (cisza {int(quietness)}/100).")
        elif kat_ciszy == 'umiarkowana':
            parts.append(f"Umiarkowany poziom hałasu.")
        else:
            parts.append(f"Głośna okolica - blisko drogi głównej.")

    # Natura
    nature = parcel.get('nature_score')
    kat_natury = parcel.get('kategoria_natury')
    if nature is not None:
        if kat_natury == 'bardzo_zielona':
            parts.append(f"Bardzo zielona okolica, blisko natury (natura {int(nature)}/100).")
        elif kat_natury == 'zielona':
            parts.append(f"Zielona okolica z dostępem do natury.")
        elif kat_natury == 'umiarkowana':
            parts.append(f"Umiarkowanie zielona okolica.")
        else:
            parts.append(f"Zurbanizowana okolica.")

    # Dostępność
    access = parcel.get('accessibility_score')
    if access is not None:
        if access >= 70:
            parts.append(f"Doskonała dostępność komunikacyjna i usług.")
        elif access >= 50:
            parts.append(f"Dobra dostępność usług.")
        elif access >= 30:
            parts.append(f"Umiarkowana dostępność.")
        else:
            parts.append(f"Ograniczona dostępność - spokojne przedmieścia.")

    # Woda
    water_type = parcel.get('nearest_water_type')
    dist_water = parcel.get('dist_to_water')
    if water_type and dist_water:
        water_names = {
            'morze': 'morza',
            'jezioro': 'jeziora',
            'rzeka': 'rzeki',
            'kanal': 'kanału',
            'staw': 'stawu'
        }
        water_name = water_names.get(water_type, 'wody')
        if dist_water < 500:
            parts.append(f"Blisko {water_name} ({int(dist_water)}m).")
        elif dist_water < 1000:
            parts.append(f"W pobliżu {water_name} ({int(dist_water)}m).")

    # Las
    dist_forest = parcel.get('dist_to_forest')
    if dist_forest is not None:
        if dist_forest < 200:
            parts.append(f"Bezpośrednio przy lesie ({int(dist_forest)}m).")
        elif dist_forest < 500:
            parts.append(f"Blisko lasu ({int(dist_forest)}m).")

    # Szkoła
    dist_school = parcel.get('dist_to_school')
    if dist_school is not None:
        if dist_school < 500:
            parts.append(f"Szkoła w zasięgu spaceru ({int(dist_school)}m).")
        elif dist_school < 1000:
            parts.append(f"Szkoła w pobliżu ({int(dist_school)}m).")

    # Komunikacja
    dist_bus = parcel.get('dist_to_bus_stop')
    if dist_bus is not None:
        if dist_bus < 300:
            parts.append(f"Przystanek autobusowy bardzo blisko ({int(dist_bus)}m).")
        elif dist_bus < 500:
            parts.append(f"Dobry dostęp do komunikacji ({int(dist_bus)}m do przystanku).")

    # POG / Planowanie
    pog_symbol = parcel.get('pog_symbol')
    is_residential = parcel.get('is_residential_zone')
    if pog_symbol:
        if is_residential:
            parts.append(f"Strefa {pog_symbol} - przeznaczona pod zabudowę mieszkaniową.")
        else:
            parts.append(f"Strefa planistyczna {pog_symbol}.")

    # Gęstość zabudowy
    gestosc = parcel.get('gestosc_zabudowy')
    if gestosc:
        gestosc_desc = {
            'bardzo_rzadka': 'Bardzo rzadka zabudowa w okolicy - dużo przestrzeni.',
            'rzadka': 'Rzadka zabudowa - spokojna okolica.',
            'umiarkowana': 'Umiarkowana gęstość zabudowy.',
            'gesta': 'Gęsta zabudowa w okolicy.'
        }.get(gestosc, '')
        if gestosc_desc:
            parts.append(gestosc_desc)

    return " ".join(parts)


def load_parcels_for_text_embedding(session) -> List[Dict]:
    """Load parcels with properties needed for text description."""
    logger.info("Loading parcels for text embedding...")

    query = """
    MATCH (p:Parcel)
    RETURN
        p.id_dzialki AS id_dzialki,
        p.dzielnica AS dzielnica,
        p.gmina AS gmina,
        p.area_m2 AS area_m2,
        p.size_category AS size_category,
        p.typ_wlasnosci AS typ_wlasnosci,
        p.is_built AS is_built,
        p.building_type AS building_type,
        p.quietness_score AS quietness_score,
        p.kategoria_ciszy AS kategoria_ciszy,
        p.nature_score AS nature_score,
        p.kategoria_natury AS kategoria_natury,
        p.accessibility_score AS accessibility_score,
        p.nearest_water_type AS nearest_water_type,
        p.dist_to_water AS dist_to_water,
        p.dist_to_forest AS dist_to_forest,
        p.dist_to_school AS dist_to_school,
        p.dist_to_bus_stop AS dist_to_bus_stop,
        p.pog_symbol AS pog_symbol,
        p.is_residential_zone AS is_residential_zone,
        p.gestosc_zabudowy AS gestosc_zabudowy
    """

    result = session.run(query)
    parcels = [dict(record) for record in result]
    logger.info(f"  Loaded {len(parcels):,} parcels")
    return parcels


def generate_text_embeddings(session, parcels: List[Dict]):
    """Generate and save text embeddings for all parcels."""
    logger.info("\n" + "=" * 60)
    logger.info("GENEROWANIE TEKSTOWYCH EMBEDDINGÓW (512-dim)")
    logger.info("=" * 60)

    embedder = get_embedder()

    # Generate descriptions
    logger.info("Generating parcel descriptions...")
    descriptions = []
    parcel_ids = []

    for parcel in parcels:
        desc = generate_parcel_description(parcel)
        descriptions.append(desc)
        parcel_ids.append(parcel['id_dzialki'])

    # Sample descriptions
    logger.info("\n  Sample descriptions:")
    for i in range(min(3, len(descriptions))):
        logger.info(f"    [{parcel_ids[i]}]: {descriptions[i][:100]}...")

    # Generate embeddings in batches
    logger.info(f"\nGenerating embeddings (batch_size={BATCH_SIZE})...")

    total = len(descriptions)
    for i in range(0, total, BATCH_SIZE):
        batch_desc = descriptions[i:i + BATCH_SIZE]
        batch_ids = parcel_ids[i:i + BATCH_SIZE]

        # Generate embeddings
        embeddings = embedder.encode(batch_desc, show_progress_bar=False)

        # Save to Neo4j
        batch_data = [
            {"id": pid, "embedding": emb.tolist()}
            for pid, emb in zip(batch_ids, embeddings)
        ]

        query = """
        UNWIND $batch AS row
        MATCH (p:Parcel {id_dzialki: row.id})
        SET p.text_embedding = row.embedding
        """
        session.run(query, {"batch": batch_data})

        if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= total:
            logger.info(f"  Processed {min(i + BATCH_SIZE, total):,} / {total:,}")

    logger.info(f"\nText embeddings saved for {total:,} parcels")


# =============================================================================
# CZĘŚĆ 2: GRAFOWE EMBEDDINGI (FastRP 256-dim)
# =============================================================================

def check_gds_available(session) -> bool:
    """Check if Neo4j GDS is available."""
    try:
        result = session.run("RETURN gds.version() AS version")
        record = result.single()
        logger.info(f"  Neo4j GDS version: {record['version']}")
        return True
    except Exception as e:
        logger.warning(f"  Neo4j GDS not available: {e}")
        return False


def create_graph_projection(session):
    """Create a graph projection for FastRP."""
    logger.info("\n  Creating graph projection for FastRP...")

    # Drop existing projection if exists
    try:
        session.run("CALL gds.graph.drop('parcel-graph', false)")
    except:
        pass

    # Create projection with relevant relationships and properties
    query = """
    CALL gds.graph.project(
        'parcel-graph',
        {
            Parcel: {
                properties: [
                    'quietness_score',
                    'nature_score',
                    'accessibility_score',
                    'area_m2',
                    'dist_to_water',
                    'dist_to_forest',
                    'dist_to_school'
                ]
            },
            District: {},
            QuietnessCategory: {},
            NatureCategory: {},
            SizeCategory: {},
            OwnershipType: {},
            BuildStatus: {}
        },
        {
            LOCATED_IN: {orientation: 'UNDIRECTED'},
            HAS_QUIETNESS: {orientation: 'UNDIRECTED'},
            HAS_NATURE: {orientation: 'UNDIRECTED'},
            HAS_SIZE: {orientation: 'UNDIRECTED'},
            HAS_OWNERSHIP: {orientation: 'UNDIRECTED'},
            HAS_BUILD_STATUS: {orientation: 'UNDIRECTED'}
        }
    )
    YIELD graphName, nodeCount, relationshipCount
    RETURN graphName, nodeCount, relationshipCount
    """

    try:
        result = session.run(query)
        record = result.single()
        logger.info(f"    Graph: {record['graphName']}")
        logger.info(f"    Nodes: {record['nodeCount']:,}")
        logger.info(f"    Relationships: {record['relationshipCount']:,}")
        return True
    except Exception as e:
        logger.error(f"  Failed to create projection: {e}")
        return False


def generate_fastrp_embeddings(session):
    """Generate FastRP embeddings using Neo4j GDS."""
    logger.info("\n" + "=" * 60)
    logger.info("GENEROWANIE GRAFOWYCH EMBEDDINGÓW (FastRP 256-dim)")
    logger.info("=" * 60)

    # Check GDS availability
    if not check_gds_available(session):
        logger.error("Neo4j GDS is required for graph embeddings. Skipping.")
        return False

    # Create graph projection
    if not create_graph_projection(session):
        return False

    # Run FastRP using pure graph topology
    # Note: We use relationships (HAS_QUIETNESS, HAS_NATURE, etc.) to encode
    # semantic information through graph structure rather than node properties
    logger.info("\n  Running FastRP algorithm (topology-based)...")

    query = """
    CALL gds.fastRP.mutate(
        'parcel-graph',
        {
            embeddingDimension: $dim,
            iterationWeights: [0.0, 1.0, 1.0, 0.5, 0.25],
            randomSeed: 42,
            mutateProperty: 'fastRP_embedding'
        }
    )
    YIELD nodePropertiesWritten, computeMillis
    RETURN nodePropertiesWritten, computeMillis
    """

    try:
        result = session.run(query, {"dim": GRAPH_EMBEDDING_DIM})
        record = result.single()
        logger.info(f"    Embeddings generated: {record['nodePropertiesWritten']:,}")
        logger.info(f"    Compute time: {record['computeMillis']}ms")
    except Exception as e:
        logger.error(f"  FastRP failed: {e}")
        return False

    # Write embeddings back to nodes
    logger.info("\n  Writing embeddings to Parcel nodes...")

    query = """
    CALL gds.graph.nodeProperty.stream('parcel-graph', 'fastRP_embedding', ['Parcel'])
    YIELD nodeId, propertyValue
    WITH gds.util.asNode(nodeId) AS node, propertyValue AS embedding
    WHERE node:Parcel
    SET node.graph_embedding = embedding
    RETURN count(*) AS updated
    """

    try:
        result = session.run(query)
        record = result.single()
        logger.info(f"    Updated {record['updated']:,} Parcel nodes")
    except Exception as e:
        logger.error(f"  Failed to write embeddings: {e}")
        return False

    # Clean up projection
    try:
        session.run("CALL gds.graph.drop('parcel-graph', false)")
        logger.info("  Graph projection dropped")
    except:
        pass

    return True


# =============================================================================
# CZĘŚĆ 3: TWORZENIE INDEKSÓW WEKTOROWYCH
# =============================================================================

def create_vector_indexes(session):
    """Create vector indexes for both embedding types."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE INDEKSÓW WEKTOROWYCH")
    logger.info("=" * 60)

    # Text embedding index (512-dim)
    logger.info("\n  Creating text_embedding index (512-dim)...")
    try:
        session.run("""
            CREATE VECTOR INDEX parcel_text_embedding_idx IF NOT EXISTS
            FOR (p:Parcel) ON (p.text_embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 512,
                `vector.similarity_function`: 'cosine'
            }}
        """)
        logger.info("    Index parcel_text_embedding_idx created")
    except Exception as e:
        logger.warning(f"    Index creation failed (may already exist): {e}")

    # Graph embedding index (256-dim)
    logger.info("\n  Creating graph_embedding index (256-dim)...")
    try:
        session.run("""
            CREATE VECTOR INDEX parcel_graph_embedding_idx IF NOT EXISTS
            FOR (p:Parcel) ON (p.graph_embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 256,
                `vector.similarity_function`: 'cosine'
            }}
        """)
        logger.info("    Index parcel_graph_embedding_idx created")
    except Exception as e:
        logger.warning(f"    Index creation failed (may already exist): {e}")


# =============================================================================
# CZĘŚĆ 4: WERYFIKACJA I TESTY
# =============================================================================

def verify_embeddings(session):
    """Verify embeddings were created correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("WERYFIKACJA EMBEDDINGÓW")
    logger.info("=" * 60)

    # Count text embeddings
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.text_embedding IS NOT NULL
        RETURN count(p) as cnt, size(p.text_embedding) as dim
        LIMIT 1
    """)
    record = result.single()
    if record and record['cnt'] > 0:
        logger.info(f"  Text embeddings: {record['cnt']:,} parcels, dim={record['dim']}")
    else:
        logger.warning("  No text embeddings found")

    # Count graph embeddings
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.graph_embedding IS NOT NULL
        RETURN count(p) as cnt, size(p.graph_embedding) as dim
        LIMIT 1
    """)
    record = result.single()
    if record and record['cnt'] > 0:
        logger.info(f"  Graph embeddings: {record['cnt']:,} parcels, dim={record['dim']}")
    else:
        logger.warning("  No graph embeddings found")


def test_semantic_search(session):
    """Test semantic search with text embeddings."""
    logger.info("\n  Testing semantic search...")

    embedder = get_embedder()

    # Test query
    test_query = "cicha zielona działka blisko lasu pod dom jednorodzinny"
    logger.info(f"    Query: '{test_query}'")

    query_embedding = embedder.encode(test_query).tolist()

    result = session.run("""
        CALL db.index.vector.queryNodes('parcel_text_embedding_idx', 5, $embedding)
        YIELD node, score
        RETURN
            node.id_dzialki AS id,
            node.dzielnica AS dzielnica,
            node.quietness_score AS quietness,
            node.nature_score AS nature,
            score
    """, {"embedding": query_embedding})

    logger.info("    Top 5 results:")
    for record in result:
        logger.info(f"      {record['id']} ({record['dzielnica']}) - quiet={record['quietness']}, nature={record['nature']}, score={record['score']:.3f}")


def test_similarity_search(session):
    """Test similarity search with graph embeddings."""
    logger.info("\n  Testing graph similarity search...")

    # Get a sample parcel
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.graph_embedding IS NOT NULL AND p.quietness_score > 70
        RETURN p.id_dzialki AS id, p.graph_embedding AS embedding, p.dzielnica AS dzielnica
        LIMIT 1
    """)
    record = result.single()

    if not record:
        logger.warning("    No parcels with graph embeddings found")
        return

    sample_id = record['id']
    sample_embedding = record['embedding']
    logger.info(f"    Reference parcel: {sample_id} ({record['dzielnica']})")

    # Find similar parcels
    result = session.run("""
        CALL db.index.vector.queryNodes('parcel_graph_embedding_idx', 6, $embedding)
        YIELD node, score
        WHERE node.id_dzialki <> $exclude_id
        RETURN
            node.id_dzialki AS id,
            node.dzielnica AS dzielnica,
            node.quietness_score AS quietness,
            score
        LIMIT 5
    """, {"embedding": sample_embedding, "exclude_id": sample_id})

    logger.info("    Similar parcels (by graph structure):")
    for record in result:
        logger.info(f"      {record['id']} ({record['dzielnica']}) - quiet={record['quietness']}, score={record['score']:.3f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate parcel embeddings")
    parser.add_argument("--text-only", action="store_true", help="Generate only text embeddings")
    parser.add_argument("--graph-only", action="store_true", help="Generate only graph embeddings")
    parser.add_argument("--skip-test", action="store_true", help="Skip verification tests")
    args = parser.parse_args()

    do_text = not args.graph_only
    do_graph = not args.text_only

    logger.info("=" * 60)
    logger.info("GENEROWANIE EMBEDDINGÓW DLA DZIAŁEK")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"Text embeddings (512-dim): {do_text}")
    logger.info(f"Graph embeddings (256-dim): {do_graph}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Text embeddings
            if do_text:
                parcels = load_parcels_for_text_embedding(session)
                if parcels:
                    generate_text_embeddings(session, parcels)

            # Graph embeddings
            if do_graph:
                generate_fastrp_embeddings(session)

            # Create indexes
            create_vector_indexes(session)

            # Verify
            verify_embeddings(session)

            # Tests
            if not args.skip_test:
                if do_text:
                    try:
                        test_semantic_search(session)
                    except Exception as e:
                        logger.warning(f"  Semantic search test failed: {e}")

                if do_graph:
                    try:
                        test_similarity_search(session)
                    except Exception as e:
                        logger.warning(f"  Similarity search test failed: {e}")

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("EMBEDDINGI WYGENEROWANE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
