#!/usr/bin/env python3
"""
01_parse_pog.py - Parse POG GML files for Trójmiasto

Parses Plan Ogólny Gminy (POG) GML files for Gdańsk, Gdynia, Sopot
and outputs a unified GeoPackage with planning zones.

Input: GML files in /home/marcin/moja-dzialka/pog/{gdansk,gdynia,sopot}/
Output: /home/marcin/moja-dzialka/egib/data/processed/pog_trojmiasto.gpkg
"""

import logging
from pathlib import Path
from typing import Optional
import re

import geopandas as gpd
import pandas as pd
from lxml import etree
from shapely.geometry import Polygon, MultiPolygon
from shapely import wkt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_PATH = Path("/home/marcin/moja-dzialka")
POG_PATH = BASE_PATH / "pog"
OUTPUT_PATH = BASE_PATH / "egib" / "data" / "processed"

# POG source files
POG_FILES = {
    "gdansk": POG_PATH / "gdansk" / "pog-gdansk-proj-uzg-042025.gml",
    "gdynia": POG_PATH / "gdynia" / "POG_Gdynia_projekt_uzg_032025_podpisany.gml",
    "sopot": POG_PATH / "sopot" / "POG_SOPOT_12092025.gml",
}

# XML Namespaces
NAMESPACES = {
    'wfs': 'http://www.opengis.net/wfs/2.0',
    'app': 'https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0',
    'gml': 'http://www.opengis.net/gml/3.2',
    'xlink': 'http://www.w3.org/1999/xlink',
}

# Symbol descriptions (Polish planning zone types)
SYMBOL_DESCRIPTIONS = {
    'SW': 'strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną',
    'SJ': 'strefa wielofunkcyjna z zabudową mieszkaniową jednorodzinną',
    'SN': 'strefa zieleni i rekreacji',
    'SU': 'strefa usługowa',
    'SK': 'strefa komunikacyjna',
    'SH': 'strefa handlowa',
    'SC': 'strefa centralna',
    'SO': 'strefa otwarta',
    'SP': 'strefa produkcyjna',
    'SR': 'strefa rolnicza',
    'SI': 'strefa infrastruktury technicznej',
    'SZ': 'strefa zabudowy zagrodowej',
}


def parse_gml_coordinates(pos_list_text: str) -> list:
    """Parse GML posList coordinates into list of (x, y) tuples."""
    coords = pos_list_text.strip().split()
    points = []
    for i in range(0, len(coords), 2):
        # GML format: y x (northing, easting) for EPSG:2177
        y = float(coords[i])
        x = float(coords[i + 1])
        points.append((x, y))
    return points


def parse_polygon_element(polygon_elem) -> Optional[Polygon]:
    """Parse a GML Polygon element into a Shapely Polygon."""
    try:
        exterior_ring = None
        interior_rings = []

        # Parse exterior ring
        exterior = polygon_elem.find('.//gml:exterior/gml:LinearRing/gml:posList', NAMESPACES)
        if exterior is not None and exterior.text:
            exterior_ring = parse_gml_coordinates(exterior.text)

        # Parse interior rings (holes)
        for interior in polygon_elem.findall('.//gml:interior/gml:LinearRing/gml:posList', NAMESPACES):
            if interior.text:
                interior_rings.append(parse_gml_coordinates(interior.text))

        if exterior_ring:
            if interior_rings:
                return Polygon(exterior_ring, interior_rings)
            return Polygon(exterior_ring)

    except Exception as e:
        logger.warning(f"Failed to parse polygon: {e}")

    return None


def parse_geometry(geom_elem) -> Optional[Polygon | MultiPolygon]:
    """Parse GML geometry element (Polygon or MultiPolygon)."""
    if geom_elem is None:
        return None

    # Try single Polygon
    polygon = geom_elem.find('.//gml:Polygon', NAMESPACES)
    if polygon is not None:
        return parse_polygon_element(polygon)

    # Try MultiPolygon (Surface with patches)
    polygons = geom_elem.findall('.//gml:Polygon', NAMESPACES)
    if len(polygons) > 1:
        parsed = [parse_polygon_element(p) for p in polygons]
        valid = [p for p in parsed if p is not None]
        if valid:
            return MultiPolygon(valid) if len(valid) > 1 else valid[0]

    return None


