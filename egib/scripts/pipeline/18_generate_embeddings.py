#!/usr/bin/env python3
"""
18_generate_embeddings.py - Generate embeddings for Neo4j vector search

Creates 32-dimensional embeddings from parcel features:
- Scores: quietness, nature, accessibility (3)
- Distances: school, bus, forest, water, sea, river, lake, main_road (8)
- Context: pct_forest_500m, pct_water_500m, count_buildings_500m (3)
- Size: area_m2, shape_index (2)
- Zoning: is_residential_zone, has_pog (2)
- Building: is_built, building_coverage_pct (2)
- Water proximity indicators (6)
- Padding (6)

Total: 32 dimensions
"""

import os
import sys
from pathlib import Path
import numpy as np
from typing import List, Dict, Any

from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "moja-dzialka-neo4j-2026")

BATCH_SIZE = 5000


def normalize_distance(value: float, max_val: float = 5000.0) -> float:
    """Normalize distance to 0-1 range (inverse - closer = higher)."""
    if value is None or value < 0:
        return 0.0
    return max(0.0, 1.0 - min(value, max_val) / max_val)


def normalize_score(value: float) -> float:
    """Normalize score (0-100) to 0-1 range."""
    if value is None:
        return 0.5
    return max(0.0, min(1.0, value / 100.0))


def normalize_percentage(value: float) -> float:
    """Normalize percentage (0-100) to 0-1 range."""
    if value is None:
        return 0.0
    return max(0.0, min(1.0, value / 100.0))


def normalize_area(value: float, min_val: float = 100, max_val: float = 10000) -> float:
    """Normalize area using log scale."""
    if value is None or value <= 0:
        return 0.5
    log_val = np.log10(max(min_val, min(value, max_val)))
    log_min = np.log10(min_val)
    log_max = np.log10(max_val)
    return (log_val - log_min) / (log_max - log_min)


def normalize_count(value: float, max_val: float = 500) -> float:
    """Normalize count to 0-1 range."""
    if value is None or value < 0:
        return 0.0
    return min(1.0, value / max_val)


def create_embedding(parcel: Dict[str, Any]) -> List[float]:
    """Create 32-dim embedding from parcel features."""
    embedding = []

    # 1. Scores (3 dims) - normalized 0-1
    embedding.append(normalize_score(parcel.get('quietness_score')))
    embedding.append(normalize_score(parcel.get('nature_score')))
    embedding.append(normalize_score(parcel.get('accessibility_score')))

    # 2. Key distances (8 dims) - inverse normalized (closer = higher)
    embedding.append(normalize_distance(parcel.get('dist_to_school'), 3000))
    embedding.append(normalize_distance(parcel.get('dist_to_bus_stop'), 1000))
    embedding.append(normalize_distance(parcel.get('dist_to_forest'), 2000))
    embedding.append(normalize_distance(parcel.get('dist_to_water'), 2000))
    embedding.append(normalize_distance(parcel.get('dist_to_sea'), 10000))
    embedding.append(normalize_distance(parcel.get('dist_to_river'), 3000))
    embedding.append(normalize_distance(parcel.get('dist_to_lake'), 5000))
    embedding.append(normalize_distance(parcel.get('dist_to_main_road'), 2000))

    # 3. Context (3 dims)
    embedding.append(normalize_percentage(parcel.get('pct_forest_500m')))
    embedding.append(normalize_percentage(parcel.get('pct_water_500m')))
    embedding.append(normalize_count(parcel.get('count_buildings_500m'), 500))

    # 4. Size & shape (2 dims)
    embedding.append(normalize_area(parcel.get('area_m2')))
    shape_index = parcel.get('shape_index')
    embedding.append(min(1.0, (shape_index or 1.0) / 3.0))  # shape_index ~1-3

    # 5. Zoning (2 dims)
    embedding.append(1.0 if parcel.get('is_residential_zone') else 0.0)
    embedding.append(1.0 if parcel.get('has_pog') else 0.0)

    # 6. Building (2 dims)
    embedding.append(1.0 if parcel.get('is_built') else 0.0)
    embedding.append(normalize_percentage(parcel.get('building_coverage_pct')))

    # 7. Water type indicators (6 dims) - one-hot style
    nearest_water = parcel.get('nearest_water_type') or ''
    embedding.append(1.0 if nearest_water == 'morze' else 0.0)
    embedding.append(1.0 if nearest_water == 'jezioro' else 0.0)
    embedding.append(1.0 if nearest_water == 'rzeka' else 0.0)
    embedding.append(1.0 if nearest_water == 'kanal' else 0.0)
    embedding.append(1.0 if nearest_water == 'staw' else 0.0)
    embedding.append(1.0 if nearest_water == 'zatoka' else 0.0)

    # 8. Padding to 32 dims (6 dims)
    # Use derived features
    embedding.append(normalize_distance(parcel.get('dist_to_supermarket'), 2000))
    embedding.append(normalize_distance(parcel.get('dist_to_pharmacy'), 3000))
    embedding.append(normalize_distance(parcel.get('dist_to_kindergarten'), 2000))
    embedding.append(normalize_distance(parcel.get('dist_to_restaurant'), 2000))
    embedding.append(normalize_distance(parcel.get('dist_to_industrial'), 1000))  # inverse - far from industrial is good
    # Last one: composite "premium location" score
    sea_score = normalize_distance(parcel.get('dist_to_sea'), 1000)
    forest_score = normalize_percentage(parcel.get('pct_forest_500m'))
    quiet_score = normalize_score(parcel.get('quietness_score'))
    embedding.append((sea_score + forest_score + quiet_score) / 3.0)

    assert len(embedding) == 32, f"Expected 32 dims, got {len(embedding)}"
    return embedding


