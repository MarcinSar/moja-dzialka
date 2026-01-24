#!/usr/bin/env python3
"""
04_bdot10k_features.py - Compute BDOT10k-based features for parcels

Computes distances and proximity features from BDOT10k layers:
- dist_to_forest: nearest forest (PTLZ_A)
- dist_to_water: nearest water body (PTWP_A)
- dist_to_school: nearest school (KUOS_A, types: szkoła, przedszkole)
- dist_to_bus_stop: nearest bus/tram stop (OIKM_P)
- dist_to_main_road: nearest main road (SKDR_L, classes: główna+)
- dist_to_industrial: nearest industrial area (KUPG_A)
- count_buildings_500m: buildings within 500m buffer (BUBD_A)
- pct_forest_500m: % forest in 500m buffer
- pct_water_500m: % water in 500m buffer

Input:
  - egib/data/processed/parcels_trojmiasto.gpkg
  - bdot10k/*.gpkg

Output:
  - Updates parcels_trojmiasto.gpkg with new feature columns
"""

import logging
from pathlib import Path
from typing import Optional
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
from shapely import prepare

warnings.filterwarnings('ignore')

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

# BDOT10k layer files
LAYERS = {
    'forest': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_PTLZ_A.gpkg",
    'water': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_PTWP_A.gpkg",
    'school': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_KUOS_A.gpkg",
    'bus_stop': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_OIKM_P.gpkg",
    'road': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_SKDR_L.gpkg",
    'industrial': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_KUPG_A.gpkg",
    'building': BDOT10K_PATH / "PL.PZGiK.336.BDOT10k.22_OT_BUBD_A.gpkg",
}

# Filter criteria
SCHOOL_TYPES = ['szkoła lub zespół szkół', 'przedszkole']
BUS_STOP_TYPES = ['przystanek autobusowy lub tramwajowy', 'stacja lub przystanek kolejowy']
MAIN_ROAD_CLASSES = ['autostrada', 'droga ekspresowa', 'droga główna ruchu przyśpieszonego', 'droga główna']

# Buffer radius for density features
BUFFER_RADIUS = 500  # meters


def load_and_clip_layer(layer_path: Path, bbox: tuple, layer_name: str,
                         filter_col: str = None, filter_values: list = None) -> gpd.GeoDataFrame:
    """Load BDOT10k layer and clip to bounding box."""
    logger.info(f"  Loading {layer_name}...")

    gdf = gpd.read_file(layer_path, bbox=bbox)

    if filter_col and filter_values:
        original_count = len(gdf)
        gdf = gdf[gdf[filter_col].isin(filter_values)]
        logger.info(f"    Filtered {filter_col}: {original_count} → {len(gdf)}")

    logger.info(f"    Loaded {len(gdf)} features")
    return gdf


def extract_points_from_geometries(gdf: gpd.GeoDataFrame, sample_distance: int = 50) -> np.ndarray:
    """
    Extract representative points from geometries for KD-tree.

    For polygons/lines: sample points along boundary/length
    For points: use directly
    """
    points = []

    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == 'Point':
            points.append((geom.x, geom.y))
        elif geom.geom_type == 'MultiPoint':
            for pt in geom.geoms:
                points.append((pt.x, pt.y))
        elif geom.geom_type in ('Polygon', 'MultiPolygon'):
            # Use centroid and boundary points
            points.append((geom.centroid.x, geom.centroid.y))
            # Sample boundary
            if geom.geom_type == 'Polygon':
                boundary = geom.exterior
            else:
                boundary = geom.boundary
            if boundary.length > 0:
                num_points = max(1, int(boundary.length / sample_distance))
                for i in range(num_points):
                    pt = boundary.interpolate(i / num_points, normalized=True)
                    points.append((pt.x, pt.y))
        elif geom.geom_type in ('LineString', 'MultiLineString'):
            # Sample along line
            if geom.length > 0:
                num_points = max(2, int(geom.length / sample_distance))
                for i in range(num_points):
                    pt = geom.interpolate(i / num_points, normalized=True)
                    points.append((pt.x, pt.y))

    return np.array(points) if points else np.array([]).reshape(0, 2)


