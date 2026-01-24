#!/usr/bin/env python3
"""
15_create_neo4j_schema.py - Tworzenie schematu Neo4j

Tworzy indeksy, constraints i węzły kategorialne dla grafu wiedzy:

Węzły (15 typów):
- Parcel (Działka) - 155k
- POGZone - 7.5k
- District (Dzielnica) - 109
- City (Gmina) - 3
- School, BusStop, Forest, Water, Shop, Road - POI
- QuietnessCategory, NatureCategory, AccessCategory, DensityCategory - kategorie
- WaterType, PriceSegment - kategorie

Relacje (15 typów):
- LOCATED_IN, BELONGS_TO, HAS_POG - hierarchia
- NEAR_SCHOOL, NEAR_BUS_STOP, NEAR_FOREST, NEAR_WATER, NEAR_SHOP, NEAR_ROAD - przestrzenne
- HAS_QUIETNESS, HAS_NATURE, HAS_ACCESS, HAS_DENSITY - kategorie
- WATER_IS_TYPE, IN_PRICE_SEGMENT - klasyfikacje
"""

import os
import sys
from pathlib import Path

# Add backend to path for config access
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection - use environment or defaults
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def run_query(session, query: str, params: dict = None, description: str = ""):
    """Execute a Cypher query and log result."""
    try:
        result = session.run(query, params or {})
        summary = result.consume()
        if description:
            logger.info(f"  {description}: {summary.counters}")
        return True
    except Exception as e:
        logger.error(f"  Error: {e}")
        return False


def create_constraints(session):
    """Create unique constraints for node IDs."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE CONSTRAINTS")
    logger.info("=" * 60)

    constraints = [
        ("Parcel", "id_dzialki"),
        ("District", "name"),
        ("City", "name"),
        ("POGZone", "id"),
        ("School", "id"),
        ("BusStop", "id"),
        ("Forest", "id"),
        ("Water", "id"),
        ("Shop", "id"),
        ("Road", "id"),
        ("QuietnessCategory", "id"),
        ("NatureCategory", "id"),
        ("AccessCategory", "id"),
        ("DensityCategory", "id"),
        ("WaterType", "id"),
        ("PriceSegment", "id"),
    ]

    for label, prop in constraints:
        query = f"""
        CREATE CONSTRAINT IF NOT EXISTS
        FOR (n:{label})
        REQUIRE n.{prop} IS UNIQUE
        """
        run_query(session, query, description=f"Constraint {label}.{prop}")


def create_indexes(session):
    """Create indexes for fast lookups."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE INDEKSÓW")
    logger.info("=" * 60)

    # Parcel property indexes
    parcel_indexes = [
        "gmina", "dzielnica", "area_m2", "is_built", "is_residential_zone",
        "quietness_score", "nature_score", "accessibility_score",
        "dist_to_sea", "dist_to_river", "dist_to_lake",
        "kategoria_ciszy", "kategoria_natury", "kategoria_dostepu", "gestosc_zabudowy",
        "nearest_water_type", "pog_symbol",
    ]

    for prop in parcel_indexes:
        query = f"""
        CREATE INDEX IF NOT EXISTS
        FOR (p:Parcel)
        ON (p.{prop})
        """
        run_query(session, query, description=f"Index Parcel.{prop}")

    # Composite indexes for common queries
    composite_indexes = [
        ("Parcel", ["gmina", "is_residential_zone"]),
        ("Parcel", ["gmina", "kategoria_ciszy"]),
        ("Parcel", ["dzielnica", "is_built"]),
    ]

    for label, props in composite_indexes:
        props_str = ", ".join([f"n.{p}" for p in props])
        idx_name = f"idx_{label.lower()}_{'_'.join(props)}"
        query = f"""
        CREATE INDEX {idx_name} IF NOT EXISTS
        FOR (n:{label})
        ON ({props_str})
        """
        run_query(session, query, description=f"Composite index {idx_name}")

    # Water indexes
    water_indexes = ["name", "water_type"]
    for prop in water_indexes:
        query = f"""
        CREATE INDEX IF NOT EXISTS
        FOR (w:Water)
        ON (w.{prop})
        """
        run_query(session, query, description=f"Index Water.{prop}")