def create_vector_index(session):
    """Create vector index in Neo4j."""
    logger.info("Creating vector index...")

    # Check if index exists
    result = session.run("""
        SHOW INDEXES YIELD name, type
        WHERE name = 'parcel_embedding_index' AND type = 'VECTOR'
        RETURN count(*) as cnt
    """)
    if result.single()['cnt'] > 0:
        logger.info("  Vector index already exists")
        return

    # Create index
    session.run("""
        CREATE VECTOR INDEX parcel_embedding_index IF NOT EXISTS
        FOR (p:Parcel) ON (p.embedding)
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 32,
                `vector.similarity_function`: 'cosine'
            }
        }
    """)
    logger.info("  Created vector index: parcel_embedding_index (32 dims, cosine)")


def generate_and_store_embeddings(session):
    """Generate embeddings for all parcels and store in Neo4j."""
    logger.info("\n" + "=" * 60)
    logger.info("GENEROWANIE EMBEDDINGÓW")
    logger.info("=" * 60)

    # Get total count
    result = session.run("MATCH (p:Parcel) RETURN count(p) as total")
    total = result.single()['total']
    logger.info(f"  Łącznie działek: {total:,}")

    # Process in batches
    processed = 0
    batch_num = 0

    while processed < total:
        # Fetch batch of parcels
        result = session.run("""
            MATCH (p:Parcel)
            RETURN p.id_dzialki as id,
                   p.quietness_score as quietness_score,
                   p.nature_score as nature_score,
                   p.accessibility_score as accessibility_score,
                   p.dist_to_school as dist_to_school,
                   p.dist_to_bus_stop as dist_to_bus_stop,
                   p.dist_to_forest as dist_to_forest,
                   p.dist_to_water as dist_to_water,
                   p.dist_to_sea as dist_to_sea,
                   p.dist_to_river as dist_to_river,
                   p.dist_to_lake as dist_to_lake,
                   p.dist_to_main_road as dist_to_main_road,
                   p.dist_to_supermarket as dist_to_supermarket,
                   p.dist_to_pharmacy as dist_to_pharmacy,
                   p.dist_to_kindergarten as dist_to_kindergarten,
                   p.dist_to_restaurant as dist_to_restaurant,
                   p.dist_to_industrial as dist_to_industrial,
                   p.pct_forest_500m as pct_forest_500m,
                   p.pct_water_500m as pct_water_500m,
                   p.count_buildings_500m as count_buildings_500m,
                   p.area_m2 as area_m2,
                   p.shape_index as shape_index,
                   p.is_residential_zone as is_residential_zone,
                   p.has_pog as has_pog,
                   p.is_built as is_built,
                   p.building_coverage_pct as building_coverage_pct,
                   p.nearest_water_type as nearest_water_type
            SKIP $skip LIMIT $limit
        """, skip=processed, limit=BATCH_SIZE)

        # Generate embeddings for batch
        updates = []
        for record in result:
            parcel = dict(record)
            parcel_id = parcel.pop('id')
            embedding = create_embedding(parcel)
            updates.append({
                'id': parcel_id,
                'embedding': embedding
            })

        if not updates:
            break

        # Store embeddings in batch
        session.run("""
            UNWIND $updates AS update
            MATCH (p:Parcel {id_dzialki: update.id})
            SET p.embedding = update.embedding
        """, updates=updates)

        processed += len(updates)
        batch_num += 1

        if batch_num % 10 == 0 or processed >= total:
            logger.info(f"  Przetworzono {processed:,} / {total:,} ({100*processed/total:.1f}%)")

    logger.info(f"  Wygenerowano embeddingi dla {processed:,} działek")


def verify_embeddings(session):
    """Verify embeddings were created correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("WERYFIKACJA")
    logger.info("=" * 60)

    # Count parcels with embeddings
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.embedding IS NOT NULL
        RETURN count(p) as with_embedding
    """)
    with_emb = result.single()['with_embedding']

    result = session.run("MATCH (p:Parcel) RETURN count(p) as total")
    total = result.single()['total']

    logger.info(f"  Działki z embeddingami: {with_emb:,} / {total:,}")

    # Sample embedding
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.embedding IS NOT NULL
        RETURN p.id_dzialki as id, p.embedding as emb
        LIMIT 1
    """)
    record = result.single()
    if record:
        emb = record['emb']
        logger.info(f"  Przykładowy embedding (ID: {record['id']}):")
        logger.info(f"    Wymiary: {len(emb)}")
        logger.info(f"    Min/Max: {min(emb):.3f} / {max(emb):.3f}")
        logger.info(f"    Średnia: {sum(emb)/len(emb):.3f}")

    # Test vector search
    logger.info("\n  Test wyszukiwania wektorowego:")
    result = session.run("""
        MATCH (p:Parcel)
        WHERE p.embedding IS NOT NULL
        WITH p LIMIT 1
        CALL db.index.vector.queryNodes('parcel_embedding_index', 5, p.embedding)
        YIELD node, score
        RETURN node.id_dzialki as id, node.gmina as gmina, score
    """)
    logger.info("  Top 5 najbardziej podobnych do pierwszej działki:")
    for record in result:
        logger.info(f"    {record['id']} ({record['gmina']}): {record['score']:.4f}")


def main():
    from neo4j import GraphDatabase

    logger.info("=" * 60)
    logger.info("GENEROWANIE EMBEDDINGÓW DLA NEO4J")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            create_vector_index(session)
            generate_and_store_embeddings(session)
            verify_embeddings(session)
    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("ZAKOŃCZONO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
