# Projekt: Mechanizm opisu i prezentacji działek

**Data:** 2026-01-22
**Cel:** Zaprojektować system generowania bogatych, kontekstowych opisów działek przez agenta

---

## 1. Wizja

### Problem obecny
Agent zwraca suche dane:
```
Działka 226301_1.0012.152/5
- Powierzchnia: 1718 m²
- Strefa: SJ
- Odległość do lasu: 150m
- Cisza: 85/100
```

### Wizja docelowa
Agent tworzy narrację dostosowaną do preferencji użytkownika:

> **Działka w Oliwie - idealna dla rodziny szukającej ciszy**
>
> Ta przestronna działka (1718 m²) położona jest w jednej z najbardziej
> prestiżowych dzielnic Gdańska - Oliwie, znanej z zabytkowego parku i
> bliskości Trójmiejskiego Parku Krajobrazowego.
>
> **Dlaczego ta działka pasuje do Twoich wymagań:**
> - ✓ Szukałeś ciszy - działka ma wskaźnik ciszy 85/100, daleko od
>   głównych dróg i przemysłu
> - ✓ Chciałeś blisko lasu - las jest zaledwie 150m, możesz spacerować
>   z psem bez samochodu
> - ✓ Zależało Ci na szkole w pobliżu - Szkoła Podstawowa nr 47 jest
>   w odległości 800m (10 min pieszo)
>
> **Co możesz tu zbudować:**
> Dom jednorodzinny do 9m wysokości, max 30% zabudowy. Musisz zachować
> min. 50% powierzchni biologicznie czynnej - idealne na ogród.

---

## 2. Architektura mechanizmu

### 2.1 Przepływ danych

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION PIPELINE                            │
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐ │
│  │   CONTEXT    │────►│   ENRICHER   │────►│   NARRATIVE GENERATOR    │ │
│  │   BUILDER    │     │              │     │                          │ │
│  └──────────────┘     └──────────────┘     └──────────────────────────┘ │
│         │                    │                        │                  │
│         ▼                    ▼                        ▼                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐ │
│  │ User prefs   │     │ Parcel data  │     │ Structured description   │ │
│  │ Search query │     │ POI details  │     │ + LLM narrative          │ │
│  │ Conversation │     │ Area context │     │ + Visual components      │ │
│  └──────────────┘     └──────────────┘     └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Komponenty

| Komponent | Rola | Input | Output |
|-----------|------|-------|--------|
| **Context Builder** | Zbiera kontekst użytkownika | Konwersacja, preferencje | UserContext |
| **Enricher** | Wzbogaca dane o kontekst obszaru | Parcel ID, bbox | EnrichedParcel |
| **Narrative Generator** | Generuje opis | EnrichedParcel + UserContext | ParcelPresentation |

---

## 3. Struktura danych

### 3.1 UserContext (preferencje użytkownika)

```python
@dataclass
class UserContext:
    # Preferencje explicite (user powiedział)
    explicit_preferences: dict = {
        "purpose": "dom_jednorodzinny",      # cel zakupu
        "area_min": 800,                      # min powierzchnia
        "area_max": 1500,                     # max powierzchnia
        "location": "Gdańsk lub okolice",     # lokalizacja
        "must_have": ["cisza", "las"],        # wymagania
        "nice_to_have": ["szkoła", "sklep"],  # mile widziane
        "avoid": ["przemysł", "hałas"],       # unikać
    }

    # Preferencje implicite (wynikające z konwersacji)
    implicit_preferences: dict = {
        "family_with_children": True,         # wywnioskowane z "szkoła"
        "nature_lover": True,                 # wywnioskowane z "las", "cisza"
        "car_owner": None,                    # nieznane
        "budget_sensitive": False,            # nie wspominał o cenie
    }

    # Historia konwersacji (key phrases)
    conversation_highlights: list[str] = [
        "szukam spokojnego miejsca",
        "dzieci idą do szkoły",
        "lubię spacery po lesie",
    ]

    # Feedback na poprzednie działki
    feedback_history: list[dict] = [
        {"parcel_id": "...", "reaction": "too_small", "comment": "za mała"},
        {"parcel_id": "...", "reaction": "liked", "comment": "fajna okolica"},
    ]
```

