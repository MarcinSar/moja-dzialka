#!/usr/bin/env python3
"""
06_import_neo4j.py - Import parcel data to Neo4j Knowledge Graph

This script creates a knowledge graph in Neo4j with:
- Parcel nodes (basic attributes, no geometry)
- Administrative hierarchy (Wojewodztwo -> Powiat -> Gmina -> Miejscowosc)
- MPZP zones and relationships
- POI proximity relationships

Usage:
    python 06_import_neo4j.py --sample    # Import dev sample (10k parcels)
    python 06_import_neo4j.py             # Import full dataset (1.3M parcels)

Requirements:
    - Neo4j database running (docker-compose up neo4j)
    - Data files in data/dev/ or data/processed/v1.0.0/

Environment variables (or .env file):
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=secret
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd
import geopandas as gpd
from loguru import logger
from neo4j import GraphDatabase

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.config import (
    DEV_DATA_DIR,
    PROCESSED_DATA_DIR,
    PARCEL_FEATURES_GPKG,
    MPZP_SYMBOLS,
    MPZP_BUILDABLE,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default Neo4j connection (override via environment)
NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "secret"),
}

# Batch size for imports
BATCH_SIZE = 1000


# =============================================================================
# NEO4J DRIVER
# =============================================================================

class Neo4jConnection:
    """Neo4j connection wrapper."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_connectivity(self) -> bool:
        """Test connection to Neo4j."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False

    def run_query(self, query: str, parameters: dict = None):
        """Run a single Cypher query."""
        with self.driver.session() as session:
            return session.run(query, parameters or {})

    def run_batch(self, query: str, data: List[dict], batch_size: int = BATCH_SIZE):
        """Run query in batches using UNWIND."""
        total = len(data)
        for i in range(0, total, batch_size):
            batch = data[i:i + batch_size]
            with self.driver.session() as session:
                session.run(query, {"batch": batch})
            if (i + batch_size) % (batch_size * 10) == 0:
                logger.debug(f"Processed {min(i + batch_size, total):,}/{total:,}")


# =============================================================================
# SCHEMA CREATION
# =============================================================================

def create_constraints(conn: Neo4jConnection):
    """Create uniqueness constraints and indexes."""
    logger.info("Creating constraints and indexes...")

    constraints = [
        # Unique constraints
        "CREATE CONSTRAINT dzialka_id IF NOT EXISTS FOR (d:Dzialka) REQUIRE d.id_dzialki IS UNIQUE",
        "CREATE CONSTRAINT wojewodztwo_name IF NOT EXISTS FOR (w:Wojewodztwo) REQUIRE w.name IS UNIQUE",
        "CREATE CONSTRAINT powiat_name IF NOT EXISTS FOR (p:Powiat) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT gmina_name IF NOT EXISTS FOR (g:Gmina) REQUIRE g.name IS UNIQUE",
        "CREATE CONSTRAINT miejscowosc_id IF NOT EXISTS FOR (m:Miejscowosc) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT mpzp_symbol IF NOT EXISTS FOR (s:SymbolMPZP) REQUIRE s.kod IS UNIQUE",

        # Performance indexes
        "CREATE INDEX dzialka_gmina IF NOT EXISTS FOR (d:Dzialka) ON (d.gmina)",
        "CREATE INDEX dzialka_area IF NOT EXISTS FOR (d:Dzialka) ON (d.area_m2)",
        "CREATE INDEX dzialka_quietness IF NOT EXISTS FOR (d:Dzialka) ON (d.quietness_score)",
        "CREATE INDEX dzialka_nature IF NOT EXISTS FOR (d:Dzialka) ON (d.nature_score)",
        "CREATE INDEX dzialka_has_mpzp IF NOT EXISTS FOR (d:Dzialka) ON (d.has_mpzp)",
    ]

    for constraint in constraints:
        try:
            conn.run_query(constraint)
        except Exception as e:
            # Constraint may already exist
            logger.debug(f"Constraint: {e}")

    logger.info("Constraints and indexes created")


def clear_database(conn: Neo4jConnection):
    """Clear all data from Neo4j."""
    logger.info("Clearing existing data...")

    # Delete in batches to avoid memory issues
    queries = [
        "MATCH (d:Dzialka) DETACH DELETE d",
        "MATCH (m:Miejscowosc) DETACH DELETE m",
        "MATCH (g:Gmina) DETACH DELETE g",
        "MATCH (p:Powiat) DETACH DELETE p",
        "MATCH (w:Wojewodztwo) DETACH DELETE w",
        "MATCH (s:SymbolMPZP) DETACH DELETE s",
    ]

    for query in queries:
        try:
            # Use CALL { ... } IN TRANSACTIONS for large deletes
            batch_query = f"""
                CALL {{
                    {query}
                }} IN TRANSACTIONS OF 10000 ROWS
            """
            conn.run_query(batch_query)
        except Exception:
            # Fallback for older Neo4j versions
            conn.run_query(query)

    logger.info("Database cleared")


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(sample: bool = False) -> gpd.GeoDataFrame:
    """Load parcel data from file."""
    if sample:
        filepath = DEV_DATA_DIR / "parcels_dev.gpkg"
        logger.info(f"Loading DEV sample from {filepath}")
    else:
        filepath = PARCEL_FEATURES_GPKG
        logger.info(f"Loading FULL dataset from {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    gdf = gpd.read_file(filepath)
    logger.info(f"Loaded {len(gdf):,} parcels")

    return gdf


# =============================================================================
# NODE CREATION
# =============================================================================

def create_administrative_hierarchy(conn: Neo4jConnection, df: pd.DataFrame):
    """
    Create administrative hierarchy nodes:
    Wojewodztwo -> Powiat -> Gmina -> Miejscowosc
    """
    logger.info("Creating administrative hierarchy...")

    # Create Wojewodztwo (should be just 'pomorskie')
    wojewodztwa = df["wojewodztwo"].dropna().unique()
    for woj in wojewodztwa:
        conn.run_query(
            "MERGE (w:Wojewodztwo {name: $name})",
            {"name": woj}
        )
    logger.info(f"Created {len(wojewodztwa)} wojewodztwo nodes")

    # Create Powiaty
    powiaty = df[["powiat", "wojewodztwo"]].drop_duplicates().dropna()
    for _, row in powiaty.iterrows():
        conn.run_query(
            """
            MATCH (w:Wojewodztwo {name: $woj})
            MERGE (p:Powiat {name: $powiat})
            MERGE (p)-[:W_WOJEWODZTWIE]->(w)
            """,
            {"powiat": row["powiat"], "woj": row["wojewodztwo"]}
        )
    logger.info(f"Created {len(powiaty)} powiat nodes")

    # Create Gminy
    gminy = df[["gmina", "powiat"]].drop_duplicates().dropna()
    for _, row in gminy.iterrows():
        conn.run_query(
            """
            MATCH (p:Powiat {name: $powiat})
            MERGE (g:Gmina {name: $gmina})
            MERGE (g)-[:W_POWIECIE]->(p)
            """,
            {"gmina": row["gmina"], "powiat": row["powiat"]}
        )
    logger.info(f"Created {len(gminy)} gmina nodes")

    # Create Miejscowosci
    miejscowosci = df[["miejscowosc", "gmina", "rodzaj_miejscowosci"]].drop_duplicates()
    miejscowosci = miejscowosci[miejscowosci["miejscowosc"].notna()]

    miejscowosc_data = []
    for _, row in miejscowosci.iterrows():
        miejscowosc_data.append({
            "id": f"{row['miejscowosc']}_{row['gmina']}",
            "name": row["miejscowosc"],
            "gmina": row["gmina"],
            "rodzaj": row.get("rodzaj_miejscowosci", ""),
        })

    if miejscowosc_data:
        conn.run_batch(
            """
            UNWIND $batch AS m
            MATCH (g:Gmina {name: m.gmina})
            MERGE (msc:Miejscowosc {id: m.id})
            SET msc.name = m.name, msc.rodzaj = m.rodzaj
            MERGE (msc)-[:W_GMINIE]->(g)
            """,
            miejscowosc_data
        )
    logger.info(f"Created {len(miejscowosc_data)} miejscowosc nodes")


def create_mpzp_symbols(conn: Neo4jConnection):
    """Create MPZP symbol nodes from config."""
    logger.info("Creating MPZP symbol nodes...")

    for kod, nazwa in MPZP_SYMBOLS.items():
        is_buildable = kod in MPZP_BUILDABLE
        conn.run_query(
            """
            MERGE (s:SymbolMPZP {kod: $kod})
            SET s.nazwa = $nazwa, s.budowlany = $buildable
            """,
            {"kod": kod, "nazwa": nazwa, "buildable": is_buildable}
        )

    logger.info(f"Created {len(MPZP_SYMBOLS)} MPZP symbol nodes")


def create_parcel_nodes(conn: Neo4jConnection, df: pd.DataFrame):
    """Create Dzialka nodes with attributes."""
    logger.info(f"Creating {len(df):,} parcel nodes...")

    start_time = time.time()

    # Prepare parcel data
    parcel_data = []
    for _, row in df.iterrows():
        parcel = {
            "id_dzialki": row["ID_DZIALKI"],
            "teryt_powiat": row.get("TERYT_POWIAT"),
            "area_m2": float(row["area_m2"]) if pd.notna(row.get("area_m2")) else None,
            "gmina": row.get("gmina"),
            "miejscowosc": row.get("miejscowosc"),
            "centroid_lat": float(row["centroid_lat"]) if pd.notna(row.get("centroid_lat")) else None,
            "centroid_lon": float(row["centroid_lon"]) if pd.notna(row.get("centroid_lon")) else None,

            # Scores
            "quietness_score": float(row["quietness_score"]) if pd.notna(row.get("quietness_score")) else None,
            "nature_score": float(row["nature_score"]) if pd.notna(row.get("nature_score")) else None,
            "accessibility_score": float(row["accessibility_score"]) if pd.notna(row.get("accessibility_score")) else None,

            # MPZP
            "has_mpzp": bool(row["has_mpzp"]) if pd.notna(row.get("has_mpzp")) else False,
            "mpzp_symbol": row.get("mpzp_symbol") if pd.notna(row.get("mpzp_symbol")) else None,
            "mpzp_czy_budowlane": bool(row["mpzp_czy_budowlane"]) if pd.notna(row.get("mpzp_czy_budowlane")) else None,

            # Key distances
            "dist_to_school": float(row["dist_to_school"]) if pd.notna(row.get("dist_to_school")) else None,
            "dist_to_forest": float(row["dist_to_forest"]) if pd.notna(row.get("dist_to_forest")) else None,
            "dist_to_water": float(row["dist_to_water"]) if pd.notna(row.get("dist_to_water")) else None,

            # Road access
            "has_public_road_access": bool(row["has_public_road_access"]) if pd.notna(row.get("has_public_road_access")) else None,
        }
        parcel_data.append(parcel)

    # Batch insert parcels
    conn.run_batch(
        """
        UNWIND $batch AS p
        CREATE (d:Dzialka {
            id_dzialki: p.id_dzialki,
            teryt_powiat: p.teryt_powiat,
            area_m2: p.area_m2,
            gmina: p.gmina,
            miejscowosc: p.miejscowosc,
            centroid_lat: p.centroid_lat,
            centroid_lon: p.centroid_lon,
            quietness_score: p.quietness_score,
            nature_score: p.nature_score,
            accessibility_score: p.accessibility_score,
            has_mpzp: p.has_mpzp,
            mpzp_symbol: p.mpzp_symbol,
            mpzp_czy_budowlane: p.mpzp_czy_budowlane,
            dist_to_school: p.dist_to_school,
            dist_to_forest: p.dist_to_forest,
            dist_to_water: p.dist_to_water,
            has_public_road_access: p.has_public_road_access
        })
        """,
        parcel_data,
        batch_size=BATCH_SIZE
    )

    elapsed = time.time() - start_time
    logger.info(f"Created {len(df):,} parcel nodes in {elapsed:.1f}s")


# =============================================================================
# RELATIONSHIP CREATION
# =============================================================================

def create_parcel_relationships(conn: Neo4jConnection, df: pd.DataFrame):
    """Create relationships between parcels and other nodes."""
    logger.info("Creating parcel relationships...")

    start_time = time.time()

    # Relationship: Dzialka -> Miejscowosc
    logger.info("Creating Dzialka -> Miejscowosc relationships...")
    miejscowosc_rels = []
    for _, row in df.iterrows():
        if pd.notna(row.get("miejscowosc")) and pd.notna(row.get("gmina")):
            miejscowosc_rels.append({
                "id_dzialki": row["ID_DZIALKI"],
                "miejscowosc_id": f"{row['miejscowosc']}_{row['gmina']}"
            })

    if miejscowosc_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (m:Miejscowosc {id: r.miejscowosc_id})
            MERGE (d)-[:W_MIEJSCOWOSCI]->(m)
            """,
            miejscowosc_rels,
            batch_size=BATCH_SIZE
        )
    logger.info(f"Created {len(miejscowosc_rels):,} miejscowosc relationships")

    # Relationship: Dzialka -> Gmina (for parcels without miejscowosc)
    logger.info("Creating Dzialka -> Gmina relationships...")
    gmina_rels = []
    for _, row in df.iterrows():
        if pd.notna(row.get("gmina")):
            gmina_rels.append({
                "id_dzialki": row["ID_DZIALKI"],
                "gmina": row["gmina"]
            })

    if gmina_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (g:Gmina {name: r.gmina})
            MERGE (d)-[:W_GMINIE]->(g)
            """,
            gmina_rels,
            batch_size=BATCH_SIZE
        )
    logger.info(f"Created {len(gmina_rels):,} gmina relationships")

    # Relationship: Dzialka -> SymbolMPZP
    logger.info("Creating Dzialka -> SymbolMPZP relationships...")
    mpzp_rels = []
    for _, row in df.iterrows():
        if pd.notna(row.get("mpzp_symbol")):
            mpzp_rels.append({
                "id_dzialki": row["ID_DZIALKI"],
                "symbol": row["mpzp_symbol"]
            })

    if mpzp_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (s:SymbolMPZP {kod: r.symbol})
            MERGE (d)-[:MA_PRZEZNACZENIE]->(s)
            """,
            mpzp_rels,
            batch_size=BATCH_SIZE
        )
    logger.info(f"Created {len(mpzp_rels):,} MPZP relationships")

    elapsed = time.time() - start_time
    logger.info(f"All relationships created in {elapsed:.1f}s")


