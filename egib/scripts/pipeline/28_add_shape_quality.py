#!/usr/bin/env python3
"""
28_add_shape_quality.py - Pre-compute aspect_ratio for shape quality filtering

Adds aspect_ratio column to PostGIS and Neo4j:
    aspect_ratio = max(bbox_width, bbox_height) / min(bbox_width, bbox_height)

Used by search_parcels() for:
- Hard filter: aspect_ratio <= 6.0 (exclude extreme road strips)
- Soft scoring: compact parcels get ranking bonus

Usage:
    python 28_add_shape_quality.py              # PostGIS + Neo4j
    python 28_add_shape_quality.py --postgis    # PostGIS only
    python 28_add_shape_quality.py --neo4j      # Neo4j only
"""

import os
import sys
import argparse

from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# PostGIS connection
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "moja_dzialka")
PG_USER = os.getenv("POSTGRES_USER", "app")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "secret")


def update_postgis():
    """Add aspect_ratio column to PostGIS parcels table."""
    import psycopg2

    logger.info("Connecting to PostGIS...")
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Add column if not exists
    logger.info("Adding aspect_ratio column...")
    cur.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS aspect_ratio DOUBLE PRECISION;")

    # Compute aspect_ratio
    logger.info("Computing aspect_ratio...")
    cur.execute("""
        UPDATE parcels SET aspect_ratio =
            CASE WHEN LEAST(bbox_width, bbox_height) > 0
                 THEN GREATEST(bbox_width, bbox_height) / LEAST(bbox_width, bbox_height)
                 ELSE NULL END
        WHERE bbox_width IS NOT NULL AND bbox_height IS NOT NULL;
    """)
    updated = cur.rowcount
    logger.info(f"Updated {updated:,} rows in PostGIS")

    # Verify
    cur.execute("SELECT count(*) FROM parcels WHERE aspect_ratio IS NOT NULL;")
    total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM parcels WHERE aspect_ratio > 6;")
    extreme = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM parcels WHERE shape_index < 0.15;")
    irregular = cur.fetchone()[0]
    cur.execute("SELECT avg(aspect_ratio), percentile_cont(0.5) WITHIN GROUP (ORDER BY aspect_ratio) FROM parcels WHERE aspect_ratio IS NOT NULL;")
    avg_ar, median_ar = cur.fetchone()

    logger.info(f"PostGIS results:")
    logger.info(f"  Total with aspect_ratio: {total:,}")
    logger.info(f"  Extreme (aspect_ratio > 6): {extreme:,} ({extreme/total*100:.1f}%)")
    logger.info(f"  Irregular (shape_index < 0.15): {irregular:,} ({irregular/total*100:.1f}%)")
    logger.info(f"  Mean aspect_ratio: {avg_ar:.2f}, Median: {median_ar:.2f}")

    cur.close()
    conn.close()


def update_neo4j():
    """Add aspect_ratio property to Neo4j Parcel nodes."""
    from neo4j import GraphDatabase

    logger.info("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Compute aspect_ratio for all parcels with bbox data
        logger.info("Computing aspect_ratio on Neo4j Parcel nodes...")
        result = session.run("""
            MATCH (p:Parcel)
            WHERE p.bbox_width IS NOT NULL AND p.bbox_height IS NOT NULL
              AND p.bbox_width > 0 AND p.bbox_height > 0
            SET p.aspect_ratio = CASE
                WHEN p.bbox_width >= p.bbox_height
                THEN p.bbox_width / p.bbox_height
                ELSE p.bbox_height / p.bbox_width END
            RETURN count(p) as updated
        """)
        updated = result.single()["updated"]
        logger.info(f"Updated {updated:,} Parcel nodes in Neo4j")

        # Verify
        result = session.run("""
            MATCH (p:Parcel) WHERE p.aspect_ratio IS NOT NULL
            RETURN count(p) as total,
                   avg(p.aspect_ratio) as avg_ar,
                   sum(CASE WHEN p.aspect_ratio > 6 THEN 1 ELSE 0 END) as extreme,
                   sum(CASE WHEN p.shape_index < 0.15 THEN 1 ELSE 0 END) as irregular
        """)
        r = result.single()
        logger.info(f"Neo4j results:")
        logger.info(f"  Total with aspect_ratio: {r['total']:,}")
        logger.info(f"  Extreme (aspect_ratio > 6): {r['extreme']:,}")
        logger.info(f"  Irregular (shape_index < 0.15): {r['irregular']:,}")
        logger.info(f"  Mean aspect_ratio: {r['avg_ar']:.2f}")

    driver.close()


def main():
    parser = argparse.ArgumentParser(description="Add aspect_ratio to PostGIS + Neo4j")
    parser.add_argument("--postgis", action="store_true", help="PostGIS only")
    parser.add_argument("--neo4j", action="store_true", help="Neo4j only")
    args = parser.parse_args()

    do_both = not args.postgis and not args.neo4j

    if do_both or args.postgis:
        update_postgis()

    if do_both or args.neo4j:
        update_neo4j()

    logger.info("Done!")


if __name__ == "__main__":
    main()
