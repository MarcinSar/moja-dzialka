"""
I/O utility functions for data pipeline.
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import Optional, List, Union
import warnings


def load_geopackage(
    filepath: Union[str, Path],
    layer: Optional[str] = None,
    columns: Optional[List[str]] = None,
    bbox: Optional[tuple] = None,
    logger=None
) -> gpd.GeoDataFrame:
    """
    Load a GeoPackage file with optional filtering.

    Args:
        filepath: Path to the GeoPackage file
        layer: Layer name (optional if single layer)
        columns: List of columns to load (None for all)
        bbox: Bounding box filter (minx, miny, maxx, maxy)
        logger: Optional logger instance

    Returns:
        GeoDataFrame
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if logger:
        logger.info(f"Loading {filepath.name}...")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        kwargs = {}
        if layer:
            kwargs["layer"] = layer
        if bbox:
            kwargs["bbox"] = bbox

        gdf = gpd.read_file(filepath, **kwargs)

        if columns:
            # Always keep geometry
            cols_to_keep = [c for c in columns if c in gdf.columns]
            if "geometry" not in cols_to_keep:
                cols_to_keep.append("geometry")
            gdf = gdf[cols_to_keep]

    if logger:
        logger.info(f"Loaded {len(gdf):,} records")

    return gdf


def save_geopackage(
    gdf: gpd.GeoDataFrame,
    filepath: Union[str, Path],
    layer: Optional[str] = None,
    driver: str = "GPKG",
    logger=None
) -> None:
    """
    Save GeoDataFrame to GeoPackage.

    Args:
        gdf: GeoDataFrame to save
        filepath: Output file path
        layer: Layer name (defaults to filename)
        driver: OGR driver (default GPKG)
        logger: Optional logger instance
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if layer is None:
        layer = filepath.stem

    if logger:
        logger.info(f"Saving {len(gdf):,} records to {filepath.name}...")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf.to_file(filepath, layer=layer, driver=driver)

    if logger:
        logger.info(f"Saved: {filepath}")


def load_parquet(
    filepath: Union[str, Path],
    columns: Optional[List[str]] = None,
    logger=None
) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
    """
    Load a Parquet file (with optional geometry).

    Args:
        filepath: Path to the Parquet file
        columns: List of columns to load (None for all)
        logger: Optional logger instance

    Returns:
        DataFrame or GeoDataFrame
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if logger:
        logger.info(f"Loading {filepath.name}...")

    # Try loading as GeoParquet first
    try:
        gdf = gpd.read_parquet(filepath, columns=columns)
        if logger:
            logger.info(f"Loaded {len(gdf):,} records (GeoParquet)")
        return gdf
    except Exception:
        pass

    # Fall back to regular Parquet
    df = pd.read_parquet(filepath, columns=columns)
    if logger:
        logger.info(f"Loaded {len(df):,} records (Parquet)")
    return df


def save_parquet(
    df: Union[pd.DataFrame, gpd.GeoDataFrame],
    filepath: Union[str, Path],
    compression: str = "snappy",
    logger=None
) -> None:
    """
    Save DataFrame to Parquet format.

    If GeoDataFrame, saves as GeoParquet.

    Args:
        df: DataFrame or GeoDataFrame to save
        filepath: Output file path
        compression: Compression algorithm
        logger: Optional logger instance
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if logger:
        logger.info(f"Saving {len(df):,} records to {filepath.name}...")

    if isinstance(df, gpd.GeoDataFrame):
        df.to_parquet(filepath, compression=compression)
    else:
        df.to_parquet(filepath, compression=compression)

    if logger:
        logger.info(f"Saved: {filepath}")


def list_layers(filepath: Union[str, Path]) -> List[str]:
    """
    List all layers in a GeoPackage file.

    Args:
        filepath: Path to the GeoPackage file

    Returns:
        List of layer names
    """
    import fiona
    filepath = Path(filepath)

    if not filepath.exists():
        return []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fiona.listlayers(filepath)


def get_layer_info(filepath: Union[str, Path], layer: Optional[str] = None) -> dict:
    """
    Get information about a layer in a GeoPackage.

    Args:
        filepath: Path to the GeoPackage file
        layer: Layer name (optional if single layer)

    Returns:
        Dictionary with layer info (crs, schema, bounds, count)
    """
    import fiona
    filepath = Path(filepath)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fiona.open(filepath, layer=layer) as src:
            return {
                "crs": str(src.crs),
                "schema": dict(src.schema),
                "bounds": src.bounds,
                "count": len(src),
                "driver": src.driver,
            }


def count_records(filepath: Union[str, Path], layer: Optional[str] = None) -> int:
    """
    Count records in a GeoPackage layer without loading.

    Args:
        filepath: Path to the GeoPackage file
        layer: Layer name (optional if single layer)

    Returns:
        Number of records
    """
    import fiona
    filepath = Path(filepath)

    with fiona.open(filepath, layer=layer) as src:
        return len(src)


def get_crs(filepath: Union[str, Path], layer: Optional[str] = None) -> str:
    """
    Get CRS of a GeoPackage layer.

    Args:
        filepath: Path to the GeoPackage file
        layer: Layer name (optional if single layer)

    Returns:
        CRS as string
    """
    import fiona
    filepath = Path(filepath)

    with fiona.open(filepath, layer=layer) as src:
        return str(src.crs)


def load_geopackage_chunked(
    filepath: Union[str, Path],
    chunk_size: int = 100000,
    layer: Optional[str] = None,
    logger=None
):
    """
    Generator to load GeoPackage in chunks.

    Useful for very large files that don't fit in memory.

    Args:
        filepath: Path to the GeoPackage file
        chunk_size: Number of records per chunk
        layer: Layer name (optional if single layer)
        logger: Optional logger instance

    Yields:
        GeoDataFrame chunks
    """
    import fiona
    filepath = Path(filepath)

    if logger:
        logger.info(f"Loading {filepath.name} in chunks of {chunk_size:,}...")

    with fiona.open(filepath, layer=layer) as src:
        crs = src.crs
        total = len(src)
        chunk_num = 0

        features = []
        for i, feature in enumerate(src):
            features.append(feature)

            if len(features) >= chunk_size:
                chunk_num += 1
                if logger:
                    logger.debug(f"Chunk {chunk_num}: records {i - chunk_size + 2} to {i + 1}")
                gdf = gpd.GeoDataFrame.from_features(features, crs=crs)
                features = []
                yield gdf

        # Yield remaining features
        if features:
            chunk_num += 1
            if logger:
                logger.debug(f"Final chunk {chunk_num}: {len(features)} records")
            gdf = gpd.GeoDataFrame.from_features(features, crs=crs)
            yield gdf
