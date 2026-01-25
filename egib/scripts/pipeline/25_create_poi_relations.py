#!/usr/bin/env python3
"""
25_create_poi_relations.py - Tworzenie relacji NEAR_* z odległościami

Tworzy relacje przestrzenne między działkami a POI z metadanymi odległości:

RELACJE:
- (Parcel)-[:NEAR_SCHOOL {distance_m}]->(School)       threshold: 2000m
- (Parcel)-[:NEAR_BUS_STOP {distance_m}]->(BusStop)    threshold: 1000m
- (Parcel)-[:NEAR_SHOP {distance_m}]->(Shop)           threshold: 1500m
- (Parcel)-[:NEAR_WATER {distance_m}]->(Water)         threshold: 500m
- (Parcel)-[:NEAR_FOREST {distance_m}]->(Forest)       threshold: 500m
- (Parcel)-[:NEAR_ROAD {distance_m}]->(Road)           threshold: 200m

Algorytm:
1. Załaduj wszystkie POI z CSV (z koordynatami x,y)
2. Załaduj centroidy działek z Neo4j
3. Dla każdego typu POI:
   - Oblicz odległości między działkami a POI
   - Dla działek w threshold: utwórz relację z distance_m
4. Użyj batch processing dla wydajności

UWAGA: Ten skrypt może zająć dużo czasu (~1-2h) ze względu na liczbę obliczeń.
"""

import csv
import math
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from neo4j import GraphDatabase
from loguru import logger
from scipy.spatial import cKDTree
import numpy as np

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
CSV_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j" / "csv"

# Distance thresholds (meters)
POI_THRESHOLDS = {
    "School": {
        "csv_file": "schools.csv",
        "threshold_m": 2000,
        "relation_type": "NEAR_SCHOOL",
        "max_relations_per_parcel": 3,  # nearest 3 schools
    },
    "BusStop": {
        "csv_file": "bus_stops.csv",
        "threshold_m": 1000,
        "relation_type": "NEAR_BUS_STOP",
        "max_relations_per_parcel": 5,  # nearest 5 stops
    },
    "Shop": {
        "csv_file": "shops.csv",
        "threshold_m": 1500,
        "relation_type": "NEAR_SHOP",
        "max_relations_per_parcel": 5,
    },
    "Water": {
        "csv_file": "waters.csv",
        "threshold_m": 500,
        "relation_type": "NEAR_WATER",
        "max_relations_per_parcel": 3,
    },
    "Forest": {
        "csv_file": "forests.csv",
        "threshold_m": 500,
        "relation_type": "NEAR_FOREST",
        "max_relations_per_parcel": 3,
    },
    "Road": {
        "csv_file": "roads.csv",
        "threshold_m": 200,
        "relation_type": "NEAR_ROAD",
        "max_relations_per_parcel": 2,
    },
}

# Batch size for Neo4j operations
BATCH_SIZE = 5000


def load_poi_coordinates(csv_file: str) -> Tuple[np.ndarray, List[str]]:
    """Load POI coordinates from CSV file."""
    filepath = CSV_PATH / csv_file
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return np.array([]), []

    coords = []
    ids = []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row['x'])
                y = float(row['y'])
                poi_id = row['id']
                coords.append([x, y])
                ids.append(poi_id)
            except (ValueError, KeyError):
                continue

    return np.array(coords), ids


def load_parcel_centroids(session) -> Tuple[np.ndarray, List[str]]:
    """Load parcel centroids from Neo4j."""
    logger.info("  Loading parcel centroids from Neo4j...")

    query = """
    MATCH (p:Parcel)
    WHERE p.centroid_x IS NOT NULL AND p.centroid_y IS NOT NULL
    RETURN p.id_dzialki AS id, p.centroid_x AS x, p.centroid_y AS y
    """

    result = session.run(query)

    coords = []
    ids = []
    for record in result:
        coords.append([record['x'], record['y']])
        ids.append(record['id'])

    logger.info(f"  Loaded {len(ids):,} parcel centroids")
    return np.array(coords), ids


def import_poi_nodes(session, poi_type: str, config: dict):
    """Import POI nodes from CSV if not already present."""
    csv_file = config['csv_file']
    filepath = CSV_PATH / csv_file

    if not filepath.exists():
        logger.warning(f"  POI file not found: {filepath}")
        return 0

    # Check if already imported
    result = session.run(f"MATCH (n:{poi_type}) RETURN count(n) as cnt")
    record = result.single()
    if record['cnt'] > 0:
        logger.info(f"  {poi_type}: {record['cnt']:,} already in database")
        return record['cnt']

    # Import from CSV
    logger.info(f"  Importing {poi_type} from {csv_file}...")

    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                if v == '' or v == 'None':
                    cleaned[k] = None
                else:
                    try:
                        cleaned[k] = float(v) if '.' in v else int(v)
                    except (ValueError, TypeError):
                        cleaned[k] = v
            rows.append(cleaned)

    # Build property list based on available columns
    sample = rows[0] if rows else {}
    props = list(sample.keys())

    prop_clause = ", ".join([f"n.{p} = row.{p}" for p in props])

    query = f"""
    UNWIND $batch AS row
    MERGE (n:{poi_type} {{id: row.id}})
    SET {prop_clause}
    """

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, {"batch": batch})

    logger.info(f"  Imported {len(rows):,} {poi_type} nodes")
    return len(rows)


