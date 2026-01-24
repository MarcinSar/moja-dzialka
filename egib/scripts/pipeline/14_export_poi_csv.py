#!/usr/bin/env python3
"""
14_export_poi_csv.py - Eksport danych POI do CSV dla Neo4j

Eksportuje punkty zainteresowania (POI) do formatu CSV
dla importu do Neo4j jako węzły:
- schools.csv: School nodes
- bus_stops.csv: BusStop nodes
- forests.csv: Forest nodes
- waters.csv: Water nodes (z klasyfikacją!)
- shops.csv: Shop nodes
- roads.csv: Road nodes (główne drogi)
- categories.csv: Category nodes (cisza, natura, dostęp, ceny)

Output: data/ready-for-import/neo4j/*.csv
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
EGIB_PATH = BASE_PATH / "egib" / "data"
PROCESSED_PATH = EGIB_PATH / "processed"
BDOT_PATH = EGIB_PATH / "bdot10k_trojmiasto"
OUTPUT_PATH = BASE_PATH / "data" / "ready-for-import" / "neo4j"


def extract_coordinates(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Extract centroid coordinates from GeoDataFrame."""
    df = pd.DataFrame(gdf.drop(columns=['geometry']))
    df['centroid_x'] = gdf.geometry.centroid.x
    df['centroid_y'] = gdf.geometry.centroid.y
    return df


def export_schools():
    """Export schools from BDOT10k."""
    logger.info("\nEksport szkół...")

    try:
        gdf = gpd.read_file(BDOT_PATH / "szkoly.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} szkół")

        df = extract_coordinates(gdf)

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"school_{r['TERYT']}_{r['LOKALNYID'][:8]}" if pd.notna(r.get('LOKALNYID')) else f"school_{r.name}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'NAZWA': 'name',
            'RODZAJ': 'type',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[list(export_cols.keys())].rename(columns=export_cols)
        df = df.fillna('')

        output_file = OUTPUT_PATH / "schools.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_bus_stops():
    """Export bus stops from BDOT10k."""
    logger.info("\nEksport przystanków...")

    try:
        gdf = gpd.read_file(BDOT_PATH / "przystanki.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} przystanków")

        df = extract_coordinates(gdf)

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"busstop_{r['TERYT']}_{r['LOKALNYID'][:8]}" if pd.notna(r.get('LOKALNYID')) else f"busstop_{r.name}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'NAZWA': 'name',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[[c for c in export_cols.keys() if c in df.columns]].rename(
            columns={k: v for k, v in export_cols.items() if k in df.columns}
        )
        df = df.fillna('')

        output_file = OUTPUT_PATH / "bus_stops.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_forests():
    """Export forests from BDOT10k."""
    logger.info("\nEksport lasów...")

    try:
        gdf = gpd.read_file(BDOT_PATH / "lasy.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} terenów leśnych")

        df = extract_coordinates(gdf)

        # Calculate area
        df['area_m2'] = gdf.geometry.area

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"forest_{r['TERYT']}_{r['LOKALNYID'][:8]}" if pd.notna(r.get('LOKALNYID')) else f"forest_{r.name}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'RODZAJ': 'type',
            'area_m2': 'area_m2',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[[c for c in export_cols.keys() if c in df.columns]].rename(
            columns={k: v for k, v in export_cols.items() if k in df.columns}
        )
        df = df.fillna('')
        df['area_m2'] = df['area_m2'].apply(lambda x: round(x, 0) if x != '' else x)

        output_file = OUTPUT_PATH / "forests.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_waters():
    """Export classified water bodies."""
    logger.info("\nEksport wód (z klasyfikacją)...")

    try:
        gdf = gpd.read_file(PROCESSED_PATH / "water_classified.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} obiektów wodnych")

        df = extract_coordinates(gdf)

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"water_{r['TERYT']}_{r['LOKALNYID'][:8]}" if pd.notna(r.get('LOKALNYID')) else f"water_{r.name}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'NAZWA': 'name',
            'RODZAJ': 'rodzaj',
            'water_type': 'water_type',
            'water_type_pl': 'water_type_pl',
            'water_priority': 'priority',
            'water_premium_factor': 'premium_factor',
            'area_m2': 'area_m2',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[[c for c in export_cols.keys() if c in df.columns]].rename(
            columns={k: v for k, v in export_cols.items() if k in df.columns}
        )
        df = df.fillna('')
        df['area_m2'] = df['area_m2'].apply(lambda x: round(x, 0) if x != '' else x)

        output_file = OUTPUT_PATH / "waters.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

        # Statistics by type
        logger.info("  Typy wód:")
        for wtype, count in gdf['water_type'].value_counts().items():
            logger.info(f"    {wtype}: {count}")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_shops():
    """Export shops from POI data."""
    logger.info("\nEksport sklepów z POI...")

    try:
        gdf = gpd.read_file(PROCESSED_PATH / "poi_trojmiasto.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} POI")

        # Filter shops
        shops = gdf[gdf['category'] == 'shop']
        logger.info(f"  Sklepy: {len(shops):,}")

        if len(shops) == 0:
            # Try supermarkets
            shops = gdf[gdf['type'].isin(['supermarket', 'convenience', 'mall'])]
            logger.info(f"  Supermarkety: {len(shops):,}")

        df = extract_coordinates(shops)

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"shop_{r.name}_{str(r.get('name', ''))[:8]}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'name': 'name',
            'type': 'shop_type',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[[c for c in export_cols.keys() if c in df.columns]].rename(
            columns={k: v for k, v in export_cols.items() if k in df.columns}
        )
        df = df.fillna('')

        output_file = OUTPUT_PATH / "shops.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_roads():
    """Export main roads from BDOT10k."""
    logger.info("\nEksport głównych dróg...")

    try:
        gdf = gpd.read_file(BDOT_PATH / "drogi_glowne.gpkg")
        logger.info(f"  Załadowano {len(gdf):,} dróg głównych")

        df = extract_coordinates(gdf)

        # Calculate length
        df['length_m'] = gdf.geometry.length

        # Add unique ID
        df['node_id'] = df.apply(
            lambda r: f"road_{r['TERYT']}_{r['LOKALNYID'][:8]}" if pd.notna(r.get('LOKALNYID')) else f"road_{r.name}",
            axis=1
        )

        # Select and rename columns
        export_cols = {
            'node_id': 'id',
            'NAZWA': 'name',
            'RODZAJ': 'type',
            'length_m': 'length_m',
            'centroid_x': 'x',
            'centroid_y': 'y',
        }
        df = df[[c for c in export_cols.keys() if c in df.columns]].rename(
            columns={k: v for k, v in export_cols.items() if k in df.columns}
        )
        df = df.fillna('')
        df['length_m'] = df['length_m'].apply(lambda x: round(x, 0) if x != '' else x)

        output_file = OUTPUT_PATH / "roads.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"  Zapisano: {output_file} ({len(df)} rekordów)")

    except Exception as e:
        logger.error(f"  Błąd: {e}")


