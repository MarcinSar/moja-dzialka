# Data Pipeline Documentation

## Overview

The data pipeline transforms raw geospatial data (parcels + BDOT10k) into searchable vector embeddings using the SRAI (Spatial Reasoning AI) library.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAW DATA                                  │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │   Parcels      │  │    BDOT10k     │  │     MPZP       │    │
│  │   (GeoPackage) │  │   (GeoPackage) │  │  (GeoPackage)  │    │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘    │
└──────────┼───────────────────┼───────────────────┼──────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     STEP 1: LOAD & VALIDATE                      │
│                                                                  │
│  - Load GeoPackages into GeoDataFrames                          │
│  - Validate CRS (must be EPSG:2180)                             │
│  - Filter invalid geometries                                     │
│  - Calculate parcel areas                                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 2: SPATIAL JOINS                         │
│                                                                  │
│  - SRAI IntersectionJoiner: Parcels × BDOT10k                   │
│  - Spatial join: Parcels × MPZP coverage                         │
│  - Buffer analysis for distance features                         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STEP 3: FEATURE ENGINEERING                    │
│                                                                  │
│  - Distance to POIs (schools, shops, forests)                   │
│  - Percentage coverage in buffers                                │
│  - Categorical encoding (road types, zoning)                    │
│  - Normalization                                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 4: SRAI EMBEDDING                        │
│                                                                  │
│  - ContextualCountEmbedder with parcel adjacency                │
│  - ~260 dimensions per parcel                                    │
│  - Normalize to unit vectors                                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 5: EXPORT                                │
│                                                                  │
│  - PostGIS: parcel geometries + attributes                      │
│  - Milvus: embeddings for similarity search                     │
│  - Neo4j: MPZP relationships                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Implementation

### Step 1: Load & Validate Data

```python
# scripts/pipeline/01_load_data.py

import geopandas as gpd
import pandas as pd
from pathlib import Path
from loguru import logger

DATA_DIR = Path("/home/marcin/moja-dzialka")
TARGET_CRS = "EPSG:2180"

def load_parcels() -> gpd.GeoDataFrame:
    """Load and validate parcel geometries."""
    logger.info("Loading parcels...")

    gdf = gpd.read_file(DATA_DIR / "dzialki/dzialki_pomorskie.gpkg")
    logger.info(f"Loaded {len(gdf)} parcels")

    # Ensure correct CRS
    if gdf.crs != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)

    # Filter invalid geometries
    valid_mask = gdf.geometry.is_valid
    invalid_count = (~valid_mask).sum()
    if invalid_count > 0:
        logger.warning(f"Removing {invalid_count} invalid geometries")
        gdf = gdf[valid_mask].copy()

    # Calculate area
    gdf['area_m2'] = gdf.geometry.area

    # Filter by reasonable area (exclude tiny fragments and huge areas)
    gdf = gdf[(gdf['area_m2'] >= 100) & (gdf['area_m2'] <= 100000)]
    logger.info(f"After filtering: {len(gdf)} parcels")

    return gdf


def load_bdot10k_layers() -> dict[str, gpd.GeoDataFrame]:
    """Load all BDOT10k layers."""
    logger.info("Loading BDOT10k layers...")

    bdot10k_dir = DATA_DIR / "bdot10k"
    layers = {}

    for gpkg_file in bdot10k_dir.glob("*.gpkg"):
        layer_name = gpkg_file.stem.split("_")[-1]  # e.g., "BUBD_A"

        try:
            gdf = gpd.read_file(gpkg_file)
            if gdf.crs != TARGET_CRS:
                gdf = gdf.to_crs(TARGET_CRS)

            layers[layer_name] = gdf
            logger.info(f"  {layer_name}: {len(gdf)} features")
        except Exception as e:
            logger.error(f"Failed to load {gpkg_file}: {e}")

    return layers


def load_mpzp_coverage() -> gpd.GeoDataFrame:
    """Load MPZP coverage polygons."""
    logger.info("Loading MPZP coverage...")

    gdf = gpd.read_file(DATA_DIR / "mpzp-pomorskie/mpzp_pomorskie_coverage.gpkg")

    if gdf.crs != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)

    logger.info(f"Loaded {len(gdf)} MPZP polygons")
    return gdf


if __name__ == "__main__":
    parcels = load_parcels()
    bdot10k = load_bdot10k_layers()
    mpzp = load_mpzp_coverage()

    # Save intermediate results
    parcels.to_parquet(DATA_DIR / "processed/parcels_validated.parquet")
    logger.info("Saved validated parcels")
```

