#!/usr/bin/env python3
"""
04_merge_poi.py - Merge BDOT10k and OSM POI data into unified schema

Unified POI schema with deduplication for schools and bus stops.
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_PATH = Path("/home/marcin/moja-dzialka/egib")
BDOT_PATH = BASE_PATH / "data" / "bdot10k_trojmiasto"
OSM_PATH = BASE_PATH / "data" / "osm_trojmiasto"
OUTPUT_PATH = BASE_PATH / "data" / "processed"


def normalize_geometry_to_point(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert all geometries to points (centroid for polygons)."""
    gdf = gdf.copy()
    gdf['geometry'] = gdf.geometry.apply(
        lambda g: g.centroid if g.geom_type in ['Polygon', 'MultiPolygon'] else
                  Point(g.coords[0]) if g.geom_type == 'LineString' else g
    )
    return gdf


def process_education() -> gpd.GeoDataFrame:
    """Merge schools from BDOT10k and OSM with deduplication."""
    logger.info("Processing EDUCATION...")

    # Load BDOT10k
    bdot = gpd.read_file(BDOT_PATH / "szkoly.gpkg")
    bdot = normalize_geometry_to_point(bdot)

    # Map BDOT10k to unified schema
    bdot_mapped = gpd.GeoDataFrame({
        'source': 'bdot10k',
        'source_id': bdot['LOKALNYID'],
        'category': 'education',
        'type': bdot['RODZAJ'].map({
            'szkoła lub zespół szkół': 'school',
            'przedszkole': 'kindergarten'
        }),
        'subtype': None,
        'name': bdot['NAZWA'],
        'brand': None,
        'address_street': None,
        'address_number': None,
        'address_city': None,
        'phone': None,
        'website': None,
        'opening_hours': None,
        'network': None,
        'operator': None,
        'transport_mode': None,
        'geometry': bdot.geometry
    }, crs=bdot.crs)

    # Load OSM
    osm = gpd.read_file(OSM_PATH / "szkoly_full.gpkg")
    osm = normalize_geometry_to_point(osm)

    # Map OSM amenity to type/subtype
    def map_osm_education(row):
        amenity = row.get('amenity', '')
        if amenity == 'school':
            return 'school', None
        elif amenity == 'kindergarten':
            return 'kindergarten', None
        elif amenity == 'language_school':
            return 'school', 'language_school'
        elif amenity == 'driving_school':
            return 'school', 'driving_school'
        elif amenity == 'music_school':
            return 'school', 'music_school'
        elif amenity == 'dancing_school':
            return 'school', 'dancing_school'
        else:
            return 'school', amenity

    osm_types = osm.apply(map_osm_education, axis=1)
    osm['_type'] = [t[0] for t in osm_types]
    osm['_subtype'] = [t[1] for t in osm_types]

    osm_mapped = gpd.GeoDataFrame({
        'source': 'osm',
        'source_id': osm['osm_id'],
        'category': 'education',
        'type': osm['_type'],
        'subtype': osm['_subtype'],
        'name': osm.get('name'),
        'brand': None,
        'address_street': osm.get('addr:street'),
        'address_number': osm.get('addr:housenumber'),
        'address_city': osm.get('addr:city'),
        'phone': osm.get('phone'),
        'website': osm.get('website'),
        'opening_hours': osm.get('opening_hours'),
        'network': None,
        'operator': osm.get('operator'),
        'transport_mode': None,
        'geometry': osm.geometry
    }, crs=osm.crs)

    # Deduplication: remove OSM that are within 100m of BDOT10k (for school/kindergarten)
    # Keep OSM records that are unique types (language_school, driving_school, etc.)

    # BDOT10k schools/kindergartens as reference
    bdot_ref = bdot_mapped[bdot_mapped['type'].isin(['school', 'kindergarten'])].copy()
    bdot_ref_buffered = bdot_ref.copy()
    bdot_ref_buffered['geometry'] = bdot_ref_buffered.geometry.buffer(100)

    # Find OSM duplicates
    osm_schools = osm_mapped[osm_mapped['type'].isin(['school', 'kindergarten']) & osm_mapped['subtype'].isna()].copy()
    osm_other = osm_mapped[~osm_mapped.index.isin(osm_schools.index)].copy()

    # Spatial join to find duplicates
    osm_with_match = gpd.sjoin(osm_schools, bdot_ref_buffered[['geometry']], how='left', predicate='within')
    osm_unique = osm_with_match[osm_with_match['index_right'].isna()].drop(columns=['index_right'])

    # Combine: BDOT10k + unique OSM schools + other OSM (language schools etc.)
    result = pd.concat([bdot_mapped, osm_unique, osm_other], ignore_index=True)
    result = gpd.GeoDataFrame(result, crs=bdot.crs)

    logger.info(f"  BDOT10k: {len(bdot_mapped)}")
    logger.info(f"  OSM total: {len(osm_mapped)}")
    logger.info(f"  OSM unique schools: {len(osm_unique)}")
    logger.info(f"  OSM other types: {len(osm_other)}")
    logger.info(f"  MERGED: {len(result)}")

    return result


