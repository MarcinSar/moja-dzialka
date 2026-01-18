#!/usr/bin/env python3
"""
01_validate.py - Data Validation Script

Validates input data files (parcels, BDOT10k, MPZP) and generates a validation report.

Usage:
    python scripts/pipeline/01_validate.py

Output:
    data/reports/validation_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

import geopandas as gpd
import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RAW_PARCELS_FILE,
    RAW_BDOT10K_DIR,
    RAW_MPZP_FILE,
    REPORTS_DIR,
    VALIDATION_REPORT_FILE,
    TARGET_CRS,
    BDOT10K_LAYERS,
    VALIDATION_THRESHOLDS,
    ensure_directories,
)
from utils.logging import setup_logger, log_dataframe_info
from utils.io import load_geopackage, count_records, get_crs, list_layers


# Setup logger
logger = setup_logger(level="INFO")


def validate_crs(filepath: Path, expected_crs: str = TARGET_CRS) -> Dict[str, Any]:
    """Validate that the file has the expected CRS."""
    try:
        actual_crs = get_crs(filepath)
        # Normalize CRS comparison
        is_valid = expected_crs.lower().replace(":", "") in actual_crs.lower().replace(":", "")

        return {
            "valid": is_valid,
            "expected": expected_crs,
            "actual": actual_crs,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
        }


def validate_parcels() -> Dict[str, Any]:
    """Validate parcels dataset."""
    logger.info("=" * 60)
    logger.info("VALIDATING PARCELS")
    logger.info("=" * 60)

    result = {
        "file": str(RAW_PARCELS_FILE),
        "exists": RAW_PARCELS_FILE.exists(),
        "timestamp": datetime.now().isoformat(),
    }

    if not result["exists"]:
        logger.error(f"Parcels file not found: {RAW_PARCELS_FILE}")
        return result

    # File size
    result["file_size_mb"] = RAW_PARCELS_FILE.stat().st_size / 1024 / 1024
    logger.info(f"File size: {result['file_size_mb']:.1f} MB")

    # Record count
    result["record_count"] = count_records(RAW_PARCELS_FILE)
    logger.info(f"Record count: {result['record_count']:,}")

    # CRS validation
    result["crs"] = validate_crs(RAW_PARCELS_FILE)
    if result["crs"]["valid"]:
        logger.info(f"CRS: {result['crs']['actual']} [OK]")
    else:
        logger.warning(f"CRS mismatch: expected {TARGET_CRS}, got {result['crs'].get('actual', 'unknown')}")

    # Load sample for detailed validation
    logger.info("Loading sample for detailed validation...")
    gdf = load_geopackage(RAW_PARCELS_FILE)

    # Geometry validation
    logger.info("Validating geometries...")
    result["geometry"] = {
        "total": len(gdf),
        "valid": int(gdf.geometry.is_valid.sum()),
        "invalid": int((~gdf.geometry.is_valid).sum()),
        "empty": int(gdf.geometry.is_empty.sum()),
        "null": int(gdf.geometry.isna().sum()),
    }
    result["geometry"]["valid_ratio"] = result["geometry"]["valid"] / result["geometry"]["total"]

    logger.info(f"  Valid geometries: {result['geometry']['valid']:,} ({result['geometry']['valid_ratio']:.1%})")
    logger.info(f"  Invalid geometries: {result['geometry']['invalid']:,}")
    logger.info(f"  Empty geometries: {result['geometry']['empty']:,}")

    # Geometry types
    geom_types = gdf.geometry.geom_type.value_counts().to_dict()
    result["geometry"]["types"] = {str(k): int(v) for k, v in geom_types.items()}
    logger.info(f"  Geometry types: {result['geometry']['types']}")

    # Area statistics
    logger.info("Calculating area statistics...")
    areas = gdf.geometry.area
    result["area_stats"] = {
        "min": float(areas.min()),
        "max": float(areas.max()),
        "mean": float(areas.mean()),
        "median": float(areas.median()),
        "std": float(areas.std()),
    }
    logger.info(f"  Area min: {result['area_stats']['min']:.1f} m²")
    logger.info(f"  Area max: {result['area_stats']['max']:.1f} m²")
    logger.info(f"  Area mean: {result['area_stats']['mean']:.1f} m²")
    logger.info(f"  Area median: {result['area_stats']['median']:.1f} m²")

    # Attribute analysis
    logger.info("Analyzing attributes...")
    result["attributes"] = {
        "columns": list(gdf.columns),
        "null_counts": {},
        "null_ratios": {},
    }

    for col in gdf.columns:
        if col != "geometry":
            null_count = int(gdf[col].isna().sum())
            null_ratio = null_count / len(gdf)
            result["attributes"]["null_counts"][col] = null_count
            result["attributes"]["null_ratios"][col] = float(null_ratio)

            if null_ratio > 0.1:
                logger.warning(f"  {col}: {null_count:,} NULLs ({null_ratio:.1%})")

    # Check for ID column
    id_cols = [c for c in gdf.columns if "id" in c.lower() or c.lower() == "fid"]
    result["attributes"]["potential_id_columns"] = id_cols
    logger.info(f"  Potential ID columns: {id_cols}")

    # Bounds
    result["bounds"] = {
        "minx": float(gdf.total_bounds[0]),
        "miny": float(gdf.total_bounds[1]),
        "maxx": float(gdf.total_bounds[2]),
        "maxy": float(gdf.total_bounds[3]),
    }
    logger.info(f"  Bounds: {result['bounds']}")

    # Validation summary
    result["validation_passed"] = (
        result["crs"]["valid"] and
        result["geometry"]["valid_ratio"] >= VALIDATION_THRESHOLDS.min_valid_geometry_ratio
    )

    logger.info(f"Validation {'PASSED' if result['validation_passed'] else 'FAILED'}")

    return result


def validate_bdot10k() -> Dict[str, Any]:
    """Validate BDOT10k datasets."""
    logger.info("=" * 60)
    logger.info("VALIDATING BDOT10K")
    logger.info("=" * 60)

    result = {
        "directory": str(RAW_BDOT10K_DIR),
        "exists": RAW_BDOT10K_DIR.exists(),
        "timestamp": datetime.now().isoformat(),
        "layers": {},
    }

    if not result["exists"]:
        logger.error(f"BDOT10k directory not found: {RAW_BDOT10K_DIR}")
        return result

    # Find all gpkg files
    gpkg_files = list(RAW_BDOT10K_DIR.glob("*.gpkg"))
    result["total_files"] = len(gpkg_files)
    logger.info(f"Found {result['total_files']} GeoPackage files")

    # Calculate total size
    total_size = sum(f.stat().st_size for f in gpkg_files)
    result["total_size_mb"] = total_size / 1024 / 1024
    logger.info(f"Total size: {result['total_size_mb']:.1f} MB")

    # Check critical layers
    critical_layers = [
        "BUBD_A",  # Buildings
        "SKDR_L",  # Roads
        "SKJZ_L",  # Road lanes
        "PTLZ_A",  # Forests
        "PTWP_A",  # Waters
        "OIKM_P",  # Bus stops
        "ADJA_A",  # Administrative units
        "ADMS_A",  # Localities
    ]

    result["critical_layers_status"] = {}
    for layer_code in critical_layers:
        if layer_code in BDOT10K_LAYERS:
            layer_file = RAW_BDOT10K_DIR / BDOT10K_LAYERS[layer_code]
            exists = layer_file.exists()
            result["critical_layers_status"][layer_code] = {
                "exists": exists,
                "file": BDOT10K_LAYERS[layer_code],
            }

            if exists:
                try:
                    count = count_records(layer_file)
                    result["critical_layers_status"][layer_code]["record_count"] = count
                    logger.info(f"  {layer_code}: {count:,} records [OK]")
                except Exception as e:
                    result["critical_layers_status"][layer_code]["error"] = str(e)
                    logger.warning(f"  {layer_code}: Error - {e}")
            else:
                logger.warning(f"  {layer_code}: NOT FOUND")

    # Validate each file
    logger.info("\nValidating all layers...")
    for gpkg_file in sorted(gpkg_files):
        layer_name = gpkg_file.stem.split(".")[-1]  # Extract layer code

        try:
            crs_result = validate_crs(gpkg_file)
            record_count = count_records(gpkg_file)

            result["layers"][layer_name] = {
                "file": gpkg_file.name,
                "record_count": record_count,
                "crs_valid": crs_result["valid"],
                "size_mb": gpkg_file.stat().st_size / 1024 / 1024,
            }
        except Exception as e:
            result["layers"][layer_name] = {
                "file": gpkg_file.name,
                "error": str(e),
            }

    # Summary
    total_records = sum(
        layer.get("record_count", 0)
        for layer in result["layers"].values()
    )
    result["total_records"] = total_records
    logger.info(f"\nTotal records across all layers: {total_records:,}")

    # Check for missing critical layers
    missing_critical = [
        layer for layer, status in result["critical_layers_status"].items()
        if not status.get("exists", False)
    ]
    result["missing_critical_layers"] = missing_critical
    result["validation_passed"] = len(missing_critical) == 0

    if missing_critical:
        logger.warning(f"Missing critical layers: {missing_critical}")

    logger.info(f"Validation {'PASSED' if result['validation_passed'] else 'FAILED'}")

    return result


def validate_mpzp() -> Dict[str, Any]:
    """Validate MPZP dataset."""
    logger.info("=" * 60)
    logger.info("VALIDATING MPZP")
    logger.info("=" * 60)

    result = {
        "file": str(RAW_MPZP_FILE),
        "exists": RAW_MPZP_FILE.exists(),
        "timestamp": datetime.now().isoformat(),
    }

    if not result["exists"]:
        logger.error(f"MPZP file not found: {RAW_MPZP_FILE}")
        return result

    # File size
    result["file_size_mb"] = RAW_MPZP_FILE.stat().st_size / 1024 / 1024
    logger.info(f"File size: {result['file_size_mb']:.1f} MB")

    # Record count
    result["record_count"] = count_records(RAW_MPZP_FILE)
    logger.info(f"Record count: {result['record_count']:,}")

    # CRS validation
    result["crs"] = validate_crs(RAW_MPZP_FILE)
    if result["crs"]["valid"]:
        logger.info(f"CRS: {result['crs']['actual']} [OK]")
    else:
        logger.warning(f"CRS mismatch: expected {TARGET_CRS}, got {result['crs'].get('actual', 'unknown')}")

    # Load for detailed validation
    logger.info("Loading for detailed validation...")
    gdf = load_geopackage(RAW_MPZP_FILE)

    # Geometry validation
    logger.info("Validating geometries...")
    result["geometry"] = {
        "total": len(gdf),
        "valid": int(gdf.geometry.is_valid.sum()),
        "invalid": int((~gdf.geometry.is_valid).sum()),
        "empty": int(gdf.geometry.is_empty.sum()),
    }
    result["geometry"]["valid_ratio"] = result["geometry"]["valid"] / result["geometry"]["total"]
    logger.info(f"  Valid geometries: {result['geometry']['valid']:,} ({result['geometry']['valid_ratio']:.1%})")

    # Geometry types
    geom_types = gdf.geometry.geom_type.value_counts().to_dict()
    result["geometry"]["types"] = {str(k): int(v) for k, v in geom_types.items()}
    logger.info(f"  Geometry types: {result['geometry']['types']}")

    # Coverage statistics
    total_area = gdf.geometry.area.sum()
    result["coverage"] = {
        "total_area_km2": float(total_area / 1_000_000),
        "plan_count": len(gdf),
    }
    logger.info(f"  Total coverage: {result['coverage']['total_area_km2']:.1f} km²")

    # Attribute analysis
    logger.info("Analyzing attributes...")
    result["attributes"] = {
        "columns": list(gdf.columns),
        "null_counts": {},
    }

    # Check key columns
    key_columns = ["teryt", "status", "symbol", "nazwa", "data_uchwalenia"]
    for col in key_columns:
        matching_cols = [c for c in gdf.columns if col.lower() in c.lower()]
        if matching_cols:
            for match in matching_cols:
                null_count = int(gdf[match].isna().sum())
                null_ratio = null_count / len(gdf)
                result["attributes"]["null_counts"][match] = {
                    "count": null_count,
                    "ratio": float(null_ratio),
                }
                logger.info(f"  {match}: {null_count:,} NULLs ({null_ratio:.1%})")

    # Unique TERYTs (municipalities)
    teryt_cols = [c for c in gdf.columns if "teryt" in c.lower()]
    if teryt_cols:
        teryt_col = teryt_cols[0]
        unique_teryts = gdf[teryt_col].dropna().unique()
        result["coverage"]["unique_teryts"] = len(unique_teryts)
        logger.info(f"  Unique TERYT codes: {result['coverage']['unique_teryts']}")

    # Symbol/przeznaczenie analysis
    symbol_cols = [c for c in gdf.columns if "symbol" in c.lower() or "przezn" in c.lower()]
    if symbol_cols:
        for col in symbol_cols[:2]:  # Analyze first 2
            value_counts = gdf[col].value_counts().head(10).to_dict()
            result["attributes"][f"{col}_top10"] = {str(k): int(v) for k, v in value_counts.items()}
            logger.info(f"  Top {col} values: {list(value_counts.keys())[:5]}")

    # Bounds
    result["bounds"] = {
        "minx": float(gdf.total_bounds[0]),
        "miny": float(gdf.total_bounds[1]),
        "maxx": float(gdf.total_bounds[2]),
        "maxy": float(gdf.total_bounds[3]),
    }

    # Validation summary
    result["validation_passed"] = (
        result["crs"]["valid"] and
        result["geometry"]["valid_ratio"] >= 0.9
    )

    logger.info(f"Validation {'PASSED' if result['validation_passed'] else 'FAILED'}")

    return result


def main():
    """Main validation function."""
    logger.info("=" * 60)
    logger.info("MOJA-DZIALKA DATA VALIDATION")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()

    # Run validations
    report = {
        "timestamp": datetime.now().isoformat(),
        "parcels": validate_parcels(),
        "bdot10k": validate_bdot10k(),
        "mpzp": validate_mpzp(),
    }

    # Overall status
    all_passed = all([
        report["parcels"].get("validation_passed", False),
        report["bdot10k"].get("validation_passed", False),
        report["mpzp"].get("validation_passed", False),
    ])
    report["all_validations_passed"] = all_passed

    # Save report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(VALIDATION_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("VALIDATION COMPLETE")
    logger.info(f"Report saved to: {VALIDATION_REPORT_FILE}")
    logger.info(f"Overall status: {'PASSED' if all_passed else 'FAILED'}")
    logger.info("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
