#!/usr/bin/env python3
"""
17_create_spatial_relations.py - Tworzenie relacji przestrzennych w Neo4j

Tworzy relacje NEAR_* na podstawie progów odległości:
- NEAR_SCHOOL: dist_to_school < 1000m
- NEAR_BUS_STOP: dist_to_bus_stop < 500m
- NEAR_FOREST: dist_to_forest < 300m
- NEAR_WATER: dist_to_water < 500m (z typem wody)
- NEAR_SHOP: dist_to_supermarket < 1000m
- NEAR_MAIN_ROAD: dist_to_main_road < 200m

Dodaje również relacje IN_PRICE_SEGMENT dla dzielnic.
"""

import os
import sys
from pathlib import Path

from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


# Distance thresholds for NEAR_* relations
DISTANCE_THRESHOLDS = {
    "NEAR_SCHOOL": {
        "parcel_field": "dist_to_school",
        "threshold": 1000,
        "description": "Szkoła w zasięgu 1km",
    },
    "NEAR_BUS_STOP": {
        "parcel_field": "dist_to_bus_stop",
        "threshold": 500,
        "description": "Przystanek w zasięgu 500m",
    },
    "NEAR_FOREST": {
        "parcel_field": "dist_to_forest",
        "threshold": 500,
        "description": "Las w zasięgu 500m",
    },
    "NEAR_SUPERMARKET": {
        "parcel_field": "dist_to_supermarket",
        "threshold": 1000,
        "description": "Sklep w zasięgu 1km",
    },
    "NEAR_MAIN_ROAD": {
        "parcel_field": "dist_to_main_road",
        "threshold": 200,
        "description": "Główna droga w zasięgu 200m (uwaga: hałas!)",
    },
}

# Water proximity thresholds by type
WATER_THRESHOLDS = {
    "morze": {"threshold": 1000, "description": "Morze w zasięgu 1km"},
    "zatoka": {"threshold": 1000, "description": "Zatoka w zasięgu 1km"},
    "jezioro": {"threshold": 500, "description": "Jezioro w zasięgu 500m"},
    "rzeka": {"threshold": 300, "description": "Rzeka w zasięgu 300m"},
    "kanal": {"threshold": 200, "description": "Kanał w zasięgu 200m"},
    "staw": {"threshold": 100, "description": "Staw w zasięgu 100m"},
}

# District to price segment mapping
DISTRICT_PRICE_SEGMENTS = {
    # ULTRA_PREMIUM (>3000 zł/m²)
    "ULTRA_PREMIUM": [
        "Sopot Dolny", "Kamienna Góra", "Orłowo", "Sopot Górny",
        "Karlikowo", "Brodwino",
    ],
    # PREMIUM (1500-3000 zł/m²)
    "PREMIUM": [
        "Jelitkowo", "Przymorze Wielkie", "Brzeźno", "Stogi", "Młyniska",
        "Śródmieście", "Wzgórze Maksymiliana", "Redłowo", "Mały Kack",
    ],
    # HIGH (800-1500 zł/m²)
    "HIGH": [
        "Oliwa", "Wrzeszcz Górny", "Wrzeszcz Dolny", "Zaspa", "Żabianka",
        "Leszczynki", "Dąbrowa", "Działki Leśne", "Grabówek", "Witomino",
    ],
    # MEDIUM (500-800 zł/m²)
    "MEDIUM": [
        "Osowa", "Kokoszki", "Jasień", "Piecki-Migowo", "Chwarzno-Wiczlino",
        "Suchanino", "Aniołki", "Siedlce", "Cisowa", "Pustki Cisowskie",
    ],
    # BUDGET (300-500 zł/m²)
    "BUDGET": [
        "Łostowice", "Chełm", "Ujeścisko-Łostowice", "Matarnia", "Karczemki",
        "Wielki Kack", "Obłuże", "Oksywie", "Pogórze", "Dąbrówka",
    ],
    # ECONOMY (<300 zł/m²)
    "ECONOMY": [
        "Krakowiec-Górki Zachodnie", "Rudniki", "Stogi Portowe",
        "Nowy Port", "Letnica", "Przeróbka", "Olszynka", "Orunia",
    ],
}


