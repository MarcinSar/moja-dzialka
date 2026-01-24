#!/usr/bin/env python3
"""
03d_osm_with_tags.py - Download OSM data with full tags using osmnx
"""

import logging
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import box

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("/home/marcin/moja-dzialka/egib/data/osm_trojmiasto")

# Bbox for Trójmiasto (N, S, E, W for osmnx)
BBOX = (54.65, 54.25, 19.09, 18.34)  # north, south, east, west

# Categories to download
CATEGORIES = {
    'szkoly': {'amenity': ['school', 'kindergarten', 'college', 'university']},
    'przystanki': {'public_transport': ['stop_position', 'platform', 'station'],
                   'highway': ['bus_stop'],
                   'railway': ['station', 'halt', 'tram_stop']},
    'sklepy': {'shop': True},
    'zdrowie': {'amenity': ['hospital', 'clinic', 'doctors', 'pharmacy', 'dentist']},
    'gastronomia': {'amenity': ['restaurant', 'cafe', 'fast_food', 'bar', 'pub']},
}


def download_category(name: str, tags: dict) -> gpd.GeoDataFrame:
    """Download OSM features with all tags."""
    logger.info(f"Downloading {name}...")

    try:
        gdf = ox.features_from_bbox(bbox=BBOX, tags=tags)

        if len(gdf) > 0:
            # Reset index to get feature_id
            gdf = gdf.reset_index()

            # Convert to EPSG:2180
            gdf = gdf.to_crs("EPSG:2180")

            logger.info(f"  {len(gdf)} features downloaded")
            return gdf
        else:
            logger.info(f"  No features found")
            return None

    except Exception as e:
        logger.error(f"  Error: {e}")
        return None


def analyze_attributes(gdf: gpd.GeoDataFrame, name: str):
    """Analyze attribute completeness."""
    logger.info(f"\n--- {name.upper()} ATTRIBUTES ---")
    logger.info(f"Total: {len(gdf)} features")
    logger.info(f"Geometry types: {gdf.geometry.geom_type.value_counts().to_dict()}")

    # Find columns with >10% fill rate
    useful_cols = []
    for col in gdf.columns:
        if col not in ['geometry', 'osmid', 'element_type']:
            non_null = gdf[col].notna().sum()
            pct = non_null / len(gdf) * 100
            if pct >= 10:
                unique = gdf[col].nunique()
                useful_cols.append((col, non_null, pct, unique))

    useful_cols.sort(key=lambda x: -x[2])

    logger.info(f"\nUseful columns (>10% filled):")
    for col, non_null, pct, unique in useful_cols[:15]:
        logger.info(f"  {col}: {non_null}/{len(gdf)} ({pct:.0f}%), {unique} unique")

    # Check name specifically
    if 'name' in gdf.columns:
        name_pct = gdf['name'].notna().sum() / len(gdf) * 100
        logger.info(f"\n'name' fill rate: {name_pct:.1f}%")
        if name_pct > 0:
            logger.info(f"Examples: {gdf['name'].dropna().head(5).tolist()}")


def main():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    results = {}

    for name, tags in CATEGORIES.items():
        gdf = download_category(name, tags)

        if gdf is not None and len(gdf) > 0:
            # Analyze
            analyze_attributes(gdf, name)

            # Save
            output_file = OUTPUT_PATH / f"{name}_full.gpkg"
            gdf.to_file(output_file, driver='GPKG')
            logger.info(f"Saved to {output_file.name}")

            results[name] = len(gdf)
        else:
            results[name] = 0

    # Summary
    logger.info("\n" + "="*60)
    logger.info("OSM DATA SUMMARY (with tags)")
    logger.info("="*60)
    for name, count in results.items():
        logger.info(f"  {name}: {count:,}")


if __name__ == "__main__":
    main()
