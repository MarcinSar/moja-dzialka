#!/usr/bin/env python3
"""
16_import_neo4j_full.py - Import pełnych danych do Neo4j

Importuje dane z CSV do Neo4j:
1. Działki (Parcel) - 155k węzłów z 68 właściwościami
2. POI (School, BusStop, Forest, Water, Shop, Road)
3. Dzielnice (District) - ekstrakcja z działek
4. Relacje hierarchiczne (LOCATED_IN, BELONGS_TO)
5. Relacje kategorialne (HAS_QUIETNESS, HAS_NATURE, etc.)

Używa batch processing dla wydajności.
"""

import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
CSV_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j" / "csv"

# Batch size for imports
BATCH_SIZE = 5000


def load_csv(filename: str) -> List[Dict[str, Any]]:
    """Load CSV file into list of dicts."""
    filepath = CSV_PATH / filename
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # Convert empty strings to None
            cleaned = {}
            for k, v in row.items():
                if v == '' or v == 'None':
                    cleaned[k] = None
                elif v == 'true':
                    cleaned[k] = True
                elif v == 'false':
                    cleaned[k] = False
                else:
                    # Try to convert to number
                    try:
                        if '.' in v:
                            cleaned[k] = float(v)
                        else:
                            cleaned[k] = int(v)
                    except (ValueError, TypeError):
                        cleaned[k] = v
            rows.append(cleaned)
        return rows


def run_batch_query(session, query: str, batch: List[Dict], description: str = ""):
    """Execute batch Cypher query."""
    try:
        result = session.run(query, {"batch": batch})
        summary = result.consume()
        return summary.counters.nodes_created + summary.counters.relationships_created
    except Exception as e:
        logger.error(f"Batch error: {e}")
        return 0


def import_parcels(session):
    """Import parcel nodes from CSV."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT DZIAŁEK (Parcel)")
    logger.info("=" * 60)

    parcels = load_csv("parcels_full.csv")
    logger.info(f"  Załadowano {len(parcels):,} rekordów z CSV")

    # Properties to import
    property_map = """
        id_dzialki: row.id_dzialki,
        gmina: row.gmina,
        miejscowosc: row.miejscowosc,
        dzielnica: row.dzielnica,
        powiat: row.powiat,
        wojewodztwo: row.wojewodztwo,

        // Geometry
        centroid_x: row.centroid_x,
        centroid_y: row.centroid_y,
        centroid_lat: row.centroid_lat,
        centroid_lon: row.centroid_lon,

        // Size
        area_m2: row.area_m2,
        shape_index: row.shape_index,
        size_category: row.size_category,
        bbox_width: row.bbox_width,
        bbox_height: row.bbox_height,

        // Ownership
        typ_wlasnosci: row.typ_wlasnosci,
        grupa_rej: row.grupa_rej,
        grupa_rej_nazwa: row.grupa_rej_nazwa,

        // Building info
        is_built: row.is_built,
        building_count: row.building_count,
        building_area_m2: row.building_area_m2,
        building_coverage_pct: row.building_coverage_pct,
        building_main_function: row.building_main_function,
        building_type: row.building_type,
        building_max_floors: row.building_max_floors,
        has_residential: row.has_residential,
        has_industrial: row.has_industrial,
        under_construction: row.under_construction,

        // POG (zoning)
        has_pog: row.has_pog,
        is_residential_zone: row.is_residential_zone,
        pog_symbol: row.pog_symbol,
        pog_oznaczenie: row.pog_oznaczenie,
        pog_nazwa: row.pog_nazwa,
        pog_profil_podstawowy: row.pog_profil_podstawowy,
        pog_profil_podstawowy_nazwy: row.pog_profil_podstawowy_nazwy,
        pog_profil_dodatkowy: row.pog_profil_dodatkowy,
        pog_profil_dodatkowy_nazwy: row.pog_profil_dodatkowy_nazwy,
        pog_maks_intensywnosc: row.pog_maks_intensywnosc,
        pog_maks_wysokosc_m: row.pog_maks_wysokosc_m,
        pog_maks_zabudowa_pct: row.pog_maks_zabudowa_pct,
        pog_min_bio_pct: row.pog_min_bio_pct,

        // Distances
        dist_to_school: row.dist_to_school,
        dist_to_kindergarten: row.dist_to_kindergarten,
        dist_to_bus_stop: row.dist_to_bus_stop,
        dist_to_pharmacy: row.dist_to_pharmacy,
        dist_to_doctors: row.dist_to_doctors,
        dist_to_supermarket: row.dist_to_supermarket,
        dist_to_restaurant: row.dist_to_restaurant,
        dist_to_forest: row.dist_to_forest,
        dist_to_water: row.dist_to_water,
        dist_to_industrial: row.dist_to_industrial,
        dist_to_main_road: row.dist_to_main_road,

        // Water distances (NEW)
        dist_to_sea: row.dist_to_sea,
        dist_to_river: row.dist_to_river,
        dist_to_lake: row.dist_to_lake,
        dist_to_canal: row.dist_to_canal,
        dist_to_pond: row.dist_to_pond,
        nearest_water_type: row.nearest_water_type,

        // Scores
        quietness_score: row.quietness_score,
        nature_score: row.nature_score,
        accessibility_score: row.accessibility_score,

        // Categories
        kategoria_ciszy: row.kategoria_ciszy,
        kategoria_natury: row.kategoria_natury,
        kategoria_dostepu: row.kategoria_dostepu,
        gestosc_zabudowy: row.gestosc_zabudowy,

        // Context
        pct_forest_500m: row.pct_forest_500m,
        pct_water_500m: row.pct_water_500m,
        count_buildings_500m: row.count_buildings_500m
    """

    query = f"""
    UNWIND $batch AS row
    MERGE (p:Parcel {{id_dzialki: row.id_dzialki}})
    SET p += {{
        {property_map}
    }}
    """

    # Process in batches
    total_created = 0
    for i in range(0, len(parcels), BATCH_SIZE):
        batch = parcels[i:i + BATCH_SIZE]
        created = run_batch_query(session, query, batch)
        total_created += created
        if (i + BATCH_SIZE) % 25000 == 0 or i + BATCH_SIZE >= len(parcels):
            logger.info(f"  Processed {min(i + BATCH_SIZE, len(parcels)):,} / {len(parcels):,}")

    logger.info(f"  Zaimportowano {len(parcels):,} działek")


def import_districts(session):
    """Extract and import district nodes from parcels."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT DZIELNIC (District)")
    logger.info("=" * 60)

    # Extract unique districts from parcels
    query = """
    MATCH (p:Parcel)
    WHERE p.dzielnica IS NOT NULL
    WITH DISTINCT p.dzielnica AS name, p.gmina AS city
    MERGE (d:District {name: name})
    SET d.city = city
    RETURN count(d) as count
    """

    result = session.run(query)
    record = result.single()
    logger.info(f"  Utworzono {record['count']} dzielnic")


