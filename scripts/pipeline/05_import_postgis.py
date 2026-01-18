#!/usr/bin/env python3
"""
05_import_postgis.py - Import parcel data to PostGIS

This script imports parcel features from GeoPackage/Parquet to PostGIS database.
Supports both dev sample (--sample flag) and full dataset.

Usage:
    python 05_import_postgis.py --sample    # Import dev sample (10k parcels)
    python 05_import_postgis.py             # Import full dataset (1.3M parcels)

Requirements:
    - PostGIS database running (docker-compose up postgres)
    - Data files in data/dev/ or data/processed/v1.0.0/

Environment variables (or .env file):
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=moja_dzialka
    POSTGRES_USER=app
    POSTGRES_PASSWORD=secret
"""

import argparse
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text
from geoalchemy2 import Geometry, WKTElement

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.config import (
    DEV_DATA_DIR,
    PROCESSED_DATA_DIR,
    PARCEL_FEATURES_GPKG,
    TARGET_CRS,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default database connection (override via environment)
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "moja_dzialka"),
    "user": os.getenv("POSTGRES_USER", "app"),
    "password": os.getenv("POSTGRES_PASSWORD", "secret"),
}

# Batch size for bulk inserts
BATCH_SIZE = 5000

# Column mapping: GeoDataFrame column -> PostGIS column
COLUMN_MAPPING = {
    "ID_DZIALKI": "id_dzialki",
    "TERYT_POWIAT": "teryt_powiat",
    "area_m2": "area_m2",
    "forest_ratio": "forest_ratio",
    "water_ratio": "water_ratio",
    "builtup_ratio": "builtup_ratio",
    "wojewodztwo": "wojewodztwo",
    "powiat": "powiat",
    "gmina": "gmina",
    "miejscowosc": "miejscowosc",
    "rodzaj_miejscowosci": "rodzaj_miejscowosci",
    "charakter_terenu": "charakter_terenu",
    "centroid_lat": "centroid_lat",
    "centroid_lon": "centroid_lon",
    "compactness": "compactness",
    "dist_to_school": "dist_to_school",
    "dist_to_shop": "dist_to_shop",
    "dist_to_hospital": "dist_to_hospital",
    "dist_to_bus_stop": "dist_to_bus_stop",
    "dist_to_public_road": "dist_to_public_road",
    "dist_to_main_road": "dist_to_main_road",
    "dist_to_forest": "dist_to_forest",
    "dist_to_water": "dist_to_water",
    "dist_to_industrial": "dist_to_industrial",
    "pct_forest_500m": "pct_forest_500m",
    "pct_water_500m": "pct_water_500m",
    "count_buildings_500m": "count_buildings_500m",
    "has_mpzp": "has_mpzp",
    "mpzp_symbol": "mpzp_symbol",
    "mpzp_przeznaczenie": "mpzp_przeznaczenie",
    "mpzp_czy_budowlane": "mpzp_czy_budowlane",
    "quietness_score": "quietness_score",
    "has_public_road_access": "has_public_road_access",
    "nature_score": "nature_score",
    "accessibility_score": "accessibility_score",
}


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_connection_string() -> str:
    """Build PostgreSQL connection string."""
    return (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )


def test_connection(engine) -> bool:
    """Test database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.fetchone()[0]
            logger.info(f"PostGIS version: {version}")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def clear_table(engine):
    """Clear existing data from parcels table."""
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE parcels RESTART IDENTITY CASCADE"))
        conn.commit()
    logger.info("Cleared existing parcels data")


def get_table_count(engine) -> int:
    """Get current row count in parcels table."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM parcels"))
        return result.fetchone()[0]


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(sample: bool = False) -> gpd.GeoDataFrame:
    """
    Load parcel data from file.

    Args:
        sample: If True, load dev sample. Otherwise load full dataset.

    Returns:
        GeoDataFrame with parcel data
    """
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

    # Ensure correct CRS
    if gdf.crs is None:
        gdf = gdf.set_crs(TARGET_CRS)
    elif str(gdf.crs) != TARGET_CRS:
        logger.warning(f"Converting CRS from {gdf.crs} to {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)

    return gdf


def prepare_dataframe(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Prepare GeoDataFrame for PostGIS import.

    Args:
        gdf: Input GeoDataFrame

    Returns:
        DataFrame ready for SQL insert
    """
    # Rename columns to match PostGIS schema
    df = gdf.rename(columns=COLUMN_MAPPING).copy()

    # Keep only columns that exist in mapping (plus geometry)
    valid_cols = list(COLUMN_MAPPING.values()) + ["geometry"]
    cols_to_keep = [c for c in valid_cols if c in df.columns]
    df = df[cols_to_keep]

    # Convert geometry to WKT for PostGIS
    df["geom"] = df["geometry"].apply(lambda g: g.wkt if g is not None else None)
    df = df.drop(columns=["geometry"])

    # Handle NaN values
    df = df.where(pd.notnull(df), None)

    # Convert boolean columns explicitly
    bool_cols = ["has_mpzp", "mpzp_czy_budowlane", "has_public_road_access"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: bool(x) if pd.notna(x) else None)

    # Convert integer columns
    int_cols = ["count_buildings_500m"]
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) else None)

    return df


# =============================================================================
# IMPORT FUNCTIONS
# =============================================================================

def import_batch(engine, batch_df: pd.DataFrame, batch_num: int):
    """
    Import a batch of parcels to PostGIS.

    Args:
        engine: SQLAlchemy engine
        batch_df: DataFrame with batch data
        batch_num: Batch number for logging
    """
    # Build INSERT statement
    columns = [c for c in batch_df.columns if c != "geom"]
    col_names = ", ".join(columns + ["geom"])
    placeholders = ", ".join([f":{c}" for c in columns] + ["ST_GeomFromText(:geom, 2180)"])

    insert_sql = f"""
        INSERT INTO parcels ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (id_dzialki) DO NOTHING
    """

    # Execute batch insert
    with engine.connect() as conn:
        for _, row in batch_df.iterrows():
            params = {c: row[c] for c in columns}
            params["geom"] = row["geom"]
            conn.execute(text(insert_sql), params)
        conn.commit()


def import_with_geopandas(engine, gdf: gpd.GeoDataFrame):
    """
    Import using GeoPandas to_postgis (simpler but slower for large datasets).

    Args:
        engine: SQLAlchemy engine
        gdf: GeoDataFrame to import
    """
    # Rename columns
    gdf_renamed = gdf.rename(columns=COLUMN_MAPPING).copy()

    # Keep only valid columns
    valid_cols = list(COLUMN_MAPPING.values()) + ["geometry"]
    cols_to_keep = [c for c in valid_cols if c in gdf_renamed.columns]
    gdf_renamed = gdf_renamed[cols_to_keep]

    # Rename geometry column to geom
    gdf_renamed = gdf_renamed.rename_geometry("geom")

    # Import to PostGIS
    gdf_renamed.to_postgis(
        name="parcels",
        con=engine,
        if_exists="append",
        index=False,
        dtype={"geom": Geometry("POLYGON", srid=2180)},
    )


def import_data(engine, gdf: gpd.GeoDataFrame, method: str = "geopandas"):
    """
    Import parcel data to PostGIS.

    Args:
        engine: SQLAlchemy engine
        gdf: GeoDataFrame with parcel data
        method: Import method ('geopandas' or 'batch')
    """
    total = len(gdf)
    logger.info(f"Importing {total:,} parcels using {method} method...")

    start_time = time.time()

    if method == "geopandas":
        # Use GeoPandas - simpler, works well for moderate sizes
        import_with_geopandas(engine, gdf)
    else:
        # Use batch inserts - more control, better for very large datasets
        df = prepare_dataframe(gdf)
        num_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, len(df))
            batch_df = df.iloc[start_idx:end_idx]

            import_batch(engine, batch_df, i + 1)

            if (i + 1) % 10 == 0 or (i + 1) == num_batches:
                elapsed = time.time() - start_time
                progress = (end_idx / total) * 100
                rate = end_idx / elapsed
                logger.info(
                    f"Batch {i + 1}/{num_batches}: {end_idx:,}/{total:,} "
                    f"({progress:.1f}%) - {rate:.0f} parcels/sec"
                )

    elapsed = time.time() - start_time
    final_count = get_table_count(engine)
    logger.info(f"Import completed: {final_count:,} parcels in {elapsed:.1f}s")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import parcel data to PostGIS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 05_import_postgis.py --sample           # Dev sample (10k parcels)
    python 05_import_postgis.py                    # Full dataset (1.3M parcels)
    python 05_import_postgis.py --sample --clear   # Clear and reimport sample
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
        "--method",
        choices=["geopandas", "batch"],
        default="geopandas",
        help="Import method (default: geopandas)",
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
    logger.info("POSTGIS IMPORT - moja-dzialka")
    logger.info("=" * 60)

    # Create database engine
    conn_string = get_connection_string()
    logger.info(f"Connecting to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    engine = create_engine(conn_string)

    # Test connection
    if not test_connection(engine):
        logger.error("Cannot connect to database. Is Docker running?")
        logger.info("Start with: docker-compose up -d postgres")
        sys.exit(1)

    # Load data
    try:
        gdf = load_data(sample=args.sample)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run - data loaded successfully, not importing")
        logger.info(f"Columns: {list(gdf.columns)}")
        logger.info(f"Sample:\n{gdf.head(3)}")
        return

    # Clear existing data if requested
    if args.clear:
        clear_table(engine)

    # Check current count
    current_count = get_table_count(engine)
    if current_count > 0 and not args.clear:
        logger.warning(f"Table already contains {current_count:,} rows")
        logger.info("Use --clear to replace existing data")
        response = input("Continue with append? [y/N]: ")
        if response.lower() != "y":
            logger.info("Aborted")
            return

    # Import data
    import_data(engine, gdf, method=args.method)

    # Final stats
    final_count = get_table_count(engine)
    logger.info(f"Final count: {final_count:,} parcels in database")

    # Show sample query
    logger.info("\nSample query to test:")
    logger.info("  SELECT id_dzialki, gmina, area_m2, quietness_score")
    logger.info("  FROM parcels LIMIT 5;")


if __name__ == "__main__":
    main()