### Step 2: Spatial Joins

```python
# scripts/pipeline/02_spatial_joins.py

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from loguru import logger

from srai.joiners import IntersectionJoiner


def create_srai_joint(
    parcels: gpd.GeoDataFrame,
    bdot10k_layers: dict[str, gpd.GeoDataFrame]
) -> gpd.GeoDataFrame:
    """
    Create SRAI joint DataFrame using IntersectionJoiner.

    This maps which BDOT10k features intersect each parcel.
    """
    logger.info("Creating SRAI joint table...")

    # Combine all BDOT10k layers with layer name as category
    all_features = []

    for layer_name, gdf in bdot10k_layers.items():
        gdf = gdf.copy()
        gdf['feature_category'] = layer_name
        all_features.append(gdf[['geometry', 'feature_category']])

    combined = pd.concat(all_features, ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(combined, crs="EPSG:2180")

    logger.info(f"Combined BDOT10k: {len(combined_gdf)} features")

    # Use SRAI IntersectionJoiner
    joiner = IntersectionJoiner()
    joint = joiner.transform(parcels, combined_gdf)

    logger.info(f"Joint table: {len(joint)} rows")
    return joint


def assign_mpzp_coverage(
    parcels: gpd.GeoDataFrame,
    mpzp: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Assign MPZP coverage to parcels via spatial join."""
    logger.info("Assigning MPZP coverage...")

    # Spatial join
    parcels_with_mpzp = gpd.sjoin(
        parcels,
        mpzp[['geometry', 'teryt', 'tytul', 'status']],
        how='left',
        predicate='intersects'
    )

    # Mark parcels that have any MPZP coverage
    parcels['has_mpzp'] = ~parcels_with_mpzp['index_right'].isna()

    mpzp_count = parcels['has_mpzp'].sum()
    logger.info(f"Parcels with MPZP: {mpzp_count} ({mpzp_count/len(parcels)*100:.1f}%)")

    return parcels


if __name__ == "__main__":
    from pathlib import Path

    DATA_DIR = Path("/home/marcin/moja-dzialka")

    parcels = gpd.read_parquet(DATA_DIR / "processed/parcels_validated.parquet")
    bdot10k = {}  # Load from step 1
    mpzp = gpd.read_file(DATA_DIR / "mpzp-pomorskie/mpzp_pomorskie_coverage.gpkg")

    joint = create_srai_joint(parcels, bdot10k)
    parcels = assign_mpzp_coverage(parcels, mpzp)

    joint.to_parquet(DATA_DIR / "processed/srai_joint.parquet")
    parcels.to_parquet(DATA_DIR / "processed/parcels_with_mpzp.parquet")
```

### Step 3: Feature Engineering

