#!/usr/bin/env python3
"""
05_feature_engineering.py - Add POG data and compute distances to POI

Enriches parcel data with:
1. POG parameters (zoning, building limits)
2. Distances to nearest POI (schools, bus stops, etc.)
3. Buffer statistics (% forest, buildings count in 500m)
4. Quality scores (quietness, nature, accessibility)
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_PATH = Path("/home/marcin/moja-dzialka/egib")
DATA_PATH = BASE_PATH / "data" / "processed"
BDOT_PATH = BASE_PATH / "data" / "bdot10k_trojmiasto"


def load_parcels() -> gpd.GeoDataFrame:
    """Load parcel data."""
    logger.info("Loading parcels...")
    parcels = gpd.read_file(DATA_PATH / "parcels_trojmiasto.gpkg")
    logger.info(f"  Loaded {len(parcels):,} parcels")
    return parcels


def load_pog() -> gpd.GeoDataFrame:
    """Load POG data and reproject to EPSG:2180."""
    logger.info("Loading POG...")
    pog = gpd.read_file(DATA_PATH / "pog_trojmiasto.gpkg")
    logger.info(f"  Loaded {len(pog):,} POG zones (CRS: {pog.crs})")

    # Reproject to EPSG:2180 to match parcels
    pog = pog.to_crs("EPSG:2180")
    logger.info(f"  Reprojected to EPSG:2180")
    return pog


def spatial_join_pog(parcels: gpd.GeoDataFrame, pog: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Spatial join parcels with POG zones.
    Uses centroid intersection for assignment.
    If multiple POG zones match, keeps the first one.
    """
    logger.info("Spatial join with POG...")

    # Create centroid geometries for parcels
    parcels_centroids = parcels.copy()
    parcels_centroids['geometry'] = parcels_centroids.geometry.centroid
    parcels_centroids['_orig_idx'] = parcels_centroids.index

    # Spatial join: find POG zone for each parcel centroid
    joined = gpd.sjoin(parcels_centroids, pog, how='left', predicate='within')

    # Handle duplicates: keep first match for each parcel
    joined = joined.drop_duplicates(subset=['_orig_idx'], keep='first')
    joined = joined.set_index('_orig_idx')
    joined = joined.reindex(parcels.index)

    # Select POG columns to keep
    pog_cols = [
        'oznaczenie', 'symbol', 'nazwa', 'profil_podstawowy', 'profil_podstawowy_nazwy',
        'profil_dodatkowy', 'profil_dodatkowy_nazwy', 'maks_intensywnosc',
        'maks_zabudowa_pct', 'maks_wysokosc_m', 'min_bio_pct'
    ]

    # Rename POG columns with prefix
    for col in pog_cols:
        if col in joined.columns:
            parcels[f'pog_{col}'] = joined[col].values

    # Count how many parcels have POG data
    has_pog = parcels['pog_symbol'].notna().sum()
    logger.info(f"  Parcels with POG: {has_pog:,} ({has_pog/len(parcels)*100:.1f}%)")

    return parcels


