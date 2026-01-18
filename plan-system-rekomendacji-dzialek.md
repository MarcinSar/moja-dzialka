# Plan: System rekomendacji działek z wykorzystaniem SRAI + BDOT10k + Knowledge Graph MPZP

## 1. Przegląd projektu

### Cel
Aplikacja webowa (React + Leaflet) do wyszukiwania działek budowlanych i inwestycyjnych na terenie **województwa pomorskiego**, wykorzystująca:
- **SRAI** - embeddingi przestrzenne działek
- **Knowledge Graph (Neo4j)** - grafowa baza wiedzy z uchwał MPZP
- **RAG** - odpowiadanie na pytania o przeznaczenie działek w języku naturalnym

### Grupy docelowe
1. **Kupujący działkę budowlaną** - szukają terenu pod dom jednorodzinny
2. **Inwestorzy/deweloperzy** - szukają większych działek pod zabudowę wielorodzinną/usługową

### Dostępne dane

#### 1. Geometrie działek
- Unikalny ID (województwo/powiat/gmina/miejscowość/nr ewidencyjny)
- **Powierzchnia** - obliczana z geometrii (kluczowy parametr!)

#### 2. BDOT10k - wykorzystywane warstwy

| Kategoria | Użycie | Priorytet | Uwagi |
|-----------|--------|-----------|-------|
| **SK** - Sieć komunikacyjna | ✅ TAK | WYSOKI | Krytyczna dla dostępności działki |
| **BU** - Budynki i budowle | ✅ TAK | WYSOKI | Bardzo bogate dane, wymaga dobrego wykorzystania |
| **PT** - Pokrycie terenu | ✅ TAK | WYSOKI | Zabudowa, lasy, woda, uprawy |
| **KU** - Kompleksy użytkowania | ✅ TAK | WYSOKI | Mieszkaniowe, oświatowe, sportowe, etc. |
| **AD** - Jednostki podziału | ✅ TAK | ŚREDNI | Gmina, miejscowość, dzielnica |
| **TC** - Tereny chronione | ✅ TAK | ŚREDNI | Natura 2000, parki, rezerwaty |
| **SW** - Sieć wodna | ⚠️ CZĘŚCIOWO | NISKI | Tylko odległość do jezior/rzek jako wskaźnik atrakcyjności |
| **SU** - Sieć uzbrojenia | ❌ NIE | - | Dane niekompletne, nie dają wartości |
| **OI** - Obiekty inne | ❌ NIE | - | Nie dają wartości dla użytkownika |

#### 3. Dane dodatkowe
- **KIEG**: Klasy bonitacyjne gruntu, grupy rejestrowe (struktura właścicielska)
- **MPZP**: Boolean + szczegółowe dane z Knowledge Graph

---

## 2. Perspektywa użytkownika - Cele i funkcjonalności

### 2.1 User Stories

#### Kupujący działkę budowlaną (osoba prywatna)
```
Jako osoba szukająca działki pod budowę domu jednorodzinnego:
- Chcę znaleźć działki o powierzchni 800-1500 m² w określonej lokalizacji
- Chcę widzieć odległość do szkoły, przedszkola, sklepów
- Chcę wiedzieć czy działka jest budowlana (MPZP)
- Chcę znać dostęp do drogi (publicznej vs prywatnej)
- Chcę widzieć co jest w sąsiedztwie (zabudowa, las, pole)
- Chcę porównać kilka działek obok siebie
- Chcę zadać pytanie: "Czy mogę tu wybudować dom dwukondygnacyjny?"
```

#### Inwestor / Deweloper
```
Jako inwestor szukający działki pod zabudowę wielorodzinną:
- Chcę znaleźć działki o powierzchni > 2000 m² z przeznaczeniem MW/U
- Chcę znać parametry zabudowy (intensywność, wysokość, pow. biol. czynna)
- Chcę widzieć dostęp do głównych dróg i komunikacji publicznej
- Chcę wiedzieć o ograniczeniach (strefy ochronne, konserwator)
- Chcę analizować potencjał inwestycyjny całego obszaru
- Chcę eksportować raport dla konkretnej działki
```

### 2.2 Kluczowe funkcjonalności aplikacji

| Funkcjonalność | Opis | Priorytet | Faza |
|----------------|------|-----------|------|
| **Wyszukiwanie po lokalizacji** | Mapa + wyszukiwarka adresowa | KRYTYCZNY | 1 |
| **Filtrowanie po powierzchni** | Suwak min-max m² | KRYTYCZNY | 1 |
| **Filtrowanie po przeznaczeniu** | MN, MW, U, R, etc. | KRYTYCZNY | 1 |
| **Wizualizacja działek na mapie** | Kolory wg przeznaczenia/statusu | KRYTYCZNY | 1 |
| **Karta działki** | Podstawowe atrybuty, zdjęcie satelitarne | KRYTYCZNY | 1 |
| **Odległość do POI** | Szkoła, sklep, przystanek, las | WYSOKI | 1 |
| **Dostęp drogowy** | Typ drogi, odległość do głównej | WYSOKI | 1 |
| **Parametry zabudowy z MPZP** | Wysokość, intensywność, PBC | WYSOKI | 2 |
| **Chat RAG o MPZP** | Pytania o możliwości zabudowy | ŚREDNI | 3 |
| **Porównanie działek** | Side-by-side comparison | ŚREDNI | 2 |
| **Podobne działki** | "Pokaż podobne do tej" | ŚREDNI | 2 |
| **Eksport raportu PDF** | Podsumowanie dla działki | NISKI | 3 |
| **Alerty email** | Nowe działki wg kryteriów | NISKI | 4 |

### 2.3 Kryteria wyszukiwania (filtry)

#### Podstawowe (Faza 1)
- **Lokalizacja**: Gmina, miejscowość, promień od punktu
- **Powierzchnia**: min-max m²
- **Przeznaczenie MPZP**: budowlana / usługowa / rolna / leśna / nieokreślona
- **Cena** (jeśli dostępna z zewnętrznego źródła)

#### Kontekstowe (Faza 2)
- **Dostęp do drogi**: publiczna / prywatna / brak
- **Odległość do**: szkoły, przedszkola, sklepu, przystanku
- **Sąsiedztwo**: % lasu, % zabudowy, % pola w promieniu 500m
- **Tereny chronione**: blisko / daleko / bez znaczenia

#### Zaawansowane (Faza 3)
- **Parametry zabudowy**: max wysokość, intensywność, PBC
- **Ograniczenia**: strefa ochronna, konserwator
- **Klasa bonitacyjna**: I-VI (dla rolnych)
- **Profil podobieństwa**: "znajdź podobne do wybranej"

---

## 3. Szczegółowe mapowanie warstw BDOT10k

### 3.1 SK - Sieć komunikacyjna (KRYTYCZNA)