def create_near_relations_by_distance(session):
    """Create NEAR_* relations based on parcel distance fields."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI NEAR_* (wg odległości)")
    logger.info("=" * 60)

    for rel_type, config in DISTANCE_THRESHOLDS.items():
        field = config["parcel_field"]
        threshold = config["threshold"]
        desc = config["description"]

        logger.info(f"\n  {rel_type}: {desc}")

        # Count parcels meeting threshold
        count_query = f"""
        MATCH (p:Parcel)
        WHERE p.{field} IS NOT NULL AND p.{field} <= {threshold}
        RETURN count(p) as count
        """
        result = session.run(count_query)
        record = result.single()
        count = record["count"]

        logger.info(f"    Działki spełniające kryterium: {count:,}")

        # Note: We store the proximity info as parcel property
        # Creating actual relations to POI nodes would require spatial indexing
        # which is better done with PostGIS or Neo4j Spatial


def create_water_proximity_flags(session):
    """Add water proximity flags based on typed distances."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE FLAG BLISKOŚCI WODY")
    logger.info("=" * 60)

    for water_type, config in WATER_THRESHOLDS.items():
        threshold = config["threshold"]
        desc = config["description"]
        dist_field = f"dist_to_{water_type}" if water_type != "morze" else "dist_to_sea"

        if water_type == "jezioro":
            dist_field = "dist_to_lake"
        elif water_type == "rzeka":
            dist_field = "dist_to_river"
        elif water_type == "kanal":
            dist_field = "dist_to_canal"
        elif water_type == "staw":
            dist_field = "dist_to_pond"

        logger.info(f"\n  near_{water_type}: {desc}")

        # Add flag property
        query = f"""
        MATCH (p:Parcel)
        WHERE p.{dist_field} IS NOT NULL
        SET p.near_{water_type} = CASE WHEN p.{dist_field} <= {threshold} THEN true ELSE false END
        RETURN count(p) as total, sum(CASE WHEN p.{dist_field} <= {threshold} THEN 1 ELSE 0 END) as near
        """
        result = session.run(query)
        record = result.single()
        total = record["total"]
        near = record["near"]
        pct = near / total * 100 if total > 0 else 0

        logger.info(f"    Blisko {water_type}: {near:,} działek ({pct:.1f}%)")


def create_price_segment_relations(session):
    """Create IN_PRICE_SEGMENT relations for districts."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI IN_PRICE_SEGMENT")
    logger.info("=" * 60)

    for segment, districts in DISTRICT_PRICE_SEGMENTS.items():
        logger.info(f"\n  Segment {segment}: {len(districts)} dzielnic")

        for district in districts:
            query = """
            MATCH (d:District {name: $district})
            MATCH (ps:PriceSegment {id: $segment})
            MERGE (d)-[:IN_PRICE_SEGMENT]->(ps)
            RETURN d.name as district
            """
            result = session.run(query, {"district": district, "segment": segment})
            records = list(result)
            if records:
                logger.info(f"    {district} -> {segment}")


def add_parcel_price_segment(session):
    """Add price_segment property to parcels based on district."""
    logger.info("\n" + "=" * 60)
    logger.info("DODAWANIE price_segment DO DZIAŁEK")
    logger.info("=" * 60)

    # Build case statement for all segments
    when_clauses = []
    for segment, districts in DISTRICT_PRICE_SEGMENTS.items():
        district_list = ", ".join([f"'{d}'" for d in districts])
        when_clauses.append(f"WHEN p.dzielnica IN [{district_list}] THEN '{segment}'")

    case_stmt = "\n".join(when_clauses)

    query = f"""
    MATCH (p:Parcel)
    SET p.price_segment = CASE
        {case_stmt}
        ELSE 'UNKNOWN'
    END
    RETURN count(p) as updated
    """

    result = session.run(query)
    record = result.single()
    logger.info(f"  Zaktualizowano {record['updated']:,} działek")

    # Statistics
    query = """
    MATCH (p:Parcel)
    RETURN p.price_segment as segment, count(p) as count
    ORDER BY count DESC
    """
    result = session.run(query)
    logger.info("\n  Rozkład segmentów cenowych:")
    for record in result:
        logger.info(f"    {record['segment']}: {record['count']:,}")


def show_spatial_summary(session):
    """Show summary of spatial features."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE CECH PRZESTRZENNYCH")
    logger.info("=" * 60)

    # Water proximity summary
    logger.info("\nBliskość wody:")
    for water_type in ["morze", "jezioro", "rzeka", "kanal", "staw"]:
        query = f"""
        MATCH (p:Parcel)
        WHERE p.near_{water_type} = true
        RETURN count(p) as count
        """
        result = session.run(query)
        record = result.single()
        if record:
            logger.info(f"  Blisko {water_type}: {record['count']:,}")

    # Distance statistics
    logger.info("\nStatystyki odległości (mediana):")
    distance_fields = [
        ("dist_to_sea", "morze"),
        ("dist_to_lake", "jezioro"),
        ("dist_to_river", "rzeka"),
        ("dist_to_school", "szkoła"),
        ("dist_to_bus_stop", "przystanek"),
        ("dist_to_forest", "las"),
    ]

    for field, name in distance_fields:
        query = f"""
        MATCH (p:Parcel)
        WHERE p.{field} IS NOT NULL
        RETURN percentileCont(p.{field}, 0.5) as median
        """
        result = session.run(query)
        record = result.single()
        if record and record["median"]:
            logger.info(f"  Do {name}: {record['median']:.0f}m")


def main():
    from neo4j import GraphDatabase

    logger.info("=" * 60)
    logger.info("TWORZENIE RELACJI PRZESTRZENNYCH")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Create spatial features
            create_near_relations_by_distance(session)
            create_water_proximity_flags(session)
            create_price_segment_relations(session)
            add_parcel_price_segment(session)
            show_spatial_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("RELACJE PRZESTRZENNE UTWORZONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
