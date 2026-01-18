#!/usr/bin/env python3
"""
03_feature_engineering.py - Feature Engineering Script

Calculates features for each parcel:
1. Distance features (to schools, shops, bus stops, roads, etc.)
2. Buffer features (land cover percentages in 500m radius)
3. MPZP features (coverage, symbol)
4. Composite features (quietness score, road access)

Usage:
    python scripts/pipeline/03_feature_engineering.py

Output:
    data/processed/v1.0.0/parcel_features.parquet
    data/processed/v1.0.0/parcel_features.gpkg
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
import warnings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    CLEANED_PARCELS_FILE,
    CLEANED_BDOT10K_DIR,
    CLEANED_MPZP_FILE,
    PARCEL_FEATURES_FILE,
    PARCEL_FEATURES_GPKG,
    TARGET_CRS,
    FEATURE_CONFIG,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info, ProgressLogger
from utils.io import load_geopackage, save_geopackage, save_parquet
from utils.spatial import (
    find_nearest_distance,
    prepare_target_kdtree,
    calculate_buffer_coverage,
    count_features_in_buffer,
)

# Setup logger
logger = setup_logger(level="INFO")


def load_cleaned_data():
    """Load all cleaned datasets."""
    logger.info("Loading cleaned datasets...")

    # Load parcels
    parcels = load_geopackage(CLEANED_PARCELS_FILE, logger=logger)

    # Load BDOT10k layers
    bdot10k = {}
    bdot10k_files = [
        ("buildings", "bdot10k_buildings.gpkg"),
        ("roads", "bdot10k_roads.gpkg"),
        ("forest", "bdot10k_forest.gpkg"),
        ("water", "bdot10k_water.gpkg"),
        ("poi", "bdot10k_poi.gpkg"),
        ("protected", "bdot10k_protected.gpkg"),
        ("industrial", "bdot10k_industrial.gpkg"),
    ]

    for name, filename in bdot10k_files:
        filepath = CLEANED_BDOT10K_DIR / filename
        if filepath.exists():
            bdot10k[name] = load_geopackage(filepath, logger=logger)
        else:
            logger.warning(f"  {filename} not found")
            bdot10k[name] = None

    # Load MPZP
    mpzp = None
    if CLEANED_MPZP_FILE.exists():
        mpzp = load_geopackage(CLEANED_MPZP_FILE, logger=logger)
    else:
        logger.warning("  MPZP not found")

    return parcels, bdot10k, mpzp


def extract_poi_by_type(poi_gdf: gpd.GeoDataFrame, poi_type: str) -> gpd.GeoDataFrame:
    """Extract POIs of a specific type."""
    if poi_gdf is None or poi_gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    if "poi_type" not in poi_gdf.columns:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    filtered = poi_gdf[poi_gdf["poi_type"] == poi_type]
    return filtered if not filtered.empty else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)


def extract_buildings_by_category(buildings_gdf: gpd.GeoDataFrame, category: str) -> gpd.GeoDataFrame:
    """Extract buildings of a specific category."""
    if buildings_gdf is None or buildings_gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    if "kategoria_uproszczona" not in buildings_gdf.columns:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    filtered = buildings_gdf[buildings_gdf["kategoria_uproszczona"] == category]
    return filtered if not filtered.empty else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)


def extract_main_roads(roads_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Extract main roads (autostrada, ekspresowa, glowna, zbiorcza)."""
    if roads_gdf is None or roads_gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    if "typ_drogi" not in roads_gdf.columns:
        return roads_gdf

    main_types = ["autostrada", "ekspresowa", "glowna", "zbiorcza"]
    filtered = roads_gdf[roads_gdf["typ_drogi"].isin(main_types)]
    return filtered if not filtered.empty else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)