#### SKJZ - Jezdnie
| Atrybut | Wartości | Wykorzystanie |
|---------|----------|---------------|
| `klasaDrogi` | A, S, GP, G, Z, L, D, I | Hierarchia dostępności |
| `katZarzadzania` | K, W, P, G, Z, I | Droga publiczna vs prywatna |
| `materialNawierzchni` | Bt, Br, Mb, Gr, etc. | Jakość drogi |
| `szerNawierzchni` | metry | Przepustowość |
| `ulica` | tak/nie | Czy ma nazwę ulicy |

**Cechy do obliczenia:**
```python
parcel_features = {
    # Bezpośredni dostęp
    "ma_dostep_do_drogi_publicznej": bool,
    "klasa_najblizszej_drogi": str,  # A/S/GP/G/Z/L/D/I
    "odleglosc_do_drogi_publicznej": float,  # metry

    # Dostępność komunikacyjna
    "odleglosc_do_autostrady": float,  # km
    "odleglosc_do_drogi_ekspresowej": float,
    "odleglosc_do_drogi_glownej": float,
    "odleglosc_do_drogi_lokalnej": float,

    # Jakość dostępu
    "nawierzchnia_utwardzona": bool,
}
```

#### SKRP - Ciągi ruchu pieszego i rowerowego
| Atrybut | Wykorzystanie |
|---------|---------------|
| `klasaCiaguRuchuPieszego` | Alejka, pasaż, ścieżka |
| `ruchRowerowy` | Czy dopuszczony ruch rowerowy |

**Cechy:**
```python
{
    "odleglosc_do_sciezki_rowerowej": float,
    "dostep_pieszy_do_centrum": bool,
}
```

#### SKTR - Tory kolejowe
```python
{
    "odleglosc_do_linii_kolejowej": float,  # hałas vs dostępność
    "blisko_stacji_kolejowej": bool,
}
```

#### OIKM - Obiekty komunikacyjne (przystanki)
```python
{
    "odleglosc_do_przystanku_autobusowego": float,
    "odleglosc_do_przystanku_kolejowego": float,
    "liczba_przystankow_w_promieniu_1km": int,
}
```

### 3.2 BU - Budynki, budowle i urządzenia (KRYTYCZNA)

#### BUBD - Budynki (21 typów)
| Kod | Funkcja ogólna | Wykorzystanie |
|-----|----------------|---------------|
| 1110 | Mieszkalne jednorodzinne | Sąsiedztwo mieszkaniowe |
| 1121-1122 | Mieszkalne wielorodzinne | Gęstość zabudowy |
| 1220 | Biurowe | Bliskość miejsca pracy |
| 1230 | Handlowo-usługowe | Dostęp do usług |
| 1251 | Przemysłowe | Potencjalne uciążliwości |
| 1263 | Szkoły i instytucje | Edukacja |
| 1264 | Szpitale i opieka | Zdrowie |
| 1265 | Kultury fizycznej | Rekreacja |
| 1272 | Kultu religijnego | Kościoły |

**Funkcje szczegółowe (kluczowe):**
| Kod | Funkcja | Wykorzystanie |
|-----|---------|---------------|
| 1263.Ps | Przedszkole | Rodziny z dziećmi |
| 1263.Sp | Szkoła podstawowa | Rodziny z dziećmi |
| 1230.Hm | Hipermarket | Zakupy |
| 1230.Ap | Apteka | Zdrowie |
| 1264.Po | Placówka ochrony zdrowia | Przychodnia |
| 1220.Sp | Straż pożarna | Bezpieczeństwo |
| 1220.Pc | Policja | Bezpieczeństwo |

**Cechy do obliczenia:**
```python
parcel_features = {
    # Edukacja
    "odleglosc_do_przedszkola": float,
    "odleglosc_do_szkoly_podstawowej": float,
    "odleglosc_do_szkoly_sredniej": float,
    "liczba_przedszkoli_w_promieniu_2km": int,

    # Handel i usługi
    "odleglosc_do_sklepu": float,  # hipermarket/supermarket
    "odleglosc_do_apteki": float,
    "liczba_sklepow_w_promieniu_1km": int,

    # Zdrowie
    "odleglosc_do_przychodni": float,
    "odleglosc_do_szpitala": float,

    # Sąsiedztwo - charakter zabudowy
    "procent_zabudowy_jednorodzinnej_500m": float,
    "procent_zabudowy_wielorodzinnej_500m": float,
    "procent_zabudowy_przemyslowej_500m": float,
    "liczba_budynkow_w_promieniu_100m": int,

    # Bezpieczeństwo
    "odleglosc_do_straz_pozarnej": float,
    "odleglosc_do_policji": float,
}
```

### 3.3 KU - Kompleksy użytkowania terenu

| Klasa | Przykłady | Wykorzystanie |
|-------|-----------|---------------|
| KUMN | Osiedle, posesja | Charakter sąsiedztwa |
| KUPG | Elektrownia, kopalnia, oczyszczalnia | Uciążliwości |
| KUHU | Centrum handlowe, targowisko | Dostęp do zakupów |
| KUKO | Dworzec, parking, stacja paliw | Komunikacja |
| KUSK | Ogród, park, ośrodek sportowy | Rekreacja |
| KUHO | Hotel, kemping | Turystyka |
| KUOS | Szkoła, przedszkole, uczelnia | Edukacja |
| KUOZ | Szpital, sanatorium | Zdrowie |
| KUZA | Zespół pałacowy, muzeum | Kultura |
| KUSC | Cmentarz, kościół | Infrastruktura społeczna |

**Cechy:**
```python
{
    "odleglosc_do_parku": float,
    "odleglosc_do_osrodka_sportowego": float,
    "odleglosc_do_cmentarza": float,  # potencjalna uciążliwość
    "odleglosc_do_zakladu_przemyslowego": float,
    "odleglosc_do_oczyszczalni": float,
    "w_obrebie_osiedla": bool,
}
```

### 3.4 PT - Pokrycie terenu

| Klasa | Rodzaje | Wykorzystanie |
|-------|---------|---------------|
| PTZB | Zabudowa (jednorodzinna, wielorodzinna, przemysłowa) | Charakter okolicy |
| PTLZ | Las, zadrzewienie, zagajnik | Tereny zielone |
| PTTR | Roślinność trawiasta, uprawa rolna | Charakter rolniczy |
| PTWP | Woda (morska, płynąca, stojąca) | Atrakcyjność |
| PTKM | Teren pod drogami | Komunikacja |

**Cechy:**
```python
{
    # Pokrycie działki
    "pokrycie_dzialki": str,  # zabudowana/las/pole/woda/inne

    # Sąsiedztwo (promień 500m)
    "procent_lasu_500m": float,
    "procent_zabudowy_500m": float,
    "procent_pol_500m": float,
    "procent_wody_500m": float,

    # Wskaźniki
    "blisko_lasu": bool,  # <200m
    "blisko_wody": bool,  # <500m
}
```

### 3.5 SW - Sieć wodna (ograniczone użycie)

