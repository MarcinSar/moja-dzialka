#!/usr/bin/env python3
"""
02_clean_parcels.py - Parcel Cleaning Script

Cleans and enriches parcels dataset:
1. Fix invalid geometries
2. Explode MultiPolygons
3. Calculate area
4. Calculate land cover ratios (forest, water, built-up)
5. Assign administrative location (powiat, gmina, miejscowosc)
6. Determine terrain character
7. Add WGS84 centroids

Usage:
    python scripts/pipeline/02_clean_parcels.py

Output:
    data/cleaned/v1.0.0/parcels_cleaned.gpkg
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely import make_valid
import warnings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RAW_PARCELS_FILE,
    RAW_BDOT10K_DIR,
    CLEANED_PARCELS_FILE,
    TARGET_CRS,
    BDOT10K_LAYERS,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info, ProgressLogger
from utils.io import load_geopackage, save_geopackage
from utils.geometry import (
    make_geometries_valid,
    explode_multipolygons,
    calculate_area,
    calculate_centroid_wgs84,
    calculate_compactness,
    calculate_intersection_ratio,
)
from utils.spatial import find_containing_polygon, spatial_join_attributes

# Setup logger
logger = setup_logger(level="INFO")


def load_bdot10k_layer(layer_code: str) -> Optional[gpd.GeoDataFrame]:
    """Load a BDOT10k layer if it exists."""
    if layer_code not in BDOT10K_LAYERS:
        logger.warning(f"Unknown layer code: {layer_code}")
        return None

    filepath = RAW_BDOT10K_DIR / BDOT10K_LAYERS[layer_code]
    if not filepath.exists():
        logger.warning(f"Layer file not found: {filepath}")
        return None

    try:
        gdf = load_geopackage(filepath, logger=logger)
        return gdf
    except Exception as e:
        logger.error(f"Error loading {layer_code}: {e}")
        return None


def fix_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fix invalid geometries and explode MultiPolygons."""
    logger.info("Fixing geometries...")

    original_count = len(gdf)
    invalid_before = (~gdf.geometry.is_valid).sum()
    logger.info(f"  Invalid geometries before: {invalid_before:,}")

    # Make valid
    gdf = make_geometries_valid(gdf, logger=logger)

    invalid_after = (~gdf.geometry.is_valid).sum()
    logger.info(f"  Invalid geometries after: {invalid_after:,}")

    # Explode MultiPolygons
    multi_count = (gdf.geometry.geom_type == "MultiPolygon").sum()
    logger.info(f"  MultiPolygons to explode: {multi_count:,}")

    gdf = explode_multipolygons(gdf, logger=logger)

    logger.info(f"  Records: {original_count:,} -> {len(gdf):,}")

    return gdf


def calculate_land_cover_ratios(
    parcels: gpd.GeoDataFrame,
    batch_size: int = 50000
) -> gpd.GeoDataFrame:
    """
    Calculate land cover ratios for each parcel.

    - forest_ratio: intersection with PTLZ_A
    - water_ratio: intersection with PTWP_A
    - builtup_ratio: intersection with PTZB_A
    """
    logger.info("Calculating land cover ratios...")

    # Initialize columns
    parcels["forest_ratio"] = 0.0
    parcels["water_ratio"] = 0.0
    parcels["builtup_ratio"] = 0.0

    # Load land cover layers
    land_cover_layers = {
        "forest_ratio": "PTLZ_A",
        "water_ratio": "PTWP_A",
        "builtup_ratio": "PTZB_A",
    }

    for ratio_col, layer_code in land_cover_layers.items():
        logger.info(f"  Processing {ratio_col} from {layer_code}...")

        coverage_gdf = load_bdot10k_layer(layer_code)
        if coverage_gdf is None or coverage_gdf.empty:
            logger.warning(f"  Skipping {ratio_col}: no data")
            continue

        # Ensure same CRS
        if coverage_gdf.crs != parcels.crs:
            coverage_gdf = coverage_gdf.to_crs(parcels.crs)

        # Process in batches to avoid memory issues
        n_batches = (len(parcels) + batch_size - 1) // batch_size
        progress = ProgressLogger(n_batches, f"  {ratio_col}", log_every=25, logger_instance=logger)

        for i in range(0, len(parcels), batch_size):
            batch_end = min(i + batch_size, len(parcels))
            batch = parcels.iloc[i:batch_end].copy()

            # Calculate intersection ratio for batch
            batch = calculate_intersection_ratio(batch, coverage_gdf, ratio_col, logger=None)
            parcels.loc[batch.index, ratio_col] = batch[ratio_col]

            progress.update()

        # Summary stats
        mean_ratio = parcels[ratio_col].mean()
        nonzero_count = (parcels[ratio_col] > 0).sum()
        logger.info(f"    Mean {ratio_col}: {mean_ratio:.3f}, Non-zero: {nonzero_count:,}")

    return parcels


