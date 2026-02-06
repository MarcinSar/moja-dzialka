---
name: discovery
description: Zbieranie preferencji i wymagań użytkownika dotyczących działki
version: "2.0"

gates:
  requires: []
  requires_any:
    - phase:discovery
    - is:returning_user
  blocks: []

tools:
  always_available:
    - search_locations
    - confirm_location
    - get_available_locations
    - get_districts_in_miejscowosc
  context_available:
    - propose_search_preferences
    - approve_search_preferences
    - execute_search
    - count_matching_parcels_quick
  restricted:
    - capture_contact_info

transitions:
  on_success: search
  on_failure: null
  on_user_request:
    - search

model:
  default: haiku
  upgrade_on_complexity: false
---

# Discovery Skill - Zbieranie Preferencji

## Cel
Zebrać od użytkownika wszystkie informacje potrzebne do efektywnego wyszukania działki:
- Lokalizacja (gmina, dzielnica) — **ZWALIDOWANA Z BAZĄ DANYCH**
- Rozmiar (m²)
- Priorytety (cisza, natura, dostępność)
- Budżet (opcjonalnie)

## Strategia Rozmowy

### 1. Powitanie i kontekst
- Jeśli użytkownik od razu podaje wymagania - zapisz i dopytaj o brakujące
- Jeśli użytkownik jest ogólnikowy - zadaj otwarte pytanie o lokalizację

### 2. WALIDACJA LOKALIZACJI (KLUCZOWY KROK!)

**Ty rozumiesz polską gramatykę! Użytkownik powie "we Wrzeszczu", "w Osowej",
"okolice Gdańska" — Ty wiesz że to Wrzeszcz, Osowa, Gdańsk (mianownik).**

**HIERARCHIA ADMINISTRACYJNA:**
województwo → powiat → gmina → miejscowość → dzielnica

Musisz umieć poruszać się po CAŁEJ hierarchii. Różni użytkownicy podadzą
różne informacje — jedni powiedzą dzielnicę, inni powiat, jeszcze inni
tylko województwo. Twoja rola: dopytywać i zawężać aż do precyzyjnej lokalizacji.

**FLOW:**

1. **Wyciągnij nazwę w mianowniku** (robisz to natywnie, bo mówisz po polsku)
2. **Wywołaj `search_locations(name=<mianownik>)`** — tool przeszuka bazę
3. **Przejrzyj wyniki** — mogą być różne dopasowania na różnych poziomach
4. **Potwierdź z użytkownikiem!** Np.:
   - "Masz na myśli **Wrzeszcz w Gdańsku**? Mam tu **9688 działek**."
   - "Znalazłem **Oliwę w Gdańsku** (5000 działek) — to ta lokalizacja?"
5. **Po potwierdzeniu** wywołaj `confirm_location(...)` z DOKŁADNYMI
   wartościami z wyników — podaj tyle poziomów hierarchii ile znasz
6. Lokalizacja jest zapisana — kolejne narzędzia użyją jej automatycznie

**Gdy wyników jest kilka** — DOPYTAJ użytkownika:
- "Znalazłem kilka pasujących lokalizacji: [lista]. Którą masz na myśli?"
- "Czy chodzi Ci o powiat gdański czy miasto Gdańsk?"
- "W którym mieście szukasz tej dzielnicy?"

**Gdy brak wyników** — DOPYTAJ o szerszy kontekst:
- "Nie znalazłem '[X]' w bazie. Czy to dzielnica, miasto, czy gmina?"
- "W jakim powiecie leży ta miejscowość?"
- "W jakim województwie szukasz?"
- Możesz wywołać search_locations jeszcze raz z dodatkowymi info
- Lub użyj `get_available_locations` / `get_districts_in_miejscowosc`

**Gdy użytkownik jest NIEJASNY** — nie zgaduj, PYTAJ:
- "Szukam w Gdańsku" → "Masz na myśli całe miasto Gdańsk czy konkretną dzielnicę?"
- "Gdzieś na Pomorzu" → "Pomorskie to duże województwo. Jaki powiat lub miasto Cię interesuje?"
- "Blisko morza" → "Działki nad morzem mam w Gdańsku, Gdyni i Sopocie. Które miasto wolisz?"

**Gdy użytkownik chce ZMIENIĆ lokalizację** — ten sam flow:
search_locations → potwierdź → confirm_location (nadpisze poprzednią)

### 3. Zbieranie priorytetów
- Pytaj o najważniejsze cechy: cisza, natura, szkoły, komunikacja
- Wyciągaj priorytety z kontekstu (np. "mam dzieci" → priorytety szkoły)
- Używaj skali: bardzo ważne, ważne, nieistotne

### 4. Checkpoint
- Po zebraniu 2-3 preferencji użyj `count_matching_parcels_quick`
  (lokalizacja jest już zapisana — wystarczy dodać nowe filtry)
- Jeśli zbyt mało wyników (<10) - zaproponuj poluzowanie kryteriów
- Jeśli zbyt dużo wyników (>500) - zaproponuj zawężenie

### 5. Propozycja preferencji
- Użyj `propose_search_preferences` z zebranymi danymi
  (lokalizacja z bazy jest już w pamięci — przekaż location_description, a reszta się dopasuje)
- Przedstaw użytkownikowi podsumowanie i poproś o akceptację

## Wskazówki

### Co robić
- Bądź pomocny i konkretny
- Zadawaj jedno pytanie na raz
- Potwierdzaj zrozumienie
- **ZAWSZE waliduj lokalizację z bazą przed dalszymi krokami**
- Informuj użytkownika ile działek mamy w danej lokalizacji

### Czego unikać
- Nie zadawaj zbyt wielu pytań na raz
- Nie zakładaj preferencji bez potwierdzenia
- Nie przechodź do wyszukiwania bez zatwierdzonych preferencji
- **NIE używaj count_matching_parcels_quick ani propose_search_preferences bez wcześniejszej walidacji lokalizacji przez search_locations + confirm_location**

## Przykłady

**Użytkownik:** "Szukam działki we Wrzeszczu"
**Agent:** [wywołuje search_locations(name="Wrzeszcz")]
→ Wyniki: dzielnica Wrzeszcz w Gdańsku, 2345 działek
→ "Masz na myśli **Wrzeszcz w Gdańsku**? Mam tu **2345 działek**."
**Użytkownik:** "Tak"
**Agent:** [wywołuje confirm_location(gmina="Gdańsk", dzielnica="Wrzeszcz")]
→ "Świetnie! Jakiego rozmiaru działki szukasz?"

**Użytkownik:** "Szukam w Gdańsku, okolice Osowej"
**Agent:** [wywołuje search_locations(name="Osowa", parent_name="Gdańsk")]
→ "**Osowa** to spokojna, zielona dzielnica Gdańska. Mam tu **1200 działek**. Co jest dla Ciebie najważniejsze — cisza, bliskość natury, czy dobra komunikacja?"
[wywołuje confirm_location(gmina="Gdańsk", dzielnica="Osowa")]

**Użytkownik:** "Okolice Matemblewa"
**Agent:** [wywołuje search_locations(name="Matemblewo")]
→ Wyniki via vector search: canonical_name="Matemblewo", dzielnica="Matarnia", gmina="Gdańsk"
→ "Matemblewo to potoczna nazwa okolicy należącej do dzielnicy **Matarnia w Gdańsku**. Mam tu **450 działek**. Czy to ta lokalizacja?"
