#!/usr/bin/env python3
"""
03b_enrich_admin_data.py - Enrich parcel data with administrative boundaries from BDOT10k

This script adds proper gmina and powiat information to parcels by performing
a spatial join with BDOT10k administrative layers (ADJA_A).

Input:
    - data/processed/v1.0.0/parcel_features.gpkg (or parquet)
    - bdot10k/PL.PZGiK.336.BDOT10k.22_OT_ADJA_A.gpkg (gminy, powiaty)
    - bdot10k/PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg (miejscowości - optional refinement)

Output:
    - Updated parcel_features with correct gmina, powiat, miejscowosc data

Usage:
    python 03b_enrich_admin_data.py           # Process full dataset
    python 03b_enrich_admin_data.py --sample  # Process dev sample only
"""

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# CONFIGURATION
# =============================================================================

BDOT10K_DIR = PROJECT_ROOT / "bdot10k"
ADJA_FILE = BDOT10K_DIR / "PL.PZGiK.336.BDOT10k.22_OT_ADJA_A.gpkg"  # Admin units
ADMS_FILE = BDOT10K_DIR / "PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg"  # Miejscowości

DEV_DATA_DIR = PROJECT_ROOT / "data" / "dev"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "v1.0.0"


# =============================================================================
# FUNCTIONS
# =============================================================================

def load_admin_boundaries() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load gminy, powiaty and miejscowości from BDOT10k."""
    logger.info("Loading administrative boundaries from BDOT10k...")

    # Load ADJA (jednostki administracyjne)
    adja = gpd.read_file(ADJA_FILE)
    logger.info(f"  ADJA: {len(adja)} records")

    # Filter gminy
    gminy = adja[adja['RODZAJ'] == 'gmina'].copy()
    gminy = gminy.rename(columns={
        'NAZWA': 'gmina_nazwa',
        'TERYT': 'gmina_teryt',
        'IDTERYTJEDNOSTKINADRZEDNEJ': 'powiat_teryt'
    })
    gminy = gminy[['gmina_nazwa', 'gmina_teryt', 'powiat_teryt', 'geometry']]
    logger.info(f"  Gminy: {len(gminy)} records")

    # Filter powiaty
    powiaty = adja[adja['RODZAJ'] == 'powiat'].copy()
    powiaty = powiaty.rename(columns={
        'NAZWA': 'powiat_nazwa',
        'TERYT': 'powiat_teryt'
    })
    powiaty = powiaty[['powiat_nazwa', 'powiat_teryt']]
    logger.info(f"  Powiaty: {len(powiaty)} records")

    # Load miejscowości (ADMS)
    adms = gpd.read_file(ADMS_FILE)
    adms = adms.rename(columns={
        'NAZWA': 'miejscowosc_nazwa',
        'RODZAJ': 'rodzaj_miejscowosci',
        'IDENTYFIKATORTERC': 'gmina_terc'
    })
    adms = adms[['miejscowosc_nazwa', 'rodzaj_miejscowosci', 'gmina_terc', 'geometry']]
    logger.info(f"  Miejscowości: {len(adms)} records")

    return gminy, powiaty, adms


def enrich_with_gmina(parcels: gpd.GeoDataFrame, gminy: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign gmina to each parcel via spatial join."""
    logger.info("Performing spatial join with gminy...")

    # Ensure same CRS
    if parcels.crs != gminy.crs:
        logger.info(f"  Reprojecting gminy from {gminy.crs} to {parcels.crs}")
        gminy = gminy.to_crs(parcels.crs)

    # Use parcel centroids for faster join
    parcels_centroids = parcels.copy()
    parcels_centroids['geometry'] = parcels_centroids.geometry.centroid

    # Spatial join
    start = time.time()
    joined = gpd.sjoin(
        parcels_centroids,
        gminy,
        how='left',
        predicate='within'
    )
    elapsed = time.time() - start
    logger.info(f"  Spatial join completed in {elapsed:.1f}s")

    # Handle duplicates (parcel on boundary)
    duplicates = joined.index.duplicated(keep='first')
    if duplicates.sum() > 0:
        logger.info(f"  Removing {duplicates.sum()} duplicate matches")
        joined = joined[~duplicates]

    # Merge back to original parcels
    parcels_result = parcels.copy()
    parcels_result['gmina'] = joined['gmina_nazwa'].values
    parcels_result['gmina_teryt'] = joined['gmina_teryt'].values
    parcels_result['powiat_teryt'] = joined['powiat_teryt'].values

    matched = parcels_result['gmina'].notna().sum()
    logger.info(f"  Matched {matched:,}/{len(parcels):,} parcels to gminy ({100*matched/len(parcels):.1f}%)")

    return parcels_result


def enrich_with_powiat(parcels: gpd.GeoDataFrame, powiaty: pd.DataFrame) -> gpd.GeoDataFrame:
    """Add powiat names based on powiat_teryt."""
    logger.info("Adding powiat names...")

    # Create mapping
    powiat_map = dict(zip(powiaty['powiat_teryt'], powiaty['powiat_nazwa']))

    # Apply mapping
    parcels['powiat'] = parcels['powiat_teryt'].map(powiat_map)

    matched = parcels['powiat'].notna().sum()
    logger.info(f"  Matched {matched:,} parcels to powiaty")

    return parcels


