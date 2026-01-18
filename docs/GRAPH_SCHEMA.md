# Neo4j Graph Schema

## Overview

The knowledge graph stores local zoning plan (MPZP) information and relationships to cadastral parcels. This enables rich queries about building regulations and constraints.

## Node Types

### Administrative Hierarchy

```cypher
// Voivodeship (Wojewodztwo)
(:Wojewodztwo {
  teryt: "22",
  nazwa: "pomorskie"
})

// County (Powiat)
(:Powiat {
  teryt: "2261",
  nazwa: "Gdansk",
  typ: "miasto na prawach powiatu"  // or "powiat"
})

// Municipality (Gmina)
(:Gmina {
  teryt: "226101",
  nazwa: "Gdansk",
  typ: "gmina miejska"  // gmina miejska, gmina wiejska, gmina miejsko-wiejska
})

// Locality (Miejscowosc)
(:Miejscowosc {
  teryt: "0933011",
  nazwa: "Orunia Gorna",
  typ: "dzielnica"  // miasto, wies, dzielnica, osiedle
})
```

### Zoning Plans

```cypher
// Local Zoning Plan (MPZP)
(:MPZP {
  id: "mpzp-gdansk-2023-001",
  numer_uchwaly: "XLII/1234/2023",
  data_uchwalenia: date("2023-06-15"),
  obowiazuje_od: date("2023-09-01"),
  tytul: "Miejscowy plan zagospodarowania przestrzennego Orunia Gorna rejon ul. Platynowej",
  status: "obowiazujacy",  // obowiazujacy, uchylony, w_opracowaniu
  link_uchwala: "https://bip.gdansk.pl/...",
  link_rysunek: "https://...",
  powierzchnia_ha: 45.7
})

// Zoning Area within MPZP (Teren)
(:TerenMPZP {
  id: "mpzp-gdansk-2023-001-1MN",
  symbol: "1MN",
  przeznaczenie_podstawowe: "zabudowa mieszkaniowa jednorodzinna",
  przeznaczenie_dopuszczalne: ["uslugowa nieuciazliwa", "zielen urzadzona"],
  opis: "Teren zabudowy mieszkaniowej jednorodzinnej wolnostojącej i bliźniaczej"
})

// Standard Zoning Symbol
(:SymbolMPZP {
  kod: "MN",
  nazwa: "Zabudowa mieszkaniowa jednorodzinna",
  kategoria: "mieszkaniowa",
  opis: "Tereny przeznaczone pod budownictwo mieszkaniowe jednorodzinne"
})
```

### Building Parameters

```cypher
// Building Parameter
(:ParametrZabudowy {
  id: "param-001",
  typ: "max_wysokosc",
  wartosc: "12",
  jednostka: "m",
  opis: "maksymalna wysokość zabudowy"
})

// Common parameter types:
// - max_wysokosc (m)
// - max_liczba_kondygnacji (int)
// - intensywnosc_zabudowy (float, e.g., 0.8)
// - pow_zabudowy_max (%, e.g., 40)
// - pow_biologicznie_czynna_min (%, e.g., 30)
// - linia_zabudowy_obowiazujaca (m from road)
// - linia_zabudowy_nieprzekraczalna (m from road)
// - min_pow_dzialki (m2)
// - szerokosc_frontu_min (m)
// - geometria_dachu (typ, e.g., "dwuspadowy", "wielospadowy", "płaski")
// - kat_nachylenia_dachu (degrees range, e.g., "30-45")
```

### Restrictions and Constraints

```cypher
// Restriction/Constraint
(:Ograniczenie {
  id: "ogr-001",
  typ: "strefa_ochrony_konserwatorskiej",
  kategoria: "ochrona_zabytkow",
  opis: "Strefa A ochrony konserwatorskiej - pełna ochrona substancji zabytkowej",
  wymogi: ["uzgodnienie z konserwatorem zabytkow", "zachowanie historycznej linii zabudowy"]
})

// Common restriction types:
// - strefa_ochrony_konserwatorskiej (A, B, K)
// - strefa_ochrony_archeologicznej
// - strefa_ochrony_krajobrazowej
// - obszar_natura_2000
// - pas_techniczny_wybrzeza
// - strefa_ochronna_ujecia_wody
// - obszar_zalewowy
// - strefa_ograniczen_lotniska
// - linia_wysokiego_napiecia
```

### Cadastral Parcels

