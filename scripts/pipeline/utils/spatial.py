"""
Spatial analysis utility functions for data pipeline.
"""

import numpy as np
import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point, box
from shapely.strtree import STRtree
from typing import List, Dict, Optional, Union, Tuple
import warnings


def build_spatial_index(gdf: gpd.GeoDataFrame) -> STRtree:
    """
    Build an STRtree spatial index for a GeoDataFrame.

    Args:
        gdf: GeoDataFrame to index

    Returns:
        STRtree spatial index
    """
    return STRtree(gdf.geometry.values)


def extract_representative_points(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """
    Extract representative points (centroids) as numpy array.

    Args:
        gdf: GeoDataFrame with geometries

    Returns:
        Numpy array of shape (n, 2) with x, y coordinates
    """
    centroids = gdf.geometry.centroid
    return np.column_stack([centroids.x, centroids.y])


def build_kdtree(points: np.ndarray) -> cKDTree:
    """
    Build a KD-tree for efficient nearest neighbor queries.

    Args:
        points: Numpy array of shape (n, 2) with coordinates

    Returns:
        cKDTree instance
    """
    return cKDTree(points)


def find_nearest_distance(
    source_gdf: gpd.GeoDataFrame,
    target_gdf: gpd.GeoDataFrame,
    max_distance: float = 10000.0,
    logger=None,
    prebuilt_tree: cKDTree = None
) -> np.ndarray:
    """
    Find distance from each source geometry to nearest target geometry.

    Uses KD-tree for efficiency with point approximation.

    Args:
        source_gdf: GeoDataFrame with source geometries (parcels)
        target_gdf: GeoDataFrame with target geometries (POIs, roads, etc.)
        max_distance: Maximum distance to consider (caps results)
        logger: Optional logger instance
        prebuilt_tree: Optional prebuilt KD-tree for reuse (major speedup!)

    Returns:
        Numpy array of distances (same length as source_gdf)
    """
    if target_gdf.empty and prebuilt_tree is None:
        return np.full(len(source_gdf), max_distance)

    # Extract centroids
    source_points = extract_representative_points(source_gdf)

    # Use prebuilt tree if available
    if prebuilt_tree is not None:
        tree = prebuilt_tree
    else:
        # For line/polygon targets, use representative points
        if target_gdf.geometry.geom_type.iloc[0] in ["LineString", "MultiLineString"]:
            # Sample points along lines
            target_points = sample_line_points(target_gdf, spacing=100)
        elif target_gdf.geometry.geom_type.iloc[0] in ["Polygon", "MultiPolygon"]:
            # Use boundary points
            target_points = sample_polygon_boundary_points(target_gdf, spacing=100)
        else:
            # Points
            target_points = extract_representative_points(target_gdf)

        if len(target_points) == 0:
            return np.full(len(source_gdf), max_distance)

        # Build KD-tree
        tree = build_kdtree(target_points)

    # Query with parallel workers for speed
    distances, _ = tree.query(source_points, k=1, workers=-1)

    # Cap at max distance
    return np.minimum(distances, max_distance)


def prepare_target_kdtree(target_gdf: gpd.GeoDataFrame, spacing: float = 100, logger=None) -> cKDTree:
    """
    Pre-build a KD-tree from target geometries for reuse across batches.

    This is a MAJOR optimization - build once, query many times!

    Args:
        target_gdf: GeoDataFrame with target geometries
        spacing: Sampling spacing for lines/polygons
        logger: Optional logger

    Returns:
        cKDTree ready for queries
    """
    if target_gdf.empty:
        return None

    geom_type = target_gdf.geometry.geom_type.iloc[0]

    if logger:
        logger.info(f"    Pre-building KD-tree for {len(target_gdf):,} {geom_type} features...")

    if geom_type in ["LineString", "MultiLineString"]:
        target_points = sample_line_points(target_gdf, spacing=spacing)
    elif geom_type in ["Polygon", "MultiPolygon"]:
        target_points = sample_polygon_boundary_points(target_gdf, spacing=spacing)
    else:
        target_points = extract_representative_points(target_gdf)

    if len(target_points) == 0:
        return None

    if logger:
        logger.info(f"    Sampled {len(target_points):,} points, building KD-tree...")

    tree = cKDTree(target_points)

    if logger:
        logger.info(f"    KD-tree ready!")

    return tree


def sample_line_points(gdf: gpd.GeoDataFrame, spacing: float = 100) -> np.ndarray:
    """
    Sample points along line geometries at regular intervals.

    Args:
        gdf: GeoDataFrame with line geometries
        spacing: Distance between sample points in meters

    Returns:
        Numpy array of shape (n, 2) with sampled points
    """
    points = []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        try:
            length = geom.length
            num_points = max(2, int(length / spacing))
            for i in range(num_points):
                point = geom.interpolate(i * spacing)
                points.append([point.x, point.y])
        except Exception:
            continue

    return np.array(points) if points else np.empty((0, 2))


def sample_polygon_boundary_points(gdf: gpd.GeoDataFrame, spacing: float = 100) -> np.ndarray:
    """
    Sample points along polygon boundaries at regular intervals.

    Args:
        gdf: GeoDataFrame with polygon geometries
        spacing: Distance between sample points in meters

    Returns:
        Numpy array of shape (n, 2) with sampled points
    """
    points = []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        try:
            boundary = geom.boundary
            if boundary.geom_type == "MultiLineString":
                for line in boundary.geoms:
                    length = line.length
                    num_points = max(2, int(length / spacing))
                    for i in range(num_points):
                        point = line.interpolate(i * spacing)
                        points.append([point.x, point.y])
            else:
                length = boundary.length
                num_points = max(2, int(length / spacing))
                for i in range(num_points):
                    point = boundary.interpolate(i * spacing)
                    points.append([point.x, point.y])
        except Exception:
            continue

    return np.array(points) if points else np.empty((0, 2))


def calculate_buffer_coverage(
    parcels_gdf: gpd.GeoDataFrame,
    coverage_gdf: gpd.GeoDataFrame,
    buffer_radius: float,
    parcel_centroids: Optional[np.ndarray] = None,
    logger=None
) -> np.ndarray:
    """
    Calculate what percentage of a buffer around each parcel centroid
    is covered by the coverage layer.

    Args:
        parcels_gdf: GeoDataFrame with parcels
        coverage_gdf: GeoDataFrame with coverage polygons
        buffer_radius: Buffer radius in meters
        parcel_centroids: Optional precomputed centroids
        logger: Optional logger instance

    Returns:
        Numpy array of coverage percentages (0.0 to 1.0)
    """
    if coverage_gdf.empty:
        return np.zeros(len(parcels_gdf))

    # Get centroids
    if parcel_centroids is None:
        centroids = parcels_gdf.geometry.centroid
    else:
        centroids = gpd.GeoSeries([Point(p) for p in parcel_centroids], crs=parcels_gdf.crs)

    # Create buffers
    buffers = centroids.buffer(buffer_radius)
    buffer_area = np.pi * buffer_radius ** 2

    # Build spatial index for coverage
    coverage_sindex = coverage_gdf.sindex

    # Calculate coverage for each buffer
    coverages = np.zeros(len(parcels_gdf))

    for i, buffer_geom in enumerate(buffers):
        if buffer_geom is None or buffer_geom.is_empty:
            continue

        # Find potential intersections
        possible_matches_idx = list(coverage_sindex.intersection(buffer_geom.bounds))
        if not possible_matches_idx:
            continue

        # Calculate actual intersection
        possible_matches = coverage_gdf.iloc[possible_matches_idx]
        try:
            intersections = possible_matches.geometry.intersection(buffer_geom)
            total_intersection_area = intersections.area.sum()
            coverages[i] = min(total_intersection_area / buffer_area, 1.0)
        except Exception:
            continue

    return coverages


def count_features_in_buffer(
    parcels_gdf: gpd.GeoDataFrame,
    features_gdf: gpd.GeoDataFrame,
    buffer_radius: float,
    logger=None
) -> np.ndarray:
    """
    Count the number of features within a buffer around each parcel centroid.

    Args:
        parcels_gdf: GeoDataFrame with parcels
        features_gdf: GeoDataFrame with features to count
        buffer_radius: Buffer radius in meters
        logger: Optional logger instance

    Returns:
        Numpy array of feature counts
    """
    if features_gdf.empty:
        return np.zeros(len(parcels_gdf), dtype=int)

    # Get centroids
    centroids = parcels_gdf.geometry.centroid

    # Create buffers
    buffers = centroids.buffer(buffer_radius)

    # Build spatial index
    features_sindex = features_gdf.sindex

    # Count features
    counts = np.zeros(len(parcels_gdf), dtype=int)

    for i, buffer_geom in enumerate(buffers):
        if buffer_geom is None or buffer_geom.is_empty:
            continue

        # Find intersections
        possible_matches_idx = list(features_sindex.intersection(buffer_geom.bounds))
        if not possible_matches_idx:
            continue

        # Verify actual intersection
        possible_matches = features_gdf.iloc[possible_matches_idx]
        actual_intersects = possible_matches.geometry.intersects(buffer_geom)
        counts[i] = actual_intersects.sum()

    return counts


def spatial_join_attributes(
    left_gdf: gpd.GeoDataFrame,
    right_gdf: gpd.GeoDataFrame,
    columns: List[str],
    how: str = "left",
    predicate: str = "intersects",
    logger=None
) -> gpd.GeoDataFrame:
    """
    Spatial join to transfer attributes from right to left GeoDataFrame.

    Args:
        left_gdf: Target GeoDataFrame
        right_gdf: Source GeoDataFrame with attributes
        columns: Columns to transfer from right
        how: Join type ("left", "inner")
        predicate: Spatial predicate
        logger: Optional logger instance

    Returns:
        GeoDataFrame with joined attributes
    """
    if right_gdf.empty:
        for col in columns:
            left_gdf[col] = None
        return left_gdf

    # Ensure same CRS
    if right_gdf.crs != left_gdf.crs:
        right_gdf = right_gdf.to_crs(left_gdf.crs)

    # Perform spatial join
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        joined = gpd.sjoin(
            left_gdf,
            right_gdf[["geometry"] + columns],
            how=how,
            predicate=predicate
        )

    # Handle duplicates by keeping first match
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])

    # Remove duplicates keeping first
    joined = joined[~joined.index.duplicated(keep="first")]

    return joined


