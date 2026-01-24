// =============================================================================
// NEO4J IMPORT SCRIPT - moja-dzialka Domain Graph
// =============================================================================
//
// Usage:
//   1. Copy CSV files to Neo4j import directory
//   2. Run this script in Neo4j Browser or via cypher-shell
//
// Order is CRITICAL:
//   1. Create constraints (for uniqueness and performance)
//   2. Create all nodes first
//   3. Create relationships after all nodes exist
// =============================================================================


// =============================================================================
// PHASE 1: CONSTRAINTS (must run first!)
// =============================================================================

// Gmina
CREATE CONSTRAINT gmina_nazwa IF NOT EXISTS
FOR (g:Gmina) REQUIRE g.nazwa IS UNIQUE;

// Dzielnica
CREATE CONSTRAINT dzielnica_id IF NOT EXISTS
FOR (d:Dzielnica) REQUIRE d.id IS UNIQUE;

// StrefaPOG
CREATE CONSTRAINT strefa_id IF NOT EXISTS
FOR (s:StrefaPOG) REQUIRE s.id IS UNIQUE;

// ProfilFunkcji
CREATE CONSTRAINT profil_kod IF NOT EXISTS
FOR (p:ProfilFunkcji) REQUIRE p.kod IS UNIQUE;

// Kategorie
CREATE CONSTRAINT cisza_poziom IF NOT EXISTS
FOR (c:KategoriaCiszy) REQUIRE c.poziom IS UNIQUE;

CREATE CONSTRAINT natura_poziom IF NOT EXISTS
FOR (n:KategoriaNatury) REQUIRE n.poziom IS UNIQUE;

CREATE CONSTRAINT dostepnosc_poziom IF NOT EXISTS
FOR (d:KategoriaDostepnosci) REQUIRE d.poziom IS UNIQUE;

CREATE CONSTRAINT powierzchnia_klasa IF NOT EXISTS
FOR (p:KlasaPowierzchni) REQUIRE p.klasa IS UNIQUE;

CREATE CONSTRAINT zabudowa_typ IF NOT EXISTS
FOR (t:TypZabudowy) REQUIRE t.typ IS UNIQUE;

// Dzialka
CREATE CONSTRAINT dzialka_id IF NOT EXISTS
FOR (d:Dzialka) REQUIRE d.id IS UNIQUE;


// =============================================================================
// PHASE 2: CREATE NODES
// =============================================================================

// --- Gmina (3 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/gmina.csv' AS row
CREATE (g:Gmina {
    teryt: row.teryt,
    nazwa: row.nazwa,
    wojewodztwo: row.wojewodztwo
});

// --- Dzielnica (138 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/dzielnica.csv' AS row
CREATE (d:Dzielnica {
    id: row.id,
    nazwa: row.nazwa,
    gmina: row.gmina
});

// --- StrefaPOG (7,523 nodes) ---
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
});

// --- ProfilFunkcji (45 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/profil_funkcji.csv' AS row
CREATE (p:ProfilFunkcji {
    kod: row.kod,
    nazwa: row.nazwa
});

// --- KategoriaCiszy (4 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/kategoria_ciszy.csv' AS row
CREATE (c:KategoriaCiszy {
    poziom: row.poziom,
    opis: row.opis,
    score_min: toInteger(row.score_min)
});

// --- KategoriaNatury (4 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/kategoria_natury.csv' AS row
CREATE (n:KategoriaNatury {
    poziom: row.poziom,
    opis: row.opis,
    score_min: toInteger(row.score_min)
});

// --- KategoriaDostepnosci (4 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/kategoria_dostepnosci.csv' AS row
CREATE (d:KategoriaDostepnosci {
    poziom: row.poziom,
    opis: row.opis,
    score_min: toInteger(row.score_min)
});

// --- KlasaPowierzchni (4 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/klasa_powierzchni.csv' AS row
CREATE (p:KlasaPowierzchni {
    klasa: row.klasa,
    zakres: row.zakres,
    min_m2: toInteger(row.min_m2),
    max_m2: toInteger(row.max_m2)
});

// --- TypZabudowy (13 nodes) ---
LOAD CSV WITH HEADERS FROM 'file:///nodes/typ_zabudowy.csv' AS row
CREATE (t:TypZabudowy {
    typ: row.typ,
    opis: row.opis
});

// --- Dzialka (154,959 nodes) - use PERIODIC COMMIT for large imports ---
:auto LOAD CSV WITH HEADERS FROM 'file:///nodes/dzialka.csv' AS row
CALL {
    WITH row
    CREATE (d:Dzialka:Pomorskie {
        id: row.id,
        area_m2: toFloat(row.area_m2),
        centroid_lat: toFloat(row.centroid_lat),
        centroid_lon: toFloat(row.centroid_lon),
        quietness_score: toInteger(row.quietness_score),
        nature_score: toInteger(row.nature_score),
        accessibility_score: toInteger(row.accessibility_score),
        shape_index: toFloat(row.shape_index)
    })
} IN TRANSACTIONS OF 5000 ROWS;


