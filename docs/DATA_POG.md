# Dokumentacja danych POG (Plany Ogólne Gmin)

## Lokalizacja
`/home/marcin/moja-dzialka/pog/`

## Pliki źródłowe

| Gmina | Plik | Rozmiar | Stref | Format | EPSG |
|-------|------|---------|-------|--------|------|
| Gdańsk | `gdansk/pog-gdansk-proj-uzg-042025.gml` | 23.5 MB | ~3,710 | GML 3.2 | 2177 |
| Gdynia | `gdynia/POG_Gdynia_projekt_uzg_032025_podpisany.gml` | 17.7 MB | ~6,390 | GML 3.2 | 2177 |
| Sopot | `sopot/POG_SOPOT_12092025.gml` | 3.4 MB | ~1,236 | GML 3.2 | 2177 |
| **RAZEM** | - | 44.6 MB | **~11,336** | - | - |

**Dodatkowe pliki:**
- `gdansk/pog-gdansk-uzasadnienie-cz-graficzna-uzg-042025.tif` (230 MB) - raster uzasadnienia
- `gdynia/POG_Gdynia_uzasadnienie_cz_graficzna_nr_1_uzg_032025.pdf` (14 MB)
- `gdynia/POG_Gdynia_uzasadnienie_cz_tekstowa_uzg_062025.pdf` (1 MB)

## Format GML

Standard: WFS 2.0 Feature Collection zgodny z polskim schematem `app:2.0`
```
https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0/planowaniePrzestrzenne_2_0.xsd
```

Namespaces:
- `wfs` - OGC WFS 2.0
- `gml` - OGC GML 3.2
- `app` - polski schemat planowania przestrzennego

---

## Struktura danych (analiza Gdańska)

### Typy obiektów

| Typ | Liczba | Opis |
|-----|--------|------|
| **StrefaPlanistyczna** | 3,710 | Główne strefy z parametrami zabudowy |
| **ObszarUzupelnieniaZabudowy (OUZ)** | 138 | Obszary uzupełnienia zabudowy |
| **ObszarZabudowySrodmiejskiej (OZS)** | 5 | Obszary śródmiejskie |
| **ObszarStandardowDostepnosciInfrastrukturySpolecznej (OSD)** | 8 | Standardy dostępności |
| **RAZEM** | 3,861 | |

---

## StrefaPlanistyczna - szczegóły

### Atrybuty identyfikacyjne

| Atrybut | Przykład | Opis |
|---------|----------|------|
| `gml:id` | `PL.ZIPPZP.9389_226101-POG_1POG-838SW_20250304T000000` | Globalny ID |
| `idIIP/lokalnyId` | `1POG-838SW` | Lokalny ID |
| `oznaczenie` | `838SW` | Oznaczenie na mapie |
| `symbol` | `SW` | Kod strefy |
| `nazwa` | `strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną` | Pełna nazwa |

### Symbole stref (15 kodów)

| Symbol | Liczba | Nazwa |
|--------|--------|-------|
| **SW** | 1,975 | Strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną |
| **SJ** | 379 | Strefa mieszkaniowa jednorodzinna |
| **SN** | 418 | Strefa zieleni i rekreacji |
| **SU** | 309 | Strefa usług |
| **SK** | 165 | Strefa komunikacji |
| **SH** | 17 | Strefa handlu wielkopowierzchniowego |
| **SC** | 16 | Strefa cmentarzy |
| **SO** | 83 | Strefa obsługi komunikacji |
| **SP** | 166 | Strefa usług publicznych |
| **SR** | 12 | Teren rolniczy |
| **SI** | 105 | Strefa infrastruktury |
| **SZ** | 65 | Strefa ochrony przyrody |

### Profile podstawowe (28 wartości)

Profile określają dozwolone funkcje terenu:

