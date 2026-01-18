# AI Agent Documentation

## Overview

The moja-dzialka AI agent is a conversational interface powered by Claude API that helps users find building plots through natural language interaction.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CONVERSATION FLOW                         │
│                                                              │
│   User Message                                               │
│       │                                                      │
│       ▼                                                      │
│   ┌───────────────────┐                                     │
│   │ Session State     │ ◄── Load from Redis/MongoDB         │
│   │ - preferences     │                                     │
│   │ - credits         │                                     │
│   │ - history         │                                     │
│   └─────────┬─────────┘                                     │
│             │                                                │
│             ▼                                                │
│   ┌───────────────────┐     ┌───────────────────┐          │
│   │   Claude API      │────▶│   Tool Executor   │          │
│   │   (with tools)    │     │                   │          │
│   └─────────┬─────────┘     └─────────┬─────────┘          │
│             │                         │                     │
│             │ ◄───────────────────────┘                     │
│             │                                                │
│             ▼                                                │
│   ┌───────────────────┐                                     │
│   │ Stream Response   │ ──▶ WebSocket to Client             │
│   └───────────────────┘                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## System Prompt

```python
SYSTEM_PROMPT = """
Jestes asystentem pomagajacym znalezc idealna dzialke budowlana w wojewodztwie pomorskim.

## Twoja rola:
1. Prowadz naturalna rozmowe po polsku
2. Zadawaj pytania, aby zrozumiec potrzeby uzytkownika
3. Uzywaj narzedzi do ustawiania preferencji i wyszukiwania
4. Wyjasniaj wyniki w przystepny sposob

## Zasady rozmowy:
- Zacznij od pytania o lokalizacje
- Potem zapytaj o powierzchnie
- Nastepnie o preferencje otoczenia (las, szkola, cisza)
- Pokazuj wyniki progresywnie (najpierw liczba, potem szczegoly)

## Zasady monetyzacji:
- Kazdy uzytkownik ma 3 darmowe odkrycia szczegolów
- Po wykorzystaniu darmowych kredytow, kazde odkrycie kosztuje 1 PLN
- Jasno komunikuj zasady platnosci
- Nie naciskaj na platnosci, ale informuj o koniecznosci

## Dostepne narzedzia:
1. set_location_preference - ustaw lokalizacje (gmina, promien)
2. set_area_preference - ustaw zakres powierzchni (m2)
3. set_purpose_preference - ustaw przeznaczenie (MN, MW, U, R, ZL)
4. set_proximity_preferences - ustaw wagi bliskosci (las, szkola, cisza)
5. count_matching_plots - policz pasujace dzialki
6. get_top_matches - pobierz najlepsze dzialki
7. reveal_plot_details - odkryj pelne szczegoly (kosztuje kredyt)
8. initiate_payment - rozpocznij proces platnosci
9. submit_lead - zapisz zainteresowanie dzialka

## Skroty przeznaczenia MPZP:
- MN = zabudowa mieszkaniowa jednorodzinna
- MW = zabudowa mieszkaniowa wielorodzinna
- U = uslugowa
- MN/U = mieszkaniowo-uslugowa
- R = rolna
- ZL = lesna

## Ograniczenia:
- Obslugujemy tylko wojewodztwo pomorskie
- Dane aktualne na dzien importu (informuj o tym przy pytaniach o ceny)
- Nie mamy danych o cenach dzialek - tylko dane ewidencyjne i planistyczne

Jesli uzytkownik pyta o cos poza zakresem, uprzejmie wyjasnij ograniczenia.
"""
```

## Tool Definitions

### 1. set_location_preference

Sets the geographic search area.

```python
{
    "name": "set_location_preference",
    "description": "Ustaw preferencje lokalizacji dzialki. Mozna podac nazwe gminy, punkt na mapie lub promien wyszukiwania.",
    "input_schema": {
        "type": "object",
        "properties": {
            "gmina": {
                "type": "string",
                "description": "Nazwa gminy (np. 'Sopot', 'Gdansk', 'Zukowo')"
            },
            "gminas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista gmin do przeszukania"
            },
            "near_point": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"}
                },
                "description": "Punkt centralny wyszukiwania (wspolrzedne WGS84)"
            },
            "radius_km": {
                "type": "number",
                "description": "Promien wyszukiwania w km (domyslnie 10)"
            }
        }
    }
}
```

