#!/usr/bin/env python3
"""
13_export_full_csv.py - Eksport pełnych danych działek do CSV dla Neo4j

Eksportuje wszystkie kolumny z parcels_enriched.gpkg do formatu CSV
gotowego do importu do Neo4j. Dodaje brakujące kolumny kategorialne
jeśli nie istnieją.

Output: data/ready-for-import/neo4j/parcels_full.csv
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka")
DATA_PATH = BASE_PATH / "egib" / "data" / "processed"
OUTPUT_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j"


def add_binned_categories(parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add binned categorical columns for Neo4j graph filtering."""
    logger.info("Dodawanie kategorii...")

    def categorize_quietness(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 80:
            return "bardzo_cicha"
        if score >= 60:
            return "cicha"
        if score >= 40:
            return "umiarkowana"
        return "glosna"

    def categorize_nature(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 70:
            return "bardzo_zielona"
        if score >= 50:
            return "zielona"
        if score >= 30:
            return "umiarkowana"
        return "zurbanizowana"

    def categorize_accessibility(score):
        if pd.isna(score):
            return "nieznana"
        if score >= 70:
            return "doskonala"
        if score >= 50:
            return "dobra"
        if score >= 30:
            return "umiarkowana"
        return "ograniczona"

    def categorize_density(count):
        if pd.isna(count):
            return "nieznana"
        if count >= 50:
            return "gesta"
        if count >= 20:
            return "umiarkowana"
        if count >= 5:
            return "rzadka"
        return "bardzo_rzadka"

    # Apply categorizations
    if 'kategoria_ciszy' not in parcels.columns:
        parcels['kategoria_ciszy'] = parcels['quietness_score'].apply(categorize_quietness)

    if 'kategoria_natury' not in parcels.columns:
        parcels['kategoria_natury'] = parcels['nature_score'].apply(categorize_nature)

    if 'kategoria_dostepu' not in parcels.columns:
        parcels['kategoria_dostepu'] = parcels['accessibility_score'].apply(categorize_accessibility)

    if 'gestosc_zabudowy' not in parcels.columns:
        parcels['gestosc_zabudowy'] = parcels['count_buildings_500m'].apply(categorize_density)

    # Log distribution
    logger.info(f"  Kategorie ciszy: {parcels['kategoria_ciszy'].value_counts().to_dict()}")
    logger.info(f"  Kategorie natury: {parcels['kategoria_natury'].value_counts().to_dict()}")
    logger.info(f"  Kategorie dostępu: {parcels['kategoria_dostepu'].value_counts().to_dict()}")
    logger.info(f"  Gęstość zabudowy: {parcels['gestosc_zabudowy'].value_counts().to_dict()}")

    return parcels


def prepare_for_neo4j(parcels: gpd.GeoDataFrame) -> pd.DataFrame:
    """Prepare data for Neo4j import - handle types and nulls."""
    logger.info("Przygotowanie danych dla Neo4j...")

    # Drop geometry column (not needed for CSV)
    df = pd.DataFrame(parcels.drop(columns=['geometry']))

    # Convert boolean columns to Neo4j friendly format
    bool_cols = df.select_dtypes(include=['bool']).columns
    for col in bool_cols:
        df[col] = df[col].map({True: 'true', False: 'false', None: ''})

    # Convert NaN to empty string for Neo4j
    df = df.fillna('')

    # Ensure id_dzialki is string
    df['id_dzialki'] = df['id_dzialki'].astype(str)

    # Round float columns to reasonable precision
    float_cols = df.select_dtypes(include=['float64']).columns
    for col in float_cols:
        df[col] = df[col].apply(lambda x: round(x, 2) if x != '' and pd.notna(x) else x)

    return df


def main():
    logger.info("=" * 60)
    logger.info("EKSPORT DANYCH DZIAŁEK DO CSV DLA NEO4J")
    logger.info("=" * 60)

    # Create output directory
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Load parcels
    logger.info("\nŁadowanie działek...")
    parcels = gpd.read_file(DATA_PATH / "parcels_enriched.gpkg")
    logger.info(f"  Załadowano {len(parcels):,} działek z {len(parcels.columns)} kolumnami")

    # Add binned categories if missing
    parcels = add_binned_categories(parcels)

    # Save updated parcels back to GPKG
    logger.info("\nZapisywanie zaktualizowanych działek...")
    parcels.to_file(DATA_PATH / "parcels_enriched.gpkg", driver='GPKG')

    # Prepare for Neo4j
    df = prepare_for_neo4j(parcels)

    # Export to CSV
    output_file = OUTPUT_PATH / "parcels_full.csv"
    logger.info(f"\nEksportowanie do: {output_file}")
    df.to_csv(output_file, index=False)

    # Statistics
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE EKSPORTU")
    logger.info("=" * 60)
    logger.info(f"Działki: {len(df):,}")
    logger.info(f"Kolumny: {len(df.columns)}")
    logger.info(f"Rozmiar pliku: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

    # List all columns
    logger.info("\nKolumny:")
    for col in sorted(df.columns):
        non_empty = (df[col] != '').sum()
        pct = non_empty / len(df) * 100
        logger.info(f"  {col}: {pct:.1f}% wypełnionych")

    logger.info("\n" + "=" * 60)
    logger.info("ZAKOŃCZONO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