def import_water(session):
    """Import water nodes with classification."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT WÓD (Water)")
    logger.info("=" * 60)

    waters = load_csv("waters.csv")
    logger.info(f"  Załadowano {len(waters):,} rekordów z CSV")

    query = """
    UNWIND $batch AS row
    MERGE (w:Water {id: row.id})
    SET w.name = row.name,
        w.rodzaj = row.rodzaj,
        w.water_type = row.water_type,
        w.water_type_pl = row.water_type_pl,
        w.priority = row.priority,
        w.premium_factor = row.premium_factor,
        w.area_m2 = row.area_m2,
        w.x = row.x,
        w.y = row.y
    """

    for i in range(0, len(waters), BATCH_SIZE):
        batch = waters[i:i + BATCH_SIZE]
        run_batch_query(session, query, batch)

    logger.info(f"  Zaimportowano {len(waters):,} obiektów wodnych")


def import_poi(session, filename: str, label: str, properties: dict):
    """Generic POI import."""
    logger.info(f"\n  Import {label} z {filename}...")

    rows = load_csv(filename)
    if not rows:
        return

    # Build property SET clause
    prop_clause = ", ".join([f"n.{k} = row.{v}" for k, v in properties.items()])

    query = f"""
    UNWIND $batch AS row
    MERGE (n:{label} {{id: row.id}})
    SET {prop_clause}
    """

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        run_batch_query(session, query, batch)

    logger.info(f"    Zaimportowano {len(rows):,} {label}")


def import_all_poi(session):
    """Import all POI nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT POI")
    logger.info("=" * 60)

    import_poi(session, "schools.csv", "School", {
        "name": "name", "type": "type", "x": "x", "y": "y"
    })

    import_poi(session, "bus_stops.csv", "BusStop", {
        "name": "name", "x": "x", "y": "y"
    })

    import_poi(session, "forests.csv", "Forest", {
        "type": "type", "area_m2": "area_m2", "x": "x", "y": "y"
    })

    import_poi(session, "shops.csv", "Shop", {
        "name": "name", "shop_type": "shop_type", "x": "x", "y": "y"
    })

    import_poi(session, "roads.csv", "Road", {
        "name": "name", "type": "type", "length_m": "length_m", "x": "x", "y": "y"
    })


