# Dokumentacja danych Działek (Parcele katastralne)

## Lokalizacja
`/home/marcin/moja-dzialka/dzialki/dzialki_pomorskie.gpkg`

## Informacje ogólne

- **Źródło:** ULDK / GUGiK (Ewidencja Gruntów i Budynków)
- **Format:** GeoPackage (.gpkg)
- **EPSG:** 2180 (PUWG 1992)
- **Rozmiar:** 429 MB
- **Liczba obiektów:** 1,300,779 (całe województwo pomorskie)

---

## Struktura danych

### Kolumny

| Kolumna | Typ | Opis |
|---------|-----|------|
| `fid` | INTEGER | Primary key (indeks wewnętrzny) |
| `ID_DZIALKI` | TEXT | Unikatowy identyfikator działki |
| `TERYT_POWIAT` | TEXT | Kod TERYT powiatu (4 cyfry) |
| `geom` | POLYGON | Geometria działki |

### Format ID_DZIALKI

```
TTTTTT_X.OOOO.NNNN/PP
│     │ │    │    │
│     │ │    │    └── Numer poddziałki (opcjonalny)
│     │ │    └─────── Numer działki
│     │ └──────────── Numer obrębu
│     └────────────── Typ obrębu (1=wiejski, 2=miejski)
└──────────────────── Kod TERYT gminy (6 cyfr)
```

**Przykłady:**
- `226301_1.0012.152/5` - Gdynia, obręb wiejski 0012, działka 152/5
- `221404_5.0008.214/10` - powiat 2214, obręb 0008, działka 214/10

---

## Statystyki

### Całe województwo

| Metryka | Wartość |
|---------|---------|
| Liczba działek | 1,300,779 |
| Średnia powierzchnia | 14,162 m² |
| Mediana | 1,199 m² |
| Min | 0.006 m² |
| Max | 179,217,300 m² |

### Trójmiasto

| Gmina | TERYT | Liczba działek | % całości |
|-------|-------|----------------|-----------|
| Gdańsk | 2261 | 107,006 | 8.2% |
| Sopot | 2213 | 99,300 | 7.6% |
| Gdynia | 2263 | 19,283 | 1.5% |
| **RAZEM** | - | **225,589** | **17.3%** |

### Rozkład powierzchni (Gdynia)

| Przedział | Liczba | % |
|-----------|--------|---|
| < 100 m² | 2,847 | 14.8% |
| 100-500 m² | 8,154 | 42.3% |
| 500-1000 m² | 3,000 | 15.6% |
| 1000-1500 m² | 1,449 | 7.5% |
| 1500-2000 m² | 900 | 4.7% |
| > 2000 m² | 2,933 | 15.2% |

**Działki "pod dom" (800-1500 m²):** ~2,349 w Gdyni (~12%)

---

## Kody TERYT powiatów

| TERYT | Powiat/Miasto |
|-------|---------------|
| 2201 | Bytów |
| 2202 | Chojnice |
| 2203 | Człuchów |
| 2204 | Gdańsk (powiat) |
| 2205 | Kartuzy |
| 2206 | Kościerzyna |
| 2207 | Kwidzyn |
| 2208 | Lębork |
| 2209 | Malbork |
| 2210 | Nowy Dwór Gdański |
| 2211 | Puck |
| 2212 | Słupsk (powiat) |
| 2213 | Starogard Gdański |
| 2214 | Sztum |
| 2215 | Tczew |
| 2216 | Wejherowo |
| **2261** | **Gdańsk (miasto)** |
| 2262 | Słupsk (miasto) |
| **2263** | **Gdynia (miasto)** |
| 2264 | Sopot (miasto) |

**Uwaga:** Sopot ma TERYT 2264, ale w danych występuje jako 2213. Do weryfikacji.

---

## Przetwarzanie

### Odczyt w Python

```python
import geopandas as gpd

# Odczyt całości
parcels = gpd.read_file('dzialki/dzialki_pomorskie.gpkg')

# Sprawdzenie struktury
print(f"Liczba działek: {len(parcels)}")
print(f"Kolumny: {parcels.columns.tolist()}")
print(f"CRS: {parcels.crs}")
```

### Filtrowanie do Trójmiasta

```python
# Kody TERYT Trójmiasta
TROJMIASTO_TERYT = ['2261', '2263', '2264']  # Gdańsk, Gdynia, Sopot

# Filtrowanie
parcels_trojmiasto = parcels[parcels['TERYT_POWIAT'].isin(TROJMIASTO_TERYT)]
print(f"Działki w Trójmieście: {len(parcels_trojmiasto)}")
```

### Obliczanie powierzchni i centroidów

