#!/usr/bin/env python3
"""
21_create_neo4j_schema_v2.py - Przebudowany schemat Neo4j v2

Tworzy kompletną architekturę grafową z pełnym wykorzystaniem multi-hop traversals:

WĘZŁY GŁÓWNE (25 typów):
- Parcel (154,959) - działki z 68 właściwościami
- District (138), City (3) - hierarchia lokalizacji

WŁASNOŚĆ:
- OwnershipType (5): prywatna, publiczna, spółdzielcza, kościelna, inna
- OwnershipGroup (15): Osoby fizyczne, Gminy, Skarb Państwa, etc.

ZABUDOWA:
- BuildStatus (2): zabudowana, niezabudowana
- BuildingFunction (11): mieszkalne, gospodarcze, handlowo-usługowe, etc.
- BuildingType (30+): budynek jednorodzinny, wielorodzinny, etc.

PLANOWANIE:
- POGZone (7,523): strefy planistyczne z parametrami
- POGProfile (15): MN, MW, U, P, ZP, etc.

ROZMIAR:
- SizeCategory (4): mala, pod_dom, duza, bardzo_duza

KATEGORIE JAKOŚCIOWE:
- QuietnessCategory (4), NatureCategory (4), AccessCategory (4), DensityCategory (4)
- WaterType (6), PriceSegment (6)

POI:
- School (60), BusStop (339), Shop (~8000), Water (521), Forest (~2000), Road (~1000)

ENTITY RESOLUTION (512-dim):
- LocationName, SemanticCategory, WaterTypeName, POITypeName

RELACJE (20 typów):
- Hierarchia: LOCATED_IN, BELONGS_TO
- Własność: HAS_OWNERSHIP, HAS_OWNER_GROUP
- Zabudowa: HAS_BUILD_STATUS, HAS_BUILDING_FUNCTION, HAS_BUILDING_TYPE
- Planowanie: HAS_POG, ALLOWS_PROFILE
- Rozmiar: HAS_SIZE
- Kategorie: HAS_QUIETNESS, HAS_NATURE, HAS_ACCESS, HAS_DENSITY, NEAREST_WATER_TYPE
- POI: NEAR_SCHOOL, NEAR_BUS_STOP, NEAR_SHOP, NEAR_WATER, NEAR_FOREST, NEAR_ROAD
- Sąsiedztwo: ADJACENT_TO
"""

import os
import sys
from pathlib import Path

from neo4j import GraphDatabase
from loguru import logger

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def run_query(session, query: str, params: dict = None, description: str = ""):
    """Execute a Cypher query and log result."""
    try:
        result = session.run(query, params or {})
        summary = result.consume()
        if description:
            logger.info(f"  {description}: {summary.counters}")
        return True
    except Exception as e:
        logger.error(f"  Error ({description}): {e}")
        return False


def drop_existing_indexes(session):
    """Drop all existing indexes and constraints for clean start."""
    logger.info("\n" + "=" * 60)
    logger.info("USUWANIE ISTNIEJĄCYCH INDEKSÓW I CONSTRAINTS")
    logger.info("=" * 60)

    # Get all constraints
    result = session.run("SHOW CONSTRAINTS")
    constraints = [record["name"] for record in result]

    for name in constraints:
        try:
            session.run(f"DROP CONSTRAINT {name} IF EXISTS")
            logger.info(f"  Usunięto constraint: {name}")
        except Exception as e:
            logger.warning(f"  Nie można usunąć constraint {name}: {e}")

    # Get all indexes (excluding lookup indexes)
    result = session.run("SHOW INDEXES WHERE type <> 'LOOKUP'")
    indexes = [record["name"] for record in result]

    for name in indexes:
        try:
            session.run(f"DROP INDEX {name} IF EXISTS")
            logger.info(f"  Usunięto index: {name}")
        except Exception as e:
            logger.warning(f"  Nie można usunąć index {name}: {e}")