def enrich_with_miejscowosc(parcels: gpd.GeoDataFrame, miejscowosci: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Optionally refine miejscowosc via spatial join."""
    logger.info("Performing spatial join with miejscowości...")

    # Ensure same CRS
    if parcels.crs != miejscowosci.crs:
        miejscowosci = miejscowosci.to_crs(parcels.crs)

    # Use centroids for speed
    parcels_centroids = parcels.copy()
    parcels_centroids['geometry'] = parcels_centroids.geometry.centroid

    # Spatial join
    start = time.time()
    joined = gpd.sjoin(
        parcels_centroids,
        miejscowosci,
        how='left',
        predicate='within'
    )
    elapsed = time.time() - start
    logger.info(f"  Spatial join completed in {elapsed:.1f}s")

    # Handle duplicates
    duplicates = joined.index.duplicated(keep='first')
    if duplicates.sum() > 0:
        joined = joined[~duplicates]

    # Update miejscowosc and rodzaj_miejscowosci
    parcels_result = parcels.copy()
    parcels_result['miejscowosc'] = joined['miejscowosc_nazwa'].values

    # Handle column name conflict (might be suffixed with _left/_right)
    rodzaj_col = 'rodzaj_miejscowosci'
    if rodzaj_col not in joined.columns:
        # Try with suffix
        if 'rodzaj_miejscowosci_right' in joined.columns:
            rodzaj_col = 'rodzaj_miejscowosci_right'
        elif 'rodzaj_miejscowosci_left' in joined.columns:
            rodzaj_col = 'rodzaj_miejscowosci_left'

    if rodzaj_col in joined.columns:
        parcels_result['rodzaj_miejscowosci'] = joined[rodzaj_col].values
    else:
        logger.warning(f"  Could not find rodzaj_miejscowosci column. Available: {list(joined.columns)}")

    matched = parcels_result['miejscowosc'].notna().sum()
    logger.info(f"  Matched {matched:,}/{len(parcels):,} parcels to miejscowości ({100*matched/len(parcels):.1f}%)")

    return parcels_result


def main():
    parser = argparse.ArgumentParser(
        description="Enrich parcel data with BDOT10k administrative boundaries"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Process only dev sample (faster for testing)"
    )
    parser.add_argument(
        "--skip-miejscowosci",
        action="store_true",
        help="Skip miejscowości spatial join (faster)"
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
    logger.info("ENRICHING PARCEL DATA WITH BDOT10K ADMIN BOUNDARIES")
    logger.info("=" * 60)

    # Load administrative boundaries
    gminy, powiaty, miejscowosci = load_admin_boundaries()

    # Load parcels
    if args.sample:
        input_file = DEV_DATA_DIR / "parcels_dev.gpkg"
        output_file = DEV_DATA_DIR / "parcels_dev.gpkg"
    else:
        input_file = PROCESSED_DATA_DIR / "parcel_features.gpkg"
        output_file = PROCESSED_DATA_DIR / "parcel_features.gpkg"

    logger.info(f"\nLoading parcels from {input_file}")
    parcels = gpd.read_file(input_file)
    logger.info(f"  Loaded {len(parcels):,} parcels")

    # Check current state
    if 'gmina' in parcels.columns:
        current_gminy = parcels['gmina'].dropna().unique()
        logger.info(f"  Current gmina values: {current_gminy[:5]}...")

    # Enrich with gmina
    parcels = enrich_with_gmina(parcels, gminy)

    # Enrich with powiat
    parcels = enrich_with_powiat(parcels, powiaty)

    # Optionally enrich with miejscowosci
    if not args.skip_miejscowosci:
        parcels = enrich_with_miejscowosc(parcels, miejscowosci)

    # Clean up temporary columns
    if 'index_right' in parcels.columns:
        parcels = parcels.drop(columns=['index_right'])

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("ENRICHMENT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total parcels: {len(parcels):,}")
    logger.info(f"  With gmina: {parcels['gmina'].notna().sum():,}")
    logger.info(f"  With powiat: {parcels['powiat'].notna().sum():,}")
    logger.info(f"  With miejscowosc: {parcels['miejscowosc'].notna().sum():,}")

    logger.info(f"\nUnique gminy: {parcels['gmina'].nunique()}")
    logger.info(f"Unique powiaty: {parcels['powiat'].nunique()}")

    logger.info(f"\nSample gminy:")
    logger.info(parcels['gmina'].value_counts().head(10).to_string())

    # Save
    logger.info(f"\nSaving to {output_file}")

    # Create backup first
    backup_file = output_file.with_suffix('.gpkg.bak')
    if output_file.exists():
        import shutil
        shutil.copy(output_file, backup_file)
        logger.info(f"  Created backup: {backup_file}")

    parcels.to_file(output_file, driver='GPKG')
    logger.info(f"  Saved {len(parcels):,} parcels")

    # Also save parquet version if full dataset
    if not args.sample:
        parquet_file = PROCESSED_DATA_DIR / "parcel_features.parquet"
        parcels_df = pd.DataFrame(parcels.drop(columns=['geometry']))
        parcels_df.to_parquet(parquet_file)
        logger.info(f"  Saved parquet: {parquet_file}")

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
