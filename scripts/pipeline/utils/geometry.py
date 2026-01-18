"""
Geometry utility functions for data pipeline.
"""

import numpy as np
import geopandas as gpd
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform
import pyproj
from typing import Union, Optional
import warnings


def make_geometries_valid(gdf: gpd.GeoDataFrame, logger=None) -> gpd.GeoDataFrame:
    """
    Make all geometries valid using shapely.make_valid().

    Args:
        gdf: GeoDataFrame with potentially invalid geometries
        logger: Optional logger instance

    Returns:
        GeoDataFrame with valid geometries
    """
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        if logger:
            logger.info(f"Fixing {invalid_count} invalid geometries...")
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.apply(lambda g: make_valid(g) if g is not None else None)
    return gdf


def explode_multipolygons(gdf: gpd.GeoDataFrame, logger=None) -> gpd.GeoDataFrame:
    """
    Explode MultiPolygons into separate Polygon records.

    Each polygon gets a separate row, preserving all other attributes.
    The index is reset after explosion.

    Args:
        gdf: GeoDataFrame with potential MultiPolygons
        logger: Optional logger instance

    Returns:
        GeoDataFrame with only Polygon geometries
    """
    multi_count = gdf.geometry.geom_type.eq("MultiPolygon").sum()
    if multi_count > 0:
        if logger:
            logger.info(f"Exploding {multi_count} MultiPolygons...")

        original_count = len(gdf)
        gdf = gdf.explode(index_parts=False).reset_index(drop=True)
        new_count = len(gdf)

        if logger:
            logger.info(f"Exploded: {original_count} -> {new_count} records "
                       f"(+{new_count - original_count})")
    return gdf


def calculate_area(gdf: gpd.GeoDataFrame, column_name: str = "area_m2") -> gpd.GeoDataFrame:
    """
    Calculate area in square meters for all geometries.

    Assumes CRS is already in meters (e.g., EPSG:2180).

    Args:
        gdf: GeoDataFrame with polygon geometries
        column_name: Name for the area column

    Returns:
        GeoDataFrame with new area column
    """
    gdf = gdf.copy()
    gdf[column_name] = gdf.geometry.area
    return gdf


def calculate_centroid_wgs84(
    gdf: gpd.GeoDataFrame,
    source_crs: str = "EPSG:2180"
) -> gpd.GeoDataFrame:
    """
    Calculate centroids and add lat/lon columns in WGS84.

    Args:
        gdf: GeoDataFrame with polygon geometries
        source_crs: Source CRS (default EPSG:2180)

    Returns:
        GeoDataFrame with 'centroid_lat' and 'centroid_lon' columns
    """
    gdf = gdf.copy()

    # Calculate centroids in source CRS
    centroids = gdf.geometry.centroid

    # Create transformer
    transformer = pyproj.Transformer.from_crs(
        source_crs, "EPSG:4326", always_xy=True
    )

    # Transform coordinates
    coords = np.array([(p.x, p.y) for p in centroids])
    lon, lat = transformer.transform(coords[:, 0], coords[:, 1])

    gdf["centroid_lat"] = lat
    gdf["centroid_lon"] = lon

    return gdf


def calculate_compactness(gdf: gpd.GeoDataFrame, column_name: str = "compactness") -> gpd.GeoDataFrame:
    """
    Calculate compactness ratio (isoperimetric quotient): 4*pi*A / P^2

    Value ranges from 0 to 1, where 1 is a perfect circle.

    Args:
        gdf: GeoDataFrame with polygon geometries
        column_name: Name for the compactness column

    Returns:
        GeoDataFrame with compactness column
    """
    gdf = gdf.copy()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        areas = gdf.geometry.area
        perimeters = gdf.geometry.length

    # Avoid division by zero
    compactness = np.where(
        perimeters > 0,
        (4 * np.pi * areas) / (perimeters ** 2),
        0
    )
    gdf[column_name] = compactness

    return gdf


def calculate_intersection_ratio(
    parcels_gdf: gpd.GeoDataFrame,
    coverage_gdf: gpd.GeoDataFrame,
    ratio_column: str,
    logger=None
) -> gpd.GeoDataFrame:
    """
    Calculate the ratio of each parcel covered by the coverage layer.

    Args:
        parcels_gdf: GeoDataFrame with parcels
        coverage_gdf: GeoDataFrame with coverage polygons (e.g., forests)
        ratio_column: Name for the ratio column (0.0 to 1.0)
        logger: Optional logger instance

    Returns:
        GeoDataFrame with new ratio column
    """
    parcels_gdf = parcels_gdf.copy()

    if coverage_gdf.empty:
        parcels_gdf[ratio_column] = 0.0
        return parcels_gdf

    # Ensure same CRS
    if coverage_gdf.crs != parcels_gdf.crs:
        coverage_gdf = coverage_gdf.to_crs(parcels_gdf.crs)

    # Build spatial index
    if logger:
        logger.debug(f"Building spatial index for {ratio_column}...")

    # Use sjoin to find potential intersections
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        joined = gpd.sjoin(
            parcels_gdf[["geometry"]].reset_index(),
            coverage_gdf[["geometry"]],
            how="left",
            predicate="intersects"
        )

    # Calculate intersection areas for matching pairs
    if logger:
        logger.debug(f"Calculating intersection areas for {ratio_column}...")

    # Group by parcel index and calculate total intersection area
    intersection_areas = {}
    for parcel_idx, group in joined.groupby("index"):
        if group["index_right"].isna().all():
            intersection_areas[parcel_idx] = 0.0
            continue

        # Use .loc with original index, not .iloc with position
        parcel_geom = parcels_gdf.loc[parcel_idx].geometry
        total_intersection = 0.0

        # Get unique coverage indices that intersect
        coverage_indices = group["index_right"].dropna().unique().astype(int)
        for cov_idx in coverage_indices:
            try:
                cov_geom = coverage_gdf.iloc[cov_idx].geometry
                intersection = parcel_geom.intersection(cov_geom)
                total_intersection += intersection.area
            except Exception:
                continue

        intersection_areas[parcel_idx] = total_intersection

    # Calculate ratios using the actual index
    parcel_areas = parcels_gdf.geometry.area
    ratios = []
    for idx in parcels_gdf.index:
        area = parcel_areas.loc[idx]
        if area > 0:
            ratios.append(intersection_areas.get(idx, 0.0) / area)
        else:
            ratios.append(0.0)
    ratios = np.array(ratios)

    # Clip to [0, 1] (can exceed 1 due to overlap)
    parcels_gdf[ratio_column] = np.clip(ratios, 0.0, 1.0)

    return parcels_gdf


def get_geometry_bounds(gdf: gpd.GeoDataFrame) -> tuple:
    """
    Get the bounding box of a GeoDataFrame.

    Returns:
        Tuple of (minx, miny, maxx, maxy)
    """
    return tuple(gdf.total_bounds)


def filter_by_bounds(gdf: gpd.GeoDataFrame, bounds: tuple) -> gpd.GeoDataFrame:
    """
    Filter GeoDataFrame to geometries within bounds.

    Args:
        gdf: Input GeoDataFrame
        bounds: Tuple of (minx, miny, maxx, maxy)

    Returns:
        Filtered GeoDataFrame
    """
    minx, miny, maxx, maxy = bounds
    return gdf.cx[minx:maxx, miny:maxy]
