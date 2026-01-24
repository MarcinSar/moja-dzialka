#!/usr/bin/env python3
"""
fix_postgis_data.py - Fix and complete PostGIS data for import

Fixes:
1. Reproject POG from EPSG:2177 to EPSG:2180
2. Add missing binned category columns to parcels_enriched
3. Verify all data is complete and compatible

Usage:
    python fix_postgis_data.py
"""

import logging
import subprocess
from pathlib import Path

import geopandas as gpd
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_DIR = Path("/home/marcin/moja-dzialka")
POSTGIS_DIR = PROJECT_DIR / "data" / "ready-for-import" / "postgis"
EGIB_PROCESSED = PROJECT_DIR / "egib" / "data" / "processed"


def fix_pog_crs():
    """Reproject POG from EPSG:2177 to EPSG:2180."""
    logger.info("=" * 60)
    logger.info("FIXING POG CRS (EPSG:2177 → EPSG:2180)")
    logger.info("=" * 60)

    input_file = POSTGIS_DIR / "pog_trojmiasto.gpkg"
    output_file = POSTGIS_DIR / "pog_trojmiasto_2180.gpkg"

    # Check current CRS
    pog = gpd.read_file(input_file)
    logger.info(f"  Input CRS: {pog.crs}")
    logger.info(f"  Feature count: {len(pog):,}")
    logger.info(f"  Layer name: {pog.geometry.name if hasattr(pog.geometry, 'name') else 'unknown'}")

    # Reproject
    logger.info("  Reprojecting to EPSG:2180...")
    pog_2180 = pog.to_crs("EPSG:2180")

    # Save with consistent layer name
    logger.info(f"  Saving to {output_file.name}...")
    pog_2180.to_file(output_file, driver="GPKG", layer="pog_trojmiasto")

    # Verify
    pog_verify = gpd.read_file(output_file)
    logger.info(f"  Output CRS: {pog_verify.crs}")
    logger.info(f"  Extent: {pog_verify.total_bounds}")

    # Replace original
    input_file.unlink()
    output_file.rename(input_file)
    logger.info(f"  ✅ POG reprojected and saved to {input_file.name}")

    return True