```cypher
// Cadastral Parcel (Dzialka)
(:Dzialka {
  id: "226101_2.0001.123/4",
  teryt: "226101",
  obreb: "0001",
  nr_ewidencyjny: "123/4",
  powierzchnia_m2: 1250.5,
  centroid_lat: 54.3456,
  centroid_lon: 18.6789,
  has_mpzp: true,
  embedding_id: 12345
})
```

## Relationships

### Administrative Hierarchy

```cypher
(:Gmina)-[:NALEZY_DO]->(:Powiat)
(:Powiat)-[:NALEZY_DO]->(:Wojewodztwo)
(:Miejscowosc)-[:NALEZY_DO]->(:Gmina)
```

### Zoning Plans

```cypher
// Gmina owns MPZP
(:Gmina)-[:POSIADA_MPZP]->(:MPZP)

// MPZP defines zoning areas
(:MPZP)-[:WYZNACZA_TEREN]->(:TerenMPZP)

// Zoning area has standard symbol
(:TerenMPZP)-[:MA_SYMBOL]->(:SymbolMPZP)

// Zoning area has parameters
(:TerenMPZP)-[:MA_PARAMETR {
  zrodlo: "tekst uchwaly",
  paragraf: "§12 ust. 2"
}]->(:ParametrZabudowy)

// Zoning area has restrictions
(:TerenMPZP)-[:MA_OGRANICZENIE]->(:Ograniczenie)
```

### Parcel Relationships

```cypher
// Parcel is in locality
(:Dzialka)-[:W_MIEJSCOWOSCI]->(:Miejscowosc)

// Parcel is in zoning area (may be partial)
(:Dzialka)-[:W_TERENIE {
  procent_powierzchni: 100,  // % of parcel in this zoning area
  data_przypisania: date("2024-01-15")
}]->(:TerenMPZP)

// Parcel is covered by MPZP (derived relationship)
(:Dzialka)-[:OBJETA_MPZP]->(:MPZP)
```

## Example Data

### Creating Sample Data

```cypher
// Create administrative hierarchy
CREATE (woj:Wojewodztwo {teryt: "22", nazwa: "pomorskie"})

CREATE (pow:Powiat {teryt: "2261", nazwa: "Gdansk", typ: "miasto na prawach powiatu"})
CREATE (pow)-[:NALEZY_DO]->(woj)

CREATE (gm:Gmina {teryt: "226101", nazwa: "Gdansk", typ: "gmina miejska"})
CREATE (gm)-[:NALEZY_DO]->(pow)

CREATE (msc:Miejscowosc {teryt: "0933011", nazwa: "Orunia Gorna", typ: "dzielnica"})
CREATE (msc)-[:NALEZY_DO]->(gm)

// Create MPZP
CREATE (mpzp:MPZP {
  id: "mpzp-gdansk-2023-001",
  numer_uchwaly: "XLII/1234/2023",
  data_uchwalenia: date("2023-06-15"),
  tytul: "MPZP Orunia Gorna rejon ul. Platynowej",
  status: "obowiazujacy"
})
CREATE (gm)-[:POSIADA_MPZP]->(mpzp)

// Create zoning symbol
CREATE (sym:SymbolMPZP {
  kod: "MN",
  nazwa: "Zabudowa mieszkaniowa jednorodzinna",
  kategoria: "mieszkaniowa"
})

// Create zoning area
CREATE (teren:TerenMPZP {
  id: "mpzp-gdansk-2023-001-1MN",
  symbol: "1MN",
  przeznaczenie_podstawowe: "zabudowa mieszkaniowa jednorodzinna"
})
CREATE (mpzp)-[:WYZNACZA_TEREN]->(teren)
CREATE (teren)-[:MA_SYMBOL]->(sym)

// Create parameters
CREATE (p1:ParametrZabudowy {typ: "max_wysokosc", wartosc: "12", jednostka: "m"})
CREATE (p2:ParametrZabudowy {typ: "intensywnosc_zabudowy", wartosc: "0.4", jednostka: ""})
CREATE (p3:ParametrZabudowy {typ: "pow_biologicznie_czynna_min", wartosc: "40", jednostka: "%"})

CREATE (teren)-[:MA_PARAMETR {paragraf: "§12"}]->(p1)
CREATE (teren)-[:MA_PARAMETR {paragraf: "§12"}]->(p2)
CREATE (teren)-[:MA_PARAMETR {paragraf: "§13"}]->(p3)

// Create parcel
CREATE (dz:Dzialka {
  id: "226101_2.0001.123/4",
  teryt: "226101",
  obreb: "0001",
  nr_ewidencyjny: "123/4",
  powierzchnia_m2: 1250.5,
  has_mpzp: true
})
CREATE (dz)-[:W_MIEJSCOWOSCI]->(msc)
CREATE (dz)-[:W_TERENIE {procent_powierzchni: 100}]->(teren)
CREATE (dz)-[:OBJETA_MPZP]->(mpzp)
```