```python
# scripts/pipeline/03_feature_engineering.py

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point
from loguru import logger


class FeatureExtractor:
    """Extract distance and coverage features for parcels."""

    BUFFER_RADIUS = 500  # meters

    # BDOT10k layer mappings for POI types
    POI_MAPPINGS = {
        'school': ['BUBD_A'],  # Filter by funkcja_og = 1263
        'kindergarten': ['BUBD_A'],  # funkcja_sz = 1263.Ps
        'shop': ['BUBD_A'],  # funkcja_og = 1230
        'hospital': ['BUBD_A'],  # funkcja_og = 1264
        'bus_stop': ['OIKM_P'],  # komunikacja
        'forest': ['PTLZ_A'],  # las
        'water': ['PTWP_A', 'SWRS_L'],  # woda
    }

    def __init__(self, parcels: gpd.GeoDataFrame, bdot10k: dict):
        self.parcels = parcels
        self.bdot10k = bdot10k
        self.parcel_centroids = parcels.geometry.centroid

    def compute_distance_to_nearest(
        self,
        target_layer: str,
        filter_col: str = None,
        filter_vals: list = None
    ) -> np.ndarray:
        """Compute distance from each parcel to nearest feature."""

        if target_layer not in self.bdot10k:
            logger.warning(f"Layer {target_layer} not found")
            return np.full(len(self.parcels), np.nan)

        gdf = self.bdot10k[target_layer]

        # Apply filter if specified
        if filter_col and filter_vals:
            gdf = gdf[gdf[filter_col].isin(filter_vals)]

        if len(gdf) == 0:
            return np.full(len(self.parcels), np.nan)

        # Get centroids for distance calculation
        if gdf.geometry.type.iloc[0] in ['Polygon', 'MultiPolygon']:
            target_points = np.array([[g.centroid.x, g.centroid.y] for g in gdf.geometry])
        else:
            target_points = np.array([[g.x, g.y] for g in gdf.geometry])

        parcel_points = np.array([[p.x, p.y] for p in self.parcel_centroids])

        # Use KDTree for efficient nearest neighbor search
        tree = cKDTree(target_points)
        distances, _ = tree.query(parcel_points, k=1)

        return distances

    def compute_coverage_in_buffer(
        self,
        target_layer: str,
        buffer_m: float = 500
    ) -> np.ndarray:
        """Compute percentage of buffer area covered by feature type."""

        if target_layer not in self.bdot10k:
            return np.full(len(self.parcels), 0.0)

        gdf = self.bdot10k[target_layer]

        # Create buffers around parcel centroids
        buffers = self.parcel_centroids.buffer(buffer_m)
        buffer_area = np.pi * buffer_m**2

        # Compute intersection area for each parcel
        coverage = []

        # Build spatial index for target features
        target_sindex = gdf.sindex

        for i, buffer_geom in enumerate(buffers):
            # Find candidate features
            candidates_idx = list(target_sindex.intersection(buffer_geom.bounds))

            if not candidates_idx:
                coverage.append(0.0)
                continue

            candidates = gdf.iloc[candidates_idx]

            # Compute intersection area
            intersect_area = sum(
                buffer_geom.intersection(g).area
                for g in candidates.geometry
                if buffer_geom.intersects(g)
            )

            coverage.append(intersect_area / buffer_area)

        return np.array(coverage)

    def extract_all_features(self) -> pd.DataFrame:
        """Extract all features for parcels."""
        logger.info("Extracting features...")

        features = pd.DataFrame(index=self.parcels.index)

        # Distance features
        features['dist_to_school_m'] = self.compute_distance_to_nearest(
            'BUBD_A', 'funkcja_og', ['1263']
        )
        features['dist_to_shop_m'] = self.compute_distance_to_nearest(
            'BUBD_A', 'funkcja_og', ['1230']
        )
        features['dist_to_hospital_m'] = self.compute_distance_to_nearest(
            'BUBD_A', 'funkcja_og', ['1264']
        )
        features['dist_to_forest_m'] = self.compute_distance_to_nearest('PTLZ_A')
        features['dist_to_water_m'] = self.compute_distance_to_nearest('PTWP_A')
        features['dist_to_bus_stop_m'] = self.compute_distance_to_nearest('OIKM_P')
        features['dist_to_main_road_m'] = self.compute_distance_to_nearest('SKDR_L')

        # Coverage features (500m buffer)
        features['pct_forest_500m'] = self.compute_coverage_in_buffer('PTLZ_A', 500)
        features['pct_water_500m'] = self.compute_coverage_in_buffer('PTWP_A', 500)
        features['pct_built_500m'] = self.compute_coverage_in_buffer('PTZB_A', 500)

        # Normalize distance features (cap at 10km)
        dist_cols = [c for c in features.columns if c.startswith('dist_')]
        for col in dist_cols:
            features[col] = features[col].clip(upper=10000)
            features[f'{col}_norm'] = 1 - (features[col] / 10000)

        logger.info(f"Extracted {len(features.columns)} features")
        return features


if __name__ == "__main__":
    from pathlib import Path

    DATA_DIR = Path("/home/marcin/moja-dzialka")

    parcels = gpd.read_parquet(DATA_DIR / "processed/parcels_with_mpzp.parquet")
    bdot10k = {}  # Load all layers

    extractor = FeatureExtractor(parcels, bdot10k)
    features = extractor.extract_all_features()

    features.to_parquet(DATA_DIR / "processed/parcel_features.parquet")
```

### Step 4: SRAI Embedding

