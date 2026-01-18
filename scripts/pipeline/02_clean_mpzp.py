#!/usr/bin/env python3
"""
02_clean_mpzp.py - MPZP Standardization Script

Cleans and standardizes MPZP (local spatial development plans) data:
1. Fix invalid geometries
2. Standardize column names (lowercase, no Polish characters)
3. Standardize MPZP symbols (MN, MW, U, R, ZL, etc.)
4. Standardize destination categories
5. Parse and standardize dates
6. Standardize statuses
7. Fill NULL values with sensible defaults
8. Validate TERYT codes

Usage:
    python scripts/pipeline/02_clean_mpzp.py

Output:
    data/cleaned/v1.0.0/mpzp_cleaned.gpkg
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely import make_valid
import warnings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RAW_MPZP_FILE,
    CLEANED_MPZP_FILE,
    TARGET_CRS,
    MPZP_SYMBOLS,
    MPZP_PRIMARY_CATEGORIES,
    MPZP_BUILDABLE,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info
from utils.io import load_geopackage, save_geopackage
from utils.geometry import make_geometries_valid

# Setup logger
logger = setup_logger(level="INFO")


# Polish character mapping for column names
POLISH_CHARS = {
    'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
    'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
    'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z',
}


def remove_polish_chars(text: str) -> str:
    """Remove Polish diacritical marks from text."""
    for pl, en in POLISH_CHARS.items():
        text = text.replace(pl, en)
    return text


def standardize_column_name(name: str) -> str:
    """Standardize column name: lowercase, no polish chars, underscores."""
    name = remove_polish_chars(name.lower())
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')
    return name


def standardize_column_names(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Standardize all column names."""
    logger.info("Standardizing column names...")

    rename_map = {}
    for col in gdf.columns:
        if col == "geometry":
            continue
        new_name = standardize_column_name(col)
        if new_name != col:
            rename_map[col] = new_name

    if rename_map:
        gdf = gdf.rename(columns=rename_map)
        logger.info(f"  Renamed {len(rename_map)} columns")
        for old, new in list(rename_map.items())[:5]:
            logger.info(f"    {old} -> {new}")

    return gdf


def extract_mpzp_symbol(value: str) -> Tuple[str, str]:
    """
    Extract and normalize MPZP symbol.

    Returns:
        Tuple of (symbol_glowny, symbol_szczegolowy)
    """
    if pd.isna(value) or not str(value).strip():
        return ("BRAK", "BRAK")

    # Clean the value
    value = str(value).upper().strip()

    # Remove common prefixes/suffixes
    value = re.sub(r'^[0-9]+\.?', '', value)  # Remove leading numbers
    value = re.sub(r'\s*\(.*\)\s*', '', value)  # Remove parentheses content
    value = value.strip()

    if not value:
        return ("BRAK", "BRAK")

    # Extract main symbol (first 1-2 letters)
    match = re.match(r'^([A-Z]{1,2})', value)
    if match:
        symbol_glowny = match.group(1)
    else:
        symbol_glowny = value[:2] if len(value) >= 2 else value

    return (symbol_glowny, value)