def create_constraints(session):
    """Create unique constraints for all node types."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE CONSTRAINTS")
    logger.info("=" * 60)

    constraints = [
        # Main entities
        ("Parcel", "id_dzialki"),
        ("District", "name"),
        ("City", "name"),

        # Ownership
        ("OwnershipType", "id"),
        ("OwnershipGroup", "id"),

        # Building
        ("BuildStatus", "id"),
        ("BuildingFunction", "id"),
        ("BuildingType", "id"),

        # Planning
        ("POGZone", "id"),
        ("POGProfile", "id"),

        # Size
        ("SizeCategory", "id"),

        # POI
        ("School", "id"),
        ("BusStop", "id"),
        ("Forest", "id"),
        ("Water", "id"),
        ("Shop", "id"),
        ("Road", "id"),

        # Categories
        ("QuietnessCategory", "id"),
        ("NatureCategory", "id"),
        ("AccessCategory", "id"),
        ("DensityCategory", "id"),
        ("WaterType", "id"),
        ("PriceSegment", "id"),

        # Entity Resolution
        ("LocationName", "id"),
        ("SemanticCategory", "id"),
        ("WaterTypeName", "id"),
        ("POITypeName", "id"),
    ]

    for label, prop in constraints:
        query = f"""
        CREATE CONSTRAINT constraint_{label.lower()}_{prop} IF NOT EXISTS
        FOR (n:{label})
        REQUIRE n.{prop} IS UNIQUE
        """
        run_query(session, query, description=f"Constraint {label}.{prop}")


def create_indexes(session):
    """Create indexes for fast lookups."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE INDEKSÓW")
    logger.info("=" * 60)

    # =========================================================================
    # Parcel property indexes
    # =========================================================================
    parcel_indexes = [
        # Location
        "gmina", "dzielnica",
        # Size & geometry
        "area_m2", "size_category",
        # Building
        "is_built", "building_main_function", "building_type",
        # Planning
        "has_pog", "is_residential_zone", "pog_symbol",
        # Ownership
        "typ_wlasnosci", "grupa_rej_nazwa",
        # Scores
        "quietness_score", "nature_score", "accessibility_score",
        # Categories
        "kategoria_ciszy", "kategoria_natury", "kategoria_dostepu", "gestosc_zabudowy",
        # Water
        "dist_to_sea", "dist_to_river", "dist_to_lake", "nearest_water_type",
        # POI distances
        "dist_to_school", "dist_to_bus_stop", "dist_to_supermarket",
        "dist_to_forest", "dist_to_water", "dist_to_main_road",
    ]

    for prop in parcel_indexes:
        query = f"""
        CREATE INDEX idx_parcel_{prop} IF NOT EXISTS
        FOR (p:Parcel)
        ON (p.{prop})
        """
        run_query(session, query, description=f"Index Parcel.{prop}")

    # =========================================================================
    # Composite indexes for common multi-hop queries
    # =========================================================================
    composite_indexes = [
        # "Prywatna niezabudowana działka w Gdańsku"
        ("Parcel", ["gmina", "typ_wlasnosci", "is_built"]),
        # "Działka pod dom w cichej okolicy"
        ("Parcel", ["size_category", "kategoria_ciszy"]),
        # "Budowlana działka w dzielnicy"
        ("Parcel", ["dzielnica", "is_residential_zone"]),
        # "Działka blisko morza prywatna"
        ("Parcel", ["nearest_water_type", "typ_wlasnosci"]),
    ]

    for label, props in composite_indexes:
        props_str = ", ".join([f"n.{p}" for p in props])
        idx_name = f"idx_{label.lower()}_{'_'.join(props)}"
        query = f"""
        CREATE INDEX {idx_name} IF NOT EXISTS
        FOR (n:{label})
        ON ({props_str})
        """
        run_query(session, query, description=f"Composite index {idx_name}")

    # =========================================================================
    # POI indexes
    # =========================================================================
    poi_indexes = [
        ("Water", "water_type"),
        ("Water", "name"),
        ("School", "name"),
        ("BusStop", "name"),
        ("Shop", "shop_type"),
        ("Road", "type"),
    ]

    for label, prop in poi_indexes:
        query = f"""
        CREATE INDEX idx_{label.lower()}_{prop} IF NOT EXISTS
        FOR (n:{label})
        ON (n.{prop})
        """
        run_query(session, query, description=f"Index {label}.{prop}")

    # =========================================================================
    # POGZone indexes
    # =========================================================================
    pog_indexes = ["symbol", "is_residential", "gmina"]
    for prop in pog_indexes:
        query = f"""
        CREATE INDEX idx_pogzone_{prop} IF NOT EXISTS
        FOR (z:POGZone)
        ON (z.{prop})
        """
        run_query(session, query, description=f"Index POGZone.{prop}")

    # =========================================================================
    # Fulltext indexes for fuzzy search
    # =========================================================================
    logger.info("\n  Creating fulltext indexes...")

    fulltext_indexes = [
        ("district_names_ft", "District", ["name"]),
        ("city_names_ft", "City", ["name"]),
        ("parcel_locations_ft", "Parcel", ["dzielnica", "gmina"]),
        ("pog_zone_names_ft", "POGZone", ["nazwa", "oznaczenie"]),
    ]

    for idx_name, label, props in fulltext_indexes:
        props_str = ", ".join([f"n.{p}" for p in props])
        query = f"""
        CREATE FULLTEXT INDEX {idx_name} IF NOT EXISTS
        FOR (n:{label}) ON EACH [{props_str}]
        """
        run_query(session, query, description=f"Fulltext Index {idx_name}")