**Tylko jako wskaźnik atrakcyjności:**
```python
{
    "odleglosc_do_jeziora": float,
    "odleglosc_do_rzeki": float,
    "nad_woda": bool,  # działka przylega do wody
}
```

### 3.6 TC - Tereny chronione

| Klasa | Wykorzystanie |
|-------|---------------|
| TCON - Natura 2000 | Ograniczenia zabudowy |
| TCPK - Park krajobrazowy | Ograniczenia, walory |
| TCPN - Park narodowy | Ograniczenia |
| TCRZ - Rezerwat | Ograniczenia |

**Cechy:**
```python
{
    "w_obszarze_natura2000": bool,
    "w_parku_krajobrazowym": bool,
    "odleglosc_do_rezerwatu": float,
    "w_strefie_ochronnej": bool,
}
```

### 3.7 AD - Jednostki podziału terytorialnego

```python
{
    "gmina_teryt": str,
    "gmina_nazwa": str,
    "miejscowosc": str,
    "typ_miejscowosci": str,  # miasto/wieś/osada
    "liczba_mieszkancow_miejscowosci": int,  # jeśli dostępne
}
```

---

## 4. Obliczanie powierzchni działki

```python
import geopandas as gpd

# Wczytanie działek
parcels_gdf = gpd.read_file("parcels.gpkg")

# Konwersja do układu metrycznego (EPSG:2180 - PUWG 1992)
parcels_gdf = parcels_gdf.to_crs(epsg=2180)

# Obliczenie powierzchni w m²
parcels_gdf["powierzchnia_m2"] = parcels_gdf.geometry.area

# Kategorie powierzchni
def kategoryzuj_powierzchnie(pow_m2):
    if pow_m2 < 500:
        return "mala"
    elif pow_m2 < 1000:
        return "srednia"
    elif pow_m2 < 2000:
        return "duza"
    else:
        return "bardzo_duza"

parcels_gdf["kategoria_pow"] = parcels_gdf["powierzchnia_m2"].apply(kategoryzuj_powierzchnie)
```

---

## 5. Architektura rozwiązania z SRAI

### 5.1 Pipeline przetwarzania danych

```
┌──────────────────┐     ┌───────────────────┐     ┌─────────────────┐
│  DZIAŁKI         │     │     BDOT10k       │     │   KIEG + MPZP   │
│  (GeoDataFrame)  │     │   (GeoDataFrame)  │     │   (atrybuty)    │
└────────┬─────────┘     └─────────┬─────────┘     └────────┬────────┘
         │                         │                        │
         └─────────────┬───────────┘                        │
                       ▼                                    │
              ┌────────────────┐                           │
              │ IntersectionJoiner                         │
              │ (przypisanie cech                          │
              │  BDOT10k do działek)                       │
              └────────┬───────┘                           │
                       │                                    │
                       ▼                                    │
              ┌────────────────┐                           │
              │ Feature Engineering                        │
              │ + merge KIEG/MPZP  ◄────────────────────────┘
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │   EMBEDDER     │
              │ (CountEmbedder │
              │  lub Hex2Vec)  │
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │   WEKTOR       │
              │   DZIAŁKI      │
              │  (d-wymiarowy) │
              └────────────────┘
```

### 5.2 Adaptacja SRAI do działek (zamiast H3)

**Kluczowa modyfikacja**: SRAI standardowo używa H3/S2 jako regionów.
W naszym przypadku **działki ewidencyjne są naturalnymi regionami**.

```python
# Zamiast H3Regionalizer używamy działek jako regionów
regions_gdf = parcels_gdf  # GeoDataFrame z geometriami działek

# Joiner łączy cechy BDOT10k z działkami
joiner = IntersectionJoiner()
joint = joiner.transform(regions_gdf, bdot10k_features)

# Embedder tworzy wektory dla każdej działki
embedder = CountEmbedder()  # lub ContextualCountEmbedder
embeddings = embedder.transform(regions_gdf, bdot10k_features, joint)
```

---

## 6. Cechy do ekstrakcji z BDOT10k

### 6.1 Cechy bezpośrednie (na działce)
| Kategoria | Cechy | Typ |
|-----------|-------|-----|
| PT - Pokrycie | Typ zabudowy, las/zadrzewienie, woda | categorical |
| BU - Budynki | Typy budynków na działce, liczba kondygnacji | count/categorical |
| TC - Tereny chronione | Natura 2000, park krajobrazowy, rezerwat | boolean |

### 6.2 Cechy kontekstowe (bufor wokół działki)
| Kategoria | Cechy | Metryka |
|-----------|-------|---------|
| SK - Komunikacja | Odległość do drogi głównej/ekspresowej/autostrady | distance (m) |
| SK - Komunikacja | Odległość do przystanku autobusowego/kolejowego | distance (m) |
| SK - Komunikacja | Dostępność ścieżek rowerowych | boolean/distance |
| KU - Kompleksy | Odległość do: szkoły, przedszkola, szpitala, parku | distance (m) |
| KU - Kompleksy | Odległość do: centrum handlowego, stacji paliw | distance (m) |
| SW - Woda | Bliskość rzeki/jeziora | distance (m) |
| PT - Pokrycie | % lasu w promieniu 500m/1km | percentage |
| TC - Chronione | Bliskość terenów chronionych | distance (m) |

### 6.3 Cechy z KIEG
| Cecha | Opis | Typ |
|-------|------|-----|
| Klasa bonitacyjna | I-VI (jakość gleby rolnej) | ordinal |
| Grupa rejestrowa | Struktura właścicielska (SP, prywatna, etc.) | categorical |

### 6.4 Cechy planistyczne
| Cecha | Opis | Typ |
|-------|------|-----|
| MPZP | Czy działka pod MPZP | boolean |
| Przeznaczenie w MPZP | Mieszkaniowe/usługowe/rolne/etc. | categorical (jeśli dostępne) |

---

## 7. Strategie embeddingu

### Opcja A: CountEmbedder (prosty, bez treningu)
```python
from srai.embedders import CountEmbedder

embedder = CountEmbedder()
# Tworzy wektor zliczający wystąpienia każdego typu obiektu BDOT10k na działce
```

**Zalety**: Szybki, interpretowalny, nie wymaga treningu
**Wady**: Nie uwzględnia kontekstu przestrzennego

### Opcja B: ContextualCountEmbedder (z kontekstem sąsiedztwa)
```python
from srai.embedders import ContextualCountEmbedder
from srai.neighbourhoods import AdjacencyNeighbourhood

neighbourhood = AdjacencyNeighbourhood(parcels_gdf)
embedder = ContextualCountEmbedder(neighbourhood=neighbourhood)
```

**Zalety**: Uwzględnia cechy sąsiednich działek
**Wady**: Bardziej złożony

