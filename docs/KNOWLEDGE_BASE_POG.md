# Baza Wiedzy: Plany Ogólne Gmin (POG)

**Data utworzenia:** 2026-01-22
**Cel:** Kompletna baza wiedzy o POG dla systemu moja-dzialka i modelu LLM

---

## Spis treści

1. [Czym jest Plan Ogólny Gminy](#1-czym-jest-plan-ogólny-gminy)
2. [Podstawy prawne](#2-podstawy-prawne)
3. [Strefy planistyczne - pełny katalog](#3-strefy-planistyczne---pełny-katalog)
4. [Profile funkcjonalne](#4-profile-funkcjonalne)
5. [Parametry zabudowy](#5-parametry-zabudowy)
6. [Obszary Uzupełnienia Zabudowy (OUZ)](#6-obszary-uzupełnienia-zabudowy-ouz)
7. [Konsekwencje dla właściciela działki](#7-konsekwencje-dla-właściciela-działki)
8. [Słownik pojęć](#8-słownik-pojęć)
9. [Interpretacje dla agenta LLM](#9-interpretacje-dla-agenta-llm)

---

## 1. Czym jest Plan Ogólny Gminy

### 1.1 Definicja

**Plan Ogólny Gminy (POG)** to nowe, obowiązkowe narzędzie planistyczne wprowadzone reformą planowania przestrzennego z 2023 roku. Jest to **akt prawa miejscowego**, co oznacza, że:

- Jest prawem powszechnie obowiązującym na terenie gminy
- Wiąże zarówno organy administracji, jak i mieszkańców
- Stanowi podstawę do wydawania decyzji o warunkach zabudowy
- Jest podstawą do sporządzania miejscowych planów zagospodarowania przestrzennego (MPZP)

### 1.2 Co zastępuje?

POG zastępuje dotychczasowe **Studium uwarunkowań i kierunków zagospodarowania przestrzennego**, które:
- Nie było aktem prawa miejscowego (nie wiązało bezpośrednio)
- Było tylko dokumentem kierunkowym dla gminy
- Nie miało bezpośredniego wpływu na wydawanie WZ

### 1.3 Kluczowe terminy

| Termin | Znaczenie |
|--------|-----------|
| **24 września 2023** | Wejście w życie nowelizacji ustawy |
| **30 czerwca 2026** | Ostateczny termin uchwalenia POG przez gminy |
| **1 stycznia 2026** | Nowe WZ ważne tylko 5 lat (wcześniej bezterminowo) |

### 1.4 Co zawiera Plan Ogólny?

1. **Strefy planistyczne** - podział całego terenu gminy na 13 rodzajów stref
2. **Gminne standardy urbanistyczne** - parametry zabudowy dla każdej strefy
3. **Obszary uzupełnienia zabudowy (OUZ)** - fakultatywnie, gdzie można wydawać WZ
4. **Obszary zabudowy śródmiejskiej** - fakultatywnie
5. **Standardy dostępności infrastruktury społecznej** - fakultatywnie

---

## 2. Podstawy prawne

### 2.1 Główne akty prawne

| Dokument | Zakres |
|----------|--------|
| **Ustawa z dnia 27 marca 2003 r. o planowaniu i zagospodarowaniu przestrzennym** (z późn. zm.) | Główna ustawa, art. 13a-13m definiują POG |
| **Ustawa z dnia 7 lipca 2023 r.** o zmianie ustawy o planowaniu... | Reforma wprowadzająca POG |
| **Rozporządzenie Ministra Rozwoju i Technologii z dnia 8 grudnia 2023 r.** (Dz.U. poz. 2758) | Szczegóły techniczne POG, załącznik z profilami stref |
| **Rozporządzenie z dnia 22 listopada 2024 r.** (Dz.U. poz. 1775) | Nowelizacja rozporządzenia |

### 2.2 Gdzie szukać informacji

- **Rejestr Urbanistyczny** - oficjalna baza planów
- **Geoportal Krajowy** - mapy z warstwami POG
- **BIP gminy** - projekty i uchwalone plany
- **ISAP** (isap.sejm.gov.pl) - akty prawne

---

## 3. Strefy planistyczne - pełny katalog

### 3.1 Przegląd wszystkich 13 stref

Obszar gminy dzieli się **rozłącznie** na dokładnie 13 rodzajów stref. Każda działka może należeć tylko do jednej strefy.

| Symbol | Nazwa strefy | Kategoria | Min. bio % |
|--------|--------------|-----------|------------|
| **SW** | Strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną | Mieszkaniowa | 30% |
| **SJ** | Strefa wielofunkcyjna z zabudową mieszkaniową jednorodzinną | Mieszkaniowa | 30% |
| **SZ** | Strefa wielofunkcyjna z zabudową zagrodową | Mieszkaniowa | 30% |
| **SU** | Strefa usługowa | Funkcjonalna | 20% |
| **SH** | Strefa handlu wielkopowierzchniowego | Funkcjonalna | 20% |
| **SP** | Strefa gospodarcza | Funkcjonalna | 20% |
| **SR** | Strefa produkcji rolniczej | Rolnicza | 50% |
| **SI** | Strefa infrastrukturalna | Infrastruktura | 0% |
| **SN** | Strefa zieleni i rekreacji | Środowiskowa | 70% |
| **SC** | Strefa cmentarzy | Specjalna | 40% |
| **SG** | Strefa górnictwa | Specjalna | - |
| **SO** | Strefa otwarta | Środowiskowa | - |
| **SK** | Strefa komunikacyjna | Infrastruktura | - |

### 3.2 Szczegółowy opis każdej strefy

---

#### SW - Strefa wielofunkcyjna z zabudową mieszkaniową wielorodzinną

**Charakterystyka:**
Obszary intensywnej, miejskiej zabudowy mieszkaniowej z usługami towarzyszącymi. Stosowana głównie w:
- Centrach miast
- Obszarach przewidzianych do dogęszczania
- Rejonach dobrze obsługiwanych transportem publicznym

**Profil podstawowy (obowiązkowy):**
- Teren zabudowy mieszkaniowej wielorodzinnej
- Teren usług
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy (opcjonalny):**
- Teren zabudowy mieszkaniowej jednorodzinnej
- Teren handlu wielkopowierzchniowego
- Teren zieleni naturalnej
- Teren ogrodów działkowych
- Teren lasu
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość | Zakres |
|----------|----------------|--------|
| Intensywność zabudowy | 1.5 | 0.5 - 3.7 |
| Max % zabudowy | 40% | 30% - 60% |
| Max wysokość | 19m | 12m - 100m |
| Min % biologicznie czynnej | 30% | 20% - 40% |

**Co można budować:**
- Bloki mieszkalne
- Kamienice
- Budynki wielorodzinne z usługami w parterze
- Hotele
- Biurowce (jeśli w profilu dodatkowym)
- Przedszkola, szkoły (infrastruktura towarzysząca)

**Czego NIE można budować:**
- Zakładów przemysłowych
- Gospodarstw rolnych
- Domów jednorodzinnych wolnostojących (chyba że w profilu dodatkowym)

---

#### SJ - Strefa wielofunkcyjna z zabudową mieszkaniową jednorodzinną

**Charakterystyka:**
Rozległe obszary osiedli jednorodzinnych. Obejmuje zarówno zabudowę zwartą (szeregówki, bliźniaki), jak i ekstensywną (domy wolnostojące).

**Profil podstawowy (obowiązkowy):**
- Teren zabudowy mieszkaniowej jednorodzinnej
- Teren usług
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy (opcjonalny):**
- Teren zabudowy letniskowej lub rekreacji indywidualnej
- Teren ogrodów działkowych
- Teren zieleni naturalnej
- Teren lasu
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość | Zakres |
|----------|----------------|--------|
| Intensywność zabudowy | 0.5 | 0.3 - 0.8 |
| Max % zabudowy | 30% | 20% - 40% |
| Max wysokość | 9m | 7m - 12m |
| Min % biologicznie czynnej | 50% | 40% - 60% |

**Co można budować:**
- Domy jednorodzinne wolnostojące
- Domy w zabudowie bliźniaczej
- Domy szeregowe
- Małe usługi (gabinet, sklep osiedlowy)
- Garaże, budynki gospodarcze

**Czego NIE można budować:**
- Bloków wielorodzinnych
- Zakładów przemysłowych
- Hal produkcyjnych
- Wielkopowierzchniowych obiektów handlowych

**Dla kogo idealna:**
Rodziny szukające działki pod budowę domu jednorodzinnego.

---

#### SZ - Strefa wielofunkcyjna z zabudową zagrodową

**Charakterystyka:**
Tereny wiejskie z tradycyjną zabudową zagrodową (gospodarstwa rolne). Chroni istniejący charakter osadniczy.

**Profil podstawowy:**
- Teren zabudowy zagrodowej
- Teren produkcji w gospodarstwach rolnych
- Teren usług
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren zabudowy mieszkaniowej jednorodzinnej
- Teren zabudowy letniskowej lub rekreacji indywidualnej
- Teren zieleni naturalnej
- Teren lasu
- Teren wód
- Teren rolnictwa z zakazem zabudowy

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.4 |
| Max % zabudowy | 25% |
| Max wysokość | 10m |
| Min % biologicznie czynnej | 50% |

**Co można budować:**
- Domy z częścią gospodarczą
- Budynki inwentarskie
- Stodoły, obory
- Siedliska rolnicze

---

#### SU - Strefa usługowa

**Charakterystyka:**
Lokalizacja dużych kompleksów usługowych o charakterze monofunkcyjnym: administracja, edukacja, zdrowie, kultura, sport, kult religijny.

**Profil podstawowy:**
- Teren usług
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren usług sportu i rekreacji
- Teren usług kultury i rozrywki
- Teren usług edukacji
- Teren usług zdrowia i pomocy społecznej
- Teren usług nauki
- Teren usług turystyki
- Teren zieleni naturalnej
- Teren lasu
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 1.0 |
| Max % zabudowy | 50% |
| Max wysokość | 15m |
| Min % biologicznie czynnej | 20% |

**Co można budować:**
- Szkoły, przedszkola, uczelnie
- Szpitale, przychodnie
- Urzędy, centra administracyjne
- Teatry, kina, muzea
- Hale sportowe, baseny
- Kościoły, świątynie

---

#### SH - Strefa handlu wielkopowierzchniowego

**Charakterystyka:**
Wyodrębniona strefa dla dużych obiektów handlowych o powierzchni sprzedaży > 2000 m². Kontroluje lokalizację galerii i hipermarketów.

**Profil podstawowy:**
- Teren handlu wielkopowierzchniowego
- Teren usług
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren usług sportu i rekreacji
- Teren usług gastronomii
- Teren składów i magazynów

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.8 |
| Max % zabudowy | 60% |
| Max wysokość | 15m |
| Min % biologicznie czynnej | 20% |

**Co można budować:**
- Galerie handlowe
- Hipermarkety
- Centra handlowe
- Parki handlowe

---

#### SP - Strefa gospodarcza

**Charakterystyka:**
Tereny produkcji, logistyki i działalności gospodarczej. Lokalizowane w obszarach dobrze skomunikowanych.

**Profil podstawowy:**
- Teren produkcji
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren usług
- Teren handlu wielkopowierzchniowego
- Teren składów i magazynów
- Teren zieleni naturalnej
- Teren lasu
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.8 |
| Max % zabudowy | 60% |
| Max wysokość | 20m |
| Min % biologicznie czynnej | 20% |

**Co można budować:**
- Fabryki
- Hale produkcyjne
- Centra logistyczne
- Magazyny
- Biura związane z produkcją

---

#### SR - Strefa produkcji rolniczej

**Charakterystyka:**
Tereny przeznaczone na wielkotowarową produkcję rolną (fermy, gospodarstwa przemysłowe).

**Profil podstawowy:**
- Teren wielkotowarowej produkcji rolnej
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren produkcji w gospodarstwach rolnych
- Teren akwakultury i obsługi rybactwa
- Teren elektrowni słonecznej
- Teren zieleni naturalnej
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.3 |
| Max % zabudowy | 30% |
| Max wysokość | 15m |
| Min % biologicznie czynnej | 50% |

---

#### SI - Strefa infrastrukturalna

**Charakterystyka:**
Tereny zarezerwowane pod infrastrukturę techniczną: energetyka, wodociągi, kanalizacja, telekomunikacja.

**Profil podstawowy:**
- Teren infrastruktury technicznej
- Teren komunikacji
- Teren zieleni urządzonej

**Profil dodatkowy:**
- Teren elektrowni słonecznej
- Teren zieleni naturalnej
- Teren wód

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.5 |
| Max % zabudowy | 50% |
| Max wysokość | 30m |
| Min % biologicznie czynnej | 0% |

---

#### SN - Strefa zieleni i rekreacji

**Charakterystyka:**
Parki, ogrody działkowe, tereny rekreacyjne, zieleń publiczna. Jeden z filarów systemu przyrodniczego miasta.

**Profil podstawowy:**
- Teren zieleni urządzonej
- Teren komunikacji
- Teren infrastruktury technicznej

**Profil dodatkowy:**
- Teren usług sportu i rekreacji
- Teren ogrodów działkowych
- Teren zieleni naturalnej
- Teren lasu
- Teren wód
- Teren plaży

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.1 |
| Max % zabudowy | 10% |
| Max wysokość | 9m |
| Min % biologicznie czynnej | 70% |

**Co można budować:**
- Małą architekturę parkową
- Altany, pergole
- Obiekty sportowe (boiska, korty)
- Baseny odkryte
- Budynki zaplecza (szatnie, toalety)

**Czego NIE można budować:**
- Budynków mieszkalnych
- Obiektów usługowych (poza związanymi z rekreacją)

---

#### SC - Strefa cmentarzy

**Charakterystyka:**
Istniejące cmentarze oraz tereny zarezerwowane pod ich rozbudowę.

**Profil podstawowy:**
- Teren cmentarza
- Teren komunikacji
- Teren zieleni urządzonej
- Teren infrastruktury technicznej

**Typowe parametry:**
| Parametr | Typowa wartość |
|----------|----------------|
| Intensywność zabudowy | 0.1 |
| Max % zabudowy | 10% |
| Max wysokość | 12m |
| Min % biologicznie czynnej | 40% |

---

#### SG - Strefa górnictwa

**Charakterystyka:**
Tereny udokumentowanych złóż kopalin oraz obszary górnicze.

**Profil podstawowy:**
- Teren górniczy
- Teren komunikacji
- Teren infrastruktury technicznej

**Uwaga:** Brak wymogu minimalnej powierzchni biologicznie czynnej.

---

#### SO - Strefa otwarta

**Charakterystyka:**
Tereny chronione przed zabudową: lasy, tereny rolnicze, doliny rzeczne, obszary ekologicznie wartościowe. **Kluczowa dla ochrony krajobrazu.**

**Profil podstawowy:**
- Teren zieleni naturalnej
- Teren lasu
- Teren wód
- Teren rolnictwa z zakazem zabudowy

**Profil dodatkowy:**
- Teren komunikacji (tylko niezbędnej)

**Co można:**
- Prowadzić działalność rolniczą
- Utrzymywać lasy
- Chronić obszary przyrodnicze

**Czego NIE można:**
- Budować żadnych budynków mieszkalnych
- Stawiać obiektów usługowych
- Realizować inwestycji komercyjnych

**Uwaga:** Działka w strefie SO **nie ma potencjału budowlanego** - nie można uzyskać WZ ani pozwolenia na budowę domu.

---

#### SK - Strefa komunikacyjna

**Charakterystyka:**
Istniejące i planowane drogi, koleje, lotniska, porty. Rezerwacja terenów pod rozwój sieci komunikacyjnej.

**Profil podstawowy:**
- Teren autostrady
- Teren drogi ekspresowej
- Teren drogi głównej ruchu przyspieszonego
- Teren drogi głównej
- Teren drogi zbiorczej
- Teren komunikacji kolejowej i szynowej
- Teren komunikacji lotniczej
- Teren komunikacji wodnej
- Teren obsługi komunikacji
- Teren infrastruktury technicznej

**Uwaga:** Brak wymogu minimalnej powierzchni biologicznie czynnej.

---

## 4. Profile funkcjonalne

### 4.1 Czym jest profil?

**Profil funkcjonalny** to katalog dozwolonych funkcji (przeznaczeń) terenu w ramach danej strefy. Dzieli się na:

| Typ profilu | Charakter | Znaczenie |
|-------------|-----------|-----------|
| **Profil podstawowy** | Obowiązkowy, jednolity dla całego kraju | Określa, jakie funkcje MUSZĄ być dozwolone w danej strefie |
| **Profil dodatkowy** | Fakultatywny, wybierany przez gminę | Określa, jakie funkcje MOGĄ być dodatkowo dozwolone |

### 4.2 Lista wszystkich funkcji (terenów)

Zgodnie z rozporządzeniem, tereny dzielą się na klasy:

#### Tereny zabudowy mieszkaniowej

| Kod | Nazwa | Opis |
|-----|-------|------|
| **MW** | Teren zabudowy mieszkaniowej wielorodzinnej | Bloki, kamienice, budynki z >2 mieszkaniami |
| **MN** | Teren zabudowy mieszkaniowej jednorodzinnej | Domy wolnostojące, bliźniaki, szeregówki |
| **ML** | Teren zabudowy letniskowej lub rekreacji indywidualnej | Domki letniskowe, działki rekreacyjne |
| **MZ** | Teren zabudowy zagrodowej | Siedliska rolnicze z budynkami mieszkalnymi |

#### Tereny usług

| Kod | Nazwa | Opis |
|-----|-------|------|
| **U** | Teren usług | Ogólna kategoria usług |
| **US** | Teren usług sportu i rekreacji | Hale sportowe, boiska, baseny |
| **UK** | Teren usług kultury i rozrywki | Kina, teatry, muzea, kluby |
| **UHD** | Teren usług handlu detalicznego | Sklepy, małe centra handlowe |
| **UH** | Teren handlu wielkopowierzchniowego | Galerie, hipermarkety (>2000 m²) |
| **UG** | Teren usług gastronomii | Restauracje, bary, kawiarnie |
| **UT** | Teren usług turystyki | Hotele, pensjonaty, campingi |
| **UN** | Teren usług nauki | Instytuty badawcze, laboratoria |
| **UE** | Teren usług edukacji | Szkoły, przedszkola, uczelnie |
| **UZ** | Teren usług zdrowia i pomocy społecznej | Szpitale, przychodnie, domy opieki |
| **UC** | Teren usług kultu religijnego | Kościoły, świątynie, cmentarze wyznaniowe |

#### Tereny produkcji i gospodarki

| Kod | Nazwa | Opis |
|-----|-------|------|
| **P** | Teren produkcji | Fabryki, hale produkcyjne |
| **PM** | Teren składów i magazynów | Centra logistyczne, magazyny |
| **PG** | Teren górniczy | Kopalnie, wyrobiska |

#### Tereny rolnicze

| Kod | Nazwa | Opis |
|-----|-------|------|
| **R** | Teren rolnictwa z zakazem zabudowy | Pola uprawne chronione |
| **RM** | Teren wielkotowarowej produkcji rolnej | Fermy, gospodarstwa przemysłowe |
| **RZ** | Teren produkcji w gospodarstwach rolnych | Małe gospodarstwa |
| **RA** | Teren akwakultury i obsługi rybactwa | Stawy hodowlane |

#### Tereny zieleni i wód

| Kod | Nazwa | Opis |
|-----|-------|------|
| **ZP** | Teren zieleni urządzonej | Parki, skwery, zieleńce |
| **ZN** | Teren zieleni naturalnej | Łąki, nieużytki, tereny naturalne |
| **ZL** | Teren lasu | Lasy, zadrzewienia |
| **ZD** | Teren ogrodów działkowych | ROD-y |
| **ZC** | Teren cmentarza | Cmentarze |
| **W** | Teren wód | Jeziora, rzeki, stawy |
| **WP** | Teren plaży | Plaże nadmorskie i śródlądowe |

#### Tereny komunikacji

| Kod | Nazwa | Opis |
|-----|-------|------|
| **KD** | Teren komunikacji drogowej | Drogi publiczne |
| **KDA** | Teren autostrady | Autostrady |
| **KDE** | Teren drogi ekspresowej | Drogi ekspresowe |
| **KDG** | Teren drogi głównej | Drogi główne |
| **KDGP** | Teren drogi głównej ruchu przyspieszonego | Drogi GP |
| **KDZ** | Teren drogi zbiorczej | Drogi zbiorcze |
| **KDL** | Teren drogi lokalnej | Drogi lokalne |
| **KDD** | Teren drogi dojazdowej | Drogi dojazdowe |
| **KDW** | Teren drogi wewnętrznej | Drogi wewnętrzne |
| **KK** | Teren komunikacji kolejowej i szynowej | Kolej, tramwaj |
| **KL** | Teren komunikacji lotniczej | Lotniska, lądowiska |
| **KW** | Teren komunikacji wodnej | Porty, przystanie |
| **KO** | Teren obsługi komunikacji | Stacje paliw, parkingi |
| **KKL** | Teren komunikacji kolei linowej | Kolejki górskie |

#### Tereny infrastruktury

| Kod | Nazwa | Opis |
|-----|-------|------|
| **E** | Teren infrastruktury technicznej | Ogólna kategoria |
| **EE** | Teren elektroenergetyczny | Stacje transformatorowe, linie |
| **ES** | Teren elektrowni słonecznej | Farmy fotowoltaiczne |
| **EW** | Teren wodociągowy | Stacje uzdatniania, przepompownie |
| **EK** | Teren kanalizacyjny | Oczyszczalnie, przepompownie |
| **EG** | Teren gazowy | Stacje redukcyjne |
| **EC** | Teren ciepłowniczy | Elektrociepłownie |
| **ET** | Teren telekomunikacyjny | Maszty, centrale |

---

## 5. Parametry zabudowy

### 5.1 Cztery główne parametry

Każda strefa planistyczna ma określone **gminne standardy urbanistyczne** - cztery kluczowe parametry:

#### 5.1.1 Maksymalna nadziemna intensywność zabudowy

**Definicja:** Stosunek sumy powierzchni wszystkich kondygnacji nadziemnych budynków do powierzchni działki.

**Wzór:**
```
Intensywność = Suma powierzchni wszystkich kondygnacji / Powierzchnia działki
```

**Przykład:**
- Działka: 1000 m²
- Intensywność: 0.5
- Możliwa suma kondygnacji: 500 m²
- Np. dom parterowy 250 m² + piętro 250 m²

**Typowe wartości:**

| Strefa | Intensywność |
|--------|--------------|
| SJ (jednorodzinna) | 0.3 - 0.8 |
| SW (wielorodzinna) | 0.8 - 3.7 |
| SP (gospodarcza) | 0.5 - 1.5 |
| SN (zieleń) | 0.05 - 0.2 |

**Konsekwencje dla inwestora:**
- Przy niskiej intensywności (0.3) można postawić mały dom
- Przy wysokiej (2.0) można postawić duży budynek wielorodzinny
- **Przekroczenie = odmowa pozwolenia na budowę**

---

#### 5.1.2 Maksymalny udział powierzchni zabudowy

**Definicja:** Procent powierzchni działki, który może być zabudowany (rzut pionowy budynków).

**Wzór:**
```
% zabudowy = (Powierzchnia zabudowy / Powierzchnia działki) × 100%
```

**Przykład:**
- Działka: 1000 m²
- Max zabudowa: 30%
- Możliwa powierzchnia zabudowy: 300 m²

**Typowe wartości:**

| Strefa | Max % zabudowy |
|--------|----------------|
| SJ | 20% - 40% |
| SW | 30% - 60% |
| SN | 5% - 15% |
| SP | 40% - 70% |

**Co wlicza się do zabudowy:**
- Budynki mieszkalne
- Garaże wolnostojące
- Budynki gospodarcze
- Altany o trwałej konstrukcji

**Czego NIE wlicza się:**
- Tarasy naziemne
- Utwardzone podjazdy
- Baseny

---

#### 5.1.3 Maksymalna wysokość zabudowy

**Definicja:** Różnica między najwyższym punktem budynku (bez kominów) a średnią wysokością terenu przy budynku.

**Jak mierzyć:**
1. Zmierz poziom terenu w kilku punktach wokół budynku
2. Oblicz średnią arytmetyczną najniższego i najwyższego poziomu
3. Zmierz do najwyższego punktu dachu/attyki

**Typowe wartości:**

| Strefa | Max wysokość |
|--------|--------------|
| SJ | 7m - 12m |
| SW | 12m - 100m |
| SN | 6m - 12m |
| SP | 12m - 30m |

**Co oznaczają wysokości:**
- **7m** - dom parterowy z dachem dwuspadowym
- **9m** - dom z poddaszem użytkowym
- **12m** - dom piętrowy z poddaszem
- **19m** - blok 5-6 piętrowy
- **30m+** - wieżowiec

---

#### 5.1.4 Minimalny udział powierzchni biologicznie czynnej

**Definicja:** Procent działki, który musi pozostać jako powierzchnia naturalna, zapewniająca wegetację roślin i retencję wód.

**Co się wlicza:**
- Trawniki i rabaty
- Tereny z drzewami i krzewami
- Oczka wodne, stawy
- **50% powierzchni** zielonych dachów (min. 10 m²)
- **50% powierzchni** tarasów z roślinnością
- **50% powierzchni** nawierzchni ażurowych (geokraty)

**Czego NIE wlicza się:**
- Utwardzone podjazdy
- Betonowe tarasy
- Kostka brukowa

**Typowe wartości:**

| Strefa | Min % bio |
|--------|-----------|
| SJ | 40% - 60% |
| SW | 25% - 40% |
| SN | 60% - 80% |
| SP | 15% - 30% |

**Przykład:**
- Działka: 1000 m²
- Wymaganie: 50% bio
- Minimum: 500 m² musi pozostać jako zieleń

**Konsekwencje:**
- Zmniejszenie poniżej wymaganego poziomu = zmiana istotna
- Inspektor sprawdza zgodność
- **Brak możliwości legalizacji** przy naruszeniu

---

### 5.2 Standardy dostępności infrastruktury społecznej

Oprócz parametrów zabudowy, POG może określać **standardy dostępności**:

#### Dostęp do szkoły podstawowej

| Lokalizacja | Max odległość |
|-------------|---------------|
| Miasto | 1500 m |
| Wieś | 3000 m |

#### Dostęp do zieleni publicznej

| Wielkość obszaru | Max odległość |
|------------------|---------------|
| Min. 3 ha | 1500 m |
| Min. 20 ha | 3000 m |

**Uwaga:** Odległość mierzy się jako "droga dojścia ogólnodostępną trasą dla pieszych".

**Konsekwencje:** Brak spełnienia standardów może uniemożliwić wydanie WZ dla zabudowy mieszkaniowej.

---

## 6. Obszary Uzupełnienia Zabudowy (OUZ)

### 6.1 Czym jest OUZ?

**Obszar Uzupełnienia Zabudowy (OUZ)** to wyznaczony w planie ogólnym teren, na którym **można wydawać decyzje o warunkach zabudowy** po wejściu POG w życie.

### 6.2 Dlaczego OUZ jest kluczowy?

| Sytuacja | Przed POG | Po wejściu POG w życie |
|----------|-----------|------------------------|
| Działka w OUZ | Można uzyskać WZ | Można uzyskać WZ |
| Działka poza OUZ | Można uzyskać WZ | **NIE MOŻNA uzyskać WZ** |
| Działka w MPZP | Zależy od MPZP | Zależy od MPZP |

### 6.3 Kryteria wyznaczania OUZ

Gminy wyznaczają OUZ według kryteriów:

1. **Skupisko minimum 5 budynków** (bez czysto rolniczych)
2. **Odległość między budynkami max 100 m**
3. **Bufor 50 m** wokół skupiska

**Cel:** Zapobieganie rozpraszaniu zabudowy (urban sprawl) i racjonalne wykorzystanie przestrzeni.

### 6.4 Jak sprawdzić, czy działka jest w OUZ?

1. **Geoportal Krajowy** (geoportal-krajowy.pl)
   - Warstwa: "Tereny budowlane / Obszary uzupełnienia zabudowy"
   - Działki w OUZ oznaczone kolorem pomarańczowym

2. **BIP gminy**
   - Projekt/uchwała planu ogólnego
   - Załącznik graficzny z OUZ

3. **Wypis z POG**
   - Formalny dokument z gminy

### 6.5 Co jeśli działka NIE jest w OUZ?

| Opcja | Opis |
|-------|------|
| **Złóż uwagi do projektu POG** | W trakcie konsultacji społecznych wnioskuj o rozszerzenie OUZ |
| **Uzyskaj WZ przed uchwaleniem POG** | Do 30.06.2026 można uzyskać WZ na starych zasadach |
| **Czekaj na MPZP** | Gmina może uchwalić MPZP obejmujący działkę |
| **Sprzedaj działkę** | Wartość działki poza OUZ może spaść |

### 6.6 OUZ a okres przejściowy

| Moment złożenia wniosku o WZ | Zasady |
|------------------------------|--------|
| Przed 24.09.2023 | Stare zasady w całości |
| Od 24.09.2023 do wejścia POG | Zasady mieszane, **nie wymaga OUZ** |
| Po wejściu POG w życie | Wymaga położenia w OUZ |

---

## 7. Konsekwencje dla właściciela działki

### 7.1 Scenariusze - co POG oznacza dla Twojej działki

#### Scenariusz A: Działka w strefie SJ + w OUZ

**Stan:** Najlepszy dla budowy domu jednorodzinnego.

**Możliwości:**
- Uzyskanie WZ na dom jednorodzinny
- Budowa zgodna z parametrami strefy
- Stabilna wartość działki

**Ograniczenia:**
- Max wysokość (np. 9m)
- Max % zabudowy (np. 30%)
- Min % biologicznie czynnej (np. 50%)

---

#### Scenariusz B: Działka w strefie SJ, ale POZA OUZ

**Stan:** Problematyczny - brak możliwości WZ po wejściu POG.

**Możliwości:**
- Złóż wniosek o WZ PRZED uchwaleniem POG
- Składaj uwagi do projektu POG o włączenie do OUZ
- Czekaj na MPZP

**Ryzyko:**
- Spadek wartości działki
- Brak możliwości budowy na czas nieokreślony

---

#### Scenariusz C: Działka w strefie SO (otwartej)

**Stan:** Działka bez potencjału budowlanego.

**Możliwości:**
- Prowadzenie rolnictwa
- Utrzymanie lasu

**Ograniczenia:**
- **BRAK możliwości budowy domu**
- Brak możliwości uzyskania WZ
- Ochrona przed zabudową

**Uwaga:** Jeśli kupiłeś działkę jako "budowlaną", a trafiła do SO - wartość znacząco spadnie.

---

#### Scenariusz D: Działka w strefie SW (wielorodzinnej)

**Stan:** Dobry dla inwestorów deweloperskich.

**Możliwości:**
- Budowa bloku wielorodzinnego
- Wyższa intensywność zabudowy
- Usługi w parterze

**Dla osoby prywatnej:**
- Możliwy dom jednorodzinny (jeśli w profilu dodatkowym)
- Ale sąsiedztwo może być intensywne

---

### 7.2 Odszkodowania

**Kluczowa informacja:** Plan Ogólny **NIE daje prawa do odszkodowania** za spadek wartości nieruchomości.

W przeciwieństwie do MPZP, który daje możliwość roszczeń (art. 36 ustawy), uchwalenie POG samo w sobie nie generuje odpowiedzialności odszkodowawczej gminy.

**Wyjątek:** Odszkodowanie możliwe dopiero przy uchwaleniu MPZP, który będzie zgodny z POG.

### 7.3 Nowe WZ - ważność 5 lat

Od 1 stycznia 2026 roku:

| Kiedy WZ stało się prawomocne | Ważność |
|-------------------------------|---------|
| Przed 1.01.2026 | Bezterminowo |
| Od 1.01.2026 | 5 lat |

**Konsekwencja:** Musisz rozpocząć budowę w ciągu 5 lat od uzyskania WZ.

### 7.4 Co robić TERAZ?

#### Dla właścicieli działek:

1. **Sprawdź projekt POG swojej gminy**
   - BIP gminy lub Rejestr Urbanistyczny

2. **Zidentyfikuj strefę i OUZ**
   - Czy działka jest w OUZ?
   - Jaki symbol strefy?

3. **Jeśli niekorzystne - działaj:**
   - Złóż uwagi w konsultacjach społecznych
   - Rozważ wniosek o WZ przed uchwaleniem
   - Skonsultuj się z prawnikiem

4. **Dokumentuj:**
   - Zapisz stan obecny (studium, WZ)
   - Przechowuj korespondencję z gminą

#### Dla kupujących działkę:

1. **Przed zakupem sprawdź:**
   - Czy jest MPZP? Jaki symbol?
   - Jaki jest projekt POG? Jaka strefa?
   - Czy działka będzie w OUZ?

2. **Unikaj działek:**
   - W projektowanej strefie SO
   - Poza projektowanym OUZ
   - Bez MPZP w gminie bez POG

3. **Preferuj działki:**
   - Z obowiązującym MPZP na MN
   - W projektowanej strefie SJ + OUZ
   - Z już wydanym WZ

---

## 8. Słownik pojęć

| Pojęcie | Definicja |
|---------|-----------|
| **POG** | Plan Ogólny Gminy - akt prawa miejscowego zastępujący studium |
| **MPZP** | Miejscowy Plan Zagospodarowania Przestrzennego - szczegółowy plan |
| **WZ** | Warunki Zabudowy - decyzja administracyjna dla terenu bez MPZP |
| **OUZ** | Obszar Uzupełnienia Zabudowy - teren, gdzie można wydać WZ po POG |
| **Strefa planistyczna** | Jedna z 13 kategorii przeznaczenia terenu w POG |
| **Profil funkcjonalny** | Katalog dozwolonych funkcji terenu w strefie |
| **Intensywność zabudowy** | Stosunek sumy kondygnacji do powierzchni działki |
| **Powierzchnia biologicznie czynna** | Teren zapewniający wegetację i retencję wód |
| **Studium** | Poprzedni dokument planistyczny (zastępowany przez POG) |
| **Akt prawa miejscowego** | Dokument wiążący prawnie na terenie gminy |

---

## 9. Interpretacje dla agenta LLM

### 9.1 Jak tłumaczyć użytkownikowi strefy

#### Dla strefy SJ:
```
Ta działka znajduje się w strefie SJ - czyli strefie przeznaczonej pod zabudowę
mieszkaniową jednorodzinną. To dobra wiadomość, jeśli szukasz miejsca na dom
jednorodzinny.

W tej strefie możesz:
- Wybudować dom wolnostojący, bliźniak lub szeregówkę
- Prowadzić małą działalność usługową (np. gabinet)
- Postawić garaż i budynki gospodarcze

Ograniczenia w tej strefie:
- Maksymalna wysokość budynku: [X]m (typowo 9-12m)
- Możesz zabudować max [X]% działki
- Min [X]% działki musi pozostać jako zieleń
```

#### Dla strefy SO:
```
UWAGA: Ta działka znajduje się w strefie SO - czyli strefie otwartej.

To oznacza, że działka jest chroniona przed zabudową. Nie możesz na niej:
- Wybudować domu mieszkalnego
- Uzyskać warunków zabudowy
- Prowadzić działalności budowlanej

Strefa SO jest przeznaczona na:
- Tereny rolnicze
- Lasy i zieleń naturalną
- Obszary przyrodniczo wartościowe

Jeśli szukasz działki pod budowę domu, ta działka NIE jest odpowiednia.
```

### 9.2 Jak tłumaczyć parametry

#### Intensywność zabudowy:
```
Intensywność zabudowy [X] oznacza, że suma powierzchni wszystkich kondygnacji
Twojego domu nie może przekroczyć [X × powierzchnia działki].

Przykład dla Twojej działki [1000 m²] z intensywnością [0.5]:
- Maksymalna suma kondygnacji: 500 m²
- Możesz np. wybudować dom parterowy 250 m² z piętrem 250 m²
- Lub dom parterowy 500 m² bez piętra

To [wystarczający/ograniczający] parametr dla typowego domu jednorodzinnego.
```

#### Max wysokość:
```
Maksymalna wysokość [X]m pozwala na:
- 7m: dom parterowy z dachem dwuspadowym
- 9m: dom z poddaszem użytkowym (pełne piętro)
- 12m: dom piętrowy z poddaszem

Twoja działka pozwala na [opis co można].
```

### 9.3 Jak oceniać działkę pod kątem POG

#### Checklist dla agenta:

1. **Strefa planistyczna:**
   - [ ] SJ/SW = można budować mieszkania
   - [ ] SN/SO = NIE można budować mieszkań
   - [ ] Inne = zależy od profilu

2. **OUZ (jeśli brak MPZP):**
   - [ ] W OUZ = można uzyskać WZ
   - [ ] Poza OUZ = NIE można uzyskać WZ po wejściu POG

3. **Parametry:**
   - [ ] Intensywność ≥0.4 = wystarczy na typowy dom
   - [ ] Max wysokość ≥9m = można z poddaszem
   - [ ] Max zabudowa ≥25% = standardowo

4. **Profil podstawowy:**
   - [ ] Zawiera "teren zabudowy mieszkaniowej jednorodzinnej" = OK dla domu
   - [ ] Brak takiego terenu = sprawdź profil dodatkowy

### 9.4 Szablony odpowiedzi

#### Podsumowanie działki:
```
## Podsumowanie parametrów POG dla działki [ID]

**Strefa:** [symbol] - [nazwa]

**Możliwości zabudowy:**
- [lista co można budować]

**Parametry:**
| Parametr | Wartość | Interpretacja |
|----------|---------|---------------|
| Intensywność | [X] | [interpretacja] |
| Max zabudowa | [X]% | [interpretacja] |
| Max wysokość | [X]m | [interpretacja] |
| Min bio | [X]% | [interpretacja] |

**Ocena dla Twoich potrzeb:**
[Personalizowana ocena na podstawie preferencji użytkownika]
```

---

## Źródła

- [Ustawa o planowaniu i zagospodarowaniu przestrzennym](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20030800717)
- [Rozporządzenie MRiT z 8.12.2023 (Dz.U. poz. 2758)](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20230002758)
- [Reforma planowania przestrzennego - gov.pl](https://www.gov.pl/web/rozwoj-technologia/reforma-planowania-przestrzennego-2)
- [OnGeo.pl - Obszary uzupełnienia zabudowy](https://blog.ongeo.pl/obszary-uzupelnienia-zabudowy)
- [Geoportal360.pl - Plan ogólny gminy](https://geoportal360.pl/blog/plan-ogolny-gminy-czym-jest-i-co-zawiera/)

---

**Dokument utworzony:** 2026-01-22
**Wersja:** 1.0
**Autor:** System moja-dzialka (research + Claude)
