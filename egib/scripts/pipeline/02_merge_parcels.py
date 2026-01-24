#!/usr/bin/env python3
"""
02_merge_parcels.py - Merge and enrich parcel data for Trójmiasto

Merges parcel files for Gdańsk, Gdynia, Sopot and adds:
- Centroid coordinates
- Area in m2
- Gmina name
- Grupa rejestrowa (ownership structure)
- Unified CRS (EPSG:2180)

Grupa rejestrowa (ownership groups) - key for understanding who owns the land:
  1-2:  Skarb Państwa (State Treasury) - difficult to buy
  3:    State-owned companies
  4-5:  Gminy (municipalities) - public tenders required
  6:    Municipal companies
  7:    Osoby fizyczne (private individuals) - easiest to purchase!
  8:    Spółdzielnie (cooperatives)
  9:    Kościoły (churches) - rarely for sale
  10:   Wspólnoty gruntowe (land communities)
  11-12: Powiaty (counties)
  13-14: Województwa (voivodeships)
  15-16: Other public entities

Input: /home/marcin/moja-dzialka/dzialki/trojmiasto/{gdansk,gdynia,sopot}.gpkg
Output: /home/marcin/moja-dzialka/egib/data/processed/parcels_trojmiasto.gpkg
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka")
PARCELS_PATH = BASE_PATH / "dzialki" / "trojmiasto"
OUTPUT_PATH = BASE_PATH / "egib" / "data" / "processed"

# Source files
PARCEL_FILES = {
    "Gdańsk": PARCELS_PATH / "dzialki_gdansk.gpkg",
    "Gdynia": PARCELS_PATH / "dzialki_gdynia.gpkg",
    "Sopot": PARCELS_PATH / "dzialki_sopot.gpkg",
}

# Target CRS
TARGET_CRS = "EPSG:2180"

# Grupa rejestrowa mapping (ownership categories)
GRUPA_REJ_NAMES = {
    '1': 'Skarb Państwa',
    '2': 'Skarb Państwa (w zarządzie)',
    '3': 'Spółki Skarbu Państwa',
    '4': 'Gminy (własność)',
    '5': 'Gminy (w zarządzie)',
    '6': 'Spółki komunalne',
    '7': 'Osoby fizyczne',
    '8': 'Spółdzielnie',
    '9': 'Kościoły i związki wyznaniowe',
    '10': 'Wspólnoty gruntowe',
    '11': 'Powiaty (własność)',
    '12': 'Powiaty (w zarządzie)',
    '13': 'Województwa (własność)',
    '14': 'Województwa (w zarządzie)',
    '15': 'Inne podmioty publiczne',
    '16': 'Inne',
}

# Ownership type classification for easier filtering
OWNERSHIP_TYPE = {
    '1': 'publiczna',
    '2': 'publiczna',
    '3': 'publiczna',
    '4': 'publiczna',
    '5': 'publiczna',
    '6': 'publiczna',
    '7': 'prywatna',  # Most interesting for buyers!
    '8': 'spółdzielcza',
    '9': 'kościelna',
    '10': 'wspólnota',
    '11': 'publiczna',
    '12': 'publiczna',
    '13': 'publiczna',
    '14': 'publiczna',
    '15': 'publiczna',
    '16': 'inna',
}


def load_and_tag_parcels(filepath: Path, gmina: str) -> gpd.GeoDataFrame:
    """Load parcels from file and add gmina tag."""
    logger.info(f"Loading parcels for {gmina}: {filepath}")

    gdf = gpd.read_file(filepath)

    # Ensure correct CRS
    if gdf.crs is None:
        logger.warning(f"No CRS for {gmina}, assuming EPSG:2180")
        gdf = gdf.set_crs(TARGET_CRS)
    elif gdf.crs.to_epsg() != 2180:
        logger.info(f"Reprojecting {gmina} from {gdf.crs} to {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)

    # Add gmina column
    gdf['gmina'] = gmina

    # Standardize ID column name
    id_col = None
    for col in ['ID_DZIALKI', 'id_dzialki', 'id', 'ID']:
        if col in gdf.columns:
            id_col = col
            break

    if id_col and id_col != 'id_dzialki':
        gdf = gdf.rename(columns={id_col: 'id_dzialki'})

    # Standardize grupa_rej column name
    grupa_col = None
    for col in ['kieg_grupa_rej', 'grupa_rej', 'GRUPA_REJ']:
        if col in gdf.columns:
            grupa_col = col
            break

    if grupa_col and grupa_col != 'grupa_rej':
        gdf = gdf.rename(columns={grupa_col: 'grupa_rej'})
    elif grupa_col is None:
        logger.warning(f"  No grupa_rej column found in {gmina}")
        gdf['grupa_rej'] = None

    logger.info(f"  Loaded {len(gdf)} parcels for {gmina}")
    return gdf


def normalize_grupa_rej(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize grupa_rej values and add ownership type."""
    logger.info("Normalizing grupa rejestrowa...")

    # Extract just the number from values like "3 - Jednoosobowe spółki..."
    def extract_grupa_number(val):
        if pd.isna(val) or val == '':
            return None
        val_str = str(val).strip()
        # If it starts with a number, extract just the number part
        if val_str and val_str[0].isdigit():
            return val_str.split()[0].split('-')[0].strip()
        return val_str

    gdf['grupa_rej'] = gdf['grupa_rej'].apply(extract_grupa_number)

    # Add human-readable name
    gdf['grupa_rej_nazwa'] = gdf['grupa_rej'].map(GRUPA_REJ_NAMES)

    # Add ownership type classification
    gdf['typ_wlasnosci'] = gdf['grupa_rej'].map(OWNERSHIP_TYPE)

    # Log statistics
    logger.info("  Ownership type distribution:")
    for typ, count in gdf['typ_wlasnosci'].value_counts().items():
        pct = count / len(gdf) * 100
        logger.info(f"    {typ}: {count:,} ({pct:.1f}%)")

    return gdf


