#!/usr/bin/env python3
"""
import_neo4j.py - Import data into Neo4j graph database

Prerequisites:
1. Neo4j must be running
2. CSV files must be prepared (run prepare_neo4j_data.py first)
3. CSV files must be in Neo4j import directory

Usage:
    python import_neo4j.py [--uri bolt://localhost:7687] [--user neo4j] [--password <pwd>]
"""

import argparse
import logging
import os
from pathlib import Path
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default connection
DEFAULT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
DEFAULT_USER = os.environ.get("NEO4J_USER", "neo4j")
DEFAULT_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# Paths
PROJECT_DIR = Path("/home/marcin/moja-dzialka")
CSV_DIR = PROJECT_DIR / "data" / "ready-for-import" / "neo4j" / "csv"


class Neo4jImporter:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j at {uri}")

    def close(self):
        self.driver.close()

    def run_query(self, query: str, params: dict = None):
        """Run a single Cypher query."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return result.consume()

    def run_query_with_count(self, query: str, params: dict = None) -> int:
        """Run query and return affected count."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            summary = result.consume()
            return summary.counters.nodes_created + summary.counters.relationships_created

    # =========================================================================
    # PHASE 1: CONSTRAINTS
    # =========================================================================

    def create_constraints(self):
        """Create uniqueness constraints."""
        logger.info("Creating constraints...")

        constraints = [
            ("gmina_nazwa", "Gmina", "nazwa"),
            ("dzielnica_id", "Dzielnica", "id"),
            ("strefa_id", "StrefaPOG", "id"),
            ("profil_kod", "ProfilFunkcji", "kod"),
            ("cisza_poziom", "KategoriaCiszy", "poziom"),
            ("natura_poziom", "KategoriaNatury", "poziom"),
            ("dostepnosc_poziom", "KategoriaDostepnosci", "poziom"),
            ("powierzchnia_klasa", "KlasaPowierzchni", "klasa"),
            ("zabudowa_typ", "TypZabudowy", "typ"),
            ("dzialka_id", "Dzialka", "id"),
        ]

        for name, label, prop in constraints:
            query = f"""
            CREATE CONSTRAINT {name} IF NOT EXISTS
            FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE
            """
            try:
                self.run_query(query)
                logger.info(f"  ✓ Constraint: {name}")
            except Exception as e:
                logger.warning(f"  ⚠ Constraint {name}: {e}")

    # =========================================================================
    # PHASE 2: NODES
    # =========================================================================

    def import_small_nodes(self):
        """Import small static nodes."""
        logger.info("Importing small nodes...")

        # Gmina
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/gmina.csv' AS row
        CREATE (g:Gmina {
            teryt: row.teryt,
            nazwa: row.nazwa,
            wojewodztwo: row.wojewodztwo
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ Gmina: {count} nodes")

        # Dzielnica
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/dzielnica.csv' AS row
        CREATE (d:Dzielnica {
            id: row.id,
            nazwa: row.nazwa,
            gmina: row.gmina
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ Dzielnica: {count} nodes")

        # ProfilFunkcji
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/profil_funkcji.csv' AS row
        CREATE (p:ProfilFunkcji {
            kod: row.kod,
            nazwa: row.nazwa
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ ProfilFunkcji: {count} nodes")

        # Categories
        for label, filename in [
            ("KategoriaCiszy", "kategoria_ciszy.csv"),
            ("KategoriaNatury", "kategoria_natury.csv"),
            ("KategoriaDostepnosci", "kategoria_dostepnosci.csv"),
        ]:
            query = f"""
            LOAD CSV WITH HEADERS FROM 'file:///nodes/{filename}' AS row
            CREATE (n:{label} {{
                poziom: row.poziom,
                opis: row.opis,
                score_min: toInteger(row.score_min)
            }})
            """
            count = self.run_query_with_count(query)
            logger.info(f"  ✓ {label}: {count} nodes")

        # KlasaPowierzchni
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/klasa_powierzchni.csv' AS row
        CREATE (p:KlasaPowierzchni {
            klasa: row.klasa,
            zakres: row.zakres,
            min_m2: toInteger(row.min_m2),
            max_m2: toInteger(row.max_m2)
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ KlasaPowierzchni: {count} nodes")

        # TypZabudowy
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/typ_zabudowy.csv' AS row
        CREATE (t:TypZabudowy {
            typ: row.typ,
            opis: row.opis
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ TypZabudowy: {count} nodes")

    def import_strefy_pog(self):
        """Import StrefaPOG nodes."""
        logger.info("Importing StrefaPOG nodes...")

        query = """
        LOAD CSV WITH HEADERS FROM 'file:///nodes/strefa_pog.csv' AS row
        CREATE (s:StrefaPOG {
            id: row.id,
            gmina: row.gmina,
            oznaczenie: row.oznaczenie,
            symbol: row.symbol,
            nazwa: row.nazwa,
            profil_podstawowy: row.profil_podstawowy,
            profil_dodatkowy: row.profil_dodatkowy,
            maks_intensywnosc: toFloat(row.maks_intensywnosc),
            maks_zabudowa_pct: toFloat(row.maks_zabudowa_pct),
            maks_wysokosc_m: toFloat(row.maks_wysokosc_m),
            min_bio_pct: toFloat(row.min_bio_pct)
        })
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ StrefaPOG: {count} nodes")

    def import_dzialki(self, batch_size: int = 5000):
        """Import Dzialka nodes in batches."""
        logger.info("Importing Dzialka nodes (this may take a while)...")

        query = f"""
        CALL apoc.periodic.iterate(
            "LOAD CSV WITH HEADERS FROM 'file:///nodes/dzialka.csv' AS row RETURN row",
            "CREATE (d:Dzialka:Pomorskie {{
                id: row.id,
                area_m2: toFloat(row.area_m2),
                centroid_lat: toFloat(row.centroid_lat),
                centroid_lon: toFloat(row.centroid_lon),
                quietness_score: toInteger(row.quietness_score),
                nature_score: toInteger(row.nature_score),
                accessibility_score: toInteger(row.accessibility_score),
                shape_index: toFloat(row.shape_index)
            }})",
            {{batchSize: {batch_size}, parallel: false}}
        )
        YIELD batches, total, errorMessages
        RETURN batches, total, errorMessages
        """
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            logger.info(f"  ✓ Dzialka: {record['total']} nodes in {record['batches']} batches")

    # =========================================================================
    # PHASE 3: RELATIONSHIPS
    # =========================================================================

    def import_small_relationships(self):
        """Import small relationship sets."""
        logger.info("Importing small relationships...")

        # Dzielnica -> Gmina
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///relationships/dzielnica_nalezy_do_gmina.csv' AS row
        MATCH (d:Dzielnica {id: row.dzielnica_id})
        MATCH (g:Gmina {nazwa: row.gmina_nazwa})
        CREATE (d)-[:NALEZY_DO]->(g)
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ NALEZY_DO: {count} rels")

        # StrefaPOG -> ProfilFunkcji
        query = """
        LOAD CSV WITH HEADERS FROM 'file:///relationships/strefa_dozwala_profil.csv' AS row
        MATCH (s:StrefaPOG {id: row.strefa_id})
        MATCH (p:ProfilFunkcji {kod: row.profil_kod})
        CREATE (s)-[:DOZWALA {typ: row.typ}]->(p)
        """
        count = self.run_query_with_count(query)
        logger.info(f"  ✓ DOZWALA: {count} rels")

    def import_dzialka_relationships(self, batch_size: int = 5000):
        """Import Dzialka relationships in batches."""
        logger.info("Importing Dzialka relationships (this may take a while)...")

        relationships = [
            ("dzialka_w_gminie.csv", "W_GMINIE", "Gmina", "nazwa", "gmina_nazwa", None),
            ("dzialka_w_dzielnicy.csv", "W_DZIELNICY", "Dzielnica", "id", "dzielnica_id", None),
            ("dzialka_w_strefie_pog.csv", "W_STREFIE_POG", "StrefaPOG", "id", "strefa_id", None),
            ("dzialka_ma_cisze.csv", "MA_CISZE", "KategoriaCiszy", "poziom", "poziom", None),
            ("dzialka_ma_nature.csv", "MA_NATURE", "KategoriaNatury", "poziom", "poziom", None),
            ("dzialka_ma_dostepnosc.csv", "MA_DOSTEPNOSC", "KategoriaDostepnosci", "poziom", "poziom", None),
            ("dzialka_ma_powierzchnie.csv", "MA_POWIERZCHNIE", "KlasaPowierzchni", "klasa", "klasa", None),
            ("dzialka_mozna_zabudowac.csv", "MOZNA_ZABUDOWAC", "TypZabudowy", "typ", "typ", None),
        ]

        for filename, rel_type, target_label, target_prop, csv_col, rel_props in relationships:
            props_str = ""
            if rel_props:
                props_str = " {" + ", ".join(f"{k}: row.{v}" for k, v in rel_props.items()) + "}"

            query = f"""
            CALL apoc.periodic.iterate(
                "LOAD CSV WITH HEADERS FROM 'file:///relationships/{filename}' AS row RETURN row",
                "MATCH (d:Dzialka {{id: row.dzialka_id}})
                 MATCH (t:{target_label} {{{target_prop}: row.{csv_col}}})
                 CREATE (d)-[:{rel_type}{props_str}]->(t)",
                {{batchSize: {batch_size}, parallel: false}}
            )
            YIELD batches, total, errorMessages
            RETURN batches, total, errorMessages
            """
            with self.driver.session() as session:
                result = session.run(query)
                record = result.single()
                logger.info(f"  ✓ {rel_type}: {record['total']} rels")

    # =========================================================================
    # PHASE 4: INDEXES
    # =========================================================================

    def create_indexes(self):
        """Create indexes for query performance."""
        logger.info("Creating indexes...")

        indexes = [
            ("Dzialka", "area_m2"),
            ("Dzialka", "quietness_score"),
            ("Dzialka", "nature_score"),
            ("Dzialka", "accessibility_score"),
            ("StrefaPOG", "symbol"),
            ("Dzielnica", "gmina"),
        ]

        for label, prop in indexes:
            name = f"idx_{label.lower()}_{prop}"
            query = f"""
            CREATE INDEX {name} IF NOT EXISTS
            FOR (n:{label}) ON (n.{prop})
            """
            try:
                self.run_query(query)
                logger.info(f"  ✓ Index: {name}")
            except Exception as e:
                logger.warning(f"  ⚠ Index {name}: {e}")

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def verify_import(self):
        """Verify the import was successful."""
        logger.info("Verifying import...")

        # Count nodes
        query = """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(*) AS count
        ORDER BY count DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            logger.info("  Node counts:")
            for record in result:
                logger.info(f"    {record['label']}: {record['count']:,}")

        # Count relationships
        query = """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        ORDER BY count DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            logger.info("  Relationship counts:")
            for record in result:
                logger.info(f"    {record['type']}: {record['count']:,}")

        # Sample query
        query = """
        MATCH (d:Dzialka)-[:W_GMINIE]->(:Gmina {nazwa: "Gdańsk"})
        MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)
        WHERE c.poziom IN ['bardzo_cicha', 'cicha']
        RETURN count(d) AS quiet_parcels_gdansk
        """
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            logger.info(f"  Sample query (quiet parcels in Gdańsk): {record['quiet_parcels_gdansk']:,}")


def main():
    parser = argparse.ArgumentParser(description="Import data into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j user")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--skip-constraints", action="store_true", help="Skip constraint creation")
    parser.add_argument("--skip-nodes", action="store_true", help="Skip node import")
    parser.add_argument("--skip-relationships", action="store_true", help="Skip relationship import")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("NEO4J IMPORT")
    logger.info("=" * 60)

    # Check CSV files exist
    if not CSV_DIR.exists():
        logger.error(f"CSV directory not found: {CSV_DIR}")
        logger.error("Run prepare_neo4j_data.py first!")
        return 1

    logger.info(f"CSV source: {CSV_DIR}")
    logger.info(f"NOTE: Copy CSV files to Neo4j import directory before running!")
    logger.info("")

    importer = Neo4jImporter(args.uri, args.user, args.password)

    try:
        # Phase 1: Constraints
        if not args.skip_constraints:
            importer.create_constraints()

        # Phase 2: Nodes
        if not args.skip_nodes:
            importer.import_small_nodes()
            importer.import_strefy_pog()
            importer.import_dzialki()

        # Phase 3: Relationships
        if not args.skip_relationships:
            importer.import_small_relationships()
            importer.import_dzialka_relationships()

        # Phase 4: Indexes
        importer.create_indexes()

        # Verify
        importer.verify_import()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ NEO4J IMPORT COMPLETE")
        logger.info("=" * 60)

    finally:
        importer.close()

    return 0


if __name__ == "__main__":
    exit(main())