def create_vector_indexes(session):
    """Create vector indexes for similarity search."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE INDEKSÓW WEKTOROWYCH")
    logger.info("=" * 60)

    # =========================================================================
    # Entity Resolution vectors (512-dim, distiluse-base-multilingual)
    # =========================================================================
    logger.info("\n  Entity Resolution (512-dim)...")

    entity_vectors = [
        ("location_name_embedding_idx", "LocationName"),
        ("semantic_category_embedding_idx", "SemanticCategory"),
        ("water_type_name_embedding_idx", "WaterTypeName"),
        ("poi_type_name_embedding_idx", "POITypeName"),
    ]

    for idx_name, label in entity_vectors:
        query = f"""
        CREATE VECTOR INDEX {idx_name} IF NOT EXISTS
        FOR (n:{label}) ON (n.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: 512,
            `vector.similarity_function`: 'cosine'
        }}}}
        """
        run_query(session, query, description=f"Vector Index {idx_name}")

    # =========================================================================
    # Parcel TEXT embeddings (512-dim, sentence-transformers)
    # Użycie: semantic search - "szukam cichej działki blisko lasu"
    # =========================================================================
    logger.info("\n  Parcel text embeddings (512-dim, semantic search)...")

    query = """
    CREATE VECTOR INDEX parcel_text_embedding_idx IF NOT EXISTS
    FOR (p:Parcel) ON (p.text_embedding)
    OPTIONS {indexConfig: {
        `vector.dimensions`: 512,
        `vector.similarity_function`: 'cosine'
    }}
    """
    run_query(session, query, description="Vector Index parcel_text_embedding_idx (512-dim)")

    # =========================================================================
    # Parcel GRAPH embeddings (256-dim, FastRP from Neo4j GDS)
    # Użycie: similarity search - "znajdź podobne działki"
    # =========================================================================
    logger.info("\n  Parcel graph embeddings (256-dim, FastRP similarity)...")

    query = """
    CREATE VECTOR INDEX parcel_graph_embedding_idx IF NOT EXISTS
    FOR (p:Parcel) ON (p.graph_embedding)
    OPTIONS {indexConfig: {
        `vector.dimensions`: 256,
        `vector.similarity_function`: 'cosine'
    }}
    """
    run_query(session, query, description="Vector Index parcel_graph_embedding_idx (256-dim)")


def create_category_nodes(session):
    """Create all category nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE WĘZŁÓW KATEGORII")
    logger.info("=" * 60)

    # =========================================================================
    # Ownership Type (5 types)
    # =========================================================================
    logger.info("\n  OwnershipType nodes...")
    ownership_types = [
        {"id": "prywatna", "name_pl": "Prywatna", "can_buy": True, "priority": 1},
        {"id": "publiczna", "name_pl": "Publiczna", "can_buy": False, "priority": 5},
        {"id": "spoldzielcza", "name_pl": "Spółdzielcza", "can_buy": False, "priority": 4},
        {"id": "koscielna", "name_pl": "Kościelna", "can_buy": False, "priority": 3},
        {"id": "inna", "name_pl": "Inna", "can_buy": False, "priority": 2},
    ]
    for ot in ownership_types:
        query = """
        MERGE (o:OwnershipType {id: $id})
        SET o.name_pl = $name_pl, o.can_buy = $can_buy, o.priority = $priority
        """
        run_query(session, query, ot, f"OwnershipType: {ot['id']}")

    # =========================================================================
    # Ownership Group (15 groups)
    # =========================================================================
    logger.info("\n  OwnershipGroup nodes...")
    ownership_groups = [
        {"id": "osoby_fizyczne", "name_pl": "Osoby fizyczne", "ownership_type": "prywatna"},
        {"id": "gminy_wlasnosc", "name_pl": "Gminy (własność)", "ownership_type": "publiczna"},
        {"id": "gminy_zarzad", "name_pl": "Gminy (w zarządzie)", "ownership_type": "publiczna"},
        {"id": "skarb_panstwa", "name_pl": "Skarb Państwa", "ownership_type": "publiczna"},
        {"id": "skarb_panstwa_zarzad", "name_pl": "Skarb Państwa (w zarządzie)", "ownership_type": "publiczna"},
        {"id": "inne_publiczne", "name_pl": "Inne podmioty publiczne", "ownership_type": "publiczna"},
        {"id": "wojewodztwa_wlasnosc", "name_pl": "Województwa (własność)", "ownership_type": "publiczna"},
        {"id": "wojewodztwa_zarzad", "name_pl": "Województwa (w zarządzie)", "ownership_type": "publiczna"},
        {"id": "powiaty_wlasnosc", "name_pl": "Powiaty (własność)", "ownership_type": "publiczna"},
        {"id": "powiaty_zarzad", "name_pl": "Powiaty (w zarządzie)", "ownership_type": "publiczna"},
        {"id": "spoldzielnie", "name_pl": "Spółdzielnie", "ownership_type": "spoldzielcza"},
        {"id": "spolki_sp", "name_pl": "Spółki Skarbu Państwa", "ownership_type": "publiczna"},
        {"id": "spolki_komunalne", "name_pl": "Spółki komunalne", "ownership_type": "publiczna"},
        {"id": "koscioly", "name_pl": "Kościoły i związki wyznaniowe", "ownership_type": "koscielna"},
        {"id": "inne", "name_pl": "Inne", "ownership_type": "inna"},
    ]
    for og in ownership_groups:
        query = """
        MERGE (o:OwnershipGroup {id: $id})
        SET o.name_pl = $name_pl, o.ownership_type = $ownership_type
        """
        run_query(session, query, og, f"OwnershipGroup: {og['id']}")

    # =========================================================================
    # Build Status (2 statuses)
    # =========================================================================
    logger.info("\n  BuildStatus nodes...")
    build_statuses = [
        {"id": "zabudowana", "name_pl": "Zabudowana", "is_built": True},
        {"id": "niezabudowana", "name_pl": "Niezabudowana", "is_built": False},
    ]
    for bs in build_statuses:
        query = """
        MERGE (b:BuildStatus {id: $id})
        SET b.name_pl = $name_pl, b.is_built = $is_built
        """
        run_query(session, query, bs, f"BuildStatus: {bs['id']}")

    # =========================================================================
    # Building Function (11 functions)
    # =========================================================================
    logger.info("\n  BuildingFunction nodes...")
    building_functions = [
        {"id": "mieszkalne", "name_pl": "Mieszkalne", "is_residential": True},
        {"id": "gospodarcze", "name_pl": "Gospodarcze", "is_residential": False},
        {"id": "handlowo-uslugowe", "name_pl": "Handlowo-usługowe", "is_residential": False},
        {"id": "biurowe", "name_pl": "Biurowe", "is_residential": False},
        {"id": "przemyslowe", "name_pl": "Przemysłowe", "is_residential": False},
        {"id": "magazynowe", "name_pl": "Magazynowe", "is_residential": False},
        {"id": "transport", "name_pl": "Transport", "is_residential": False},
        {"id": "edukacja_kultura", "name_pl": "Edukacja/kultura", "is_residential": False},
        {"id": "zdrowie", "name_pl": "Zdrowie", "is_residential": False},
        {"id": "inne", "name_pl": "Inne", "is_residential": False},
    ]
    for bf in building_functions:
        query = """
        MERGE (b:BuildingFunction {id: $id})
        SET b.name_pl = $name_pl, b.is_residential = $is_residential
        """
        run_query(session, query, bf, f"BuildingFunction: {bf['id']}")

    # =========================================================================
    # Size Category (4 categories)
    # =========================================================================
    logger.info("\n  SizeCategory nodes...")
    size_categories = [
        {"id": "mala", "name_pl": "Mała (<500m²)", "min_m2": 0, "max_m2": 499, "good_for_house": False},
        {"id": "pod_dom", "name_pl": "Pod dom (500-2000m²)", "min_m2": 500, "max_m2": 1999, "good_for_house": True},
        {"id": "duza", "name_pl": "Duża (2000-5000m²)", "min_m2": 2000, "max_m2": 4999, "good_for_house": True},
        {"id": "bardzo_duza", "name_pl": "Bardzo duża (>5000m²)", "min_m2": 5000, "max_m2": 999999, "good_for_house": True},
    ]
    for sc in size_categories:
        query = """
        MERGE (s:SizeCategory {id: $id})
        SET s.name_pl = $name_pl, s.min_m2 = $min_m2, s.max_m2 = $max_m2, s.good_for_house = $good_for_house
        """
        run_query(session, query, sc, f"SizeCategory: {sc['id']}")

    # =========================================================================
    # POG Profile (15 profiles)
    # =========================================================================
    logger.info("\n  POGProfile nodes...")
    pog_profiles = [
        {"id": "MN", "name_pl": "Zabudowa jednorodzinna", "is_residential": True},
        {"id": "MW", "name_pl": "Zabudowa wielorodzinna", "is_residential": True},
        {"id": "U", "name_pl": "Usługi", "is_residential": False},
        {"id": "P", "name_pl": "Przemysł", "is_residential": False},
        {"id": "ZP", "name_pl": "Zieleń parkowa", "is_residential": False},
        {"id": "ZD", "name_pl": "Zieleń działkowa", "is_residential": False},
        {"id": "ZB", "name_pl": "Zieleń biologicznie czynna", "is_residential": False},
        {"id": "K", "name_pl": "Komunikacja", "is_residential": False},
        {"id": "W", "name_pl": "Wody", "is_residential": False},
        {"id": "I", "name_pl": "Infrastruktura", "is_residential": False},
        {"id": "R", "name_pl": "Rolnictwo", "is_residential": False},
        {"id": "L", "name_pl": "Las", "is_residential": False},
        {"id": "C", "name_pl": "Cmentarz", "is_residential": False},
        {"id": "N", "name_pl": "Tereny militarne", "is_residential": False},
        {"id": "O", "name_pl": "Ochrony zdrowia", "is_residential": False},
    ]
    for pp in pog_profiles:
        query = """
        MERGE (p:POGProfile {id: $id})
        SET p.name_pl = $name_pl, p.is_residential = $is_residential
        """
        run_query(session, query, pp, f"POGProfile: {pp['id']}")

    # =========================================================================
    # Quietness categories (existing)
    # =========================================================================
    logger.info("\n  QuietnessCategory nodes...")
    quietness = [
        {"id": "bardzo_cicha", "name_pl": "Bardzo cicha", "score_min": 80, "score_max": 100},
        {"id": "cicha", "name_pl": "Cicha", "score_min": 60, "score_max": 79},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 40, "score_max": 59},
        {"id": "glosna", "name_pl": "Głośna", "score_min": 0, "score_max": 39},
    ]
    for cat in quietness:
        query = """
        MERGE (c:QuietnessCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"QuietnessCategory: {cat['id']}")

    # =========================================================================
    # Nature categories (existing)
    # =========================================================================
    logger.info("\n  NatureCategory nodes...")
    nature = [
        {"id": "bardzo_zielona", "name_pl": "Bardzo zielona", "score_min": 70, "score_max": 100},
        {"id": "zielona", "name_pl": "Zielona", "score_min": 50, "score_max": 69},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 30, "score_max": 49},
        {"id": "zurbanizowana", "name_pl": "Zurbanizowana", "score_min": 0, "score_max": 29},
    ]
    for cat in nature:
        query = """
        MERGE (c:NatureCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"NatureCategory: {cat['id']}")

    # =========================================================================
    # Access categories (existing)
    # =========================================================================
    logger.info("\n  AccessCategory nodes...")
    access = [
        {"id": "doskonala", "name_pl": "Doskonała", "score_min": 70, "score_max": 100},
        {"id": "dobra", "name_pl": "Dobra", "score_min": 50, "score_max": 69},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "score_min": 30, "score_max": 49},
        {"id": "ograniczona", "name_pl": "Ograniczona", "score_min": 0, "score_max": 29},
    ]
    for cat in access:
        query = """
        MERGE (c:AccessCategory {id: $id})
        SET c.name_pl = $name_pl, c.score_min = $score_min, c.score_max = $score_max
        """
        run_query(session, query, cat, f"AccessCategory: {cat['id']}")

    # =========================================================================
    # Density categories (existing)
    # =========================================================================
    logger.info("\n  DensityCategory nodes...")
    density = [
        {"id": "gesta", "name_pl": "Gęsta", "buildings_min": 50, "buildings_max": 999999},
        {"id": "umiarkowana", "name_pl": "Umiarkowana", "buildings_min": 20, "buildings_max": 49},
        {"id": "rzadka", "name_pl": "Rzadka", "buildings_min": 5, "buildings_max": 19},
        {"id": "bardzo_rzadka", "name_pl": "Bardzo rzadka", "buildings_min": 0, "buildings_max": 4},
    ]
    for cat in density:
        query = """
        MERGE (c:DensityCategory {id: $id})
        SET c.name_pl = $name_pl, c.buildings_min = $buildings_min, c.buildings_max = $buildings_max
        """
        run_query(session, query, cat, f"DensityCategory: {cat['id']}")

    # =========================================================================
    # Water types (existing)
    # =========================================================================
    logger.info("\n  WaterType nodes...")
    water_types = [
        {"id": "morze", "name_pl": "Morze", "priority": 1, "premium_factor": 2.0},
        {"id": "zatoka", "name_pl": "Zatoka", "priority": 2, "premium_factor": 1.8},
        {"id": "jezioro", "name_pl": "Jezioro", "priority": 3, "premium_factor": 1.5},
        {"id": "rzeka", "name_pl": "Rzeka", "priority": 4, "premium_factor": 1.3},
        {"id": "kanal", "name_pl": "Kanał", "priority": 5, "premium_factor": 1.1},
        {"id": "staw", "name_pl": "Staw", "priority": 6, "premium_factor": 1.05},
    ]
    for wt in water_types:
        query = """
        MERGE (w:WaterType {id: $id})
        SET w.name_pl = $name_pl, w.priority = $priority, w.premium_factor = $premium_factor
        """
        run_query(session, query, wt, f"WaterType: {wt['id']}")

    # =========================================================================
    # Price segments (existing)
    # =========================================================================
    logger.info("\n  PriceSegment nodes...")
    price_segments = [
        {"id": "ULTRA_PREMIUM", "name_pl": "Ultra Premium", "price_min": 3000, "price_max": 999999},
        {"id": "PREMIUM", "name_pl": "Premium", "price_min": 1500, "price_max": 2999},
        {"id": "HIGH", "name_pl": "Wysoki", "price_min": 800, "price_max": 1499},
        {"id": "MEDIUM", "name_pl": "Średni", "price_min": 500, "price_max": 799},
        {"id": "BUDGET", "name_pl": "Budżetowy", "price_min": 300, "price_max": 499},
        {"id": "ECONOMY", "name_pl": "Ekonomiczny", "price_min": 0, "price_max": 299},
    ]
    for ps in price_segments:
        query = """
        MERGE (p:PriceSegment {id: $id})
        SET p.name_pl = $name_pl, p.price_min = $price_min, p.price_max = $price_max
        """
        run_query(session, query, ps, f"PriceSegment: {ps['id']}")


