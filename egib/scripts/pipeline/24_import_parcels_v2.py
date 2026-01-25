#!/usr/bin/env python3
"""
24_import_parcels_v2.py - Import działek z nowymi relacjami

Importuje 154,959 działek z pełnym zestawem relacji:

WĘZŁY:
- Parcel - działka z 68 właściwościami
- District - dzielnica (ekstrahowane z działek)

RELACJE HIERARCHICZNE:
- (Parcel)-[:LOCATED_IN]->(District)
- (District)-[:BELONGS_TO]->(City)

RELACJE WŁASNOŚCI:
- (Parcel)-[:HAS_OWNERSHIP]->(OwnershipType)
- (Parcel)-[:HAS_OWNER_GROUP]->(OwnershipGroup)

RELACJE ZABUDOWY:
- (Parcel)-[:HAS_BUILD_STATUS]->(BuildStatus)
- (Parcel)-[:HAS_BUILDING_FUNCTION]->(BuildingFunction)  // tylko zabudowane
- (Parcel)-[:HAS_BUILDING_TYPE]->(BuildingType)          // tylko zabudowane

RELACJE PLANOWANIA:
- (Parcel)-[:HAS_POG]->(POGZone)

RELACJE ROZMIARU:
- (Parcel)-[:HAS_SIZE]->(SizeCategory)

RELACJE KATEGORIALNE:
- (Parcel)-[:HAS_QUIETNESS]->(QuietnessCategory)
- (Parcel)-[:HAS_NATURE]->(NatureCategory)
- (Parcel)-[:HAS_ACCESS]->(AccessCategory)
- (Parcel)-[:HAS_DENSITY]->(DensityCategory)
- (Parcel)-[:NEAREST_WATER_TYPE]->(WaterType)
"""

import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
CSV_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j" / "csv"

# Batch size for imports
BATCH_SIZE = 3000


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
                elif v == 'true' or v == 'True':
                    cleaned[k] = True
                elif v == 'false' or v == 'False':
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


def import_parcels(session, parcels: List[Dict]):
    """Import parcel nodes with all properties."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT DZIAŁEK (Parcel)")
    logger.info("=" * 60)
    logger.info(f"  Total parcels: {len(parcels):,}")

    # All parcel properties
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

        // Ownership (also as relations)
        typ_wlasnosci: row.typ_wlasnosci,
        grupa_rej: row.grupa_rej,
        grupa_rej_nazwa: row.grupa_rej_nazwa,

        // Building info (also as relations)
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

        // POG (zoning) - relations will be created separately
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

        // Water distances
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
    total = len(parcels)
    for i in range(0, total, BATCH_SIZE):
        batch = parcels[i:i + BATCH_SIZE]
        session.run(query, {"batch": batch})
        if (i + BATCH_SIZE) % 15000 == 0 or i + BATCH_SIZE >= total:
            logger.info(f"  Processed {min(i + BATCH_SIZE, total):,} / {total:,}")

    logger.info(f"  Imported {total:,} parcels")


def import_districts(session):
    """Extract and import district nodes from parcels."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT DZIELNIC (District)")
    logger.info("=" * 60)

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
    logger.info(f"  Created {record['count']} districts")


def create_hierarchy_relations(session):
    """Create LOCATED_IN and BELONGS_TO relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE HIERARCHICZNE")
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
    logger.info(f"  LOCATED_IN (Parcel -> District): {summary.counters.relationships_created:,}")

    # District -> City
    query = """
    MATCH (d:District)
    WHERE d.city IS NOT NULL
    MATCH (c:City {name: d.city})
    MERGE (d)-[:BELONGS_TO]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  BELONGS_TO (District -> City): {summary.counters.relationships_created:,}")