def calculate_distance_features(
    parcels: gpd.GeoDataFrame,
    bdot10k: Dict[str, gpd.GeoDataFrame],
    batch_size: int = 100000  # Increased from 10k to 100k for better RAM usage
) -> gpd.GeoDataFrame:
    """
    Calculate distance features for each parcel.

    OPTIMIZED VERSION:
    - Pre-builds KD-tree once per target type (major speedup!)
    - Uses workers=-1 for parallel KD-tree queries
    - Larger batch size for better memory utilization

    Features:
    - dist_to_school
    - dist_to_shop
    - dist_to_hospital
    - dist_to_bus_stop
    - dist_to_public_road
    - dist_to_main_road
    - dist_to_forest
    - dist_to_water
    - dist_to_industrial
    """
    logger.info("Calculating distance features (OPTIMIZED)...")

    max_distance = FEATURE_CONFIG.max_distance

    # Define distance features
    distance_features = {
        "dist_to_school": lambda: extract_poi_by_type(bdot10k.get("poi"), "szkola"),
        "dist_to_shop": lambda: extract_poi_by_type(bdot10k.get("poi"), "sklep"),
        "dist_to_hospital": lambda: extract_poi_by_type(bdot10k.get("poi"), "szpital_przychodnia"),
        "dist_to_bus_stop": lambda: extract_poi_by_type(bdot10k.get("poi"), "przystanek"),
        "dist_to_public_road": lambda: bdot10k.get("roads") if bdot10k.get("roads") is not None else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS),
        "dist_to_main_road": lambda: extract_main_roads(bdot10k.get("roads")),
        "dist_to_forest": lambda: bdot10k.get("forest") if bdot10k.get("forest") is not None else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS),
        "dist_to_water": lambda: bdot10k.get("water") if bdot10k.get("water") is not None else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS),
        "dist_to_industrial": lambda: bdot10k.get("industrial") if bdot10k.get("industrial") is not None else gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS),
    }

    # Initialize columns
    for feature_name in distance_features.keys():
        parcels[feature_name] = max_distance

    # Calculate each feature
    for feature_name, get_targets in distance_features.items():
        logger.info(f"  Calculating {feature_name}...")

        try:
            targets = get_targets()

            if targets.empty:
                logger.warning(f"    No targets found for {feature_name}")
                continue

            logger.info(f"    Using {len(targets):,} target features")

            # PRE-BUILD KD-tree once (MAJOR OPTIMIZATION!)
            kdtree = prepare_target_kdtree(targets, spacing=100, logger=logger)

            if kdtree is None:
                logger.warning(f"    Could not build KD-tree for {feature_name}")
                continue

            # Calculate distances in batches (larger batches now)
            n_batches = (len(parcels) + batch_size - 1) // batch_size
            progress = ProgressLogger(n_batches, f"    {feature_name}", log_every=10, logger_instance=logger)

            for i in range(0, len(parcels), batch_size):
                batch_end = min(i + batch_size, len(parcels))
                batch = parcels.iloc[i:batch_end]

                # Use prebuilt KD-tree (no rebuild per batch!)
                distances = find_nearest_distance(
                    batch, targets,
                    max_distance=max_distance,
                    prebuilt_tree=kdtree
                )
                parcels.loc[batch.index, feature_name] = distances

                progress.update()

            # Summary
            mean_dist = parcels[feature_name].mean()
            min_dist = parcels[feature_name].min()
            logger.info(f"    Mean distance: {mean_dist:.0f}m, Min: {min_dist:.0f}m")

        except Exception as e:
            logger.error(f"    Error calculating {feature_name}: {e}")
            import traceback
            traceback.print_exc()

    return parcels


def calculate_buffer_features(
    parcels: gpd.GeoDataFrame,
    bdot10k: Dict[str, gpd.GeoDataFrame],
    buffer_radius: int = 500,
    batch_size: int = 5000
) -> gpd.GeoDataFrame:
    """
    Calculate buffer features (500m radius around centroid).

    Features:
    - pct_forest_500m
    - pct_water_500m
    - pct_builtup_500m
    - count_buildings_500m
    """
    logger.info(f"Calculating buffer features (radius: {buffer_radius}m)...")

    # Initialize columns
    parcels["pct_forest_500m"] = 0.0
    parcels["pct_water_500m"] = 0.0
    parcels["count_buildings_500m"] = 0

    # Get centroids once
    logger.info("  Computing centroids...")
    centroids = np.column_stack([
        parcels.geometry.centroid.x,
        parcels.geometry.centroid.y
    ])

    # Forest coverage
    if bdot10k.get("forest") is not None and not bdot10k["forest"].empty:
        logger.info("  Calculating forest coverage in buffer...")
        n_batches = (len(parcels) + batch_size - 1) // batch_size
        progress = ProgressLogger(n_batches, "    pct_forest_500m", log_every=25, logger_instance=logger)

        for i in range(0, len(parcels), batch_size):
            batch_end = min(i + batch_size, len(parcels))
            batch = parcels.iloc[i:batch_end]
            batch_centroids = centroids[i:batch_end]

            coverages = calculate_buffer_coverage(
                batch, bdot10k["forest"], buffer_radius, batch_centroids
            )
            parcels.loc[batch.index, "pct_forest_500m"] = coverages
            progress.update()

        logger.info(f"    Mean forest coverage: {parcels['pct_forest_500m'].mean():.2%}")

    # Water coverage
    if bdot10k.get("water") is not None and not bdot10k["water"].empty:
        logger.info("  Calculating water coverage in buffer...")
        n_batches = (len(parcels) + batch_size - 1) // batch_size
        progress = ProgressLogger(n_batches, "    pct_water_500m", log_every=25, logger_instance=logger)

        for i in range(0, len(parcels), batch_size):
            batch_end = min(i + batch_size, len(parcels))
            batch = parcels.iloc[i:batch_end]
            batch_centroids = centroids[i:batch_end]

            coverages = calculate_buffer_coverage(
                batch, bdot10k["water"], buffer_radius, batch_centroids
            )
            parcels.loc[batch.index, "pct_water_500m"] = coverages
            progress.update()

        logger.info(f"    Mean water coverage: {parcels['pct_water_500m'].mean():.2%}")

    # Building count
    if bdot10k.get("buildings") is not None and not bdot10k["buildings"].empty:
        logger.info("  Counting buildings in buffer...")
        n_batches = (len(parcels) + batch_size - 1) // batch_size
        progress = ProgressLogger(n_batches, "    count_buildings_500m", log_every=25, logger_instance=logger)

        for i in range(0, len(parcels), batch_size):
            batch_end = min(i + batch_size, len(parcels))
            batch = parcels.iloc[i:batch_end]

            counts = count_features_in_buffer(batch, bdot10k["buildings"], buffer_radius)
            parcels.loc[batch.index, "count_buildings_500m"] = counts
            progress.update()

        logger.info(f"    Mean building count: {parcels['count_buildings_500m'].mean():.1f}")

    return parcels


