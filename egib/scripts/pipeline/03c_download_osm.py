#!/usr/bin/env python3
"""
03c_download_osm.py - Download OSM data for Trójmiasto using QuackOSM
"""

import logging
from pathlib import Path

import geopandas as gpd
from quackosm import convert_geometry_to_geodataframe
from shapely.geometry import box

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_PATH = Path("/home/marcin/moja-dzialka/egib")
OUTPUT_PATH = BASE_PATH / "data" / "osm_trojmiasto"

# OSM tags to extract
OSM_CATEGORIES = {
    'szkoly': {'amenity': ['school', 'kindergarten', 'college', 'university']},
    'przystanki': {
        'public_transport': ['stop_position', 'platform', 'station'],
        'highway': ['bus_stop'],
        'railway': ['station', 'halt', 'tram_stop'],
    },
    'lasy_parki': {
        'landuse': ['forest'],
        'natural': ['wood'],
        'leisure': ['park', 'nature_reserve'],
    },
    'wody': {
        'natural': ['water'],
        'waterway': ['river', 'stream', 'canal'],
    },
    'przemysl': {'landuse': ['industrial', 'commercial']},
    'sklepy': {'shop': True},
    'zdrowie': {'amenity': ['hospital', 'clinic', 'doctors', 'pharmacy']},
    'gastronomia': {'amenity': ['restaurant', 'cafe', 'fast_food', 'bar']},
}


def main():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Bbox for Trójmiasto (WGS84)
    bbox = box(18.34, 54.25, 19.09, 54.65)

    results = []

    for name, tags in OSM_CATEGORIES.items():
        logger.info(f"\nExtracting {name}...")

        try:
            gdf = convert_geometry_to_geodataframe(
                geometry_filter=bbox,
                tags_filter=tags,
            )

            if gdf is not None and len(gdf) > 0:
                gdf = gdf.to_crs("EPSG:2180")
                output_file = OUTPUT_PATH / f"{name}.gpkg"
                gdf.to_file(output_file, driver='GPKG')
                results.append({'name': name, 'count': len(gdf)})
                logger.info(f"  {len(gdf)} features → {output_file.name}")
            else:
                results.append({'name': name, 'count': 0})
                logger.info(f"  No features found")

        except Exception as e:
            logger.error(f"  Error: {e}")
            results.append({'name': name, 'count': 0, 'error': str(e)})

    # Summary
    logger.info("\n" + "="*60)
    logger.info("OSM TRÓJMIASTO SUMMARY")
    logger.info("="*60)
    for r in results:
        logger.info(f"  {r['name']}: {r.get('count', 0):,}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
