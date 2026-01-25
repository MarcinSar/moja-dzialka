#!/usr/bin/env python3
"""
23_import_pog_zones.py - Import stref POG do Neo4j

Importuje 7,523 stref planistycznych (Plan Ogólny Gminy) jako węzły POGZone:

Źródło: egib/data/processed/pog_trojmiasto.gpkg

Właściwości POGZone:
- id: unikalny identyfikator (np. "1POG-838SW")
- oznaczenie: kod oznaczenia (np. "838SW")
- symbol: symbol strefy (np. "SW", "SJ", "SN")
- nazwa: pełna nazwa (np. "strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną")
- gmina: miasto (gdansk, gdynia, sopot)
- profil_podstawowy: profile funkcji (np. "MW|U|K|ZP|ZD|I")
- profil_podstawowy_nazwy: pełne nazwy profili
- maks_intensywnosc: maksymalna intensywność zabudowy
- maks_wysokosc_m: maksymalna wysokość budynku [m]
- maks_zabudowa_pct: maksymalny % zabudowy działki
- min_bio_pct: minimalny % powierzchni biologicznie czynnej
- is_residential: czy strefa dopuszcza zabudowę mieszkaniową
- centroid_x, centroid_y: współrzędne centroidu (EPSG:2180)
- centroid_lat, centroid_lon: współrzędne WGS84

Tworzy również relacje:
- (POGZone)-[:ALLOWS_PROFILE]->(POGProfile)
- (POGZone)-[:IN_CITY]->(City)
"""

import os
import sys
from pathlib import Path

import geopandas as gpd
from neo4j import GraphDatabase
from loguru import logger
from pyproj import Transformer

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
BASE_PATH = Path("/root/moja-dzialka")
POG_PATH = BASE_PATH / "egib" / "data" / "processed" / "pog_trojmiasto.gpkg"

# Batch size
BATCH_SIZE = 500


def run_query(session, query: str, params: dict = None, description: str = ""):
    """Execute a Cypher query and log result."""
    try:
        result = session.run(query, params or {})
        summary = result.consume()
        return True
    except Exception as e:
        logger.error(f"  Error ({description}): {e}")
        return False


def load_pog_zones() -> gpd.GeoDataFrame:
    """Load POG zones from GeoPackage."""
    logger.info(f"\n  Loading POG zones from: {POG_PATH}")

    if not POG_PATH.exists():
        logger.error(f"POG file not found: {POG_PATH}")
        sys.exit(1)

    gdf = gpd.read_file(POG_PATH)
    logger.info(f"  Loaded {len(gdf):,} POG zones")

    # Calculate centroids
    logger.info("  Calculating centroids...")
    gdf['centroid'] = gdf.geometry.centroid
    gdf['centroid_x'] = gdf['centroid'].x
    gdf['centroid_y'] = gdf['centroid'].y

    # Transform to WGS84 for lat/lon
    transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    lons, lats = transformer.transform(
        gdf['centroid_x'].values,
        gdf['centroid_y'].values
    )
    gdf['centroid_lon'] = lons
    gdf['centroid_lat'] = lats

    # Determine is_residential based on profiles
    residential_profiles = {'MN', 'MW'}

    def check_residential(profil):
        if not profil or profil == 'None':
            return False
        profiles = set(profil.split('|'))
        return bool(profiles & residential_profiles)

    gdf['is_residential'] = gdf['profil_podstawowy'].apply(check_residential)

    logger.info(f"  Residential zones: {gdf['is_residential'].sum():,}")

    # Show symbol distribution
    logger.info("\n  Symbol distribution:")
    for symbol, count in gdf['symbol'].value_counts().head(10).items():
        logger.info(f"    {symbol}: {count:,}")

    return gdf