def create_category_nodes(session):
    """Create category nodes for graph traversal."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE WĘZŁÓW KATEGORII")
    logger.info("=" * 60)

    # Quietness categories
    quietness = [
        {"id": "bardzo_cicha", "name_pl": "Bardzo cicha", "score_min": 80, "score_max": 100},
        {"id": "cicha", "name_pl": "Cicha", "score_min": 60, "score_max": 79},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 40, "score_max": 59},
        {"id": "glosna", "name_pl": "Głośna", "score_min": 0, "score_max": 39},
    ]
    for cat in quietness:
        query = """
        MERGE (c:QuietnessCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"QuietnessCategory: {cat['id']}")

    # Nature categories
    nature = [
        {"id": "bardzo_zielona", "name_pl": "Bardzo zielona", "score_min": 70, "score_max": 100},
        {"id": "zielona", "name_pl": "Zielona", "score_min": 50, "score_max": 69},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 30, "score_max": 49},
        {"id": "zurbanizowana", "name_pl": "Zurbanizowana", "score_min": 0, "score_max": 29},
    ]
    for cat in nature:
        query = """
        MERGE (c:NatureCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"NatureCategory: {cat['id']}")

    # Access categories
    access = [
        {"id": "doskonala", "name_pl": "Doskonała", "score_min": 70, "score_max": 100},
        {"id": "dobra", "name_pl": "Dobra", "score_min": 50, "score_max": 69},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 30, "score_max": 49},
        {"id": "ograniczona", "name_pl": "Ograniczona", "score_min": 0, "score_max": 29},
    ]
    for cat in access:
        query = """
        MERGE (c:AccessCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"AccessCategory: {cat['id']}")

    # Density categories
    density = [
        {"id": "gesta", "name_pl": "Gęsta", "buildings_min": 50, "buildings_max": 999999},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "buildings_min": 20, "buildings_max": 49},
        {"id": "rzadka", "name_pl": "Rzadka", "buildings_min": 5, "buildings_max": 19},
        {"id": "bardzo_rzadka", "name_pl": "Bardzo rzadka", "buildings_min": 0, "buildings_max": 4},
    ]
    for cat in density:
        query = """
        MERGE (c:DensityCategory {id: $id})
        SET c.name_pl = $name_pl, c.buildings_min = $buildings_min, c.buildings_max = $buildings_max
        """
        run_query(session, query, cat, f"DensityCategory: {cat['id']}")

    # Water type categories
    water_types = [
        {"id": "morze", "name_pl": "Morze", "priority": 1, "premium_factor": 2.0},
        {"id": "zatoka", "name_pl": "Zatoka", "priority": 2, "premium_factor": 1.8},
        {"id": "rzeka", "name_pl": "Rzeka", "priority": 3, "premium_factor": 1.3},
        {"id": "jezioro", "name_pl": "Jezioro", "priority": 4, "premium_factor": 1.5},
        {"id": "kanal", "name_pl": "Kanał", "priority": 5, "premium_factor": 1.1},
        {"id": "staw", "name_pl": "Staw", "priority": 6, "premium_factor": 1.05},
    ]
    for wt in water_types:
        query = """
        MERGE (w:WaterType {id: $id})
        SET w.name_pl = $name_pl, w.priority = $priority, w.premium_factor = $premium_factor
        """
        run_query(session, query, wt, f"WaterType: {wt['id']}")

    # Price segment categories
    price_segments = [
        {"id": "ULTRA_PREMIUM", "name_pl": "Ultra Premium", "price_min": 3000, "price_max": 999999, "locations": "Sopot centrum, Orłowo"},
        {"id": "PREMIUM", "name_pl": "Premium", "price_min": 1500, "price_max": 2999, "locations": "Jelitkowo, Oliwa"},
        {"id": "HIGH", "name_pl": "Wysoki", "price_min": 800, "price_max": 1499, "locations": "Wrzeszcz, Redłowo"},
        {"id": "MEDIUM", "name_pl": "Średni", "price_min": 500, "price_max": 799, "locations": "Osowa, Kokoszki"},
        {"id": "BUDGET", "name_pl": "Budżetowy", "price_min": 300, "price_max": 499, "locations": "Łostowice, Wiczlino"},
        {"id": "ECONOMY", "name_pl": "Ekonomiczny", "price_min": 0, "price_max": 299, "locations": "Żukowo, Kolbudy"},
    ]
    for ps in price_segments:
        query = """
        MERGE (p:PriceSegment {id: $id})
        SET p.name_pl = $name_pl, p.price_min = $price_min, p.price_max = $price_max, p.locations = $locations
        """
        run_query(session, query, ps, f"PriceSegment: {ps['id']}")


def create_city_nodes(session):
    """Create city (gmina) nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE WĘZŁÓW MIAST")
    logger.info("=" * 60)

    cities = [
        {"name": "Gdańsk", "wojewodztwo": "pomorskie", "powiat": "Gdańsk"},
        {"name": "Gdynia", "wojewodztwo": "pomorskie", "powiat": "Gdynia"},
        {"name": "Sopot", "wojewodztwo": "pomorskie", "powiat": "Sopot"},
    ]

    for city in cities:
        query = """
        MERGE (c:City {name: $name})
        SET c.wojewodztwo = $wojewodztwo, c.powiat = $powiat
        """
        run_query(session, query, city, f"City: {city['name']}")


def show_schema_summary(session):
    """Show summary of created schema."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE SCHEMATU")
    logger.info("=" * 60)

    # Count nodes by label
    result = session.run("""
        CALL db.labels() YIELD label
        CALL {
            WITH label
            MATCH (n)
            WHERE label IN labels(n)
            RETURN count(n) AS cnt
        }
        RETURN label, cnt
        ORDER BY cnt DESC
    """)

    for record in result:
        logger.info(f"  {record['label']}: {record['cnt']} węzłów")

    # List indexes
    result = session.run("SHOW INDEXES")
    logger.info("\nIndeksy:")
    for record in result:
        logger.info(f"  {record['name']}: {record['labelsOrTypes']} ({record['state']})")

    # List constraints
    result = session.run("SHOW CONSTRAINTS")
    logger.info("\nConstraints:")
    for record in result:
        logger.info(f"  {record['name']}: {record['type']}")


def main():
    logger.info("=" * 60)
    logger.info("TWORZENIE SCHEMATU NEO4J")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Create schema elements
            create_constraints(session)
            create_indexes(session)
            create_category_nodes(session)
            create_city_nodes(session)
            show_schema_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("SCHEMAT UTWORZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