### 3.2 EnrichedParcel (wzbogacone dane działki)

```python
@dataclass
class EnrichedParcel:
    # === PODSTAWOWE ===
    id: str
    area_m2: float
    centroid: tuple[float, float]  # lat, lon
    geometry: Polygon

    # === LOKALIZACJA ===
    location: ParcelLocation

    # === POG ===
    zoning: ZoningInfo

    # === OTOCZENIE ===
    surroundings: SurroundingsInfo

    # === WSKAŹNIKI ===
    scores: QualityScores

    # === TEREN (z LiDAR) ===
    terrain: TerrainInfo


@dataclass
class ParcelLocation:
    # Mikrolokalizacja
    gmina: str                    # "Gdańsk"
    dzielnica: str                # "Oliwa"
    ulica: str | None             # "ul. Spacerowa" (jeśli dostępna)

    # Makrolokalizacja
    region_description: str       # "północna część Gdańska"
    character: str                # "willowa dzielnica", "nowe osiedle"

    # Kontekst
    notable_landmarks: list[str]  # ["Park Oliwski", "ZOO", "Ergo Arena"]
    district_reputation: str      # "prestiżowa", "rozwijająca się", "spokojna"


@dataclass
class ZoningInfo:
    symbol: str                   # "SJ"
    nazwa: str                    # "strefa mieszkaniowa jednorodzinna"

    # Parametry
    max_wysokosc: float           # 9.0
    max_zabudowa_pct: float       # 30.0
    max_intensywnosc: float       # 0.5
    min_bio_pct: float            # 50.0

    # Profile funkcji
    dozwolone_funkcje: list[str]  # ["jednorodzinna", "usługi", "zieleń"]

    # Human-readable
    building_summary: str         # "dom do 9m, max 30% zabudowy"
    restrictions_summary: str     # "min 50% zieleni, zakaz produkcji"


@dataclass
class SurroundingsInfo:
    # Odległości do POI
    distances: dict[str, DistanceInfo]  # {typ: info}

    # Charakter otoczenia
    urbanization_level: str       # "niska", "średnia", "wysoka"
    building_density: int         # liczba budynków w 500m
    dominant_land_use: str        # "lasy", "zabudowa jednorodzinna"

    # Sąsiedztwo
    neighbors_description: str    # "otoczona domami jednorodzinnymi"


@dataclass
class DistanceInfo:
    distance_m: int               # 150
    name: str | None              # "Las Oliwski" / "SP nr 47"
    walk_time_min: int            # 2
    description: str              # "spacer przez park"


@dataclass
class QualityScores:
    quietness: int                # 0-100
    nature: int                   # 0-100
    accessibility: int            # 0-100

    # Kategorie (human-readable)
    quietness_category: str       # "bardzo cicha"
    nature_category: str          # "zielona"
    accessibility_category: str   # "dobra"


@dataclass
class TerrainInfo:
    elevation_min: float          # 45.2
    elevation_max: float          # 48.7
    elevation_diff: float         # 3.5
    slope_avg_pct: float          # 2.1%
    slope_category: str           # "płaska", "łagodna", "umiarkowana", "stroma"
    orientation: str              # "południowy stok", "płaska"
    terrain_description: str      # "Łagodnie opadający teren w kierunku..."
```

### 3.3 ParcelPresentation (output)

```python
@dataclass
class ParcelPresentation:
    parcel_id: str

    # === NAGŁÓWEK ===
    headline: str                 # "Działka w Oliwie - idealna dla rodziny"
    tagline: str                  # "1718 m² ciszy przy lesie"

    # === SEKCJE OPISU ===
    sections: list[PresentationSection]

    # === DOPASOWANIE DO PREFERENCJI ===
    preference_matches: list[PreferenceMatch]

    # === WIZUALIZACJE ===
    visuals: VisualComponents

    # === METADANE ===
    generated_at: datetime
    data_freshness: str           # "dane z 2026-01"


@dataclass
class PresentationSection:
    title: str                    # "Lokalizacja"
    icon: str                     # "📍"
    content: str                  # tekst opisu
    highlights: list[str]         # bullet points
    data_points: dict             # surowe dane do wyświetlenia


@dataclass
class PreferenceMatch:
    preference: str               # "cisza"
    matched: bool                 # True
    score: int                    # 85
    explanation: str              # "Działka ma wskaźnik ciszy 85/100..."
    icon: str                     # "✓" / "~" / "✗"


@dataclass
class VisualComponents:
    map_config: dict              # konfiguracja mapy Leaflet
    terrain_3d_url: str | None    # URL do Potree viewer
    gallery_images: list[str]     # URLs do zdjęć satelitarnych/street view
    charts: list[dict]            # wykresy (np. porównanie z innymi działkami)
```

