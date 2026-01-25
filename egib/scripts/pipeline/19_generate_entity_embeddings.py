#!/usr/bin/env python3
"""
19_generate_entity_embeddings.py - Generate 384-dim embeddings for entity resolution.

Creates semantic embeddings for location names, categories, and POI types
to enable fuzzy matching via vector similarity search.

Entity Types:
- LocationName: Districts, cities, neighborhoods (e.g., "Matemblewo" → "Matarnia")
- SemanticCategory: User descriptions → graph categories (e.g., "spokojna" → "cicha")
- WaterTypeName: Water descriptions → water types (e.g., "nad morzem" → "morze")
- POITypeName: POI descriptions → POI types (e.g., "szkoła" → "school")

Model: distiluse-base-multilingual-cased (384 dimensions, Polish + English)

Usage:
    python 19_generate_entity_embeddings.py

Requires:
    - sentence-transformers installed
    - Neo4j running with schema from 15_create_neo4j_schema.py
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

# Add backend to path for config access
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection - use environment or defaults
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LocationEntry:
    """Location name entry for embedding."""
    id: str  # unique identifier
    canonical_name: str  # display name
    name_variants: List[str]  # alternative spellings
    source: str  # "egib", "price_data", "alias"
    type: str  # "city", "district", "area"
    maps_to_district: Optional[str]  # EGiB district name or None
    maps_to_gmina: str  # always set
    search_in_districts: List[str]  # fallback search districts
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    price_segment: Optional[str] = None
    note: Optional[str] = None


@dataclass
class SemanticCategoryEntry:
    """Semantic category entry for embedding."""
    id: str
    type: str  # "quietness", "nature", "accessibility", "density"
    canonical_name: str
    name_variants: List[str]
    maps_to_values: List[str]  # Graph category values


@dataclass
class WaterTypeEntry:
    """Water type name entry for embedding."""
    id: str
    canonical_name: str
    name_variants: List[str]
    maps_to_water_type: str  # WaterType.id
    premium_factor: float


@dataclass
class POITypeEntry:
    """POI type name entry for embedding."""
    id: str
    canonical_name: str
    name_variants: List[str]
    maps_to_poi_types: List[str]  # POI type IDs


# =============================================================================
# LOCATION DATA COLLECTION
# =============================================================================

def get_egib_districts(session) -> List[Dict[str, Any]]:
    """Get all districts from Neo4j EGiB data."""
    query = """
    MATCH (p:Parcel)
    WITH p.dzielnica as district, p.gmina as gmina, count(p) as cnt
    WHERE district IS NOT NULL
    RETURN district, gmina, cnt
    ORDER BY cnt DESC
    """
    result = session.run(query)
    return [{"district": r["district"], "gmina": r["gmina"], "count": r["cnt"]} for r in result]


def get_egib_cities(session) -> List[Dict[str, Any]]:
    """Get all cities/gminy from Neo4j."""
    query = """
    MATCH (c:City)
    RETURN c.name as name
    ORDER BY c.name
    """
    result = session.run(query)
    return [{"name": r["name"]} for r in result]


def collect_location_entries(session) -> List[LocationEntry]:
    """Collect all location entries from various sources."""
    entries = []
    seen_ids = set()

    # Price data from backend - import directly to avoid config loading
    try:
        import importlib.util
        price_data_path = backend_path / "app" / "engine" / "price_data.py"
        spec = importlib.util.spec_from_file_location("price_data", price_data_path)
        price_data_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(price_data_module)
        DISTRICT_PRICES = price_data_module.DISTRICT_PRICES
        price_lookup = {(c, d): v for (c, d), v in DISTRICT_PRICES.items()}
        logger.info(f"Loaded {len(price_lookup)} price entries from price_data.py")
    except Exception as e:
        logger.warning(f"Could not import price_data: {e}, using empty lookup")
        price_lookup = {}

    # 1. Get EGiB districts
    logger.info("Collecting EGiB districts...")
    egib_districts = get_egib_districts(session)

    for d in egib_districts:
        district_name = d["district"]
        gmina = d["gmina"]
        district_id = district_name.lower().replace(" ", "_").replace("-", "_")

        if district_id in seen_ids:
            continue
        seen_ids.add(district_id)

        # Look up price data
        price_info = price_lookup.get((gmina, district_name), {})

        entries.append(LocationEntry(
            id=district_id,
            canonical_name=district_name,
            name_variants=[district_name, district_name.lower()],
            source="egib",
            type="district",
            maps_to_district=district_name,
            maps_to_gmina=gmina,
            search_in_districts=[district_name],
            price_min=price_info.get("min"),
            price_max=price_info.get("max"),
            price_segment=price_info.get("segment"),
        ))

    # 2. Get EGiB cities
    logger.info("Collecting EGiB cities...")
    egib_cities = get_egib_cities(session)

    for c in egib_cities:
        city_name = c["name"]
        city_id = city_name.lower().replace(" ", "_")

        if city_id in seen_ids:
            continue
        seen_ids.add(city_id)

        price_info = price_lookup.get((city_name, None), {})

        entries.append(LocationEntry(
            id=city_id,
            canonical_name=city_name,
            name_variants=[city_name, city_name.lower()],
            source="egib",
            type="city",
            maps_to_district=None,
            maps_to_gmina=city_name,
            search_in_districts=[],  # Search all districts in city
            price_min=price_info.get("min"),
            price_max=price_info.get("max"),
            price_segment=price_info.get("segment"),
        ))

    # 3. Add price_data districts that might not be in EGiB
    logger.info("Adding price_data districts...")
    for (city, district), price_info in price_lookup.items():
        if district is None:
            continue

        district_id = district.lower().replace(" ", "_").replace("-", "_")

        if district_id in seen_ids:
            continue
        seen_ids.add(district_id)

        # This district exists in price data but not in EGiB
        # Try to find a mapping (e.g., Matemblewo → Matarnia)
        entries.append(LocationEntry(
            id=district_id,
            canonical_name=district,
            name_variants=[district, district.lower()],
            source="price_data",
            type="district",
            maps_to_district=None,  # Will be resolved by DISTRICT_MAPPINGS
            maps_to_gmina=city,
            search_in_districts=[],  # Will be set by DISTRICT_MAPPINGS
            price_min=price_info.get("min"),
            price_max=price_info.get("max"),
            price_segment=price_info.get("segment"),
            note=price_info.get("desc"),
        ))

    # 4. Add manual aliases and mappings
    logger.info("Adding manual aliases...")
    DISTRICT_MAPPINGS = {
        # Matemblewo doesn't exist in EGiB, maps to Matarnia
        "matemblewo": {
            "canonical": "Matemblewo",
            "maps_to": "Matarnia",
            "gmina": "Gdańsk",
            "search_in": ["Matarnia", "Osowa"],
            "note": "Obszar przy TPK, administracyjnie część Matarni"
        },
        # VII Dwór - part of Oliwa/Wrzeszcz area
        "vii_dwor": {
            "canonical": "VII Dwór",
            "maps_to": None,
            "gmina": "Gdańsk",
            "search_in": ["Oliwa", "Wrzeszcz"],
            "note": "Okolica między Oliwą a Wrzeszczem"
        },
        "vii_dwór": {
            "canonical": "VII Dwór",
            "maps_to": None,
            "gmina": "Gdańsk",
            "search_in": ["Oliwa", "Wrzeszcz"],
            "note": "Okolica między Oliwą a Wrzeszczem"
        },
        # Chwarzno-Wiczlino split
        "chwarzno": {
            "canonical": "Chwarzno",
            "maps_to": "Chwarzno-Wiczlino",
            "gmina": "Gdynia",
            "search_in": ["Chwarzno-Wiczlino"],
            "note": "Część dzielnicy Chwarzno-Wiczlino"
        },
        # Common misspellings and variants
        "mateblewo": {
            "canonical": "Matemblewo",
            "maps_to": "Matarnia",
            "gmina": "Gdańsk",
            "search_in": ["Matarnia"],
            "note": "Wariant Matemblewa"
        },
        # Trójmiasto as a region
        "trojmiasto": {
            "canonical": "Trójmiasto",
            "maps_to": None,
            "gmina": None,
            "search_in": [],  # Search all
            "note": "Cały obszar Gdańsk-Gdynia-Sopot"
        },
    }

    for alias_id, mapping in DISTRICT_MAPPINGS.items():
        if alias_id in seen_ids:
            # Update existing entry with mapping info
            for entry in entries:
                if entry.id == alias_id:
                    if mapping.get("maps_to"):
                        entry.maps_to_district = mapping["maps_to"]
                    if mapping.get("search_in"):
                        entry.search_in_districts = mapping["search_in"]
                    break
        else:
            seen_ids.add(alias_id)
            entries.append(LocationEntry(
                id=alias_id,
                canonical_name=mapping["canonical"],
                name_variants=[mapping["canonical"], alias_id.replace("_", " ")],
                source="alias",
                type="area" if mapping.get("gmina") is None else "district",
                maps_to_district=mapping.get("maps_to"),
                maps_to_gmina=mapping.get("gmina", ""),
                search_in_districts=mapping.get("search_in", []),
                note=mapping.get("note"),
            ))

    logger.info(f"Collected {len(entries)} location entries")
    return entries


# =============================================================================
# SEMANTIC CATEGORY DATA
# =============================================================================

def get_semantic_categories() -> List[SemanticCategoryEntry]:
    """Define semantic category mappings."""
    return [
        # Quietness categories
        SemanticCategoryEntry(
            id="cicha",
            type="quietness",
            canonical_name="Cicha okolica",
            name_variants=["cicha", "cicho", "spokojna", "spokojnie", "spokój", "cisza", "quiet", "peaceful"],
            maps_to_values=["bardzo_cicha", "cicha"]
        ),
        SemanticCategoryEntry(
            id="bardzo_cicha",
            type="quietness",
            canonical_name="Bardzo cicha okolica",
            name_variants=["bardzo cicha", "super cicha", "idealna cisza", "kompletna cisza", "totalny spokój"],
            maps_to_values=["bardzo_cicha"]
        ),
        SemanticCategoryEntry(
            id="umiarkowana_cisza",
            type="quietness",
            canonical_name="Umiarkowana cisza",
            name_variants=["umiarkowanie cicha", "średnio cicha", "niezbyt głośna", "w miarę spokojna"],
            maps_to_values=["umiarkowana"]
        ),
        SemanticCategoryEntry(
            id="glosna",
            type="quietness",
            canonical_name="Głośna okolica",
            name_variants=["głośna", "głośno", "hałaśliwa", "hałas", "ruchliwa", "tętniąca życiem", "noisy"],
            maps_to_values=["głośna"]
        ),

        # Nature categories
        SemanticCategoryEntry(
            id="zielona",
            type="nature",
            canonical_name="Zielona okolica",
            name_variants=["zielona", "zielono", "blisko natury", "naturalna", "przyroda", "green", "nature"],
            maps_to_values=["bardzo_zielona", "zielona"]
        ),
        SemanticCategoryEntry(
            id="blisko_lasu",
            type="nature",
            canonical_name="Blisko lasu",
            name_variants=["blisko lasu", "przy lesie", "obok lasu", "las", "leśna", "forest", "lasy"],
            maps_to_values=["bardzo_zielona", "zielona"]
        ),
        SemanticCategoryEntry(
            id="zurbanizowana",
            type="nature",
            canonical_name="Zurbanizowana",
            name_variants=["zurbanizowana", "miejska", "miasto", "urban", "bez natury", "beton"],
            maps_to_values=["zurbanizowana"]
        ),

        # Accessibility categories
        SemanticCategoryEntry(
            id="dobry_dojazd",
            type="accessibility",
            canonical_name="Dobry dojazd",
            name_variants=["dobry dojazd", "łatwy dojazd", "blisko komunikacji", "dobrze skomunikowana", "transport"],
            maps_to_values=["doskonała", "dobra"]
        ),
        SemanticCategoryEntry(
            id="blisko_szkoly",
            type="accessibility",
            canonical_name="Blisko szkoły",
            name_variants=["blisko szkoły", "przy szkole", "dla dzieci", "szkoła w pobliżu", "edukacja"],
            maps_to_values=["doskonała", "dobra"]
        ),
        SemanticCategoryEntry(
            id="blisko_sklepu",
            type="accessibility",
            canonical_name="Blisko sklepu",
            name_variants=["blisko sklepu", "sklep w pobliżu", "przy sklepie", "zakupy", "market"],
            maps_to_values=["doskonała", "dobra"]
        ),
        SemanticCategoryEntry(
            id="odlegla",
            type="accessibility",
            canonical_name="Odległa",
            name_variants=["odległa", "daleko od wszystkiego", "na uboczu", "zaciszna", "remote"],
            maps_to_values=["ograniczona"]
        ),

        # Density categories
        SemanticCategoryEntry(
            id="rzadka_zabudowa",
            type="density",
            canonical_name="Rzadka zabudowa",
            name_variants=["rzadka zabudowa", "mało domów", "przestronnie", "duże działki", "niezbyt zabudowane"],
            maps_to_values=["rzadka", "bardzo_rzadka"]
        ),
        SemanticCategoryEntry(
            id="gesta_zabudowa",
            type="density",
            canonical_name="Gęsta zabudowa",
            name_variants=["gęsta zabudowa", "dużo domów", "osiedle", "zabudowana", "dense"],
            maps_to_values=["gęsta", "bardzo_gęsta"]
        ),
    ]


# =============================================================================
# WATER TYPE DATA
# =============================================================================

def get_water_type_names() -> List[WaterTypeEntry]:
    """Define water type name mappings."""
    return [
        WaterTypeEntry(
            id="morze",
            canonical_name="Morze Bałtyckie",
            name_variants=["morze", "Bałtyk", "ocean", "plaża", "beach", "nad morzem", "przy morzu",
                          "blisko morza", "morski", "sea"],
            maps_to_water_type="morze",
            premium_factor=2.0
        ),
        WaterTypeEntry(
            id="jezioro",
            canonical_name="Jezioro",
            name_variants=["jezioro", "jezior", "lake", "nad jeziorem", "przy jeziorze", "blisko jeziora"],
            maps_to_water_type="jezioro",
            premium_factor=1.5
        ),
        WaterTypeEntry(
            id="rzeka",
            canonical_name="Rzeka",
            name_variants=["rzeka", "rzeki", "river", "nad rzeką", "przy rzece", "blisko rzeki"],
            maps_to_water_type="rzeka",
            premium_factor=1.3
        ),
        WaterTypeEntry(
            id="zatoka",
            canonical_name="Zatoka",
            name_variants=["zatoka", "bay", "zatoka gdańska", "blisko zatoki"],
            maps_to_water_type="zatoka",
            premium_factor=1.8
        ),
        WaterTypeEntry(
            id="kanal",
            canonical_name="Kanał",
            name_variants=["kanał", "kanal", "canal", "przy kanale"],
            maps_to_water_type="kanal",
            premium_factor=1.1
        ),
        WaterTypeEntry(
            id="staw",
            canonical_name="Staw/Oczko wodne",
            name_variants=["staw", "oczko", "oczko wodne", "pond", "przy stawie"],
            maps_to_water_type="staw",
            premium_factor=1.05
        ),
        WaterTypeEntry(
            id="woda_ogolnie",
            canonical_name="Blisko wody",
            name_variants=["woda", "blisko wody", "przy wodzie", "nad wodą", "water", "waterfront"],
            maps_to_water_type="jezioro",  # Default to jezioro for general "water"
            premium_factor=1.3
        ),
    ]


# =============================================================================
# POI TYPE DATA
# =============================================================================

def get_poi_type_names() -> List[POITypeEntry]:
    """Define POI type name mappings."""
    return [
        POITypeEntry(
            id="edukacja",
            canonical_name="Placówka edukacyjna",
            name_variants=["szkoła", "przedszkole", "żłobek", "edukacja", "school", "dla dzieci",
                          "szkoła podstawowa", "gimnazjum", "liceum"],
            maps_to_poi_types=["school", "kindergarten"]
        ),
        POITypeEntry(
            id="sklepy",
            canonical_name="Sklepy",
            name_variants=["sklep", "market", "supermarket", "zakupy", "shop", "biedronka", "lidl",
                          "żabka", "spożywczy", "shopping"],
            maps_to_poi_types=["shop", "supermarket"]
        ),
        POITypeEntry(
            id="komunikacja",
            canonical_name="Komunikacja publiczna",
            name_variants=["przystanek", "autobus", "tramwaj", "SKM", "komunikacja", "transport",
                          "bus_stop", "public_transport", "metro"],
            maps_to_poi_types=["bus_stop"]
        ),
        POITypeEntry(
            id="zdrowie",
            canonical_name="Placówki medyczne",
            name_variants=["szpital", "przychodnia", "lekarz", "zdrowie", "hospital", "apteka",
                          "clinic", "medical"],
            maps_to_poi_types=["hospital", "doctors", "pharmacy"]
        ),
        POITypeEntry(
            id="przemysl",
            canonical_name="Tereny przemysłowe",
            name_variants=["przemysł", "fabryka", "zakład", "industrial", "hałas przemysłowy",
                          "strefa przemysłowa"],
            maps_to_poi_types=["industrial"]
        ),
    ]


# =============================================================================
# EMBEDDING GENERATION
# =============================================================================

def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate 384-dim embeddings for texts using sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        raise

    logger.info(f"Loading embedding model...")
    model = SentenceTransformer('distiluse-base-multilingual-cased')
    logger.info(f"Generating embeddings for {len(texts)} texts...")

    # Normalize and encode
    cleaned = [t.lower().strip() for t in texts]
    embeddings = model.encode(cleaned, normalize_embeddings=True, show_progress_bar=True)

    return embeddings.tolist()


# =============================================================================
# NEO4J IMPORT
# =============================================================================

def import_location_names(session, entries: List[LocationEntry], embeddings: Dict[str, List[float]]):
    """Import LocationName nodes to Neo4j."""
    logger.info(f"Importing {len(entries)} LocationName nodes...")

    for entry in entries:
        # Get embedding for canonical name
        embedding = embeddings.get(entry.canonical_name.lower())
        if embedding is None:
            logger.warning(f"No embedding for {entry.canonical_name}")
            continue

        query = """
        MERGE (ln:LocationName {id: $id})
        SET ln.canonical_name = $canonical_name,
            ln.name_variants = $name_variants,
            ln.source = $source,
            ln.type = $type,
            ln.maps_to_district = $maps_to_district,
            ln.maps_to_gmina = $maps_to_gmina,
            ln.search_in_districts = $search_in_districts,
            ln.price_min = $price_min,
            ln.price_max = $price_max,
            ln.price_segment = $price_segment,
            ln.note = $note,
            ln.embedding = $embedding
        """

        session.run(query, {
            "id": entry.id,
            "canonical_name": entry.canonical_name,
            "name_variants": entry.name_variants,
            "source": entry.source,
            "type": entry.type,
            "maps_to_district": entry.maps_to_district,
            "maps_to_gmina": entry.maps_to_gmina,
            "search_in_districts": entry.search_in_districts,
            "price_min": entry.price_min,
            "price_max": entry.price_max,
            "price_segment": entry.price_segment,
            "note": entry.note,
            "embedding": embedding,
        })

    # Create MAPS_TO relations
    logger.info("Creating MAPS_TO relations...")
    query = """
    MATCH (ln:LocationName)
    WHERE ln.maps_to_district IS NOT NULL
    MATCH (d:District {name: ln.maps_to_district})
    MERGE (ln)-[:MAPS_TO]->(d)
    """
    session.run(query)

    # Create MAPS_TO relations to City
    query = """
    MATCH (ln:LocationName)
    WHERE ln.type = 'city' AND ln.maps_to_gmina IS NOT NULL
    MATCH (c:City {name: ln.maps_to_gmina})
    MERGE (ln)-[:MAPS_TO]->(c)
    """
    session.run(query)


def import_semantic_categories(session, entries: List[SemanticCategoryEntry], embeddings: Dict[str, List[float]]):
    """Import SemanticCategory nodes to Neo4j."""
    logger.info(f"Importing {len(entries)} SemanticCategory nodes...")

    for entry in entries:
        embedding = embeddings.get(entry.canonical_name.lower())
        if embedding is None:
            logger.warning(f"No embedding for {entry.canonical_name}")
            continue

        query = """
        MERGE (sc:SemanticCategory {id: $id})
        SET sc.type = $type,
            sc.canonical_name = $canonical_name,
            sc.name_variants = $name_variants,
            sc.maps_to_values = $maps_to_values,
            sc.embedding = $embedding
        """

        session.run(query, {
            "id": entry.id,
            "type": entry.type,
            "canonical_name": entry.canonical_name,
            "name_variants": entry.name_variants,
            "maps_to_values": entry.maps_to_values,
            "embedding": embedding,
        })


def import_water_type_names(session, entries: List[WaterTypeEntry], embeddings: Dict[str, List[float]]):
    """Import WaterTypeName nodes to Neo4j."""
    logger.info(f"Importing {len(entries)} WaterTypeName nodes...")

    for entry in entries:
        embedding = embeddings.get(entry.canonical_name.lower())
        if embedding is None:
            logger.warning(f"No embedding for {entry.canonical_name}")
            continue

        query = """
        MERGE (wn:WaterTypeName {id: $id})
        SET wn.canonical_name = $canonical_name,
            wn.name_variants = $name_variants,
            wn.maps_to_water_type = $maps_to_water_type,
            wn.premium_factor = $premium_factor,
            wn.embedding = $embedding
        """

        session.run(query, {
            "id": entry.id,
            "canonical_name": entry.canonical_name,
            "name_variants": entry.name_variants,
            "maps_to_water_type": entry.maps_to_water_type,
            "premium_factor": entry.premium_factor,
            "embedding": embedding,
        })

    # Create MAPS_TO relations to WaterType
    logger.info("Creating WaterTypeName -> WaterType relations...")
    query = """
    MATCH (wn:WaterTypeName)
    WHERE wn.maps_to_water_type IS NOT NULL
    MATCH (wt:WaterType {id: wn.maps_to_water_type})
    MERGE (wn)-[:MAPS_TO]->(wt)
    """
    session.run(query)


def import_poi_type_names(session, entries: List[POITypeEntry], embeddings: Dict[str, List[float]]):
    """Import POITypeName nodes to Neo4j."""
    logger.info(f"Importing {len(entries)} POITypeName nodes...")

    for entry in entries:
        embedding = embeddings.get(entry.canonical_name.lower())
        if embedding is None:
            logger.warning(f"No embedding for {entry.canonical_name}")
            continue

        query = """
        MERGE (pn:POITypeName {id: $id})
        SET pn.canonical_name = $canonical_name,
            pn.name_variants = $name_variants,
            pn.maps_to_poi_types = $maps_to_poi_types,
            pn.embedding = $embedding
        """

        session.run(query, {
            "id": entry.id,
            "canonical_name": entry.canonical_name,
            "name_variants": entry.name_variants,
            "maps_to_poi_types": entry.maps_to_poi_types,
            "embedding": embedding,
        })


# =============================================================================
# MAIN
# =============================================================================

def main():
    logger.info("=" * 60)
    logger.info("GENERATING ENTITY EMBEDDINGS FOR NEO4J")
    logger.info("=" * 60)
    logger.info(f"Neo4j URI: {NEO4J_URI}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # 1. Collect all data
            logger.info("\n" + "=" * 60)
            logger.info("COLLECTING DATA")
            logger.info("=" * 60)

            location_entries = collect_location_entries(session)
            semantic_categories = get_semantic_categories()
            water_type_names = get_water_type_names()
            poi_type_names = get_poi_type_names()

            # 2. Collect all texts for embedding
            all_texts = []

            # Locations
            for entry in location_entries:
                all_texts.append(entry.canonical_name)
                all_texts.extend(entry.name_variants)

            # Semantic categories
            for entry in semantic_categories:
                all_texts.append(entry.canonical_name)
                all_texts.extend(entry.name_variants)

            # Water types
            for entry in water_type_names:
                all_texts.append(entry.canonical_name)
                all_texts.extend(entry.name_variants)

            # POI types
            for entry in poi_type_names:
                all_texts.append(entry.canonical_name)
                all_texts.extend(entry.name_variants)

            # Deduplicate
            unique_texts = list(set(all_texts))
            logger.info(f"Total unique texts to embed: {len(unique_texts)}")

            # 3. Generate embeddings
            logger.info("\n" + "=" * 60)
            logger.info("GENERATING EMBEDDINGS")
            logger.info("=" * 60)

            embeddings_list = generate_embeddings(unique_texts)

            # Create lookup dict
            embeddings = {t.lower(): e for t, e in zip(unique_texts, embeddings_list)}
            logger.info(f"Generated {len(embeddings)} embeddings")

            # 4. Import to Neo4j
            logger.info("\n" + "=" * 60)
            logger.info("IMPORTING TO NEO4J")
            logger.info("=" * 60)

            import_location_names(session, location_entries, embeddings)
            import_semantic_categories(session, semantic_categories, embeddings)
            import_water_type_names(session, water_type_names, embeddings)
            import_poi_type_names(session, poi_type_names, embeddings)

            # 5. Verify
            logger.info("\n" + "=" * 60)
            logger.info("VERIFICATION")
            logger.info("=" * 60)

            counts = session.run("""
            MATCH (ln:LocationName) WITH count(ln) as locations
            MATCH (sc:SemanticCategory) WITH locations, count(sc) as categories
            MATCH (wn:WaterTypeName) WITH locations, categories, count(wn) as water_types
            MATCH (pn:POITypeName) WITH locations, categories, water_types, count(pn) as poi_types
            RETURN locations, categories, water_types, poi_types
            """).single()

            logger.info(f"LocationName nodes: {counts['locations']}")
            logger.info(f"SemanticCategory nodes: {counts['categories']}")
            logger.info(f"WaterTypeName nodes: {counts['water_types']}")
            logger.info(f"POITypeName nodes: {counts['poi_types']}")

            # Test vector search
            logger.info("\nTesting vector search for 'Matemblewo'...")
            test_embedding = embeddings.get("matemblewo")
            if test_embedding:
                result = session.run("""
                CALL db.index.vector.queryNodes('location_name_embedding_idx', 3, $embedding)
                YIELD node, score
                RETURN node.canonical_name as name, node.maps_to_district as maps_to, score
                ORDER BY score DESC
                """, {"embedding": test_embedding})

                for r in result:
                    logger.info(f"  {r['name']} -> {r['maps_to']} (score: {r['score']:.3f})")

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("ENTITY EMBEDDINGS GENERATED SUCCESSFULLY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
