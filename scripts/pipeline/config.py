"""
Configuration for moja-dzialka data pipeline.

Contains paths, CRS settings, thresholds, and layer mappings.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Base paths
PROJECT_ROOT = Path("/root/moja-dzialka")
DATA_ROOT = PROJECT_ROOT / "data"

# Data directories
RAW_DATA_DIR = DATA_ROOT / "raw"
CLEANED_DATA_DIR = DATA_ROOT / "cleaned" / "v1.0.0"
PROCESSED_DATA_DIR = DATA_ROOT / "processed" / "v1.0.0"
DEV_DATA_DIR = DATA_ROOT / "dev"
REPORTS_DIR = DATA_ROOT / "reports"

# Raw data files
RAW_PARCELS_FILE = RAW_DATA_DIR / "dzialki_pomorskie.gpkg"
RAW_BDOT10K_DIR = RAW_DATA_DIR / "bdot10k"
RAW_MPZP_FILE = RAW_DATA_DIR / "mpzp_pomorskie_coverage.gpkg"

# Cleaned output files
CLEANED_PARCELS_FILE = CLEANED_DATA_DIR / "parcels_cleaned.gpkg"
CLEANED_BDOT10K_DIR = CLEANED_DATA_DIR / "bdot10k"
CLEANED_MPZP_FILE = CLEANED_DATA_DIR / "mpzp_cleaned.gpkg"

# Processed output files
PARCEL_FEATURES_FILE = PROCESSED_DATA_DIR / "parcel_features.parquet"
PARCEL_FEATURES_GPKG = PROCESSED_DATA_DIR / "parcel_features.gpkg"

# Reports
VALIDATION_REPORT_FILE = REPORTS_DIR / "validation_report.json"

# =============================================================================
# CRS CONFIGURATION
# =============================================================================

# EPSG:2180 - PUWG 1992 (Poland national CRS)
TARGET_CRS = "EPSG:2180"
WGS84_CRS = "EPSG:4326"

# =============================================================================
# BDOT10K LAYER CONFIGURATION
# =============================================================================

# Layer name patterns in BDOT10k files
BDOT10K_LAYERS = {
    # Administrative units
    "ADJA_A": "PL.PZGiK.336.BDOT10k.22_OT_ADJA_A.gpkg",  # Administrative units (powiaty, gminy)
    "ADMS_A": "PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg",  # Localities (miejscowosci)
    "ADMS_P": "PL.PZGiK.336.BDOT10k.22_OT_ADMS_P.gpkg",  # Locality points

    # Buildings
    "BUBD_A": "PL.PZGiK.336.BDOT10k.22_OT_BUBD_A.gpkg",  # Buildings (all types)

    # Land cover / use
    "PTLZ_A": "PL.PZGiK.336.BDOT10k.22_OT_PTLZ_A.gpkg",  # Forests
    "PTWP_A": "PL.PZGiK.336.BDOT10k.22_OT_PTWP_A.gpkg",  # Surface waters
    "PTWZ_A": "PL.PZGiK.336.BDOT10k.22_OT_PTWZ_A.gpkg",  # Water-related areas
    "PTZB_A": "PL.PZGiK.336.BDOT10k.22_OT_PTZB_A.gpkg",  # Built-up areas
    "PTUT_A": "PL.PZGiK.336.BDOT10k.22_OT_PTUT_A.gpkg",  # Hardened surfaces
    "PTTR_A": "PL.PZGiK.336.BDOT10k.22_OT_PTTR_A.gpkg",  # Grass/meadows
    "PTGN_A": "PL.PZGiK.336.BDOT10k.22_OT_PTGN_A.gpkg",  # Agricultural land
    "PTKM_A": "PL.PZGiK.336.BDOT10k.22_OT_PTKM_A.gpkg",  # Shrubs
    "PTSO_A": "PL.PZGiK.336.BDOT10k.22_OT_PTSO_A.gpkg",  # Orchards
    "PTPL_A": "PL.PZGiK.336.BDOT10k.22_OT_PTPL_A.gpkg",  # Beaches/sandy areas
    "PTRK_A": "PL.PZGiK.336.BDOT10k.22_OT_PTRK_A.gpkg",  # Heathlands
    "PTNZ_A": "PL.PZGiK.336.BDOT10k.22_OT_PTNZ_A.gpkg",  # Other vegetation

    # Roads
    "SKDR_L": "PL.PZGiK.336.BDOT10k.22_OT_SKDR_L.gpkg",  # Roads (lines)
    "SKJZ_L": "PL.PZGiK.336.BDOT10k.22_OT_SKJZ_L.gpkg",  # Road lanes
    "SKPP_L": "PL.PZGiK.336.BDOT10k.22_OT_SKPP_L.gpkg",  # Ferry routes
    "SKRP_L": "PL.PZGiK.336.BDOT10k.22_OT_SKRP_L.gpkg",  # Road junctions
    "SKRW_L": "PL.PZGiK.336.BDOT10k.22_OT_SKRW_L.gpkg",  # Road roundabouts

    # Railways
    "SKTR_L": "PL.PZGiK.336.BDOT10k.22_OT_SKTR_L.gpkg",  # Railway lines

    # Public transport
    "OIKM_P": "PL.PZGiK.336.BDOT10k.22_OT_OIKM_P.gpkg",  # Bus stops (points)
    "OIKM_A": "PL.PZGiK.336.BDOT10k.22_OT_OIKM_A.gpkg",  # Transport areas
    "OIKM_L": "PL.PZGiK.336.BDOT10k.22_OT_OIKM_L.gpkg",  # Transport lines

    # Industrial/commercial areas
    "KUPG_A": "PL.PZGiK.336.BDOT10k.22_OT_KUPG_A.gpkg",  # Industrial areas
    "KUSK_A": "PL.PZGiK.336.BDOT10k.22_OT_KUSK_A.gpkg",  # Commercial areas
    "KUZA_A": "PL.PZGiK.336.BDOT10k.22_OT_KUZA_A.gpkg",  # Agricultural complexes

    # Protected areas
    "TCON_A": "PL.PZGiK.336.BDOT10k.22_OT_TCON_A.gpkg",  # Natura 2000
    "TCPK_A": "PL.PZGiK.336.BDOT10k.22_OT_TCPK_A.gpkg",  # National parks
    "TCRZ_A": "PL.PZGiK.336.BDOT10k.22_OT_TCRZ_A.gpkg",  # Nature reserves
    "TCPZ_A": "PL.PZGiK.336.BDOT10k.22_OT_TCPZ_A.gpkg",  # Landscape parks
}

# Building function codes (X_KOD in BUBD_A) - selected important ones
BUILDING_FUNCTIONS = {
    # Residential
    "mieszkalne": ["1110", "1121", "1122"],  # Single-family, multi-family

    # Commercial
    "handel": ["1230"],  # Retail, shops

    # Education
    "edukacja": ["1263"],  # Schools, kindergartens
    "przedszkola": ["1263"],
    "szkoly": ["1263"],

    # Healthcare
    "szpitale": ["1264"],  # Hospitals
    "przychodnie": ["1264"],  # Clinics

    # Industrial
    "przemyslowe": ["1251", "1252"],  # Industrial, warehouses

    # Religious
    "sakralne": ["1272"],  # Churches, chapels

    # Sports/recreation
    "sportowe": ["1265"],  # Sports facilities
}

# Road class codes (klasa in SKJZ_L)
ROAD_CLASSES = {
    "autostrada": "A",
    "ekspresowa": "S",
    "glowna": "GP",
    "zbiorcza": "G",
    "lokalna": "L",
    "dojazdowa": "D",
    "inna": "I",
}

# =============================================================================
# MPZP SYMBOL MAPPING
# =============================================================================

# Standard MPZP symbols and their meanings
MPZP_SYMBOLS = {
    # Residential
    "MN": "mieszkaniowa_jednorodzinna",
    "MW": "mieszkaniowa_wielorodzinna",
    "MN/U": "mieszkaniowo_uslugowa",
    "MU": "mieszkaniowo_uslugowa",

    # Services
    "U": "uslugowa",
    "UC": "uslugowa_centra_handlowe",
    "UO": "uslugowa_oswiata",
    "UZ": "uslugowa_zdrowie",
    "US": "uslugowa_sport",
    "UK": "uslugowa_kultura",

    # Industrial
    "P": "przemyslowa",
    "PU": "przemyslowo_uslugowa",

    # Agricultural
    "R": "rolna",
    "RU": "rolna_z_zabudowa",
    "RM": "rolna_siedliskowa",

    # Green areas
    "ZL": "lesna",
    "ZP": "zieleni_urzadzonej",
    "ZN": "zieleni_naturalnej",
    "ZC": "cmentarze",

    # Communication/transport
    "KD": "komunikacja_drogi",
    "KDG": "komunikacja_drogi_glowne",
    "KDD": "komunikacja_drogi_dojazdowe",
    "KK": "komunikacja_kolejowa",
    "KP": "komunikacja_parkowanie",

    # Water
    "WS": "wody_powierzchniowe",
    "WZ": "wody_zbiorniki",

    # Technical infrastructure
    "E": "elektroenergetyka",
    "G": "gazownictwo",
    "W": "wodociagi",
    "K": "kanalizacja",
    "IT": "infrastruktura_techniczna",
}

# Primary destination categories
MPZP_PRIMARY_CATEGORIES = {
    "mieszkaniowe": ["MN", "MW", "MN/U", "MU", "MR"],
    "uslugowe": ["U", "UC", "UO", "UZ", "US", "UK"],
    "przemyslowe": ["P", "PU"],
    "rolne": ["R", "RU", "RM"],
    "lesne": ["ZL", "ZN"],
    "komunikacja": ["KD", "KDG", "KDD", "KK", "KP"],
    "zieleni": ["ZP", "ZC"],
    "wodne": ["WS", "WZ"],
    "infrastruktura": ["E", "G", "W", "K", "IT"],
}

# Buildable zones
MPZP_BUILDABLE = ["MN", "MW", "MN/U", "MU", "U", "UC", "UO", "UZ", "US", "UK",
                  "P", "PU", "RU", "RM", "MR"]

# =============================================================================
# FEATURE ENGINEERING CONFIGURATION
# =============================================================================

@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    # Buffer distances (meters)
    buffer_radius: int = 500

    # Distance features to calculate
    distance_features: Dict[str, Dict] = field(default_factory=lambda: {
        "dist_to_school": {"layer": "BUBD_A", "filter": {"X_KOD": "1263"}},
        "dist_to_kindergarten": {"layer": "BUBD_A", "filter": {"X_KOD": "1263"}},
        "dist_to_shop": {"layer": "BUBD_A", "filter": {"X_KOD": "1230"}},
        "dist_to_hospital": {"layer": "BUBD_A", "filter": {"X_KOD": "1264"}},
        "dist_to_clinic": {"layer": "BUBD_A", "filter": {"X_KOD": "1264"}},
        "dist_to_bus_stop": {"layer": "OIKM_P", "filter": None},
        "dist_to_public_road": {"layer": "SKJZ_L", "filter": None},
        "dist_to_main_road": {"layer": "SKJZ_L", "filter": {"klasa": ["A", "S", "GP", "G"]}},
        "dist_to_forest": {"layer": "PTLZ_A", "filter": None},
        "dist_to_water": {"layer": "PTWP_A", "filter": None},
        "dist_to_industrial": {"layer": "KUPG_A", "filter": None},
    })

    # Buffer features to calculate
    buffer_features: List[str] = field(default_factory=lambda: [
        "pct_forest_500m",
        "pct_water_500m",
        "pct_builtup_500m",
        "pct_residential_500m",
        "count_buildings_500m",
    ])

    # Max distance cap (meters) - distances beyond this are capped
    max_distance: float = 10000.0

    # Batch size for processing (number of parcels per batch)
    batch_size: int = 10000

    # Number of workers for parallel processing
    n_workers: int = 4


FEATURE_CONFIG = FeatureConfig()

# =============================================================================
# DEVELOPMENT SAMPLE CONFIGURATION
# =============================================================================

@dataclass
class DevSampleConfig:
    """Configuration for development sample."""

    # Target number of parcels
    target_count: int = 10000

    # Municipalities to include (TERYT codes)
    target_municipalities: List[str] = field(default_factory=lambda: [
        "2261011",  # Gdansk
        "2262011",  # Sopot
        "2204052",  # Zukowo
        "2204011",  # Kartuzy
        "2206011",  # Koscierzyna
    ])

    # Municipality names for reference
    target_municipality_names: Dict[str, str] = field(default_factory=lambda: {
        "2261011": "Gdansk",
        "2262011": "Sopot",
        "2204052": "Zukowo",
        "2204011": "Kartuzy",
        "2206011": "Koscierzyna",
    })

    # Stratification settings
    area_bins: List[float] = field(default_factory=lambda: [
        0, 500, 1000, 2000, 5000, 10000, float('inf')
    ])
    area_bin_names: List[str] = field(default_factory=lambda: [
        "tiny", "small", "medium", "large", "very_large", "huge"
    ])


DEV_SAMPLE_CONFIG = DevSampleConfig()

# =============================================================================
# VALIDATION THRESHOLDS
# =============================================================================

@dataclass
class ValidationThresholds:
    """Thresholds for data validation."""

    # Minimum parcel area (m2) - parcels smaller are likely errors
    min_parcel_area: float = 10.0

    # Maximum parcel area (m2) - parcels larger might need review
    max_parcel_area: float = 10_000_000.0  # 10 km2

    # Minimum valid geometry ratio (proportion of valid geometries)
    min_valid_geometry_ratio: float = 0.95

    # Maximum NULL ratio for critical attributes
    max_null_ratio_critical: float = 0.05

    # Maximum NULL ratio for optional attributes
    max_null_ratio_optional: float = 0.30


VALIDATION_THRESHOLDS = ValidationThresholds()

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOG_LEVEL = "INFO"
LOG_FILE = PROJECT_ROOT / "logs" / "pipeline.log"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ensure_directories():
    """Create all required directories if they don't exist."""
    dirs = [
        DATA_ROOT,
        RAW_DATA_DIR,
        CLEANED_DATA_DIR,
        CLEANED_BDOT10K_DIR,
        PROCESSED_DATA_DIR,
        DEV_DATA_DIR,
        REPORTS_DIR,
        LOG_FILE.parent,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_bdot10k_path(layer_code: str) -> Optional[Path]:
    """Get the full path to a BDOT10k layer file."""
    if layer_code not in BDOT10K_LAYERS:
        return None
    return RAW_BDOT10K_DIR / BDOT10K_LAYERS[layer_code]


def list_available_bdot10k_layers() -> List[str]:
    """List all available BDOT10k layer files."""
    if not RAW_BDOT10K_DIR.exists():
        return []
    return [f.name for f in RAW_BDOT10K_DIR.glob("*.gpkg")]


if __name__ == "__main__":
    # Print configuration summary
    print("=" * 60)
    print("MOJA-DZIALKA PIPELINE CONFIGURATION")
    print("=" * 60)
    print(f"\nProject root: {PROJECT_ROOT}")
    print(f"Target CRS: {TARGET_CRS}")

    print(f"\n--- Raw Data ---")
    print(f"Parcels: {RAW_PARCELS_FILE}")
    print(f"BDOT10k: {RAW_BDOT10K_DIR}")
    print(f"MPZP: {RAW_MPZP_FILE}")

    print(f"\n--- Output ---")
    print(f"Cleaned: {CLEANED_DATA_DIR}")
    print(f"Processed: {PROCESSED_DATA_DIR}")
    print(f"Reports: {REPORTS_DIR}")

    print(f"\n--- Available BDOT10k layers ---")
    for layer in sorted(list_available_bdot10k_layers())[:10]:
        print(f"  - {layer}")
    print(f"  ... and {len(list_available_bdot10k_layers()) - 10} more")