1. teren zabudowy mieszkaniowej wielorodzinnej
2. teren zabudowy mieszkaniowej jednorodzinnej
3. teren usług
4. teren komunikacji
5. teren zieleni urządzonej
6. teren zieleni naturalnej
7. teren lasu
8. teren wód
9. teren ogrodów działkowych
10. teren infrastruktury technicznej
11. teren plaży
12. teren komunikacji kolejowej i szynowej
13. teren komunikacji lotniczej
14. teren komunikacji wodnej
15. teren autostrady
16. teren drogi ekspresowej
17. teren drogi głównej
18. teren drogi głównej ruchu przyspieszonego
19. teren obsługi komunikacji
20. teren handlu wielkopowierzchniowego
21. teren produkcji
22. teren cmentarza
23. teren rolnictwa z zakazem zabudowy
24. teren wielkotowarowej produkcji rolnej
25. teren zabudowy zagrodowej
26. teren produkcji w gospodarstwach rolnych
27. teren akwakultury i obsługi rybactwa
28. teren komunikacji kolei linowej

### Profile dodatkowe (23 wartości)

Opcjonalne, doprecyzowujące:

1. teren zabudowy mieszkaniowej jednorodzinnej (MN)
2. teren zabudowy letniskowej lub rekreacji indywidualnej
3. teren zieleni naturalnej (ZN)
4. teren lasu (L)
5. teren wód (W)
6. teren usług sportu i rekreacji (US)
7. teren usług kultury i rozrywki (UK)
8. teren usług handlu detalicznego (UHD)
9. teren usług gastronomii (UG)
10. teren usług turystyki (UT)
11. teren usług nauki (UN)
12. teren usług edukacji (UE)
13. teren usług zdrowia i pomocy społecznej (UZ)
14. teren usług kultu religijnego
15. teren produkcji
16. teren handlu wielkopowierzchniowego
17. teren składów i magazynów
18. teren rolnictwa z zakazem zabudowy
19. teren wielkotowarowej produkcji rolnej
20. teren elektrowni słonecznej
21. teren drogi zbiorczej
22. teren zieleni urządzonej (ZP)
23. (inne)

### Parametry zabudowy

| Parametr | Atrybut | Min | Max | Opis |
|----------|---------|-----|-----|------|
| Intensywność | `maksNadziemnaIntensywnoscZabudowy` | 0.0 | 3.7 | Stosunek powierzchni zabudowy do działki |
| % zabudowy | `maksUdzialPowierzchniZabudowy` | 0% | 100% | Max procent zabudowy |
| Wysokość | `maksWysokoscZabudowy` | 0m | 100m | Max wysokość budynków |
| % bioczynna | `minUdzialPowierzchniBiologicznieCzynnej` | 0% | 100% | Min procent zieleni |

**Typowe wartości dla SJ (jednorodzinna):**
- Intensywność: 0.5
- Max zabudowa: 30%
- Max wysokość: 9m
- Min bio: 50%

**Typowe wartości dla SW (wielorodzinna):**
- Intensywność: 1.5
- Max zabudowa: 40%
- Max wysokość: 19m
- Min bio: 30%

---

## Geometria

- **Format:** GML Polygon
- **EPSG:** 2177 (PL-2000 strefa 7)
- **Wymiar:** 2D
- **Struktura:** exterior ring + opcjonalne interior rings (dziury)

```xml
<gml:Polygon srsDimension="2" srsName="http://www.opengis.net/def/crs/EPSG/0/2177">
    <gml:exterior>
        <gml:LinearRing>
            <gml:posList>
                X1 Y1 X2 Y2 X3 Y3 ... X1 Y1
            </gml:posList>
        </gml:LinearRing>
    </gml:exterior>
</gml:Polygon>
```

---

## Przykład pełnego rekordu