---

## 4. Sekcje opisu działki

### 4.1 Struktura prezentacji

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🏡 NAGŁÓWEK                                                            │
│  ─────────────────────────────────────────────────────────────────────  │
│  Działka w Oliwie - idealna dla rodziny szukającej ciszy               │
│  1718 m² · SJ (jednorodzinna) · Oliwa, Gdańsk                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ✅ DOPASOWANIE DO TWOICH WYMAGAŃ                                       │
│  ─────────────────────────────────────────────────────────────────────  │
│  ✓ Cisza (85/100) - daleko od głównych dróg i przemysłu               │
│  ✓ Las w 150m - codzienne spacery bez samochodu                        │
│  ✓ Szkoła 800m - SP nr 47, 10 min pieszo                               │
│  ~ Sklep 1.2km - wymaga krótkiego spaceru                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  📍 LOKALIZACJA                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  MAKRO: Oliwa to jedna z najbardziej prestiżowych dzielnic Gdańska,   │
│  położona w północnej części miasta. Znana z zabytkowego Parku         │
│  Oliwskiego, katedry oraz bliskości Trójmiejskiego Parku Krajobrazowego│
│                                                                         │
│  MIKRO: Działka znajduje się w spokojnej, willowej części Oliwy,       │
│  przy ul. Spacerowej. Otoczona jest domami jednorodzinnymi z lat       │
│  80-90. W bezpośrednim sąsiedztwie - dojrzała zieleń i Las Oliwski.   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  🏗️ CO MOŻESZ ZBUDOWAĆ (POG)                                           │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Strefa: SJ - mieszkaniowa jednorodzinna                               │
│                                                                         │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐         │
│  │  max 9m      │  max 30%     │  min 50%     │  0.5         │         │
│  │  wysokość    │  zabudowy    │  zieleni     │  intensywn.  │         │
│  └──────────────┴──────────────┴──────────────┴──────────────┘         │
│                                                                         │
│  Możesz: dom jednorodzinny, garaż, mały budynek usługowy               │
│  Nie możesz: zabudowa wielorodzinna, produkcja, handel wielkopow.      │
│                                                                         │
│  💡 Przy 1718 m² możesz zabudować max 515 m² (30%), zostanie           │
│     859 m² na ogród (50% biologicznie czynnej)                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  🌲 OTOCZENIE I ODLEGŁOŚCI                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Natura:                                                                │
│  • Las Oliwski ─────────── 150m (2 min) 🌲                             │
│  • Potok Oliwski ───────── 400m (5 min) 💧                             │
│                                                                         │
│  Edukacja:                                                              │
│  • SP nr 47 ────────────── 800m (10 min) 🏫                            │
│  • Przedszkole nr 12 ───── 600m (8 min) 👶                             │
│                                                                         │
│  Transport:                                                             │
│  • Przystanek autobus. ─── 300m (4 min) 🚌                             │
│  • SKM Oliwa ───────────── 1.2km (15 min) 🚃                           │
│                                                                         │
│  Usługi:                                                                │
│  • Sklep spożywczy ─────── 500m (6 min) 🛒                             │
│  • Apteka ──────────────── 800m (10 min) 💊                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ⛰️ TEREN                                                               │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Nachylenie: łagodne (2.1%) - idealne pod budowę                       │
│  Różnica wysokości: 3.5m (od 45.2m do 48.7m n.p.m.)                    │
│  Orientacja: południowy stok - dużo słońca                              │
│                                                                         │
│  Teren łagodnie opada w kierunku południowym, co zapewnia dobre        │
│  nasłonecznienie i naturalne odprowadzenie wody.                       │
│                                                                         │
│  [🗺️ Zobacz model 3D terenu]                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  📊 WSKAŹNIKI JAKOŚCI                                                   │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Cisza        ████████████████████░░░░  85/100  bardzo cicha           │
│  Natura       ██████████████████░░░░░░  72/100  zielona                │
│  Dostępność   █████████████████░░░░░░░  68/100  dobra                  │
│                                                                         │
│  Porównanie z innymi działkami w Oliwie:                               │
│  • Cisza: lepsza niż 78% działek                                       │
│  • Natura: lepsza niż 65% działek                                      │
│  • Dostępność: lepsza niż 52% działek                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Generowanie narracji przez LLM

