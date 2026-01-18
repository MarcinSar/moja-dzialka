"""
AI Agent orchestrator using Claude API.

Implements patterns from Neo4j Knowledge Graph courses:
- Human-in-the-Loop: propose → confirm → approve
- Guard Patterns: validate state before operations
- Critic Pattern: iterative refinement
- Few-Shot Prompting: examples in system prompt
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import json
import time

from loguru import logger
import anthropic

from app.config import settings
from app.agent.tools import AGENT_TOOLS, execute_tool, reset_state


# =============================================================================
# EVENT TYPES
# =============================================================================

class EventType(str, Enum):
    """Types of events emitted by the agent."""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"
    ERROR = "error"
    DONE = "done"


@dataclass
class AgentEvent:
    """Event emitted during agent processing."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# =============================================================================
# SYSTEM PROMPT (with Few-Shot Examples from KG courses)
# =============================================================================

SYSTEM_PROMPT = """Jesteś Działkowiczem - przyjaznym ekspertem od działek budowlanych w województwie pomorskim.
Pomagasz użytkownikom znaleźć idealną działkę pod budowę domu.

## TWOJA OSOBOWOŚĆ
- Przyjazny, pomocny, kompetentny
- Znasz Pomorze jak własną kieszeń
- Mówisz prostym językiem, unikasz żargonu
- Jesteś szczery - mówisz zarówno o zaletach jak i wadach
- ZADAJESZ PYTANIA - chcesz dobrze poznać potrzeby użytkownika

## BAZA WIEDZY (GRAF NEO4J)

Masz dostęp do szczegółowej bazy wiedzy o 10,471 działkach. Każda działka ma:

### Kategorie ciszy:
- bardzo_cicha - daleko od dróg i zabudowy
- cicha - spokojna okolica
- umiarkowana - typowa okolica podmiejska
- glosna - blisko ruchliwych dróg

### Kategorie natury:
- wysoka - las/woda w bezpośrednim sąsiedztwie
- dobra - dużo zieleni w okolicy
- srednia - trochę zieleni
- niska - zurbanizowane

### Charakter terenu:
- lesny - w lesie lub przy lesie
- rolny - pola, łąki
- mieszany - pola + zabudowa
- zabudowany - osiedle, wieś
- wodny - przy jeziorze/rzece

### Gęstość zabudowy:
- bardzo_gesta, gesta, umiarkowana, rzadka, bardzo_rzadka

### Bliskość do:
- SZKOŁY (6,388 działek w pobliżu)
- SKLEPU (6,333 działek)
- PRZYSTANKU (5,503 działek)
- SZPITALA (7,332 działek)
- LASU (9,607 działek)
- WODY (9,487 działek)

### MPZP (Plan zagospodarowania):
- 6,180 działek ma MPZP (59%)
- Symbole: MN (mieszkaniowa), U (usługowa), R (rolna), ZL (leśna)...

### Gminy (15):
Gdańsk, Pruszcz Gdański, Kolbudy, Żukowo, Somonino, Kartuzy...

## STRATEGIA ROZMOWY - ZADAWAJ PYTANIA!

**ZANIM zaproponujesz preferencje, ZAPYTAJ o:**

1. **Cel działki:**
   - "Czy to ma być działka pod dom jednorodzinny, bliźniak, czy może rekreacyjna?"

2. **Lokalizacja:**
   - "Czy masz konkretną gminę na myśli, czy szukamy w całym województwie?"
   - "Blisko jakiego miasta chcesz mieszkać?"

3. **Charakter okolicy:**
   - "Wolisz ciszę i spokój (wiejskie klimaty) czy bliskość miasta i udogodnień?"
   - "Las i natura są dla Ciebie ważne?"
   - "Zależy Ci na bliskości wody - jeziora, rzeki?"

4. **Infrastruktura:**
   - "Czy ważna jest bliskość szkoły dla dzieci?"
   - "Komunikacja publiczna - autobusy, PKM?"
   - "Sklep w zasięgu spaceru?"

5. **MPZP (bardzo ważne!):**
   - "Czy zależy Ci na działce z planem zagospodarowania (MPZP)?"
   - "To ważne - bez MPZP musisz czekać na warunki zabudowy"

6. **Powierzchnia:**
   - "Jaka powierzchnia? 800-1000 m² to typowe pod dom, 1500+ dla większego ogrodu"

## DOSTĘPNE NARZĘDZIA

### Preferencje (Human-in-the-Loop)
- `propose_search_preferences` - PIERWSZY KROK: zaproponuj preferencje
- `approve_search_preferences` - DRUGI KROK: zatwierdź po potwierdzeniu użytkownika
- `modify_search_preferences` - zmień pojedynczą preferencję

### Wyszukiwanie (używa grafu wiedzy!)
- `execute_search` - wyszukaj działki (wymaga zatwierdzonych preferencji!)
- `find_similar_parcels` - znajdź podobne do wskazanej

### Ulepszanie wyników (Critic Pattern)
- `critique_search_results` - zapisz feedback użytkownika
- `refine_search` - popraw wyniki na podstawie feedbacku

### Informacje
- `get_parcel_details` - szczegóły działki
- `get_gmina_info` - informacje o gminie
- `list_gminy` - lista gmin
- `get_mpzp_symbols` - symbole MPZP (MN, U, ZL, itp.)

### Mapa
- `generate_map_data` - GeoJSON do wyświetlenia na mapie

## KLUCZOWE ZASADY

1. **NAJPIERW PYTANIA, POTEM WYSZUKIWANIE**
   - Zadaj 2-3 pytania żeby lepiej zrozumieć potrzeby
   - Dopiero potem użyj `propose_search_preferences`
   - Zapytaj: "Czy te preferencje są poprawne?"
   - Po potwierdzeniu: `approve_search_preferences` → `execute_search`

2. **UŻYWAJ WIEDZY O GRAFIE**
   - Gdy użytkownik mówi "cicha" → ustaw has_mpzp i quietness_weight
   - Gdy mówi "las" → nature_weight wysoki + charakter "lesny"
   - Gdy mówi "szkoła" → accessibility_weight wyższy
   - Gdy mówi "MPZP" → has_mpzp = true

3. **POKAZUJ NA MAPIE**
   - Po wyszukaniu ZAWSZE użyj `generate_map_data`
   - Pokaż użytkownikowi gdzie są działki

4. **ITERUJ (CRITIC PATTERN)**
   - Jeśli użytkownik nie jest zadowolony: dopytaj co zmienić
   - `critique_search_results` → `refine_search`

## PRZYKŁAD DOBREJ ROZMOWY

**User:** "Szukam działki"

**Agent:** "Świetnie! Pomogę Ci znaleźć idealną działkę na Pomorzu. Żeby dobrze dopasować wyniki, mam kilka pytań:

1. Czy szukasz działki pod dom jednorodzinny?
2. Czy masz preferencje co do lokalizacji - konkretna gmina, okolice jakiegoś miasta?
3. Co jest dla Ciebie ważniejsze - cisza i natura, czy bliskość miasta i udogodnień?"

**User:** "Dom jednorodzinny, okolice Pruszcza, ważna cisza i las w pobliżu"

**Agent:** "Rozumiem - szukamy spokojnej działki przy lesie, w okolicach Pruszcza Gdańskiego. Jeszcze jedno pytanie - czy zależy Ci na działce z planem zagospodarowania (MPZP)? To znacznie przyspiesza formalności budowlane."

**User:** "Tak, z MPZP"

**Agent:** [propose_search_preferences z: gmina="Pruszcz Gdański", has_mpzp=true, quietness_weight=0.8, nature_weight=0.8]

"Szukam działki:
- Gmina: Pruszcz Gdański
- Z planem zagospodarowania (MPZP)
- Priorytet: cisza (80%) i bliskość lasu (80%)
- Powierzchnia: 800-1500 m² (standardowa)

Czy to się zgadza, czy chcesz coś zmienić?"

## MONETYZACJA (PAMIĘTAJ!)

- Pierwszych 3 działek pokazujesz ZA DARMO
- Dla więcej wyników użytkownik musi zapłacić 20 PLN
- Wspominaj o tym naturalnie gdy użytkownik chce więcej

## SYMBOLE MPZP (dla referencji)

| Symbol | Znaczenie |
|--------|-----------|
| MN | Mieszkaniowa jednorodzinna |
| MW | Mieszkaniowa wielorodzinna |
| U | Usługowa |
| ZL | Leśna |
| R | Rolna |
| KD | Komunikacja drogowa |

## FLOW KONWERSACJI

```
1. Powitanie → zbierz preferencje (pytaj!)
2. propose_search_preferences → "Czy to poprawne?"
3. User: "Tak" → approve_search_preferences
4. execute_search → pokaż wyniki
5. User niezadowolony? → critique + refine
6. User zadowolony? → generate_map_data + szczegóły
7. Więcej niż 3 działki? → wspomnieć o płatności
```

PAMIĘTAJ: ZAWSZE używaj narzędzi do wyszukiwania. Nie wymyślaj danych!
"""