```python
# Powierzchnia (już jest w m², bo EPSG:2180 ma jednostki metryczne)
parcels['area_m2'] = parcels.geometry.area

# Centroid
parcels['centroid'] = parcels.geometry.centroid

# Współrzędne WGS84
parcels_wgs84 = parcels.to_crs('EPSG:4326')
parcels['centroid_lon'] = parcels_wgs84.centroid.x
parcels['centroid_lat'] = parcels_wgs84.centroid.y
```

### Usuwanie anomalii

```python
# Działki o absurdalnie małej powierzchni (błędy/slivery)
parcels = parcels[parcels['area_m2'] > 10]

# Działki o absurdalnie dużej powierzchni (prawdopodobnie błędy)
parcels = parcels[parcels['area_m2'] < 1_000_000]
```

---

## Enrichment (wzbogacanie danych)

Działki źródłowe mają tylko ID, TERYT i geometrię. Trzeba je wzbogacić o:

### Z POG (spatial join)
- `pog_strefa_id`
- `pog_symbol`
- `pog_profil_podstawowy[]`
- `pog_max_intensywnosc`
- `pog_max_zabudowa_pct`
- `pog_max_wysokosc`
- `pog_min_bio_pct`

### Z BDOT10k (odległości)
- `dist_to_forest`
- `dist_to_water`
- `dist_to_school`
- `dist_to_bus_stop`
- `dist_to_main_road`
- `dist_to_industrial`

### Z BDOT10k (bufory 500m)
- `pct_forest_500m`
- `pct_water_500m`
- `count_buildings_500m`

### Z BDOT10k ADMS (miejscowość)
- `gmina`
- `miejscowosc` / `dzielnica`

### Wskaźniki kompozytowe (obliczone)
- `quietness_score` (0-100)
- `nature_score` (0-100)
- `accessibility_score` (0-100)

### Kategorie (dyskretne)
- `cisza_kategoria` (bardzo_cicha, cicha, umiarkowana, głośna)
- `natura_kategoria` (bardzo_zielona, zielona, umiarkowana, zurbanizowana)
- `dostepnosc_kategoria` (doskonała, dobra, umiarkowana, ograniczona)
- `powierzchnia_klasa` (mala, pod_dom, duza, bardzo_duza)

### Flagi
- `is_buildable` (czy można budować wg POG)
- `has_road_access` (czy ma dostęp do drogi)

---

## Docelowy schemat

```python
parcels_enriched = {
    # Identyfikacja
    'id_dzialki': str,           # PRIMARY KEY
    'teryt_powiat': str,

    # Geometria
    'geom': Polygon,             # EPSG:2180
    'area_m2': float,
    'centroid_lat': float,       # WGS84
    'centroid_lon': float,       # WGS84

    # Lokalizacja
    'gmina': str,                # Gdańsk, Gdynia, Sopot
    'miejscowosc': str,          # dzielnica/osiedle

    # POG
    'pog_strefa_id': str,
    'pog_symbol': str,           # SJ, SW, SN, ...
    'pog_profil_podstawowy': list[str],
    'pog_max_intensywnosc': float,
    'pog_max_zabudowa_pct': float,
    'pog_max_wysokosc': float,
    'pog_min_bio_pct': float,

    # Odległości (metry)
    'dist_to_forest': int,
    'dist_to_water': int,
    'dist_to_school': int,
    'dist_to_bus_stop': int,
    'dist_to_main_road': int,
    'dist_to_industrial': int,

    # Bufory 500m
    'pct_forest_500m': float,
    'pct_water_500m': float,
    'count_buildings_500m': int,

    # Wskaźniki (0-100)
    'quietness_score': int,
    'nature_score': int,
    'accessibility_score': int,

    # Kategorie
    'cisza_kategoria': str,
    'natura_kategoria': str,
    'dostepnosc_kategoria': str,
    'powierzchnia_klasa': str,

    # Flagi
    'is_buildable': bool,
    'road_access_quality': str,
}
```

---

## Wykorzystanie w projekcie

### PostGIS
- Tabela `parcels` z pełnym schematem
- Indeks GIST na `geom`
- Indeks B-tree na `gmina`, `pog_symbol`

### Neo4j
- Węzły `(:Dzialka {id, area_m2, centroid_lat, centroid_lon})`
- Relacje do lokalizacji, POG, kategorii

### Milvus
- Embedding 32-dim z cech numerycznych
- ID jako primary key

### Agent
- Wyszukiwanie po wszystkich kryteriach
- Prezentacja z wyjaśnieniem dopasowania

---

## TODO

- [ ] Zweryfikować kody TERYT (Sopot: 2213 vs 2264?)
- [ ] Sprawdzić jakość geometrii (self-intersections, slivers)
- [ ] Określić threshold dla "działki pod dom" (800-1500 m²?)
- [ ] Ustalić logikę `is_buildable` na podstawie POG