### 5.1 Strategia: Structured Data + LLM Polish

Agent **NIE** generuje całego opisu przez LLM (ryzyko halucynacji).

Zamiast tego:
1. **Backend** przygotowuje strukturyzowane dane (EnrichedParcel)
2. **Agent** otrzymuje template z placeholderami
3. **LLM** "poleruje" narrację, dodaje płynność, kontekstualizuje

### 5.2 Prompt template dla agenta

```python
PARCEL_DESCRIPTION_PROMPT = """
Opisz działkę dla użytkownika, który szuka: {user_requirements}

## Dane działki (FAKTY - nie zmieniaj wartości!):
{structured_data}

## Preferencje użytkownika:
- Explicite: {explicit_preferences}
- Z konwersacji: {conversation_highlights}

## Zasady:
1. NIE wymyślaj danych - używaj TYLKO podanych faktów
2. Odwołuj się do preferencji użytkownika ("Szukałeś ciszy...")
3. Zamień liczby na kontekst ("150m do lasu" → "2 minuty spaceru")
4. Używaj polskich nazw i naturalnego języka
5. Podkreśl mocne strony, neutralnie wspomnij słabe
6. NIGDY nie sugeruj ceny ani wartości działki

## Format odpowiedzi:
Wygeneruj JSON z sekcjami:
- headline: krótki, chwytliwy nagłówek
- tagline: 5-10 słów podsumowania
- location_macro: 2-3 zdania o dzielnicy/okolicy
- location_micro: 2-3 zdania o bezpośrednim sąsiedztwie
- preference_matches: lista dopasowań do wymagań użytkownika
- terrain_narrative: 1-2 zdania o terenie
- building_summary: co można zbudować, prostym językiem
"""
```

### 5.3 Walidacja odpowiedzi LLM

```python
def validate_llm_response(llm_response: dict, source_data: EnrichedParcel) -> bool:
    """
    Sprawdza czy LLM nie zhallucynował danych.
    """
    # Sprawdź czy odległości są zgodne
    for poi, claimed_distance in llm_response.get('distances', {}).items():
        actual = source_data.surroundings.distances.get(poi)
        if actual and abs(claimed_distance - actual.distance_m) > 50:
            raise HallucinationError(f"LLM zmienił odległość do {poi}")

    # Sprawdź czy parametry POG są zgodne
    if 'max_wysokosc' in llm_response:
        if llm_response['max_wysokosc'] != source_data.zoning.max_wysokosc:
            raise HallucinationError("LLM zmienił parametry POG")

    return True
```

---

## 6. Kontekstualizacja preferencji użytkownika

### 6.1 Mapowanie preferencji → danych

