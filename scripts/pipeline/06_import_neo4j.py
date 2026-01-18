#!/usr/bin/env python3
"""
06_import_neo4j.py - Complete Knowledge Graph Import for Neo4j

This script creates a comprehensive knowledge graph utilizing ALL 36 parcel features:

NODES (14 types):
    - Dzialka: Main parcel nodes with all numeric attributes
    - Wojewodztwo, Powiat, Gmina, Miejscowosc: Administrative hierarchy
    - RodzajMiejscowosci: wieś, miasto, osada, kolonia, przysiółek, część wsi/miasta
    - CharakterTerenu: rolny, zabudowany, lesny, mieszany, wodny
    - SymbolMPZP: Planning zone symbols with buildability info
    - POIType: school, shop, hospital, bus_stop, industrial
    - LandCoverType: forest, water
    - KategoriaCiszy: bardzo_cicha, cicha, umiarkowana, glosna
    - KategoriaNatury: wysoka, dobra, srednia, niska
    - KategoriaDostepu: doskonaly, dobry, sredni, slaby
    - KategoriaPowierzchni: dzialka budowlana (<1000), standard, duza, bardzo_duza

RELATIONSHIPS (17 types):
    Administrative: W_MIEJSCOWOSCI, W_GMINIE, W_POWIECIE, W_WOJEWODZTWIE
    Locality type: JEST_TYPU (Miejscowosc -> RodzajMiejscowosci)
    Land character: MA_CHARAKTER (Dzialka -> CharakterTerenu)
    Zoning: MA_PRZEZNACZENIE (Dzialka -> SymbolMPZP)
    POI proximity: BLISKO_SZKOLY, BLISKO_SKLEPU, BLISKO_SZPITALA, BLISKO_PRZYSTANKU, BLISKO_PRZEMYSLU
    Nature proximity: BLISKO_LASU, BLISKO_WODY (with distance_m and pct_500m properties)
    Categories: MA_CISZE, MA_NATURE, MA_DOSTEP, MA_POWIERZCHNIE

This rich graph enables powerful Cypher queries for hybrid search:
    - "Find buildable parcels near forests in quiet areas"
    - "Find rural parcels with good accessibility"
    - "Find parcels similar to reference by category matches"

Usage:
    python 06_import_neo4j.py --sample    # Import dev sample (10k parcels)
    python 06_import_neo4j.py             # Import full dataset (1.3M parcels)
    python 06_import_neo4j.py --clear     # Clear existing data first

Requirements:
    - Neo4j database running (docker-compose up neo4j)
    - Data files in data/dev/ or data/processed/v1.0.0/

Environment variables (or .env file):
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=secretpassword
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import geopandas as gpd
from loguru import logger
from neo4j import GraphDatabase

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.config import (
    DEV_DATA_DIR,
    PROCESSED_DATA_DIR,
    PARCEL_FEATURES_GPKG,
    MPZP_SYMBOLS,
    MPZP_BUILDABLE,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default Neo4j connection (override via environment)
NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "secretpassword"),
}

# Batch size for imports
BATCH_SIZE = 1000

# =============================================================================
# CATEGORY DEFINITIONS (for score binning)
# =============================================================================

# Quietness score categories (0-100)
QUIETNESS_CATEGORIES = {
    "bardzo_cicha": (90, 100),   # Very quiet
    "cicha": (75, 90),           # Quiet
    "umiarkowana": (50, 75),     # Moderate
    "glosna": (0, 50),           # Noisy
}

# Nature score categories (0-100)
NATURE_CATEGORIES = {
    "wysoka": (70, 100),         # High nature
    "dobra": (50, 70),           # Good nature
    "srednia": (25, 50),         # Medium nature
    "niska": (0, 25),            # Low nature
}

# Accessibility score categories (0-100)
ACCESSIBILITY_CATEGORIES = {
    "doskonaly": (80, 100),      # Excellent access
    "dobry": (60, 80),           # Good access
    "sredni": (40, 60),          # Medium access
    "slaby": (0, 40),            # Poor access
}

# Area categories (m2)
AREA_CATEGORIES = {
    "dzialka_budowlana": (0, 1000),          # Building plot <1000m²
    "dzialka_standardowa": (1000, 3000),     # Standard plot 1000-3000m²
    "dzialka_duza": (3000, 10000),           # Large plot 3000-10000m²
    "dzialka_bardzo_duza": (10000, float('inf')),  # Very large >10000m²
}

# POI types with distance thresholds for "close" relationship (meters)
POI_PROXIMITY_THRESHOLDS = {
    "school": 2000,      # Close to school = within 2km
    "shop": 1000,        # Close to shop = within 1km
    "hospital": 5000,    # Close to hospital = within 5km
    "bus_stop": 500,     # Close to bus stop = within 500m
    "industrial": 500,   # Close to industrial = within 500m (negative)
}

# Land cover types with distance thresholds
LANDCOVER_PROXIMITY_THRESHOLDS = {
    "forest": 500,       # Close to forest = within 500m
    "water": 500,        # Close to water = within 500m
}

# Building density categories (based on count_buildings_500m)
BUILDING_DENSITY_CATEGORIES = {
    "bardzo_gesta": (300, float('inf')),   # Very dense >300 buildings
    "gesta": (150, 300),                    # Dense 150-300 buildings
    "umiarkowana": (50, 150),               # Moderate 50-150 buildings
    "rzadka": (10, 50),                     # Sparse 10-50 buildings
    "bardzo_rzadka": (0, 10),               # Very sparse <10 buildings
}

# Road access threshold (meters)
ROAD_ACCESS_THRESHOLD = 100  # Close to public road = within 100m


# =============================================================================
# NEO4J DRIVER
# =============================================================================

class Neo4jConnection:
    """Neo4j connection wrapper with batch operations."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_connectivity(self) -> bool:
        """Test connection to Neo4j."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False

    def run_query(self, query: str, parameters: dict = None):
        """Run a single Cypher query."""
        with self.driver.session() as session:
            return session.run(query, parameters or {})

    def run_batch(self, query: str, data: List[dict], batch_size: int = BATCH_SIZE):
        """Run query in batches using UNWIND."""
        total = len(data)
        for i in range(0, total, batch_size):
            batch = data[i:i + batch_size]
            with self.driver.session() as session:
                session.run(query, {"batch": batch})
            if (i + batch_size) % (batch_size * 10) == 0 or (i + batch_size) >= total:
                logger.debug(f"  Progress: {min(i + batch_size, total):,}/{total:,}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_quietness_category(score: float) -> Optional[str]:
    """Map quietness score to category."""
    if pd.isna(score):
        return None
    for cat, (low, high) in QUIETNESS_CATEGORIES.items():
        if low <= score < high or (cat == "bardzo_cicha" and score == 100):
            return cat
    return None


def get_nature_category(score: float) -> Optional[str]:
    """Map nature score to category."""
    if pd.isna(score):
        return None
    for cat, (low, high) in NATURE_CATEGORIES.items():
        if low <= score < high or (cat == "wysoka" and score == 100):
            return cat
    return None


def get_accessibility_category(score: float) -> Optional[str]:
    """Map accessibility score to category."""
    if pd.isna(score):
        return None
    for cat, (low, high) in ACCESSIBILITY_CATEGORIES.items():
        if low <= score < high or (cat == "doskonaly" and score == 100):
            return cat
    return None


def get_area_category(area_m2: float) -> Optional[str]:
    """Map area to category."""
    if pd.isna(area_m2):
        return None
    for cat, (low, high) in AREA_CATEGORIES.items():
        if low <= area_m2 < high:
            return cat
    return "dzialka_bardzo_duza"


def get_building_density_category(count: float) -> Optional[str]:
    """Map building count to density category."""
    if pd.isna(count):
        return None
    for cat, (low, high) in BUILDING_DENSITY_CATEGORIES.items():
        if low <= count < high:
            return cat
    return "bardzo_gesta"


# =============================================================================
# SCHEMA CREATION
# =============================================================================

def create_constraints(conn: Neo4jConnection):
    """Create uniqueness constraints and indexes for all node types."""
    logger.info("Creating constraints and indexes...")

    constraints = [
        # === UNIQUE CONSTRAINTS ===
        # Main entities
        "CREATE CONSTRAINT dzialka_id IF NOT EXISTS FOR (d:Dzialka) REQUIRE d.id_dzialki IS UNIQUE",

        # Administrative hierarchy
        "CREATE CONSTRAINT wojewodztwo_name IF NOT EXISTS FOR (w:Wojewodztwo) REQUIRE w.name IS UNIQUE",
        "CREATE CONSTRAINT powiat_name IF NOT EXISTS FOR (p:Powiat) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT gmina_name IF NOT EXISTS FOR (g:Gmina) REQUIRE g.name IS UNIQUE",
        "CREATE CONSTRAINT miejscowosc_id IF NOT EXISTS FOR (m:Miejscowosc) REQUIRE m.id IS UNIQUE",

        # Category nodes
        "CREATE CONSTRAINT rodzaj_miejscowosci_name IF NOT EXISTS FOR (r:RodzajMiejscowosci) REQUIRE r.name IS UNIQUE",
        "CREATE CONSTRAINT charakter_terenu_name IF NOT EXISTS FOR (c:CharakterTerenu) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT mpzp_symbol IF NOT EXISTS FOR (s:SymbolMPZP) REQUIRE s.kod IS UNIQUE",
        "CREATE CONSTRAINT poi_type IF NOT EXISTS FOR (p:POIType) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT landcover_type IF NOT EXISTS FOR (l:LandCoverType) REQUIRE l.name IS UNIQUE",

        # Score categories
        "CREATE CONSTRAINT kat_ciszy_name IF NOT EXISTS FOR (k:KategoriaCiszy) REQUIRE k.name IS UNIQUE",
        "CREATE CONSTRAINT kat_natury_name IF NOT EXISTS FOR (k:KategoriaNatury) REQUIRE k.name IS UNIQUE",
        "CREATE CONSTRAINT kat_dostepu_name IF NOT EXISTS FOR (k:KategoriaDostepu) REQUIRE k.name IS UNIQUE",
        "CREATE CONSTRAINT kat_powierzchni_name IF NOT EXISTS FOR (k:KategoriaPowierzchni) REQUIRE k.name IS UNIQUE",
        "CREATE CONSTRAINT gestosc_zabudowy_name IF NOT EXISTS FOR (g:GestoscZabudowy) REQUIRE g.name IS UNIQUE",

        # === PERFORMANCE INDEXES ===
        # Dzialka properties for filtering
        "CREATE INDEX dzialka_gmina IF NOT EXISTS FOR (d:Dzialka) ON (d.gmina)",
        "CREATE INDEX dzialka_area IF NOT EXISTS FOR (d:Dzialka) ON (d.area_m2)",
        "CREATE INDEX dzialka_quietness IF NOT EXISTS FOR (d:Dzialka) ON (d.quietness_score)",
        "CREATE INDEX dzialka_nature IF NOT EXISTS FOR (d:Dzialka) ON (d.nature_score)",
        "CREATE INDEX dzialka_accessibility IF NOT EXISTS FOR (d:Dzialka) ON (d.accessibility_score)",
        "CREATE INDEX dzialka_has_mpzp IF NOT EXISTS FOR (d:Dzialka) ON (d.has_mpzp)",
        "CREATE INDEX dzialka_has_road IF NOT EXISTS FOR (d:Dzialka) ON (d.has_public_road_access)",

        # Composite indexes for common query patterns
        "CREATE INDEX dzialka_gmina_area IF NOT EXISTS FOR (d:Dzialka) ON (d.gmina, d.area_m2)",
        "CREATE INDEX dzialka_scores IF NOT EXISTS FOR (d:Dzialka) ON (d.quietness_score, d.nature_score)",
    ]

    for constraint in constraints:
        try:
            conn.run_query(constraint)
        except Exception as e:
            logger.debug(f"Constraint/index: {e}")

    logger.info("Constraints and indexes created")


def clear_database(conn: Neo4jConnection):
    """Clear all data from Neo4j."""
    logger.info("Clearing existing data...")

    # Node types to delete (in dependency order)
    node_types = [
        "Dzialka",
        "Miejscowosc", "Gmina", "Powiat", "Wojewodztwo",
        "RodzajMiejscowosci", "CharakterTerenu", "SymbolMPZP",
        "POIType", "LandCoverType",
        "KategoriaCiszy", "KategoriaNatury", "KategoriaDostepu", "KategoriaPowierzchni", "GestoscZabudowy",
    ]

    for node_type in node_types:
        try:
            # Use CALL { ... } IN TRANSACTIONS for large deletes
            batch_query = f"""
                CALL {{
                    MATCH (n:{node_type}) DETACH DELETE n
                }} IN TRANSACTIONS OF 10000 ROWS
            """
            conn.run_query(batch_query)
        except Exception:
            # Fallback for older Neo4j versions
            conn.run_query(f"MATCH (n:{node_type}) DETACH DELETE n")

    logger.info("Database cleared")


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(sample: bool = False) -> gpd.GeoDataFrame:
    """Load parcel data from file."""
    if sample:
        filepath = DEV_DATA_DIR / "parcels_dev.gpkg"
        logger.info(f"Loading DEV sample from {filepath}")
    else:
        filepath = PARCEL_FEATURES_GPKG
        logger.info(f"Loading FULL dataset from {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    gdf = gpd.read_file(filepath)
    logger.info(f"Loaded {len(gdf):,} parcels with {len(gdf.columns)} columns")

    return gdf


# =============================================================================
# NODE CREATION - REFERENCE DATA (Static nodes)
# =============================================================================

def create_reference_nodes(conn: Neo4jConnection):
    """Create all static reference nodes."""
    logger.info("Creating reference nodes...")

    # === RodzajMiejscowosci ===
    rodzaje = ["wieś", "miasto", "osada", "część wsi", "kolonia", "przysiółek", "część miasta"]
    for rodzaj in rodzaje:
        conn.run_query(
            "MERGE (r:RodzajMiejscowosci {name: $name})",
            {"name": rodzaj}
        )
    logger.info(f"  Created {len(rodzaje)} RodzajMiejscowosci nodes")

    # === CharakterTerenu ===
    charaktery = ["rolny", "zabudowany", "lesny", "mieszany", "wodny"]
    for charakter in charaktery:
        conn.run_query(
            "MERGE (c:CharakterTerenu {name: $name})",
            {"name": charakter}
        )
    logger.info(f"  Created {len(charaktery)} CharakterTerenu nodes")

    # === POIType ===
    poi_types = [
        ("school", "Szkoła", "Placówki edukacyjne"),
        ("shop", "Sklep", "Sklepy i usługi handlowe"),
        ("hospital", "Szpital/Przychodnia", "Placówki medyczne"),
        ("bus_stop", "Przystanek", "Przystanki komunikacji publicznej"),
        ("industrial", "Strefa przemysłowa", "Tereny przemysłowe"),
    ]
    for name, nazwa_pl, opis in poi_types:
        conn.run_query(
            "MERGE (p:POIType {name: $name}) SET p.nazwa_pl = $nazwa_pl, p.opis = $opis",
            {"name": name, "nazwa_pl": nazwa_pl, "opis": opis}
        )
    logger.info(f"  Created {len(poi_types)} POIType nodes")

    # === LandCoverType ===
    landcover_types = [
        ("forest", "Las", "Tereny leśne"),
        ("water", "Woda", "Zbiorniki wodne i cieki"),
    ]
    for name, nazwa_pl, opis in landcover_types:
        conn.run_query(
            "MERGE (l:LandCoverType {name: $name}) SET l.nazwa_pl = $nazwa_pl, l.opis = $opis",
            {"name": name, "nazwa_pl": nazwa_pl, "opis": opis}
        )
    logger.info(f"  Created {len(landcover_types)} LandCoverType nodes")

    # === KategoriaCiszy ===
    for name, (low, high) in QUIETNESS_CATEGORIES.items():
        nazwa_pl = {
            "bardzo_cicha": "Bardzo cicha okolica",
            "cicha": "Cicha okolica",
            "umiarkowana": "Umiarkowanie cicha",
            "glosna": "Głośna okolica",
        }[name]
        conn.run_query(
            """MERGE (k:KategoriaCiszy {name: $name})
               SET k.nazwa_pl = $nazwa_pl, k.min_score = $low, k.max_score = $high""",
            {"name": name, "nazwa_pl": nazwa_pl, "low": low, "high": high}
        )
    logger.info(f"  Created {len(QUIETNESS_CATEGORIES)} KategoriaCiszy nodes")

    # === KategoriaNatury ===
    for name, (low, high) in NATURE_CATEGORIES.items():
        nazwa_pl = {
            "wysoka": "Wysoka bliskość natury",
            "dobra": "Dobra bliskość natury",
            "srednia": "Średnia bliskość natury",
            "niska": "Niska bliskość natury",
        }[name]
        conn.run_query(
            """MERGE (k:KategoriaNatury {name: $name})
               SET k.nazwa_pl = $nazwa_pl, k.min_score = $low, k.max_score = $high""",
            {"name": name, "nazwa_pl": nazwa_pl, "low": low, "high": high}
        )
    logger.info(f"  Created {len(NATURE_CATEGORIES)} KategoriaNatury nodes")

    # === KategoriaDostepu ===
    for name, (low, high) in ACCESSIBILITY_CATEGORIES.items():
        nazwa_pl = {
            "doskonaly": "Doskonała dostępność",
            "dobry": "Dobra dostępność",
            "sredni": "Średnia dostępność",
            "slaby": "Słaba dostępność",
        }[name]
        conn.run_query(
            """MERGE (k:KategoriaDostepu {name: $name})
               SET k.nazwa_pl = $nazwa_pl, k.min_score = $low, k.max_score = $high""",
            {"name": name, "nazwa_pl": nazwa_pl, "low": low, "high": high}
        )
    logger.info(f"  Created {len(ACCESSIBILITY_CATEGORIES)} KategoriaDostepu nodes")

    # === KategoriaPowierzchni ===
    for name, (low, high) in AREA_CATEGORIES.items():
        nazwa_pl = {
            "dzialka_budowlana": "Działka budowlana (<1000 m²)",
            "dzialka_standardowa": "Działka standardowa (1000-3000 m²)",
            "dzialka_duza": "Działka duża (3000-10000 m²)",
            "dzialka_bardzo_duza": "Działka bardzo duża (>10000 m²)",
        }[name]
        conn.run_query(
            """MERGE (k:KategoriaPowierzchni {name: $name})
               SET k.nazwa_pl = $nazwa_pl, k.min_m2 = $low, k.max_m2 = $high""",
            {"name": name, "nazwa_pl": nazwa_pl, "low": low, "high": high if high != float('inf') else 999999999}
        )
    logger.info(f"  Created {len(AREA_CATEGORIES)} KategoriaPowierzchni nodes")

    # === GestoscZabudowy ===
    for name, (low, high) in BUILDING_DENSITY_CATEGORIES.items():
        nazwa_pl = {
            "bardzo_gesta": "Bardzo gęsta zabudowa (>300 budynków/500m)",
            "gesta": "Gęsta zabudowa (150-300 budynków/500m)",
            "umiarkowana": "Umiarkowana zabudowa (50-150 budynków/500m)",
            "rzadka": "Rzadka zabudowa (10-50 budynków/500m)",
            "bardzo_rzadka": "Bardzo rzadka zabudowa (<10 budynków/500m)",
        }[name]
        conn.run_query(
            """MERGE (g:GestoscZabudowy {name: $name})
               SET g.nazwa_pl = $nazwa_pl, g.min_count = $low, g.max_count = $high""",
            {"name": name, "nazwa_pl": nazwa_pl, "low": low, "high": high if high != float('inf') else 999999}
        )
    logger.info(f"  Created {len(BUILDING_DENSITY_CATEGORIES)} GestoscZabudowy nodes")

    # === SymbolMPZP === (created dynamically from data, not from config)


# =============================================================================
# NODE CREATION - ADMINISTRATIVE HIERARCHY
# =============================================================================

def create_administrative_hierarchy(conn: Neo4jConnection, df: pd.DataFrame):
    """Create administrative hierarchy nodes with relationships."""
    logger.info("Creating administrative hierarchy...")

    # === Wojewodztwo ===
    wojewodztwa = df["wojewodztwo"].dropna().unique()
    for woj in wojewodztwa:
        conn.run_query(
            "MERGE (w:Wojewodztwo {name: $name})",
            {"name": woj}
        )
    logger.info(f"  Created {len(wojewodztwa)} Wojewodztwo nodes")

    # === Powiaty ===
    powiaty = df[["powiat", "wojewodztwo"]].drop_duplicates().dropna()
    for _, row in powiaty.iterrows():
        conn.run_query(
            """
            MATCH (w:Wojewodztwo {name: $woj})
            MERGE (p:Powiat {name: $powiat})
            MERGE (p)-[:W_WOJEWODZTWIE]->(w)
            """,
            {"powiat": row["powiat"], "woj": row["wojewodztwo"]}
        )
    logger.info(f"  Created {len(powiaty)} Powiat nodes")

    # === Gminy ===
    gminy = df[["gmina", "powiat"]].drop_duplicates().dropna()
    for _, row in gminy.iterrows():
        conn.run_query(
            """
            MATCH (p:Powiat {name: $powiat})
            MERGE (g:Gmina {name: $gmina})
            MERGE (g)-[:W_POWIECIE]->(p)
            """,
            {"gmina": row["gmina"], "powiat": row["powiat"]}
        )
    logger.info(f"  Created {len(gminy)} Gmina nodes")

    # === Miejscowosci with RodzajMiejscowosci relationship ===
    miejscowosci = df[["miejscowosc", "gmina", "rodzaj_miejscowosci"]].drop_duplicates()
    miejscowosci = miejscowosci[miejscowosci["miejscowosc"].notna()]

    miejscowosc_data = []
    for _, row in miejscowosci.iterrows():
        miejscowosc_data.append({
            "id": f"{row['miejscowosc']}_{row['gmina']}",
            "name": row["miejscowosc"],
            "gmina": row["gmina"],
            "rodzaj": row.get("rodzaj_miejscowosci") if pd.notna(row.get("rodzaj_miejscowosci")) else None,
        })

    if miejscowosc_data:
        # Create miejscowosc nodes with W_GMINIE relationship
        conn.run_batch(
            """
            UNWIND $batch AS m
            MATCH (g:Gmina {name: m.gmina})
            MERGE (msc:Miejscowosc {id: m.id})
            SET msc.name = m.name
            MERGE (msc)-[:W_GMINIE]->(g)
            """,
            miejscowosc_data
        )

        # Create JEST_TYPU relationship to RodzajMiejscowosci
        miejscowosc_with_rodzaj = [m for m in miejscowosc_data if m["rodzaj"]]
        if miejscowosc_with_rodzaj:
            conn.run_batch(
                """
                UNWIND $batch AS m
                MATCH (msc:Miejscowosc {id: m.id})
                MATCH (r:RodzajMiejscowosci {name: m.rodzaj})
                MERGE (msc)-[:JEST_TYPU]->(r)
                """,
                miejscowosc_with_rodzaj
            )

    logger.info(f"  Created {len(miejscowosc_data)} Miejscowosc nodes")


def create_mpzp_nodes_from_data(conn: Neo4jConnection, df: pd.DataFrame):
    """Create MPZP symbol nodes from actual data (not predefined config)."""
    logger.info("Creating MPZP symbols from data...")

    # Get unique symbols from data
    symbols = df['mpzp_symbol'].dropna().unique()

    for symbol in symbols:
        # Check if symbol is in our predefined list
        if symbol in MPZP_SYMBOLS:
            nazwa = MPZP_SYMBOLS[symbol]
            is_buildable = symbol in MPZP_BUILDABLE
        else:
            # Unknown symbol - use generic name
            nazwa = f"Symbol {symbol}"
            # Guess buildability based on common patterns
            is_buildable = symbol not in ['BRAK', 'R', 'RL', 'RZ', 'ZL', 'ZP', 'W', 'WS']

        conn.run_query(
            """MERGE (s:SymbolMPZP {kod: $kod})
               SET s.nazwa = $nazwa, s.budowlany = $buildable""",
            {"kod": symbol, "nazwa": nazwa, "buildable": is_buildable}
        )

    logger.info(f"  Created {len(symbols)} SymbolMPZP nodes from data")


# =============================================================================
# NODE CREATION - PARCEL NODES
# =============================================================================

def create_parcel_nodes(conn: Neo4jConnection, df: pd.DataFrame):
    """Create Dzialka nodes with ALL attributes."""
    logger.info(f"Creating {len(df):,} parcel nodes with all attributes...")

    start_time = time.time()

    # Prepare parcel data with ALL 36 columns
    parcel_data = []
    for _, row in df.iterrows():
        parcel = {
            # Identifiers
            "id_dzialki": row["ID_DZIALKI"],
            "teryt_powiat": row.get("TERYT_POWIAT"),

            # Location (for reference, not geometry)
            "gmina": row.get("gmina"),
            "miejscowosc": row.get("miejscowosc"),
            "centroid_lat": float(row["centroid_lat"]) if pd.notna(row.get("centroid_lat")) else None,
            "centroid_lon": float(row["centroid_lon"]) if pd.notna(row.get("centroid_lon")) else None,

            # Area and shape
            "area_m2": float(row["area_m2"]) if pd.notna(row.get("area_m2")) else None,
            "compactness": float(row["compactness"]) if pd.notna(row.get("compactness")) else None,

            # Land cover ratios (from parcel polygon intersection)
            "forest_ratio": float(row["forest_ratio"]) if pd.notna(row.get("forest_ratio")) else None,
            "water_ratio": float(row["water_ratio"]) if pd.notna(row.get("water_ratio")) else None,
            "builtup_ratio": float(row["builtup_ratio"]) if pd.notna(row.get("builtup_ratio")) else None,

            # Terrain character
            "charakter_terenu": row.get("charakter_terenu") if pd.notna(row.get("charakter_terenu")) else None,

            # POI distances (in meters)
            "dist_to_school": float(row["dist_to_school"]) if pd.notna(row.get("dist_to_school")) else None,
            "dist_to_shop": float(row["dist_to_shop"]) if pd.notna(row.get("dist_to_shop")) else None,
            "dist_to_hospital": float(row["dist_to_hospital"]) if pd.notna(row.get("dist_to_hospital")) else None,
            "dist_to_bus_stop": float(row["dist_to_bus_stop"]) if pd.notna(row.get("dist_to_bus_stop")) else None,
            "dist_to_industrial": float(row["dist_to_industrial"]) if pd.notna(row.get("dist_to_industrial")) else None,

            # Road distances
            "dist_to_public_road": float(row["dist_to_public_road"]) if pd.notna(row.get("dist_to_public_road")) else None,
            "dist_to_main_road": float(row["dist_to_main_road"]) if pd.notna(row.get("dist_to_main_road")) else None,

            # Nature distances
            "dist_to_forest": float(row["dist_to_forest"]) if pd.notna(row.get("dist_to_forest")) else None,
            "dist_to_water": float(row["dist_to_water"]) if pd.notna(row.get("dist_to_water")) else None,

            # Buffer statistics (500m radius)
            "pct_forest_500m": float(row["pct_forest_500m"]) if pd.notna(row.get("pct_forest_500m")) else None,
            "pct_water_500m": float(row["pct_water_500m"]) if pd.notna(row.get("pct_water_500m")) else None,
            "count_buildings_500m": int(row["count_buildings_500m"]) if pd.notna(row.get("count_buildings_500m")) else None,

            # MPZP (planning zones)
            "has_mpzp": bool(row["has_mpzp"]) if pd.notna(row.get("has_mpzp")) else False,
            "mpzp_symbol": row.get("mpzp_symbol") if pd.notna(row.get("mpzp_symbol")) else None,
            "mpzp_przeznaczenie": row.get("mpzp_przeznaczenie") if pd.notna(row.get("mpzp_przeznaczenie")) else None,
            "mpzp_czy_budowlane": str(row.get("mpzp_czy_budowlane")) == "1" if pd.notna(row.get("mpzp_czy_budowlane")) else None,

            # Composite scores (0-100)
            "quietness_score": float(row["quietness_score"]) if pd.notna(row.get("quietness_score")) else None,
            "nature_score": float(row["nature_score"]) if pd.notna(row.get("nature_score")) else None,
            "accessibility_score": float(row["accessibility_score"]) if pd.notna(row.get("accessibility_score")) else None,

            # Road access
            "has_public_road_access": bool(row["has_public_road_access"]) if pd.notna(row.get("has_public_road_access")) else None,

            # Categories (computed)
            "kat_ciszy": get_quietness_category(row.get("quietness_score")),
            "kat_natury": get_nature_category(row.get("nature_score")),
            "kat_dostepu": get_accessibility_category(row.get("accessibility_score")),
            "kat_powierzchni": get_area_category(row.get("area_m2")),
            "kat_zabudowy": get_building_density_category(row.get("count_buildings_500m")),
        }
        parcel_data.append(parcel)

    # Batch insert parcels
    conn.run_batch(
        """
        UNWIND $batch AS p
        CREATE (d:Dzialka {
            id_dzialki: p.id_dzialki,
            teryt_powiat: p.teryt_powiat,
            gmina: p.gmina,
            miejscowosc: p.miejscowosc,
            centroid_lat: p.centroid_lat,
            centroid_lon: p.centroid_lon,
            area_m2: p.area_m2,
            compactness: p.compactness,
            forest_ratio: p.forest_ratio,
            water_ratio: p.water_ratio,
            builtup_ratio: p.builtup_ratio,
            charakter_terenu: p.charakter_terenu,
            dist_to_school: p.dist_to_school,
            dist_to_shop: p.dist_to_shop,
            dist_to_hospital: p.dist_to_hospital,
            dist_to_bus_stop: p.dist_to_bus_stop,
            dist_to_industrial: p.dist_to_industrial,
            dist_to_public_road: p.dist_to_public_road,
            dist_to_main_road: p.dist_to_main_road,
            dist_to_forest: p.dist_to_forest,
            dist_to_water: p.dist_to_water,
            pct_forest_500m: p.pct_forest_500m,
            pct_water_500m: p.pct_water_500m,
            count_buildings_500m: p.count_buildings_500m,
            has_mpzp: p.has_mpzp,
            mpzp_symbol: p.mpzp_symbol,
            mpzp_przeznaczenie: p.mpzp_przeznaczenie,
            mpzp_czy_budowlane: p.mpzp_czy_budowlane,
            quietness_score: p.quietness_score,
            nature_score: p.nature_score,
            accessibility_score: p.accessibility_score,
            has_public_road_access: p.has_public_road_access
        })
        """,
        parcel_data,
        batch_size=BATCH_SIZE
    )

    elapsed = time.time() - start_time
    logger.info(f"  Created {len(df):,} parcel nodes in {elapsed:.1f}s")

    return parcel_data  # Return for relationship creation


# =============================================================================
# RELATIONSHIP CREATION
# =============================================================================

def create_parcel_relationships(conn: Neo4jConnection, df: pd.DataFrame, parcel_data: List[dict]):
    """Create ALL relationships between parcels and reference nodes."""
    logger.info("Creating parcel relationships...")

    start_time = time.time()

    # === Administrative relationships ===

    # Dzialka -> Miejscowosc
    logger.info("  Creating Dzialka -> Miejscowosc relationships...")
    miejscowosc_rels = [
        {"id_dzialki": p["id_dzialki"], "miejscowosc_id": f"{p['miejscowosc']}_{p['gmina']}"}
        for p in parcel_data if p["miejscowosc"] and p["gmina"]
    ]
    if miejscowosc_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (m:Miejscowosc {id: r.miejscowosc_id})
            MERGE (d)-[:W_MIEJSCOWOSCI]->(m)
            """,
            miejscowosc_rels
        )
    logger.info(f"    -> {len(miejscowosc_rels):,} W_MIEJSCOWOSCI")

    # Dzialka -> Gmina (direct relationship for fast queries)
    logger.info("  Creating Dzialka -> Gmina relationships...")
    gmina_rels = [
        {"id_dzialki": p["id_dzialki"], "gmina": p["gmina"]}
        for p in parcel_data if p["gmina"]
    ]
    if gmina_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (g:Gmina {name: r.gmina})
            MERGE (d)-[:W_GMINIE]->(g)
            """,
            gmina_rels
        )
    logger.info(f"    -> {len(gmina_rels):,} W_GMINIE")

    # === CharakterTerenu relationship ===
    logger.info("  Creating Dzialka -> CharakterTerenu relationships...")
    charakter_rels = [
        {"id_dzialki": p["id_dzialki"], "charakter": p["charakter_terenu"]}
        for p in parcel_data if p["charakter_terenu"]
    ]
    if charakter_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (c:CharakterTerenu {name: r.charakter})
            MERGE (d)-[:MA_CHARAKTER]->(c)
            """,
            charakter_rels
        )
    logger.info(f"    -> {len(charakter_rels):,} MA_CHARAKTER")

    # === MPZP relationship ===
    logger.info("  Creating Dzialka -> SymbolMPZP relationships...")
    mpzp_rels = [
        {"id_dzialki": p["id_dzialki"], "symbol": p["mpzp_symbol"]}
        for p in parcel_data if p["mpzp_symbol"]
    ]
    if mpzp_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (s:SymbolMPZP {kod: r.symbol})
            MERGE (d)-[:MA_PRZEZNACZENIE]->(s)
            """,
            mpzp_rels
        )
    logger.info(f"    -> {len(mpzp_rels):,} MA_PRZEZNACZENIE")

    # === POI proximity relationships ===
    poi_mappings = [
        ("dist_to_school", "school", "BLISKO_SZKOLY", POI_PROXIMITY_THRESHOLDS["school"]),
        ("dist_to_shop", "shop", "BLISKO_SKLEPU", POI_PROXIMITY_THRESHOLDS["shop"]),
        ("dist_to_hospital", "hospital", "BLISKO_SZPITALA", POI_PROXIMITY_THRESHOLDS["hospital"]),
        ("dist_to_bus_stop", "bus_stop", "BLISKO_PRZYSTANKU", POI_PROXIMITY_THRESHOLDS["bus_stop"]),
        ("dist_to_industrial", "industrial", "BLISKO_PRZEMYSLU", POI_PROXIMITY_THRESHOLDS["industrial"]),
    ]

    for dist_col, poi_type, rel_type, threshold in poi_mappings:
        logger.info(f"  Creating Dzialka -[:{rel_type}]-> POIType relationships...")
        poi_rels = [
            {"id_dzialki": p["id_dzialki"], "poi": poi_type, "distance_m": p[dist_col]}
            for p in parcel_data
            if p[dist_col] is not None and p[dist_col] <= threshold
        ]
        if poi_rels:
            conn.run_batch(
                f"""
                UNWIND $batch AS r
                MATCH (d:Dzialka {{id_dzialki: r.id_dzialki}})
                MATCH (p:POIType {{name: r.poi}})
                MERGE (d)-[rel:{rel_type}]->(p)
                SET rel.distance_m = r.distance_m
                """,
                poi_rels
            )
        logger.info(f"    -> {len(poi_rels):,} {rel_type}")

    # === LandCover proximity relationships ===
    logger.info("  Creating Dzialka -> LandCoverType relationships...")

    # Forest relationship (with both distance and buffer percentage)
    forest_rels = [
        {
            "id_dzialki": p["id_dzialki"],
            "distance_m": p["dist_to_forest"],
            "pct_500m": p["pct_forest_500m"]
        }
        for p in parcel_data
        if p["dist_to_forest"] is not None and p["dist_to_forest"] <= LANDCOVER_PROXIMITY_THRESHOLDS["forest"]
    ]
    if forest_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (l:LandCoverType {name: 'forest'})
            MERGE (d)-[rel:BLISKO_LASU]->(l)
            SET rel.distance_m = r.distance_m, rel.pct_500m = r.pct_500m
            """,
            forest_rels
        )
    logger.info(f"    -> {len(forest_rels):,} BLISKO_LASU")

    # Water relationship
    water_rels = [
        {
            "id_dzialki": p["id_dzialki"],
            "distance_m": p["dist_to_water"],
            "pct_500m": p["pct_water_500m"]
        }
        for p in parcel_data
        if p["dist_to_water"] is not None and p["dist_to_water"] <= LANDCOVER_PROXIMITY_THRESHOLDS["water"]
    ]
    if water_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (l:LandCoverType {name: 'water'})
            MERGE (d)-[rel:BLISKO_WODY]->(l)
            SET rel.distance_m = r.distance_m, rel.pct_500m = r.pct_500m
            """,
            water_rels
        )
    logger.info(f"    -> {len(water_rels):,} BLISKO_WODY")

    # === Score category relationships ===

    # Quietness category
    logger.info("  Creating Dzialka -> KategoriaCiszy relationships...")
    ciszy_rels = [
        {"id_dzialki": p["id_dzialki"], "kat": p["kat_ciszy"]}
        for p in parcel_data if p["kat_ciszy"]
    ]
    if ciszy_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (k:KategoriaCiszy {name: r.kat})
            MERGE (d)-[:MA_CISZE]->(k)
            """,
            ciszy_rels
        )
    logger.info(f"    -> {len(ciszy_rels):,} MA_CISZE")

    # Nature category
    logger.info("  Creating Dzialka -> KategoriaNatury relationships...")
    natury_rels = [
        {"id_dzialki": p["id_dzialki"], "kat": p["kat_natury"]}
        for p in parcel_data if p["kat_natury"]
    ]
    if natury_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (k:KategoriaNatury {name: r.kat})
            MERGE (d)-[:MA_NATURE]->(k)
            """,
            natury_rels
        )
    logger.info(f"    -> {len(natury_rels):,} MA_NATURE")

    # Accessibility category
    logger.info("  Creating Dzialka -> KategoriaDostepu relationships...")
    dostepu_rels = [
        {"id_dzialki": p["id_dzialki"], "kat": p["kat_dostepu"]}
        for p in parcel_data if p["kat_dostepu"]
    ]
    if dostepu_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (k:KategoriaDostepu {name: r.kat})
            MERGE (d)-[:MA_DOSTEP]->(k)
            """,
            dostepu_rels
        )
    logger.info(f"    -> {len(dostepu_rels):,} MA_DOSTEP")

    # Area category
    logger.info("  Creating Dzialka -> KategoriaPowierzchni relationships...")
    powierzchni_rels = [
        {"id_dzialki": p["id_dzialki"], "kat": p["kat_powierzchni"]}
        for p in parcel_data if p["kat_powierzchni"]
    ]
    if powierzchni_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (k:KategoriaPowierzchni {name: r.kat})
            MERGE (d)-[:MA_POWIERZCHNIE]->(k)
            """,
            powierzchni_rels
        )
    logger.info(f"    -> {len(powierzchni_rels):,} MA_POWIERZCHNIE")

    # Building density category
    logger.info("  Creating Dzialka -> GestoscZabudowy relationships...")
    zabudowy_rels = [
        {"id_dzialki": p["id_dzialki"], "kat": p["kat_zabudowy"]}
        for p in parcel_data if p.get("kat_zabudowy")
    ]
    if zabudowy_rels:
        conn.run_batch(
            """
            UNWIND $batch AS r
            MATCH (d:Dzialka {id_dzialki: r.id_dzialki})
            MATCH (g:GestoscZabudowy {name: r.kat})
            MERGE (d)-[:MA_ZABUDOWE]->(g)
            """,
            zabudowy_rels
        )
    logger.info(f"    -> {len(zabudowy_rels):,} MA_ZABUDOWE")

    # Road access relationship (for parcels close to public roads)
    logger.info("  Creating Dzialka road access relationships...")
    road_rels = [
        {"id_dzialki": p["id_dzialki"], "distance_m": p["dist_to_public_road"]}
        for p in parcel_data
        if p.get("dist_to_public_road") is not None and p["dist_to_public_road"] <= ROAD_ACCESS_THRESHOLD
    ]
    # We'll create a simple boolean property on parcels for now
    # since we already have has_public_road_access
    logger.info(f"    -> {len(road_rels):,} parcels within {ROAD_ACCESS_THRESHOLD}m of public road")

    elapsed = time.time() - start_time
    logger.info(f"All relationships created in {elapsed:.1f}s")


# =============================================================================
# STATISTICS
# =============================================================================

def print_statistics(conn: Neo4jConnection):
    """Print comprehensive database statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("NEO4J DATABASE STATISTICS")
    logger.info("=" * 60)

    # Node counts
    node_queries = [
        ("Dzialka", "MATCH (n:Dzialka) RETURN count(n) as count"),
        ("Wojewodztwo", "MATCH (n:Wojewodztwo) RETURN count(n) as count"),
        ("Powiat", "MATCH (n:Powiat) RETURN count(n) as count"),
        ("Gmina", "MATCH (n:Gmina) RETURN count(n) as count"),
        ("Miejscowosc", "MATCH (n:Miejscowosc) RETURN count(n) as count"),
        ("RodzajMiejscowosci", "MATCH (n:RodzajMiejscowosci) RETURN count(n) as count"),
        ("CharakterTerenu", "MATCH (n:CharakterTerenu) RETURN count(n) as count"),
        ("SymbolMPZP", "MATCH (n:SymbolMPZP) RETURN count(n) as count"),
        ("POIType", "MATCH (n:POIType) RETURN count(n) as count"),
        ("LandCoverType", "MATCH (n:LandCoverType) RETURN count(n) as count"),
        ("KategoriaCiszy", "MATCH (n:KategoriaCiszy) RETURN count(n) as count"),
        ("KategoriaNatury", "MATCH (n:KategoriaNatury) RETURN count(n) as count"),
        ("KategoriaDostepu", "MATCH (n:KategoriaDostepu) RETURN count(n) as count"),
        ("KategoriaPowierzchni", "MATCH (n:KategoriaPowierzchni) RETURN count(n) as count"),
        ("GestoscZabudowy", "MATCH (n:GestoscZabudowy) RETURN count(n) as count"),
    ]

    logger.info("\nNODE COUNTS:")
    total_nodes = 0
    for name, query in node_queries:
        with conn.driver.session() as session:
            result = session.run(query)
            count = result.single()["count"]
        total_nodes += count
        if count > 0:
            logger.info(f"  {name}: {count:,}")
    logger.info(f"  TOTAL NODES: {total_nodes:,}")

    # Relationship counts
    rel_queries = [
        ("W_WOJEWODZTWIE", "MATCH ()-[r:W_WOJEWODZTWIE]->() RETURN count(r) as count"),
        ("W_POWIECIE", "MATCH ()-[r:W_POWIECIE]->() RETURN count(r) as count"),
        ("W_GMINIE", "MATCH ()-[r:W_GMINIE]->() RETURN count(r) as count"),
        ("W_MIEJSCOWOSCI", "MATCH ()-[r:W_MIEJSCOWOSCI]->() RETURN count(r) as count"),
        ("JEST_TYPU", "MATCH ()-[r:JEST_TYPU]->() RETURN count(r) as count"),
        ("MA_CHARAKTER", "MATCH ()-[r:MA_CHARAKTER]->() RETURN count(r) as count"),
        ("MA_PRZEZNACZENIE", "MATCH ()-[r:MA_PRZEZNACZENIE]->() RETURN count(r) as count"),
        ("BLISKO_SZKOLY", "MATCH ()-[r:BLISKO_SZKOLY]->() RETURN count(r) as count"),
        ("BLISKO_SKLEPU", "MATCH ()-[r:BLISKO_SKLEPU]->() RETURN count(r) as count"),
        ("BLISKO_SZPITALA", "MATCH ()-[r:BLISKO_SZPITALA]->() RETURN count(r) as count"),
        ("BLISKO_PRZYSTANKU", "MATCH ()-[r:BLISKO_PRZYSTANKU]->() RETURN count(r) as count"),
        ("BLISKO_PRZEMYSLU", "MATCH ()-[r:BLISKO_PRZEMYSLU]->() RETURN count(r) as count"),
        ("BLISKO_LASU", "MATCH ()-[r:BLISKO_LASU]->() RETURN count(r) as count"),
        ("BLISKO_WODY", "MATCH ()-[r:BLISKO_WODY]->() RETURN count(r) as count"),
        ("MA_CISZE", "MATCH ()-[r:MA_CISZE]->() RETURN count(r) as count"),
        ("MA_NATURE", "MATCH ()-[r:MA_NATURE]->() RETURN count(r) as count"),
        ("MA_DOSTEP", "MATCH ()-[r:MA_DOSTEP]->() RETURN count(r) as count"),
        ("MA_POWIERZCHNIE", "MATCH ()-[r:MA_POWIERZCHNIE]->() RETURN count(r) as count"),
        ("MA_ZABUDOWE", "MATCH ()-[r:MA_ZABUDOWE]->() RETURN count(r) as count"),
    ]

    logger.info("\nRELATIONSHIP COUNTS:")
    total_rels = 0
    for name, query in rel_queries:
        with conn.driver.session() as session:
            result = session.run(query)
            count = result.single()["count"]
        total_rels += count
        if count > 0:
            logger.info(f"  {name}: {count:,}")
    logger.info(f"  TOTAL RELATIONSHIPS: {total_rels:,}")