def compute_nearest_distance(parcel_centroids: np.ndarray, feature_points: np.ndarray,
                              max_distance: int = 10000) -> np.ndarray:
    """Compute distance from each parcel centroid to nearest feature point using KD-tree."""
    if len(feature_points) == 0:
        return np.full(len(parcel_centroids), max_distance)

    tree = cKDTree(feature_points)
    distances, _ = tree.query(parcel_centroids, k=1, distance_upper_bound=max_distance)

    # Replace inf with max_distance
    distances = np.where(np.isinf(distances), max_distance, distances)
    return distances.astype(int)


def compute_buffer_stats(parcels: gpd.GeoDataFrame, features: gpd.GeoDataFrame,
                          buffer_radius: int = 500, stat_type: str = 'pct') -> np.ndarray:
    """
    Compute buffer-based statistics.

    stat_type:
        'pct': percentage of buffer covered by features (for polygons)
        'count': count of features in buffer (for points/small polygons)
    """
    logger.info(f"    Computing {stat_type} in {buffer_radius}m buffer...")

    results = np.zeros(len(parcels))
    buffer_area = np.pi * buffer_radius ** 2

    # Prepare features for faster intersection
    if len(features) > 0:
        features_union = unary_union(features.geometry)
        prepare(features_union)
    else:
        return results

    # Process in chunks for memory efficiency
    chunk_size = 5000
    centroids = parcels.geometry.centroid

    for i in range(0, len(parcels), chunk_size):
        chunk_end = min(i + chunk_size, len(parcels))
        chunk_centroids = centroids.iloc[i:chunk_end]

        for j, centroid in enumerate(chunk_centroids):
            buffer = centroid.buffer(buffer_radius)

            if stat_type == 'pct':
                intersection = buffer.intersection(features_union)
                results[i + j] = (intersection.area / buffer_area) * 100
            elif stat_type == 'count':
                # Count features whose centroid is in buffer
                count = features[features.geometry.centroid.within(buffer)].shape[0]
                results[i + j] = count

        if (i + chunk_size) % 20000 == 0:
            logger.info(f"      Processed {min(i + chunk_size, len(parcels)):,} / {len(parcels):,}")

    return results


def compute_building_count(parcels: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame,
                            buffer_radius: int = 500) -> np.ndarray:
    """Count buildings within buffer using spatial index."""
    logger.info(f"    Counting buildings in {buffer_radius}m buffer...")

    results = np.zeros(len(parcels), dtype=int)

    # Create spatial index for buildings
    buildings_sindex = buildings.sindex
    centroids = parcels.geometry.centroid

    for i, centroid in enumerate(centroids):
        buffer = centroid.buffer(buffer_radius)
        possible_matches_idx = list(buildings_sindex.intersection(buffer.bounds))
        if possible_matches_idx:
            possible_buildings = buildings.iloc[possible_matches_idx]
            results[i] = possible_buildings[possible_buildings.geometry.intersects(buffer)].shape[0]

        if (i + 1) % 20000 == 0:
            logger.info(f"      Processed {i + 1:,} / {len(parcels):,}")

    return results