def export_categories():
    """Export category nodes for graph traversal."""
    logger.info("\nEksport węzłów kategorii...")

    # Quietness categories
    quietness = pd.DataFrame([
        {'id': 'bardzo_cicha', 'name_pl': 'Bardzo cicha', 'score_min': 80, 'score_max': 100},
        {'id': 'cicha', 'name_pl': 'Cicha', 'score_min': 60, 'score_max': 79},
        {'id': 'umiarkowana', 'name_pl': 'Umiarkowana', 'score_min': 40, 'score_max': 59},
        {'id': 'glosna', 'name_pl': 'Głośna', 'score_min': 0, 'score_max': 39},
    ])
    quietness.to_csv(OUTPUT_PATH / "categories_quietness.csv", index=False)
    logger.info(f"  Zapisano: categories_quietness.csv")

    # Nature categories
    nature = pd.DataFrame([
        {'id': 'bardzo_zielona', 'name_pl': 'Bardzo zielona', 'score_min': 70, 'score_max': 100},
        {'id': 'zielona', 'name_pl': 'Zielona', 'score_min': 50, 'score_max': 69},
        {'id': 'umiarkowana', 'name_pl': 'Umiarkowana', 'score_min': 30, 'score_max': 49},
        {'id': 'zurbanizowana', 'name_pl': 'Zurbanizowana', 'score_min': 0, 'score_max': 29},
    ])
    nature.to_csv(OUTPUT_PATH / "categories_nature.csv", index=False)
    logger.info(f"  Zapisano: categories_nature.csv")

    # Access categories
    access = pd.DataFrame([
        {'id': 'doskonala', 'name_pl': 'Doskonała', 'score_min': 70, 'score_max': 100},
        {'id': 'dobra', 'name_pl': 'Dobra', 'score_min': 50, 'score_max': 69},
        {'id': 'umiarkowana', 'name_pl': 'Umiarkowana', 'score_min': 30, 'score_max': 49},
        {'id': 'ograniczona', 'name_pl': 'Ograniczona', 'score_min': 0, 'score_max': 29},
    ])
    access.to_csv(OUTPUT_PATH / "categories_access.csv", index=False)
    logger.info(f"  Zapisano: categories_access.csv")

    # Density categories
    density = pd.DataFrame([
        {'id': 'gesta', 'name_pl': 'Gęsta', 'buildings_min': 50, 'buildings_max': 999999},
        {'id': 'umiarkowana', 'name_pl': 'Umiarkowana', 'buildings_min': 20, 'buildings_max': 49},
        {'id': 'rzadka', 'name_pl': 'Rzadka', 'buildings_min': 5, 'buildings_max': 19},
        {'id': 'bardzo_rzadka', 'name_pl': 'Bardzo rzadka', 'buildings_min': 0, 'buildings_max': 4},
    ])
    density.to_csv(OUTPUT_PATH / "categories_density.csv", index=False)
    logger.info(f"  Zapisano: categories_density.csv")

    # Water type categories
    water_types = pd.DataFrame([
        {'id': 'morze', 'name_pl': 'Morze', 'priority': 1, 'premium_factor': 2.0},
        {'id': 'zatoka', 'name_pl': 'Zatoka', 'priority': 2, 'premium_factor': 1.8},
        {'id': 'rzeka', 'name_pl': 'Rzeka', 'priority': 3, 'premium_factor': 1.3},
        {'id': 'jezioro', 'name_pl': 'Jezioro', 'priority': 4, 'premium_factor': 1.5},
        {'id': 'kanal', 'name_pl': 'Kanał', 'priority': 5, 'premium_factor': 1.1},
        {'id': 'staw', 'name_pl': 'Staw', 'priority': 6, 'premium_factor': 1.05},
    ])
    water_types.to_csv(OUTPUT_PATH / "categories_water_type.csv", index=False)
    logger.info(f"  Zapisano: categories_water_type.csv")

    # Price segment categories
    price_segments = pd.DataFrame([
        {'id': 'ULTRA_PREMIUM', 'name_pl': 'Ultra Premium', 'price_min': 3000, 'price_max': 999999, 'locations': 'Sopot centrum, Orłowo'},
        {'id': 'PREMIUM', 'name_pl': 'Premium', 'price_min': 1500, 'price_max': 2999, 'locations': 'Jelitkowo, Oliwa'},
        {'id': 'HIGH', 'name_pl': 'Wysoki', 'price_min': 800, 'price_max': 1499, 'locations': 'Wrzeszcz, Redłowo'},
        {'id': 'MEDIUM', 'name_pl': 'Średni', 'price_min': 500, 'price_max': 799, 'locations': 'Osowa, Kokoszki'},
        {'id': 'BUDGET', 'name_pl': 'Budżetowy', 'price_min': 300, 'price_max': 499, 'locations': 'Łostowice, Wiczlino'},
        {'id': 'ECONOMY', 'name_pl': 'Ekonomiczny', 'price_min': 0, 'price_max': 299, 'locations': 'Żukowo, Kolbudy'},
    ])
    price_segments.to_csv(OUTPUT_PATH / "categories_price_segment.csv", index=False)
    logger.info(f"  Zapisano: categories_price_segment.csv")


def main():
    logger.info("=" * 60)
    logger.info("EKSPORT POI DO CSV DLA NEO4J")
    logger.info("=" * 60)

    # Create output directory
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Export all POI types
    export_schools()
    export_bus_stops()
    export_forests()
    export_waters()
    export_shops()
    export_roads()
    export_categories()

    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE")
    logger.info("=" * 60)

    # List generated files
    csv_files = list(OUTPUT_PATH.glob("*.csv"))
    total_size = sum(f.stat().st_size for f in csv_files)
    logger.info(f"Wygenerowano {len(csv_files)} plików CSV")
    logger.info(f"Łączny rozmiar: {total_size / 1024 / 1024:.1f} MB")

    for f in sorted(csv_files):
        size = f.stat().st_size / 1024
        logger.info(f"  {f.name}: {size:.1f} KB")

    logger.info("\n" + "=" * 60)
    logger.info("ZAKOŃCZONO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