```python
PREFERENCE_MAPPING = {
    # Preferencja użytkownika → które dane sprawdzić
    "cisza": {
        "primary": "quietness_score",
        "threshold_good": 70,
        "related_data": ["dist_to_industrial", "dist_to_main_road"],
        "positive_phrase": "daleko od hałasu i przemysłu",
        "negative_phrase": "w pobliżu ruchliwych dróg",
    },
    "las": {
        "primary": "dist_to_forest",
        "threshold_good": 500,  # metry
        "related_data": ["pct_forest_500m"],
        "positive_phrase": "las na wyciągnięcie ręki",
        "negative_phrase": "las wymaga dojazdu",
    },
    "szkoła": {
        "primary": "dist_to_school",
        "threshold_good": 1000,
        "related_data": ["school_name", "school_type"],
        "positive_phrase": "szkoła w zasięgu pieszego spaceru",
        "negative_phrase": "szkoła wymaga dowozu",
    },
    "spokojna okolica": {
        "primary": "quietness_score",
        "secondary": "building_density",
        "threshold_good": 60,
        "positive_phrase": "spokojna, niezatłoczona okolica",
        "negative_phrase": "gęsta zabudowa i ruch",
    },
    "blisko natury": {
        "primary": "nature_score",
        "threshold_good": 60,
        "related_data": ["dist_to_forest", "dist_to_water", "pct_forest_500m"],
        "positive_phrase": "otoczona zielenią",
        "negative_phrase": "zurbanizowana okolica",
    },
}
```

### 6.2 Generowanie PreferenceMatch

```python
def generate_preference_matches(
    parcel: EnrichedParcel,
    user_context: UserContext
) -> list[PreferenceMatch]:
    """
    Dla każdej preferencji użytkownika generuje ocenę dopasowania.
    """
    matches = []

    for pref in user_context.explicit_preferences.get('must_have', []):
        mapping = PREFERENCE_MAPPING.get(pref)
        if not mapping:
            continue

        # Pobierz wartość z danych
        value = getattr(parcel, mapping['primary'], None)
        threshold = mapping['threshold_good']

        # Oceń dopasowanie
        if mapping['primary'].endswith('_score'):
            # Wyższy = lepszy
            matched = value >= threshold
            score = value
        else:
            # Odległość - niższy = lepszy
            matched = value <= threshold
            score = 100 - min(100, (value / threshold) * 100)

        # Wygeneruj wyjaśnienie
        if matched:
            explanation = f"{mapping['positive_phrase']} ({format_value(value, mapping['primary'])})"
            icon = "✓"
        else:
            explanation = f"{mapping['negative_phrase']} ({format_value(value, mapping['primary'])})"
            icon = "✗"

        matches.append(PreferenceMatch(
            preference=pref,
            matched=matched,
            score=int(score),
            explanation=explanation,
            icon=icon
        ))

    return sorted(matches, key=lambda m: (not m.matched, -m.score))
```

---

## 7. Baza wiedzy o lokalizacjach

### 7.1 Opisy dzielnic (statyczne + LLM-enriched)

```python
DISTRICT_KNOWLEDGE = {
    "Oliwa": {
        "city": "Gdańsk",
        "character": "willowa, prestiżowa",
        "reputation": "jedna z najbardziej pożądanych dzielnic",
        "landmarks": ["Park Oliwski", "Katedra Oliwska", "ZOO"],
        "description": """
            Oliwa to historyczna dzielnica Gdańska, znana z zabytkowego
            zespołu parkowego i katedry z słynnymi organami. Okolica
            przyciąga rodziny szukające spokoju i bliskości natury,
            przy jednoczesnym dobrym połączeniu z centrum.
        """,
        "pros": ["prestiż", "zieleń", "cisza", "dobre szkoły"],
        "cons": ["wyższe ceny", "daleko od centrum"],
        "typical_residents": "rodziny z dziećmi, kadra menedżerska",
    },
    "Wrzeszcz": {
        "city": "Gdańsk",
        "character": "miejska, tętniąca życiem",
        "reputation": "popularna wśród młodych profesjonalistów",
        "landmarks": ["Galeria Bałtycka", "PG", "Park Kuźniczki"],
        "description": """
            Wrzeszcz to dynamiczna dzielnica łącząca historyczną zabudowę
            z nowoczesnymi inwestycjami. Doskonałe połączenie komunikacyjne,
            bogata oferta usług i rozrywki.
        """,
        "pros": ["komunikacja", "usługi", "życie nocne", "uczelnie"],
        "cons": ["hałas", "tłok", "mało zieleni w centrum"],
        "typical_residents": "studenci, młodzi profesjonaliści, single",
    },
    # ... więcej dzielnic
}
```

### 7.2 Dynamiczne wzbogacanie kontekstu