def create_city_nodes(session):
    """Create city (gmina) nodes."""
    logger.info("\n" + "=" * 60)
    logger.info("TWORZENIE WĘZŁÓW MIAST")
    logger.info("=" * 60)

    cities = [
        {"name": "Gdańsk", "wojewodztwo": "pomorskie", "powiat": "Gdańsk"},
        {"name": "Gdynia", "wojewodztwo": "pomorskie", "powiat": "Gdynia"},
        {"name": "Sopot", "wojewodztwo": "pomorskie", "powiat": "Sopot"},
    ]

    for city in cities:
        query = """
        MERGE (c:City {name: $name})
        SET c.wojewodztwo = $wojewodztwo, c.powiat = $powiat
        """
        run_query(session, query, city, f"City: {city['name']}")


def show_schema_summary(session):
    """Show summary of created schema."""
    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE SCHEMATU V2")
    logger.info("=" * 60)

    # Count nodes by label
    result = session.run("""
        CALL db.labels() YIELD label
        CALL {
            WITH label
            MATCH (n)
            WHERE label IN labels(n)
            RETURN count(n) AS cnt
        }
        RETURN label, cnt
        ORDER BY cnt DESC
    """)

    logger.info("\nWęzły:")
    for record in result:
        if record['cnt'] > 0:
            logger.info(f"  {record['label']}: {record['cnt']}")

    # Count indexes
    result = session.run("SHOW INDEXES")
    indexes = list(result)
    logger.info(f"\nIndeksy: {len(indexes)}")

    # Group by type
    idx_types = {}
    for idx in indexes:
        t = idx['type']
        idx_types[t] = idx_types.get(t, 0) + 1
    for t, cnt in sorted(idx_types.items()):
        logger.info(f"  {t}: {cnt}")

    # Count constraints
    result = session.run("SHOW CONSTRAINTS")
    constraints = list(result)
    logger.info(f"\nConstraints: {len(constraints)}")


def main():
    logger.info("=" * 60)
    logger.info("TWORZENIE SCHEMATU NEO4J V2")
    logger.info("=" * 60)
    logger.info(f"URI: {NEO4J_URI}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Optional: clean slate
            # drop_existing_indexes(session)

            # Create schema elements
            create_constraints(session)
            create_indexes(session)
            create_vector_indexes(session)
            create_category_nodes(session)
            create_city_nodes(session)
            show_schema_summary(session)

    finally:
        driver.close()

    logger.info("\n" + "=" * 60)
    logger.info("SCHEMAT V2 UTWORZONY")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
