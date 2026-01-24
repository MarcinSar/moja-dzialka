#!/usr/bin/env python3
"""
03e_overpass_download.py - Download OSM data via Overpass API

Direct Overpass API queries for better control over tags.
"""

import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, Polygon, LineString, shape

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("/home/marcin/moja-dzialka/egib/data/osm_trojmiasto")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bbox for Trójmiasto (south, west, north, east for Overpass)
BBOX = "54.25,18.34,54.65,19.09"

# Overpass queries
QUERIES = {
    'szkoly': f"""
        [out:json][timeout:120];
        (
          node["amenity"~"school|kindergarten"]({BBOX});
          way["amenity"~"school|kindergarten"]({BBOX});
          relation["amenity"~"school|kindergarten"]({BBOX});
        );
        out body;
        >;
        out skel qt;
    """,
    'przystanki': f"""
        [out:json][timeout:120];
        (
          node["highway"="bus_stop"]({BBOX});
          node["public_transport"~"stop_position|platform|station"]({BBOX});
          node["railway"~"station|halt|tram_stop"]({BBOX});
        );
        out body;
    """,
    'sklepy': f"""
        [out:json][timeout:180];
        (
          node["shop"]({BBOX});
          way["shop"]({BBOX});
        );
        out body;
        >;
        out skel qt;
    """,
    'zdrowie': f"""
        [out:json][timeout:120];
        (
          node["amenity"~"hospital|clinic|doctors|pharmacy|dentist"]({BBOX});
          way["amenity"~"hospital|clinic|doctors|pharmacy|dentist"]({BBOX});
        );
        out body;
        >;
        out skel qt;
    """,
    'gastronomia': f"""
        [out:json][timeout:120];
        (
          node["amenity"~"restaurant|cafe|fast_food|bar|pub"]({BBOX});
          way["amenity"~"restaurant|cafe|fast_food|bar|pub"]({BBOX});
        );
        out body;
        >;
        out skel qt;
    """,
}


def query_overpass(query: str) -> dict:
    """Execute Overpass API query."""
    response = requests.post(OVERPASS_URL, data={'data': query}, timeout=300)
    response.raise_for_status()
    return response.json()


def parse_overpass_response(data: dict) -> gpd.GeoDataFrame:
    """Parse Overpass JSON response to GeoDataFrame."""
    elements = data.get('elements', [])

    # Build node lookup for ways
    nodes = {e['id']: (e['lon'], e['lat']) for e in elements if e['type'] == 'node' and 'lon' in e}

    features = []

    for elem in elements:
        if elem['type'] == 'node' and 'tags' in elem:
            # Node with tags
            geom = Point(elem['lon'], elem['lat'])
            props = elem.get('tags', {})
            props['osm_id'] = f"node/{elem['id']}"
            props['osm_type'] = 'node'
            features.append({'geometry': geom, **props})

        elif elem['type'] == 'way' and 'tags' in elem:
            # Way with tags
            coords = [nodes.get(n) for n in elem.get('nodes', [])]
            coords = [c for c in coords if c is not None]

            if len(coords) >= 3 and coords[0] == coords[-1]:
                geom = Polygon(coords)
            elif len(coords) >= 2:
                geom = LineString(coords)
            else:
                continue

            props = elem.get('tags', {})
            props['osm_id'] = f"way/{elem['id']}"
            props['osm_type'] = 'way'
            features.append({'geometry': geom, **props})

    if not features:
        return gpd.GeoDataFrame()

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    return gdf.to_crs("EPSG:2180")


def analyze_gdf(gdf: gpd.GeoDataFrame, name: str):
    """Analyze and report on GeoDataFrame."""
    logger.info(f"\n--- {name.upper()} ---")
    logger.info(f"Features: {len(gdf)}")

    if len(gdf) == 0:
        return

    logger.info(f"Geometry: {gdf.geometry.geom_type.value_counts().to_dict()}")

    # Check key columns
    key_cols = ['name', 'amenity', 'shop', 'highway', 'public_transport', 'railway',
                'addr:street', 'addr:housenumber', 'addr:city', 'opening_hours', 'phone', 'website']

    logger.info("Key attributes:")
    for col in key_cols:
        if col in gdf.columns:
            count = gdf[col].notna().sum()
            pct = count / len(gdf) * 100
            if pct > 0:
                logger.info(f"  {col}: {count}/{len(gdf)} ({pct:.0f}%)")


def main():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    results = {}

    for name, query in QUERIES.items():
        logger.info(f"\nDownloading {name}...")

        try:
            data = query_overpass(query)
            gdf = parse_overpass_response(data)

            if len(gdf) > 0:
                analyze_gdf(gdf, name)

                output_file = OUTPUT_PATH / f"{name}_full.gpkg"
                gdf.to_file(output_file, driver='GPKG')
                logger.info(f"Saved to {output_file.name}")

                results[name] = len(gdf)
            else:
                results[name] = 0

            # Be nice to Overpass API
            time.sleep(2)

        except Exception as e:
            logger.error(f"Error downloading {name}: {e}")
            results[name] = 0

    # Summary
    logger.info("\n" + "="*60)
    logger.info("OSM DATA WITH FULL TAGS")
    logger.info("="*60)
    for name, count in results.items():
        logger.info(f"  {name}: {count:,}")


if __name__ == "__main__":
    main()
