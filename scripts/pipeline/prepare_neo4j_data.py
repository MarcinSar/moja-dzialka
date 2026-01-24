#!/usr/bin/env python3
"""
prepare_neo4j_data.py - Prepare CSV files for Neo4j import

Creates CSV files for:
1. Node CSVs: Gmina, Dzielnica, StrefaPOG, ProfilFunkcji, Kategorie, Dzialka
2. Relationship CSVs: W_GMINIE, W_DZIELNICY, W_STREFIE_POG, DOZWALA, MA_*, etc.

Output: data/ready-for-import/neo4j/csv/
"""

import logging
from pathlib import Path
import geopandas as gpd
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_DIR = Path("/home/marcin/moja-dzialka")
NEO4J_DIR = PROJECT_DIR / "data" / "ready-for-import" / "neo4j"
CSV_DIR = NEO4J_DIR / "csv"


def create_output_dirs():
    """Create output directories."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    (CSV_DIR / "nodes").mkdir(exist_ok=True)
    (CSV_DIR / "relationships").mkdir(exist_ok=True)
    logger.info(f"Output directory: {CSV_DIR}")


# =============================================================================
# STATIC DATA DEFINITIONS
# =============================================================================

GMINY = [
    {"teryt": "2261", "nazwa": "Gdańsk", "wojewodztwo": "pomorskie"},
    {"teryt": "2262", "nazwa": "Gdynia", "wojewodztwo": "pomorskie"},
    {"teryt": "2263", "nazwa": "Sopot", "wojewodztwo": "pomorskie"},
]

KATEGORIE_CISZY = [
    {"poziom": "bardzo_cicha", "opis": "Daleko od ruchu i przemysłu (>2km)", "score_min": 80},
    {"poziom": "cicha", "opis": "Umiarkowana odległość od ruchu (1-2km)", "score_min": 60},
    {"poziom": "umiarkowana", "opis": "Blisko ruchu (500m-1km)", "score_min": 40},
    {"poziom": "glosna", "opis": "Bardzo blisko ruchu (<500m)", "score_min": 0},
]

KATEGORIE_NATURY = [
    {"poziom": "bardzo_zielona", "opis": "Las lub woda w zasięgu 200m", "score_min": 70},
    {"poziom": "zielona", "opis": "Las lub woda w zasięgu 500m", "score_min": 50},
    {"poziom": "umiarkowana", "opis": "Zieleń w dalszej odległości", "score_min": 30},
    {"poziom": "zurbanizowana", "opis": "Brak natury w pobliżu", "score_min": 0},
]

KATEGORIE_DOSTEPNOSCI = [
    {"poziom": "doskonala", "opis": "Szkoła i przystanek w zasięgu 500m", "score_min": 70},
    {"poziom": "dobra", "opis": "Dobra dostępność komunikacyjna", "score_min": 50},
    {"poziom": "umiarkowana", "opis": "Średnia dostępność", "score_min": 30},
    {"poziom": "ograniczona", "opis": "Słaba dostępność komunikacyjna", "score_min": 0},
]

KLASY_POWIERZCHNI = [
    {"klasa": "mala", "zakres": "<500 m²", "min_m2": 0, "max_m2": 500},
    {"klasa": "pod_dom", "zakres": "500-1500 m²", "min_m2": 500, "max_m2": 1500},
    {"klasa": "duza", "zakres": "1500-5000 m²", "min_m2": 1500, "max_m2": 5000},
    {"klasa": "bardzo_duza", "zakres": ">5000 m²", "min_m2": 5000, "max_m2": 999999},
]

# POG Symbol → Typ Zabudowy mapping
POG_SYMBOL_TO_TYP_ZABUDOWY = {
    'SJ': 'jednorodzinna',
    'SW': 'wielorodzinna',
    'SN': 'wielorodzinna',
    'SC': 'centrum',
    'SU': 'uslugowa',
    'SP': 'przemyslowa',
    'SG': 'gospodarcza',
    'SH': 'handlowa',
    'SK': 'komunikacja',
    'SI': 'infrastruktura',
    'SZ': 'zielona',
    'SO': 'ochronna',
    'SR': 'rekreacyjna',
}

TYPY_ZABUDOWY = [
    {"typ": "jednorodzinna", "opis": "Zabudowa mieszkaniowa jednorodzinna"},
    {"typ": "wielorodzinna", "opis": "Zabudowa mieszkaniowa wielorodzinna"},
    {"typ": "centrum", "opis": "Zabudowa centrum miejskiego"},
    {"typ": "uslugowa", "opis": "Zabudowa usługowa"},
    {"typ": "przemyslowa", "opis": "Zabudowa przemysłowa"},
    {"typ": "gospodarcza", "opis": "Zabudowa gospodarcza"},
    {"typ": "handlowa", "opis": "Zabudowa handlowa"},
    {"typ": "komunikacja", "opis": "Tereny komunikacji"},
    {"typ": "infrastruktura", "opis": "Tereny infrastruktury"},
    {"typ": "zielona", "opis": "Tereny zieleni"},
    {"typ": "ochronna", "opis": "Tereny ochronne"},
    {"typ": "rekreacyjna", "opis": "Tereny rekreacyjne"},
    {"typ": "brak", "opis": "Brak określonego typu zabudowy"},
]


# =============================================================================
# NODE EXPORTS
# =============================================================================

def export_gminy():
    """Export Gmina nodes."""
    df = pd.DataFrame(GMINY)
    output = CSV_DIR / "nodes" / "gmina.csv"
    df.to_csv(output, index=False)
    logger.info(f"  Gmina: {len(df)} nodes → {output.name}")
    return df


def export_dzielnice(parcels: gpd.GeoDataFrame):
    """Export Dzielnica nodes."""
    # Get unique dzielnica + gmina combinations
    dzielnice = parcels[['dzielnica', 'gmina']].drop_duplicates()
    dzielnice = dzielnice.rename(columns={'dzielnica': 'nazwa'})
    dzielnice['id'] = dzielnice['nazwa'] + '_' + dzielnice['gmina']

    output = CSV_DIR / "nodes" / "dzielnica.csv"
    dzielnice.to_csv(output, index=False)
    logger.info(f"  Dzielnica: {len(dzielnice)} nodes → {output.name}")
    return dzielnice


def export_strefy_pog(pog: gpd.GeoDataFrame):
    """Export StrefaPOG nodes."""
    # Create composite ID (gmina_oznaczenie) since oznaczenie is not unique across gminy
    pog = pog.copy()
    pog['strefa_id'] = pog['gmina'] + '_' + pog['oznaczenie']

    # Select relevant columns
    cols = ['strefa_id', 'gmina', 'oznaczenie', 'symbol', 'nazwa',
            'profil_podstawowy', 'profil_podstawowy_nazwy',
            'profil_dodatkowy', 'profil_dodatkowy_nazwy',
            'maks_intensywnosc', 'maks_zabudowa_pct',
            'maks_wysokosc_m', 'min_bio_pct']

    # Rename columns if needed (check actual names)
    pog_cols = pog.columns.tolist()
    if 'maks_wysokosc' in pog_cols and 'maks_wysokosc_m' not in pog_cols:
        pog = pog.rename(columns={'maks_wysokosc': 'maks_wysokosc_m'})

    available_cols = [c for c in cols if c in pog.columns]
    strefy = pog[available_cols].copy()

    # Rename strefa_id to id for Neo4j
    strefy = strefy.rename(columns={'strefa_id': 'id'})

    output = CSV_DIR / "nodes" / "strefa_pog.csv"
    strefy.to_csv(output, index=False)
    logger.info(f"  StrefaPOG: {len(strefy)} nodes → {output.name}")
    return strefy


def export_profile_funkcji(pog: gpd.GeoDataFrame):
    """Export ProfilFunkcji nodes from POG profiles."""
    profiles = {}

    for col in ['profil_podstawowy', 'profil_dodatkowy']:
        if col not in pog.columns:
            continue
        typ = 'podstawowy' if 'podstawowy' in col else 'dodatkowy'

        # Also get names if available
        names_col = col + '_nazwy'

        for idx, row in pog.iterrows():
            if pd.isna(row[col]):
                continue
            codes = str(row[col]).split('|')
            names = str(row.get(names_col, '')).split('|') if names_col in pog.columns else [''] * len(codes)

            for code, name in zip(codes, names):
                code = code.strip()
                name = name.strip()
                if code and code not in profiles:
                    profiles[code] = {
                        'kod': code,
                        'nazwa': name if name else code,
                    }

    df = pd.DataFrame(list(profiles.values()))
    output = CSV_DIR / "nodes" / "profil_funkcji.csv"
    df.to_csv(output, index=False)
    logger.info(f"  ProfilFunkcji: {len(df)} nodes → {output.name}")
    return df


def export_kategorie():
    """Export all category nodes."""
    # Cisza
    df = pd.DataFrame(KATEGORIE_CISZY)
    df.to_csv(CSV_DIR / "nodes" / "kategoria_ciszy.csv", index=False)
    logger.info(f"  KategoriaCiszy: {len(df)} nodes")

    # Natura
    df = pd.DataFrame(KATEGORIE_NATURY)
    df.to_csv(CSV_DIR / "nodes" / "kategoria_natury.csv", index=False)
    logger.info(f"  KategoriaNatury: {len(df)} nodes")

    # Dostępność
    df = pd.DataFrame(KATEGORIE_DOSTEPNOSCI)
    df.to_csv(CSV_DIR / "nodes" / "kategoria_dostepnosci.csv", index=False)
    logger.info(f"  KategoriaDostepnosci: {len(df)} nodes")

    # Powierzchnia
    df = pd.DataFrame(KLASY_POWIERZCHNI)
    df.to_csv(CSV_DIR / "nodes" / "klasa_powierzchni.csv", index=False)
    logger.info(f"  KlasaPowierzchni: {len(df)} nodes")

    # Typ zabudowy
    df = pd.DataFrame(TYPY_ZABUDOWY)
    df.to_csv(CSV_DIR / "nodes" / "typ_zabudowy.csv", index=False)
    logger.info(f"  TypZabudowy: {len(df)} nodes")


def export_dzialki(parcels: gpd.GeoDataFrame):
    """Export Dzialka nodes."""
    # Select columns for Neo4j (without geometry)
    cols = [
        'id_dzialki', 'area_m2', 'centroid_lat', 'centroid_lon',
        'quietness_score', 'nature_score', 'accessibility_score',
        'shape_index'
    ]
    available_cols = [c for c in cols if c in parcels.columns]
    dzialki = parcels[available_cols].copy()
    dzialki = dzialki.rename(columns={'id_dzialki': 'id'})

    output = CSV_DIR / "nodes" / "dzialka.csv"
    dzialki.to_csv(output, index=False)
    logger.info(f"  Dzialka: {len(dzialki)} nodes → {output.name}")
    return dzialki


# =============================================================================
# RELATIONSHIP EXPORTS
# =============================================================================

def export_rel_dzielnica_gmina(dzielnice: pd.DataFrame):
    """Export Dzielnica -[NALEZY_DO]-> Gmina."""
    rels = dzielnice[['id', 'gmina']].copy()
    rels = rels.rename(columns={'id': 'dzielnica_id', 'gmina': 'gmina_nazwa'})

    output = CSV_DIR / "relationships" / "dzielnica_nalezy_do_gmina.csv"
    rels.to_csv(output, index=False)
    logger.info(f"  NALEZY_DO (Dzielnica→Gmina): {len(rels)} rels")


def export_rel_dzialka_gmina(parcels: gpd.GeoDataFrame):
    """Export Dzialka -[W_GMINIE]-> Gmina."""
    rels = parcels[['id_dzialki', 'gmina']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'gmina': 'gmina_nazwa'})

    output = CSV_DIR / "relationships" / "dzialka_w_gminie.csv"
    rels.to_csv(output, index=False)
    logger.info(f"  W_GMINIE: {len(rels)} rels")


def export_rel_dzialka_dzielnica(parcels: gpd.GeoDataFrame):
    """Export Dzialka -[W_DZIELNICY]-> Dzielnica."""
    rels = parcels[['id_dzialki', 'dzielnica', 'gmina']].copy()
    rels['dzielnica_id'] = rels['dzielnica'] + '_' + rels['gmina']
    rels = rels[['id_dzialki', 'dzielnica_id']]
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id'})

    output = CSV_DIR / "relationships" / "dzialka_w_dzielnicy.csv"
    rels.to_csv(output, index=False)
    logger.info(f"  W_DZIELNICY: {len(rels)} rels")


def export_rel_dzialka_strefa_pog(parcels: gpd.GeoDataFrame):
    """Export Dzialka -[W_STREFIE_POG]-> StrefaPOG."""
    # Filter parcels with POG
    with_pog = parcels[parcels['pog_oznaczenie'].notna()].copy()

    # Build strefa_id from gmina + oznaczenie (composite key)
    rels = with_pog[['id_dzialki', 'gmina', 'pog_oznaczenie']].copy()

    # Create composite ID matching StrefaPOG nodes
    # Normalize gmina to lowercase (POG uses lowercase: gdansk, gdynia, sopot)
    rels['gmina_lower'] = rels['gmina'].str.lower().str.replace('ń', 'n').str.replace('ó', 'o')
    rels['strefa_id'] = rels['gmina_lower'] + '_' + rels['pog_oznaczenie']
    rels = rels[['id_dzialki', 'strefa_id']]
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id'})

    output = CSV_DIR / "relationships" / "dzialka_w_strefie_pog.csv"
    rels.to_csv(output, index=False)
    logger.info(f"  W_STREFIE_POG: {len(rels)} rels")


def export_rel_strefa_dozwala_profil(pog: gpd.GeoDataFrame):
    """Export StrefaPOG -[DOZWALA]-> ProfilFunkcji."""
    rels = []

    for _, row in pog.iterrows():
        # Use composite ID (gmina_oznaczenie)
        strefa_id = row['gmina'] + '_' + row['oznaczenie']

        # podstawowy profiles
        if pd.notna(row.get('profil_podstawowy')):
            for kod in str(row['profil_podstawowy']).split('|'):
                kod = kod.strip()
                if kod:
                    rels.append({
                        'strefa_id': strefa_id,
                        'profil_kod': kod,
                        'typ': 'podstawowy'
                    })

        # dodatkowy profiles
        if pd.notna(row.get('profil_dodatkowy')):
            for kod in str(row['profil_dodatkowy']).split('|'):
                kod = kod.strip()
                if kod:
                    rels.append({
                        'strefa_id': strefa_id,
                        'profil_kod': kod,
                        'typ': 'dodatkowy'
                    })

    df = pd.DataFrame(rels)
    output = CSV_DIR / "relationships" / "strefa_dozwala_profil.csv"
    df.to_csv(output, index=False)
    logger.info(f"  DOZWALA: {len(df)} rels")


def export_rel_dzialka_kategorie(parcels: gpd.GeoDataFrame):
    """Export Dzialka -[MA_*]-> Kategorie."""

    # MA_CISZE
    rels = parcels[['id_dzialki', 'kategoria_ciszy']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'kategoria_ciszy': 'poziom'})
    rels.to_csv(CSV_DIR / "relationships" / "dzialka_ma_cisze.csv", index=False)
    logger.info(f"  MA_CISZE: {len(rels)} rels")

    # MA_NATURE
    rels = parcels[['id_dzialki', 'kategoria_natury']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'kategoria_natury': 'poziom'})
    rels.to_csv(CSV_DIR / "relationships" / "dzialka_ma_nature.csv", index=False)
    logger.info(f"  MA_NATURE: {len(rels)} rels")

    # MA_DOSTEPNOSC
    rels = parcels[['id_dzialki', 'kategoria_dostepu']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'kategoria_dostepu': 'poziom'})
    rels.to_csv(CSV_DIR / "relationships" / "dzialka_ma_dostepnosc.csv", index=False)
    logger.info(f"  MA_DOSTEPNOSC: {len(rels)} rels")

    # MA_POWIERZCHNIE
    rels = parcels[['id_dzialki', 'size_category']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'size_category': 'klasa'})
    rels.to_csv(CSV_DIR / "relationships" / "dzialka_ma_powierzchnie.csv", index=False)
    logger.info(f"  MA_POWIERZCHNIE: {len(rels)} rels")


def export_rel_dzialka_typ_zabudowy(parcels: gpd.GeoDataFrame):
    """Export Dzialka -[MOZNA_ZABUDOWAC]-> TypZabudowy."""
    # Map POG symbol to typ zabudowy
    parcels_copy = parcels.copy()
    parcels_copy['typ_zabudowy'] = parcels_copy['pog_symbol'].map(POG_SYMBOL_TO_TYP_ZABUDOWY)
    parcels_copy['typ_zabudowy'] = parcels_copy['typ_zabudowy'].fillna('brak')

    rels = parcels_copy[['id_dzialki', 'typ_zabudowy']].copy()
    rels = rels.rename(columns={'id_dzialki': 'dzialka_id', 'typ_zabudowy': 'typ'})

    output = CSV_DIR / "relationships" / "dzialka_mozna_zabudowac.csv"
    rels.to_csv(output, index=False)
    logger.info(f"  MOZNA_ZABUDOWAC: {len(rels)} rels")


# =============================================================================
# MAIN
# =============================================================================

def main():
    logger.info("=" * 60)
    logger.info("PREPARE NEO4J DATA")
    logger.info("=" * 60)

    # Create directories
    create_output_dirs()

    # Load source data
    logger.info("\nLoading source data...")
    parcels = gpd.read_file(NEO4J_DIR / "parcels_enriched.gpkg")
    logger.info(f"  Parcels: {len(parcels):,}")

    pog = gpd.read_file(NEO4J_DIR / "pog_trojmiasto.gpkg")
    logger.info(f"  POG zones: {len(pog):,}")

    # Export nodes
    logger.info("\n" + "=" * 60)
    logger.info("EXPORTING NODES")
    logger.info("=" * 60)

    export_gminy()
    dzielnice = export_dzielnice(parcels)
    strefy = export_strefy_pog(pog)
    export_profile_funkcji(pog)
    export_kategorie()
    export_dzialki(parcels)

    # Export relationships
    logger.info("\n" + "=" * 60)
    logger.info("EXPORTING RELATIONSHIPS")
    logger.info("=" * 60)

    export_rel_dzielnica_gmina(dzielnice)
    export_rel_dzialka_gmina(parcels)
    export_rel_dzialka_dzielnica(parcels)
    export_rel_dzialka_strefa_pog(parcels)
    export_rel_strefa_dozwala_profil(pog)
    export_rel_dzialka_kategorie(parcels)
    export_rel_dzialka_typ_zabudowy(parcels)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    node_files = list((CSV_DIR / "nodes").glob("*.csv"))
    rel_files = list((CSV_DIR / "relationships").glob("*.csv"))

    logger.info(f"Node CSVs: {len(node_files)}")
    for f in sorted(node_files):
        df = pd.read_csv(f)
        logger.info(f"  {f.name}: {len(df):,} rows")

    logger.info(f"\nRelationship CSVs: {len(rel_files)}")
    for f in sorted(rel_files):
        df = pd.read_csv(f)
        logger.info(f"  {f.name}: {len(df):,} rows")

    logger.info("\n✅ Neo4j data preparation complete!")
    logger.info(f"Output: {CSV_DIR}")


if __name__ == "__main__":
    main()
