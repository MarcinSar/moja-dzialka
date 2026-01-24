#!/usr/bin/env python3
"""
12_calculate_water_distances.py - Obliczanie odległości do różnych typów wód

Oblicza odległości od każdej działki do:
- dist_to_sea: odległość do morza (woda morska)
- dist_to_river: odległość do najbliższej rzeki
- dist_to_lake: odległość do najbliższego jeziora
- dist_to_canal: odległość do najbliższego kanału

Aktualizuje parcels_enriched.gpkg z nowymi kolumnami.
Zachowuje istniejącą kolumnę dist_to_water jako minimum ze wszystkich typów.
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka/egib")
DATA_PATH = BASE_PATH / "data" / "processed"


def get_water_points(water: gpd.GeoDataFrame, water_type: str) -> np.ndarray:
    """
    Extract representative points from water bodies of given type.

    For polygons: use centroid and boundary points
    For lines: sample points along the line
    """
    water_subset = water[water['water_type'] == water_type]

    if len(water_subset) == 0:
        return None

    points = []

    for _, row in water_subset.iterrows():
        geom = row.geometry

        if geom is None:
            continue

        if geom.geom_type == 'Polygon':
            # Add centroid
            points.append((geom.centroid.x, geom.centroid.y))
            # Sample boundary points for more accuracy
            boundary = geom.exterior
            for dist in range(0, int(boundary.length), 100):
                point = boundary.interpolate(dist)
                points.append((point.x, point.y))

        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                points.append((poly.centroid.x, poly.centroid.y))
                boundary = poly.exterior
                for dist in range(0, int(boundary.length), 100):
                    point = boundary.interpolate(dist)
                    points.append((point.x, point.y))

        elif geom.geom_type == 'LineString':
            for dist in range(0, int(geom.length), 50):
                point = geom.interpolate(dist)
                points.append((point.x, point.y))

        elif geom.geom_type == 'MultiLineString':
            for line in geom.geoms:
                for dist in range(0, int(line.length), 50):
                    point = line.interpolate(dist)
                    points.append((point.x, point.y))

        elif geom.geom_type == 'Point':
            points.append((geom.x, geom.y))

    if not points:
        return None

    return np.array(points)


def calculate_distances_to_type(
    parcel_coords: np.ndarray,
    water_points: np.ndarray,
    max_distance: int = 50000
) -> np.ndarray:
    """
    Calculate distances from parcel centroids to nearest water points.
    Returns distances in meters, capped at max_distance.
    """
    if water_points is None or len(water_points) == 0:
        return np.full(len(parcel_coords), np.nan)

    tree = cKDTree(water_points)
    distances, _ = tree.query(parcel_coords, k=1)

    # Cap at max distance
    distances = np.clip(distances, 0, max_distance)

    return distances


def main():
    logger.info("=" * 60)
    logger.info("OBLICZANIE ODLEGŁOŚCI DO WÓD")
    logger.info("=" * 60)

    # Load classified water
    logger.info("\nŁadowanie sklasyfikowanych wód...")
    water = gpd.read_file(DATA_PATH / "water_classified.gpkg")
    logger.info(f"  Załadowano {len(water):,} obiektów wodnych")
    logger.info(f"  Typy: {water['water_type'].value_counts().to_dict()}")

    # Load parcels
    logger.info("\nŁadowanie działek...")
    parcels = gpd.read_file(DATA_PATH / "parcels_enriched.gpkg")
    logger.info(f"  Załadowano {len(parcels):,} działek")

    # Ensure same CRS
    if water.crs != parcels.crs:
        logger.info(f"  Reprojekcja wód z {water.crs} do {parcels.crs}")
        water = water.to_crs(parcels.crs)

    # Get parcel centroids
    logger.info("\nObliczanie centroidów działek...")
    parcel_coords = np.array([
        (geom.centroid.x, geom.centroid.y)
        for geom in parcels.geometry
    ])

    # Calculate distances for each water type
    water_types = ['morze', 'rzeka', 'jezioro', 'kanal', 'staw']
    distance_columns = {
        'morze': 'dist_to_sea',
        'rzeka': 'dist_to_river',
        'jezioro': 'dist_to_lake',
        'kanal': 'dist_to_canal',
        'staw': 'dist_to_pond',  # New column
    }

    for water_type, col_name in distance_columns.items():
        logger.info(f"\nObliczanie odległości do: {water_type}...")

        # Get water points
        water_points = get_water_points(water, water_type)

        if water_points is None:
            logger.warning(f"  Brak punktów dla typu: {water_type}")
            parcels[col_name] = np.nan
            continue

        logger.info(f"  Punkty reprezentatywne: {len(water_points):,}")

        # Calculate distances
        distances = calculate_distances_to_type(parcel_coords, water_points)

        # Convert to integer meters (using float to handle NaN)
        parcels[col_name] = distances.round().astype(int)

        # Statistics
        valid = parcels[col_name].notna()
        if valid.sum() > 0:
            median = parcels.loc[valid, col_name].median()
            min_val = parcels.loc[valid, col_name].min()
            max_val = parcels.loc[valid, col_name].max()
            within_1km = (parcels[col_name] <= 1000).sum()
            logger.info(f"  Mediana: {median:,.0f}m, Min: {min_val:,.0f}m, Max: {max_val:,.0f}m")
            logger.info(f"  Działki w promieniu 1km: {within_1km:,} ({within_1km/len(parcels)*100:.1f}%)")

    # Update dist_to_water as minimum of all water types
    logger.info("\nAktualizacja dist_to_water jako minimum...")
    water_dist_cols = ['dist_to_sea', 'dist_to_river', 'dist_to_lake', 'dist_to_canal', 'dist_to_pond']
    parcels['dist_to_water'] = parcels[water_dist_cols].min(axis=1)

    # Determine nearest water type
    logger.info("Określanie najbliższego typu wody...")

    def get_nearest_water_type(row):
        min_dist = row['dist_to_water']
        if pd.isna(min_dist):
            return None
        for col, wtype in [
            ('dist_to_sea', 'morze'),
            ('dist_to_river', 'rzeka'),
            ('dist_to_lake', 'jezioro'),
            ('dist_to_canal', 'kanal'),
            ('dist_to_pond', 'staw'),
        ]:
            if row[col] == min_dist:
                return wtype
        return None

    parcels['nearest_water_type'] = parcels.apply(get_nearest_water_type, axis=1)

    # Statistics for nearest water type
    logger.info("\n" + "=" * 60)
    logger.info("STATYSTYKI NAJBLIŻSZEJ WODY")
    logger.info("=" * 60)

    nearest_counts = parcels['nearest_water_type'].value_counts()
    for wtype, count in nearest_counts.items():
        pct = count / len(parcels) * 100
        logger.info(f"  {wtype}: {count:,} działek ({pct:.1f}%)")

    # Premium locations (within 500m of sea/lake)
    logger.info("\n" + "=" * 60)
    logger.info("LOKALIZACJE PREMIUM (blisko wody)")
    logger.info("=" * 60)

    near_sea = (parcels['dist_to_sea'] <= 500).sum()
    near_lake = (parcels['dist_to_lake'] <= 300).sum()
    near_river = (parcels['dist_to_river'] <= 200).sum()

    logger.info(f"  Blisko morza (≤500m): {near_sea:,} działek")
    logger.info(f"  Blisko jeziora (≤300m): {near_lake:,} działek")
    logger.info(f"  Blisko rzeki (≤200m): {near_river:,} działek")

    # Save updated parcels
    output_file = DATA_PATH / "parcels_enriched.gpkg"
    logger.info(f"\nZapisywanie do: {output_file}")
    parcels.to_file(output_file, driver='GPKG')
    logger.info(f"Zapisano {len(parcels):,} działek z {len(parcels.columns)} kolumnami")

    # List new columns
    new_cols = ['dist_to_sea', 'dist_to_river', 'dist_to_lake', 'dist_to_canal', 'dist_to_pond', 'nearest_water_type']
    logger.info(f"\nNowe kolumny: {new_cols}")

    logger.info("\n" + "=" * 60)
    logger.info("ZAKOŃCZONO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
