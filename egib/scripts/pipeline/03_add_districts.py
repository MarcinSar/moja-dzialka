#!/usr/bin/env python3
"""
03_add_districts.py - Add administrative hierarchy to parcels

Performs spatial join with BDOT10k ADMS_A to add:
- dzielnica (district/neighborhood) - most valuable for search!
- powiat (county)
- wojewodztwo (voivodeship)

Strategy:
1. Use intersection (not centroid within) to find overlapping districts
2. For parcels overlapping multiple districts - pick the one with largest overlap
3. For parcels with no district match - use city name as fallback

Input:
  - egib/data/processed/parcels_trojmiasto.gpkg (from 02_merge_parcels.py)
  - bdot10k/PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg

Output:
  - Updates parcels_trojmiasto.gpkg with dzielnica, powiat columns
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import unary_union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka")
BDOT10K_PATH = BASE_PATH / "bdot10k"
PROCESSED_PATH = BASE_PATH / "egib" / "data" / "processed"

# ADMS layer
ADMS_FILE = BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg"

# TERYT codes for Trójmiasto
TROJMIASTO_TERYT = {
    '2261': 'Gdańsk',
    '2262': 'Gdynia',
    '2264': 'Sopot',
}

# Fixed values
WOJEWODZTWO = 'pomorskie'


def load_districts_and_cities() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load district polygons and city boundaries from BDOT10k ADMS_A."""
    logger.info(f"Loading administrative data from {ADMS_FILE}")

    gdf = gpd.read_file(ADMS_FILE)

    # Filter to Trójmiasto only
    gdf = gdf[gdf['TERYT'].isin(TROJMIASTO_TERYT.keys())].copy()

    # Separate districts and city boundaries
    districts = gdf[gdf['RODZAJ'] == 'część miasta'].copy()
    cities = gdf[gdf['RODZAJ'] == 'miasto'].copy()

    # Keep relevant columns
    districts = districts[['NAZWA', 'TERYT', 'geometry']].copy()
    districts = districts.rename(columns={'NAZWA': 'dzielnica_nazwa'})
    districts['gmina_adms'] = districts['TERYT'].map(TROJMIASTO_TERYT)

    cities = cities[['NAZWA', 'TERYT', 'geometry']].copy()
    cities['gmina_adms'] = cities['TERYT'].map(TROJMIASTO_TERYT)

    logger.info(f"  Loaded {len(districts)} districts, {len(cities)} city boundaries")

    for teryt, gmina in TROJMIASTO_TERYT.items():
        d_count = (districts['TERYT'] == teryt).sum()
        c_count = (cities['TERYT'] == teryt).sum()
        logger.info(f"    {gmina}: {d_count} districts, {c_count} city boundary")

    return districts, cities