def extract_xlink_title(element) -> Optional[str]:
    """Extract xlink:title attribute from element."""
    if element is not None:
        return element.get('{http://www.w3.org/1999/xlink}title')
    return None


def extract_profile_code(href: str) -> Optional[str]:
    """Extract profile code from xlink:href (e.g., KPT-MPZP-MN -> MN)."""
    if href:
        match = re.search(r'KPT-MPZP-(\w+)', href)
        if match:
            return match.group(1)
    return None


def parse_strefa_planistyczna(zone_elem, gmina: str) -> Optional[dict]:
    """Parse a single StrefaPlanistyczna element."""
    try:
        # ID
        lokalny_id = zone_elem.find('.//app:lokalnyId', NAMESPACES)
        zone_id = lokalny_id.text if lokalny_id is not None else None

        # Basic attributes
        oznaczenie = zone_elem.find('app:oznaczenie', NAMESPACES)
        symbol = zone_elem.find('app:symbol', NAMESPACES)
        nazwa = zone_elem.find('app:nazwa', NAMESPACES)

        # Geometry
        geom_elem = zone_elem.find('app:geometria', NAMESPACES)
        geometry = parse_geometry(geom_elem)

        if geometry is None:
            logger.warning(f"No geometry for zone {zone_id}")
            return None

        # Planning parameters
        maks_intensywnosc = zone_elem.find('app:maksNadziemnaIntensywnoscZabudowy', NAMESPACES)
        maks_zabudowa = zone_elem.find('app:maksUdzialPowierzchniZabudowy', NAMESPACES)
        maks_wysokosc = zone_elem.find('app:maksWysokoscZabudowy', NAMESPACES)
        min_bio = zone_elem.find('app:minUdzialPowierzchniBiologicznieCzynnej', NAMESPACES)

        # Profiles (multiple elements)
        profile_podstawowe = []
        profile_podstawowe_kody = []
        for prof in zone_elem.findall('app:profilPodstawowy', NAMESPACES):
            title = extract_xlink_title(prof)
            if title:
                profile_podstawowe.append(title)
            href = prof.get('{http://www.w3.org/1999/xlink}href', '')
            code = extract_profile_code(href)
            if code:
                profile_podstawowe_kody.append(code)

        profile_dodatkowe = []
        profile_dodatkowe_kody = []
        for prof in zone_elem.findall('app:profilDodatkowy', NAMESPACES):
            title = extract_xlink_title(prof)
            if title:
                profile_dodatkowe.append(title)
            href = prof.get('{http://www.w3.org/1999/xlink}href', '')
            code = extract_profile_code(href)
            if code:
                profile_dodatkowe_kody.append(code)

        return {
            'id': zone_id,
            'gmina': gmina,
            'oznaczenie': oznaczenie.text if oznaczenie is not None else None,
            'symbol': symbol.text if symbol is not None else None,
            'nazwa': extract_xlink_title(nazwa),
            'profil_podstawowy': profile_podstawowe_kody,  # List of codes
            'profil_podstawowy_nazwy': profile_podstawowe,  # List of names
            'profil_dodatkowy': profile_dodatkowe_kody,
            'profil_dodatkowy_nazwy': profile_dodatkowe,
            'maks_intensywnosc': float(maks_intensywnosc.text) if maks_intensywnosc is not None and maks_intensywnosc.text else None,
            'maks_zabudowa_pct': float(maks_zabudowa.text) if maks_zabudowa is not None and maks_zabudowa.text else None,
            'maks_wysokosc_m': float(maks_wysokosc.text) if maks_wysokosc is not None and maks_wysokosc.text else None,
            'min_bio_pct': float(min_bio.text) if min_bio is not None and min_bio.text else None,
            'geometry': geometry,
        }

    except Exception as e:
        logger.error(f"Failed to parse zone: {e}")
        return None


