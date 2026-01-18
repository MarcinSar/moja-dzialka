#!/usr/bin/env python3
"""
04_create_dev_sample.py - Development Sample Creation Script

Creates a representative sample of ~10,000 parcels for development:
- Selects 5 target municipalities (Gdansk, Sopot, Zukowo, Kartuzy, Koscierzyna)
- Stratified sampling by area category and MPZP coverage
- Includes special cases (near forest, water, Natura 2000)
- Exports subset of BDOT10k and MPZP for the sample area

Usage:
    python scripts/pipeline/04_create_dev_sample.py

Output:
    data/dev/parcels_dev.gpkg
    data/dev/bdot10k_dev.gpkg
    data/dev/mpzp_dev.gpkg
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box
import warnings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PARCEL_FEATURES_GPKG,
    PARCEL_FEATURES_FILE,
    CLEANED_BDOT10K_DIR,
    CLEANED_MPZP_FILE,
    DEV_DATA_DIR,
    TARGET_CRS,
    DEV_SAMPLE_CONFIG,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info
from utils.io import load_geopackage, save_geopackage, load_parquet

# Setup logger
logger = setup_logger(level="INFO")


def load_parcel_features() -> Optional[gpd.GeoDataFrame]:
    """Load parcel features from processed data."""
    logger.info("Loading parcel features...")

    # Try GeoPackage first
    if PARCEL_FEATURES_GPKG.exists():
        return load_geopackage(PARCEL_FEATURES_GPKG, logger=logger)

    # Try Parquet
    if PARCEL_FEATURES_FILE.exists():
        df = load_parquet(PARCEL_FEATURES_FILE, logger=logger)
        if isinstance(df, gpd.GeoDataFrame):
            return df
        logger.warning("Parquet file is not a GeoDataFrame")
        return None

    logger.error("No parcel features file found!")
    return None


def categorize_area(area: float) -> str:
    """Categorize parcel area."""
    bins = DEV_SAMPLE_CONFIG.area_bins
    names = DEV_SAMPLE_CONFIG.area_bin_names

    for i, (low, high) in enumerate(zip(bins[:-1], bins[1:])):
        if low <= area < high:
            return names[i]
    return names[-1]


def filter_by_municipality(
    parcels: gpd.GeoDataFrame,
    target_teryts: List[str]
) -> gpd.GeoDataFrame:
    """
    Filter parcels to target municipalities.

    Uses gmina column or tries to match TERYT from other columns.
    """
    logger.info(f"Filtering to target municipalities: {target_teryts}")

    # Try to find municipality column
    gmina_col = None
    for col in parcels.columns:
        if "gmina" in col.lower() or "teryt" in col.lower():
            gmina_col = col
            break

    if gmina_col is None:
        logger.warning("No gmina/teryt column found, using geographic filtering")
        return filter_by_geographic_bounds(parcels, target_teryts)

    # Check if we can filter by TERYT
    sample_values = parcels[gmina_col].dropna().head(10).astype(str).tolist()
    logger.info(f"Sample {gmina_col} values: {sample_values}")

    # Try to match by TERYT code or name
    target_names = list(DEV_SAMPLE_CONFIG.target_municipality_names.values())

    # Filter by name match
    def matches_target(value):
        if pd.isna(value):
            return False
        value_str = str(value).lower()

        # Check TERYT codes
        for teryt in target_teryts:
            if teryt in value_str or value_str in teryt:
                return True

        # Check names
        for name in target_names:
            if name.lower() in value_str or value_str in name.lower():
                return True

        return False

    filtered = parcels[parcels[gmina_col].apply(matches_target)]

    if filtered.empty:
        logger.warning("No parcels matched by name/TERYT, falling back to geographic filter")
        return filter_by_geographic_bounds(parcels, target_teryts)

    logger.info(f"Filtered to {len(filtered):,} parcels in target municipalities")
    return filtered


def filter_by_geographic_bounds(
    parcels: gpd.GeoDataFrame,
    target_teryts: List[str]
) -> gpd.GeoDataFrame:
    """
    Filter parcels by approximate geographic bounds of target municipalities.

    Uses known approximate bounds for Pomorskie municipalities.
    """
    logger.info("Using geographic bounds filter...")

    # Approximate bounds for target areas (EPSG:2180)
    # These are rough estimates for the Tri-City area and Kashubian Lake District
    bounds = {
        # Gdansk area
        "gdansk": (460000, 720000, 520000, 760000),
        # Sopot
        "sopot": (467000, 726000, 472000, 732000),
        # Zukowo/Kartuzy area (Kaszuby)
        "kaszuby": (440000, 700000, 480000, 750000),
    }

    # Combine all bounds
    all_minx = min(b[0] for b in bounds.values())
    all_miny = min(b[1] for b in bounds.values())
    all_maxx = max(b[2] for b in bounds.values())
    all_maxy = max(b[3] for b in bounds.values())

    bbox = box(all_minx, all_miny, all_maxx, all_maxy)

    # Filter by bbox
    filtered = parcels[parcels.geometry.intersects(bbox)]

    logger.info(f"Geographic filter: {len(filtered):,} parcels in bounds")
    return filtered


def stratified_sample(
    parcels: gpd.GeoDataFrame,
    target_count: int = 10000
) -> gpd.GeoDataFrame:
    """
    Create stratified sample based on area category and MPZP coverage.
    """
    logger.info(f"Creating stratified sample (target: {target_count:,})...")

    # Add area category
    parcels = parcels.copy()
    parcels["area_category"] = parcels["area_m2"].apply(categorize_area)

    # Create stratification groups
    if "has_mpzp" in parcels.columns:
        parcels["strat_group"] = parcels["area_category"] + "_" + parcels["has_mpzp"].astype(str)
    else:
        parcels["strat_group"] = parcels["area_category"]

    # Calculate sample sizes per group (proportional)
    group_counts = parcels["strat_group"].value_counts()
    total = len(parcels)
    sample_sizes = (group_counts / total * target_count).round().astype(int)

    # Ensure at least 1 per group
    sample_sizes = sample_sizes.apply(lambda x: max(1, x))

    # Adjust if we have too many or too few
    if sample_sizes.sum() > target_count:
        # Reduce proportionally
        factor = target_count / sample_sizes.sum()
        sample_sizes = (sample_sizes * factor).round().astype(int)
    elif sample_sizes.sum() < target_count:
        # Add to largest groups
        diff = target_count - sample_sizes.sum()
        for group in sample_sizes.index[:diff]:
            sample_sizes[group] += 1

    logger.info("  Sample sizes per stratum:")
    for group, size in sample_sizes.head(10).items():
        logger.info(f"    {group}: {size}")

    # Sample from each group
    samples = []
    for group, size in sample_sizes.items():
        group_data = parcels[parcels["strat_group"] == group]
        if len(group_data) <= size:
            samples.append(group_data)
        else:
            samples.append(group_data.sample(n=size, random_state=42))

    result = pd.concat(samples, ignore_index=True)
    logger.info(f"  Stratified sample: {len(result):,} parcels")

    return result


def add_special_cases(
    sample: gpd.GeoDataFrame,
    full_parcels: gpd.GeoDataFrame,
    n_special: int = 500
) -> gpd.GeoDataFrame:
    """
    Add special case parcels (near forest, water, protected areas).
    """
    logger.info(f"Adding special cases (up to {n_special})...")

    special_cases = []

    # Near forest (dist_to_forest < 100m)
    if "dist_to_forest" in full_parcels.columns:
        near_forest = full_parcels[
            (full_parcels["dist_to_forest"] < 100) &
            (~full_parcels.index.isin(sample.index))
        ]
        if not near_forest.empty:
            n = min(n_special // 3, len(near_forest))
            special_cases.append(near_forest.sample(n=n, random_state=42))
            logger.info(f"  Near forest: {n}")

    # Near water (dist_to_water < 100m)
    if "dist_to_water" in full_parcels.columns:
        near_water = full_parcels[
            (full_parcels["dist_to_water"] < 100) &
            (~full_parcels.index.isin(sample.index))
        ]
        if not near_water.empty:
            n = min(n_special // 3, len(near_water))
            special_cases.append(near_water.sample(n=n, random_state=42))
            logger.info(f"  Near water: {n}")

    # High nature score (nature_score > 80)
    if "nature_score" in full_parcels.columns:
        high_nature = full_parcels[
            (full_parcels["nature_score"] > 80) &
            (~full_parcels.index.isin(sample.index))
        ]
        if not high_nature.empty:
            n = min(n_special // 3, len(high_nature))
            special_cases.append(high_nature.sample(n=n, random_state=42))
            logger.info(f"  High nature score: {n}")

    if special_cases:
        combined = pd.concat([sample] + special_cases, ignore_index=True)
        # Remove duplicates
        combined = combined.drop_duplicates(subset=["geometry"], keep="first")
        logger.info(f"  Total with special cases: {len(combined):,}")
        return combined

    return sample


def extract_bdot10k_for_area(sample_bounds: Tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Extract BDOT10k features for the sample area."""
    logger.info("Extracting BDOT10k for sample area...")

    bbox = box(*sample_bounds)
    all_layers = []

    bdot10k_files = list(CLEANED_BDOT10K_DIR.glob("*.gpkg"))
    for filepath in bdot10k_files:
        try:
            gdf = load_geopackage(filepath)
            # Filter by bbox
            filtered = gdf[gdf.geometry.intersects(bbox)]
            if not filtered.empty:
                filtered = filtered.copy()
                filtered["source_layer"] = filepath.stem
                all_layers.append(filtered)
                logger.info(f"  {filepath.stem}: {len(filtered):,} features")
        except Exception as e:
            logger.warning(f"  Error loading {filepath.stem}: {e}")

    if all_layers:
        # Normalize column names to avoid duplicates (e.g., 'nazwa' vs 'NAZWA')
        for i, layer in enumerate(all_layers):
            # Lowercase all column names except geometry
            new_cols = {}
            for col in layer.columns:
                if col != 'geometry':
                    new_cols[col] = col.lower()
            all_layers[i] = layer.rename(columns=new_cols)

        # Combine all layers
        combined = pd.concat(all_layers, ignore_index=True)
        combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=TARGET_CRS)

        # Remove any remaining duplicate columns (keep first)
        combined = combined.loc[:, ~combined.columns.duplicated()]

        return combined

    return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)


