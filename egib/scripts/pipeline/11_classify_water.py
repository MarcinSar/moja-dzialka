#!/usr/bin/env python3
"""
11_classify_water.py - Klasyfikacja obiektów wodnych dla Neo4j

Klasyfikuje 2,307 obiektów wodnych z BDOT10k do 6 typów:
- morze: Morze Bałtyckie, zatoki
- zatoka: Zatoka Gdańska, Zatoka Pucka
- rzeka: Radunia, Motława, Strzyża, etc.
- jezioro: Osowskie, Jasień, Wysockie, etc.
- kanal: Kanał Raduni, Czarna Łacha, etc.
- staw: małe zbiorniki wodne

Używa kombinacji:
1. Atrybutu RODZAJ (woda morska, woda płynąca, woda stojąca)
2. Nazwy obiektu wodnego (jeśli dostępna)
3. Powierzchni dla rozróżnienia jezioro vs staw
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka/egib")
BDOT_PATH = BASE_PATH / "data" / "bdot10k_trojmiasto"
OUTPUT_PATH = BASE_PATH / "data" / "processed"


# Classification rules for named water bodies
WATER_CLASSIFICATION = {
    # Sea and bays (priority 1-2)
    'morze': {
        'names': ['Morze Bałtyckie', 'Bałtyk'],
        'rodzaj': 'woda morska',
        'priority': 1,
        'premium_factor': 2.0,
    },
    'zatoka': {
        'names': ['Zatoka Gdańska', 'Zatoka Pucka', 'Zatoka'],
        'partial_names': ['Zatoka'],
        'priority': 2,
        'premium_factor': 1.8,
    },
    # Rivers (priority 3)
    'rzeka': {
        'names': [
            # Main rivers
            'Wisła', 'Martwa Wisła', 'Przekop Wisły',
            'Radunia', 'Motława', 'Nowa Motława', 'Stara Motława', 'Opływ Motławy',
            'Strzyża', 'Potok Oliwski',
            # Gdynia rivers
            'Kacza', 'Chylonka', 'Swelina', 'Kamienna',
            # Other rivers
            'Rozwójka', 'Potok Siedlecki', 'Łaba', 'Oruński Potok',
            'Karaś', 'Bielawa', 'Jasień',  # Some are rivers
        ],
        'rodzaj': 'woda płynąca',
        'priority': 3,
        'premium_factor': 1.3,
    },
    # Canals (priority 4)
    'kanal': {
        'names': [
            'Kanał Raduni', 'Kanał Raduński',
            'Czarna Łacha', 'Kanał Czarna Łacha',
            'Kanał Wielki', 'Kanał Piaskowy', 'Kanał Młynówka',
            'Kanał na Stępce', 'Kanał Kaszubski',
        ],
        'partial_names': ['Kanał'],
        'priority': 5,
        'premium_factor': 1.1,
    },
    # Lakes (priority 4)
    'jezioro': {
        'names': [
            'Jezioro Osowskie', 'Osowskie',
            'Jezioro Jasień', 'Jasień',
            'Jezioro Wysockie', 'Wysockie',
            'Jezioro Czarne', 'Czarne',
            'Jezioro Otomińskie', 'Otomińskie',
            'Jezioro Jelitkowskie',
            'Zbiornik Powstańców Warszawskich',  # Large reservoir
        ],
        'partial_names': ['Jezioro', 'Zbiornik'],
        'rodzaj': 'woda stojąca',
        'min_area_m2': 10000,  # > 1 ha for unnamed
        'priority': 4,
        'premium_factor': 1.5,
    },
    # Ponds (priority 6 - lowest)
    'staw': {
        'partial_names': ['Staw', 'Sadzawka', 'Oczko'],
        'rodzaj': 'woda stojąca',
        'max_area_m2': 10000,  # < 1 ha
        'priority': 6,
        'premium_factor': 1.05,
    },
}


def classify_water_body(row: pd.Series) -> dict:
    """
    Classify a single water body based on name and attributes.

    Returns dict with:
    - water_type: classified type (morze, zatoka, rzeka, jezioro, kanal, staw)
    - water_type_pl: Polish name
    - priority: for sorting (lower = more important)
    - premium_factor: price multiplier for nearby parcels
    """
    nazwa = row.get('NAZWA')
    rodzaj = row.get('RODZAJ')
    area = row.get('area_m2', 0)

    # Default to staw for unknown
    result = {
        'water_type': 'staw',
        'water_type_pl': 'Staw',
        'priority': 6,
        'premium_factor': 1.05,
    }

    # 1. Check for sea water first (highest priority)
    if rodzaj == 'woda morska':
        if nazwa and any(bay in nazwa for bay in ['Zatoka']):
            return {
                'water_type': 'zatoka',
                'water_type_pl': 'Zatoka',
                'priority': 2,
                'premium_factor': 1.8,
            }
        return {
            'water_type': 'morze',
            'water_type_pl': 'Morze',
            'priority': 1,
            'premium_factor': 2.0,
        }

    # 2. Check by name (if available)
    if nazwa:
        nazwa_lower = nazwa.lower()

        # Check each category for exact or partial match
        for water_type, rules in WATER_CLASSIFICATION.items():
            # Skip morze - already handled above
            if water_type == 'morze':
                continue

            # Check exact names
            if 'names' in rules:
                if any(name.lower() == nazwa_lower or name.lower() in nazwa_lower
                       for name in rules['names']):
                    return {
                        'water_type': water_type,
                        'water_type_pl': water_type.capitalize(),
                        'priority': rules['priority'],
                        'premium_factor': rules['premium_factor'],
                    }

            # Check partial names
            if 'partial_names' in rules:
                if any(partial.lower() in nazwa_lower for partial in rules['partial_names']):
                    return {
                        'water_type': water_type,
                        'water_type_pl': water_type.capitalize(),
                        'priority': rules['priority'],
                        'premium_factor': rules['premium_factor'],
                    }

    # 3. Classify by RODZAJ and area (for unnamed water bodies)
    if rodzaj == 'woda płynąca':
        return {
            'water_type': 'rzeka',
            'water_type_pl': 'Rzeka',
            'priority': 3,
            'premium_factor': 1.3,
        }

    if rodzaj == 'woda stojąca':
        # Large standing water = lake, small = pond
        if area >= 10000:  # > 1 ha
            return {
                'water_type': 'jezioro',
                'water_type_pl': 'Jezioro',
                'priority': 4,
                'premium_factor': 1.5,
            }
        else:
            return {
                'water_type': 'staw',
                'water_type_pl': 'Staw',
                'priority': 6,
                'premium_factor': 1.05,
            }

    return result


def main():
    logger.info("=" * 60)
    logger.info("KLASYFIKACJA OBIEKTÓW WODNYCH")
    logger.info("=" * 60)

    # Load water data
    logger.info("\nŁadowanie danych wodnych...")
    water = gpd.read_file(BDOT_PATH / "wody.gpkg")
    logger.info(f"  Załadowano {len(water):,} obiektów wodnych")

    # Calculate area for classification
    logger.info("Obliczanie powierzchni...")
    water['area_m2'] = water.geometry.area

    # Classify each water body
    logger.info("Klasyfikacja obiektów...")
    classifications = water.apply(classify_water_body, axis=1)

    # Unpack classification results
    water['water_type'] = classifications.apply(lambda x: x['water_type'])
    water['water_type_pl'] = classifications.apply(lambda x: x['water_type_pl'])
    water['water_priority'] = classifications.apply(lambda x: x['priority'])
    water['water_premium_factor'] = classifications.apply(lambda x: x['premium_factor'])

    # Statistics
    logger.info("\n" + "=" * 60)
    logger.info("STATYSTYKI KLASYFIKACJI")
    logger.info("=" * 60)

    type_counts = water['water_type'].value_counts()
    for wtype, count in type_counts.items():
        pct = count / len(water) * 100
        logger.info(f"  {wtype}: {count:,} ({pct:.1f}%)")

    # Named water bodies by type
    logger.info("\nNazwane obiekty wodne:")
    named_water = water[water['NAZWA'].notna()]
    logger.info(f"  Razem: {len(named_water)} nazwanych")

    for wtype in ['morze', 'zatoka', 'rzeka', 'jezioro', 'kanal', 'staw']:
        type_named = named_water[named_water['water_type'] == wtype]
        if len(type_named) > 0:
            names = type_named['NAZWA'].unique()[:10]  # Show first 10
            logger.info(f"\n  {wtype.upper()} ({len(type_named)}):")
            for name in names:
                logger.info(f"    - {name}")

    # Key water bodies for Trójmiasto
    logger.info("\n" + "=" * 60)
    logger.info("KLUCZOWE OBIEKTY WODNE TRÓJMIASTA")
    logger.info("=" * 60)

    key_waters = [
        'Morze Bałtyckie', 'Zatoka Gdańska',
        'Wisła', 'Martwa Wisła', 'Motława', 'Radunia', 'Strzyża',
        'Jezioro Osowskie', 'Jezioro Jasień',
        'Kanał Raduni', 'Kanał Raduński',
    ]

    for key_name in key_waters:
        matches = water[water['NAZWA'].str.contains(key_name, na=False, case=False)]
        if len(matches) > 0:
            wtype = matches.iloc[0]['water_type']
            area = matches['area_m2'].sum()
            logger.info(f"  {key_name}: {wtype} ({area/10000:.1f} ha)")

    # Save classified water data
    output_file = OUTPUT_PATH / "water_classified.gpkg"
    water.to_file(output_file, driver='GPKG')
    logger.info(f"\nZapisano do: {output_file}")

    # Save summary CSV for reference
    summary = water[['NAZWA', 'RODZAJ', 'water_type', 'water_type_pl', 'area_m2', 'water_premium_factor']].copy()
    summary = summary.sort_values(['water_type', 'area_m2'], ascending=[True, False])
    summary_file = OUTPUT_PATH / "water_classified_summary.csv"
    summary.to_csv(summary_file, index=False)
    logger.info(f"Zapisano podsumowanie: {summary_file}")

    logger.info("\n" + "=" * 60)
    logger.info("KLASYFIKACJA ZAKOŃCZONA")
    logger.info("=" * 60)
    logger.info(f"Obiekty wodne: {len(water):,}")
    logger.info(f"Typy wód: {len(type_counts)}")
    logger.info(f"Nazwane: {len(named_water)}")


if __name__ == "__main__":
    main()