def standardize_mpzp_symbols(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Standardize MPZP symbols.

    Looks for columns containing 'symbol' or 'przezn' and standardizes them.
    Adds:
    - symbol_glowny (main symbol: MN, MW, U, R, ZL, etc.)
    - symbol_szczegolowy (full symbol)
    """
    logger.info("Standardizing MPZP symbols...")

    # Find symbol columns
    symbol_cols = [c for c in gdf.columns if 'symbol' in c.lower() or 'przezn' in c.lower()]
    logger.info(f"  Found symbol columns: {symbol_cols}")

    if not symbol_cols:
        # Try to find any column that might contain symbols
        for col in gdf.columns:
            if gdf[col].dtype == object:
                sample = gdf[col].dropna().head(10).astype(str)
                if any(re.match(r'^[A-Z]{1,2}', s) for s in sample):
                    symbol_cols.append(col)
                    logger.info(f"  Using {col} as symbol column (detected pattern)")
                    break

    if symbol_cols:
        primary_col = symbol_cols[0]
        logger.info(f"  Primary symbol column: {primary_col}")

        # Extract and standardize symbols
        results = gdf[primary_col].apply(extract_mpzp_symbol)
        gdf["symbol_glowny"] = results.apply(lambda x: x[0])
        gdf["symbol_szczegolowy"] = results.apply(lambda x: x[1])

        # Map to canonical symbols
        canonical_map = {}
        for symbol in MPZP_SYMBOLS.keys():
            canonical_map[symbol] = symbol
            # Add variations
            canonical_map[symbol.replace("/", "")] = symbol
            canonical_map[symbol.replace("/", "-")] = symbol

        gdf["symbol_kanoniczny"] = gdf["symbol_glowny"].map(canonical_map).fillna(gdf["symbol_glowny"])

        # Log distribution
        symbol_counts = gdf["symbol_glowny"].value_counts()
        logger.info("  Top symbols:")
        for sym, count in symbol_counts.head(10).items():
            logger.info(f"    {sym}: {count:,}")
    else:
        gdf["symbol_glowny"] = "BRAK"
        gdf["symbol_szczegolowy"] = "BRAK"
        gdf["symbol_kanoniczny"] = "BRAK"
        logger.warning("  No symbol column found")

    return gdf


def determine_primary_destination(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Determine primary destination category based on symbol.

    Adds:
    - przeznaczenie_podstawowe (mieszkaniowe/uslugowe/przemyslowe/rolne/lesne/komunikacja)
    - czy_budowlane (boolean)
    """
    logger.info("Determining primary destination...")

    def get_category(symbol):
        if pd.isna(symbol) or symbol == "BRAK":
            return "nieokreslone"

        symbol = str(symbol).upper()

        for category, symbols in MPZP_PRIMARY_CATEGORIES.items():
            if symbol in symbols or any(symbol.startswith(s) for s in symbols):
                return category

        return "inne"

    gdf["przeznaczenie_podstawowe"] = gdf["symbol_glowny"].apply(get_category)

    # Is buildable?
    gdf["czy_budowlane"] = gdf["symbol_glowny"].apply(
        lambda s: str(s).upper() in MPZP_BUILDABLE or
                  any(str(s).upper().startswith(b) for b in MPZP_BUILDABLE)
        if pd.notna(s) else False
    )

    # Log distribution
    dest_counts = gdf["przeznaczenie_podstawowe"].value_counts()
    logger.info("  Destination categories:")
    for dest, count in dest_counts.items():
        logger.info(f"    {dest}: {count:,}")

    buildable_count = gdf["czy_budowlane"].sum()
    logger.info(f"  Buildable zones: {buildable_count:,} ({buildable_count/len(gdf)*100:.1f}%)")

    return gdf


def parse_dates(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Parse and standardize date columns.

    Looks for columns containing 'data' and tries to parse them.
    """
    logger.info("Parsing dates...")

    date_cols = [c for c in gdf.columns if 'data' in c.lower()]
    logger.info(f"  Found date columns: {date_cols}")

    for col in date_cols:
        try:
            # Try to parse dates
            parsed = pd.to_datetime(gdf[col], errors='coerce', format='mixed')
            valid_count = parsed.notna().sum()
            logger.info(f"  {col}: {valid_count:,} valid dates")

            # Store as date string in ISO format
            gdf[col] = parsed.dt.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"  Could not parse {col}: {e}")

    return gdf


def standardize_statuses(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Standardize status column.

    Maps various status values to canonical forms:
    - obowiazujacy
    - w_trakcie
    - uchylony
    - zmieniony
    """
    logger.info("Standardizing statuses...")

    status_cols = [c for c in gdf.columns if 'status' in c.lower() or 'stan' in c.lower()]

    if not status_cols:
        gdf["status"] = "nieokreslony"
        logger.warning("  No status column found")
        return gdf

    status_col = status_cols[0]
    logger.info(f"  Using status column: {status_col}")

    # Status mapping
    status_map = {
        # Obowiązujący
        'obowiązujący': 'obowiazujacy',
        'obowiazujacy': 'obowiazujacy',
        'aktualny': 'obowiazujacy',
        'aktywny': 'obowiazujacy',
        'obowiązuje': 'obowiazujacy',
        'obowiazuje': 'obowiazujacy',

        # W trakcie
        'w trakcie': 'w_trakcie',
        'w_trakcie': 'w_trakcie',
        'procedowany': 'w_trakcie',
        'w opracowaniu': 'w_trakcie',
        'projekt': 'w_trakcie',

        # Uchylony
        'uchylony': 'uchylony',
        'nieobowiązujący': 'uchylony',
        'nieobowiazujacy': 'uchylony',
        'nieaktualny': 'uchylony',

        # Zmieniony
        'zmieniony': 'zmieniony',
        'zmieniany': 'zmieniony',
        'zmiana': 'zmieniony',
    }

    def map_status(value):
        if pd.isna(value):
            return "nieokreslony"
        value_lower = str(value).lower().strip()
        return status_map.get(value_lower, "nieokreslony")

    gdf["status"] = gdf[status_col].apply(map_status)

    # Log distribution
    status_counts = gdf["status"].value_counts()
    logger.info("  Status distribution:")
    for status, count in status_counts.items():
        logger.info(f"    {status}: {count:,}")

    return gdf


def fill_null_values(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fill NULL values with sensible defaults."""
    logger.info("Filling NULL values...")

    defaults = {
        "symbol_glowny": "BRAK",
        "symbol_szczegolowy": "BRAK",
        "symbol_kanoniczny": "BRAK",
        "przeznaczenie_podstawowe": "nieokreslone",
        "status": "nieokreslony",
    }

    for col, default in defaults.items():
        if col in gdf.columns:
            null_count = gdf[col].isna().sum()
            if null_count > 0:
                gdf[col] = gdf[col].fillna(default)
                logger.info(f"  {col}: filled {null_count:,} NULLs with '{default}'")

    return gdf


def validate_teryt(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Validate TERYT codes."""
    logger.info("Validating TERYT codes...")

    teryt_cols = [c for c in gdf.columns if 'teryt' in c.lower()]

    if not teryt_cols:
        logger.warning("  No TERYT column found")
        return gdf

    teryt_col = teryt_cols[0]

    # Check format (should be 7 digits for gmina)
    def validate_teryt_code(value):
        if pd.isna(value):
            return False
        value_str = str(value).strip()
        # TERYT for gmina: 7 digits
        if re.match(r'^\d{7}$', value_str):
            return True
        # Some might have different format
        if re.match(r'^\d{6,8}$', value_str):
            return True
        return False

    gdf["teryt_valid"] = gdf[teryt_col].apply(validate_teryt_code)

    valid_count = gdf["teryt_valid"].sum()
    invalid_count = len(gdf) - valid_count
    logger.info(f"  Valid TERYT: {valid_count:,}, Invalid: {invalid_count:,}")

    if invalid_count > 0:
        invalid_samples = gdf[~gdf["teryt_valid"]][teryt_col].head(5).tolist()
        logger.warning(f"  Sample invalid TERYTs: {invalid_samples}")

    return gdf


def add_area_column(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add area column in hectares."""
    gdf["area_ha"] = gdf.geometry.area / 10000
    return gdf


def main():
    """Main cleaning function."""
    logger.info("=" * 60)
    logger.info("MPZP STANDARDIZATION")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Load raw MPZP
    logger.info(f"\nLoading MPZP from {RAW_MPZP_FILE}...")
    gdf = load_geopackage(RAW_MPZP_FILE, logger=logger)
    log_dataframe_info(gdf, "Raw MPZP", logger)

    original_count = len(gdf)

    # Step 1: Fix geometries
    logger.info("\n--- Step 1: Fix Geometries ---")
    invalid_before = (~gdf.geometry.is_valid).sum()
    logger.info(f"  Invalid geometries: {invalid_before:,}")

    gdf = make_geometries_valid(gdf, logger=logger)

    invalid_after = (~gdf.geometry.is_valid).sum()
    logger.info(f"  After fixing: {invalid_after:,}")

    # Remove empty geometries
    empty_count = gdf.geometry.is_empty.sum()
    if empty_count > 0:
        logger.info(f"  Removing {empty_count:,} empty geometries...")
        gdf = gdf[~gdf.geometry.is_empty].copy()

    # Step 2: Standardize column names
    logger.info("\n--- Step 2: Standardize Column Names ---")
    logger.info(f"  Original columns: {list(gdf.columns)}")
    gdf = standardize_column_names(gdf)
    logger.info(f"  New columns: {list(gdf.columns)}")

    # Step 3: Standardize MPZP symbols
    logger.info("\n--- Step 3: Standardize MPZP Symbols ---")
    gdf = standardize_mpzp_symbols(gdf)

    # Step 4: Determine primary destination
    logger.info("\n--- Step 4: Determine Primary Destination ---")
    gdf = determine_primary_destination(gdf)

    # Step 5: Parse dates
    logger.info("\n--- Step 5: Parse Dates ---")
    gdf = parse_dates(gdf)

    # Step 6: Standardize statuses
    logger.info("\n--- Step 6: Standardize Statuses ---")
    gdf = standardize_statuses(gdf)

    # Step 7: Fill NULL values
    logger.info("\n--- Step 7: Fill NULL Values ---")
    gdf = fill_null_values(gdf)

    # Step 8: Validate TERYT
    logger.info("\n--- Step 8: Validate TERYT ---")
    gdf = validate_teryt(gdf)

    # Step 9: Add area
    logger.info("\n--- Step 9: Add Area ---")
    gdf = add_area_column(gdf)
    logger.info(f"  Total area: {gdf['area_ha'].sum():,.1f} ha")

    # Final summary
    logger.info("\n--- Final Summary ---")
    log_dataframe_info(gdf, "Cleaned MPZP", logger)

    retention_rate = len(gdf) / original_count * 100
    logger.info(f"Retention rate: {retention_rate:.1f}%")

    # Save
    logger.info(f"\nSaving to {CLEANED_MPZP_FILE}...")
    save_geopackage(gdf, CLEANED_MPZP_FILE, logger=logger)

    logger.info("=" * 60)
    logger.info("MPZP STANDARDIZATION COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
