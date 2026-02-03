---
name: market_analysis
description: Analiza rynku i wycena działek
version: "1.0"

gates:
  requires: []
  requires_any:
    - phase:evaluation
    - phase:negotiation
  blocks: []

tools:
  always_available:
    - market_analysis
    - get_district_prices
    - estimate_parcel_value
  context_available:
    - get_parcel_full_context
  restricted:
    - execute_search
    - capture_contact_info

transitions:
  on_success: lead_capture
  on_failure: evaluation
  on_user_request:
    - evaluation
    - lead_capture

model:
  default: sonnet
  upgrade_on_complexity: true
---

# Market Analysis Skill - Analiza Rynku

## Cel
Dostarczyć użytkownikowi informacje o cenach i wartości rynkowej działek:
- Ceny w dzielnicach
- Szacunkowa wycena działki
- Trendy rynkowe
- Porównanie z podobnymi ofertami

## Strategia Analizy

### 1. Ceny w dzielnicy
- Użyj `get_district_prices` dla ogólnego obrazu
- Podaj zakres cen (min-max) i średnią
- Wspomnij o czynnikach wpływających na cenę

### 2. Wycena konkretnej działki
- Użyj `estimate_parcel_value` dla szacunku
- Podaj zakres (pesymistyczny-optymistyczny)
- Wyjaśnij czynniki wpływające na wartość

### 3. Kontekst rynkowy
- Wspomnij o segmentach rynku
- Porównaj do podobnych lokalizacji
- Zasygnalizuj trendy (jeśli dostępne)

## Segmenty cenowe

### Premium (>1500 zł/m²)
- Sopot (cały)
- Jelitkowo, Brzeźno
- Orłowo, Kamienna Góra

### Wysoki (800-1500 zł/m²)
- Oliwa, Wrzeszcz
- Redłowo, Mały Kack

### Średni (500-800 zł/m²)
- Osowa, Kokoszki, Jasień
- Chwarzno-Wiczlino

### Budżetowy (300-500 zł/m²)
- Łostowice, Chełm
- Obrzeża Gdyni

### Ekonomiczny (<300 zł/m²)
- Gminy podmiejskie
- Żukowo, Kolbudy, Reda

## Czynniki wpływające na cenę

### Podnoszą wartość (+)
- Bliskość morza/jeziora (+20-100%)
- Prestiżowa lokalizacja (+30-50%)
- Plan MN (mieszkaniowa) (+10-20%)
- Niezabudowana, gotowa pod budowę (+5-10%)

### Obniżają wartość (-)
- Hałas (przy drodze głównej) (-10-20%)
- Strefa przemysłowa w okolicy (-15-25%)
- Brak planu miejscowego (-5-10%)
- Trudny kształt działki (-5-10%)

## Prezentacja wyceny

### Format odpowiedzi
```
**Szacunkowa wartość działki w Osowej (1,250 m²)**

💰 Zakres cenowy: 625,000 - 875,000 PLN
📊 Cena za m²: 500-700 zł

**Czynniki wpływające:**
✅ Cicha okolica (+5%)
✅ Bliskość lasu (+10%)
✅ Plan MN (+10%)
⚠️ Daleko od szkoły (-5%)

**Kontekst rynkowy:**
Osowa to segment średni-wyższy. Ceny w ostatnich latach stabilne
z lekką tendencją wzrostową (3-5% rocznie).

⚠️ *To szacunek, nie wycena rzeczoznawcy. Przed zakupem
zalecamy profesjonalną wycenę.*
```

## Ważne zastrzeżenia

ZAWSZE dodawaj:
1. To szacunek, nie wycena rzeczoznawcy
2. Rzeczywista cena zależy od negocjacji
3. Zalecamy profesjonalną wycenę przed zakupem

## Przykłady

**Użytkownik:** "Ile kosztują działki w Osowej?"
**Agent:** [get_district_prices("Osowa")]
Ceny działek w Osowej wahają się od 500 do 700 zł/m². Zależy od dokładnej lokalizacji, dostępu do drogi i planu miejscowego.

**Użytkownik:** "Czy ta działka jest droga?"
**Agent:** [estimate_parcel_value]
Działka o powierzchni 1,250 m² w Osowej ma szacunkową wartość 625,000-875,000 PLN. To segment średni-wyższy w Gdańsku. Podobne działki w Kokoszkach byłyby o 10-15% tańsze.