### Opcja C: Custom Embedder (hybrydowy)
Połączenie:
1. CountEmbedder dla cech bezpośrednich
2. Obliczone odległości jako dodatkowe wymiary
3. One-hot encoding dla cech kategorycznych (KIEG, MPZP)

---

## 8. System rekomendacji

### 8.1 Wyszukiwanie podobnych działek
```python
from sklearn.neighbors import NearestNeighbors

# Trening modelu k-NN na embeddingach
knn = NearestNeighbors(n_neighbors=10, metric='cosine')
knn.fit(embeddings_matrix)

# Dla wybranej działki znajdź podobne
distances, indices = knn.kneighbors(target_embedding)
```

### 8.2 Wyszukiwanie na podstawie preferencji użytkownika

**Preferencje użytkownika** → **Wektor preferencji** → **Cosine similarity**

```python
def create_preference_vector(preferences: dict) -> np.array:
    """
    preferences = {
        'blisko_lasu': 0.8,        # waga 0-1
        'blisko_szkoly': 0.9,
        'cisza': 0.7,              # daleko od głównych dróg
        'uzbrojenie_pelne': 1.0,
        'teren_chroniony': 0.3,    # niekoniecznie
        ...
    }
    """
    # Mapowanie preferencji na wymiary embeddingu
    return weighted_vector
```

### 8.3 Klasteryzacja działek
```python
from sklearn.cluster import KMeans

# Grupowanie działek w klastry o podobnych cechach
kmeans = KMeans(n_clusters=20)
clusters = kmeans.fit_predict(embeddings_matrix)

# Etykiety klastrów: "Działki leśne z dobrym dojazdem",
#                   "Działki miejskie z pełnym uzbrojeniem", etc.
```

---

## 9. Architektura aplikacji

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│   Web (React/Vue) / Mobile (React Native/Flutter)               │
│   - Mapa z działkami                                            │
│   - Panel preferencji (suwaki, checkboxy)                       │
│   - Lista wyników z kartami działek                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API / GraphQL
┌─────────────────────────────▼───────────────────────────────────┐
│                        BACKEND                                   │
│   FastAPI / Django                                              │
│   - /api/search - wyszukiwanie po preferencjach                 │
│   - /api/similar/{id} - podobne działki                         │
│   - /api/parcel/{id} - szczegóły działki                        │
│   - /api/clusters - lista klastrów                              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                     DATA LAYER                                   │
│   - PostgreSQL + PostGIS (geometrie, atrybuty)                  │
│   - Redis (cache embeddingów, wyników)                          │
│   - Faiss/Milvus (wektorowe wyszukiwanie podobieństwa)          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                   PREPROCESSING PIPELINE                         │
│   (uruchamiany offline / batch)                                 │
│   - SRAI: Joiner + Embedder                                     │
│   - Feature engineering                                         │
│   - Trening modeli (k-NN, klastry)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Przykładowe preferencje użytkownika

### Profil "Rodzina z dziećmi"
- Blisko szkoły/przedszkola: ★★★★★
- Blisko parku/placu zabaw: ★★★★☆
- Cisza (daleko od głównych dróg): ★★★☆☆
- Pełne uzbrojenie: ★★★★★
- Komunikacja publiczna: ★★★★☆

### Profil "Działka rekreacyjna"
- Blisko lasu: ★★★★★
- Blisko wody: ★★★★☆
- Cisza: ★★★★★
- Pełne uzbrojenie: ★★☆☆☆
- Teren chroniony w pobliżu: ★★★☆☆

### Profil "Inwestor"
- MPZP: ★★★★★ (wymagane)
- Dobry dojazd: ★★★★★
- Pełne uzbrojenie: ★★★★☆
- Klasa bonitacyjna niska: ★★★☆☆ (łatwiej odrolnić)

---

## 11. Implementacja krok po kroku

### Krok 1: Przygotowanie danych
1. Załadowanie geometrii działek do GeoDataFrame
2. Załadowanie warstw BDOT10k (GML → GeoDataFrame)
3. Merge danych KIEG i MPZP z działkami

### Krok 2: Feature engineering
1. Spatial join BDOT10k → działki (cechy bezpośrednie)
2. Buffer analysis dla cech kontekstowych (odległości)
3. Normalizacja cech numerycznych

### Krok 3: Embedding z SRAI
```python
from srai.joiners import IntersectionJoiner
from srai.embedders import CountEmbedder

joiner = IntersectionJoiner()
joint = joiner.transform(parcels_gdf, bdot10k_gdf)

embedder = CountEmbedder()
embeddings = embedder.transform(parcels_gdf, bdot10k_gdf, joint)
```

### Krok 4: Budowa indeksu wektorowego
```python
import faiss

# Normalizacja dla cosine similarity
embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

# Budowa indeksu FAISS
index = faiss.IndexFlatIP(embeddings_norm.shape[1])
index.add(embeddings_norm)
```

### Krok 5: API wyszukiwania
```python
@app.get("/api/search")
async def search_parcels(preferences: PreferencesModel):
    preference_vector = create_preference_vector(preferences)
    distances, indices = index.search(preference_vector, k=100)
    return parcels_gdf.iloc[indices].to_dict()
```

---

## 12. Wartość dodana projektu

1. **Personalizacja** - każdy użytkownik ma inne potrzeby
2. **Odkrywanie** - system może znaleźć działki, których użytkownik by nie znalazł
3. **Porównywalność** - embeddingi umożliwiają obiektywne porównanie działek
4. **Skalowalność** - wyszukiwanie wektorowe jest bardzo szybkie (ms)

---

## 13. Knowledge Graph MPZP (Neo4j)

### 13.1 Cel
Stworzenie grafowej bazy wiedzy z uchwał MPZP umożliwiającej:
- Odpowiadanie na pytania w języku naturalnym (RAG)
- Wyszukiwanie działek po przeznaczeniu planistycznym
- Analizę ograniczeń zabudowy

### 13.2 Schemat grafu (Node types)

```
(:Gmina {teryt, nazwa})
    -[:POSIADA_MPZP]->
(:MPZP {numer_uchwaly, data, nazwa, status})
    -[:WYZNACZA_TEREN]->
(:TerenMPZP {symbol, przeznaczenie_podstawowe, przeznaczenie_dopuszczalne})
    -[:OBEJMUJE]->
(:Dzialka {id, nr_ewid, obreb, powierzchnia})

(:TerenMPZP)
    -[:MA_PARAMETR]->
(:ParametrZabudowy {typ, wartosc})
    # np. max_wysokosc: "12m", intensywnosc: "0.8", pow_biologicznie_czynna: "30%"

(:TerenMPZP)
    -[:POSIADA_OGRANICZENIE]->
(:Ograniczenie {typ, opis})
    # np. strefa_ochronna, linia_zabudowy, ochrona_konserwatorska

(:MPZP)
    -[:POCHODZI_Z_DOKUMENTU]->
(:DokumentMPZP {url, tekst_peln, data_pobrania})
```

### 13.3 Relacje dodatkowe