**Example Usage**:
```
User: "Szukam dzialki w okolicach Sopotu"
Agent: [set_location_preference(gmina="Sopot", radius_km=10)]
```

---

### 2. set_area_preference

Sets the plot area range.

```python
{
    "name": "set_area_preference",
    "description": "Ustaw zakres powierzchni dzialki w metrach kwadratowych.",
    "input_schema": {
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

**Example Usage**:
```
User: "Potrzebuje okolo 1000 metrow"
Agent: [set_area_preference(min_m2=800, max_m2=1200)]
```

---

### 3. set_purpose_preference

Sets the zoning type preference.

```python
{
    "name": "set_purpose_preference",
    "description": "Ustaw przeznaczenie dzialki wedlug MPZP (Miejscowego Planu Zagospodarowania Przestrzennego).",
    "input_schema": {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "enum": ["MN", "MW", "U", "MN/U", "R", "ZL", "any"],
                "description": "Typ przeznaczenia: MN=jednorodzinna, MW=wielorodzinna, U=uslugowa, R=rolna, ZL=lesna, any=dowolne"
            },
            "require_mpzp": {
                "type": "boolean",
                "description": "Czy wymagany jest plan miejscowy (domyslnie false)"
            }
        }
    }
}
```

**Example Usage**:
```
User: "Szukam dzialki pod dom jednorodzinny"
Agent: [set_purpose_preference(purpose="MN")]
```

---

### 4. set_proximity_preferences

Sets weights for proximity to various features.

```python
{
    "name": "set_proximity_preferences",
    "description": "Ustaw wagi waznosci bliskosci roznych obiektow. Kazda waga to liczba od 0 (nieistotne) do 1 (bardzo wazne).",
    "input_schema": {
        "type": "object",
        "properties": {
            "forest": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga bliskosci lasu"
            },
            "school": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga bliskosci szkoly/przedszkola"
            },
            "shop": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga bliskosci sklepow"
            },
            "public_transport": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga bliskosci komunikacji publicznej"
            },
            "quiet": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga ciszy (daleko od glownych drog)"
            },
            "water": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Waga bliskosci wody (jezioro, rzeka)"
            }
        }
    }
}
```

**Example Usage**:
```
User: "Zalezy mi na lesie i ciszy, mamy male dzieci wiec przedszkole tez wazne"
Agent: [set_proximity_preferences(forest=0.9, quiet=0.8, school=0.7)]
```

---

### 5. count_matching_plots

Counts plots matching current criteria.

```python
{
    "name": "count_matching_plots",
    "description": "Policz dzialki spelniajace aktualne kryteria wyszukiwania. Zwraca liczbe dzialek i rozklad po gminach.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
}
```

**Returns**:
```json
{
    "count": 127,
    "by_gmina": {
        "Zukowo": 34,
        "Kolbudy": 28,
        "Pruszcz Gdanski": 22
    }
}
```

---

### 6. get_top_matches

Gets the best matching plots.

```python
{
    "name": "get_top_matches",
    "description": "Pobierz najlepiej dopasowane dzialki wedlug aktualnych kryteriow. Zwraca przyblizona lokalizacje (bez pelnych danych).",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 3,
                "maximum": 10,
                "description": "Liczba dzialek do zwrocenia"
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "description": "Przesuniecie (dla paginacji)"
            }
        }
    }
}
```

**Returns**:
```json
{
    "plots": [
        {
            "id": "plot-123",
            "approximate_location": {"lat": 54.35, "lon": 18.41, "precision": "500m"},
            "area_m2": 1050,
            "gmina": "Zukowo",
            "miejscowosc": "Chwaszczyno",
            "similarity_score": 0.94,
            "key_features": ["300m do lasu", "przedszkole 1.2km"],
            "has_mpzp": true,
            "mpzp_purpose": "MN"
        }
    ]
}
```

---

### 7. reveal_plot_details

Reveals full plot details (costs 1 credit).

```python
{
    "name": "reveal_plot_details",
    "description": "Odkryj pelne szczegoly dzialki. Kosztuje 1 kredyt. Jesli brak kredytow, zwraca informacje o koniecznosci zakupu.",
    "input_schema": {
        "type": "object",
        "properties": {
            "plot_id": {
                "type": "string",
                "description": "ID dzialki do odkrycia"
            }
        },
        "required": ["plot_id"]
    }
}
```

**Returns (success)**:
```json
{
    "success": true,
    "credits_remaining": 2,
    "plot": {
        "id": "226115_2.0003.456/7",
        "exact_location": {"lat": 54.35672, "lon": 18.41234},
        "nr_ewidencyjny": "456/7",
        "obreb": "0003",
        "mpzp": {
            "plan_name": "MPZP Chwaszczyno Polnocne",
            "symbol": "1MN",
            "parameters": {
                "max_wysokosc_m": 12,
                "intensywnosc": 0.4
            }
        },
        "distances": {
            "forest_m": 312,
            "school_m": 1245
        }
    }
}
```

**Returns (insufficient credits)**:
```json
{
    "success": false,
    "error": "insufficient_credits",
    "credits_remaining": 0,
    "packages": [
        {"name": "single", "credits": 1, "price_pln": 1},
        {"name": "pack_10", "credits": 10, "price_pln": 9},
        {"name": "pack_25", "credits": 25, "price_pln": 20}
    ]
}
```

---

### 8. initiate_payment

Starts the payment process.

```python
{
    "name": "initiate_payment",
    "description": "Rozpocznij proces zakupu kredytow przez Stripe. Zwraca link do platnosci.",
    "input_schema": {
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "enum": ["single", "pack_10", "pack_25"],
                "description": "Pakiet kredytow: single=1PLN/1kredyt, pack_10=9PLN/10kredytow, pack_25=20PLN/25kredytow"
            }
        },
        "required": ["package"]
    }
}
```

**Returns**:
```json
{
    "checkout_url": "https://checkout.stripe.com/c/pay/...",
    "message": "Kliknij link ponizej, aby dokonac platnosci. Akceptujemy BLIK, karty i Przelewy24."
}
```

---

### 9. submit_lead

Records user interest in a plot.

```python
{
    "name": "submit_lead",
    "description": "Zapisz zainteresowanie uzytkownika konkretna dzialka. Zbiera dane kontaktowe do pozniejszego kontaktu.",
    "input_schema": {
        "type": "object",
        "properties": {
            "plot_id": {
                "type": "string",
                "description": "ID dzialki"
            },
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
                    "financing": {
                        "type": "string",
                        "enum": ["cash", "mortgage", "undecided"]
                    },
                    "timeline_months": {"type": "integer"},
                    "notes": {"type": "string"}
                }
            }
        },
        "required": ["plot_id", "contact"]
    }
}
```

---

## Conversation Examples

### Example 1: Family Looking for a House Plot

```
User: Czesc, szukam dzialki pod budowe domu dla rodziny

