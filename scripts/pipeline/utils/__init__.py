"""
Utility functions for moja-dzialka data pipeline.
"""

from .geometry import (
    make_geometries_valid,
    explode_multipolygons,
    calculate_area,
    calculate_centroid_wgs84,
    calculate_compactness,
    calculate_intersection_ratio,
)

from .spatial import (
    build_spatial_index,
    find_nearest_distance,
    calculate_buffer_coverage,
    spatial_join_attributes,
)

from .io import (
    load_geopackage,
    save_geopackage,
    load_parquet,
    save_parquet,
)

from .logging import setup_logger, log_dataframe_info

__all__ = [
    # Geometry
    "make_geometries_valid",
    "explode_multipolygons",
    "calculate_area",
    "calculate_centroid_wgs84",
    "calculate_compactness",
    "calculate_intersection_ratio",
    # Spatial
    "build_spatial_index",
    "find_nearest_distance",
    "calculate_buffer_coverage",
    "spatial_join_attributes",
    # IO
    "load_geopackage",
    "save_geopackage",
    "load_parquet",
    "save_parquet",
    # Logging
    "setup_logger",
    "log_dataframe_info",
]