```cypher
// Działka może być częściowo w różnych terenach MPZP
(:Dzialka)-[:W_TERENIE {procent_pow}]->(:TerenMPZP)

// Symbole terenów MPZP (standardowe)
(:SymbolMPZP {kod: "MN", nazwa: "Zabudowa mieszkaniowa jednorodzinna"})
(:SymbolMPZP {kod: "MW", nazwa: "Zabudowa mieszkaniowa wielorodzinna"})
(:SymbolMPZP {kod: "U", nazwa: "Zabudowa usługowa"})
(:SymbolMPZP {kod: "R", nazwa: "Tereny rolne"})
(:SymbolMPZP {kod: "ZL", nazwa: "Lasy"})
// ... etc.

(:TerenMPZP)-[:MA_SYMBOL]->(:SymbolMPZP)
```

### 13.4 Pipeline ETL dla uchwał MPZP

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Źródła MPZP    │     │   Ekstrakcja     │     │   Knowledge     │
│  - BIP gmin     │────▶│   LLM-powered    │────▶│   Graph         │
│  - geoportale   │     │   (Claude/GPT)   │     │   (Neo4j)       │
│  - PDF/DOC      │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

#### Krok 1: Pobranie dokumentów
```python
# Lista gmin województwa pomorskiego z aktami MPZP
# Źródła: BIP, lokalne geoportale, SIPWP (System Informacji Przestrzennej Woj. Pomorskiego)
```

#### Krok 2: Ekstrakcja strukturalna (LLM)
```python
extraction_prompt = """
Przeanalizuj tekst uchwały MPZP i wyodrębnij:
1. Numer i datę uchwały
2. Obszar objęty planem (granice, obręby)
3. Dla każdego terenu (np. 1MN, 2U):
   - Symbol i przeznaczenie podstawowe
   - Przeznaczenie dopuszczalne
   - Parametry zabudowy (wysokość, intensywność, pow. biol. czynna)
   - Linie zabudowy
   - Ograniczenia (strefy ochronne, ochrona konserwatorska)

Zwróć dane w formacie JSON.
"""
```

#### Krok 3: Spatial join z działkami
```python
# Rysunki MPZP (GeoJSON/Shapefile) + działki
# Przypisanie: która działka w którym terenie MPZP
```

### 13.5 RAG na uchwałach MPZP

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Pytanie        │     │   Graph RAG      │     │   Odpowiedź     │
│  użytkownika    │────▶│   Retrieval +    │────▶│   z kontekstem  │
│                 │     │   Generation     │     │   prawnym       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

#### Przykładowe pytania użytkownika:
1. "Czy na działce 123/4 w Gdańsku mogę wybudować dom jednorodzinny?"
2. "Jaka jest maksymalna wysokość zabudowy na tej działce?"
3. "Czy działka jest objęta ochroną konserwatorską?"
4. "Jakie są ograniczenia dla zabudowy usługowej w tym terenie?"

#### Implementacja RAG:
```python
from langchain_community.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain

# 1. Połączenie z Neo4j
graph = Neo4jGraph(url="bolt://localhost:7687", username="neo4j", password="...")

# 2. Chain do odpowiadania na pytania
qa_chain = GraphCypherQAChain.from_llm(
    llm=Claude(),
    graph=graph,
    verbose=True,
    return_intermediate_steps=True
)

# 3. Pytanie z kontekstem działki
response = qa_chain.run("""
Działka o ID 226101_2.0001.123/4 w gminie Gdańsk.
Pytanie: Czy mogę tu wybudować dom jednorodzinny?
""")
```

### 13.6 Integracja z systemem rekomendacji

```python
# Rozszerzony wektor cech działki o dane z MPZP
parcel_features = {
    # Cechy z BDOT10k (embeddingi SRAI)
    "srai_embedding": [...],

    # Cechy z Knowledge Graph MPZP
    "mpzp_przeznaczenie": "MN",  # zabudowa jednorodzinna
    "mpzp_max_wysokosc": 12,
    "mpzp_intensywnosc": 0.4,
    "mpzp_pow_biol_czynna": 0.4,
    "mpzp_ograniczenia": ["strefa_ochrony_konserwatorskiej"],

    # Boolean flags
    "czy_budowlana": True,
    "czy_uslugowa": False,
    "czy_rolna": False,
}
```

---

## 14. Zrewidowana architektura (z Knowledge Graph)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Leaflet)                   │
│   - Mapa z działkami (kolory wg przeznaczenia MPZP)                │
│   - Panel preferencji                                               │
│   - Chat RAG do pytań o MPZP                                        │
│   - Karty działek z parametrami zabudowy                           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ REST API / GraphQL
┌─────────────────────────────▼───────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│   /api/search          - wyszukiwanie działek                       │
│   /api/parcel/{id}     - szczegóły + dane MPZP                      │
│   /api/mpzp/chat       - RAG na dokumentach MPZP                    │
│   /api/mpzp/params/{id} - parametry zabudowy dla działki           │
└────────────┬─────────────────────────────┬──────────────────────────┘
             │                             │
┌────────────▼─────────────┐  ┌────────────▼──────────────────────────┐
│  PostgreSQL + PostGIS    │  │         Neo4j                         │
│  - geometrie działek     │  │  - Knowledge Graph MPZP               │
│  - atrybuty BDOT10k      │  │  - relacje teren-działka              │
│  - embeddingi SRAI       │  │  - parametry zabudowy                 │
└──────────────────────────┘  └───────────────────────────────────────┘
             │                             │