Agent: Dzien dobry! Chetnie pomoge znalezc idealna dzialke.
       Zacznijmy od lokalizacji - w jakiej okolicy szukacie?

User: Gdzies w okolicach Trojmiasta, ale niekoniecznie w samym Gdansku

Agent: [set_location_preference(gminas=["Gdansk","Sopot","Gdynia","Pruszcz Gdanski","Zukowo","Kolbudy"], radius_km=20)]

       Rozumiem - okolice Trojmiasta. Jakiej powierzchni szukacie?

User: Okolo 1000 metrow, moze troche wiecej

Agent: [set_area_preference(min_m2=900, max_m2=1500)]

       Swietnie. A co jest dla Was wazne w otoczeniu?

User: Zdecydowanie las i cisza, mamy male dzieci wiec przedszkole by sie przydalo

Agent: [set_purpose_preference(purpose="MN")]
       [set_proximity_preferences(forest=0.9, quiet=0.8, school=0.7)]
       [count_matching_plots]

       Mam dobre wiesci! Znalazlem 87 dzialek spelniajacych Wasze kryteria.
       Najwiecej w gminach: Zukowo (23), Kolbudy (18), Pruszcz Gdanski (15).

       [get_top_matches(limit=3)]

       Oto 3 najlepiej dopasowane:

       1. **Dzialka w Chwaszczyznie** (gmina Zukowo)
          - ~1050 m², 300m do lasu, przedszkole 1.2 km
          - Dopasowanie: 94%

       2. **Dzialka w Borkowie** (gmina Kolbudy)
          - ~1120 m², bezposrednio przy lesie, szkola 800m
          - Dopasowanie: 91%

       3. **Dzialka w Straszynie** (gmina Pruszcz Gd.)
          - ~980 m², 200m do lasu, cicha okolica
          - Dopasowanie: 89%

       Chcecie zobaczyc dokladne lokalizacje i szczegoly ktorejs z nich?

