# Dokumentacja danych BDOT10k

## Lokalizacja
`/home/marcin/moja-dzialka/bdot10k/`

## Informacje ogólne

- **Źródło:** GUGiK (Główny Urząd Geodezji i Kartografii)
- **Format:** GeoPackage (.gpkg)
- **EPSG:** 2180 (PUWG 1992)
- **Pokrycie:** Województwo Pomorskie
- **Liczba warstw:** 72
- **Liczba obiektów:** 3,738,105
- **Rozmiar:** 2.63 GB

---

## Kategorie warstw

| Prefiks | Kategoria | Liczba warstw | Obiektów |
|---------|-----------|---------------|----------|
| AD | Jednostki administracyjne | 3 | 8,395 |
| BU | Budynki, budowle, urządzenia | 17 | 795,006 |
| KU | Kompleksy użytkowania terenu | 13 | 10,512 |
| OI | Obiekty inne | 10 | 608,611 |
| PT | Pokrycie terenu | 12 | 338,234 |
| RT | Rzeźba terenu | 2 | 809,836 |
| SK | Sieć komunikacyjna | 6 | 906,793 |
| SU | Sieć uzbrojenia terenu | 2 | 21,202 |
| SW | Sieć wodna | 3 | 238,568 |
| TC | Tereny chronione | 4 | 948 |

---

## Warstwy priorytetowe dla projektu

### 1. BUBD_A - Budynki

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_BUBD_A.gpkg`
**Rozmiar:** 381 MB
**Obiektów:** 695,642
**Geometria:** Polygon

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `FUNKCJAOGOLNABUDYNKU` | Mieszkalne (428k), Produkcyjne (199k), Handlowo-usługowe (12k), Przemysłowe (11k), Szpitalne (1.3k) | Klasyfikacja typu zabudowy |
| `PRZEWAZAJACAFUNKCJABUDYNKU` | Jednorodzinny (340k), Gospodarczy (197k), Dom letniskowy (43k), Wielorodzinny (42k), Garaż (10k) | Szczegółowa klasyfikacja |
| `LICZBAKONDYGNACJI` | 1 (341k), 2 (282k), 3 (43k), 4+ (12k) | Wysokość zabudowy |

#### Wykorzystanie
- Gęstość zabudowy w bufferze 500m
- Typ dominującej zabudowy (jednorodzinna vs wielorodzinna)
- Odległość do budynków przemysłowych

---

### 2. SKDR_L - Drogi

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_SKDR_L.gpkg`
**Rozmiar:** 212 MB
**Obiektów:** 411,575
**Geometria:** LineString

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `KLASADROGI` | Wewnętrzna (298k), Lokalna (68k), Zbiorcza (26k), Dojazdowa (7k), Główna (7k), Ekspresowa (226), Autostrada (86) | Klasa drogi |
| `KATEGORIAZARZADZANIA` | Wewnętrzna (280k), Gminna (83k), Powiatowa (31k), Wojewódzka (10k), Krajowa (4k) | Zarządca drogi |
| `MATERIALNAWIERZCHNI` | Grunt (219k), Asfalt (101k), Żwir (34k), Kostka (23k), Beton (20k) | Jakość nawierzchni |
| `SZEROKOSCNAWIERZCHNI` | 2m - 40m (średnia: 4.8m) | Szerokość jezdni |

#### Wykorzystanie
- Jakość dostępu do działki (klasa drogi)
- Hałas (bliskość dróg głównych)
- Materiał nawierzchni dojazdowej

---

### 3. PTLZ_A - Lasy

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_PTLZ_A.gpkg`
**Rozmiar:** 94.6 MB
**Obiektów:** 75,577
**Geometria:** Polygon

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Las (41k), Zagajnik (30k), Zadrzewienie (3k) | Typ roślinności |
| `KATEGORIA` | Iglasty (30k), Mieszany (26k), Liściasty (18k) | Typ lasu |

#### Wykorzystanie
- Odległość do lasu (premium feature)
- % lasów w bufferze 500m
- Wskaźnik "natury"

---

### 4. PTWP_A - Wody powierzchniowe

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_PTWP_A.gpkg`
**Rozmiar:** 44.2 MB
**Obiektów:** 49,670
**Geometria:** Polygon

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Woda stojąca/jeziora (48k), Woda płynąca/rzeki (964), Woda morska (25) | Typ akwenu |
| `NAZWA` | Jezioro Mausz, Jezioro Kałęga, etc. | Identyfikacja |

#### Wykorzystanie
- Odległość do wody (premium feature)
- % wód w bufferze 500m
- "Działka nad jeziorem"

---

### 5. OIKM_P - Obiekty komunikacyjne (przystanki)

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_OIKM_P.gpkg`
**Rozmiar:** 3.2 MB
**Obiektów:** 10,554
**Geometria:** Point

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Przystanek autobusowy/tramwajowy (10k), Stacja kolejowa (256), Sygnalizator (53), Lądowisko (23) | Typ obiektu |
| `NAZWA` | Nazwa przystanku | Identyfikacja |

#### Wykorzystanie
- Odległość do przystanku
- Wskaźnik dostępności transportu publicznego

---

### 6. KUOS_A - Kompleksy oświaty

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_KUOS_A.gpkg`
**Rozmiar:** 0.87 MB
**Obiektów:** 1,092
**Geometria:** Polygon

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Szkoły/zespoły (874), Przedszkola (158), Szkoły wyższe (37), Ośrodki naukowe (23) | Typ placówki |
| `NAZWA` | Nazwa szkoły | Identyfikacja |

