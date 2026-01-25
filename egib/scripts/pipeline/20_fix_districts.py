#!/usr/bin/env python3
"""
20_fix_districts.py - Naprawa przypisania dzielnic przez spatial join

Problem:
- Wiele działek ma dzielnica="Gdańsk (inne)" lub niepoprawne przypisania
- Brakuje kolumny miejscowosc (miasto)

Rozwiązanie:
- Użycie oficjalnych granic dzielnic z OSM
- Spatial join centroidów działek do poligonów dzielnic
- Nearest join dla działek bez dopasowania

Input:
- data/osm_gdansk_dzielnice.gpkg (35 dzielnic)
- data/osm_gdynia_dzielnice.gpkg (21 dzielnic)
- data/sopot-dzielnice.gpkg (7 dzielnic)
- egib/data/processed/parcels_enriched.gpkg (154,959 działek)

Output:
- egib/data/processed/parcels_enriched_v2.gpkg (poprawione działki)
- egib/data/neo4j_export/parcels_full.csv (do importu Neo4j)
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths - adjust for server
BASE_PATH = Path("/root/moja-dzialka")
DATA_PATH = BASE_PATH / "data"
PROCESSED_PATH = BASE_PATH / "egib" / "data" / "processed"
EXPORT_PATH = BASE_PATH / "egib" / "data" / "neo4j_export"


def load_district_boundaries() -> gpd.GeoDataFrame:
    """
    Load and merge district boundaries from OSM files.

    Returns:
        GeoDataFrame with columns: dzielnica, miejscowosc, geometry
    """
    logger.info("Loading district boundaries...")

    # Load individual city district files
    gdansk = gpd.read_file(DATA_PATH / "osm_gdansk_dzielnice.gpkg")
    gdynia = gpd.read_file(DATA_PATH / "osm_gdynia_dzielnice.gpkg")
    sopot = gpd.read_file(DATA_PATH / "sopot-dzielnice.gpkg")

    # Add miejscowosc column (city name)
    gdansk['miejscowosc'] = 'Gdańsk'
    gdynia['miejscowosc'] = 'Gdynia'
    sopot['miejscowosc'] = 'Sopot'

    logger.info(f"  Gdańsk: {len(gdansk)} dzielnic")
    logger.info(f"  Gdynia: {len(gdynia)} dzielnic")
    logger.info(f"  Sopot: {len(sopot)} dzielnic")

    # Merge all districts
    districts = pd.concat([gdansk, gdynia, sopot], ignore_index=True)
    districts = gpd.GeoDataFrame(districts, crs=gdansk.crs)

    # Ensure we have the expected columns
    if 'dzielnica' not in districts.columns:
        raise ValueError("District files must have 'dzielnica' column")

    districts = districts[['dzielnica', 'miejscowosc', 'geometry']].copy()

    logger.info(f"  Total: {len(districts)} dzielnic (CRS: {districts.crs})")

    return districts


def load_parcels() -> gpd.GeoDataFrame:
    """Load parcels from the enriched GeoPackage."""
    logger.info("Loading parcels...")

    parcels_file = PROCESSED_PATH / "parcels_enriched.gpkg"
    parcels = gpd.read_file(parcels_file)

    logger.info(f"  Loaded {len(parcels):,} parcels (CRS: {parcels.crs})")
    logger.info(f"  Columns: {len(parcels.columns)}")

    # Show current district distribution
    if 'dzielnica' in parcels.columns:
        other_count = parcels['dzielnica'].str.contains('(inne)', regex=False, na=False).sum()
        null_count = parcels['dzielnica'].isna().sum()
        logger.info(f"  Current issues: {other_count:,} '(inne)' + {null_count:,} NULL")

    return parcels


def spatial_join_districts(parcels: gpd.GeoDataFrame,
                           districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Perform spatial join using parcel centroids to district polygons.

    Returns:
        Parcels with updated dzielnica and new miejscowosc columns.
    """
    logger.info("Performing spatial join (centroids → district polygons)...")

    # Ensure same CRS
    if parcels.crs != districts.crs:
        logger.info(f"  Reprojecting districts from {districts.crs} to {parcels.crs}")
        districts = districts.to_crs(parcels.crs)

    # Calculate centroids
    logger.info("  Calculating parcel centroids...")
    parcels = parcels.copy()
    parcels['centroid_geom'] = parcels.geometry.centroid

    # Create a GeoDataFrame with centroids for spatial join
    centroids_gdf = gpd.GeoDataFrame(
        parcels[['id_dzialki']],
        geometry=parcels['centroid_geom'],
        crs=parcels.crs
    )

    # Spatial join: centroids within district polygons
    logger.info("  Executing spatial join...")
    joined = gpd.sjoin(
        centroids_gdf,
        districts[['dzielnica', 'miejscowosc', 'geometry']],
        how='left',
        predicate='within'
    )

    # Remove duplicates (if centroid falls exactly on boundary)
    joined = joined.drop_duplicates(subset=['id_dzialki'], keep='first')

    # Create mapping from id_dzialki to dzielnica/miejscowosc
    district_map = joined.set_index('id_dzialki')['dzielnica'].to_dict()
    miejscowosc_map = joined.set_index('id_dzialki')['miejscowosc'].to_dict()

    # Apply mappings
    parcels['dzielnica_new'] = parcels['id_dzialki'].map(district_map)
    parcels['miejscowosc'] = parcels['id_dzialki'].map(miejscowosc_map)

    # Statistics
    matched = parcels['dzielnica_new'].notna().sum()
    unmatched = parcels['dzielnica_new'].isna().sum()

    logger.info(f"  Matched: {matched:,} parcels ({100*matched/len(parcels):.1f}%)")
    logger.info(f"  Unmatched: {unmatched:,} parcels ({100*unmatched/len(parcels):.1f}%)")

    # Clean up temp column
    parcels = parcels.drop(columns=['centroid_geom'])

    return parcels