def compute_basic_attributes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute basic parcel attributes."""
    logger.info("Computing basic attributes...")

    # Area in m2 (rounded to int - we don't need cm precision)
    gdf['area_m2'] = gdf.geometry.area.round().astype(int)

    # Centroid coordinates
    centroids = gdf.geometry.centroid
    gdf['centroid_x'] = centroids.x
    gdf['centroid_y'] = centroids.y

    # Centroid in WGS84 for map display
    centroids_wgs84 = centroids.to_crs("EPSG:4326")
    gdf['centroid_lat'] = centroids_wgs84.y
    gdf['centroid_lon'] = centroids_wgs84.x

    # Bounding box dimensions (useful for shape analysis)
    bounds = gdf.geometry.bounds
    gdf['bbox_width'] = bounds['maxx'] - bounds['minx']
    gdf['bbox_height'] = bounds['maxy'] - bounds['miny']

    # Shape index (compactness) - closer to 1 = more circular
    # Formula: 4 * pi * area / perimeter^2
    import numpy as np
    perimeter = gdf.geometry.length
    gdf['shape_index'] = (4 * np.pi * gdf['area_m2']) / (perimeter ** 2)
    gdf['shape_index'] = gdf['shape_index'].clip(0, 1)

    logger.info("  Basic attributes computed")
    return gdf


def analyze_parcels(gdf: gpd.GeoDataFrame) -> None:
    """Print analysis of parcel data."""
    logger.info("\n" + "="*60)
    logger.info("PARCEL DATA ANALYSIS")
    logger.info("="*60)

    logger.info(f"\nTotal parcels: {len(gdf)}")

    logger.info(f"\nParcels by gmina:")
    for gmina, count in gdf['gmina'].value_counts().items():
        logger.info(f"  {gmina}: {count:,}")

    logger.info(f"\nArea statistics (m²):")
    stats = gdf['area_m2'].describe()
    logger.info(f"  Min: {stats['min']:,.0f}")
    logger.info(f"  Max: {stats['max']:,.0f}")
    logger.info(f"  Mean: {stats['mean']:,.0f}")
    logger.info(f"  Median: {stats['50%']:,.0f}")

    # Area distribution
    logger.info(f"\nArea distribution:")
    bins = [0, 500, 1000, 1500, 2000, 5000, 10000, float('inf')]
    labels = ['<500', '500-1k', '1k-1.5k', '1.5k-2k', '2k-5k', '5k-10k', '>10k']
    gdf['area_bin'] = pd.cut(gdf['area_m2'], bins=bins, labels=labels)
    for label, count in gdf['area_bin'].value_counts().sort_index().items():
        pct = count / len(gdf) * 100
        logger.info(f"  {label}: {count:,} ({pct:.1f}%)")

    # Drop temp column
    gdf.drop(columns=['area_bin'], inplace=True)

    logger.info(f"\nShape index statistics:")
    logger.info(f"  Mean: {gdf['shape_index'].mean():.3f}")
    logger.info(f"  Very compact (>0.7): {(gdf['shape_index'] > 0.7).sum():,}")
    logger.info(f"  Irregular (<0.3): {(gdf['shape_index'] < 0.3).sum():,}")

    # Ownership analysis
    logger.info(f"\nOwnership type (typ_wlasnosci):")
    for typ, count in gdf['typ_wlasnosci'].value_counts().items():
        pct = count / len(gdf) * 100
        logger.info(f"  {typ}: {count:,} ({pct:.1f}%)")

    logger.info(f"\nTop 10 grupa rejestrowa:")
    for grupa, count in gdf['grupa_rej'].value_counts().head(10).items():
        nazwa = GRUPA_REJ_NAMES.get(grupa, '?')
        pct = count / len(gdf) * 100
        logger.info(f"  {grupa} ({nazwa}): {count:,} ({pct:.1f}%)")

    # Private parcels in typical residential sizes
    private_residential = gdf[
        (gdf['typ_wlasnosci'] == 'prywatna') &
        (gdf['area_m2'] >= 500) &
        (gdf['area_m2'] <= 3000)
    ]
    logger.info(f"\nPrivate parcels 500-3000 m² (potential residential):")
    logger.info(f"  Count: {len(private_residential):,}")
    for gmina_name, count in private_residential['gmina'].value_counts().items():
        logger.info(f"    {gmina_name}: {count:,}")

    logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    logger.info("Starting parcel merge pipeline")

    # Ensure output directory exists
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Load all parcel files
    all_parcels = []
    for gmina, filepath in PARCEL_FILES.items():
        if not filepath.exists():
            logger.error(f"Parcel file not found: {filepath}")
            continue
        gdf = load_and_tag_parcels(filepath, gmina)
        all_parcels.append(gdf)

    if not all_parcels:
        logger.error("No parcels loaded!")
        return

    # Merge all parcels
    logger.info("Merging all parcels...")
    gdf = pd.concat(all_parcels, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=TARGET_CRS)

    # Keep only necessary columns
    keep_cols = ['id_dzialki', 'gmina', 'grupa_rej', 'geometry']
    extra_cols = [c for c in gdf.columns if c not in keep_cols and c != 'fid']
    if extra_cols:
        logger.info(f"  Dropping extra columns: {extra_cols}")
    gdf = gdf[keep_cols]

    # Normalize grupa rejestrowa
    gdf = normalize_grupa_rej(gdf)

    # Compute basic attributes
    gdf = compute_basic_attributes(gdf)

    # Analyze data
    analyze_parcels(gdf)

    # Save to GeoPackage
    output_file = OUTPUT_PATH / "parcels_trojmiasto.gpkg"
    gdf.to_file(output_file, driver='GPKG', layer='parcels')
    logger.info(f"Saved {len(gdf):,} parcels to {output_file}")

    # Save summary CSV
    summary_file = OUTPUT_PATH / "parcels_trojmiasto_summary.csv"
    summary_df = gdf.drop(columns=['geometry'])
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Saved summary to {summary_file}")

    logger.info("Parcel merge complete!")


if __name__ == "__main__":
    main()