#### Wykorzystanie
- Odległość do szkoły (kluczowe dla rodzin)
- Wskaźnik dostępności edukacji

---

### 7. KUPG_A - Kompleksy przemysłowe

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_KUPG_A.gpkg`
**Rozmiar:** 2.95 MB
**Obiektów:** 3,795
**Geometria:** Polygon

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Zakład produkcyjny (2.4k), Gospodarstwo hodowlane (653), Elektrownia (161), Oczyszczalnia (140), Kopalnia (104), Składowisko odpadów (37) | Typ zakładu |

#### Wykorzystanie
- Odległość do przemysłu (ujemny wpływ)
- Wykluczenie działek blisko składowisk, oczyszczalni
- Wskaźnik "ciszy"

---

### 8. ADMS_A/P - Miejscowości

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_ADMS_A.gpkg` / `_P.gpkg`
**Obiektów:** 4,094
**Geometria:** Polygon / Point

#### Kluczowe atrybuty

| Atrybut | Wartości | Zastosowanie |
|---------|----------|--------------|
| `RODZAJ` | Miasto, Wieś, Część wsi, Przysiółek, Osada | Typ miejscowości |
| `NAZWA` | Nazwa miejscowości | Identyfikacja |

#### Wykorzystanie
- Przypisanie działki do miejscowości/dzielnicy
- Hierarchia administracyjna

---

### 9. TC*_A - Tereny chronione

**Pliki:**
- `TCON_A` - Natura 2000 (456 obiektów)
- `TCPK_A` - Parki krajobrazowe (281 obiektów)
- `TCPN_A` - Parki narodowe (32 obiekty)
- `TCRZ_A` - Rezerwaty (179 obiektów)

#### Wykorzystanie
- Wykluczenie działek wewnątrz terenów chronionych
- Marketing: "w pobliżu chronionego terenu"
- Informacja o ograniczeniach

---

### 10. RTLW_l - Linie wysokościowe

**Plik:** `PL.PZGiK.336.BDOT10k.22_OT_RTLW_l.gpkg`
**Rozmiar:** 999 MB (!)
**Obiektów:** 782,963
**Geometria:** LineString

#### Wykorzystanie
- Generowanie NMT (Numeryczny Model Terenu)
- Wizualizacja 3D rzeźby terenu
- Analiza nachylenia działki

---

## Warstwy pomocnicze

| Warstwa | Obiektów | Zastosowanie |
|---------|----------|--------------|
| KUOZ_A (zdrowie) | 143 | Odległość do szpitala |
| KUHO_A (hotele) | 654 | Dla inwestorów turystycznych |
| KUKO_A (komunikacja) | 1,040 | Parkingi, stacje paliw |
| SKRP_L (ścieżki) | 67,691 | Ścieżki rowerowe/piesze |
| SULN_L (linie) | 20,239 | Infrastruktura elektroenergetyczna |

---

## Przetwarzanie

### Odczyt w Python

```python
import geopandas as gpd

# Odczyt warstwy
budynki = gpd.read_file('bdot10k/PL.PZGiK.336.BDOT10k.22_OT_BUBD_A.gpkg')

# Sprawdzenie struktury
print(budynki.columns.tolist())
print(budynki['FUNKCJAOGOLNABUDYNKU'].value_counts())
```

### Filtrowanie do regionu

```python
# Bounding box Trójmiasta (przybliżony)
bbox = (6470000, 6530000, 6010000, 6060000)  # minx, maxx, miny, maxy w EPSG:2180

# Clip
budynki_trojmiasto = budynki.cx[bbox[0]:bbox[1], bbox[2]:bbox[3]]
```

### Obliczanie odległości (KD-tree)

```python
from scipy.spatial import cKDTree
import numpy as np

# Centroidy działek
parcel_coords = np.array([(p.centroid.x, p.centroid.y) for p in parcels.geometry])

# Centroidy szkół
school_coords = np.array([(s.centroid.x, s.centroid.y) for s in schools.geometry])

# KD-tree
tree = cKDTree(school_coords)
distances, _ = tree.query(parcel_coords)
parcels['dist_to_school'] = distances
```

### Obliczanie bufferów

```python
# Buffer 500m
parcels['buffer_500m'] = parcels.geometry.buffer(500)

# Intersection z lasami
parcels['pct_forest_500m'] = parcels['buffer_500m'].apply(
    lambda buf: forests[forests.intersects(buf)].unary_union.intersection(buf).area / buf.area * 100
)
```

---

## Wykorzystanie w projekcie

### Dla feature engineering
1. Odległości: `dist_to_forest`, `dist_to_water`, `dist_to_school`, `dist_to_bus_stop`, `dist_to_industrial`
2. Bufory: `pct_forest_500m`, `pct_water_500m`, `count_buildings_500m`
3. Wskaźniki: `quietness_score`, `nature_score`, `accessibility_score`

### Dla Neo4j
- Węzły: `Feature {typ: "las"|"woda"|"szkola"|"przystanek"|"przemysl"}`
- Relacje: `(:Dzialka)-[:BLISKO_LASU {distance_m: 150}]->(:Feature)`

### Dla agenta
- Filtrowanie: "blisko lasu", "daleko od przemysłu"
- Wyjaśnienia: "Ta działka jest 150m od lasu i 2km od najbliższej fabryki"

---

## TODO

- [ ] Clip wszystkich warstw do Trójmiasta
- [ ] Sprawdzić kompletność danych (czy są dziury?)
- [ ] Zweryfikować jakość geometrii
- [ ] Utworzyć POI z KUOS_A, KUOZ_A, OIKM_P