## Query Examples

### 1. Find parcel zoning information

```cypher
// Get all MPZP info for a specific parcel
MATCH (dz:Dzialka {nr_ewidencyjny: "123/4"})-[:W_TERENIE]->(teren:TerenMPZP)
MATCH (teren)-[:MA_SYMBOL]->(sym:SymbolMPZP)
MATCH (teren)<-[:WYZNACZA_TEREN]-(mpzp:MPZP)
OPTIONAL MATCH (teren)-[:MA_PARAMETR]->(param:ParametrZabudowy)
OPTIONAL MATCH (teren)-[:MA_OGRANICZENIE]->(ogr:Ograniczenie)
RETURN dz.nr_ewidencyjny,
       mpzp.tytul,
       teren.symbol,
       sym.nazwa as przeznaczenie,
       collect(DISTINCT {typ: param.typ, wartosc: param.wartosc, jednostka: param.jednostka}) as parametry,
       collect(DISTINCT ogr.typ) as ograniczenia
```

### 2. Find parcels by zoning type

```cypher
// Find all parcels with single-family residential zoning in Gdansk
MATCH (gm:Gmina {nazwa: "Gdansk"})-[:POSIADA_MPZP]->(mpzp:MPZP)
MATCH (mpzp)-[:WYZNACZA_TEREN]->(teren:TerenMPZP)-[:MA_SYMBOL]->(sym:SymbolMPZP {kod: "MN"})
MATCH (dz:Dzialka)-[:W_TERENIE]->(teren)
WHERE dz.powierzchnia_m2 >= 800 AND dz.powierzchnia_m2 <= 1500
RETURN dz.id, dz.powierzchnia_m2, teren.symbol, mpzp.tytul
ORDER BY dz.powierzchnia_m2
LIMIT 100
```

### 3. Get building parameters for parcel

```cypher
// Get all building parameters for parcel
MATCH (dz:Dzialka {id: $parcel_id})-[:W_TERENIE]->(teren:TerenMPZP)
MATCH (teren)-[r:MA_PARAMETR]->(param:ParametrZabudowy)
RETURN param.typ as parametr,
       param.wartosc as wartosc,
       param.jednostka as jednostka,
       r.paragraf as zrodlo
ORDER BY param.typ
```

### 4. Check if building is allowed

```cypher
// Check if single-family house can be built
MATCH (dz:Dzialka {id: $parcel_id})-[:W_TERENIE]->(teren:TerenMPZP)
MATCH (teren)-[:MA_SYMBOL]->(sym:SymbolMPZP)
WHERE sym.kod IN ['MN', 'MN/U']
OPTIONAL MATCH (teren)-[:MA_OGRANICZENIE]->(ogr:Ograniczenie)
RETURN sym.kod as przeznaczenie,
       sym.nazwa as opis,
       CASE WHEN sym.kod IN ['MN', 'MN/U'] THEN true ELSE false END as mozna_budowac_dom,
       collect(ogr.typ) as ograniczenia
```

### 5. Find parcels with specific parameters

```cypher
// Find parcels allowing buildings up to 12m height with intensity > 0.5
MATCH (dz:Dzialka)-[:W_TERENIE]->(teren:TerenMPZP)
MATCH (teren)-[:MA_PARAMETR]->(p1:ParametrZabudowy {typ: "max_wysokosc"})
MATCH (teren)-[:MA_PARAMETR]->(p2:ParametrZabudowy {typ: "intensywnosc_zabudowy"})
WHERE toFloat(p1.wartosc) >= 12 AND toFloat(p2.wartosc) >= 0.5
MATCH (teren)-[:MA_SYMBOL]->(sym:SymbolMPZP)
RETURN dz.id,
       dz.powierzchnia_m2,
       sym.kod,
       p1.wartosc as max_wysokosc,
       p2.wartosc as intensywnosc
ORDER BY toFloat(p2.wartosc) DESC
LIMIT 50
```