```python
# scripts/pipeline/04_generate_embeddings.py

import geopandas as gpd
import pandas as pd
import numpy as np
from loguru import logger

from srai.embedders import CountEmbedder, ContextualCountEmbedder
from srai.neighbourhoods import AdjacencyNeighbourhood


def generate_srai_embeddings(
    parcels: gpd.GeoDataFrame,
    joint: pd.DataFrame,
    use_contextual: bool = True
) -> np.ndarray:
    """
    Generate SRAI embeddings for parcels.

    Args:
        parcels: GeoDataFrame with parcel geometries
        joint: Joint table from IntersectionJoiner
        use_contextual: If True, use ContextualCountEmbedder (includes neighbor context)

    Returns:
        Embedding matrix of shape (n_parcels, n_dims)
    """
    logger.info("Generating SRAI embeddings...")

    if use_contextual:
        # Build adjacency graph
        logger.info("Building adjacency neighbourhood...")
        neighbourhood = AdjacencyNeighbourhood(parcels)

        embedder = ContextualCountEmbedder(
            neighbourhood=neighbourhood,
            concatenate_vectors=True
        )
    else:
        embedder = CountEmbedder()

    # Generate embeddings
    # Note: SRAI expects specific index format
    embeddings = embedder.transform(
        regions_gdf=parcels,
        features_gdf=None,  # Not needed if joint is provided
        joint_gdf=joint
    )

    logger.info(f"Generated embeddings: {embeddings.shape}")
    return embeddings.values


def combine_with_engineered_features(
    srai_embeddings: np.ndarray,
    engineered_features: pd.DataFrame
) -> np.ndarray:
    """Combine SRAI embeddings with engineered features."""

    # Normalize engineered features
    normalized = engineered_features.fillna(0)

    # Select numeric columns only
    numeric_cols = normalized.select_dtypes(include=[np.number]).columns
    normalized = normalized[numeric_cols]

    # Standardize
    normalized = (normalized - normalized.mean()) / (normalized.std() + 1e-8)

    # Combine
    combined = np.hstack([srai_embeddings, normalized.values])

    logger.info(f"Combined embeddings: {combined.shape}")
    return combined


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """Normalize embeddings to unit vectors for cosine similarity."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
    return embeddings / norms


if __name__ == "__main__":
    from pathlib import Path

    DATA_DIR = Path("/home/marcin/moja-dzialka")

    parcels = gpd.read_parquet(DATA_DIR / "processed/parcels_with_mpzp.parquet")
    joint = pd.read_parquet(DATA_DIR / "processed/srai_joint.parquet")
    features = pd.read_parquet(DATA_DIR / "processed/parcel_features.parquet")

    # Generate embeddings
    srai_emb = generate_srai_embeddings(parcels, joint, use_contextual=True)
    combined_emb = combine_with_engineered_features(srai_emb, features)
    normalized_emb = normalize_embeddings(combined_emb)

    # Save
    np.save(DATA_DIR / "processed/embeddings.npy", normalized_emb)

    # Save parcel IDs mapping
    pd.DataFrame({
        'idx': range(len(parcels)),
        'parcel_id': parcels.index
    }).to_parquet(DATA_DIR / "processed/embedding_index.parquet")

    logger.info("Embeddings saved successfully")
```

### Step 5: Export to Databases