User: Ta w Borkowie brzmi swietnie, pokaz szczegoly

Agent: [reveal_plot_details(plot_id="kolbudy-borkowo-123")]

       Oto pelne szczegoly dzialki w Borkowie:

       **Lokalizacja**: Borkowo, ul. Lesna (gmina Kolbudy)
       **Numer ewidencyjny**: 123/5, obreb 0004

       **Powierzchnia**: 1118 m² (dokladnie)

       **Plan miejscowy (MPZP)**:
       - Przeznaczenie: MN (zabudowa jednorodzinna)
       - Max wysokosc: 12m
       - Intensywnosc: 0.4
       - Pow. biologicznie czynna: min. 40%

       **Odleglosci**:
       - Las: bezposrednio przy granicy dzialki
       - Szkola podstawowa: 800m
       - Przedszkole: 1.1km
       - Sklep: 1.5km
       - Przystanek autobusowy: 450m

       **Dojazd**: droga publiczna asfaltowa

       Zostaly Ci 2 darmowe odkrycia. Chcesz zobaczyc pozostale dzialki?
```

### Example 2: Investor Looking for Multi-Family Plot

```
User: Szukam dzialki pod maly budynek wielorodzinny w Gdansku

Agent: Rozumiem - zabudowa wielorodzinna (MW) w Gdansku.

       [set_location_preference(gmina="Gdansk")]
       [set_purpose_preference(purpose="MW", require_mpzp=true)]

       Jaka minimalna powierzchnia Was interesuje?

User: Minimum 2000 m2

Agent: [set_area_preference(min_m2=2000)]
       [count_matching_plots]

       W Gdansku mam 34 dzialki z przeznaczeniem MW powyzej 2000 m².

       Najlepsze lokalizacje:
       - Orunia Gorna: 8 dzialek
       - Kokoszki: 6 dzialek
       - Jasien: 5 dzialek

       Chcecie zobaczyc parametry zabudowy z MPZP?

User: Tak, pokaz te z najwieksza intensywnoscia

Agent: [get_top_matches(limit=5)]

       Top 5 dzialek wg intensywnosci zabudowy:

       1. **Orunia, ul. Platynowa** - 3200 m²
          - Intensywnosc: 1.2, max 18m, PBC 25%
          - Szacunkowe PUM: ~3800 m²

       2. **Kokoszki, ul. Budowlanych** - 2800 m²
          - Intensywnosc: 1.0, max 15m, PBC 30%
          - Szacunkowe PUM: ~2800 m²

       3. **Jasien, ul. Kartuska** - 4100 m²
          - Intensywnosc: 0.9, max 15m, PBC 35%
          - Szacunkowe PUM: ~3700 m²

       Ktora chcecie przeanalizowac szczegolowo?
```

### Example 3: Handling Payment Flow

```
User: Pokaz mi jeszcze te dzialke na Jaseniu

Agent: [reveal_plot_details(plot_id="jasien-123")]

       Niestety, wykorzystales juz darmowe odkrycia.
       Pelne dane dzialki kosztuja 1 PLN.

       Dostepne pakiety:
       - 1 dzialka = 1 PLN
       - 10 dzialek = 9 PLN (oszczedzasz 10%)
       - 25 dzialek = 20 PLN (oszczedzasz 20%)

       Ktory pakiet wybierasz?

User: Wezme 10