def extract_mpzp_for_area(sample_bounds: Tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Extract MPZP for the sample area."""
    logger.info("Extracting MPZP for sample area...")

    if not CLEANED_MPZP_FILE.exists():
        logger.warning("No MPZP file found")
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)

    bbox = box(*sample_bounds)
    mpzp = load_geopackage(CLEANED_MPZP_FILE)
    filtered = mpzp[mpzp.geometry.intersects(bbox)]

    logger.info(f"  MPZP: {len(filtered):,} features")
    return filtered


def main():
    """Main function to create development sample."""
    logger.info("=" * 60)
    logger.info("DEVELOPMENT SAMPLE CREATION")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories
    ensure_directories()
    DEV_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load parcel features
    parcels = load_parcel_features()
    if parcels is None:
        return 1

    log_dataframe_info(parcels, "Full Parcels Dataset", logger)

    # Filter to target municipalities
    target_teryts = DEV_SAMPLE_CONFIG.target_municipalities
    filtered = filter_by_municipality(parcels, target_teryts)

    if filtered.empty:
        logger.error("No parcels found in target municipalities!")
        # Fall back to random sample from full dataset
        logger.info("Falling back to random sample from full dataset...")
        filtered = parcels.sample(
            n=min(DEV_SAMPLE_CONFIG.target_count * 2, len(parcels)),
            random_state=42
        )

    # Create stratified sample
    sample = stratified_sample(filtered, DEV_SAMPLE_CONFIG.target_count)

    # Add special cases
    sample = add_special_cases(sample, filtered)

    # Drop temporary columns
    cols_to_drop = ["strat_group", "area_category"]
    sample = sample.drop(columns=[c for c in cols_to_drop if c in sample.columns])

    # Summary
    logger.info("\n--- Sample Summary ---")
    log_dataframe_info(sample, "Development Sample", logger)

    # Get sample bounds
    sample_bounds = tuple(sample.total_bounds)
    logger.info(f"Sample bounds: {sample_bounds}")

    # Extract supporting data
    logger.info("\n--- Extracting Supporting Data ---")
    bdot10k_sample = extract_bdot10k_for_area(sample_bounds)
    mpzp_sample = extract_mpzp_for_area(sample_bounds)

    # Save outputs
    logger.info("\n--- Saving Outputs ---")

    parcels_path = DEV_DATA_DIR / "parcels_dev.gpkg"
    save_geopackage(sample, parcels_path, logger=logger)

    if not bdot10k_sample.empty:
        bdot10k_path = DEV_DATA_DIR / "bdot10k_dev.gpkg"
        save_geopackage(bdot10k_sample, bdot10k_path, logger=logger)

    if not mpzp_sample.empty:
        mpzp_path = DEV_DATA_DIR / "mpzp_dev.gpkg"
        save_geopackage(mpzp_sample, mpzp_path, logger=logger)

    # Create sample info file
    info = {
        "created": datetime.now().isoformat(),
        "parcel_count": len(sample),
        "target_municipalities": list(DEV_SAMPLE_CONFIG.target_municipality_names.values()),
        "bounds": {
            "minx": sample_bounds[0],
            "miny": sample_bounds[1],
            "maxx": sample_bounds[2],
            "maxy": sample_bounds[3],
        },
        "bdot10k_features": len(bdot10k_sample),
        "mpzp_features": len(mpzp_sample),
    }

    import json
    info_path = DEV_DATA_DIR / "sample_info.json"
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)
    logger.info(f"Saved sample info to {info_path}")

    logger.info("=" * 60)
    logger.info("DEVELOPMENT SAMPLE CREATION COMPLETE")
    logger.info(f"Output directory: {DEV_DATA_DIR}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