def main():
    """Main entry point."""
    logger.info("Starting BDOT10k feature engineering")

    # Load parcels
    parcels_file = PROCESSED_PATH / "parcels_trojmiasto.gpkg"
    logger.info(f"Loading parcels from {parcels_file}")
    parcels = gpd.read_file(parcels_file)
    logger.info(f"  Loaded {len(parcels):,} parcels")

    # Get bounding box (with buffer for edge parcels)
    total_bounds = parcels.total_bounds
    bbox_buffer = 2000  # 2km buffer
    bbox = (
        total_bounds[0] - bbox_buffer,
        total_bounds[1] - bbox_buffer,
        total_bounds[2] + bbox_buffer,
        total_bounds[3] + bbox_buffer,
    )
    logger.info(f"  Bounding box (with 2km buffer): {bbox}")

    # Extract parcel centroids as numpy array
    centroids = parcels.geometry.centroid
    parcel_coords = np.array([(c.x, c.y) for c in centroids])

    # === DISTANCE FEATURES ===
    logger.info("\nComputing distance features...")

    # 1. Distance to forest
    forests = load_and_clip_layer(LAYERS['forest'], bbox, 'forest')
    forest_points = extract_points_from_geometries(forests, sample_distance=100)
    parcels['dist_to_forest'] = compute_nearest_distance(parcel_coords, forest_points)
    del forests, forest_points

    # 2. Distance to water
    water = load_and_clip_layer(LAYERS['water'], bbox, 'water')
    water_points = extract_points_from_geometries(water, sample_distance=100)
    parcels['dist_to_water'] = compute_nearest_distance(parcel_coords, water_points)
    del water, water_points

    # 3. Distance to school
    schools = load_and_clip_layer(LAYERS['school'], bbox, 'school',
                                   filter_col='RODZAJ', filter_values=SCHOOL_TYPES)
    school_points = extract_points_from_geometries(schools, sample_distance=50)
    parcels['dist_to_school'] = compute_nearest_distance(parcel_coords, school_points)
    del schools, school_points

    # 4. Distance to bus stop
    bus_stops = load_and_clip_layer(LAYERS['bus_stop'], bbox, 'bus_stop',
                                     filter_col='RODZAJ', filter_values=BUS_STOP_TYPES)
    bus_stop_points = extract_points_from_geometries(bus_stops)
    parcels['dist_to_bus_stop'] = compute_nearest_distance(parcel_coords, bus_stop_points)
    del bus_stops, bus_stop_points

    # 5. Distance to main road
    roads = load_and_clip_layer(LAYERS['road'], bbox, 'road',
                                 filter_col='KLASADROGI', filter_values=MAIN_ROAD_CLASSES)
    road_points = extract_points_from_geometries(roads, sample_distance=100)
    parcels['dist_to_main_road'] = compute_nearest_distance(parcel_coords, road_points)
    del roads, road_points

    # 6. Distance to industrial
    industrial = load_and_clip_layer(LAYERS['industrial'], bbox, 'industrial')
    industrial_points = extract_points_from_geometries(industrial, sample_distance=100)
    parcels['dist_to_industrial'] = compute_nearest_distance(parcel_coords, industrial_points)
    del industrial, industrial_points

    # === BUFFER FEATURES ===
    logger.info("\nComputing buffer features...")

    # 7. Forest percentage in 500m buffer
    forests = load_and_clip_layer(LAYERS['forest'], bbox, 'forest (for buffer)')
    parcels['pct_forest_500m'] = compute_buffer_stats(parcels, forests, BUFFER_RADIUS, 'pct').round(1)
    del forests

    # 8. Water percentage in 500m buffer
    water = load_and_clip_layer(LAYERS['water'], bbox, 'water (for buffer)')
    parcels['pct_water_500m'] = compute_buffer_stats(parcels, water, BUFFER_RADIUS, 'pct').round(1)
    del water

    # 9. Building count in 500m buffer (simplified - use centroid count)
    logger.info("  Loading buildings...")
    buildings = load_and_clip_layer(LAYERS['building'], bbox, 'building')
    # Use simplified counting - count building centroids in buffer
    building_centroids = buildings.geometry.centroid
    building_coords = np.array([(c.x, c.y) for c in building_centroids])
    del buildings

    logger.info("    Counting buildings per parcel (KD-tree)...")
    building_tree = cKDTree(building_coords)
    # Count buildings within 500m of each parcel
    counts = building_tree.query_ball_point(parcel_coords, r=BUFFER_RADIUS)
    parcels['count_buildings_500m'] = [len(c) for c in counts]
    del building_coords, building_tree, counts

    # === ANALYSIS ===
    logger.info("\n" + "="*60)
    logger.info("BDOT10k FEATURE STATISTICS")
    logger.info("="*60)

    for col in ['dist_to_forest', 'dist_to_water', 'dist_to_school',
                'dist_to_bus_stop', 'dist_to_main_road', 'dist_to_industrial',
                'pct_forest_500m', 'pct_water_500m', 'count_buildings_500m']:
        stats = parcels[col].describe()
        logger.info(f"\n{col}:")
        logger.info(f"  min={stats['min']:.0f}, max={stats['max']:.0f}, "
                    f"mean={stats['mean']:.0f}, median={stats['50%']:.0f}")

    logger.info("="*60)

    # === SAVE ===
    output_file = PROCESSED_PATH / "parcels_trojmiasto.gpkg"
    parcels.to_file(output_file, driver='GPKG', layer='parcels')
    logger.info(f"\nSaved {len(parcels):,} parcels to {output_file}")

    # Save summary CSV
    summary_file = PROCESSED_PATH / "parcels_trojmiasto_summary.csv"
    summary_df = parcels.drop(columns=['geometry'])
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Saved summary to {summary_file}")

    logger.info("\nBDOT10k feature engineering complete!")


if __name__ == "__main__":
    main()