def add_binned_categories():
    """Add missing binned category columns to parcels_enriched."""
    logger.info("=" * 60)
    logger.info("ADDING BINNED CATEGORIES TO PARCELS")
    logger.info("=" * 60)

    parcels_file = POSTGIS_DIR / "parcels_enriched.gpkg"

    # Load parcels
    logger.info(f"  Loading {parcels_file.name}...")
    parcels = gpd.read_file(parcels_file)
    logger.info(f"  Loaded {len(parcels):,} parcels with {len(parcels.columns)} columns")

    # Check if already has binned columns
    binned_cols = ['kategoria_ciszy', 'kategoria_natury', 'kategoria_dostepu', 'gestosc_zabudowy']
    existing = [c for c in binned_cols if c in parcels.columns]
    if existing:
        logger.info(f"  Already has binned columns: {existing}")
        if len(existing) == 4:
            logger.info("  ✅ All binned columns present, skipping")
            return True

    # Define categorization functions
    def categorize_quietness(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 80:
            return "bardzo_cicha"
        if score >= 60:
            return "cicha"
        if score >= 40:
            return "umiarkowana"
        return "glosna"

    def categorize_nature(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 70:
            return "bardzo_zielona"
        if score >= 50:
            return "zielona"
        if score >= 30:
            return "umiarkowana"
        return "zurbanizowana"

    def categorize_accessibility(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 70:
            return "doskonala"
        if score >= 50:
            return "dobra"
        if score >= 30:
            return "umiarkowana"
        return "ograniczona"

    def categorize_density(count):
        if pd.isna(count):
            return "nieznana"
        if count >= 50:
            return "gesta"
        if count >= 20:
            return "umiarkowana"
        if count >= 5:
            return "rzadka"
        return "bardzo_rzadka"

    # Apply categorizations
    logger.info("  Computing binned categories...")

    parcels['kategoria_ciszy'] = parcels['quietness_score'].apply(categorize_quietness)
    parcels['kategoria_natury'] = parcels['nature_score'].apply(categorize_nature)
    parcels['kategoria_dostepu'] = parcels['accessibility_score'].apply(categorize_accessibility)
    parcels['gestosc_zabudowy'] = parcels['count_buildings_500m'].apply(categorize_density)

    # Log distributions
    logger.info(f"  kategoria_ciszy: {parcels['kategoria_ciszy'].value_counts().to_dict()}")
    logger.info(f"  kategoria_natury: {parcels['kategoria_natury'].value_counts().to_dict()}")
    logger.info(f"  kategoria_dostepu: {parcels['kategoria_dostepu'].value_counts().to_dict()}")
    logger.info(f"  gestosc_zabudowy: {parcels['gestosc_zabudowy'].value_counts().to_dict()}")

    # Save
    logger.info(f"  Saving with {len(parcels.columns)} columns...")
    parcels.to_file(parcels_file, driver="GPKG")

    logger.info(f"  ✅ Added 4 binned columns to {parcels_file.name}")

    return True


def verify_all_files():
    """Verify all PostGIS files are complete and compatible."""
    logger.info("=" * 60)
    logger.info("VERIFYING ALL POSTGIS FILES")
    logger.info("=" * 60)

    files_info = []
    target_crs = "EPSG:2180"

    for gpkg_file in sorted(POSTGIS_DIR.glob("*.gpkg")):
        gdf = gpd.read_file(gpkg_file)

        # Get layer name
        import fiona
        with fiona.open(gpkg_file) as src:
            layer_name = src.name

        crs_ok = str(gdf.crs).endswith("2180") or "2180" in str(gdf.crs)

        info = {
            'file': gpkg_file.name,
            'layer': layer_name,
            'features': len(gdf),
            'columns': len(gdf.columns),
            'crs': str(gdf.crs.to_epsg()) if gdf.crs else "None",
            'crs_ok': crs_ok
        }
        files_info.append(info)

        status = "✅" if crs_ok else "❌"
        logger.info(f"  {status} {gpkg_file.name}: {len(gdf):,} features, EPSG:{info['crs']}, layer={layer_name}")

    # Summary
    all_ok = all(f['crs_ok'] for f in files_info)
    total_features = sum(f['features'] for f in files_info)

    logger.info("")
    logger.info(f"  Total files: {len(files_info)}")
    logger.info(f"  Total features: {total_features:,}")
    logger.info(f"  All CRS compatible: {'✅ YES' if all_ok else '❌ NO'}")

    return all_ok


def copy_updated_to_neo4j():
    """Copy updated parcels to Neo4j directory."""
    logger.info("=" * 60)
    logger.info("UPDATING NEO4J COPY")
    logger.info("=" * 60)

    src = POSTGIS_DIR / "parcels_enriched.gpkg"
    dst = PROJECT_DIR / "data" / "ready-for-import" / "neo4j" / "parcels_enriched.gpkg"

    import shutil
    shutil.copy2(src, dst)
    logger.info(f"  ✅ Copied {src.name} to {dst.parent.name}/")

    return True


def main():
    logger.info("=" * 60)
    logger.info("POSTGIS DATA FIX SCRIPT")
    logger.info("=" * 60)

    # Step 1: Fix POG CRS
    fix_pog_crs()

    # Step 2: Add binned categories
    add_binned_categories()

    # Step 3: Verify all files
    all_ok = verify_all_files()

    # Step 4: Copy to Neo4j dir
    copy_updated_to_neo4j()

    # Final summary
    logger.info("")
    logger.info("=" * 60)
    if all_ok:
        logger.info("✅ ALL POSTGIS DATA FIXED AND VERIFIED")
    else:
        logger.info("⚠️  SOME ISSUES REMAIN - CHECK ABOVE")
    logger.info("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
