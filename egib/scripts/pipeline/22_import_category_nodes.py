#!/usr/bin/env python3
"""
22_import_category_nodes.py - Import dynamicznych węzłów kategorii

Importuje kategorie których wartości pochodzą z danych:
- BuildingType (30+): ekstrahowane z kolumny building_type w parcels_full.csv
- Weryfikuje spójność z węzłami utworzonymi w 21_create_neo4j_schema_v2.py

Węzły statyczne (utworzone w skrypcie 21):
- OwnershipType (5)
- OwnershipGroup (15)
- BuildStatus (2)
- BuildingFunction (11)
- SizeCategory (4)
- POGProfile (15)
- QuietnessCategory (4)
- NatureCategory (4)
- AccessCategory (4)
- DensityCategory (4)
- WaterType (6)
- PriceSegment (6)
"""

import csv
import os
import sys
from pathlib import Path
from collections import Counter

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
CSV_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j" / "csv"


def run_query(session, query: str, params: dict = None, description: str = ""):
    """Execute a Cypher query and log result."""
    try:
        result = session.run(query, params or {})
        summary = result.consume()
        if description:
            logger.info(f"  {description}")
        return True
    except Exception as e:
        logger.error(f"  Error ({description}): {e}")
        return False


def extract_building_types(csv_path: Path) -> list:
    """Extract unique building types from CSV."""
    logger.info("\n  Extracting building types from CSV...")

    building_types = Counter()
    with open(csv_path / "parcels_full.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bt = row.get('building_type', '').strip()
            if bt and bt != 'None':
                building_types[bt] += 1

    logger.info(f"  Found {len(building_types)} unique building types")
    return building_types


def import_building_types(session, building_types: Counter):
    """Import BuildingType nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT BUILDING TYPE NODES")
    logger.info("=" * 60)

    # Map building types to residential flag
    residential_types = {
        'budynek jednorodzinny', 'budynek wielorodzinny', 'dom letniskowy',
        'budynek mieszkalny', 'blok mieszkalny'
    }

    for bt, count in sorted(building_types.items(), key=lambda x: -x[1]):
        # Create normalized ID
        bt_id = bt.lower().replace(' ', '_').replace('-', '_')

        is_residential = bt.lower() in residential_types

        query = """
        MERGE (b:BuildingType {id: $id})
        SET b.name_pl = $name_pl,
            b.is_residential = $is_residential,
            b.parcel_count = $parcel_count
        """
        params = {
            "id": bt_id,
            "name_pl": bt,
            "is_residential": is_residential,
            "parcel_count": count
        }
        run_query(session, query, params, f"BuildingType: {bt} ({count:,} działek)")

    logger.info(f"\n  Imported {len(building_types)} BuildingType nodes")


def verify_category_nodes(session):
    """Verify all category nodes exist."""
    logger.info("\n" + "=" * 60)
    logger.info("WERYFIKACJA WĘZŁÓW KATEGORII")
    logger.info("=" * 60)

    categories = [
        ("OwnershipType", 5),
        ("OwnershipGroup", 15),
        ("BuildStatus", 2),
        ("BuildingFunction", 10),
        ("BuildingType", 20),  # minimum expected
        ("SizeCategory", 4),
        ("POGProfile", 15),
        ("QuietnessCategory", 4),
        ("NatureCategory", 4),
        ("AccessCategory", 4),
        ("DensityCategory", 4),
        ("WaterType", 6),
        ("PriceSegment", 6),
    ]

    all_ok = True
    for label, min_expected in categories:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) as cnt")
        record = result.single()
        count = record['cnt']

        status = "OK" if count >= min_expected else "MISSING"
        if count < min_expected:
            all_ok = False

        logger.info(f"  {label}: {count} węzłów ({status})")

    return all_ok


def create_ownership_group_relations(session):
    """Create BELONGS_TO_TYPE relations between OwnershipGroup and OwnershipType."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI OwnershipGroup -> OwnershipType")
    logger.info("=" * 60)

    query = """
    MATCH (og:OwnershipGroup)
    WHERE og.ownership_type IS NOT NULL
    MATCH (ot:OwnershipType {id: og.ownership_type})
    MERGE (og)-[:BELONGS_TO_TYPE]->(ot)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  Created {record['cnt']} BELONGS_TO_TYPE relations")


def show_summary(session):
    """Show summary of category nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE WĘZŁÓW KATEGORII")
    logger.info("=" * 60)

    # Count all category nodes
    category_labels = [
        "OwnershipType", "OwnershipGroup", "BuildStatus", "BuildingFunction",
        "BuildingType", "SizeCategory", "POGProfile", "QuietnessCategory",
        "NatureCategory", "AccessCategory", "DensityCategory", "WaterType", "PriceSegment"
    ]

    total = 0
    for label in category_labels:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) as cnt")
        record = result.single()
        count = record['cnt']
        total += count
        logger.info(f"  {label}: {count}")

    logger.info(f"\n  RAZEM: {total} węzłów kategorii")

    # Top BuildingTypes
    logger.info("\n  Top 10 BuildingType (by parcel count):")
    result = session.run("""
        MATCH (b:BuildingType)
        RETURN b.name_pl as name, b.parcel_count as cnt
        ORDER BY b.parcel_count DESC
        LIMIT 10
    """)
    for record in result:
        logger.info(f"    {record['name']}: {record['cnt']:,}")


def main():
    logger.info("=" * 60)
    logger.info("IMPORT WĘZŁÓW KATEGORII")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"CSV Path: {CSV_PATH}")

    # Check CSV exists
    if not (CSV_PATH / "parcels_full.csv").exists():
        logger.error(f"CSV not found: {CSV_PATH / 'parcels_full.csv'}")
        logger.error("Run 13_export_full_csv.py first")
        sys.exit(1)

    # Extract building types
    building_types = extract_building_types(CSV_PATH)

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Import building types
            import_building_types(session, building_types)

            # Create relations
            create_ownership_group_relations(session)

            # Verify
            verify_category_nodes(session)

            # Summary
            show_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("IMPORT KATEGORII ZAKOŃCZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