┌────────────▼─────────────┐  ┌────────────▼──────────────────────────┐
│  Faiss / Milvus          │  │  Vector Store (embeddingi dokumentów) │
│  - wyszukiwanie          │  │  - ChromaDB / Pinecone                │
│    wektorowe działek     │  │  - chunki tekstów uchwał MPZP        │
└──────────────────────────┘  └───────────────────────────────────────┘
```

---

## 15. Priorytetyzacja implementacji

### Faza 1: MVP
- [ ] Załadowanie geometrii działek (woj. pomorskie)
- [ ] Przetworzenie BDOT10k (GML → PostGIS)
- [ ] Pipeline SRAI: Joiner + CountEmbedder
- [ ] Podstawowe API wyszukiwania
- [ ] Frontend: mapa + filtry podstawowe

### Faza 2: Knowledge Graph MPZP
- [ ] Pobranie uchwał MPZP dla głównych gmin
- [ ] Ekstrakcja LLM → Neo4j
- [ ] Spatial join rysunki MPZP ↔ działki
- [ ] Rozszerzenie API o dane MPZP
- [ ] Frontend: wizualizacja przeznaczenia

### Faza 3: RAG i zaawansowane funkcje
- [ ] Vector store na dokumentach MPZP
- [ ] Chat RAG w aplikacji
- [ ] Zaawansowane filtrowanie (parametry zabudowy)
- [ ] Eksport raportów dla działek

### Faza 4: Optymalizacja i skalowanie
- [ ] Caching (Redis)
- [ ] Optymalizacja zapytań przestrzennych
- [ ] A/B testing rekomendacji
- [ ] Mobile-responsive design

---

## 16. Kluczowe pliki do utworzenia

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── api/
│   │   │   ├── search.py           # wyszukiwanie działek
│   │   │   ├── parcels.py          # CRUD działek
│   │   │   └── mpzp.py             # RAG endpoint
│   │   ├── services/
│   │   │   ├── srai_embedder.py    # pipeline SRAI
│   │   │   ├── graph_service.py    # Neo4j queries
│   │   │   └── rag_service.py      # LangChain RAG
│   │   └── models/
│   │       └── schemas.py          # Pydantic models
│   └── scripts/
│       ├── load_bdot10k.py         # ETL BDOT10k
│       ├── load_mpzp.py            # ETL uchwały MPZP
│       └── compute_embeddings.py   # SRAI batch
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.tsx             # Leaflet map
│   │   │   ├── SearchPanel.tsx     # filtry
│   │   │   ├── ParcelCard.tsx      # karta działki
│   │   │   └── ChatMPZP.tsx        # RAG chat
│   │   └── services/
│   │       └── api.ts              # API client
│   └── package.json
├── data/
│   ├── bdot10k/                    # pliki GML
│   ├── parcels/                    # geometrie działek
│   └── mpzp/                       # dokumenty MPZP
└── docker-compose.yml              # PostgreSQL, Neo4j, Redis
```

---

## 17. AI Agent - Konwersacyjny interfejs wyszukiwania

### 17.1 Cel

Zamiast tradycyjnych filtrów, użytkownik prowadzi naturalną rozmowę z AI agentem, który:
- Zadaje pytania o preferencje
- Buduje profil wyszukiwania
- Pokazuje wyniki progresywnie (najpierw liczba, potem szczegóły)
- Zarządza monetyzacją (kredyty za pełne dane)

### 17.2 Architektura Agenta

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Chat UI)                        │
│   - React/React Native                                       │
│   - WebSocket dla real-time                                  │
│   - Mapa Leaflet z wizualizacją działek                     │
└─────────────────────────────┬───────────────────────────────┘
                              │ WebSocket / REST
┌─────────────────────────────▼───────────────────────────────┐
│                    BACKEND (FastAPI)                         │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           CONVERSATION SERVICE                       │   │
│   │   - Session state (preferences, revealed plots)     │   │
│   │   - Credit balance tracking                          │   │
│   │   - Tool execution engine                            │   │
│   └─────────────────────────────────────────────────────┘   │
│                              │                               │
│   ┌─────────────────────────▼───────────────────────────┐   │
│   │           CLAUDE API (Anthropic)                     │   │
│   │   - Tool definitions                                 │   │
│   │   - Conversation context                             │   │
│   │   - Response streaming                               │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 17.3 Definicje Narzędzi (Tools)

#### Tool 1: `set_location_preference`
```json
{
  "name": "set_location_preference",
  "description": "Ustaw preferencje lokalizacji działki",
  "parameters": {
    "type": "object",
    "properties": {
      "gmina": {
        "type": "string",
        "description": "Nazwa gminy (np. 'Sopot', 'Gdańsk')"
      },
      "miejscowosc": {
        "type": "string",
        "description": "Nazwa miejscowości"
      },
      "near_point": {
        "type": "object",
        "properties": {
          "lat": {"type": "number"},
          "lon": {"type": "number"}
        }
      },
      "radius_km": {
        "type": "number",
        "description": "Promień wyszukiwania w km (domyślnie 10)"
      }
    }
  }
}
```

#### Tool 2: `set_area_preference`
```json
{
  "name": "set_area_preference",
  "description": "Ustaw zakres powierzchni działki",
  "parameters": {
    "type": "object",
    "properties": {
      "min_m2": {
        "type": "number",
        "description": "Minimalna powierzchnia w m2"
      },
      "max_m2": {
        "type": "number",
        "description": "Maksymalna powierzchnia w m2"
      }
    },
    "required": ["min_m2"]
  }
}
```

#### Tool 3: `set_purpose_preference`
```json
{
  "name": "set_purpose_preference",
  "description": "Ustaw przeznaczenie działki według MPZP",
  "parameters": {
    "type": "object",
    "properties": {
      "purpose": {
        "type": "string",
        "enum": ["MN", "MW", "U", "MN/U", "R", "ZL", "any"],
        "description": "MN=jednorodzinna, MW=wielorodzinna, U=usługowa, R=rolna, ZL=leśna"
      },
      "require_mpzp": {
        "type": "boolean",
        "description": "Czy wymagany plan miejscowy (domyślnie false)"
      }
    }
  }
}
```

#### Tool 4: `set_proximity_preferences`
```json
{
  "name": "set_proximity_preferences",
  "description": "Ustaw wagi dla bliskości różnych obiektów",
  "parameters": {
    "type": "object",
    "properties": {
      "forest": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "description": "Waga bliskości lasu (0=nieważne, 1=bardzo ważne)"
      },
      "school": {
        "type": "number",
        "description": "Waga bliskości szkoły/przedszkola"
      },
      "shop": {
        "type": "number",
        "description": "Waga bliskości sklepów"
      },
      "public_transport": {
        "type": "number",
        "description": "Waga bliskości komunikacji publicznej"
      },
      "quiet": {
        "type": "number",
        "description": "Waga ciszy (daleko od głównych dróg)"
      },
      "water": {
        "type": "number",
        "description": "Waga bliskości wody (jezioro, rzeka)"
      }
    }
  }
}
```

#### Tool 5: `count_matching_plots`
```json
{
  "name": "count_matching_plots",
  "description": "Policz działki spełniające aktualne kryteria",
  "parameters": {
    "type": "object",
    "properties": {}
  },
  "returns": {
    "type": "object",
    "properties": {
      "count": {"type": "integer"},
      "top_gminas": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Top 5 gmin z największą liczbą wyników"
      }
    }
  }
}
```

#### Tool 6: `get_top_matches`
```json
{
  "name": "get_top_matches",
  "description": "Pobierz najlepiej dopasowane działki",
  "parameters": {
    "type": "object",
    "properties": {
      "limit": {
        "type": "integer",
        "default": 3,
        "maximum": 10,
        "description": "Liczba działek do zwrócenia"
      },
      "offset": {
        "type": "integer",
        "default": 0
      }
    }
  },
  "returns": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},
        "approximate_location": {
          "type": "object",
          "description": "Przybliżona lokalizacja (offset 100-500m)"
        },
        "area_m2": {"type": "number"},
        "gmina": {"type": "string"},
        "similarity_score": {"type": "number"},
        "key_features": {"type": "array"}
      }
    }
  }
}
```