def create_ownership_relations(session):
    """Create HAS_OWNERSHIP and HAS_OWNER_GROUP relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE WŁASNOŚCI")
    logger.info("=" * 60)

    # HAS_OWNERSHIP - map typ_wlasnosci to OwnershipType
    ownership_map = {
        'prywatna': 'prywatna',
        'publiczna': 'publiczna',
        'spółdzielcza': 'spoldzielcza',
        'kościelna': 'koscielna',
        'inna': 'inna',
    }

    for source, target in ownership_map.items():
        query = """
        MATCH (p:Parcel)
        WHERE p.typ_wlasnosci = $source
        MATCH (o:OwnershipType {id: $target})
        MERGE (p)-[:HAS_OWNERSHIP]->(o)
        RETURN count(*) as cnt
        """
        result = session.run(query, {"source": source, "target": target})
        record = result.single()
        if record['cnt'] > 0:
            logger.info(f"  HAS_OWNERSHIP ({source}): {record['cnt']:,}")

    # HAS_OWNER_GROUP - map grupa_rej_nazwa to OwnershipGroup
    owner_group_map = {
        'Osoby fizyczne': 'osoby_fizyczne',
        'Gminy (własność)': 'gminy_wlasnosc',
        'Gminy (w zarządzie)': 'gminy_zarzad',
        'Skarb Państwa': 'skarb_panstwa',
        'Skarb Państwa (w zarządzie)': 'skarb_panstwa_zarzad',
        'Inne podmioty publiczne': 'inne_publiczne',
        'Województwa (własność)': 'wojewodztwa_wlasnosc',
        'Województwa (w zarządzie)': 'wojewodztwa_zarzad',
        'Powiaty (własność)': 'powiaty_wlasnosc',
        'Powiaty (w zarządzie)': 'powiaty_zarzad',
        'Spółdzielnie': 'spoldzielnie',
        'Spółki Skarbu Państwa': 'spolki_sp',
        'Spółki komunalne': 'spolki_komunalne',
        'Kościoły i związki wyznaniowe': 'koscioly',
        'Inne': 'inne',
    }

    for source, target in owner_group_map.items():
        query = """
        MATCH (p:Parcel)
        WHERE p.grupa_rej_nazwa = $source
        MATCH (o:OwnershipGroup {id: $target})
        MERGE (p)-[:HAS_OWNER_GROUP]->(o)
        RETURN count(*) as cnt
        """
        result = session.run(query, {"source": source, "target": target})
        record = result.single()
        if record['cnt'] > 0:
            logger.info(f"  HAS_OWNER_GROUP ({source}): {record['cnt']:,}")


def create_build_status_relations(session):
    """Create HAS_BUILD_STATUS relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE ZABUDOWY")
    logger.info("=" * 60)

    # HAS_BUILD_STATUS
    query = """
    MATCH (p:Parcel)
    WHERE p.is_built = true
    MATCH (bs:BuildStatus {id: 'zabudowana'})
    MERGE (p)-[:HAS_BUILD_STATUS]->(bs)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  HAS_BUILD_STATUS (zabudowana): {record['cnt']:,}")

    query = """
    MATCH (p:Parcel)
    WHERE p.is_built = false OR p.is_built IS NULL
    MATCH (bs:BuildStatus {id: 'niezabudowana'})
    MERGE (p)-[:HAS_BUILD_STATUS]->(bs)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  HAS_BUILD_STATUS (niezabudowana): {record['cnt']:,}")


def create_building_function_relations(session):
    """Create HAS_BUILDING_FUNCTION relations for built parcels."""
    logger.info("\n  Creating HAS_BUILDING_FUNCTION relations...")

    # Map building_main_function to BuildingFunction IDs
    function_map = {
        'mieszkalne': 'mieszkalne',
        'gospodarcze': 'gospodarcze',
        'handlowo-usługowe': 'handlowo-uslugowe',
        'biurowe': 'biurowe',
        'przemysłowe': 'przemyslowe',
        'magazynowe': 'magazynowe',
        'transport': 'transport',
        'edukacja/kultura': 'edukacja_kultura',
        'zdrowie': 'zdrowie',
        'inne': 'inne',
    }

    for source, target in function_map.items():
        query = """
        MATCH (p:Parcel)
        WHERE p.is_built = true AND p.building_main_function = $source
        MATCH (bf:BuildingFunction {id: $target})
        MERGE (p)-[:HAS_BUILDING_FUNCTION]->(bf)
        RETURN count(*) as cnt
        """
        result = session.run(query, {"source": source, "target": target})
        record = result.single()
        if record['cnt'] > 0:
            logger.info(f"    {source}: {record['cnt']:,}")