Agent: [initiate_payment(package="pack_10")]

       Swietny wybor! Przygotowalem link do platnosci:

       [Kliknij tutaj aby zaplacic 9 PLN](https://checkout.stripe.com/...)

       Akceptujemy:
       - BLIK
       - Karty platnicze
       - Przelewy24

       Po zaplaceniu automatycznie dodam 10 kredytow do Twojego konta
       i od razu pokaze szczegoly dzialki na Jaseniu.
```

## Implementation

### Conversation Service

```python
# backend/app/services/conversation_service.py

from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any
from anthropic import Anthropic
import json

@dataclass
class SearchPreferences:
    gminas: Optional[List[str]] = None
    near_point: Optional[tuple] = None
    radius_km: float = 10.0
    min_area_m2: Optional[float] = None
    max_area_m2: Optional[float] = None
    mpzp_purpose: Optional[str] = None
    require_mpzp: bool = False
    weights: Dict[str, float] = field(default_factory=lambda: {
        'forest': 0.5, 'school': 0.5, 'shop': 0.3,
        'public_transport': 0.3, 'quiet': 0.5, 'water': 0.3
    })


@dataclass
class ConversationState:
    session_id: str
    preferences: SearchPreferences = field(default_factory=SearchPreferences)
    credits_balance: int = 3
    revealed_plot_ids: Set[str] = field(default_factory=set)
    messages: List[Dict] = field(default_factory=list)
    last_search_results: List[str] = field(default_factory=list)


class ConversationService:
    def __init__(
        self,
        anthropic_client: Anthropic,
        search_service,
        payment_service,
        lead_service
    ):
        self.client = anthropic_client
        self.search = search_service
        self.payments = payment_service
        self.leads = lead_service
        self.tools = self._build_tools()

    def _build_tools(self) -> List[Dict]:
        """Build tool definitions for Claude."""
        return [
            # ... tool definitions as above
        ]

    async def process_message(
        self,
        state: ConversationState,
        user_message: str
    ):
        """Process user message and yield response chunks."""

        state.messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=state.messages
        )

        # Process response
        for content in response.content:
            if content.type == "text":
                yield {"type": "text", "content": content.text}

            elif content.type == "tool_use":
                # Execute tool
                result = await self._execute_tool(
                    state, content.name, content.input
                )
                yield {
                    "type": "tool_result",
                    "tool": content.name,
                    "result": result
                }

        # Add assistant response to history
        state.messages.append({
            "role": "assistant",
            "content": response.content
        })

    async def _execute_tool(
        self,
        state: ConversationState,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Any:
        """Execute a tool and return result."""

        if tool_name == "set_location_preference":
            if "gmina" in args:
                state.preferences.gminas = [args["gmina"]]
            elif "gminas" in args:
                state.preferences.gminas = args["gminas"]
            if "near_point" in args:
                state.preferences.near_point = (
                    args["near_point"]["lat"],
                    args["near_point"]["lon"]
                )
            if "radius_km" in args:
                state.preferences.radius_km = args["radius_km"]
            return {"status": "ok", "preferences": "updated"}

        elif tool_name == "set_area_preference":
            state.preferences.min_area_m2 = args.get("min_m2")
            state.preferences.max_area_m2 = args.get("max_m2")
            return {"status": "ok"}

        elif tool_name == "count_matching_plots":
            count, by_gmina = await self.search.count_plots(state.preferences)
            return {"count": count, "by_gmina": by_gmina}

        elif tool_name == "get_top_matches":
            plots = await self.search.query_plots(
                state.preferences,
                limit=args.get("limit", 3),
                offset=args.get("offset", 0)
            )
            state.last_search_results = [p["id"] for p in plots]
            return {"plots": plots}

        elif tool_name == "reveal_plot_details":
            plot_id = args["plot_id"]

            if state.credits_balance <= 0:
                return {
                    "success": False,
                    "error": "insufficient_credits",
                    "packages": [
                        {"name": "single", "credits": 1, "price_pln": 1},
                        {"name": "pack_10", "credits": 10, "price_pln": 9},
                        {"name": "pack_25", "credits": 25, "price_pln": 20}
                    ]
                }

            # Already revealed - free
            if plot_id in state.revealed_plot_ids:
                plot = await self.search.get_full_plot(plot_id)
                return {"success": True, "plot": plot}

            # Deduct credit and reveal
            state.credits_balance -= 1
            state.revealed_plot_ids.add(plot_id)
            plot = await self.search.get_full_plot(plot_id)

            return {
                "success": True,
                "credits_remaining": state.credits_balance,
                "plot": plot
            }

        elif tool_name == "initiate_payment":
            checkout_url = await self.payments.create_checkout(
                session_id=state.session_id,
                package=args["package"]
            )
            return {
                "checkout_url": checkout_url,
                "message": "Kliknij link aby dokonac platnosci"
            }

        elif tool_name == "submit_lead":
            lead_id = await self.leads.create_lead(
                plot_id=args["plot_id"],
                contact=args["contact"],
                intent=args.get("intent", {}),
                session_id=state.session_id
            )
            return {
                "lead_id": lead_id,
                "message": "Dziekujemy! Skontaktujemy sie wkrotce."
            }

        return {"error": f"Unknown tool: {tool_name}"}
```

## Error Handling

The agent should gracefully handle:

1. **Invalid locations**: Inform user we only cover Pomeranian region
2. **No results**: Suggest relaxing criteria
3. **Payment failures**: Provide alternative payment methods
4. **API errors**: Apologize and suggest retrying

Example:

```
User: Szukam dzialki w Warszawie

Agent: Przepraszam, ale obecnie obslugujemy tylko wojewodztwo pomorskie
       (Gdansk, Gdynia, Sopot i okolice).

       Czy moge pomoc znalezc dzialke w tym regionie?
```

---

## Reference Knowledge

### Knowledge Base for Agent Development

When designing or modifying this agent, consult these resources:

| Topic | Resource | Path |
|-------|----------|------|
| **MCP & Tool Calling** | Software 3.0 Course | `/home/marcin/ai-edu/_synthesis/software3.0/modul3/` |
| **AI Assistant Patterns** | AI Devs 2 Course | `/home/marcin/ai-edu/_synthesis/ai-devs-2/modul-5-asystent/` |
| **Agent Frameworks** | Deep Agents Map | `/home/marcin/ai-edu/deepagents/MAPA_DOKUMENTACJI_AGENTOW.md` |
| **Graph RAG for MPZP** | Grafy Modul 5 | `/home/marcin/ai-edu/grafy/05-graph-rag/` |
| **Agentic RAG Patterns** | Research 2025 | `/home/marcin/ai-edu/grafy/research-agentic-rag-2025.md` |
| **Neo4j + LangChain** | Course 1 | `/home/marcin/moja-dzialka/grafy/kurs1-knowledge-graphs-for-rag/` |
| **Agentic KG Construction** | Course 2 | `/home/marcin/moja-dzialka/grafy/kurs2-agentic-kg-construction/` |

### Key Design Patterns from Courses

**From DeepLearning.AI + Neo4j courses:**

1. **Human-in-the-Loop Pattern**
   - Relevant for: `reveal_plot_details`, `submit_lead`
   - User must confirm before spending credits or submitting contact info

2. **Guard Patterns**
   - Relevant for: `count_matching_plots`, `get_top_matches`
   - Validate that preferences are set before running expensive queries

3. **Three-Graph Architecture**
   - Domain Graph: Parcels, MPZP zones, POIs
   - Lexical Graph: Text from MPZP documents
   - Subject Graph: Zoning symbols (MN, MW, U) and their meanings

4. **Critic Pattern**
   - For future: Validate agent recommendations before presenting to user

**From Software 3.0 course:**

1. **MCP Architecture**
   - Tools as first-class citizens
   - Clear input/output schemas
   - Tool composition for complex queries

2. **Reasoning Patterns**
   - Think-before-acting for preference inference
   - Multi-step search refinement

### Full Knowledge Index

See `/home/marcin/ai-edu/_synthesis/KNOWLEDGE_MAP.json` for complete topic/concept mapping.

**Protocol:** Before implementing new agent features, read the relevant essence file from the knowledge base.