# =============================================================================
# AGENT CLASS
# =============================================================================

class ParcelAgent:
    """
    AI Agent for parcel search conversation.

    Uses Claude API with tool calling for natural language interaction.
    Implements Human-in-the-Loop, Guard Patterns, and Critic Pattern.
    """

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 8

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.conversation_history: List[Dict[str, Any]] = []

    async def chat(
        self,
        user_message: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Process user message and yield events.

        Args:
            user_message: User's input message

        Yields:
            AgentEvent objects for UI updates
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        yield AgentEvent(
            type=EventType.THINKING,
            data={"message": "Analizuję Twoje zapytanie..."}
        )

        try:
            # Process with tool loop
            iterations = 0
            while iterations < self.MAX_TOOL_ITERATIONS:
                iterations += 1

                # Call Claude API
                response = self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=self.MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=AGENT_TOOLS,
                    messages=self.conversation_history,
                )

                # Process response content
                assistant_content = []
                tool_calls = []

                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "tool_use":
                        tool_calls.append(block)
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_content,
                })

                # If no tool calls, we're done
                if not tool_calls:
                    text_response = ""
                    for block in response.content:
                        if block.type == "text":
                            text_response += block.text

                    yield AgentEvent(
                        type=EventType.MESSAGE,
                        data={"content": text_response}
                    )
                    break

                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    yield AgentEvent(
                        type=EventType.TOOL_CALL,
                        data={
                            "tool": tool_call.name,
                            "params": tool_call.input,
                        }
                    )

                    # Execute tool
                    start_time = time.time()
                    result = await execute_tool(tool_call.name, tool_call.input)
                    duration_ms = int((time.time() - start_time) * 1000)

                    # For map tools, include full result for frontend visualization
                    event_data = {
                        "tool": tool_call.name,
                        "duration_ms": duration_ms,
                        "result_preview": self._summarize_result(result),
                    }

                    # Include full result for visualization tools
                    if tool_call.name in ("generate_map_data", "execute_search"):
                        event_data["result"] = result

                    yield AgentEvent(
                        type=EventType.TOOL_RESULT,
                        data=event_data
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # Add tool results to history
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

                yield AgentEvent(
                    type=EventType.THINKING,
                    data={"message": "Przetwarzam wyniki..."}
                )

            yield AgentEvent(
                type=EventType.DONE,
                data={"iterations": iterations}
            )

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            yield AgentEvent(
                type=EventType.ERROR,
                data={"message": f"Błąd API: {e}"}
            )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield AgentEvent(
                type=EventType.ERROR,
                data={"message": f"Wystąpił błąd: {str(e)}"}
            )

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Create a brief summary of tool result for UI."""
        if "error" in result:
            return f"Błąd: {result['error']}"

        if "status" in result:
            status = result["status"]
            if status == "proposed":
                return "Preferencje zaproponowane - czekam na potwierdzenie"
            elif status == "approved":
                return "Preferencje zatwierdzone - gotowe do wyszukiwania"
            elif status == "modified":
                return f"Zmieniono: {result.get('field')}"

        if "count" in result:
            count = result["count"]
            if "parcels" in result:
                return f"Znaleziono {count} działek"
            elif "gminy" in result:
                return f"Lista {count} gmin"
            elif "symbols" in result:
                return f"Lista {count} symboli MPZP"
            return f"Znaleziono {count} wyników"

        if "parcel" in result:
            p = result["parcel"]
            return f"Działka {p.get('id_dzialki', 'N/A')} - {p.get('area_m2', 'N/A')} m²"

        if "gmina" in result:
            return f"Gmina {result['gmina']}: {result.get('parcel_count', 'N/A')} działek"

        if "geojson" in result:
            return f"Mapa z {result.get('parcel_count', 0)} działkami"

        return "Dane pobrane"

    def clear_history(self):
        """Clear conversation history and reset agent state."""
        self.conversation_history = []
        reset_state()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self.conversation_history.copy()

    def set_history(self, history: List[Dict[str, Any]]):
        """Set conversation history (for session restore)."""
        self.conversation_history = history.copy()


# =============================================================================
# STREAMING HELPER
# =============================================================================

async def chat_stream(
    agent: ParcelAgent,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses as Server-Sent Events (SSE).

    Args:
        agent: ParcelAgent instance
        user_message: User's input

    Yields:
        SSE-formatted event strings
    """
    async for event in agent.chat(user_message):
        yield f"data: {event.to_json()}\n\n"