# =============================================================================
# STATISTICS
# =============================================================================

def print_statistics(conn: Neo4jConnection):
    """Print database statistics."""
    logger.info("\n" + "=" * 50)
    logger.info("NEO4J DATABASE STATISTICS")
    logger.info("=" * 50)

    queries = [
        ("Dzialka nodes", "MATCH (d:Dzialka) RETURN count(d) as count"),
        ("Gmina nodes", "MATCH (g:Gmina) RETURN count(g) as count"),
        ("Miejscowosc nodes", "MATCH (m:Miejscowosc) RETURN count(m) as count"),
        ("SymbolMPZP nodes", "MATCH (s:SymbolMPZP) RETURN count(s) as count"),
        ("W_GMINIE relationships", "MATCH ()-[r:W_GMINIE]->() RETURN count(r) as count"),
        ("W_MIEJSCOWOSCI relationships", "MATCH ()-[r:W_MIEJSCOWOSCI]->() RETURN count(r) as count"),
        ("MA_PRZEZNACZENIE relationships", "MATCH ()-[r:MA_PRZEZNACZENIE]->() RETURN count(r) as count"),
    ]

    for name, query in queries:
        result = conn.run_query(query)
        count = result.single()["count"]
        logger.info(f"  {name}: {count:,}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import parcel data to Neo4j Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 06_import_neo4j.py --sample           # Dev sample (10k parcels)
    python 06_import_neo4j.py                    # Full dataset (1.3M parcels)
    python 06_import_neo4j.py --sample --clear   # Clear and reimport sample
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use dev sample (10k parcels) instead of full dataset",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but don't import (for testing)",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("NEO4J IMPORT - moja-dzialka")
    logger.info("=" * 60)

    # Create connection
    logger.info(f"Connecting to {NEO4J_CONFIG['uri']}")
    conn = Neo4jConnection(
        uri=NEO4J_CONFIG["uri"],
        user=NEO4J_CONFIG["user"],
        password=NEO4J_CONFIG["password"],
    )

    # Test connection
    if not conn.verify_connectivity():
        logger.error("Cannot connect to Neo4j. Is Docker running?")
        logger.info("Start with: docker-compose up -d neo4j")
        sys.exit(1)

    logger.info("Connected to Neo4j")

    # Load data
    try:
        gdf = load_data(sample=args.sample)
    except FileNotFoundError as e:
        logger.error(str(e))
        conn.close()
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run - data loaded successfully, not importing")
        logger.info(f"Columns: {list(gdf.columns)}")
        conn.close()
        return

    # Clear existing data if requested
    if args.clear:
        clear_database(conn)

    # Create schema
    create_constraints(conn)

    # Import data
    start_time = time.time()

    create_mpzp_symbols(conn)
    create_administrative_hierarchy(conn, gdf)
    create_parcel_nodes(conn, gdf)
    create_parcel_relationships(conn, gdf)

    elapsed = time.time() - start_time
    logger.info(f"\nTotal import time: {elapsed:.1f}s")

    # Print statistics
    print_statistics(conn)

    # Sample queries
    logger.info("\nSample Cypher queries:")
    logger.info("  // Find parcels in Gdansk with high quietness score")
    logger.info("  MATCH (d:Dzialka)-[:W_GMINIE]->(g:Gmina {name: 'Gdańsk'})")
    logger.info("  WHERE d.quietness_score > 80")
    logger.info("  RETURN d.id_dzialki, d.area_m2, d.quietness_score LIMIT 10")

    conn.close()


if __name__ == "__main__":
    main()