#### Tool 7: `reveal_plot_details`
```json
{
  "name": "reveal_plot_details",
  "description": "Odkryj pełne szczegóły działki (koszt: 1 kredyt)",
  "parameters": {
    "type": "object",
    "properties": {
      "plot_id": {
        "type": "string",
        "description": "ID działki do odkrycia"
      }
    },
    "required": ["plot_id"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "credits_remaining": {"type": "integer"},
      "plot_details": {
        "type": "object",
        "properties": {
          "exact_location": {"type": "object"},
          "nr_ewidencyjny": {"type": "string"},
          "obreb": {"type": "string"},
          "mpzp_details": {"type": "object"},
          "distances": {"type": "object"},
          "neighborhood_stats": {"type": "object"}
        }
      }
    }
  }
}
```

#### Tool 8: `initiate_payment`
```json
{
  "name": "initiate_payment",
  "description": "Rozpocznij proces zakupu kredytów",
  "parameters": {
    "type": "object",
    "properties": {
      "package": {
        "type": "string",
        "enum": ["single", "pack_10", "pack_25"],
        "description": "single=1 PLN, pack_10=9 PLN, pack_25=20 PLN"
      }
    },
    "required": ["package"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "checkout_url": {"type": "string"},
      "session_id": {"type": "string"}
    }
  }
}
```

#### Tool 9: `submit_lead`
```json
{
  "name": "submit_lead",
  "description": "Zgłoś zainteresowanie zakupem działki",
  "parameters": {
    "type": "object",
    "properties": {
      "plot_id": {"type": "string"},
      "contact": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "phone": {"type": "string"},
          "email": {"type": "string"}
        },
        "required": ["phone"]
      },
      "intent": {
        "type": "object",
        "properties": {
          "proposed_price_pln": {"type": "number"},
          "financing": {"type": "string", "enum": ["cash", "mortgage", "undecided"]},
          "timeline_months": {"type": "integer"}
        }
      }
    },
    "required": ["plot_id", "contact"]
  }
}
```

### 17.4 Przykładowe konwersacje

#### Scenariusz 1: Rodzina szuka działki pod dom

```
USER: Cześć, szukam działki pod budowę domu dla rodziny

AGENT: Dzień dobry! Chętnie pomogę znaleźć idealną działkę.
       Zacznijmy od lokalizacji - w jakiej okolicy szukacie?

USER: Gdzieś w okolicach Trójmiasta, ale niekoniecznie w samym Gdańsku

AGENT: [set_location_preference(gmina=["Gdańsk","Sopot","Gdynia","Pruszcz Gdański","Żukowo","Kolbudy"], radius_km=20)]
       Rozumiem - szerokie okolice Trójmiasta. Jakiej powierzchni działki szukacie?

USER: Około 1000 metrów, może trochę więcej

AGENT: [set_area_preference(min_m2=900, max_m2=1500)]
       Świetnie. A co jest dla Was ważne w otoczeniu?
       - Bliskość lasu czy parku?
       - Szkoła/przedszkole w pobliżu?
       - Cisza czy raczej dobry dojazd?

USER: Zdecydowanie las i cisza, mamy małe dzieci więc przedszkole by się przydało

AGENT: [set_purpose_preference(purpose="MN")]
       [set_proximity_preferences(forest=0.9, quiet=0.8, school=0.7, shop=0.3)]
       [count_matching_plots]

       Mam dobre wieści! Znalazłem 87 działek spełniających Wasze kryteria.
       Najwięcej w gminach: Żukowo (23), Kolbudy (18), Pruszcz Gdański (15).

       Pokazuję 3 najlepiej dopasowane:
       [get_top_matches(limit=3)]

       1. **Działka w Chwaszczynie** (gmina Żukowo)
          - ~1050 m², 300m do lasu, przedszkole 1.2 km
          - Dopasowanie: 94%

       2. **Działka w Borkowie** (gmina Kolbudy)
          - ~1120 m², bezpośrednio przy lesie, szkoła 800m
          - Dopasowanie: 91%

       3. **Działka w Straszynie** (gmina Pruszcz Gd.)
          - ~980 m², 200m do lasu, cicha okolica
          - Dopasowanie: 89%

       Chcecie zobaczyć dokładne lokalizacje i szczegóły?

USER: Ta w Borkowie brzmi świetnie, pokaż szczegóły

AGENT: [reveal_plot_details(plot_id="2262.0004.123/5")]

       ❌ Ups! Nie masz jeszcze kredytów. Pełne dane działki kosztują 1 PLN.

       Pakiety:
       - 1 działka = 1 PLN
       - 10 działek = 9 PLN (oszczędzasz 10%)
       - 25 działek = 20 PLN (oszczędzasz 20%)

       Który pakiet wybrać?

USER: Wezmę 10

AGENT: [initiate_payment(package="pack_10")]

       Przekierowuję do płatności (BLIK, karta, Przelewy24)...
       [Link do Stripe Checkout]
```

#### Scenariusz 2: Inwestor szuka działki pod apartamenty

```
USER: Szukam działki pod mały budynek wielorodzinny w Gdańsku

AGENT: Rozumiem - zabudowa wielorodzinna (MW) w Gdańsku.
       [set_location_preference(gmina="Gdańsk")]
       [set_purpose_preference(purpose="MW", require_mpzp=true)]

       Jaka minimalna powierzchnia Was interesuje?

USER: Minimum 2000 m2, a najlepiej większa

AGENT: [set_area_preference(min_m2=2000, max_m2=10000)]
       [count_matching_plots]

       W Gdańsku mam 34 działki z przeznaczeniem MW powyżej 2000 m².

       Najlepsze lokalizacje:
       - Orunia Górna: 8 działek
       - Kokoszki: 6 działek
       - Jasień: 5 działek

       Chcecie zobaczyć parametry zabudowy z MPZP (intensywność, wysokość)?

USER: Tak, pokaż te z największą dozwoloną intensywnością

AGENT: [get_top_matches(limit=5, sort_by="mpzp_intensity")]

       Top 5 działek wg intensywności zabudowy:

       1. **Orunia, ul. Platynowa** - 3200 m²
          - Intensywność: 1.2, max 18m, PBC 25%
          - Szacunkowe PUM: ~3800 m²

       2. **Kokoszki, ul. Budowlanych** - 2800 m²
          - Intensywność: 1.0, max 15m, PBC 30%
          - Szacunkowe PUM: ~2800 m²
       ...
```

### 17.5 System State Management