def fix_unmatched_with_nearest(parcels: gpd.GeoDataFrame,
                                districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    For parcels without a district match, find the nearest district.

    Uses KD-tree for efficient nearest neighbor search on district centroids.
    """
    unmatched_mask = parcels['dzielnica_new'].isna()
    unmatched_count = unmatched_mask.sum()

    if unmatched_count == 0:
        logger.info("No unmatched parcels - skipping nearest neighbor search")
        return parcels

    logger.info(f"Fixing {unmatched_count:,} unmatched parcels with nearest district...")

    # Ensure same CRS
    if parcels.crs != districts.crs:
        districts = districts.to_crs(parcels.crs)

    # Build KD-tree from district centroids
    district_centroids = districts.geometry.centroid
    district_coords = np.array([(p.x, p.y) for p in district_centroids])
    tree = cKDTree(district_coords)

    # Get unmatched parcel centroids
    unmatched_parcels = parcels[unmatched_mask].copy()
    parcel_centroids = unmatched_parcels.geometry.centroid
    parcel_coords = np.array([(p.x, p.y) for p in parcel_centroids])

    # Find nearest district for each unmatched parcel
    distances, indices = tree.query(parcel_coords, k=1)

    # Apply nearest district
    for i, (parcel_idx, dist_idx) in enumerate(zip(unmatched_parcels.index, indices)):
        nearest_district = districts.iloc[dist_idx]
        parcels.loc[parcel_idx, 'dzielnica_new'] = nearest_district['dzielnica']
        parcels.loc[parcel_idx, 'miejscowosc'] = nearest_district['miejscowosc']

    # Log statistics about distances
    avg_dist = distances.mean()
    max_dist = distances.max()
    logger.info(f"  Average distance to nearest district: {avg_dist:.1f}m")
    logger.info(f"  Maximum distance: {max_dist:.1f}m")

    # Flag parcels that were far from any district (might be data errors)
    very_far_mask = distances > 1000  # More than 1km from any district
    if very_far_mask.sum() > 0:
        logger.warning(f"  {very_far_mask.sum()} parcels are >1km from any district boundary!")

    return parcels


def finalize_districts(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Finalize district assignments:
    - Replace old dzielnica with new
    - Handle any remaining issues
    """
    logger.info("Finalizing district assignments...")

    # Store old for comparison
    old_dzielnica = parcels['dzielnica'].copy() if 'dzielnica' in parcels.columns else None

    # Replace dzielnica with new values
    parcels['dzielnica'] = parcels['dzielnica_new']
    parcels = parcels.drop(columns=['dzielnica_new'])

    # Validate: no nulls in dzielnica
    null_count = parcels['dzielnica'].isna().sum()
    if null_count > 0:
        logger.warning(f"  {null_count} parcels still have NULL dzielnica!")

    # Validate: no "(inne)" in dzielnica
    inne_count = parcels['dzielnica'].str.contains('(inne)', regex=False, na=False).sum()
    if inne_count > 0:
        logger.warning(f"  {inne_count} parcels have '(inne)' in dzielnica!")
    else:
        logger.info("  No '(inne)' values - all parcels have named districts")

    # Validate: miejscowosc matches gmina
    if 'gmina' in parcels.columns:
        mismatches = parcels[parcels['gmina'] != parcels['miejscowosc']]
        if len(mismatches) > 0:
            logger.warning(f"  {len(mismatches)} parcels have gmina != miejscowosc mismatch!")
            logger.warning(f"  Sample: {mismatches[['id_dzialki', 'gmina', 'miejscowosc']].head()}")

    return parcels


def analyze_results(parcels: gpd.GeoDataFrame) -> None:
    """Print analysis of district assignment results."""
    logger.info("\n" + "="*60)
    logger.info("WYNIKI NAPRAWY DZIELNIC")
    logger.info("="*60)

    # Per city statistics
    for miasto in ['Gdańsk', 'Gdynia', 'Sopot']:
        if 'miejscowosc' in parcels.columns:
            city_parcels = parcels[parcels['miejscowosc'] == miasto]
        else:
            city_parcels = parcels[parcels['gmina'] == miasto]

        n_districts = city_parcels['dzielnica'].nunique()
        logger.info(f"\n{miasto}: {len(city_parcels):,} działek w {n_districts} dzielnicach")

        # Top 10 districts by count
        top_districts = city_parcels['dzielnica'].value_counts().head(10)
        for dzielnica, count in top_districts.items():
            logger.info(f"  {dzielnica}: {count:,}")

    # Total unique districts
    total_districts = parcels['dzielnica'].nunique()
    expected_districts = 35 + 21 + 7  # Gdańsk + Gdynia + Sopot
    logger.info(f"\nTotal unique districts: {total_districts} (expected up to {expected_districts})")

    # Column summary
    logger.info(f"\nFinal columns: {len(parcels.columns)}")
    if 'miejscowosc' in parcels.columns:
        logger.info(f"miejscowosc distribution: {parcels['miejscowosc'].value_counts().to_dict()}")

    logger.info("="*60)


def prepare_for_neo4j(parcels: gpd.GeoDataFrame) -> pd.DataFrame:
    """Prepare data for Neo4j import - handle types and nulls."""
    logger.info("Preparing data for Neo4j export...")

    # Drop geometry column
    df = pd.DataFrame(parcels.drop(columns=['geometry']))

    # Convert boolean columns to Neo4j friendly format
    bool_cols = df.select_dtypes(include=['bool']).columns
    for col in bool_cols:
        df[col] = df[col].map({True: 'true', False: 'false', None: ''})

    # Convert NaN to empty string for Neo4j
    df = df.fillna('')

    # Ensure id_dzialki is string
    df['id_dzialki'] = df['id_dzialki'].astype(str)

    # Round float columns
    float_cols = df.select_dtypes(include=['float64']).columns
    for col in float_cols:
        df[col] = df[col].apply(lambda x: round(x, 2) if x != '' and pd.notna(x) else x)

    return df


def main():
    logger.info("="*60)
    logger.info("20_fix_districts.py - Naprawa przypisania dzielnic")
    logger.info("="*60)

    # Create export directory if needed
    EXPORT_PATH.mkdir(parents=True, exist_ok=True)

    # 1. Load district boundaries (63 total)
    districts = load_district_boundaries()

    # 2. Load parcels
    parcels = load_parcels()

    # 3. Spatial join - centroids to district polygons
    parcels = spatial_join_districts(parcels, districts)

    # 4. Fix unmatched parcels with nearest district
    parcels = fix_unmatched_with_nearest(parcels, districts)

    # 5. Finalize assignments
    parcels = finalize_districts(parcels)

    # 6. Analyze results
    analyze_results(parcels)

    # 7. Reorder columns - put location hierarchy at the front
    col_order = [
        'id_dzialki',
        # Location hierarchy
        'wojewodztwo', 'powiat', 'gmina', 'miejscowosc', 'dzielnica',
        # Everything else stays in place
    ]
    other_cols = [c for c in parcels.columns if c not in col_order]
    final_cols = [c for c in col_order if c in parcels.columns] + other_cols
    parcels = parcels[final_cols]

    # 8. Save GeoPackage
    output_gpkg = PROCESSED_PATH / "parcels_enriched_v2.gpkg"
    logger.info(f"\nSaving GeoPackage: {output_gpkg}")
    parcels.to_file(output_gpkg, driver='GPKG')
    logger.info(f"  Size: {output_gpkg.stat().st_size / 1024 / 1024:.1f} MB")

    # 9. Export CSV for Neo4j
    df = prepare_for_neo4j(parcels)
    output_csv = EXPORT_PATH / "parcels_full.csv"
    logger.info(f"\nSaving CSV for Neo4j: {output_csv}")
    df.to_csv(output_csv, index=False)
    logger.info(f"  Size: {output_csv.stat().st_size / 1024 / 1024:.1f} MB")
    logger.info(f"  Rows: {len(df):,}")
    logger.info(f"  Columns: {len(df.columns)}")

    logger.info("\n" + "="*60)
    logger.info("ZAKOŃCZONO - Naprawa dzielnic")
    logger.info("="*60)
    logger.info("\nNastępne kroki:")
    logger.info("  1. Zweryfikuj wyniki: parcels_enriched_v2.gpkg")
    logger.info("  2. Jeśli OK, uruchom reimport do Neo4j:")
    logger.info("     python 15_create_neo4j_schema.py")
    logger.info("     python 16_import_neo4j_full.py")
    logger.info("     python 17_create_spatial_relations.py")
    logger.info("     python 19_generate_entity_embeddings.py")


if __name__ == "__main__":
    main()