def create_hierarchy_relations(session):
    """Create LOCATED_IN and BELONGS_TO relations."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI HIERARCHICZNYCH")
    logger.info("=" * 60)

    # Parcel -> District
    query = """
    MATCH (p:Parcel)
    WHERE p.dzielnica IS NOT NULL
    MATCH (d:District {name: p.dzielnica})
    MERGE (p)-[:LOCATED_IN]->(d)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  Parcel -> District: {summary.counters.relationships_created} relacji")

    # District -> City
    query = """
    MATCH (d:District)
    WHERE d.city IS NOT NULL
    MATCH (c:City {name: d.city})
    MERGE (d)-[:BELONGS_TO]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  District -> City: {summary.counters.relationships_created} relacji")


def create_category_relations(session):
    """Create HAS_* category relations."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI KATEGORIALNYCH")
    logger.info("=" * 60)

    # HAS_QUIETNESS
    query = """
    MATCH (p:Parcel)
    WHERE p.kategoria_ciszy IS NOT NULL
    MATCH (c:QuietnessCategory {id: p.kategoria_ciszy})
    MERGE (p)-[:HAS_QUIETNESS]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_QUIETNESS: {summary.counters.relationships_created} relacji")

    # HAS_NATURE
    query = """
    MATCH (p:Parcel)
    WHERE p.kategoria_natury IS NOT NULL
    MATCH (c:NatureCategory {id: p.kategoria_natury})
    MERGE (p)-[:HAS_NATURE]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_NATURE: {summary.counters.relationships_created} relacji")

    # HAS_ACCESS
    query = """
    MATCH (p:Parcel)
    WHERE p.kategoria_dostepu IS NOT NULL
    MATCH (c:AccessCategory {id: p.kategoria_dostepu})
    MERGE (p)-[:HAS_ACCESS]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_ACCESS: {summary.counters.relationships_created} relacji")

    # HAS_DENSITY
    query = """
    MATCH (p:Parcel)
    WHERE p.gestosc_zabudowy IS NOT NULL
    MATCH (c:DensityCategory {id: p.gestosc_zabudowy})
    MERGE (p)-[:HAS_DENSITY]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_DENSITY: {summary.counters.relationships_created} relacji")

    # NEAREST_WATER_TYPE
    query = """
    MATCH (p:Parcel)
    WHERE p.nearest_water_type IS NOT NULL
    MATCH (w:WaterType {id: p.nearest_water_type})
    MERGE (p)-[:NEAREST_WATER_TYPE]->(w)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  NEAREST_WATER_TYPE: {summary.counters.relationships_created} relacji")


def create_water_type_relations(session):
    """Create WATER_IS_TYPE relations."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI WATER_IS_TYPE")
    logger.info("=" * 60)

    query = """
    MATCH (w:Water)
    WHERE w.water_type IS NOT NULL
    MATCH (wt:WaterType {id: w.water_type})
    MERGE (w)-[:WATER_IS_TYPE]->(wt)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  WATER_IS_TYPE: {summary.counters.relationships_created} relacji")


def show_import_summary(session):
    """Show summary of imported data."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE IMPORTU")
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

    logger.info("\nWęzły:")
    total_nodes = 0
    for record in result:
        logger.info(f"  {record['label']}: {record['cnt']:,}")
        total_nodes += record['cnt']
    logger.info(f"  RAZEM: {total_nodes:,}")

    # Count relationships
    result = session.run("""
        CALL db.relationshipTypes() YIELD relationshipType
        CALL {
            WITH relationshipType
            MATCH ()-[r]->()
            WHERE type(r) = relationshipType
            RETURN count(r) AS cnt
        }
        RETURN relationshipType, cnt
        ORDER BY cnt DESC
    """)

    logger.info("\nRelacje:")
    total_rels = 0
    for record in result:
        logger.info(f"  {record['relationshipType']}: {record['cnt']:,}")
        total_rels += record['cnt']
    logger.info(f"  RAZEM: {total_rels:,}")


def main():
    from neo4j import GraphDatabase

    logger.info("=" * 60)
    logger.info("IMPORT DANYCH DO NEO4J")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"CSV Path: {CSV_PATH}")

    # Check if CSV files exist
    if not CSV_PATH.exists():
        logger.error(f"CSV directory not found: {CSV_PATH}")
        logger.error("Run 13_export_full_csv.py and 14_export_poi_csv.py first")
        sys.exit(1)

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Import nodes
            import_parcels(session)
            import_districts(session)
            import_water(session)
            import_all_poi(session)

            # Create relations
            create_hierarchy_relations(session)
            create_category_relations(session)
            create_water_type_relations(session)

            # Show summary
            show_import_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("IMPORT ZAKOŃCZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