def process_transport() -> gpd.GeoDataFrame:
    """Merge bus stops from BDOT10k and OSM with deduplication."""
    logger.info("Processing TRANSPORT...")

    # Load BDOT10k
    bdot = gpd.read_file(BDOT_PATH / "przystanki.gpkg")
    # Already points

    # Map BDOT10k to unified schema
    bdot_mapped = gpd.GeoDataFrame({
        'source': 'bdot10k',
        'source_id': bdot['LOKALNYID'],
        'category': 'transport',
        'type': bdot['RODZAJ'].map({
            'przystanek autobusowy lub tramwajowy': 'bus_stop',
            'stacja lub przystanek kolejowy': 'train_station'
        }),
        'subtype': None,
        'name': bdot['NAZWA'],
        'brand': None,
        'address_street': None,
        'address_number': None,
        'address_city': None,
        'phone': None,
        'website': None,
        'opening_hours': None,
        'network': None,
        'operator': None,
        'transport_mode': None,
        'geometry': bdot.geometry
    }, crs=bdot.crs)

    # Load OSM - only platforms (user-facing location)
    osm = gpd.read_file(OSM_PATH / "przystanki_full.gpkg")
    osm_platforms = osm[osm['public_transport'] == 'platform'].copy()
    osm_stations = osm[osm['public_transport'] == 'station'].copy()

    # Determine transport mode
    def get_transport_mode(row):
        if row.get('train') == 'yes' or row.get('railway') in ['station', 'halt']:
            return 'train'
        elif row.get('tram') == 'yes':
            return 'tram'
        elif row.get('bus') == 'yes':
            return 'bus'
        elif row.get('railway') == 'tram_stop':
            return 'tram'
        else:
            return 'bus'  # default

    def get_transport_type(row):
        mode = get_transport_mode(row)
        if row.get('public_transport') == 'station':
            return 'train_station'
        elif mode == 'tram':
            return 'tram_stop'
        else:
            return 'bus_stop'

    osm_all = pd.concat([osm_platforms, osm_stations], ignore_index=True)
    osm_all['_type'] = osm_all.apply(get_transport_type, axis=1)
    osm_all['_mode'] = osm_all.apply(get_transport_mode, axis=1)

    osm_mapped = gpd.GeoDataFrame({
        'source': 'osm',
        'source_id': osm_all['osm_id'],
        'category': 'transport',
        'type': osm_all['_type'],
        'subtype': None,
        'name': osm_all.get('name'),
        'brand': None,
        'address_street': None,
        'address_number': None,
        'address_city': None,
        'phone': None,
        'website': None,
        'opening_hours': None,
        'network': osm_all.get('network'),
        'operator': osm_all.get('operator'),
        'transport_mode': osm_all['_mode'],
        'geometry': osm_all.geometry
    }, crs=osm_all.crs)

    # Deduplication: BDOT10k as base, add unique OSM
    bdot_ref = bdot_mapped.copy()
    bdot_ref_buffered = bdot_ref.copy()
    bdot_ref_buffered['geometry'] = bdot_ref_buffered.geometry.buffer(50)

    osm_with_match = gpd.sjoin(osm_mapped, bdot_ref_buffered[['geometry']], how='left', predicate='within')
    osm_unique = osm_with_match[osm_with_match['index_right'].isna()].drop(columns=['index_right'])

    # Enrich BDOT10k with OSM attributes where matched
    osm_matched = osm_with_match[osm_with_match['index_right'].notna()].copy()

    # For matched records, prefer OSM name if BDOT10k has no name
    for bdot_idx in osm_matched['index_right'].dropna().unique():
        bdot_idx = int(bdot_idx)
        if bdot_idx not in bdot_mapped.index:
            continue
        osm_rows = osm_matched[osm_matched['index_right'] == bdot_idx]
        if len(osm_rows) == 0:
            continue
        osm_row = osm_rows.iloc[0]
        if pd.isna(bdot_mapped.loc[bdot_idx, 'name']) and pd.notna(osm_row.get('name')):
            bdot_mapped.loc[bdot_idx, 'name'] = osm_row['name']
        if pd.isna(bdot_mapped.loc[bdot_idx, 'network']) and pd.notna(osm_row.get('network')):
            bdot_mapped.loc[bdot_idx, 'network'] = osm_row['network']
        if pd.isna(bdot_mapped.loc[bdot_idx, 'transport_mode']) and pd.notna(osm_row.get('transport_mode')):
            bdot_mapped.loc[bdot_idx, 'transport_mode'] = osm_row['transport_mode']

    # Combine
    result = pd.concat([bdot_mapped, osm_unique], ignore_index=True)
    result = gpd.GeoDataFrame(result, crs=bdot.crs)

    logger.info(f"  BDOT10k: {len(bdot_mapped)}")
    logger.info(f"  OSM platforms+stations: {len(osm_mapped)}")
    logger.info(f"  OSM unique: {len(osm_unique)}")
    logger.info(f"  MERGED: {len(result)}")

    return result