def calculate_mpzp_features(
    parcels: gpd.GeoDataFrame,
    mpzp: Optional[gpd.GeoDataFrame]
) -> gpd.GeoDataFrame:
    """
    Calculate MPZP features.

    Features:
    - has_mpzp (boolean)
    - mpzp_symbol (main symbol or None)
    - mpzp_przeznaczenie (primary destination)
    - mpzp_czy_budowlane (is buildable)
    """
    logger.info("Calculating MPZP features...")

    # Initialize columns
    parcels["has_mpzp"] = False
    parcels["mpzp_symbol"] = None
    parcels["mpzp_przeznaczenie"] = None
    parcels["mpzp_czy_budowlane"] = None

    if mpzp is None or mpzp.empty:
        logger.warning("  No MPZP data available")
        return parcels

    # Ensure same CRS
    if mpzp.crs != parcels.crs:
        mpzp = mpzp.to_crs(parcels.crs)

    # Use centroids for point-in-polygon
    logger.info("  Computing centroid intersections with MPZP...")
    parcels_centroids = parcels.copy()
    parcels_centroids["geometry"] = parcels_centroids.geometry.centroid

    # Columns to transfer
    mpzp_cols = ["geometry"]
    if "symbol_glowny" in mpzp.columns:
        mpzp_cols.append("symbol_glowny")
    if "przeznaczenie_podstawowe" in mpzp.columns:
        mpzp_cols.append("przeznaczenie_podstawowe")
    if "czy_budowlane" in mpzp.columns:
        mpzp_cols.append("czy_budowlane")

    # Spatial join
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        joined = gpd.sjoin(
            parcels_centroids[["geometry"]],
            mpzp[mpzp_cols],
            how="left",
            predicate="within"
        )

    # Handle duplicates (keep first match)
    joined = joined[~joined.index.duplicated(keep="first")]

    # Assign features
    has_mpzp = joined["index_right"].notna()
    parcels.loc[joined.index, "has_mpzp"] = has_mpzp.values

    if "symbol_glowny" in joined.columns:
        parcels.loc[joined.index, "mpzp_symbol"] = joined["symbol_glowny"].values

    if "przeznaczenie_podstawowe" in joined.columns:
        parcels.loc[joined.index, "mpzp_przeznaczenie"] = joined["przeznaczenie_podstawowe"].values

    if "czy_budowlane" in joined.columns:
        parcels.loc[joined.index, "mpzp_czy_budowlane"] = joined["czy_budowlane"].values

    # Summary
    mpzp_count = parcels["has_mpzp"].sum()
    logger.info(f"  Parcels with MPZP: {mpzp_count:,} ({mpzp_count/len(parcels)*100:.1f}%)")

    if "mpzp_symbol" in parcels.columns:
        symbol_counts = parcels["mpzp_symbol"].value_counts().head(5)
        logger.info("  Top MPZP symbols:")
        for sym, count in symbol_counts.items():
            logger.info(f"    {sym}: {count:,}")

    return parcels


