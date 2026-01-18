#!/usr/bin/env python3
"""
07_generate_srai.py - Generate SRAI spatial embeddings for parcels

This script generates vector embeddings for parcels using two approaches:
1. Feature-based embeddings (from pre-computed features)
2. SRAI contextual embeddings (from spatial context)

The embeddings are used for similarity search in Milvus.

Usage:
    python 07_generate_srai.py --sample    # Generate for dev sample (10k parcels)
    python 07_generate_srai.py             # Generate for full dataset (1.3M parcels)

Requirements:
    - Pre-computed features (03_feature_engineering.py output)
    - BDOT10k data (for SRAI contextual embeddings)

Output:
    - data/processed/v1.0.0/embeddings/parcel_embeddings.parquet
    - data/processed/v1.0.0/embeddings/parcel_embeddings.npy
    - data/dev/embeddings/parcel_embeddings.parquet (for sample)
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
from loguru import logger
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.config import (
    DEV_DATA_DIR,
    PROCESSED_DATA_DIR,
    PARCEL_FEATURES_GPKG,
    CLEANED_BDOT10K_DIR,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Output directories
EMBEDDINGS_DIR_FULL = PROCESSED_DATA_DIR / "embeddings"
EMBEDDINGS_DIR_DEV = DEV_DATA_DIR / "embeddings"

# Features to use for embedding (numeric only, normalized)
EMBEDDING_FEATURES = [
    # Area
    "area_m2",

    # Land cover ratios
    "forest_ratio",
    "water_ratio",
    "builtup_ratio",

    # Distances (normalized)
    "dist_to_school",
    "dist_to_shop",
    "dist_to_hospital",
    "dist_to_bus_stop",
    "dist_to_public_road",
    "dist_to_main_road",
    "dist_to_forest",
    "dist_to_water",
    "dist_to_industrial",

    # Buffer features
    "pct_forest_500m",
    "pct_water_500m",
    "count_buildings_500m",

    # Composite scores
    "quietness_score",
    "nature_score",
    "accessibility_score",
    "compactness",
]

# Target embedding dimension (after PCA if needed)
TARGET_EMBEDDING_DIM = 64

# Batch size for processing
BATCH_SIZE = 10000


# =============================================================================
# DATA LOADING
# =============================================================================

def load_parcel_data(sample: bool = False) -> gpd.GeoDataFrame:
    """Load parcel data with features."""
    if sample:
        filepath = DEV_DATA_DIR / "parcels_dev.gpkg"
        logger.info(f"Loading DEV sample from {filepath}")
    else:
        filepath = PARCEL_FEATURES_GPKG
        logger.info(f"Loading FULL dataset from {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    gdf = gpd.read_file(filepath)
    logger.info(f"Loaded {len(gdf):,} parcels")

    return gdf


def load_bdot10k_data(sample: bool = False) -> gpd.GeoDataFrame:
    """Load BDOT10k data for contextual embeddings."""
    if sample:
        filepath = DEV_DATA_DIR / "bdot10k_dev.gpkg"
        if not filepath.exists():
            logger.warning(f"BDOT10k dev sample not found: {filepath}")
            return None
        logger.info(f"Loading BDOT10k dev sample from {filepath}")
        return gpd.read_file(filepath)
    else:
        # Load from cleaned directory
        all_data = []
        for gpkg_file in CLEANED_BDOT10K_DIR.glob("*.gpkg"):
            gdf = gpd.read_file(gpkg_file)
            gdf["source_layer"] = gpkg_file.stem
            all_data.append(gdf)

        if not all_data:
            logger.warning("No BDOT10k files found")
            return None

        combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"Loaded {len(combined):,} BDOT10k features from {len(all_data)} files")
        return combined


# =============================================================================
# FEATURE-BASED EMBEDDINGS
# =============================================================================

def create_feature_embeddings(
    df: pd.DataFrame,
    features: List[str],
    target_dim: int = TARGET_EMBEDDING_DIM
) -> Tuple[np.ndarray, dict]:
    """
    Create embeddings from pre-computed features.

    Args:
        df: DataFrame with parcel features
        features: List of feature columns to use
        target_dim: Target embedding dimension

    Returns:
        Tuple of (embeddings array, metadata dict)
    """
    logger.info(f"Creating feature embeddings from {len(features)} features...")

    # Select available features
    available_features = [f for f in features if f in df.columns]
    missing = set(features) - set(available_features)
    if missing:
        logger.warning(f"Missing features: {missing}")

    logger.info(f"Using {len(available_features)} features: {available_features}")

    # Extract feature matrix
    X = df[available_features].copy()

    # Handle missing values
    X = X.fillna(X.median())

    # Handle infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Apply PCA if needed to reduce dimensionality
    if X_scaled.shape[1] > target_dim:
        logger.info(f"Applying PCA: {X_scaled.shape[1]} -> {target_dim} dimensions")
        pca = PCA(n_components=target_dim)
        embeddings = pca.fit_transform(X_scaled)
        explained_var = pca.explained_variance_ratio_.sum()
        logger.info(f"PCA explained variance: {explained_var:.2%}")
    elif X_scaled.shape[1] < target_dim:
        # Pad with zeros if fewer features than target
        padding = np.zeros((X_scaled.shape[0], target_dim - X_scaled.shape[1]))
        embeddings = np.hstack([X_scaled, padding])
        logger.info(f"Padded embeddings: {X_scaled.shape[1]} -> {target_dim} dimensions")
    else:
        embeddings = X_scaled

    # Normalize to unit vectors (for cosine similarity)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    embeddings = embeddings / norms

    metadata = {
        "method": "feature_based",
        "features_used": available_features,
        "dimension": embeddings.shape[1],
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    logger.info(f"Created embeddings: {embeddings.shape}")

    return embeddings.astype(np.float32), metadata


# =============================================================================
# SRAI CONTEXTUAL EMBEDDINGS (optional)
# =============================================================================

def create_srai_embeddings(
    parcels: gpd.GeoDataFrame,
    bdot10k: gpd.GeoDataFrame,
    target_dim: int = TARGET_EMBEDDING_DIM
) -> Tuple[np.ndarray, dict]:
    """
    Create contextual embeddings using SRAI library.

    This captures the spatial context of each parcel by counting
    nearby features from BDOT10k.

    Args:
        parcels: GeoDataFrame with parcel geometries
        bdot10k: GeoDataFrame with BDOT10k features
        target_dim: Target embedding dimension

    Returns:
        Tuple of (embeddings array, metadata dict)
    """
    try:
        from srai.joiners import IntersectionJoiner
        from srai.embedders import CountEmbedder
        from srai.neighbourhoods import H3Neighbourhood
    except ImportError:
        logger.warning("SRAI library not available, skipping contextual embeddings")
        return None, None

    logger.info("Creating SRAI contextual embeddings...")

    # Ensure same CRS
    if parcels.crs != bdot10k.crs:
        bdot10k = bdot10k.to_crs(parcels.crs)

    # Create buffer around parcels for context
    parcels_buffered = parcels.copy()
    parcels_buffered["geometry"] = parcels.geometry.buffer(500)

    # Join BDOT10k features to parcels
    logger.info("Joining BDOT10k features to parcels...")
    joiner = IntersectionJoiner()

    # Prepare BDOT10k with category column
    if "source_layer" in bdot10k.columns:
        bdot10k["category"] = bdot10k["source_layer"]
    elif "klasa" in bdot10k.columns:
        bdot10k["category"] = bdot10k["klasa"].fillna("unknown")
    else:
        bdot10k["category"] = "feature"

    # Join
    joint = joiner.transform(parcels_buffered, bdot10k)

    # Create count embeddings
    embedder = CountEmbedder()
    embeddings = embedder.transform(parcels, bdot10k, joint)

    # Normalize and reduce dimension
    X = embeddings.values.astype(np.float32)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if X_scaled.shape[1] > target_dim:
        pca = PCA(n_components=target_dim)
        X_final = pca.fit_transform(X_scaled)
    else:
        X_final = X_scaled

    # Normalize to unit vectors
    norms = np.linalg.norm(X_final, axis=1, keepdims=True)
    norms[norms == 0] = 1
    X_final = X_final / norms

    metadata = {
        "method": "srai_contextual",
        "features": list(embeddings.columns),
        "dimension": X_final.shape[1],
    }

    logger.info(f"Created SRAI embeddings: {X_final.shape}")

    return X_final.astype(np.float32), metadata


# =============================================================================
# HYBRID EMBEDDINGS
# =============================================================================

def create_hybrid_embeddings(
    feature_emb: np.ndarray,
    srai_emb: np.ndarray = None,
    feature_weight: float = 0.7
) -> np.ndarray:
    """
    Combine feature-based and SRAI embeddings.

    Args:
        feature_emb: Feature-based embeddings
        srai_emb: SRAI contextual embeddings (optional)
        feature_weight: Weight for feature embeddings (0-1)

    Returns:
        Combined embeddings
    """
    if srai_emb is None:
        return feature_emb

    # Ensure same dimension
    min_dim = min(feature_emb.shape[1], srai_emb.shape[1])
    feature_emb = feature_emb[:, :min_dim]
    srai_emb = srai_emb[:, :min_dim]

    # Weighted combination
    combined = feature_weight * feature_emb + (1 - feature_weight) * srai_emb

    # Renormalize
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    norms[norms == 0] = 1
    combined = combined / norms

    logger.info(f"Created hybrid embeddings: {combined.shape}")

    return combined.astype(np.float32)


# =============================================================================
# OUTPUT
# =============================================================================

def save_embeddings(
    embeddings: np.ndarray,
    parcel_ids: List[str],
    metadata: dict,
    output_dir: Path,
    sample: bool = False
):
    """
    Save embeddings to multiple formats.

    Args:
        embeddings: Embedding vectors
        parcel_ids: List of parcel IDs
        metadata: Embedding metadata
        output_dir: Output directory
        sample: Whether this is dev sample
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as parquet (with IDs and metadata)
    parquet_path = output_dir / "parcel_embeddings.parquet"
    df = pd.DataFrame({
        "id_dzialki": parcel_ids,
        "embedding": list(embeddings),
    })
    df["embedding_dim"] = embeddings.shape[1]
    df.to_parquet(parquet_path, index=False)
    logger.info(f"Saved: {parquet_path}")

    # Save as numpy (just vectors)
    npy_path = output_dir / "parcel_embeddings.npy"
    np.save(npy_path, embeddings)
    logger.info(f"Saved: {npy_path}")

    # Save IDs separately (for Milvus import)
    ids_path = output_dir / "parcel_ids.txt"
    with open(ids_path, "w") as f:
        for pid in parcel_ids:
            f.write(f"{pid}\n")
    logger.info(f"Saved: {ids_path}")

    # Save metadata
    import json
    meta_path = output_dir / "embedding_metadata.json"
    metadata["count"] = len(parcel_ids)
    metadata["sample"] = sample
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info(f"Saved: {meta_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate SRAI spatial embeddings for parcels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 07_generate_srai.py --sample           # Dev sample (10k parcels)
    python 07_generate_srai.py                    # Full dataset (1.3M parcels)
    python 07_generate_srai.py --sample --srai    # Include SRAI contextual embeddings
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use dev sample (10k parcels) instead of full dataset",
    )
    parser.add_argument(
        "--srai",
        action="store_true",
        help="Include SRAI contextual embeddings (requires SRAI library)",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=TARGET_EMBEDDING_DIM,
        help=f"Target embedding dimension (default: {TARGET_EMBEDDING_DIM})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but don't generate embeddings",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("SRAI EMBEDDINGS - moja-dzialka")
    logger.info("=" * 60)

    start_time = time.time()

    # Load parcel data
    try:
        parcels = load_parcel_data(sample=args.sample)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run - data loaded successfully")
        logger.info(f"Available features: {[c for c in parcels.columns if c in EMBEDDING_FEATURES]}")
        return

    # Create feature-based embeddings
    feature_emb, feature_meta = create_feature_embeddings(
        parcels,
        EMBEDDING_FEATURES,
        target_dim=args.dim
    )

    # Optionally create SRAI embeddings
    srai_emb = None
    srai_meta = None
    if args.srai:
        bdot10k = load_bdot10k_data(sample=args.sample)
        if bdot10k is not None:
            srai_emb, srai_meta = create_srai_embeddings(
                parcels,
                bdot10k,
                target_dim=args.dim
            )

    # Combine embeddings
    if srai_emb is not None:
        final_emb = create_hybrid_embeddings(feature_emb, srai_emb)
        metadata = {
            "feature_meta": feature_meta,
            "srai_meta": srai_meta,
            "method": "hybrid",
        }
    else:
        final_emb = feature_emb
        metadata = feature_meta

    # Save embeddings
    output_dir = EMBEDDINGS_DIR_DEV if args.sample else EMBEDDINGS_DIR_FULL
    parcel_ids = parcels["ID_DZIALKI"].tolist()

    save_embeddings(final_emb, parcel_ids, metadata, output_dir, sample=args.sample)

    elapsed = time.time() - start_time
    logger.info(f"\nTotal time: {elapsed:.1f}s")
    logger.info(f"Embeddings: {final_emb.shape[0]:,} parcels x {final_emb.shape[1]} dimensions")
    logger.info(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