### 6. Statistics by municipality

```cypher
// Get MPZP coverage statistics by gmina
MATCH (gm:Gmina)-[:POSIADA_MPZP]->(mpzp:MPZP)
WITH gm, count(mpzp) as liczba_mpzp
MATCH (dz:Dzialka)-[:W_MIEJSCOWOSCI]->(msc:Miejscowosc)-[:NALEZY_DO]->(gm)
WITH gm, liczba_mpzp, count(dz) as wszystkie_dzialki
MATCH (dz:Dzialka {has_mpzp: true})-[:W_MIEJSCOWOSCI]->(msc:Miejscowosc)-[:NALEZY_DO]->(gm)
RETURN gm.nazwa,
       liczba_mpzp,
       wszystkie_dzialki,
       count(dz) as dzialki_z_mpzp,
       round(count(dz) * 100.0 / wszystkie_dzialki, 1) as procent_pokrycia
ORDER BY procent_pokrycia DESC
```

## Indexes

```cypher
// Create indexes for performance
CREATE INDEX idx_dzialka_id FOR (d:Dzialka) ON (d.id);
CREATE INDEX idx_dzialka_teryt FOR (d:Dzialka) ON (d.teryt);
CREATE INDEX idx_dzialka_nr FOR (d:Dzialka) ON (d.nr_ewidencyjny);
CREATE INDEX idx_mpzp_status FOR (m:MPZP) ON (m.status);
CREATE INDEX idx_teren_symbol FOR (t:TerenMPZP) ON (t.symbol);
CREATE INDEX idx_symbol_kod FOR (s:SymbolMPZP) ON (s.kod);
CREATE INDEX idx_gmina_teryt FOR (g:Gmina) ON (g.teryt);
CREATE INDEX idx_param_typ FOR (p:ParametrZabudowy) ON (p.typ);
```

## Import Script

```python
# scripts/import_mpzp_neo4j.py

from neo4j import GraphDatabase
import geopandas as gpd
import pandas as pd
from loguru import logger


class Neo4jImporter:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def import_mpzp_coverage(self, mpzp_gdf: gpd.GeoDataFrame):
        """Import MPZP coverage data to Neo4j."""

        with self.driver.session() as session:
            for _, row in mpzp_gdf.iterrows():
                session.run("""
                    MERGE (gm:Gmina {teryt: $teryt})
                    MERGE (mpzp:MPZP {id: $mpzp_id})
                    SET mpzp.tytul = $tytul,
                        mpzp.status = $status,
                        mpzp.numer_uchwaly = $numer
                    MERGE (gm)-[:POSIADA_MPZP]->(mpzp)
                """, {
                    "teryt": row['teryt'],
                    "mpzp_id": f"mpzp-{row['teryt']}-{row.get('lokalny_id', row.name)}",
                    "tytul": row.get('tytul'),
                    "status": row.get('status', 'obowiazujacy'),
                    "numer": row.get('numer_uchwaly')
                })

        logger.info(f"Imported {len(mpzp_gdf)} MPZP records")

    def link_parcels_to_mpzp(self, parcels_gdf: gpd.GeoDataFrame):
        """Link parcels to their MPZP coverage."""

        with self.driver.session() as session:
            for _, parcel in parcels_gdf.iterrows():
                if parcel.get('has_mpzp'):
                    session.run("""
                        MERGE (dz:Dzialka {id: $parcel_id})
                        SET dz.teryt = $teryt,
                            dz.powierzchnia_m2 = $area,
                            dz.has_mpzp = true
                        WITH dz
                        MATCH (mpzp:MPZP)
                        WHERE mpzp.id STARTS WITH 'mpzp-' + $teryt
                        MERGE (dz)-[:OBJETA_MPZP]->(mpzp)
                    """, {
                        "parcel_id": parcel['id'],
                        "teryt": parcel['teryt'],
                        "area": parcel['area_m2']
                    })

        logger.info(f"Linked {len(parcels_gdf)} parcels to MPZP")


if __name__ == "__main__":
    importer = Neo4jImporter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )

    mpzp = gpd.read_file("mpzp-pomorskie/mpzp_pomorskie_coverage.gpkg")
    parcels = gpd.read_parquet("processed/parcels_with_mpzp.parquet")

    importer.import_mpzp_coverage(mpzp)
    importer.link_parcels_to_mpzp(parcels[parcels['has_mpzp']])

    importer.close()
```