def create_building_type_relations(session):
    """Create HAS_BUILDING_TYPE relations for built parcels."""
    logger.info("\n  Creating HAS_BUILDING_TYPE relations...")

    query = """
    MATCH (p:Parcel)
    WHERE p.is_built = true AND p.building_type IS NOT NULL
    WITH p, replace(replace(toLower(p.building_type), ' ', '_'), '-', '_') AS bt_id
    MATCH (bt:BuildingType {id: bt_id})
    MERGE (p)-[:HAS_BUILDING_TYPE]->(bt)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"    Total: {record['cnt']:,}")


def create_size_relations(session):
    """Create HAS_SIZE relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE ROZMIARU")
    logger.info("=" * 60)

    query = """
    MATCH (p:Parcel)
    WHERE p.size_category IS NOT NULL
    MATCH (s:SizeCategory {id: p.size_category})
    MERGE (p)-[:HAS_SIZE]->(s)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  HAS_SIZE: {record['cnt']:,}")

    # Show distribution
    result = session.run("""
        MATCH (p:Parcel)-[:HAS_SIZE]->(s:SizeCategory)
        RETURN s.id as size, count(p) as cnt
        ORDER BY cnt DESC
    """)
    logger.info("\n  Size distribution:")
    for record in result:
        logger.info(f"    {record['size']}: {record['cnt']:,}")


def create_pog_relations(session):
    """Create HAS_POG relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE POG")
    logger.info("=" * 60)

    # Match by pog_oznaczenie and gmina
    query = """
    MATCH (p:Parcel)
    WHERE p.has_pog = true AND p.pog_oznaczenie IS NOT NULL
    WITH p, p.gmina AS city_name
    MATCH (z:POGZone)
    WHERE z.oznaczenie = p.pog_oznaczenie
      AND ((city_name = 'Gdańsk' AND z.gmina = 'gdansk')
        OR (city_name = 'Gdynia' AND z.gmina = 'gdynia')
        OR (city_name = 'Sopot' AND z.gmina = 'sopot'))
    MERGE (p)-[:HAS_POG]->(z)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  HAS_POG: {record['cnt']:,} relations")


def create_category_relations(session):
    """Create all category relations."""
    logger.info("\n" + "=" * 60)
    logger.info("RELACJE KATEGORIALNE")
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
    logger.info(f"  HAS_QUIETNESS: {summary.counters.relationships_created:,}")

    # HAS_NATURE
    query = """
    MATCH (p:Parcel)
    WHERE p.kategoria_natury IS NOT NULL
    MATCH (c:NatureCategory {id: p.kategoria_natury})
    MERGE (p)-[:HAS_NATURE]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_NATURE: {summary.counters.relationships_created:,}")

    # HAS_ACCESS
    query = """
    MATCH (p:Parcel)
    WHERE p.kategoria_dostepu IS NOT NULL
    MATCH (c:AccessCategory {id: p.kategoria_dostepu})
    MERGE (p)-[:HAS_ACCESS]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_ACCESS: {summary.counters.relationships_created:,}")

    # HAS_DENSITY
    query = """
    MATCH (p:Parcel)
    WHERE p.gestosc_zabudowy IS NOT NULL
    MATCH (c:DensityCategory {id: p.gestosc_zabudowy})
    MERGE (p)-[:HAS_DENSITY]->(c)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  HAS_DENSITY: {summary.counters.relationships_created:,}")

    # NEAREST_WATER_TYPE
    query = """
    MATCH (p:Parcel)
    WHERE p.nearest_water_type IS NOT NULL
    MATCH (w:WaterType {id: p.nearest_water_type})
    MERGE (p)-[:NEAREST_WATER_TYPE]->(w)
    """
    result = session.run(query)
    summary = result.consume()
    logger.info(f"  NEAREST_WATER_TYPE: {summary.counters.relationships_created:,}")


def show_import_summary(session):
    """Show summary of imported data."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE IMPORTU V2")
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
        if record['cnt'] > 0:
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
        if record['cnt'] > 0:
            logger.info(f"  {record['relationshipType']}: {record['cnt']:,}")
            total_rels += record['cnt']
    logger.info(f"  RAZEM: {total_rels:,}")


def main():
    logger.info("=" * 60)
    logger.info("IMPORT DZIAŁEK V2 DO NEO4J")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"CSV Path: {CSV_PATH}")

    # Check if CSV files exist
    if not CSV_PATH.exists():
        logger.error(f"CSV directory not found: {CSV_PATH}")
        logger.error("Run 13_export_full_csv.py first")
        sys.exit(1)

    # Load parcels
    logger.info("\n  Loading parcels from CSV...")
    parcels = load_csv("parcels_full.csv")
    logger.info(f"  Loaded {len(parcels):,} parcels")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Import nodes
            import_parcels(session, parcels)
            import_districts(session)

            # Create relations
            create_hierarchy_relations(session)
            create_ownership_relations(session)
            create_build_status_relations(session)
            create_building_function_relations(session)
            create_building_type_relations(session)
            create_size_relations(session)
            create_pog_relations(session)
            create_category_relations(session)

            # Show summary
            show_import_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("IMPORT V2 ZAKOŃCZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
