#!/usr/bin/env python3
"""
03b_clip_bdot10k.py - Clip BDOT10k layers to Trójmiasto region

Extracts relevant BDOT10k layers for the Trójmiasto bounding box.
This allows us to analyze data coverage before feature engineering.

Output files in: egib/data/bdot10k_trojmiasto/
"""

import logging
from pathlib import Path

import geopandas as gpd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_PATH = Path("/home/marcin/moja-dzialka")
BDOT10K_PATH = BASE_PATH / "bdot10k"
OUTPUT_PATH = BASE_PATH / "egib" / "data" / "bdot10k_trojmiasto"

# Layers to extract
LAYERS = {
    'lasy': ('PL.PZGiK.336.BDOT10k.22_OT_PTLZ_A.gpkg', None, None),
    'wody': ('PL.PZGiK.336.BDOT10k.22_OT_PTWP_A.gpkg', None, None),
    'szkoly': ('PL.PZGiK.336.BDOT10k.22_OT_KUOS_A.gpkg', 'RODZAJ', ['szkoła lub zespół szkół', 'przedszkole']),
    'przystanki': ('PL.PZGiK.336.BDOT10k.22_OT_OIKM_P.gpkg', 'RODZAJ', ['przystanek autobusowy lub tramwajowy', 'stacja lub przystanek kolejowy']),
    'drogi_glowne': ('PL.PZGiK.336.BDOT10k.22_OT_SKDR_L.gpkg', 'KLASADROGI', ['autostrada', 'droga ekspresowa', 'droga główna ruchu przyśpieszonego', 'droga główna']),
    'drogi_wszystkie': ('PL.PZGiK.336.BDOT10k.22_OT_SKDR_L.gpkg', None, None),
    'przemysl': ('PL.PZGiK.336.BDOT10k.22_OT_KUPG_A.gpkg', None, None),
    'budynki': ('PL.PZGiK.336.BDOT10k.22_OT_BUBD_A.gpkg', None, None),
}


def main():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Get bbox from parcels
    parcels = gpd.read_file(BASE_PATH / "egib/data/processed/parcels_trojmiasto.gpkg")
    bounds = parcels.total_bounds
    bbox = (bounds[0] - 1000, bounds[1] - 1000, bounds[2] + 1000, bounds[3] + 1000)
    logger.info(f"Bounding box: {bbox[0]:.0f}, {bbox[1]:.0f}, {bbox[2]:.0f}, {bbox[3]:.0f}")

    results = []

    for name, (filename, filter_col, filter_values) in LAYERS.items():
        logger.info(f"\nProcessing {name}...")

        filepath = BDOT10K_PATH / filename
        gdf = gpd.read_file(filepath, bbox=bbox)

        original_count = len(gdf)

        if filter_col and filter_values:
            gdf = gdf[gdf[filter_col].isin(filter_values)]

        filtered_count = len(gdf)

        # Save
        output_file = OUTPUT_PATH / f"{name}.gpkg"
        gdf.to_file(output_file, driver='GPKG')

        results.append({
            'name': name,
            'original': original_count,
            'filtered': filtered_count,
            'file': output_file.name
        })

        logger.info(f"  {original_count} → {filtered_count} features → {output_file.name}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("BDOT10k TRÓJMIASTO SUMMARY")
    logger.info("="*60)
    for r in results:
        if r['original'] != r['filtered']:
            logger.info(f"  {r['name']}: {r['filtered']:,} (z {r['original']:,})")
        else:
            logger.info(f"  {r['name']}: {r['filtered']:,}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
