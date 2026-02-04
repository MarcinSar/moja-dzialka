---
name: search
description: Wykonywanie wyszukiwań działek i prezentacja wyników
version: "1.0"

gates:
  requires:
    - has:preferences_approved
  requires_any:
    - phase:search
    - phase:discovery
  blocks: []

tools:
  always_available:
    - execute_search
    - search_by_water_type
    - find_adjacent_parcels
    - search_near_specific_poi
    - find_similar_by_graph
    - refine_search
  context_available:
    - approve_search_preferences
    - refine_search_preferences
    - propose_filter_refinement
    - get_parcel_full_context
    - get_parcel_neighborhood
  restricted:
    - capture_contact_info

transitions:
  on_success: evaluation
  on_failure: discovery
  on_user_request:
    - evaluation
    - discovery

model:
  default: haiku
  upgrade_on_complexity: false
---

# Search Skill - Wyszukiwanie Działek

## Cel
Wykonać efektywne wyszukiwanie działek i zaprezentować wyniki użytkownikowi w przystępny sposób.

## Strategia Wyszukiwania

### 1. Wykonanie wyszukiwania
- Użyj `execute_search` z zatwierdzonymi preferencjami
- Domyślnie ustawiaj `ownership_type: "prywatna"` (działki do kupienia)
- Dla działek pod budowę: `build_status: "niezabudowana"`

### 2. Prezentacja wyników
- Pokaż 3-5 najlepszych działek
- Dla każdej działki podaj:
  - Lokalizację (dzielnica)
  - Powierzchnię
  - Kluczowe cechy (cisza, natura, dostępność)
  - Odległości do POI
- Użyj numeracji (1, 2, 3) dla łatwego odniesienia

### 3. Obsługa braku wyników
- Jeśli 0 wyników: zaproponuj poluzowanie kryteriów
- Użyj `propose_filter_refinement` z sugestiami

### 4. Iteracja
- Jeśli użytkownik chce innych wyników: `refine_search`
- Jeśli użytkownik chce więcej szczegółów: przekaż do evaluation

## Filtry Neo4j v2

### Własność (ownership_type)
- `prywatna` - 78k działek, MOŻNA KUPIĆ!
- `publiczna` - 73k, gminna/państwowa
- `spółdzielcza`, `kościelna`, `inna`

### Status zabudowy (build_status)
- `niezabudowana` - 93k działek pod budowę
- `zabudowana` - 61k z budynkami

### Rozmiar (size_category)
- `mala` - <500m² (83k)
- `pod_dom` - 500-2000m² (41k) ← IDEALNE
- `duza` - 2000-5000m² (17k)
- `bardzo_duza` - >5000m² (11k)

## Narzędzia specjalne

### find_adjacent_parcels
Użyj gdy użytkownik chce kupić sąsiednie działki lub potrzebuje większej powierzchni.

### search_near_specific_poi
Użyj gdy użytkownik wymienia konkretne POI po nazwie (np. "blisko szkoły SP nr 45").

### find_similar_by_graph
Użyj gdy użytkownik lubi jakąś działkę i chce znaleźć podobne.

## Przykłady

**Użytkownik:** "Szukaj"
**Agent:** [execute_search] Znalazłem 47 działek spełniających Twoje kryteria. Oto 5 najlepszych:

1. **Osowa, 1,250 m²** - bardzo cicha okolica, 200m do lasu, 800m do szkoły
2. **Matemblewo, 980 m²** - cicha, 150m do lasu, 1,200m do szkoły
3. ...

Która działka Cię interesuje? Mogę pokazać więcej szczegółów.

**Użytkownik:** "Pokaż działki nad jeziorem"
**Agent:** [search_by_water_type(water_type="jezioro")] Oto działki blisko jezior w Twoim obszarze...
