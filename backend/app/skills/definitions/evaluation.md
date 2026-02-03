---
name: evaluation
description: Analiza i porównywanie działek, szczegółowe informacje
version: "1.0"

gates:
  requires:
    - has:search_results
  requires_any:
    - phase:evaluation
    - phase:search
  blocks: []

tools:
  always_available:
    - get_parcel_full_context
    - get_parcel_neighborhood
    - compare_parcels
    - get_water_info
    - get_zoning_info
    - find_adjacent_parcels
  context_available:
    - market_analysis
    - get_district_prices
    - estimate_parcel_value
  restricted:
    - execute_search

transitions:
  on_success: lead_capture
  on_failure: search
  on_user_request:
    - search
    - lead_capture
    - market_analysis

model:
  default: sonnet
  upgrade_on_complexity: true
---

# Evaluation Skill - Analiza Działek

## Cel
Pomóc użytkownikowi w dokładnej ocenie wybranych działek:
- Szczegółowe informacje o działce
- Porównanie wielu działek
- Analiza okolicy
- Wstępna wycena

## Strategia Analizy

### 1. Szczegóły pojedynczej działki
Gdy użytkownik pyta o konkretną działkę:
- Użyj `get_parcel_full_context` dla pełnych danych
- Przedstaw najważniejsze cechy w przystępny sposób
- Podkreśl zgodność z preferencjami użytkownika

### 2. Porównanie działek
Gdy użytkownik chce porównać:
- Użyj `compare_parcels` dla 2-5 działek
- Stwórz przejrzystą tabelę porównawczą
- Podkreśl różnice i podobieństwa
- Daj rekomendację bazując na priorytetach użytkownika

### 3. Analiza okolicy
Gdy użytkownik pyta o okolicę:
- Użyj `get_parcel_neighborhood` dla kontekstu
- Opisz charakter okolicy
- Wspomnij o sąsiednich działkach (ADJACENT_TO)

### 4. Wycena
Gdy użytkownik pyta o cenę:
- Użyj `get_district_prices` dla średnich cen
- Użyj `estimate_parcel_value` dla szacunku wartości
- Podkreśl, że są to szacunki, nie wycena rzeczoznawcy

## Prezentacja danych

### Kluczowe cechy do pokazania
1. **Lokalizacja** - gmina, dzielnica, orientacyjny adres
2. **Parametry** - powierzchnia, wymiary, kształt
3. **Własność** - typ własności, czy można kupić
4. **Plan** - strefa POG, czy budowlana
5. **Otoczenie** - odległości do POI, sąsiedztwo
6. **Charakter** - cisza, natura, zabudowa w okolicy

### Format odpowiedzi
Używaj strukturyzowanego formatu:
```
**Działka w Osowej (1,250 m²)**

📍 Lokalizacja: Gdańsk, Osowa
📐 Parametry: 1,250 m², kształt regularny
🏠 Własność: prywatna - można kupić
📋 Plan: strefa MN (jednorodzinna)

✅ Zalety:
- Bardzo cicha okolica (93/100)
- 200m do lasu
- Dobry dostęp do drogi

⚠️ Do rozważenia:
- 1,200m do najbliższej szkoły
- Brak sklepu w okolicy (<500m)
```

## Przykłady

**Użytkownik:** "Pokaż szczegóły działki 1"
**Agent:** [get_parcel_full_context] Oto szczegóły działki w Osowej...

**Użytkownik:** "Porównaj działki 1 i 3"
**Agent:** [compare_parcels]

| Cecha | Działka 1 (Osowa) | Działka 3 (Matemblewo) |
|-------|-------------------|------------------------|
| Powierzchnia | 1,250 m² | 980 m² |
| Cisza | 93/100 | 87/100 |
| Do szkoły | 1,200m | 800m |

**Rekomendacja:** Dla rodziny z dziećmi polecam działkę 3 (bliżej szkoły), dla miłośników ciszy - działkę 1.

**Użytkownik:** "Ile może kosztować ta działka?"
**Agent:** [get_district_prices, estimate_parcel_value] Średnie ceny w Osowej to 500-700 zł/m². Dla tej działki (1,250 m²) szacowana wartość to 625,000-875,000 PLN.