def parse_pog_file(filepath: Path, gmina: str) -> list[dict]:
    """Parse a POG GML file and return list of zone dictionaries."""
    logger.info(f"Parsing POG for {gmina}: {filepath}")

    zones = []

    # Parse XML
    tree = etree.parse(str(filepath))
    root = tree.getroot()

    # Find all StrefaPlanistyczna elements
    strefa_elements = root.findall('.//app:StrefaPlanistyczna', NAMESPACES)
    logger.info(f"Found {len(strefa_elements)} StrefaPlanistyczna elements")

    for elem in strefa_elements:
        zone = parse_strefa_planistyczna(elem, gmina)
        if zone:
            zones.append(zone)

    logger.info(f"Successfully parsed {len(zones)} zones for {gmina}")
    return zones


def create_geodataframe(zones: list[dict]) -> gpd.GeoDataFrame:
    """Create GeoDataFrame from parsed zones."""
    df = pd.DataFrame(zones)

    # Convert list columns to pipe-separated strings for GeoPackage compatibility
    df['profil_podstawowy'] = df['profil_podstawowy'].apply(lambda x: '|'.join(x) if x else None)
    df['profil_podstawowy_nazwy'] = df['profil_podstawowy_nazwy'].apply(lambda x: '|'.join(x) if x else None)
    df['profil_dodatkowy'] = df['profil_dodatkowy'].apply(lambda x: '|'.join(x) if x else None)
    df['profil_dodatkowy_nazwy'] = df['profil_dodatkowy_nazwy'].apply(lambda x: '|'.join(x) if x else None)

    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:2177')
    return gdf


def analyze_pog_data(gdf: gpd.GeoDataFrame) -> None:
    """Print analysis of POG data."""
    logger.info("\n" + "="*60)
    logger.info("POG DATA ANALYSIS")
    logger.info("="*60)

    logger.info(f"\nTotal zones: {len(gdf)}")

    logger.info(f"\nZones by gmina:")
    for gmina, count in gdf['gmina'].value_counts().items():
        logger.info(f"  {gmina}: {count}")

    logger.info(f"\nZones by symbol:")
    for symbol, count in gdf['symbol'].value_counts().head(15).items():
        desc = SYMBOL_DESCRIPTIONS.get(symbol, '?')
        logger.info(f"  {symbol}: {count} ({desc})")

    logger.info(f"\nParameter statistics:")
    for col in ['maks_intensywnosc', 'maks_zabudowa_pct', 'maks_wysokosc_m', 'min_bio_pct']:
        stats = gdf[col].describe()
        non_null = gdf[col].notna().sum()
        logger.info(f"  {col}: min={stats['min']:.1f}, max={stats['max']:.1f}, mean={stats['mean']:.1f}, non-null={non_null}")

    # Profile analysis
    all_profiles = []
    for profiles in gdf['profil_podstawowy'].dropna():
        all_profiles.extend(profiles.split('|'))
    profile_counts = pd.Series(all_profiles).value_counts()

    logger.info(f"\nTop basic profiles (profil_podstawowy):")
    for profile, count in profile_counts.head(10).items():
        logger.info(f"  {profile}: {count}")

    logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    logger.info("Starting POG parsing pipeline")

    # Ensure output directory exists
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Parse all POG files
    all_zones = []
    for gmina, filepath in POG_FILES.items():
        if not filepath.exists():
            logger.error(f"POG file not found: {filepath}")
            continue
        zones = parse_pog_file(filepath, gmina)
        all_zones.extend(zones)

    if not all_zones:
        logger.error("No zones parsed!")
        return

    # Create GeoDataFrame
    gdf = create_geodataframe(all_zones)

    # Analyze data
    analyze_pog_data(gdf)

    # Save to GeoPackage
    output_file = OUTPUT_PATH / "pog_trojmiasto.gpkg"
    gdf.to_file(output_file, driver='GPKG', layer='strefy_planistyczne')
    logger.info(f"Saved {len(gdf)} zones to {output_file}")

    # Also save a summary CSV for quick inspection
    summary_file = OUTPUT_PATH / "pog_trojmiasto_summary.csv"
    gdf.drop(columns=['geometry']).to_csv(summary_file, index=False)
    logger.info(f"Saved summary to {summary_file}")

    logger.info("POG parsing complete!")


if __name__ == "__main__":
    main()