def compute_distances(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute distances from parcel centroids to nearest POI features.
    Uses KD-tree for efficient nearest neighbor search.
    """
    logger.info("Computing distances to POI...")

    # Load POI data
    poi = gpd.read_file(DATA_PATH / "poi_trojmiasto.gpkg")
    logger.info(f"  Loaded {len(poi):,} POI")

    # Get parcel centroids
    parcel_coords = np.array([(geom.centroid.x, geom.centroid.y) for geom in parcels.geometry])

    # Define POI filters for distance calculation
    poi_filters = {
        'school': (poi['category'] == 'education') & (poi['type'] == 'school'),
        'kindergarten': (poi['category'] == 'education') & (poi['type'] == 'kindergarten'),
        'bus_stop': (poi['category'] == 'transport'),
        'pharmacy': (poi['category'] == 'health') & (poi['type'] == 'pharmacy'),
        'doctors': (poi['category'] == 'health') & (poi['type'] == 'doctors'),
        'supermarket': (poi['category'] == 'shop') & (poi['type'].isin(['supermarket', 'convenience'])),
        'restaurant': (poi['category'] == 'gastro') & (poi['type'] == 'restaurant'),
    }

    # Calculate distances for each category
    for cat_name, cat_filter in poi_filters.items():
        cat_poi = poi[cat_filter]

        if len(cat_poi) == 0:
            parcels[f'dist_to_{cat_name}'] = np.nan
            logger.info(f"  {cat_name}: no POI found")
            continue

        # Get POI coordinates
        poi_coords = np.array([(geom.x, geom.y) for geom in cat_poi.geometry])

        # Build KD-tree
        tree = cKDTree(poi_coords)

        # Query nearest neighbor for each parcel
        distances, _ = tree.query(parcel_coords, k=1)

        # Store as integer meters
        parcels[f'dist_to_{cat_name}'] = distances.round().astype(int)
        logger.info(f"  {cat_name}: median={np.median(distances):.0f}m, max={np.max(distances):.0f}m")

    # Load BDOT10k for additional distances
    logger.info("Computing distances to BDOT10k features...")

    # Distance to forest
    try:
        forests = gpd.read_file(BDOT_PATH / "lasy.gpkg")
        forest_centroids = np.array([(geom.centroid.x, geom.centroid.y) for geom in forests.geometry])
        tree = cKDTree(forest_centroids)
        distances, _ = tree.query(parcel_coords, k=1)
        parcels['dist_to_forest'] = distances.round().astype(int)
        logger.info(f"  forest: median={np.median(distances):.0f}m")
    except Exception as e:
        logger.warning(f"  forest: {e}")
        parcels['dist_to_forest'] = np.nan

    # Distance to water
    try:
        water = gpd.read_file(BDOT_PATH / "wody.gpkg")
        water_centroids = np.array([(geom.centroid.x, geom.centroid.y) for geom in water.geometry])
        tree = cKDTree(water_centroids)
        distances, _ = tree.query(parcel_coords, k=1)
        parcels['dist_to_water'] = distances.round().astype(int)
        logger.info(f"  water: median={np.median(distances):.0f}m")
    except Exception as e:
        logger.warning(f"  water: {e}")
        parcels['dist_to_water'] = np.nan

    # Distance to industrial areas
    try:
        industrial = gpd.read_file(BDOT_PATH / "przemysl.gpkg")
        ind_centroids = np.array([(geom.centroid.x, geom.centroid.y) for geom in industrial.geometry])
        tree = cKDTree(ind_centroids)
        distances, _ = tree.query(parcel_coords, k=1)
        parcels['dist_to_industrial'] = distances.round().astype(int)
        logger.info(f"  industrial: median={np.median(distances):.0f}m")
    except Exception as e:
        logger.warning(f"  industrial: {e}")
        parcels['dist_to_industrial'] = np.nan

    # Distance to main roads
    try:
        roads = gpd.read_file(BDOT_PATH / "drogi_glowne.gpkg")
        # For lines, use interpolated points along the road
        road_points = []
        for geom in roads.geometry:
            if geom.geom_type == 'LineString':
                # Sample points every 100m along road
                length = geom.length
                for dist in range(0, int(length), 100):
                    point = geom.interpolate(dist)
                    road_points.append((point.x, point.y))
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    length = line.length
                    for dist in range(0, int(length), 100):
                        point = line.interpolate(dist)
                        road_points.append((point.x, point.y))

        if road_points:
            road_coords = np.array(road_points)
            tree = cKDTree(road_coords)
            distances, _ = tree.query(parcel_coords, k=1)
            parcels['dist_to_main_road'] = distances.round().astype(int)
            logger.info(f"  main_road: median={np.median(distances):.0f}m")
        else:
            parcels['dist_to_main_road'] = np.nan
    except Exception as e:
        logger.warning(f"  main_road: {e}")
        parcels['dist_to_main_road'] = np.nan

    return parcels


def compute_buffer_stats(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute statistics within 500m buffer of each parcel.
    - % forest coverage
    - % water coverage
    - count of buildings
    """
    logger.info("Computing buffer statistics (500m)...")
    logger.info("  This may take a while...")

    # Load BDOT10k layers
    try:
        forests = gpd.read_file(BDOT_PATH / "lasy.gpkg")
        water = gpd.read_file(BDOT_PATH / "wody.gpkg")
        buildings = gpd.read_file(BDOT_PATH / "budynki.gpkg")
    except Exception as e:
        logger.error(f"  Error loading BDOT10k: {e}")
        parcels['pct_forest_500m'] = np.nan
        parcels['pct_water_500m'] = np.nan
        parcels['count_buildings_500m'] = np.nan
        return parcels

    # Create spatial indexes
    forests_sindex = forests.sindex
    water_sindex = water.sindex
    buildings_sindex = buildings.sindex

    # Buffer area
    buffer_radius = 500
    buffer_area = np.pi * buffer_radius ** 2

    # Process in chunks to avoid memory issues
    chunk_size = 10000
    n_chunks = (len(parcels) + chunk_size - 1) // chunk_size

    pct_forest = np.zeros(len(parcels))
    pct_water = np.zeros(len(parcels))
    count_buildings = np.zeros(len(parcels), dtype=int)

    for chunk_idx in range(n_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min((chunk_idx + 1) * chunk_size, len(parcels))

        if chunk_idx % 5 == 0:
            logger.info(f"  Processing chunk {chunk_idx+1}/{n_chunks} ({start_idx:,}-{end_idx:,})...")

        for i in range(start_idx, end_idx):
            parcel_centroid = parcels.iloc[i].geometry.centroid
            buffer = parcel_centroid.buffer(buffer_radius)

            # Forest intersection
            possible_forests = list(forests_sindex.intersection(buffer.bounds))
            if possible_forests:
                forest_intersection = forests.iloc[possible_forests].intersection(buffer)
                pct_forest[i] = forest_intersection.area.sum() / buffer_area * 100

            # Water intersection
            possible_water = list(water_sindex.intersection(buffer.bounds))
            if possible_water:
                water_intersection = water.iloc[possible_water].intersection(buffer)
                pct_water[i] = water_intersection.area.sum() / buffer_area * 100

            # Buildings count
            possible_buildings = list(buildings_sindex.intersection(buffer.bounds))
            if possible_buildings:
                buildings_in_buffer = buildings.iloc[possible_buildings]
                count_buildings[i] = sum(buildings_in_buffer.intersects(buffer))

    parcels['pct_forest_500m'] = pct_forest.round(1)
    parcels['pct_water_500m'] = pct_water.round(1)
    parcels['count_buildings_500m'] = count_buildings

    logger.info(f"  Forest: median={np.median(pct_forest):.1f}%")
    logger.info(f"  Water: median={np.median(pct_water):.1f}%")
    logger.info(f"  Buildings: median={np.median(count_buildings):.0f}")

    return parcels


def compute_quality_scores(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute composite quality scores (0-100).
    - quietness_score: far from industry, main roads
    - nature_score: close to forest, water
    - accessibility_score: close to transport, amenities
    """
    logger.info("Computing quality scores...")

    # Quietness score (0-100): far from noise sources = better
    # - Distance to industrial: further is better (weight 0.5)
    # - Distance to main road: further is better (weight 0.5)
    dist_industrial = parcels['dist_to_industrial'].fillna(5000).clip(0, 5000)
    dist_main_road = parcels['dist_to_main_road'].fillna(3000).clip(0, 3000)

    quietness = (
        (dist_industrial / 5000) * 50 +  # 0-50 points
        (dist_main_road / 3000) * 50      # 0-50 points
    )
    parcels['quietness_score'] = quietness.round().astype(int)

    # Nature score (0-100): close to nature = better
    # - Distance to forest: closer is better (weight 0.4)
    # - Distance to water: closer is better (weight 0.3)
    # - % forest in 500m: more is better (weight 0.3)
    dist_forest = parcels['dist_to_forest'].fillna(5000).clip(0, 5000)
    dist_water = parcels['dist_to_water'].fillna(5000).clip(0, 5000)
    pct_forest = parcels['pct_forest_500m'].fillna(0).clip(0, 50)

    nature = (
        (1 - dist_forest / 5000) * 40 +  # 0-40 points (closer = more)
        (1 - dist_water / 5000) * 30 +   # 0-30 points
        (pct_forest / 50) * 30            # 0-30 points
    )
    parcels['nature_score'] = nature.round().astype(int)

    # Accessibility score (0-100): close to amenities = better
    # - Distance to bus stop: closer is better (weight 0.3)
    # - Distance to school: closer is better (weight 0.25)
    # - Distance to supermarket: closer is better (weight 0.25)
    # - Distance to pharmacy: closer is better (weight 0.2)
    dist_bus = parcels['dist_to_bus_stop'].fillna(3000).clip(0, 3000)
    dist_school = parcels['dist_to_school'].fillna(3000).clip(0, 3000)
    dist_supermarket = parcels['dist_to_supermarket'].fillna(2000).clip(0, 2000)
    dist_pharmacy = parcels['dist_to_pharmacy'].fillna(3000).clip(0, 3000)

    accessibility = (
        (1 - dist_bus / 3000) * 30 +          # 0-30 points
        (1 - dist_school / 3000) * 25 +       # 0-25 points
        (1 - dist_supermarket / 2000) * 25 +  # 0-25 points
        (1 - dist_pharmacy / 3000) * 20       # 0-20 points
    )
    parcels['accessibility_score'] = accessibility.round().astype(int)

    logger.info(f"  Quietness: median={parcels['quietness_score'].median()}")
    logger.info(f"  Nature: median={parcels['nature_score'].median()}")
    logger.info(f"  Accessibility: median={parcels['accessibility_score'].median()}")

    return parcels


def add_buildability_flags(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add flags for buildability based on POG data.
    """
    logger.info("Adding buildability flags...")

    # Residential buildable: has POG symbol for residential (SW, SJ, SN, SU)
    residential_symbols = ['SW', 'SJ', 'SN', 'SU', 'SM']
    parcels['is_residential_zone'] = parcels['pog_symbol'].isin(residential_symbols)

    # Has any POG coverage
    parcels['has_pog'] = parcels['pog_symbol'].notna()

    # Size category
    def size_category(area):
        if area < 500:
            return 'mala'
        elif area < 1500:
            return 'pod_dom'
        elif area < 5000:
            return 'duza'
        else:
            return 'bardzo_duza'

    parcels['size_category'] = parcels['area_m2'].apply(size_category)

    logger.info(f"  Residential zones: {parcels['is_residential_zone'].sum():,}")
    logger.info(f"  Has POG: {parcels['has_pog'].sum():,}")
    logger.info(f"  Size categories: {parcels['size_category'].value_counts().to_dict()}")

    return parcels


def add_binned_categories(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add binned categorical columns for Neo4j graph filtering.
    These categories enable natural language queries like "bardzo cicha" or "zielona".
    """
    logger.info("Adding binned categories...")

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
    parcels['kategoria_ciszy'] = parcels['quietness_score'].apply(categorize_quietness)
    parcels['kategoria_natury'] = parcels['nature_score'].apply(categorize_nature)
    parcels['kategoria_dostepu'] = parcels['accessibility_score'].apply(categorize_accessibility)
    parcels['gestosc_zabudowy'] = parcels['count_buildings_500m'].apply(categorize_density)

    # Log distribution
    logger.info(f"  Kategorie ciszy: {parcels['kategoria_ciszy'].value_counts().to_dict()}")
    logger.info(f"  Kategorie natury: {parcels['kategoria_natury'].value_counts().to_dict()}")
    logger.info(f"  Kategorie dostępu: {parcels['kategoria_dostepu'].value_counts().to_dict()}")
    logger.info(f"  Gęstość zabudowy: {parcels['gestosc_zabudowy'].value_counts().to_dict()}")

    return parcels


def main():
    # Load data
    parcels = load_parcels()
    pog = load_pog()

    # Feature engineering steps
    parcels = spatial_join_pog(parcels, pog)
    parcels = compute_distances(parcels)
    parcels = compute_buffer_stats(parcels)
    parcels = compute_quality_scores(parcels)
    parcels = add_buildability_flags(parcels)
    parcels = add_binned_categories(parcels)

    # Save enriched parcels
    output_file = DATA_PATH / "parcels_enriched.gpkg"
    parcels.to_file(output_file, driver='GPKG')
    logger.info(f"\nSaved enriched parcels to {output_file.name}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("FEATURE ENGINEERING SUMMARY")
    logger.info("="*60)
    logger.info(f"Total parcels: {len(parcels):,}")
    logger.info(f"Columns: {len(parcels.columns)}")
    logger.info(f"\nNew columns added:")
    new_cols = [c for c in parcels.columns if c.startswith(('pog_', 'dist_', 'pct_', 'count_', 'quietness', 'nature', 'accessibility', 'is_', 'has_', 'size_', 'kategoria_', 'gestosc_'))]
    for col in sorted(new_cols):
        logger.info(f"  {col}")


if __name__ == "__main__":
    main()
