# Plan przeprojektowania moja-dzialka v2

**Data:** 2026-01-22
**Region:** Trójmiasto (Gdańsk, Gdynia, Sopot)

---

## 1. Cel projektu

**moja-dzialka** - inteligentny agent do wyszukiwania działek budowlanych w Trójmieście.

### Problem
- Rozproszenie danych (kataster, POG, BDOT10k)
- Brak narzędzi do wyszukiwania po kryteriach jakościowych ("cicha okolica", "blisko lasu")
- Skomplikowane przepisy planistyczne

### Rozwiązanie
Web app z konwersacyjnym agentem AI który:
1. **Zbiera wymagania** - naturalny dialog o preferencjach
2. **Wyszukuje** - hybrydowe wyszukiwanie (graf + wektor + przestrzenne)
3. **Prezentuje** - zorganizowana prezentacja działek (opis, mapa, opcjonalnie 3D)
4. **Zbiera feedback** - iteracyjne doprecyzowanie
5. **Generuje leady** - zachęca do zakupu pakietu lub pozostawienia kontaktu

### Model biznesowy
- **FREE:** 3 działki w trybie prezentacji
- **Pakiety:**
  - 10 działek = 20 PLN
  - 50 działek = 40 PLN (do ustalenia)
- **Lead generation:** zbieranie danych kontaktowych zainteresowanych zakupem

### Kluczowe decyzje
- **3D terrain:** Na życzenie użytkownika przez rozmowę (nie przycisk)
- **Lead capture:** Zachęcić do zapłaty LUB pozostawienia kontaktu w celu zgłoszenia chęci zakupu
- **Płatność:** Model do zbadania - jakie możliwości integracji (Stripe, Przelewy24, BLIK?)

---

## 2. Dane źródłowe

### POG (Plany Ogólne Gmin)
Lokalizacja: `/home/marcin/moja-dzialka/pog/`
Dokumentacja: `docs/DATA_POG.md`

| Gmina | Plik | Rozmiar |
|-------|------|---------|
| Gdańsk | `pog-gdansk-proj-uzg-042025.gml` | 23.5 MB |
| Gdynia | `POG_Gdynia_projekt_uzg_032025_podpisany.gml` | 17.7 MB |
| Sopot | `POG_SOPOT_12092025.gml` | 3.4 MB |

### BDOT10k
Lokalizacja: `/home/marcin/moja-dzialka/bdot10k/`
Dokumentacja: `docs/DATA_BDOT10K.md`

### Działki
Lokalizacja: `/home/marcin/moja-dzialka/dzialki/dzialki_pomorskie.gpkg`
Dokumentacja: `docs/DATA_PARCELS.md`

---

## 3. Architektura baz danych

### PostGIS
**Cel:** Szybkie zapytania przestrzenne, wizualizacja, GeoJSON.

Tabele:
- `parcels` - działki z ~40 cechami
- `pog_zones` - strefy POG
- `poi` - punkty zainteresowania z BDOT10k

### Neo4j
**Cel:** Wyszukiwanie przez relacje, kontekst działki.

Węzły (10 typów):
- Dzialka, Gmina, Dzielnica
- StrefaPOG, ProfilFunkcji
- KategoriaCiszy, KategoriaNatury, KategoriaDostepnosci
- KlasaPowierzchni, TypZabudowy

Relacje (12 typów):
- W_GMINIE, W_DZIELNICY, W_STREFIE_POG
- MA_CISZE, MA_NATURE, MA_DOSTEPNOSC, MA_POWIERZCHNIE, MOZE_ZABUDOWAC
- BLISKO_LASU, BLISKO_WODY, BLISKO_SZKOLY, BLISKO_PRZYSTANKU, BLISKO_PRZEMYSLU

### Milvus
**Cel:** Wyszukiwanie podobieństwa.

- Wymiar wektora: 32
- Metoda: Feature-based embedding
- Index: IVF_FLAT, COSINE

---

## 4. Pipeline danych

| Krok | Skrypt | Output |
|------|--------|--------|
| 1 | `01_convert_pog.py` | `pog_trojmiasto.gpkg` |
| 2 | `02_filter_parcels.py` | `parcels_trojmiasto.gpkg` |
| 3 | `03_filter_bdot10k.py` | `bdot10k_trojmiasto/` |
| 4 | `04_feature_engineering.py` | `parcels_features.gpkg` |
| 5 | `05_import_postgis.py` | PostgreSQL tables |
| 6 | `06_import_neo4j.py` | Neo4j graph |
| 7 | `07_generate_embeddings.py` | `embeddings.npy` |
| 8 | `08_import_milvus.py` | Milvus collection |

---

## 5. Następne kroki

### Faza 1: Dokumentacja danych
- [x] `docs/DATA_POG.md`
- [x] `docs/DATA_BDOT10K.md`
- [x] `docs/DATA_PARCELS.md`

### Faza 2: Pipeline danych
- [ ] Skrypty 01-08

### Faza 3: Backend
- [ ] Refaktor serwisów
- [ ] Nowe narzędzia agenta

### Faza 4: Frontend
- [ ] Nowa forma prezentacji
- [ ] Lead capture / płatności
