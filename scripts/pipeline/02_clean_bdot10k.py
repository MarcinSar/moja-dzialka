#!/usr/bin/env python3
"""
02_clean_bdot10k.py - BDOT10k Consolidation Script

Consolidates BDOT10k layers into priority GeoPackages:
- bdot10k_buildings.gpkg - BUBD_A (buildings with function)
- bdot10k_roads.gpkg - SKDR_L + SKJZ_L (roads with class)
- bdot10k_forest.gpkg - PTLZ_A
- bdot10k_water.gpkg - PTWP_A
- bdot10k_poi.gpkg - schools, shops, bus stops
- bdot10k_protected.gpkg - TCON_A (Natura 2000)

Usage:
    python scripts/pipeline/02_clean_bdot10k.py

Output:
    data/cleaned/v1.0.0/bdot10k/*.gpkg
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely import make_valid
import warnings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RAW_BDOT10K_DIR,
    CLEANED_BDOT10K_DIR,
    TARGET_CRS,
    BDOT10K_LAYERS,
    BUILDING_FUNCTIONS,
    ROAD_CLASSES,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info
from utils.io import load_geopackage, save_geopackage
from utils.geometry import make_geometries_valid

# Setup logger
logger = setup_logger(level="INFO")


def load_bdot10k_layer(layer_code: str) -> Optional[gpd.GeoDataFrame]:
    """Load a BDOT10k layer if it exists."""
    if layer_code not in BDOT10K_LAYERS:
        logger.warning(f"Unknown layer code: {layer_code}")
        return None

    filepath = RAW_BDOT10K_DIR / BDOT10K_LAYERS[layer_code]
    if not filepath.exists():
        logger.warning(f"Layer file not found: {filepath}")
        return None

    try:
        gdf = load_geopackage(filepath, logger=logger)
        return gdf
    except Exception as e:
        logger.error(f"Error loading {layer_code}: {e}")
        return None


def clean_geometries(gdf: gpd.GeoDataFrame, layer_name: str) -> gpd.GeoDataFrame:
    """Fix invalid geometries."""
    invalid_before = (~gdf.geometry.is_valid).sum()
    if invalid_before > 0:
        logger.info(f"  Fixing {invalid_before:,} invalid geometries in {layer_name}...")
        gdf = make_geometries_valid(gdf)

    # Remove empty geometries
    empty_count = gdf.geometry.is_empty.sum()
    if empty_count > 0:
        logger.info(f"  Removing {empty_count:,} empty geometries...")
        gdf = gdf[~gdf.geometry.is_empty].copy()

    return gdf


def consolidate_buildings() -> Optional[gpd.GeoDataFrame]:
    """
    Consolidate building data from BUBD_A.

    Preserves key columns:
    - geometry
    - X_KOD (building function code)
    - funkcja (function description if available)
    - nazwa (name if available)
    """
    logger.info("Processing buildings (BUBD_A)...")

    gdf = load_bdot10k_layer("BUBD_A")
    if gdf is None or gdf.empty:
        return None

    # Clean geometries
    gdf = clean_geometries(gdf, "BUBD_A")

    # Select and rename key columns
    logger.info(f"  Available columns: {list(gdf.columns)}")

    # Find relevant columns
    columns_to_keep = ["geometry"]

    # Function code
    kod_col = next((c for c in gdf.columns if c.upper() == "X_KOD"), None)
    if kod_col:
        columns_to_keep.append(kod_col)
        gdf = gdf.rename(columns={kod_col: "funkcja_kod"})
        columns_to_keep[-1] = "funkcja_kod"

    # Function description
    funkcja_col = next((c for c in gdf.columns if "funkcja" in c.lower() and c.upper() != "X_KOD"), None)
    if funkcja_col:
        columns_to_keep.append(funkcja_col)
        gdf = gdf.rename(columns={funkcja_col: "funkcja"})
        columns_to_keep[-1] = "funkcja"

    # Name
    nazwa_col = next((c for c in gdf.columns if "nazwa" in c.lower()), None)
    if nazwa_col:
        columns_to_keep.append(nazwa_col)
        gdf = gdf.rename(columns={nazwa_col: "nazwa"})
        columns_to_keep[-1] = "nazwa"

    # Category
    kat_col = next((c for c in gdf.columns if "kat" in c.lower()), None)
    if kat_col:
        columns_to_keep.append(kat_col)
        gdf = gdf.rename(columns={kat_col: "kategoria"})
        columns_to_keep[-1] = "kategoria"

    # Keep only selected columns
    gdf = gdf[[c for c in columns_to_keep if c in gdf.columns]]

    # Add building category based on function code
    if "funkcja_kod" in gdf.columns:
        def categorize_building(kod):
            if pd.isna(kod):
                return "inne"
            kod_str = str(kod)
            for category, codes in BUILDING_FUNCTIONS.items():
                if kod_str in codes:
                    return category
            return "inne"

        gdf["kategoria_uproszczona"] = gdf["funkcja_kod"].apply(categorize_building)

        # Log category distribution
        cat_counts = gdf["kategoria_uproszczona"].value_counts()
        logger.info("  Building categories:")
        for cat, count in cat_counts.head(10).items():
            logger.info(f"    {cat}: {count:,}")

    log_dataframe_info(gdf, "Cleaned Buildings", logger)
    return gdf


def consolidate_roads() -> Optional[gpd.GeoDataFrame]:
    """
    Consolidate road data from SKDR_L and SKJZ_L.

    Merges road centerlines with lane data.
    """
    logger.info("Processing roads (SKDR_L + SKJZ_L)...")

    # Load both layers
    skdr = load_bdot10k_layer("SKDR_L")
    skjz = load_bdot10k_layer("SKJZ_L")

    roads = []

    if skdr is not None and not skdr.empty:
        skdr = clean_geometries(skdr, "SKDR_L")
        logger.info(f"  SKDR_L columns: {list(skdr.columns)}")

        # Find class column
        klasa_col = next((c for c in skdr.columns if "klasa" in c.lower()), None)
        nazwa_col = next((c for c in skdr.columns if "nazwa" in c.lower()), None)

        cols = ["geometry"]
        rename = {}

        if klasa_col:
            cols.append(klasa_col)
            rename[klasa_col] = "klasa"
        if nazwa_col:
            cols.append(nazwa_col)
            rename[nazwa_col] = "nazwa"

        skdr = skdr[[c for c in cols if c in skdr.columns]]
        if rename:
            skdr = skdr.rename(columns=rename)
        skdr["zrodlo"] = "SKDR_L"
        roads.append(skdr)

    if skjz is not None and not skjz.empty:
        skjz = clean_geometries(skjz, "SKJZ_L")
        logger.info(f"  SKJZ_L columns: {list(skjz.columns)}")

        # Find class column
        klasa_col = next((c for c in skjz.columns if "klasa" in c.lower()), None)
        kategoria_col = next((c for c in skjz.columns if "kat" in c.lower()), None)

        cols = ["geometry"]
        rename = {}

        if klasa_col:
            cols.append(klasa_col)
            rename[klasa_col] = "klasa"
        if kategoria_col:
            cols.append(kategoria_col)
            rename[kategoria_col] = "kategoria"

        skjz = skjz[[c for c in cols if c in skjz.columns]]
        if rename:
            skjz = skjz.rename(columns=rename)
        skjz["zrodlo"] = "SKJZ_L"
        roads.append(skjz)

    if not roads:
        return None

    # Combine
    gdf = pd.concat(roads, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=TARGET_CRS)

    # Add road type classification
    if "klasa" in gdf.columns:
        def classify_road(klasa):
            if pd.isna(klasa):
                return "nieokreslona"
            klasa_str = str(klasa).upper()
            for name, code in ROAD_CLASSES.items():
                if klasa_str == code:
                    return name
            return "inna"

        gdf["typ_drogi"] = gdf["klasa"].apply(classify_road)

        # Log distribution
        type_counts = gdf["typ_drogi"].value_counts()
        logger.info("  Road types:")
        for typ, count in type_counts.items():
            logger.info(f"    {typ}: {count:,}")

    log_dataframe_info(gdf, "Cleaned Roads", logger)
    return gdf


def consolidate_forest() -> Optional[gpd.GeoDataFrame]:
    """Consolidate forest data from PTLZ_A."""
    logger.info("Processing forests (PTLZ_A)...")

    gdf = load_bdot10k_layer("PTLZ_A")
    if gdf is None or gdf.empty:
        return None

    gdf = clean_geometries(gdf, "PTLZ_A")

    # Keep minimal columns
    cols_to_keep = ["geometry"]
    for col in gdf.columns:
        if any(x in col.lower() for x in ["rodzaj", "gatunek", "nazwa"]):
            cols_to_keep.append(col)

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    # Add area
    gdf["area_ha"] = gdf.geometry.area / 10000

    log_dataframe_info(gdf, "Cleaned Forest", logger)
    return gdf


def consolidate_water() -> Optional[gpd.GeoDataFrame]:
    """Consolidate water data from PTWP_A."""
    logger.info("Processing water (PTWP_A)...")

    gdf = load_bdot10k_layer("PTWP_A")
    if gdf is None or gdf.empty:
        return None

    gdf = clean_geometries(gdf, "PTWP_A")

    # Keep minimal columns
    cols_to_keep = ["geometry"]
    for col in gdf.columns:
        if any(x in col.lower() for x in ["rodzaj", "nazwa", "typ"]):
            cols_to_keep.append(col)

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    # Add area
    gdf["area_ha"] = gdf.geometry.area / 10000

    log_dataframe_info(gdf, "Cleaned Water", logger)
    return gdf


def consolidate_poi() -> Optional[gpd.GeoDataFrame]:
    """
    Consolidate POI data from various sources.

    Includes:
    - Schools (from BUBD_A - PRZEWAZAJACAFUNKCJABUDYNKU contains "szkoła")
    - Shops (from BUBD_A - FUNKCJAOGOLNABUDYNKU = "budynki handlowo-usługowe")
    - Bus stops (from OIKM_P)
    - Hospitals/clinics (from BUBD_A - FUNKCJAOGOLNABUDYNKU contains "szpitali")
    """
    logger.info("Processing POIs...")

    pois = []

    # Extract POIs from buildings
    buildings = load_bdot10k_layer("BUBD_A")
    if buildings is not None and not buildings.empty:
        # BDOT10k uses text-based function descriptions, not numeric codes
        # Key columns:
        # - FUNKCJAOGOLNABUDYNKU: general function category
        # - PRZEWAZAJACAFUNKCJABUDYNKU: specific function

        funkcja_ogolna = next((c for c in buildings.columns if "FUNKCJAOGOLNA" in c.upper()), None)
        funkcja_szczeg = next((c for c in buildings.columns if "PRZEWAZAJACAFUNKCJA" in c.upper()), None)

        logger.info(f"  Using columns: funkcja_ogolna={funkcja_ogolna}, funkcja_szczeg={funkcja_szczeg}")

        if funkcja_szczeg:
            # Schools - look for "szkoła" in specific function
            # Includes: szkoła podstawowa, przedszkole, etc.
            schools_mask = buildings[funkcja_szczeg].fillna("").str.lower().str.contains("szkoła|przedszkol")
            schools = buildings[schools_mask].copy()
            if not schools.empty:
                schools = schools[["geometry"]].copy()
                schools["poi_type"] = "szkola"
                schools["geometry"] = schools.geometry.centroid
                pois.append(schools)
                logger.info(f"  Schools/Kindergartens: {len(schools):,}")

        if funkcja_ogolna:
            # Shops - "budynki handlowo-usługowe" in general function
            shops_mask = buildings[funkcja_ogolna].fillna("").str.lower().str.contains("handlowo-usługowe")
            shops = buildings[shops_mask].copy()
            if not shops.empty:
                shops = shops[["geometry"]].copy()
                shops["poi_type"] = "sklep"
                shops["geometry"] = shops.geometry.centroid
                pois.append(shops)
                logger.info(f"  Shops: {len(shops):,}")

            # Hospitals/clinics - "szpitali i inne budynki opieki zdrowotnej"
            hospitals_mask = buildings[funkcja_ogolna].fillna("").str.lower().str.contains("szpital|opieki zdrowotnej")
            hospitals = buildings[hospitals_mask].copy()
            if not hospitals.empty:
                hospitals = hospitals[["geometry"]].copy()
                hospitals["poi_type"] = "szpital_przychodnia"
                hospitals["geometry"] = hospitals.geometry.centroid
                pois.append(hospitals)
                logger.info(f"  Hospitals/Clinics: {len(hospitals):,}")

    # Bus stops
    bus_stops = load_bdot10k_layer("OIKM_P")
    if bus_stops is not None and not bus_stops.empty:
        bus_stops = bus_stops[["geometry"]].copy()
        bus_stops["poi_type"] = "przystanek"
        pois.append(bus_stops)
        logger.info(f"  Bus stops: {len(bus_stops):,}")

    if not pois:
        return None

    # Combine
    gdf = pd.concat(pois, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=TARGET_CRS)

    log_dataframe_info(gdf, "Cleaned POIs", logger)
    return gdf


def consolidate_protected() -> Optional[gpd.GeoDataFrame]:
    """Consolidate protected areas from TCON_A (Natura 2000)."""
    logger.info("Processing protected areas (TCON_A)...")

    gdf = load_bdot10k_layer("TCON_A")
    if gdf is None or gdf.empty:
        logger.warning("  No TCON_A data found")
        return None

    gdf = clean_geometries(gdf, "TCON_A")

    # Keep relevant columns
    cols_to_keep = ["geometry"]
    for col in gdf.columns:
        if any(x in col.lower() for x in ["nazwa", "kod", "typ", "rodzaj"]):
            cols_to_keep.append(col)

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    # Add area
    gdf["area_ha"] = gdf.geometry.area / 10000

    log_dataframe_info(gdf, "Cleaned Protected Areas", logger)
    return gdf


def consolidate_industrial() -> Optional[gpd.GeoDataFrame]:
    """Consolidate industrial areas from KUPG_A."""
    logger.info("Processing industrial areas (KUPG_A)...")

    gdf = load_bdot10k_layer("KUPG_A")
    if gdf is None or gdf.empty:
        logger.warning("  No KUPG_A data found")
        return None

    gdf = clean_geometries(gdf, "KUPG_A")

    # Keep minimal columns
    cols_to_keep = ["geometry"]
    for col in gdf.columns:
        if any(x in col.lower() for x in ["nazwa", "rodzaj", "typ"]):
            cols_to_keep.append(col)

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    # Add area
    gdf["area_ha"] = gdf.geometry.area / 10000

    log_dataframe_info(gdf, "Cleaned Industrial Areas", logger)
    return gdf


def main():
    """Main consolidation function."""
    logger.info("=" * 60)
    logger.info("BDOT10K CONSOLIDATION")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()
    CLEANED_BDOT10K_DIR.mkdir(parents=True, exist_ok=True)

    # Process each layer type
    consolidations = [
        ("bdot10k_buildings.gpkg", consolidate_buildings),
        ("bdot10k_roads.gpkg", consolidate_roads),
        ("bdot10k_forest.gpkg", consolidate_forest),
        ("bdot10k_water.gpkg", consolidate_water),
        ("bdot10k_poi.gpkg", consolidate_poi),
        ("bdot10k_protected.gpkg", consolidate_protected),
        ("bdot10k_industrial.gpkg", consolidate_industrial),
    ]

    saved_files = []
    for filename, consolidate_func in consolidations:
        logger.info(f"\n--- {filename} ---")
        try:
            gdf = consolidate_func()
            if gdf is not None and not gdf.empty:
                output_path = CLEANED_BDOT10K_DIR / filename
                save_geopackage(gdf, output_path, logger=logger)
                saved_files.append(filename)
            else:
                logger.warning(f"  No data to save for {filename}")
        except Exception as e:
            logger.error(f"  Error processing {filename}: {e}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("BDOT10K CONSOLIDATION COMPLETE")
    logger.info(f"Saved {len(saved_files)} files to {CLEANED_BDOT10K_DIR}")
    for f in saved_files:
        logger.info(f"  - {f}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