def print_sample_queries(conn: Neo4jConnection):
    """Print sample Cypher queries for testing."""
    logger.info("\n" + "=" * 60)
    logger.info("SAMPLE CYPHER QUERIES")
    logger.info("=" * 60)

    queries = [
        (
            "Find quiet parcels near forest with good accessibility",
            """
MATCH (d:Dzialka)-[:MA_CISZE]->(kc:KategoriaCiszy {name: 'bardzo_cicha'})
MATCH (d)-[:BLISKO_LASU]->(forest:LandCoverType)
MATCH (d)-[:MA_DOSTEP]->(kd:KategoriaDostepu)
WHERE kd.name IN ['doskonaly', 'dobry']
RETURN d.id_dzialki, d.area_m2, d.quietness_score, d.nature_score
ORDER BY d.quietness_score DESC
LIMIT 10
"""
        ),
        (
            "Find buildable rural parcels near schools",
            """
MATCH (d:Dzialka)-[:MA_CHARAKTER]->(c:CharakterTerenu {name: 'rolny'})
MATCH (d)-[:BLISKO_SZKOLY]->(poi:POIType)
MATCH (d)-[:MA_PRZEZNACZENIE]->(mpzp:SymbolMPZP)
WHERE mpzp.budowlany = true
RETURN d.id_dzialki, d.area_m2, d.gmina, mpzp.kod, mpzp.nazwa
LIMIT 10
"""
        ),
        (
            "Count parcels by quietness category",
            """
MATCH (d:Dzialka)-[:MA_CISZE]->(k:KategoriaCiszy)
RETURN k.name as kategoria, k.nazwa_pl as opis, count(d) as liczba_dzialek
ORDER BY k.min_score DESC
"""
        ),
        (
            "Find parcels similar by category combination",
            """
// Find parcels with same category profile as reference parcel
MATCH (ref:Dzialka {id_dzialki: 'EXAMPLE_ID'})
MATCH (ref)-[:MA_CISZE]->(kc:KategoriaCiszy)
MATCH (ref)-[:MA_NATURE]->(kn:KategoriaNatury)
MATCH (ref)-[:MA_CHARAKTER]->(ct:CharakterTerenu)

MATCH (d:Dzialka)-[:MA_CISZE]->(kc)
MATCH (d)-[:MA_NATURE]->(kn)
MATCH (d)-[:MA_CHARAKTER]->(ct)
WHERE d <> ref
RETURN d.id_dzialki, d.area_m2, d.gmina
LIMIT 20
"""
        ),
    ]

    for title, query in queries:
        logger.info(f"\n--- {title} ---")
        logger.info(query.strip())


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import complete parcel Knowledge Graph to Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 06_import_neo4j.py --sample           # Dev sample (10k parcels)
    python 06_import_neo4j.py                    # Full dataset (1.3M parcels)
    python 06_import_neo4j.py --sample --clear   # Clear and reimport sample
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use dev sample (10k parcels) instead of full dataset",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but don't import (for testing)",
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
    logger.info("NEO4J COMPLETE KNOWLEDGE GRAPH IMPORT")
    logger.info("moja-dzialka")
    logger.info("=" * 60)
    logger.info(f"Graph Schema: 14 node types, 17+ relationship types")
    logger.info(f"Mode: {'DEV SAMPLE' if args.sample else 'FULL DATASET'}")

    # Create connection
    logger.info(f"\nConnecting to {NEO4J_CONFIG['uri']}")
    conn = Neo4jConnection(
        uri=NEO4J_CONFIG["uri"],
        user=NEO4J_CONFIG["user"],
        password=NEO4J_CONFIG["password"],
    )

    # Test connection
    if not conn.verify_connectivity():
        logger.error("Cannot connect to Neo4j. Is Docker running?")
        logger.info("Start with: docker compose up -d neo4j")
        sys.exit(1)

    logger.info("Connected to Neo4j")

    # Load data
    try:
        gdf = load_data(sample=args.sample)
    except FileNotFoundError as e:
        logger.error(str(e))
        conn.close()
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run - data loaded successfully, not importing")
        logger.info(f"Columns: {list(gdf.columns)}")
        conn.close()
        return

    # Clear existing data if requested
    if args.clear:
        clear_database(conn)

    # Create schema
    create_constraints(conn)

    # Import data
    start_time = time.time()

    # 1. Reference nodes (static categories)
    create_reference_nodes(conn)

    # 2. Administrative hierarchy
    create_administrative_hierarchy(conn, gdf)

    # 2b. MPZP symbols from data
    create_mpzp_nodes_from_data(conn, gdf)

    # 3. Parcel nodes with all attributes
    parcel_data = create_parcel_nodes(conn, gdf)

    # 4. All relationships
    create_parcel_relationships(conn, gdf, parcel_data)

    elapsed = time.time() - start_time
    logger.info(f"\nTotal import time: {elapsed:.1f}s")

    # Print statistics
    print_statistics(conn)

    # Print sample queries
    print_sample_queries(conn)

    conn.close()

    logger.info("\n" + "=" * 60)
    logger.info("IMPORT COMPLETE")
    logger.info("=" * 60)
    logger.info("Explore the graph at: http://localhost:7474")
    logger.info("Default credentials: neo4j / secretpassword")


if __name__ == "__main__":
    main()
