#!/usr/bin/env python3
"""
import_postgis.py - Import GeoPackage files into PostGIS database

Prerequisites:
1. PostgreSQL + PostGIS must be running
2. Database must exist with PostGIS extension enabled
3. GeoPackage files must be in data/ready-for-import/postgis/

Usage:
    python import_postgis.py [--host localhost] [--port 5432] [--db moja_dzialka]
"""

import argparse
import logging
import os
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default connection
DEFAULT_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DEFAULT_PORT = os.environ.get("POSTGRES_PORT", "5432")
DEFAULT_DB = os.environ.get("POSTGRES_DB", "moja_dzialka")
DEFAULT_USER = os.environ.get("POSTGRES_USER", "app")
DEFAULT_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password")

# Paths
PROJECT_DIR = Path("/home/marcin/moja-dzialka")
GPKG_DIR = PROJECT_DIR / "data" / "ready-for-import" / "postgis"

# Table mapping: filename -> table_name
TABLE_MAPPING = {
    "parcels_enriched.gpkg": "parcels",
    "pog_trojmiasto.gpkg": "pog_zones",
    "budynki.gpkg": "buildings",
    "drogi_glowne.gpkg": "roads_main",
    "drogi_wszystkie.gpkg": "roads_all",
    "lasy.gpkg": "forests",
    "wody.gpkg": "water",
    "szkoly.gpkg": "schools",
    "przystanki.gpkg": "bus_stops",
    "przemysl.gpkg": "industrial",
    "poi_merged.gpkg": "poi",
    "districts.gpkg": "districts",
}


def import_gpkg(
    gpkg_path: Path,
    table_name: str,
    host: str,
    port: str,
    db: str,
    user: str,
    password: str
) -> bool:
    """Import a GeoPackage file into PostGIS using ogr2ogr."""

    connection_string = f"PG:host={host} port={port} dbname={db} user={user} password={password}"

    cmd = [
        "ogr2ogr",
        "-f", "PostgreSQL",
        connection_string,
        str(gpkg_path),
        "-nln", table_name,
        "-overwrite",  # Replace existing table
        "-progress",
        "-lco", "GEOMETRY_NAME=geom",
        "-lco", "FID=gid",
        "-lco", "SPATIAL_INDEX=GIST",
    ]

    logger.info(f"Importing {gpkg_path.name} → {table_name}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"  ✓ {table_name} imported successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"  ✗ Failed to import {gpkg_path.name}: {e.stderr}")
        return False


def create_extensions(host: str, port: str, db: str, user: str, password: str):
    """Create required PostgreSQL extensions."""
    import psycopg2

    logger.info("Creating PostgreSQL extensions...")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()

        extensions = ["postgis", "postgis_topology", "pg_trgm"]
        for ext in extensions:
            try:
                cursor.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                logger.info(f"  ✓ Extension: {ext}")
            except Exception as e:
                logger.warning(f"  ⚠ Extension {ext}: {e}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to create extensions: {e}")
        return False


def create_indexes(host: str, port: str, db: str, user: str, password: str):
    """Create performance indexes."""
    import psycopg2

    logger.info("Creating indexes...")

    indexes = [
        # Parcels indexes
        ("parcels", "id_dzialki", "idx_parcels_id_dzialki"),
        ("parcels", "gmina", "idx_parcels_gmina"),
        ("parcels", "dzielnica", "idx_parcels_dzielnica"),
        ("parcels", "quietness_score", "idx_parcels_quietness"),
        ("parcels", "nature_score", "idx_parcels_nature"),
        ("parcels", "accessibility_score", "idx_parcels_accessibility"),
        ("parcels", "area_m2", "idx_parcels_area"),
        ("parcels", "kategoria_ciszy", "idx_parcels_kat_ciszy"),
        ("parcels", "kategoria_natury", "idx_parcels_kat_natury"),

        # POG zones indexes
        ("pog_zones", "symbol", "idx_pog_symbol"),
        ("pog_zones", "gmina", "idx_pog_gmina"),

        # Buildings
        ("buildings", "funkcjaogolnabudynku", "idx_buildings_funkcja"),
    ]

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()

        for table, column, idx_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})")
                logger.info(f"  ✓ Index: {idx_name}")
            except Exception as e:
                logger.warning(f"  ⚠ Index {idx_name}: {e}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        return False


def verify_import(host: str, port: str, db: str, user: str, password: str):
    """Verify the import was successful."""
    import psycopg2

    logger.info("Verifying import...")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        # Get table counts
        cursor.execute("""
            SELECT
                relname AS table_name,
                n_live_tup AS row_count
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC
        """)

        logger.info("  Table counts:")
        total = 0
        for table_name, count in cursor.fetchall():
            logger.info(f"    {table_name}: {count:,}")
            total += count

        logger.info(f"  Total rows: {total:,}")

        # Sample query
        cursor.execute("""
            SELECT
                gmina,
                COUNT(*) as count,
                AVG(quietness_score) as avg_quietness
            FROM parcels
            GROUP BY gmina
            ORDER BY count DESC
        """)

        logger.info("  Parcels by gmina:")
        for gmina, count, avg_quietness in cursor.fetchall():
            logger.info(f"    {gmina}: {count:,} (avg quietness: {avg_quietness:.1f})")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Import GeoPackage files into PostGIS")
    parser.add_argument("--host", default=DEFAULT_HOST, help="PostgreSQL host")
    parser.add_argument("--port", default=DEFAULT_PORT, help="PostgreSQL port")
    parser.add_argument("--db", default=DEFAULT_DB, help="Database name")
    parser.add_argument("--user", default=DEFAULT_USER, help="Database user")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Database password")
    parser.add_argument("--skip-extensions", action="store_true", help="Skip extension creation")
    parser.add_argument("--skip-indexes", action="store_true", help="Skip index creation")
    parser.add_argument("--only", nargs="+", help="Only import specific files")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("POSTGIS IMPORT")
    logger.info("=" * 60)

    # Check GPKG directory
    if not GPKG_DIR.exists():
        logger.error(f"GPKG directory not found: {GPKG_DIR}")
        return 1

    logger.info(f"Source: {GPKG_DIR}")
    logger.info(f"Target: {args.host}:{args.port}/{args.db}")
    logger.info("")

    # Phase 1: Extensions
    if not args.skip_extensions:
        create_extensions(args.host, args.port, args.db, args.user, args.password)

    # Phase 2: Import files
    logger.info("Importing GeoPackage files...")

    success_count = 0
    fail_count = 0

    for gpkg_file in sorted(GPKG_DIR.glob("*.gpkg")):
        if args.only and gpkg_file.name not in args.only:
            continue

        table_name = TABLE_MAPPING.get(gpkg_file.name)
        if table_name is None:
            logger.warning(f"  ⚠ Unknown file {gpkg_file.name}, using filename as table name")
            table_name = gpkg_file.stem.replace("-", "_")

        if import_gpkg(
            gpkg_file,
            table_name,
            args.host,
            args.port,
            args.db,
            args.user,
            args.password
        ):
            success_count += 1
        else:
            fail_count += 1

    # Phase 3: Indexes
    if not args.skip_indexes:
        create_indexes(args.host, args.port, args.db, args.user, args.password)

    # Phase 4: Verify
    verify_import(args.host, args.port, args.db, args.user, args.password)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    if fail_count == 0:
        logger.info(f"✅ POSTGIS IMPORT COMPLETE ({success_count} files)")
    else:
        logger.info(f"⚠️  POSTGIS IMPORT PARTIAL ({success_count} success, {fail_count} failed)")
    logger.info("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit(main())