def assign_districts_by_intersection(parcels: gpd.GeoDataFrame,
                                      districts: gpd.GeoDataFrame,
                                      cities: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign district to each parcel based on geometric intersection.

    Strategy:
    1. Find all districts that intersect each parcel
    2. Pick the district with the largest intersection area
    3. For parcels with no district match, use city name as fallback
    """
    logger.info("Assigning districts to parcels by intersection...")

    # Ensure same CRS
    if parcels.crs != districts.crs:
        logger.info(f"  Reprojecting districts from {districts.crs} to {parcels.crs}")
        districts = districts.to_crs(parcels.crs)
        cities = cities.to_crs(parcels.crs)

    # Initialize result column
    parcels['dzielnica'] = None

    # Process by gmina for efficiency
    for gmina in ['Gdańsk', 'Gdynia', 'Sopot']:
        logger.info(f"  Processing {gmina}...")

        # Get parcels and districts for this gmina
        gmina_mask = parcels['gmina'] == gmina
        gmina_parcels = parcels[gmina_mask].copy()
        gmina_districts = districts[districts['gmina_adms'] == gmina].copy()

        if len(gmina_parcels) == 0:
            continue

        if len(gmina_districts) == 0:
            logger.warning(f"    No districts for {gmina}, using city name as fallback")
            parcels.loc[gmina_mask, 'dzielnica'] = gmina
            continue

        # Create spatial index for districts
        districts_sindex = gmina_districts.sindex

        # Process each parcel
        assigned_count = 0
        for idx in gmina_parcels.index:
            parcel_geom = gmina_parcels.loc[idx, 'geometry']

            # Find candidate districts using spatial index
            possible_matches_idx = list(districts_sindex.intersection(parcel_geom.bounds))
            if not possible_matches_idx:
                continue

            possible_districts = gmina_districts.iloc[possible_matches_idx]

            # Calculate actual intersection areas
            best_district = None
            best_area = 0

            for _, district in possible_districts.iterrows():
                try:
                    intersection = parcel_geom.intersection(district['geometry'])
                    area = intersection.area
                    if area > best_area:
                        best_area = area
                        best_district = district['dzielnica_nazwa']
                except:
                    continue

            if best_district and best_area > 0:
                parcels.loc[idx, 'dzielnica'] = best_district
                assigned_count += 1

        # Fallback: use city name for parcels without district
        no_district_mask = gmina_mask & parcels['dzielnica'].isna()
        no_district_count = no_district_mask.sum()
        if no_district_count > 0:
            parcels.loc[no_district_mask, 'dzielnica'] = f"{gmina} (inne)"
            logger.info(f"    Assigned {assigned_count:,} to named districts")
            logger.info(f"    Fallback '{gmina} (inne)' for {no_district_count:,} parcels")
        else:
            logger.info(f"    Assigned all {assigned_count:,} parcels to named districts")

    # Add fixed hierarchy columns
    parcels['wojewodztwo'] = WOJEWODZTWO
    parcels['powiat'] = parcels['gmina']  # Same as gmina for cities

    # Statistics
    named_districts = ~parcels['dzielnica'].str.contains('(inne)', regex=False, na=False)
    logger.info(f"\nTotal: {named_districts.sum():,} parcels with named districts, "
                f"{(~named_districts).sum():,} with fallback")

    return parcels


def analyze_districts(parcels: gpd.GeoDataFrame) -> None:
    """Print district analysis."""
    logger.info("\n" + "="*60)
    logger.info("DISTRICT ANALYSIS")
    logger.info("="*60)

    for gmina in ['Gdańsk', 'Gdynia', 'Sopot']:
        gmina_parcels = parcels[parcels['gmina'] == gmina]
        named = gmina_parcels[~gmina_parcels['dzielnica'].str.contains('(inne)', regex=False, na=False)]
        fallback = gmina_parcels[gmina_parcels['dzielnica'].str.contains('(inne)', regex=False, na=False)]

        logger.info(f"\n{gmina}: {len(named):,} named + {len(fallback):,} fallback = {len(gmina_parcels):,} total")

        # Top districts
        district_counts = named['dzielnica'].value_counts().head(10)
        for district, count in district_counts.items():
            logger.info(f"  {district}: {count:,}")

    # Private parcels by district (for potential buyers)
    logger.info(f"\nTop districts for private parcels (500-3000 m²):")
    private_residential = parcels[
        (parcels['typ_wlasnosci'] == 'prywatna') &
        (parcels['area_m2'] >= 500) &
        (parcels['area_m2'] <= 3000) &
        (~parcels['dzielnica'].str.contains('(inne)', regex=False, na=False))
    ]
    district_counts = private_residential.groupby(['gmina', 'dzielnica']).size().sort_values(ascending=False).head(15)
    for (gmina, district), count in district_counts.items():
        logger.info(f"  {gmina} - {district}: {count:,}")

    logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    logger.info("Starting district assignment pipeline (v2 - intersection based)")

    # Load parcels
    parcels_file = PROCESSED_PATH / "parcels_trojmiasto.gpkg"
    logger.info(f"Loading parcels from {parcels_file}")
    parcels = gpd.read_file(parcels_file)

    # Remove old district columns if they exist
    for col in ['dzielnica', 'wojewodztwo', 'powiat']:
        if col in parcels.columns:
            parcels = parcels.drop(columns=[col])

    logger.info(f"  Loaded {len(parcels):,} parcels")

    # Load districts and city boundaries
    districts, cities = load_districts_and_cities()

    # Assign districts using intersection
    parcels = assign_districts_by_intersection(parcels, districts, cities)

    # Analyze
    analyze_districts(parcels)

    # Reorder columns for clarity
    col_order = [
        'id_dzialki',
        # Location hierarchy
        'wojewodztwo', 'powiat', 'gmina', 'dzielnica',
        # Ownership
        'grupa_rej', 'grupa_rej_nazwa', 'typ_wlasnosci',
        # Basic attributes
        'area_m2', 'centroid_x', 'centroid_y', 'centroid_lat', 'centroid_lon',
        'bbox_width', 'bbox_height', 'shape_index',
        # Geometry
        'geometry'
    ]
    # Keep only columns that exist
    col_order = [c for c in col_order if c in parcels.columns]
    other_cols = [c for c in parcels.columns if c not in col_order]
    parcels = parcels[col_order + other_cols]

    # Save updated parcels
    output_file = PROCESSED_PATH / "parcels_trojmiasto.gpkg"
    parcels.to_file(output_file, driver='GPKG', layer='parcels')
    logger.info(f"Saved {len(parcels):,} parcels to {output_file}")

    # Save updated summary CSV
    summary_file = PROCESSED_PATH / "parcels_trojmiasto_summary.csv"
    summary_df = parcels.drop(columns=['geometry'])
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Saved summary to {summary_file}")

    logger.info("District assignment complete!")


if __name__ == "__main__":
    main()
