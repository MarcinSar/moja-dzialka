# Dane gotowe do importu

Czyste, przetworzone dane Trójmiasta gotowe do załadowania do baz danych.

## Struktura

```
ready-for-import/
├── postgis/          # Dane przestrzenne (GeoPackage → PostGIS)
├── neo4j/            # Dane do grafu wiedzy (GPKG → CSV → Neo4j)
└── milvus/           # Dane do embeddingów (CSV → Milvus)
```

## PostGIS (11 plików, 294 MB)

Pełne dane przestrzenne dla zapytań geograficznych.

| Plik | Rekordów | Opis |
|------|----------|------|
| `parcels_enriched.gpkg` | 154,959 | Działki z 59 cechami |
| `pog_trojmiasto.gpkg` | 7,523 | Strefy planistyczne POG |
| `poi_trojmiasto.gpkg` | 15,421 | Punkty zainteresowania |
| `budynki.gpkg` | 82,368 | Budynki z BDOT10k |
| `lasy.gpkg` | - | Tereny leśne |
| `wody.gpkg` | - | Zbiorniki wodne |
| `drogi_glowne.gpkg` | - | Drogi główne |
| `drogi_wszystkie.gpkg` | - | Pełna sieć drogowa |
| `szkoly.gpkg` | - | Placówki edukacyjne |
| `przystanki.gpkg` | - | Transport publiczny |
| `przemysl.gpkg` | - | Tereny przemysłowe |

### Import do PostGIS

```bash
# Użyj skryptu pipeline
python egib/scripts/pipeline/07_import_postgis.py
```

## Neo4j (3 pliki, 162 MB)

Dane do budowy grafu wiedzy z relacjami.

| Plik | Opis | Węzły Neo4j |
|------|------|-------------|
| `parcels_enriched.gpkg` | Działki | Parcel, District, Category |
| `pog_trojmiasto.gpkg` | Strefy POG | POGZone, Profile |
| `poi_trojmiasto.gpkg` | POI | POI (szkoły, sklepy, etc.) |

### Import do Neo4j

```bash
# Użyj skryptu pipeline
python egib/scripts/pipeline/08_import_neo4j.py
```

## Milvus (1 plik, 33 MB)

Dane do generowania 32-wymiarowych embeddingów.

| Plik | Rekordów | Opis |
|------|----------|------|
| `parcels_trojmiasto_summary.csv` | 154,959 | Cechy numeryczne działek |

### Pipeline embeddingów

```bash
# 1. Generuj embeddingi
python egib/scripts/pipeline/09_generate_embeddings.py

# 2. Import do Milvus
python egib/scripts/pipeline/10_import_milvus.py
```

## Źródło danych

Dane przetworzone przez pipeline w `egib/scripts/pipeline/`:

1. `01_parse_pog.py` - Parsowanie GML POG
2. `02_merge_parcels.py` - Scalanie działek
3. `03_add_districts.py` - Dodanie dzielnic
4. `03b_clip_bdot10k.py` - Wycinanie BDOT10k
5. `04_merge_poi.py` - Scalanie POI
6. `05_feature_engineering.py` - 59 cech działek
7. `06_add_buildings.py` - Cechy zabudowy
8. `07a_district_prices.py` - Ceny dzielnic

## Wersja danych

- **Data przetworzenia:** 2026-01-24
- **Źródła:** POG Gdańsk/Gdynia/Sopot (04/2025), BDOT10k (2024), EGiB (2024)