```python
# scripts/pipeline/05_export_databases.py

import geopandas as gpd
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
from loguru import logger


def export_to_postgis(
    parcels: gpd.GeoDataFrame,
    features: pd.DataFrame,
    connection_string: str
):
    """Export parcels and features to PostGIS."""
    logger.info("Exporting to PostGIS...")

    engine = create_engine(connection_string)

    # Export parcels
    parcels.to_postgis(
        name='parcels',
        con=engine,
        if_exists='replace',
        index=True,
        index_label='id'
    )

    # Export features
    features.to_sql(
        name='parcel_features',
        con=engine,
        if_exists='replace',
        index=True,
        index_label='parcel_id'
    )

    logger.info("PostGIS export complete")


def export_to_milvus(
    embeddings: np.ndarray,
    parcel_ids: pd.Series,
    parcels: gpd.GeoDataFrame,
    host: str = "localhost",
    port: int = 19530
):
    """Export embeddings to Milvus vector store."""
    logger.info("Exporting to Milvus...")

    connections.connect(host=host, port=port)

    # Define collection schema
    dim = embeddings.shape[1]

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="parcel_id", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="gmina", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="area_m2", dtype=DataType.FLOAT),
        FieldSchema(name="has_mpzp", dtype=DataType.BOOL),
    ]

    schema = CollectionSchema(fields=fields, description="Parcel embeddings")

    # Drop existing collection if exists
    collection_name = "parcel_embeddings"
    if collection_name in [c.name for c in connections.list_collections()]:
        Collection(collection_name).drop()

    collection = Collection(name=collection_name, schema=schema)

    # Prepare data
    data = [
        parcel_ids.tolist(),
        embeddings.tolist(),
        parcels['gmina'].tolist(),
        parcels['area_m2'].tolist(),
        parcels['has_mpzp'].tolist(),
    ]

    # Insert in batches
    batch_size = 10000
    for i in range(0, len(parcel_ids), batch_size):
        batch_data = [d[i:i+batch_size] for d in data]
        collection.insert(batch_data)
        logger.info(f"Inserted batch {i//batch_size + 1}")

    # Create index
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    collection.create_index("embedding", index_params)

    logger.info(f"Milvus export complete: {len(parcel_ids)} vectors")


if __name__ == "__main__":
    from pathlib import Path
    import os

    DATA_DIR = Path("/home/marcin/moja-dzialka")

    parcels = gpd.read_parquet(DATA_DIR / "processed/parcels_with_mpzp.parquet")
    features = pd.read_parquet(DATA_DIR / "processed/parcel_features.parquet")
    embeddings = np.load(DATA_DIR / "processed/embeddings.npy")
    index_df = pd.read_parquet(DATA_DIR / "processed/embedding_index.parquet")

    # Export to PostGIS
    pg_conn = os.getenv("POSTGRES_CONNECTION", "postgresql://user:pass@localhost/moja_dzialka")
    export_to_postgis(parcels, features, pg_conn)

    # Export to Milvus
    export_to_milvus(
        embeddings,
        index_df['parcel_id'],
        parcels,
        host=os.getenv("MILVUS_HOST", "localhost")
    )
```

## Running the Pipeline

### Prerequisites

```bash
pip install geopandas pandas numpy scipy shapely srai pymilvus sqlalchemy psycopg2-binary loguru
```

### Execution Order

```bash
cd /home/marcin/moja-dzialka

# Create processed directory
mkdir -p processed

# Run pipeline steps
python scripts/pipeline/01_load_data.py
python scripts/pipeline/02_spatial_joins.py
python scripts/pipeline/03_feature_engineering.py
python scripts/pipeline/04_generate_embeddings.py
python scripts/pipeline/05_export_databases.py
```

### Pipeline Configuration

Create `scripts/pipeline/config.py`:

```python
from pathlib import Path

# Paths
DATA_DIR = Path("/home/marcin/moja-dzialka")
PROCESSED_DIR = DATA_DIR / "processed"

# CRS
TARGET_CRS = "EPSG:2180"

# Feature extraction parameters
BUFFER_RADIUS_M = 500
MAX_DISTANCE_M = 10000

# BDOT10k layer priorities
PRIORITY_LAYERS = [
    "BUBD_A",   # Buildings
    "SKDR_L",   # Roads
    "PTLZ_A",   # Forest
    "PTWP_A",   # Water
    "OIKM_P",   # Bus stops
    "PTZB_A",   # Built-up areas
]

# Database connections
POSTGRES_CONNECTION = "postgresql://user:pass@localhost/moja_dzialka"
MILVUS_HOST = "localhost"
MILVUS_PORT = 19530
```

## Embedding Dimensions

The final embedding vector contains approximately 260 dimensions:

| Component | Dimensions | Description |
|-----------|------------|-------------|
| SRAI CountEmbedder | ~70 | Counts of BDOT10k feature types on parcel |
| SRAI ContextualCount | ~70 | Counts in neighboring parcels |
| Distance features | ~20 | Normalized distances to POIs |
| Coverage features | ~10 | % coverage in 500m buffer |
| Normalized distances | ~20 | Inverted distance scores |

## Performance Considerations

1. **Memory**: Processing all parcels (~1M) requires ~16GB RAM
2. **Parallelization**: Use Dask for large datasets
3. **Incremental updates**: Track parcel changes and update only affected embeddings
4. **Index optimization**: Use spatial indexes (R-tree) for all geometric operations