def process_health() -> gpd.GeoDataFrame:
    """Process health POI from OSM only."""
    logger.info("Processing HEALTH...")

    osm = gpd.read_file(OSM_PATH / "zdrowie_full.gpkg")
    osm = normalize_geometry_to_point(osm)

    result = gpd.GeoDataFrame({
        'source': 'osm',
        'source_id': osm['osm_id'],
        'category': 'health',
        'type': osm['amenity'],  # pharmacy, doctors, dentist, clinic, hospital
        'subtype': osm.get('healthcare:speciality'),
        'name': osm.get('name'),
        'brand': osm.get('brand'),
        'address_street': osm.get('addr:street'),
        'address_number': osm.get('addr:housenumber'),
        'address_city': osm.get('addr:city'),
        'phone': osm.get('phone'),
        'website': osm.get('website'),
        'opening_hours': osm.get('opening_hours'),
        'network': None,
        'operator': osm.get('operator'),
        'transport_mode': None,
        'geometry': osm.geometry
    }, crs=osm.crs)

    logger.info(f"  OSM: {len(result)}")
    return result


def process_shop() -> gpd.GeoDataFrame:
    """Process shop POI from OSM only."""
    logger.info("Processing SHOP...")

    osm = gpd.read_file(OSM_PATH / "sklepy_full.gpkg")
    osm = normalize_geometry_to_point(osm)

    result = gpd.GeoDataFrame({
        'source': 'osm',
        'source_id': osm['osm_id'],
        'category': 'shop',
        'type': osm['shop'],  # supermarket, convenience, bakery, etc.
        'subtype': None,
        'name': osm.get('name'),
        'brand': osm.get('brand'),
        'address_street': osm.get('addr:street'),
        'address_number': osm.get('addr:housenumber'),
        'address_city': osm.get('addr:city'),
        'phone': osm.get('phone'),
        'website': osm.get('website'),
        'opening_hours': osm.get('opening_hours'),
        'network': None,
        'operator': osm.get('operator'),
        'transport_mode': None,
        'geometry': osm.geometry
    }, crs=osm.crs)

    logger.info(f"  OSM: {len(result)}")
    return result


def process_gastro() -> gpd.GeoDataFrame:
    """Process gastronomy POI from OSM only."""
    logger.info("Processing GASTRO...")

    osm = gpd.read_file(OSM_PATH / "gastronomia_full.gpkg")
    osm = normalize_geometry_to_point(osm)

    result = gpd.GeoDataFrame({
        'source': 'osm',
        'source_id': osm['osm_id'],
        'category': 'gastro',
        'type': osm['amenity'],  # restaurant, fast_food, cafe, bar, pub
        'subtype': osm.get('cuisine'),
        'name': osm.get('name'),
        'brand': osm.get('brand'),
        'address_street': osm.get('addr:street'),
        'address_number': osm.get('addr:housenumber'),
        'address_city': osm.get('addr:city'),
        'phone': osm.get('phone'),
        'website': osm.get('website'),
        'opening_hours': osm.get('opening_hours'),
        'network': None,
        'operator': osm.get('operator'),
        'transport_mode': None,
        'geometry': osm.geometry
    }, crs=osm.crs)

    logger.info(f"  OSM: {len(result)}")
    return result


def main():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Process each category
    education = process_education()
    transport = process_transport()
    health = process_health()
    shop = process_shop()
    gastro = process_gastro()

    # Combine all
    all_poi = pd.concat([education, transport, health, shop, gastro], ignore_index=True)
    all_poi = gpd.GeoDataFrame(all_poi, crs="EPSG:2180")

    # Add sequential ID
    all_poi.insert(0, 'id', range(1, len(all_poi) + 1))

    # Save combined
    output_file = OUTPUT_PATH / "poi_trojmiasto.gpkg"
    all_poi.to_file(output_file, driver='GPKG')
    logger.info(f"\nSaved combined POI to {output_file.name}")

    # Save by category for easier use
    for cat in ['education', 'transport', 'health', 'shop', 'gastro']:
        cat_gdf = all_poi[all_poi['category'] == cat]
        cat_file = OUTPUT_PATH / f"poi_{cat}.gpkg"
        cat_gdf.to_file(cat_file, driver='GPKG')
        logger.info(f"  {cat}: {len(cat_gdf)} -> {cat_file.name}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("POI MERGE SUMMARY")
    logger.info("="*60)
    summary = all_poi.groupby('category').agg({
        'id': 'count',
        'source': lambda x: (x == 'bdot10k').sum()
    }).rename(columns={'id': 'total', 'source': 'from_bdot10k'})
    summary['from_osm'] = summary['total'] - summary['from_bdot10k']
    print(summary.to_string())
    logger.info(f"\nTOTAL: {len(all_poi):,} POI")


if __name__ == "__main__":
    main()
