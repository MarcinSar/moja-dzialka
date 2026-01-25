#!/usr/bin/env python3
"""
27_create_adjacency_relations.py - Tworzenie relacji sąsiedztwa między działkami

Tworzy relacje ADJACENT_TO między działkami, które dzielą wspólną granicę.
Wymagane dla:
- Community detection (Louvain algorithm)
- Graph-based clustering
- Neighborhood analysis

Algorytm:
1. Załaduj geometrie działek z GeoPackage
2. Użyj spatial index (STRtree) do szybkiego wyszukiwania kandydatów
3. Dla każdej pary sprawdź ST_Touches (wspólna granica)
4. Oblicz długość wspólnej granicy
5. Utwórz relację ADJACENT_TO z właściwością shared_border_m

Relacja:
(p1:Parcel)-[:ADJACENT_TO {shared_border_m: 45.3}]->(p2:Parcel)

UWAGA: Ten skrypt może zająć dużo czasu (2-4h) i pamięci (~16GB RAM).
Zaleca się uruchomienie z parametrem --district dla pojedynczej dzielnicy.

Użycie:
    python 27_create_adjacency_relations.py                    # wszystkie
    python 27_create_adjacency_relations.py --district Osowa   # pojedyncza dzielnica
    python 27_create_adjacency_relations.py --limit 10000      # pierwsze N działek
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import argparse

import geopandas as gpd
import numpy as np
from shapely.strtree import STRtree
from shapely.geometry import LineString
from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
PARCELS_GPKG = BASE_PATH / "data" / "ready-for-import" / "postgis" / "parcels_enriched.gpkg"

# Batch size
BATCH_SIZE = 5000


def load_parcels(gpkg_path: Path, district: str = None, limit: int = None) -> gpd.GeoDataFrame:
    """Load parcel geometries from GeoPackage."""
    logger.info(f"Loading parcels from: {gpkg_path}")

    if not gpkg_path.exists():
        logger.error(f"File not found: {gpkg_path}")
        sys.exit(1)

    gdf = gpd.read_file(gpkg_path)
    logger.info(f"  Loaded {len(gdf):,} parcels")

    # Filter by district if specified
    if district:
        gdf = gdf[gdf['dzielnica'] == district]
        logger.info(f"  Filtered to {len(gdf):,} parcels in {district}")

    # Limit if specified
    if limit and limit < len(gdf):
        gdf = gdf.head(limit)
        logger.info(f"  Limited to {len(gdf):,} parcels")

    # Ensure valid geometries
    gdf = gdf[gdf.geometry.is_valid]
    logger.info(f"  Valid geometries: {len(gdf):,}")

    return gdf


def find_adjacent_pairs(gdf: gpd.GeoDataFrame) -> List[Tuple[str, str, float]]:
    """Find all pairs of adjacent parcels using spatial index."""
    logger.info("\nFinding adjacent parcel pairs...")

    # Build spatial index
    logger.info("  Building spatial index...")

    # Get geometry and ID arrays for efficient access
    geometries = gdf.geometry.values
    parcel_ids = gdf['id_dzialki'].values

    tree = STRtree(geometries)

    # Find adjacent pairs
    adjacent_pairs = []
    processed_pairs: Set[Tuple[str, str]] = set()

    total = len(gdf)
    for idx in range(total):
        parcel_id = parcel_ids[idx]
        geom = geometries[idx]

        # Query spatial index for candidates - returns INDICES in Shapely 2.0+
        candidate_indices = tree.query(geom)

        for cand_idx in candidate_indices:
            # Skip self
            if cand_idx == idx:
                continue

            cand_id = parcel_ids[cand_idx]
            cand_geom = geometries[cand_idx]

            # Create canonical pair key (sorted IDs)
            pair_key = tuple(sorted([parcel_id, cand_id]))
            if pair_key in processed_pairs:
                continue

            processed_pairs.add(pair_key)

            # Check if they share a boundary (touches OR intersects boundary)
            # Using touches() is too strict - parcels with tiny overlaps won't match
            # Check if boundaries intersect instead
            try:
                # First quick check: do bounding boxes touch?
                if not geom.intersects(cand_geom):
                    continue

                # Check if it's a true adjacency (boundary touches boundary)
                # Not a full overlap (which would mean data error)
                intersection = geom.intersection(cand_geom)

                if intersection.is_empty:
                    continue

                # For adjacency, intersection should be 1-dimensional (line/multiline)
                # not 2-dimensional (polygon overlap)
                if intersection.geom_type in ('Polygon', 'MultiPolygon'):
                    # This is an overlap, not adjacency - skip
                    # (or could be data error)
                    continue

                # Get length of shared boundary
                if hasattr(intersection, 'length') and intersection.length > 0.1:  # >10cm
                    shared_border = intersection.length
                    adjacent_pairs.append((parcel_id, cand_id, round(shared_border, 2)))

            except Exception as e:
                logger.debug(f"  Error processing pair {pair_key}: {e}")
                continue

        if (idx + 1) % 10000 == 0 or idx + 1 == total:
            logger.info(f"  Processed {idx + 1:,} / {total:,} parcels, found {len(adjacent_pairs):,} pairs")

    logger.info(f"\nTotal adjacent pairs found: {len(adjacent_pairs):,}")
    return adjacent_pairs


def create_adjacency_relations(session, pairs: List[Tuple[str, str, float]]):
    """Create ADJACENT_TO relations in Neo4j."""
    logger.info("\nCreating ADJACENT_TO relations in Neo4j...")

    if not pairs:
        logger.warning("  No pairs to create")
        return

    # Create relations in batches
    query = """
    UNWIND $batch AS row
    MATCH (p1:Parcel {id_dzialki: row.id1})
    MATCH (p2:Parcel {id_dzialki: row.id2})
    MERGE (p1)-[r:ADJACENT_TO]->(p2)
    SET r.shared_border_m = row.border
    """

    total = len(pairs)
    for i in range(0, total, BATCH_SIZE):
        batch = [{"id1": p[0], "id2": p[1], "border": p[2]} for p in pairs[i:i + BATCH_SIZE]]
        session.run(query, {"batch": batch})

        if (i + BATCH_SIZE) % 20000 == 0 or i + BATCH_SIZE >= total:
            logger.info(f"  Created {min(i + BATCH_SIZE, total):,} / {total:,} relations")

    logger.info(f"Created {total:,} ADJACENT_TO relations")


def verify_relations(session):
    """Verify adjacency relations."""
    logger.info("\nVerifying ADJACENT_TO relations...")

    # Count relations
    result = session.run("""
        MATCH ()-[r:ADJACENT_TO]->()
        RETURN count(r) as cnt, avg(r.shared_border_m) as avg_border
    """)
    record = result.single()
    logger.info(f"  Total relations: {record['cnt']:,}")
    if record['avg_border']:
        logger.info(f"  Average shared border: {record['avg_border']:.1f}m")

    # Sample path
    logger.info("\n  Sample adjacency path:")
    result = session.run("""
        MATCH path = (p1:Parcel)-[:ADJACENT_TO*1..3]-(p2:Parcel)
        WHERE p1.dzielnica = p2.dzielnica
        RETURN p1.id_dzialki, p2.id_dzialki, length(path) as hops, p1.dzielnica
        LIMIT 1
    """)
    record = result.single()
    if record:
        logger.info(f"    From {record['p1.id_dzialki']} to {record['p2.id_dzialki']}")
        logger.info(f"    Hops: {record['hops']}, District: {record['p1.dzielnica']}")


def analyze_graph_stats(session):
    """Analyze graph connectivity statistics."""
    logger.info("\nGraph connectivity statistics:")

    # Degree distribution
    result = session.run("""
        MATCH (p:Parcel)
        OPTIONAL MATCH (p)-[r:ADJACENT_TO]-()
        WITH p, count(r) as degree
        RETURN
            min(degree) as min_degree,
            max(degree) as max_degree,
            avg(degree) as avg_degree,
            percentileCont(degree, 0.5) as median_degree
    """)
    record = result.single()
    logger.info(f"  Degree: min={record['min_degree']}, max={record['max_degree']}, avg={record['avg_degree']:.1f}, median={record['median_degree']}")

    # Connected components (requires GDS)
    logger.info("\n  Note: For community detection, run:")
    logger.info("    CALL gds.graph.project('parcel-adjacency', 'Parcel', 'ADJACENT_TO')")
    logger.info("    CALL gds.louvain.stream('parcel-adjacency') YIELD nodeId, communityId")


def main():
    parser = argparse.ArgumentParser(description="Create adjacency relations")
    parser.add_argument("--district", type=str, help="Process only this district")
    parser.add_argument("--limit", type=int, help="Limit number of parcels")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TWORZENIE RELACJI SĄSIEDZTWA (ADJACENT_TO)")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"GeoPackage: {PARCELS_GPKG}")
    if args.district:
        logger.info(f"District filter: {args.district}")
    if args.limit:
        logger.info(f"Limit: {args.limit}")

    # Load parcels
    gdf = load_parcels(PARCELS_GPKG, args.district, args.limit)

    if len(gdf) == 0:
        logger.error("No parcels loaded")
        return

    # Find adjacent pairs
    pairs = find_adjacent_pairs(gdf)

    if len(pairs) == 0:
        logger.warning("No adjacent pairs found")
        return

    # Connect to Neo4j and create relations
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            create_adjacency_relations(session, pairs)
            verify_relations(session)
            analyze_graph_stats(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("RELACJE SĄSIEDZTWA UTWORZONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