def calculate_composite_features(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Calculate composite/derived features.

    Features:
    - quietness_score (100 - penalty for industrial/highway proximity)
    - has_public_road_access (dist_to_public_road < 100m)
    - nature_score (forest + water proximity)
    """
    logger.info("Calculating composite features...")

    # Quietness score (penalize industrial and highway proximity)
    def calc_quietness(row):
        score = 100

        # Penalty for industrial proximity
        if "dist_to_industrial" in row and row["dist_to_industrial"] < 1000:
            penalty = (1000 - row["dist_to_industrial"]) / 1000 * 30
            score -= penalty

        # Penalty for main road proximity
        if "dist_to_main_road" in row and row["dist_to_main_road"] < 500:
            penalty = (500 - row["dist_to_main_road"]) / 500 * 20
            score -= penalty

        return max(0, min(100, score))

    logger.info("  Computing quietness_score...")
    parcels["quietness_score"] = parcels.apply(calc_quietness, axis=1)
    logger.info(f"    Mean quietness: {parcels['quietness_score'].mean():.1f}")

    # Road access
    logger.info("  Computing has_public_road_access...")
    if "dist_to_public_road" in parcels.columns:
        parcels["has_public_road_access"] = parcels["dist_to_public_road"] < 100
        access_count = parcels["has_public_road_access"].sum()
        logger.info(f"    Parcels with road access: {access_count:,} ({access_count/len(parcels)*100:.1f}%)")
    else:
        parcels["has_public_road_access"] = False

    # Nature score (proximity to forest/water)
    def calc_nature_score(row):
        score = 0

        # Bonus for forest proximity
        if "dist_to_forest" in row and row["dist_to_forest"] < 1000:
            bonus = (1000 - row["dist_to_forest"]) / 1000 * 40
            score += bonus

        # Bonus for water proximity
        if "dist_to_water" in row and row["dist_to_water"] < 1000:
            bonus = (1000 - row["dist_to_water"]) / 1000 * 30
            score += bonus

        # Bonus for forest in buffer
        if "pct_forest_500m" in row:
            score += row["pct_forest_500m"] * 20

        # Bonus for water in buffer
        if "pct_water_500m" in row:
            score += row["pct_water_500m"] * 10

        return min(100, score)

    logger.info("  Computing nature_score...")
    parcels["nature_score"] = parcels.apply(calc_nature_score, axis=1)
    logger.info(f"    Mean nature score: {parcels['nature_score'].mean():.1f}")

    # Accessibility score (proximity to amenities)
    def calc_accessibility_score(row):
        score = 0
        max_dist = 5000

        features = [
            ("dist_to_school", 20),
            ("dist_to_shop", 15),
            ("dist_to_bus_stop", 20),
            ("dist_to_hospital", 15),
        ]

        for col, weight in features:
            if col in row and row[col] < max_dist:
                bonus = (max_dist - row[col]) / max_dist * weight
                score += bonus

        # Bonus for road access
        if row.get("has_public_road_access", False):
            score += 30

        return min(100, score)

    logger.info("  Computing accessibility_score...")
    parcels["accessibility_score"] = parcels.apply(calc_accessibility_score, axis=1)
    logger.info(f"    Mean accessibility: {parcels['accessibility_score'].mean():.1f}")

    return parcels


def main():
    """Main feature engineering function."""
    logger.info("=" * 60)
    logger.info("FEATURE ENGINEERING")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Load data
    logger.info("\n--- Loading Data ---")
    parcels, bdot10k, mpzp = load_cleaned_data()

    if parcels is None or parcels.empty:
        logger.error("No parcels data found!")
        return 1

    log_dataframe_info(parcels, "Input Parcels", logger)

    # Calculate features
    logger.info("\n--- Distance Features ---")
    parcels = calculate_distance_features(parcels, bdot10k)

    logger.info("\n--- Buffer Features ---")
    parcels = calculate_buffer_features(parcels, bdot10k)

    logger.info("\n--- MPZP Features ---")
    parcels = calculate_mpzp_features(parcels, mpzp)

    logger.info("\n--- Composite Features ---")
    parcels = calculate_composite_features(parcels)

    # Final summary
    logger.info("\n--- Final Summary ---")
    log_dataframe_info(parcels, "Parcel Features", logger)

    # Check NULL ratios
    null_cols = []
    for col in parcels.columns:
        if col == "geometry":
            continue
        null_ratio = parcels[col].isna().sum() / len(parcels)
        if null_ratio > 0.05:
            null_cols.append((col, null_ratio))

    if null_cols:
        logger.warning("Columns with >5% NULL values:")
        for col, ratio in null_cols:
            logger.warning(f"  {col}: {ratio:.1%}")

    # Save outputs
    logger.info("\n--- Saving Outputs ---")

    # Save as Parquet (for analysis)
    logger.info(f"Saving to {PARCEL_FEATURES_FILE}...")
    save_parquet(parcels, PARCEL_FEATURES_FILE, logger=logger)

    # Save as GeoPackage (for GIS)
    logger.info(f"Saving to {PARCEL_FEATURES_GPKG}...")
    save_geopackage(parcels, PARCEL_FEATURES_GPKG, logger=logger)

    logger.info("=" * 60)
    logger.info("FEATURE ENGINEERING COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