def find_containing_polygon(
    points_gdf: gpd.GeoDataFrame,
    polygons_gdf: gpd.GeoDataFrame,
    polygon_id_col: str,
    logger=None
) -> pd.Series:
    """
    Find which polygon contains each point.

    Args:
        points_gdf: GeoDataFrame with point geometries (or centroids)
        polygons_gdf: GeoDataFrame with polygon geometries
        polygon_id_col: Column name in polygons_gdf to return
        logger: Optional logger instance

    Returns:
        Series with polygon IDs (same index as points_gdf)
    """
    if polygons_gdf.empty:
        return pd.Series([None] * len(points_gdf), index=points_gdf.index)

    # Use centroids if not points
    if points_gdf.geometry.geom_type.iloc[0] != "Point":
        points = points_gdf.geometry.centroid
        points_gdf = gpd.GeoDataFrame(
            points_gdf.drop(columns=["geometry"]),
            geometry=points,
            crs=points_gdf.crs
        )

    # Spatial join
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        joined = gpd.sjoin(
            points_gdf[["geometry"]],
            polygons_gdf[[polygon_id_col, "geometry"]],
            how="left",
            predicate="within"
        )

    # Handle duplicates
    result = joined.groupby(joined.index)[polygon_id_col].first()

    # Reindex to match input
    return result.reindex(points_gdf.index)


def create_grid(bounds: Tuple[float, float, float, float], cell_size: float) -> gpd.GeoDataFrame:
    """
    Create a regular grid of square cells covering the bounds.

    Args:
        bounds: (minx, miny, maxx, maxy)
        cell_size: Size of each grid cell in CRS units

    Returns:
        GeoDataFrame with grid cells
    """
    minx, miny, maxx, maxy = bounds

    # Calculate grid dimensions
    cols = int(np.ceil((maxx - minx) / cell_size))
    rows = int(np.ceil((maxy - miny) / cell_size))

    # Generate cells
    cells = []
    for i in range(cols):
        for j in range(rows):
            x1 = minx + i * cell_size
            y1 = miny + j * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            cells.append(box(x1, y1, x2, y2))

    return gpd.GeoDataFrame({"geometry": cells})