def create_poi_relations(session, poi_type: str, config: dict,
                         parcel_coords: np.ndarray, parcel_ids: List[str]):
    """Create NEAR_* relations for a POI type using KD-tree."""
    logger.info(f"\n  Processing {poi_type}...")

    # Load POI coordinates
    poi_coords, poi_ids = load_poi_coordinates(config['csv_file'])
    if len(poi_coords) == 0:
        logger.warning(f"  No {poi_type} coordinates found")
        return 0

    logger.info(f"    POI count: {len(poi_ids):,}")

    # Build KD-tree for POI
    poi_tree = cKDTree(poi_coords)

    threshold = config['threshold_m']
    max_rels = config['max_relations_per_parcel']
    rel_type = config['relation_type']

    logger.info(f"    Threshold: {threshold}m, Max relations: {max_rels}")

    # Query for nearest POI for each parcel
    relations = []

    # Query in batches
    batch_size = 10000
    total_parcels = len(parcel_ids)

    for batch_start in range(0, total_parcels, batch_size):
        batch_end = min(batch_start + batch_size, total_parcels)
        batch_coords = parcel_coords[batch_start:batch_end]

        # Query k nearest neighbors (up to max_rels within threshold)
        distances, indices = poi_tree.query(
            batch_coords,
            k=min(max_rels, len(poi_ids)),
            distance_upper_bound=threshold
        )

        # Handle single neighbor case
        if max_rels == 1 or len(poi_ids) == 1:
            distances = distances.reshape(-1, 1)
            indices = indices.reshape(-1, 1)

        for i, parcel_idx in enumerate(range(batch_start, batch_end)):
            parcel_id = parcel_ids[parcel_idx]

            for j in range(distances.shape[1] if len(distances.shape) > 1 else 1):
                dist = distances[i, j] if len(distances.shape) > 1 else distances[i]
                idx = indices[i, j] if len(indices.shape) > 1 else indices[i]

                if dist < threshold and idx < len(poi_ids):
                    relations.append({
                        'parcel_id': parcel_id,
                        'poi_id': poi_ids[idx],
                        'distance_m': round(dist, 1)
                    })

        if (batch_end) % 50000 == 0 or batch_end >= total_parcels:
            logger.info(f"    Processed {batch_end:,} / {total_parcels:,} parcels, {len(relations):,} relations found")

    logger.info(f"    Total relations to create: {len(relations):,}")

    # Create relations in Neo4j
    if relations:
        query = f"""
        UNWIND $batch AS row
        MATCH (p:Parcel {{id_dzialki: row.parcel_id}})
        MATCH (poi:{poi_type} {{id: row.poi_id}})
        MERGE (p)-[r:{rel_type}]->(poi)
        SET r.distance_m = row.distance_m
        """

        for i in range(0, len(relations), BATCH_SIZE):
            batch = relations[i:i + BATCH_SIZE]
            session.run(query, {"batch": batch})
            if (i + BATCH_SIZE) % 20000 == 0 or i + BATCH_SIZE >= len(relations):
                logger.info(f"    Created {min(i + BATCH_SIZE, len(relations)):,} / {len(relations):,} relations")

    return len(relations)


def verify_relations(session):
    """Verify created relations."""
    logger.info("\n" + "=" * 60)
    logger.info("WERYFIKACJA RELACJI POI")
    logger.info("=" * 60)

    for poi_type, config in POI_THRESHOLDS.items():
        rel_type = config['relation_type']
        result = session.run(f"""
            MATCH ()-[r:{rel_type}]->()
            RETURN count(r) as cnt, avg(r.distance_m) as avg_dist, min(r.distance_m) as min_dist, max(r.distance_m) as max_dist
        """)
        record = result.single()
        if record['cnt'] > 0:
            logger.info(f"  {rel_type}: {record['cnt']:,} relations")
            logger.info(f"    Distance: min={record['min_dist']:.0f}m, avg={record['avg_dist']:.0f}m, max={record['max_dist']:.0f}m")


def show_summary(session):
    """Show summary of POI relations."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE RELACJI POI")
    logger.info("=" * 60)

    # Count relations
    result = session.run("""
        CALL db.relationshipTypes() YIELD relationshipType
        CALL {
            WITH relationshipType
            MATCH ()-[r]->()
            WHERE type(r) = relationshipType AND type(r) STARTS WITH 'NEAR_'
            RETURN count(r) AS cnt
        }
        RETURN relationshipType, cnt
        ORDER BY cnt DESC
    """)

    total = 0
    for record in result:
        if record['cnt'] > 0:
            logger.info(f"  {record['relationshipType']}: {record['cnt']:,}")
            total += record['cnt']
    logger.info(f"\n  RAZEM NEAR_* relacji: {total:,}")

    # Sample query
    logger.info("\n  Przykładowa działka z POI:")
    result = session.run("""
        MATCH (p:Parcel)-[r:NEAR_SCHOOL]->(s:School)
        WHERE p.quietness_score > 70
        RETURN p.id_dzialki, s.name, r.distance_m
        LIMIT 3
    """)
    for record in result:
        logger.info(f"    {record['p.id_dzialki']} -> {record['s.name']} ({record['r.distance_m']}m)")


def main():
    logger.info("=" * 60)
    logger.info("TWORZENIE RELACJI NEAR_* Z ODLEGŁOŚCIAMI")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"CSV Path: {CSV_PATH}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Load parcel centroids once
            parcel_coords, parcel_ids = load_parcel_centroids(session)

            if len(parcel_ids) == 0:
                logger.error("No parcel centroids found. Run 24_import_parcels_v2.py first.")
                return

            # Process each POI type
            for poi_type, config in POI_THRESHOLDS.items():
                logger.info(f"\n" + "=" * 60)
                logger.info(f"PROCESSING {poi_type.upper()}")
                logger.info("=" * 60)

                # Import POI nodes if needed
                import_poi_nodes(session, poi_type, config)

                # Create relations
                create_poi_relations(session, poi_type, config, parcel_coords, parcel_ids)

            # Verify and summarize
            verify_relations(session)
            show_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("RELACJE POI ZAKOŃCZONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
