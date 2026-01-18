#!/usr/bin/env python3
"""
08_import_milvus.py - Import embeddings to Milvus vector database

This script imports parcel embeddings to Milvus for similarity search.

Usage:
    python 08_import_milvus.py --sample    # Import dev sample embeddings
    python 08_import_milvus.py             # Import full dataset embeddings

Prerequisites:
    - Run 07_generate_srai.py first to create embeddings
    - Milvus database running (docker-compose up milvus)

Environment variables (or .env file):
    MILVUS_HOST=localhost
    MILVUS_PORT=19530
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.config import (
    DEV_DATA_DIR,
    PROCESSED_DATA_DIR,
    PARCEL_FEATURES_GPKG,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Milvus connection
MILVUS_CONFIG = {
    "host": os.getenv("MILVUS_HOST", "localhost"),
    "port": os.getenv("MILVUS_PORT", "19530"),
}

# Collection configuration
COLLECTION_NAME = "parcels"
COLLECTION_DESCRIPTION = "Parcel embeddings for similarity search"

# Embedding directories
EMBEDDINGS_DIR_FULL = PROCESSED_DATA_DIR / "embeddings"
EMBEDDINGS_DIR_DEV = DEV_DATA_DIR / "embeddings"

# Batch size for imports
BATCH_SIZE = 1000

# Index parameters
INDEX_PARAMS = {
    "metric_type": "COSINE",  # Cosine similarity for normalized vectors
    "index_type": "IVF_FLAT",  # Good balance of speed and accuracy
    "params": {"nlist": 1024},  # Number of cluster units
}

# Search parameters (for reference)
SEARCH_PARAMS = {
    "metric_type": "COSINE",
    "params": {"nprobe": 16},  # Number of clusters to search
}


# =============================================================================
# MILVUS CLIENT
# =============================================================================

def get_milvus_client():
    """Create Milvus client connection."""
    try:
        from pymilvus import connections, utility

        connections.connect(
            alias="default",
            host=MILVUS_CONFIG["host"],
            port=MILVUS_CONFIG["port"],
        )

        logger.info(f"Connected to Milvus at {MILVUS_CONFIG['host']}:{MILVUS_CONFIG['port']}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Milvus: {e}")
        return False


def disconnect_milvus():
    """Disconnect from Milvus."""
    from pymilvus import connections
    connections.disconnect("default")


def create_collection(embedding_dim: int, drop_existing: bool = False):
    """
    Create Milvus collection for parcel embeddings.

    Args:
        embedding_dim: Dimension of embedding vectors
        drop_existing: Whether to drop existing collection

    Returns:
        Collection object
    """
    from pymilvus import (
        Collection,
        CollectionSchema,
        FieldSchema,
        DataType,
        utility,
    )

    # Check if collection exists
    if utility.has_collection(COLLECTION_NAME):
        if drop_existing:
            logger.info(f"Dropping existing collection: {COLLECTION_NAME}")
            utility.drop_collection(COLLECTION_NAME)
        else:
            logger.info(f"Collection exists: {COLLECTION_NAME}")
            return Collection(COLLECTION_NAME)

    # Define schema
    fields = [
        # Primary key
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            max_length=50,
            description="Parcel ID (ID_DZIALKI)"
        ),

        # Embedding vector
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=embedding_dim,
            description="Parcel embedding vector"
        ),

        # Metadata for filtering (optional but useful)
        FieldSchema(
            name="gmina",
            dtype=DataType.VARCHAR,
            max_length=100,
            description="Municipality name"
        ),
        FieldSchema(
            name="area_m2",
            dtype=DataType.FLOAT,
            description="Parcel area in square meters"
        ),
        FieldSchema(
            name="has_mpzp",
            dtype=DataType.BOOL,
            description="Has zoning plan"
        ),
        FieldSchema(
            name="quietness_score",
            dtype=DataType.FLOAT,
            description="Quietness score (0-100)"
        ),
        FieldSchema(
            name="nature_score",
            dtype=DataType.FLOAT,
            description="Nature score (0-100)"
        ),
        FieldSchema(
            name="accessibility_score",
            dtype=DataType.FLOAT,
            description="Accessibility score (0-100)"
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description=COLLECTION_DESCRIPTION,
        enable_dynamic_field=True,  # Allow additional fields
    )

    # Create collection
    collection = Collection(
        name=COLLECTION_NAME,
        schema=schema,
        using="default",
    )

    logger.info(f"Created collection: {COLLECTION_NAME}")
    logger.info(f"Schema: {[f.name for f in fields]}")

    return collection


def create_index(collection):
    """Create index for vector search."""
    from pymilvus import Collection

    logger.info("Creating index...")

    collection.create_index(
        field_name="embedding",
        index_params=INDEX_PARAMS,
    )

    # Also create indexes on filter fields
    collection.create_index(
        field_name="gmina",
        index_name="gmina_idx",
    )
    collection.create_index(
        field_name="area_m2",
        index_name="area_idx",
    )

    logger.info(f"Index created: {INDEX_PARAMS['index_type']}")


def load_collection(collection):
    """Load collection into memory for searching."""
    logger.info("Loading collection into memory...")
    collection.load()
    logger.info("Collection loaded")


# =============================================================================
# DATA LOADING
# =============================================================================

def load_embeddings(sample: bool = False) -> tuple:
    """
    Load embeddings and metadata.

    Args:
        sample: Whether to load dev sample

    Returns:
        Tuple of (embeddings array, parcel IDs, metadata)
    """
    emb_dir = EMBEDDINGS_DIR_DEV if sample else EMBEDDINGS_DIR_FULL

    # Load embeddings
    emb_path = emb_dir / "parcel_embeddings.npy"
    if not emb_path.exists():
        raise FileNotFoundError(
            f"Embeddings not found: {emb_path}\n"
            f"Run 07_generate_srai.py first"
        )

    embeddings = np.load(emb_path)
    logger.info(f"Loaded embeddings: {embeddings.shape}")

    # Load IDs
    ids_path = emb_dir / "parcel_ids.txt"
    with open(ids_path, "r") as f:
        parcel_ids = [line.strip() for line in f]
    logger.info(f"Loaded {len(parcel_ids):,} parcel IDs")

    # Load metadata
    meta_path = emb_dir / "embedding_metadata.json"
    with open(meta_path, "r") as f:
        metadata = json.load(f)

    return embeddings, parcel_ids, metadata


def load_parcel_metadata(sample: bool = False) -> pd.DataFrame:
    """Load parcel metadata for Milvus fields."""
    import geopandas as gpd

    if sample:
        filepath = DEV_DATA_DIR / "parcels_dev.gpkg"
    else:
        filepath = PARCEL_FEATURES_GPKG

    logger.info(f"Loading parcel metadata from {filepath}")

    # Load only needed columns
    gdf = gpd.read_file(filepath)

    # Select metadata columns
    cols = ["ID_DZIALKI", "gmina", "area_m2", "has_mpzp",
            "quietness_score", "nature_score", "accessibility_score"]
    available_cols = [c for c in cols if c in gdf.columns]

    return gdf[available_cols].set_index("ID_DZIALKI")


# =============================================================================
# IMPORT FUNCTIONS
# =============================================================================

def import_embeddings(
    collection,
    embeddings: np.ndarray,
    parcel_ids: List[str],
    metadata_df: pd.DataFrame,
    batch_size: int = BATCH_SIZE
):
    """
    Import embeddings to Milvus collection.

    Args:
        collection: Milvus collection
        embeddings: Embedding vectors
        parcel_ids: List of parcel IDs
        metadata_df: DataFrame with parcel metadata
        batch_size: Batch size for inserts
    """
    total = len(parcel_ids)
    logger.info(f"Importing {total:,} embeddings in batches of {batch_size}...")

    start_time = time.time()
    inserted = 0

    for i in range(0, total, batch_size):
        batch_end = min(i + batch_size, total)
        batch_ids = parcel_ids[i:batch_end]
        batch_emb = embeddings[i:batch_end]

        # Prepare data for batch
        data = []
        for j, pid in enumerate(batch_ids):
            row = {
                "id": pid,
                "embedding": batch_emb[j].tolist(),
            }

            # Add metadata if available
            if pid in metadata_df.index:
                meta = metadata_df.loc[pid]
                row["gmina"] = str(meta.get("gmina", "")) or ""
                row["area_m2"] = float(meta.get("area_m2", 0)) or 0.0
                row["has_mpzp"] = bool(meta.get("has_mpzp", False))
                row["quietness_score"] = float(meta.get("quietness_score", 0)) or 0.0
                row["nature_score"] = float(meta.get("nature_score", 0)) or 0.0
                row["accessibility_score"] = float(meta.get("accessibility_score", 0)) or 0.0
            else:
                row["gmina"] = ""
                row["area_m2"] = 0.0
                row["has_mpzp"] = False
                row["quietness_score"] = 0.0
                row["nature_score"] = 0.0
                row["accessibility_score"] = 0.0

            data.append(row)

        # Insert batch
        collection.insert(data)
        inserted += len(data)

        if (i + batch_size) % (batch_size * 10) == 0 or batch_end == total:
            elapsed = time.time() - start_time
            rate = inserted / elapsed
            logger.info(
                f"Imported {inserted:,}/{total:,} "
                f"({inserted/total*100:.1f}%) - {rate:.0f} vectors/sec"
            )

    # Flush to ensure data is written
    collection.flush()

    elapsed = time.time() - start_time
    logger.info(f"Import completed: {inserted:,} vectors in {elapsed:.1f}s")


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_collection(collection):
    """Verify collection statistics."""
    logger.info("\n" + "=" * 50)
    logger.info("MILVUS COLLECTION STATISTICS")
    logger.info("=" * 50)

    stats = collection.num_entities
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info(f"Total entities: {stats:,}")

    # Get schema info
    schema = collection.schema
    logger.info(f"Fields: {[f.name for f in schema.fields]}")


def test_search(collection, embeddings: np.ndarray, parcel_ids: List[str], k: int = 5):
    """Test similarity search."""
    logger.info("\nTesting similarity search...")

    # Use first embedding as query
    query_vector = embeddings[0:1].tolist()
    query_id = parcel_ids[0]

    results = collection.search(
        data=query_vector,
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=k,
        output_fields=["gmina", "area_m2", "quietness_score"],
    )

    logger.info(f"Query: {query_id}")
    logger.info(f"Top {k} similar parcels:")
    for hit in results[0]:
        logger.info(
            f"  ID: {hit.id}, Score: {hit.score:.4f}, "
            f"Gmina: {hit.entity.get('gmina', 'N/A')}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import embeddings to Milvus vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 08_import_milvus.py --sample           # Import dev sample
    python 08_import_milvus.py                    # Import full dataset
    python 08_import_milvus.py --sample --clear   # Clear and reimport
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Import dev sample embeddings",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Drop existing collection before import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but don't import",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test search after import",
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
    logger.info("MILVUS IMPORT - moja-dzialka")
    logger.info("=" * 60)

    # Load embeddings
    try:
        embeddings, parcel_ids, emb_metadata = load_embeddings(sample=args.sample)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    embedding_dim = embeddings.shape[1]
    logger.info(f"Embedding dimension: {embedding_dim}")

    if args.dry_run:
        logger.info("Dry run - embeddings loaded successfully")
        logger.info(f"Metadata: {emb_metadata}")
        return

    # Connect to Milvus
    if not get_milvus_client():
        logger.error("Cannot connect to Milvus. Is Docker running?")
        logger.info("Start with: docker-compose up -d milvus")
        sys.exit(1)

    try:
        # Create/get collection
        collection = create_collection(embedding_dim, drop_existing=args.clear)

        # Load parcel metadata
        metadata_df = load_parcel_metadata(sample=args.sample)

        # Import embeddings
        import_embeddings(collection, embeddings, parcel_ids, metadata_df)

        # Create index
        create_index(collection)

        # Load collection for searching
        load_collection(collection)

        # Verify
        verify_collection(collection)

        # Test search
        if args.test:
            test_search(collection, embeddings, parcel_ids)

    finally:
        disconnect_milvus()

    logger.info("\nImport completed successfully!")
    logger.info(f"Collection '{COLLECTION_NAME}' ready for similarity search")


if __name__ == "__main__":
    main()