```python
@dataclass
class ConversationState:
    session_id: str
    user_id: Optional[str]

    # Preferences (built during conversation)
    preferences: SearchPreferences = field(default_factory=SearchPreferences)

    # Credits and revealed plots
    credits_balance: int = 3  # 3 free for new users
    revealed_plot_ids: Set[str] = field(default_factory=set)

    # Conversation history for Claude
    messages: List[dict] = field(default_factory=list)

    # Last search results (for pagination)
    last_search_results: List[str] = field(default_factory=list)


@dataclass
class SearchPreferences:
    # Location
    gminas: Optional[List[str]] = None
    near_point: Optional[Tuple[float, float]] = None
    radius_km: float = 10.0

    # Area
    min_area_m2: Optional[float] = None
    max_area_m2: Optional[float] = None

    # Purpose
    mpzp_purpose: Optional[str] = None  # MN, MW, U, R, ZL
    require_mpzp: bool = False

    # Proximity weights (0-1)
    weights: Dict[str, float] = field(default_factory=lambda: {
        'forest': 0.5,
        'school': 0.5,
        'shop': 0.3,
        'public_transport': 0.3,
        'quiet': 0.5,
        'water': 0.3
    })
```

### 17.6 Prompt systemowy dla Agenta

```python
SYSTEM_PROMPT = """
Jesteś asystentem pomagającym znaleźć idealną działkę budowlaną w województwie pomorskim.

## Twoja rola:
1. Prowadź naturalną rozmowę po polsku
2. Zadawaj pytania, aby zrozumieć potrzeby użytkownika
3. Używaj narzędzi do ustawiania preferencji i wyszukiwania
4. Wyjaśniaj wyniki w przystępny sposób

## Zasady:
- Zacznij od pytania o lokalizację, potem powierzchnię, potem preferencje
- Nie pokazuj więcej niż 3 działki na raz (darmowy tier)
- Dla pełnych szczegółów wymagaj kredytów
- Bądź pomocny, ale jasno komunikuj zasady płatności

## Dostępne narzędzia:
- set_location_preference: ustaw lokalizację
- set_area_preference: ustaw zakres powierzchni
- set_purpose_preference: ustaw przeznaczenie (MN, MW, U...)
- set_proximity_preferences: ustaw wagi bliskości (las, szkoła...)
- count_matching_plots: policz pasujące działki
- get_top_matches: pobierz najlepsze działki
- reveal_plot_details: odkryj szczegóły (kosztuje kredyt)
- initiate_payment: rozpocznij płatność
- submit_lead: zapisz zainteresowanie działką

## Skróty przeznaczenia MPZP:
- MN = zabudowa mieszkaniowa jednorodzinna
- MW = zabudowa mieszkaniowa wielorodzinna
- U = usługowa
- MN/U = mieszkaniowo-usługowa
- R = rolna
- ZL = leśna

Jeśli użytkownik pyta o coś poza zakresem (np. działki poza Pomorzem),
uprzejmie wyjaśnij, że obecnie obsługujesz tylko województwo pomorskie.
"""
```

### 17.7 Backend API dla Agenta

```python
# backend/app/api/conversation.py

from fastapi import APIRouter, WebSocket, Depends
from anthropic import Anthropic

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

@router.websocket("/ws/{session_id}")
async def conversation_websocket(
    websocket: WebSocket,
    session_id: str,
    conversation_service: ConversationService = Depends()
):
    await websocket.accept()

    # Load or create session state
    state = await conversation_service.get_or_create_state(session_id)

    try:
        while True:
            # Receive user message
            user_message = await websocket.receive_text()

            # Add to conversation history
            state.messages.append({"role": "user", "content": user_message})

            # Call Claude with tools
            response = await conversation_service.process_message(state)

            # Stream response back
            async for chunk in response:
                await websocket.send_json({
                    "type": "text" if chunk.type == "text" else "tool_result",
                    "content": chunk.content
                })

            # Send final state update
            await websocket.send_json({
                "type": "state_update",
                "credits": state.credits_balance,
                "revealed_count": len(state.revealed_plot_ids)
            })

    except WebSocketDisconnect:
        await conversation_service.save_state(state)


@router.post("/payment-webhook")
async def payment_webhook(
    payload: StripeWebhookPayload,
    conversation_service: ConversationService = Depends()
):
    """Stripe webhook - dodaj kredyty po płatności"""
    if payload.type == "checkout.session.completed":
        session_id = payload.data.object.client_reference_id
        credits = PACKAGE_CREDITS[payload.data.object.metadata.package]
        await conversation_service.add_credits(session_id, credits)
```

---

## 18. Monetyzacja i model biznesowy

### 18.1 Struktura cenowa

| Tier | Cena | Zawartość |
|------|------|-----------|
| FREE | 0 PLN | 3 działki z przybliżoną lokalizacją |
| Single | 1 PLN | 1 działka z pełnymi danymi |
| Pack 10 | 9 PLN | 10 działek (10% rabat) |
| Pack 25 | 20 PLN | 25 działek (20% rabat) |

### 18.2 Co zawiera "przybliżona" vs "pełna" lokalizacja

**Przybliżona (FREE):**
- Lokalizacja z offsetem 100-500m
- Nazwa gminy i miejscowości
- Przybliżona powierzchnia (±10%)
- Ogólne cechy (blisko lasu, szkoły w pobliżu)

**Pełna (PAID):**
- Dokładne współrzędne centroidu
- Numer ewidencyjny działki
- Nazwa obrębu
- Dokładna powierzchnia
- Pełne parametry MPZP
- Linki do dokumentów uchwał
- Dokładne odległości do POI

### 18.3 Lead Generation

```javascript
// MongoDB Schema for leads
{
  _id: ObjectId,
  plot_id: "2262.0001.123/4",
  created_at: ISODate,

  contact: {
    name: "Jan Kowalski",
    phone: "+48 600 123 456",
    email: "jan@example.com"
  },

  intent: {
    proposed_price_pln: 250000,
    financing_type: "mortgage",  // cash, mortgage, undecided
    timeline_months: 6,
    notes: "Szukam działki pod budowę domu dla 4-osobowej rodziny"
  },

  source: {
    session_id: "abc123",
    conversation_summary: "...",
    search_criteria: {...}
  },

  status: "new",  // new, contacted, qualified, converted, rejected
  assigned_to: null,

  follow_ups: [
    { date: ISODate, type: "call", notes: "...", next_action: "..." }
  ]
}
```

### 18.4 Stripe Integration

```python
# backend/app/services/payment_service.py

import stripe
from app.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

PACKAGES = {
    "single": {"credits": 1, "price_pln": 100},  # w groszach
    "pack_10": {"credits": 10, "price_pln": 900},
    "pack_25": {"credits": 25, "price_pln": 2000}
}

async def create_checkout_session(
    session_id: str,
    package: str,
    success_url: str,
    cancel_url: str
) -> str:
    """Utwórz sesję Stripe Checkout"""
    package_info = PACKAGES[package]

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card", "p24", "blik"],
        line_items=[{
            "price_data": {
                "currency": "pln",
                "product_data": {
                    "name": f"Kredyty działkowe ({package_info['credits']} szt.)",
                    "description": "Dostęp do pełnych danych działek"
                },
                "unit_amount": package_info["price_pln"]
            },
            "quantity": 1
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=session_id,
        metadata={"package": package}
    )

    return checkout.url
```