```python
async def enrich_location_context(parcel: EnrichedParcel) -> ParcelLocation:
    """
    Wzbogaca dane lokalizacyjne o kontekst z bazy wiedzy + LLM.
    """
    district = parcel.location.dzielnica
    knowledge = DISTRICT_KNOWLEDGE.get(district, {})

    # Bazowy opis z bazy wiedzy
    if knowledge:
        macro_description = knowledge['description']
        character = knowledge['character']
        landmarks = knowledge['landmarks']
    else:
        # Fallback - generuj przez LLM na podstawie danych
        macro_description = await generate_district_description(district)
        character = "nieznany charakter"
        landmarks = []

    # Mikrolokalizacja - zawsze generowana dynamicznie
    micro_description = await generate_micro_description(parcel)

    return ParcelLocation(
        gmina=parcel.location.gmina,
        dzielnica=district,
        ulica=parcel.location.ulica,
        region_description=macro_description,
        character=character,
        notable_landmarks=landmarks,
        district_reputation=knowledge.get('reputation', '')
    )
```

---

## 8. Narzędzia agenta

### 8.1 Tool: present_parcel

```python
@tool
async def present_parcel(
    parcel_id: str,
    presentation_style: Literal["full", "summary", "comparison"] = "full",
    highlight_preferences: bool = True
) -> ParcelPresentation:
    """
    Generuje pełną prezentację działki dla użytkownika.

    Użyj tego narzędzia gdy:
    - Chcesz pokazać użytkownikowi znalezioną działkę
    - Użytkownik prosi o szczegóły działki
    - Prezentujesz wyniki wyszukiwania

    Args:
        parcel_id: ID działki do prezentacji
        presentation_style:
            - "full" - pełny opis ze wszystkimi sekcjami
            - "summary" - skrócony opis (nagłówek + dopasowanie)
            - "comparison" - format do porównywania wielu działek
        highlight_preferences: czy podkreślać dopasowanie do preferencji

    Returns:
        ParcelPresentation z wszystkimi sekcjami i danymi wizualizacji
    """
    # 1. Pobierz dane działki
    parcel = await get_enriched_parcel(parcel_id)

    # 2. Pobierz kontekst użytkownika
    user_context = await get_user_context()

    # 3. Wzbogać lokalizację
    parcel.location = await enrich_location_context(parcel)

    # 4. Generuj dopasowanie do preferencji
    if highlight_preferences:
        preference_matches = generate_preference_matches(parcel, user_context)

    # 5. Generuj narrację przez LLM
    narrative = await generate_narrative(parcel, user_context, presentation_style)

    # 6. Przygotuj wizualizacje
    visuals = prepare_visuals(parcel)

    return ParcelPresentation(
        parcel_id=parcel_id,
        headline=narrative.headline,
        tagline=narrative.tagline,
        sections=build_sections(parcel, narrative),
        preference_matches=preference_matches,
        visuals=visuals,
        generated_at=datetime.now(),
        data_freshness="dane z 2026-01"
    )
```

### 8.2 Tool: compare_parcels

```python
@tool
async def compare_parcels(
    parcel_ids: list[str],
    comparison_criteria: list[str] | None = None
) -> ComparisonPresentation:
    """
    Porównuje wiele działek według wybranych kryteriów.

    Użyj gdy użytkownik:
    - Chce porównać 2-3 działki
    - Pyta "która lepsza?"
    - Chce zobaczyć różnice
    """
    # Generuj tabelę porównawczą + narrację różnic
    ...
```

---

## 9. Integracja z frontendem

### 9.1 Komponent React

```typescript
interface ParcelPresentationProps {
  presentation: ParcelPresentation;
  onFeedback: (reaction: 'like' | 'dislike' | 'info') => void;
  onNavigate: (direction: 'prev' | 'next') => void;
}

const ParcelPresentation: React.FC<ParcelPresentationProps> = ({
  presentation,
  onFeedback,
  onNavigate
}) => {
  return (
    <div className="parcel-presentation">
      {/* Nagłówek */}
      <Header
        headline={presentation.headline}
        tagline={presentation.tagline}
      />

      {/* Dopasowanie do preferencji */}
      <PreferenceMatches matches={presentation.preference_matches} />

      {/* Mapa + 3D */}
      <VisualsSection visuals={presentation.visuals} />

      {/* Sekcje opisu */}
      {presentation.sections.map(section => (
        <DescriptionSection key={section.title} section={section} />
      ))}

      {/* Feedback */}
      <FeedbackButtons onFeedback={onFeedback} />

      {/* Nawigacja */}
      <Navigation onNavigate={onNavigate} />
    </div>
  );
};
```