def assign_administrative_location(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign administrative location from BDOT10k ADJA/ADMS layers.

    Adds columns:
    - wojewodztwo (always "pomorskie")
    - powiat
    - gmina
    - miejscowosc
    - rodzaj_miejscowosci
    """
    logger.info("Assigning administrative location...")

    # Initialize columns
    parcels["wojewodztwo"] = "pomorskie"
    parcels["powiat"] = None
    parcels["gmina"] = None
    parcels["miejscowosc"] = None
    parcels["rodzaj_miejscowosci"] = None

    # Load administrative layers
    adja = load_bdot10k_layer("ADJA_A")
    adms = load_bdot10k_layer("ADMS_A")

    if adja is not None and not adja.empty:
        logger.info(f"  ADJA_A loaded: {len(adja):,} records")

        # Ensure same CRS
        if adja.crs != parcels.crs:
            adja = adja.to_crs(parcels.crs)

        # Log column names for debugging
        logger.info(f"  ADJA columns: {list(adja.columns)}")

        # Find column names (may vary)
        nazwa_col = next((c for c in adja.columns if "nazwa" in c.lower()), None)
        rodzaj_col = next((c for c in adja.columns if "rodzaj" in c.lower()), None)

        if nazwa_col:
            # Separate powiaty and gminy based on geometry size or other attributes
            # In BDOT10k, ADJA typically contains both powiaty and gminy
            # We'll use spatial join with centroids

            parcels_centroids = parcels.copy()
            parcels_centroids["geometry"] = parcels_centroids.geometry.centroid

            # Spatial join
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                joined = gpd.sjoin(
                    parcels_centroids[["geometry"]],
                    adja[[nazwa_col, "geometry"]].rename(columns={nazwa_col: "admin_nazwa"}),
                    how="left",
                    predicate="within"
                )

            # Handle duplicates
            joined = joined[~joined.index.duplicated(keep="first")]

            # Assign gmina from the join
            parcels.loc[joined.index, "gmina"] = joined["admin_nazwa"]

            assigned_count = parcels["gmina"].notna().sum()
            logger.info(f"  Assigned gmina to {assigned_count:,} parcels")

    if adms is not None and not adms.empty:
        logger.info(f"  ADMS_A loaded: {len(adms):,} records")

        # Ensure same CRS
        if adms.crs != parcels.crs:
            adms = adms.to_crs(parcels.crs)

        logger.info(f"  ADMS columns: {list(adms.columns)}")

        # Find relevant columns
        nazwa_col = next((c for c in adms.columns if "nazwa" in c.lower()), None)
        rodzaj_col = next((c for c in adms.columns if "rodzaj" in c.lower()), None)

        if nazwa_col:
            parcels_centroids = parcels.copy()
            parcels_centroids["geometry"] = parcels_centroids.geometry.centroid

            # Spatial join for miejscowosc
            cols_to_join = [nazwa_col, "geometry"]
            rename_map = {nazwa_col: "miejscowosc_nazwa"}

            if rodzaj_col:
                cols_to_join.insert(1, rodzaj_col)
                rename_map[rodzaj_col] = "miejscowosc_rodzaj"

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                joined = gpd.sjoin(
                    parcels_centroids[["geometry"]],
                    adms[cols_to_join].rename(columns=rename_map),
                    how="left",
                    predicate="within"
                )

            joined = joined[~joined.index.duplicated(keep="first")]

            parcels.loc[joined.index, "miejscowosc"] = joined["miejscowosc_nazwa"]
            if "miejscowosc_rodzaj" in joined.columns:
                parcels.loc[joined.index, "rodzaj_miejscowosci"] = joined["miejscowosc_rodzaj"]

            assigned_count = parcels["miejscowosc"].notna().sum()
            logger.info(f"  Assigned miejscowosc to {assigned_count:,} parcels")

    return parcels


def determine_terrain_character(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Determine terrain character based on land cover ratios.

    Categories:
    - zabudowany: builtup_ratio > 0.3
    - lesny: forest_ratio > 0.5
    - wodny: water_ratio > 0.3
    - rolny: remaining
    - mieszany: no dominant category
    """
    logger.info("Determining terrain character...")

    def get_character(row):
        if row["builtup_ratio"] > 0.3:
            return "zabudowany"
        elif row["forest_ratio"] > 0.5:
            return "lesny"
        elif row["water_ratio"] > 0.3:
            return "wodny"
        elif row["forest_ratio"] > 0.2 or row["water_ratio"] > 0.1 or row["builtup_ratio"] > 0.1:
            return "mieszany"
        else:
            return "rolny"

    parcels["charakter_terenu"] = parcels.apply(get_character, axis=1)

    # Summary
    char_counts = parcels["charakter_terenu"].value_counts()
    logger.info("  Terrain character distribution:")
    for char, count in char_counts.items():
        pct = count / len(parcels) * 100
        logger.info(f"    {char}: {count:,} ({pct:.1f}%)")

    return parcels


def main():
    """Main cleaning function."""
    logger.info("=" * 60)
    logger.info("PARCEL CLEANING")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Load raw parcels
    logger.info(f"\nLoading parcels from {RAW_PARCELS_FILE}...")
    parcels = load_geopackage(RAW_PARCELS_FILE, logger=logger)
    log_dataframe_info(parcels, "Raw Parcels", logger)

    # Store original count
    original_count = len(parcels)

    # Step 1: Fix geometries
    logger.info("\n--- Step 1: Fix Geometries ---")
    parcels = fix_geometries(parcels)

    # Step 2: Calculate area
    logger.info("\n--- Step 2: Calculate Area ---")
    parcels = calculate_area(parcels, "area_m2")
    logger.info(f"  Area range: {parcels['area_m2'].min():.1f} - {parcels['area_m2'].max():.1f} m²")
    logger.info(f"  Area median: {parcels['area_m2'].median():.1f} m²")

    # Step 3: Calculate land cover ratios
    logger.info("\n--- Step 3: Land Cover Ratios ---")
    parcels = calculate_land_cover_ratios(parcels)

    # Step 4: Assign administrative location
    logger.info("\n--- Step 4: Administrative Location ---")
    parcels = assign_administrative_location(parcels)

    # Step 5: Determine terrain character
    logger.info("\n--- Step 5: Terrain Character ---")
    parcels = determine_terrain_character(parcels)

    # Step 6: Calculate centroids
    logger.info("\n--- Step 6: WGS84 Centroids ---")
    parcels = calculate_centroid_wgs84(parcels, source_crs=TARGET_CRS)
    logger.info(f"  Lat range: {parcels['centroid_lat'].min():.4f} - {parcels['centroid_lat'].max():.4f}")
    logger.info(f"  Lon range: {parcels['centroid_lon'].min():.4f} - {parcels['centroid_lon'].max():.4f}")

    # Step 7: Calculate compactness
    logger.info("\n--- Step 7: Compactness ---")
    parcels = calculate_compactness(parcels)
    logger.info(f"  Compactness range: {parcels['compactness'].min():.3f} - {parcels['compactness'].max():.3f}")

    # Final summary
    logger.info("\n--- Final Summary ---")
    log_dataframe_info(parcels, "Cleaned Parcels", logger)

    retention_rate = len(parcels) / original_count * 100
    logger.info(f"Retention rate: {retention_rate:.1f}%")

    # Verify all geometries are valid
    invalid_count = (~parcels.geometry.is_valid).sum()
    logger.info(f"Invalid geometries: {invalid_count:,}")

    # Save
    logger.info(f"\nSaving to {CLEANED_PARCELS_FILE}...")
    save_geopackage(parcels, CLEANED_PARCELS_FILE, logger=logger)

    logger.info("=" * 60)
    logger.info("PARCEL CLEANING COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