// =============================================================================
// PHASE 3: CREATE RELATIONSHIPS
// =============================================================================

// --- Dzielnica -[NALEZY_DO]-> Gmina ---
LOAD CSV WITH HEADERS FROM 'file:///relationships/dzielnica_nalezy_do_gmina.csv' AS row
MATCH (d:Dzielnica {id: row.dzielnica_id})
MATCH (g:Gmina {nazwa: row.gmina_nazwa})
CREATE (d)-[:NALEZY_DO]->(g);

// --- Dzialka -[W_GMINIE]-> Gmina ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_w_gminie.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (g:Gmina {nazwa: row.gmina_nazwa})
    CREATE (d)-[:W_GMINIE]->(g)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[W_DZIELNICY]-> Dzielnica ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_w_dzielnicy.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (dz:Dzielnica {id: row.dzielnica_id})
    CREATE (d)-[:W_DZIELNICY]->(dz)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[W_STREFIE_POG]-> StrefaPOG ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_w_strefie_pog.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (s:StrefaPOG {id: row.strefa_id})
    CREATE (d)-[:W_STREFIE_POG]->(s)
} IN TRANSACTIONS OF 5000 ROWS;

// --- StrefaPOG -[DOZWALA]-> ProfilFunkcji ---
LOAD CSV WITH HEADERS FROM 'file:///relationships/strefa_dozwala_profil.csv' AS row
MATCH (s:StrefaPOG {id: row.strefa_id})
MATCH (p:ProfilFunkcji {kod: row.profil_kod})
CREATE (s)-[:DOZWALA {typ: row.typ}]->(p);

// --- Dzialka -[MA_CISZE]-> KategoriaCiszy ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_ma_cisze.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (c:KategoriaCiszy {poziom: row.poziom})
    CREATE (d)-[:MA_CISZE]->(c)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[MA_NATURE]-> KategoriaNatury ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_ma_nature.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (n:KategoriaNatury {poziom: row.poziom})
    CREATE (d)-[:MA_NATURE]->(n)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[MA_DOSTEPNOSC]-> KategoriaDostepnosci ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_ma_dostepnosc.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (a:KategoriaDostepnosci {poziom: row.poziom})
    CREATE (d)-[:MA_DOSTEPNOSC]->(a)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[MA_POWIERZCHNIE]-> KlasaPowierzchni ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_ma_powierzchnie.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (p:KlasaPowierzchni {klasa: row.klasa})
    CREATE (d)-[:MA_POWIERZCHNIE]->(p)
} IN TRANSACTIONS OF 5000 ROWS;

// --- Dzialka -[MOZNA_ZABUDOWAC]-> TypZabudowy ---
:auto LOAD CSV WITH HEADERS FROM 'file:///relationships/dzialka_mozna_zabudowac.csv' AS row
CALL {
    WITH row
    MATCH (d:Dzialka {id: row.dzialka_id})
    MATCH (t:TypZabudowy {typ: row.typ})
    CREATE (d)-[:MOZNA_ZABUDOWAC]->(t)
} IN TRANSACTIONS OF 5000 ROWS;


// =============================================================================
// PHASE 4: CREATE INDEXES (for query performance)
// =============================================================================

// Indexes for common query patterns
CREATE INDEX dzialka_area IF NOT EXISTS FOR (d:Dzialka) ON (d.area_m2);
CREATE INDEX dzialka_quietness IF NOT EXISTS FOR (d:Dzialka) ON (d.quietness_score);
CREATE INDEX dzialka_nature IF NOT EXISTS FOR (d:Dzialka) ON (d.nature_score);
CREATE INDEX dzialka_accessibility IF NOT EXISTS FOR (d:Dzialka) ON (d.accessibility_score);

CREATE INDEX strefa_symbol IF NOT EXISTS FOR (s:StrefaPOG) ON (s.symbol);
CREATE INDEX dzielnica_gmina IF NOT EXISTS FOR (d:Dzielnica) ON (d.gmina);


// =============================================================================
// PHASE 5: VERIFICATION QUERIES
// =============================================================================

// Count all nodes
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC;

// Count all relationships
MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC;

// Sample query: Find quiet parcels in Gdańsk for single-family homes
MATCH (d:Dzialka)-[:W_GMINIE]->(:Gmina {nazwa: "Gdańsk"})
MATCH (d)-[:MA_CISZE]->(c:KategoriaCiszy)
WHERE c.poziom IN ['bardzo_cicha', 'cicha']
MATCH (d)-[:MOZNA_ZABUDOWAC]->(:TypZabudowy {typ: 'jednorodzinna'})
MATCH (d)-[:MA_POWIERZCHNIE]->(:KlasaPowierzchni {klasa: 'pod_dom'})
RETURN d.id, d.area_m2, d.quietness_score, c.poziom
ORDER BY d.quietness_score DESC
LIMIT 10;