---

## 10. Przykład pełnego flow

### Konwersacja

```
USER: Szukam działki pod dom w Gdańsku, ważna dla mnie jest cisza
      i bliskość lasu. Mam dwójkę dzieci więc szkoła też się przyda.

AGENT: [analizuje preferencje, zapisuje kontekst]
       Rozumiem - szukasz spokojnego miejsca z dostępem do natury
       i w rozsądnej odległości od szkoły. Przeszukuję działki...

AGENT: [search_parcels(...)]
       Znalazłem 23 działki spełniające Twoje kryteria.
       Zaczynam od najlepiej dopasowanej.

AGENT: [present_parcel("226301_1.0012.152/5")]
```

### Wygenerowana prezentacja

```json
{
  "headline": "Działka w Oliwie - idealna dla rodziny szukającej ciszy i natury",
  "tagline": "1718 m² przy lesie, szkoła w 10 min",

  "preference_matches": [
    {
      "preference": "cisza",
      "matched": true,
      "score": 85,
      "explanation": "Działka ma wskaźnik ciszy 85/100 - daleko od głównych dróg i przemysłu",
      "icon": "✓"
    },
    {
      "preference": "las",
      "matched": true,
      "score": 95,
      "explanation": "Las Oliwski jest zaledwie 150m - 2 minuty spaceru z domu",
      "icon": "✓"
    },
    {
      "preference": "szkoła",
      "matched": true,
      "score": 80,
      "explanation": "Szkoła Podstawowa nr 47 jest 800m od działki - 10 min pieszo",
      "icon": "✓"
    }
  ],

  "sections": [
    {
      "title": "Lokalizacja",
      "icon": "📍",
      "content": "Oliwa to jedna z najbardziej prestiżowych dzielnic Gdańska, położona w północnej części miasta. Znana z zabytkowego Parku Oliwskiego i bliskości Trójmiejskiego Parku Krajobrazowego.\n\nDziałka znajduje się w spokojnej, willowej części Oliwy. Otoczona domami jednorodzinnymi z lat 80-90, z dojrzałą zielenią i bezpośrednim dostępem do Lasu Oliwskiego.",
      "highlights": ["Prestiżowa dzielnica", "Willowe sąsiedztwo", "Przy lesie"]
    },
    {
      "title": "Co możesz zbudować",
      "icon": "🏗️",
      "content": "Strefa SJ pozwala na budowę domu jednorodzinnego do 9m wysokości. Przy 1718 m² możesz zabudować max 515 m² (30%), a 859 m² musi pozostać jako zieleń.",
      "highlights": ["Dom do 9m", "Max 30% zabudowy", "Min 50% zieleni"],
      "data_points": {
        "max_wysokosc": 9.0,
        "max_zabudowa_pct": 30.0,
        "min_bio_pct": 50.0
      }
    }
  ]
}
```

---

## 11. Kolejne kroki implementacji

### Faza 1: Dane
- [ ] Wzbogacenie działek o wszystkie cechy (pipeline)
- [ ] Baza wiedzy o dzielnicach Trójmiasta
- [ ] Słownik tłumaczeń (POG symbole → opisy)

### Faza 2: Backend
- [ ] Klasy danych (EnrichedParcel, UserContext, etc.)
- [ ] Serwis generowania prezentacji
- [ ] Prompty dla LLM z walidacją

### Faza 3: Agent
- [ ] Tool `present_parcel`
- [ ] Tool `compare_parcels`
- [ ] Logika kontekstualizacji preferencji

### Faza 4: Frontend
- [ ] Komponent prezentacji
- [ ] Integracja z mapą i 3D
- [ ] UI feedbacku