```xml
<app:StrefaPlanistyczna gml:id="PL.ZIPPZP.9389_226101-POG_1POG-173SJ_20250304T000000">
    <app:idIIP>
        <app:Identyfikator>
            <app:przestrzenNazw>PL.ZIPPZP.9389/226101-POG</app:przestrzenNazw>
            <app:lokalnyId>1POG-173SJ</app:lokalnyId>
            <app:wersjaId>20250304T000000</app:wersjaId>
        </app:Identyfikator>
    </app:idIIP>
    <app:poczatekWersjiObiektu>2025-03-04T00:00:00Z</app:poczatekWersjiObiektu>
    <app:obowiazujeOd>2025-03-04</app:obowiazujeOd>
    <app:status xlink:href="..." xlink:title="w opracowaniu"/>
    <app:oznaczenie>173SJ</app:oznaczenie>
    <app:symbol>SJ</app:symbol>
    <app:nazwa xlink:title="strefa mieszkaniowa jednorodzinna"/>

    <!-- Profile -->
    <app:profilPodstawowy xlink:title="teren zabudowy mieszkaniowej jednorodzinnej"/>
    <app:profilPodstawowy xlink:title="teren usług"/>
    <app:profilPodstawowy xlink:title="teren komunikacji"/>
    <app:profilPodstawowy xlink:title="teren zieleni urządzonej"/>
    <app:profilPodstawowy xlink:title="teren ogrodów działkowych"/>
    <app:profilPodstawowy xlink:title="teren infrastruktury technicznej"/>

    <app:profilDodatkowy xlink:title="teren zabudowy letniskowej lub rekreacji indywidualnej"/>
    <app:profilDodatkowy xlink:title="teren zieleni naturalnej"/>
    <app:profilDodatkowy xlink:title="teren lasu"/>
    <app:profilDodatkowy xlink:title="teren wód"/>

    <!-- Parametry -->
    <app:maksNadziemnaIntensywnoscZabudowy>0.5</app:maksNadziemnaIntensywnoscZabudowy>
    <app:maksUdzialPowierzchniZabudowy>30.0</app:maksUdzialPowierzchniZabudowy>
    <app:maksWysokoscZabudowy uom="m">9.0</app:maksWysokoscZabudowy>
    <app:minUdzialPowierzchniBiologicznieCzynnej>50.0</app:minUdzialPowierzchniBiologicznieCzynnej>

    <!-- Geometria -->
    <app:geometria>
        <gml:Polygon srsDimension="2" srsName="http://www.opengis.net/def/crs/EPSG/0/2177">
            <gml:exterior>
                <gml:LinearRing>
                    <gml:posList>...</gml:posList>
                </gml:LinearRing>
            </gml:exterior>
        </gml:Polygon>
    </app:geometria>
</app:StrefaPlanistyczna>
```

---

## Przetwarzanie

### Konwersja GML → GeoPackage

```bash
ogr2ogr -f GPKG pog_gdansk.gpkg \
  pog/gdansk/pog-gdansk-proj-uzg-042025.gml \
  -s_srs EPSG:2177 -t_srs EPSG:2180
```

### Parsowanie w Python

```python
import geopandas as gpd

# Uwaga: geopandas może nie parsować wszystkich atrybutów z GML
# Rozważ użycie lxml do ekstrakcji
gdf = gpd.read_file('pog/gdansk/pog-gdansk-proj-uzg-042025.gml')
```

### Ekstrakcja atrybutów (lxml)

```python
from lxml import etree

tree = etree.parse('pog/gdansk/pog-gdansk-proj-uzg-042025.gml')
root = tree.getroot()

ns = {
    'app': 'https://www.gov.pl/static/zagospodarowanieprzestrzenne/schemas/app/2.0',
    'gml': 'http://www.opengis.net/gml/3.2'
}

for strefa in root.findall('.//app:StrefaPlanistyczna', ns):
    symbol = strefa.find('app:symbol', ns).text
    oznaczenie = strefa.find('app:oznaczenie', ns).text
    # ...
```

---

## Wykorzystanie w projekcie

### Dla działek
- **Spatial join** działka ↔ strefa POG
- Przypisanie: symbol, profil_podstawowy[], parametry zabudowy

### Dla Neo4j
- Węzły: `StrefaPOG`, `ProfilFunkcji`
- Relacje: `(:Dzialka)-[:W_STREFIE_POG]->(:StrefaPOG)`
- Relacje: `(:StrefaPOG)-[:DOZWALA]->(:ProfilFunkcji)`

### Dla agenta
- Filtrowanie po symbolu (SJ = jednorodzinna)
- Filtrowanie po parametrach (max wysokość, % zabudowy)
- Wyjaśnienie użytkownikowi co można budować

---

## TODO

- [ ] Sprawdzić strukturę GML dla Gdyni i Sopotu
- [ ] Zweryfikować czy profile są takie same we wszystkich miastach
- [ ] Utworzyć słownik symboli i profili
