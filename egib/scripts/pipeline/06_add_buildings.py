#!/usr/bin/env python3
"""
06_add_buildings.py - Dodanie cech zabudowy do działek

Spatial join budynków BDOT10k z działkami i agregacja cech:
- is_built: czy działka jest zabudowana
- building_count: liczba budynków
- building_area_m2: suma powierzchni zabudowy
- building_coverage_pct: % pokrycia działki budynkami
- building_main_function: dominująca funkcja (mieszkalne/gospodarcze/...)
- building_type: dominujący typ szczegółowy (jednorodzinny/wielorodzinny/...)
- building_max_floors: max liczba kondygnacji
- has_residential: czy jest budynek mieszkalny
- has_industrial: czy jest budynek przemysłowy
- under_construction: liczba budynków w budowie
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ścieżki
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PARCELS_PATH = DATA_DIR / "processed" / "parcels_enriched.gpkg"
BUILDINGS_PATH = DATA_DIR / "bdot10k_trojmiasto" / "budynki.gpkg"
OUTPUT_PATH = DATA_DIR / "processed" / "parcels_enriched.gpkg"


def get_dominant(values: pd.Series) -> str:
    """Zwraca najczęstszą wartość lub None."""
    if len(values) == 0:
        return None
    counter = Counter(values.dropna())
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def simplify_function(func: str) -> str:
    """Upraszcza funkcję ogólną do krótkiej nazwy."""
    if pd.isna(func):
        return None
    mapping = {
        'budynki mieszkalne': 'mieszkalne',
        'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa': 'gospodarcze',
        'budynki handlowo-usługowe': 'handlowo-usługowe',
        'budynki przemysłowe': 'przemysłowe',
        'budynki transportu i łączności': 'transport',
        'budynki biurowe': 'biurowe',
        'zbiorniki, silosy i budynki magazynowe': 'magazynowe',
        'pozostałe budynki niemieszkalne': 'inne',
        'budynki oświaty, nauki i kultury oraz budynki sportowe': 'edukacja/kultura',
        'budynki szpitali i inne budynki opieki zdrowotnej': 'zdrowie',
    }
    return mapping.get(func, func)


def main():
    logger.info("Ładowanie działek...")
    parcels = gpd.read_file(PARCELS_PATH)
    logger.info(f"  Załadowano {len(parcels):,} działek")

    logger.info("Ładowanie budynków...")
    buildings = gpd.read_file(BUILDINGS_PATH)
    logger.info(f"  Załadowano {len(buildings):,} budynków")

    # Upewnij się, że CRS są zgodne
    if buildings.crs != parcels.crs:
        logger.info(f"  Reprojekcja budynków z {buildings.crs} do {parcels.crs}")
        buildings = buildings.to_crs(parcels.crs)

    # Oblicz powierzchnię budynków
    logger.info("Obliczanie powierzchni budynków...")
    buildings['bld_area'] = buildings.geometry.area

    # Uproszczone funkcje
    buildings['func_simple'] = buildings['FUNKCJAOGOLNABUDYNKU'].apply(simplify_function)

    # Flagi
    buildings['is_residential'] = buildings['FUNKCJAOGOLNABUDYNKU'] == 'budynki mieszkalne'
    buildings['is_industrial'] = buildings['FUNKCJAOGOLNABUDYNKU'] == 'budynki przemysłowe'
    buildings['is_under_construction'] = buildings['KATEGORIAISTNIENIA'] == 'w budowie'

    # Spatial join - przypisz budynki do działek
    logger.info("Spatial join budynków z działkami...")
    # Używamy centroidów budynków dla szybkości (budynek należy do działki gdzie jest jego środek)
    buildings_centroids = buildings.copy()
    buildings_centroids['geometry'] = buildings_centroids.geometry.centroid

    # Przygotuj działki z indeksem jako kolumną
    parcels_for_join = parcels[['geometry']].copy()
    parcels_for_join['parcel_idx'] = parcels_for_join.index

    joined = gpd.sjoin(
        buildings_centroids,
        parcels_for_join,
        how='inner',  # tylko budynki które matchują
        predicate='within'
    )

    logger.info(f"  Zmatchowano {len(joined):,} budynków z działkami")

    # Agregacja per działka
    logger.info("Agregacja cech per działka...")

    # Grupuj po indeksie działki
    grouped = joined.groupby('parcel_idx')

    # Agregaty
    agg_df = pd.DataFrame({
        'building_count': grouped.size(),
        'building_area_m2': grouped['bld_area'].sum(),
        'building_max_floors': grouped['LICZBAKONDYGNACJI'].max(),
        'has_residential': grouped['is_residential'].any(),
        'has_industrial': grouped['is_industrial'].any(),
        'under_construction': grouped['is_under_construction'].sum(),
    })

    # Dominująca funkcja i typ - musimy policzyć osobno
    logger.info("Obliczanie dominujących funkcji...")
    dominant_func = grouped['func_simple'].apply(get_dominant)
    dominant_type = grouped['PRZEWAZAJACAFUNKCJABUDYNKU'].apply(get_dominant)

    agg_df['building_main_function'] = dominant_func
    agg_df['building_type'] = dominant_type

    # Dołącz do działek
    logger.info("Łączenie z działkami...")
    parcels = parcels.reset_index(drop=True)

    # Merge przez indeks (szybsze niż iteracja)
    parcels = parcels.join(agg_df, how='left')

    # Wypełnij braki dla niezabudowanych działek
    parcels['building_count'] = parcels['building_count'].fillna(0).astype(int)
    parcels['building_area_m2'] = parcels['building_area_m2'].fillna(0.0)
    parcels['building_max_floors'] = parcels['building_max_floors'].fillna(0).astype(int)
    parcels['has_residential'] = parcels['has_residential'].fillna(False).astype(bool)
    parcels['has_industrial'] = parcels['has_industrial'].fillna(False).astype(bool)
    parcels['under_construction'] = parcels['under_construction'].fillna(0).astype(int)

    # Oblicz dodatkowe cechy
    parcels['is_built'] = parcels['building_count'] > 0
    parcels['parcel_area_m2'] = parcels.geometry.area
    parcels['building_coverage_pct'] = (parcels['building_area_m2'] / parcels['parcel_area_m2'] * 100).round(1)
    parcels['building_coverage_pct'] = parcels['building_coverage_pct'].clip(0, 100)  # Clamp do 100%

    # Statystyki
    logger.info("\n" + "=" * 60)
    logger.info("STATYSTYKI ZABUDOWY")
    logger.info("=" * 60)

    built = parcels['is_built'].sum()
    logger.info(f"Działki zabudowane: {built:,} ({built/len(parcels)*100:.1f}%)")
    logger.info(f"Działki niezabudowane: {len(parcels)-built:,} ({(len(parcels)-built)/len(parcels)*100:.1f}%)")

    logger.info(f"\nLiczba budynków na działce:")
    logger.info(f"  0: {(parcels['building_count']==0).sum():,}")
    logger.info(f"  1: {(parcels['building_count']==1).sum():,}")
    logger.info(f"  2-5: {((parcels['building_count']>=2) & (parcels['building_count']<=5)).sum():,}")
    logger.info(f"  >5: {(parcels['building_count']>5).sum():,}")

    logger.info(f"\nDominująca funkcja budynków:")
    for func, cnt in parcels[parcels['is_built']]['building_main_function'].value_counts().head(6).items():
        logger.info(f"  {func}: {cnt:,}")

    logger.info(f"\nPokrycie zabudową (dla zabudowanych):")
    built_parcels = parcels[parcels['is_built']]
    logger.info(f"  Mediana: {built_parcels['building_coverage_pct'].median():.1f}%")
    logger.info(f"  Średnia: {built_parcels['building_coverage_pct'].mean():.1f}%")
    logger.info(f"  Max: {built_parcels['building_coverage_pct'].max():.1f}%")

    logger.info(f"\nMax kondygnacje:")
    logger.info(f"  1-2: {((parcels['building_max_floors']>=1) & (parcels['building_max_floors']<=2)).sum():,}")
    logger.info(f"  3-5: {((parcels['building_max_floors']>=3) & (parcels['building_max_floors']<=5)).sum():,}")
    logger.info(f"  6+: {(parcels['building_max_floors']>=6).sum():,}")

    logger.info(f"\nBudynki w budowie: {parcels['under_construction'].sum():,} na {(parcels['under_construction']>0).sum():,} działkach")

    # Zapisz
    logger.info(f"\nZapisywanie do {OUTPUT_PATH}...")
    parcels.to_file(OUTPUT_PATH, driver="GPKG")
    logger.info(f"Zapisano {len(parcels):,} działek z {len(parcels.columns)} kolumnami")

    # Lista nowych kolumn
    new_cols = ['is_built', 'building_count', 'building_area_m2', 'building_coverage_pct',
                'building_main_function', 'building_type', 'building_max_floors',
                'has_residential', 'has_industrial', 'under_construction', 'parcel_area_m2']
    logger.info(f"\nNowe kolumny: {new_cols}")


if __name__ == "__main__":
    main()