def import_pog_zones(session, gdf: gpd.GeoDataFrame):
    """Import POG zones as nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("IMPORT POGZone NODES")
    logger.info("=" * 60)

    # Convert to records
    records = []
    for _, row in gdf.iterrows():
        record = {
            'id': row['id'],
            'oznaczenie': row['oznaczenie'] if row['oznaczenie'] else None,
            'symbol': row['symbol'] if row['symbol'] else None,
            'nazwa': row['nazwa'] if row['nazwa'] else None,
            'gmina': row['gmina'] if row['gmina'] else None,
            'profil_podstawowy': row['profil_podstawowy'] if row['profil_podstawowy'] else None,
            'profil_podstawowy_nazwy': row['profil_podstawowy_nazwy'] if row['profil_podstawowy_nazwy'] else None,
            'profil_dodatkowy': row['profil_dodatkowy'] if row['profil_dodatkowy'] else None,
            'profil_dodatkowy_nazwy': row['profil_dodatkowy_nazwy'] if row['profil_dodatkowy_nazwy'] else None,
            'maks_intensywnosc': float(row['maks_intensywnosc']) if row['maks_intensywnosc'] else None,
            'maks_wysokosc_m': float(row['maks_wysokosc_m']) if row['maks_wysokosc_m'] else None,
            'maks_zabudowa_pct': float(row['maks_zabudowa_pct']) if row['maks_zabudowa_pct'] else None,
            'min_bio_pct': float(row['min_bio_pct']) if row['min_bio_pct'] else None,
            'is_residential': bool(row['is_residential']),
            'centroid_x': float(row['centroid_x']),
            'centroid_y': float(row['centroid_y']),
            'centroid_lat': float(row['centroid_lat']),
            'centroid_lon': float(row['centroid_lon']),
        }
        records.append(record)

    # Import in batches
    query = """
    UNWIND $batch AS row
    MERGE (z:POGZone {id: row.id})
    SET z.oznaczenie = row.oznaczenie,
        z.symbol = row.symbol,
        z.nazwa = row.nazwa,
        z.gmina = row.gmina,
        z.profil_podstawowy = row.profil_podstawowy,
        z.profil_podstawowy_nazwy = row.profil_podstawowy_nazwy,
        z.profil_dodatkowy = row.profil_dodatkowy,
        z.profil_dodatkowy_nazwy = row.profil_dodatkowy_nazwy,
        z.maks_intensywnosc = row.maks_intensywnosc,
        z.maks_wysokosc_m = row.maks_wysokosc_m,
        z.maks_zabudowa_pct = row.maks_zabudowa_pct,
        z.min_bio_pct = row.min_bio_pct,
        z.is_residential = row.is_residential,
        z.centroid_x = row.centroid_x,
        z.centroid_y = row.centroid_y,
        z.centroid_lat = row.centroid_lat,
        z.centroid_lon = row.centroid_lon
    """

    total = len(records)
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        session.run(query, {"batch": batch})
        if (i + BATCH_SIZE) % 2000 == 0 or i + BATCH_SIZE >= total:
            logger.info(f"  Imported {min(i + BATCH_SIZE, total):,} / {total:,} zones")

    logger.info(f"\n  Imported {total:,} POGZone nodes")


def create_profile_relations(session):
    """Create ALLOWS_PROFILE relations between POGZone and POGProfile."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI ALLOWS_PROFILE")
    logger.info("=" * 60)

    # Get zones with profiles
    query = """
    MATCH (z:POGZone)
    WHERE z.profil_podstawowy IS NOT NULL
    WITH z, split(z.profil_podstawowy, '|') AS profiles
    UNWIND profiles AS profile
    MATCH (p:POGProfile {id: profile})
    MERGE (z)-[:ALLOWS_PROFILE]->(p)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  Created {record['cnt']:,} ALLOWS_PROFILE relations (primary profiles)")

    # Also for secondary profiles
    query = """
    MATCH (z:POGZone)
    WHERE z.profil_dodatkowy IS NOT NULL
    WITH z, split(z.profil_dodatkowy, '|') AS profiles
    UNWIND profiles AS profile
    MATCH (p:POGProfile {id: profile})
    MERGE (z)-[:ALLOWS_PROFILE {secondary: true}]->(p)
    RETURN count(*) as cnt
    """
    result = session.run(query)
    record = result.single()
    logger.info(f"  Created {record['cnt']:,} ALLOWS_PROFILE relations (secondary profiles)")


def create_city_relations(session):
    """Create IN_CITY relations between POGZone and City."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE RELACJI IN_CITY")
    logger.info("=" * 60)

    # Map gmina names to city names
    gmina_map = {
        'gdansk': 'Gdańsk',
        'gdynia': 'Gdynia',
        'sopot': 'Sopot',
    }

    for gmina, city in gmina_map.items():
        query = """
        MATCH (z:POGZone)
        WHERE z.gmina = $gmina
        MATCH (c:City {name: $city})
        MERGE (z)-[:IN_CITY]->(c)
        RETURN count(*) as cnt
        """
        result = session.run(query, {"gmina": gmina, "city": city})
        record = result.single()
        logger.info(f"  {city}: {record['cnt']:,} zones")


def show_summary(session):
    """Show summary of imported data."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE IMPORTU POG")
    logger.info("=" * 60)

    # Count POGZone nodes
    result = session.run("MATCH (z:POGZone) RETURN count(z) as cnt")
    record = result.single()
    logger.info(f"\n  POGZone nodes: {record['cnt']:,}")

    # Count by city
    logger.info("\n  By city:")
    result = session.run("""
        MATCH (z:POGZone)
        RETURN z.gmina as gmina, count(z) as cnt
        ORDER BY cnt DESC
    """)
    for record in result:
        logger.info(f"    {record['gmina']}: {record['cnt']:,}")

    # Count by symbol
    logger.info("\n  By symbol (top 10):")
    result = session.run("""
        MATCH (z:POGZone)
        RETURN z.symbol as symbol, count(z) as cnt
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for record in result:
        logger.info(f"    {record['symbol']}: {record['cnt']:,}")

    # Residential vs non-residential
    result = session.run("""
        MATCH (z:POGZone)
        RETURN z.is_residential as is_residential, count(z) as cnt
    """)
    logger.info("\n  Residential:")
    for record in result:
        status = "TAK" if record['is_residential'] else "NIE"
        logger.info(f"    {status}: {record['cnt']:,}")

    # Profile relations
    result = session.run("""
        MATCH (z:POGZone)-[r:ALLOWS_PROFILE]->(p:POGProfile)
        RETURN count(r) as cnt
    """)
    record = result.single()
    logger.info(f"\n  ALLOWS_PROFILE relations: {record['cnt']:,}")

    # Most common profiles
    logger.info("\n  Most common profiles:")
    result = session.run("""
        MATCH (z:POGZone)-[:ALLOWS_PROFILE]->(p:POGProfile)
        RETURN p.id as profile, p.name_pl as name, count(z) as cnt
        ORDER BY cnt DESC
        LIMIT 10
    """)
    for record in result:
        logger.info(f"    {record['profile']} ({record['name']}): {record['cnt']:,}")


def main():
    logger.info("=" * 60)
    logger.info("IMPORT STREF POG DO NEO4J")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")
    logger.info(f"POG Path: {POG_PATH}")

    # Load POG zones
    gdf = load_pog_zones()

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Import zones
            import_pog_zones(session, gdf)

            # Create relations
            create_profile_relations(session)
            create_city_relations(session)

            # Show summary
            show_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("IMPORT POG ZAKOŃCZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
