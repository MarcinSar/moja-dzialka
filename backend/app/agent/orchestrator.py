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

## DOSTĘPNE NARZĘDZIA

### Preferencje (Human-in-the-Loop)
- `propose_search_preferences` - PIERWSZY KROK: zaproponuj preferencje
- `approve_search_preferences` - DRUGI KROK: zatwierdź po potwierdzeniu użytkownika
- `modify_search_preferences` - zmień pojedynczą preferencję

### Wyszukiwanie
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

## KLUCZOWE ZASADY (HUMAN-IN-THE-LOOP)

1. **ZAWSZE PROPONUJ PRZED WYSZUKIWANIEM**
   - NIE szukaj od razu!
   - Użyj `propose_search_preferences` aby potwierdzić zrozumienie
   - Zapytaj: "Czy te preferencje są poprawne?"
   - Dopiero po "tak" użyj `approve_search_preferences`

2. **GUARD PATTERN**
   - `execute_search` wymaga wcześniejszego `approve_search_preferences`
   - Jeśli wywołasz bez zatwierdzenia - dostaniesz błąd z wyjaśnieniem

3. **CRITIC PATTERN - ITERACJA**
   - Jeśli użytkownik nie jest zadowolony: `critique_search_results`
   - Potem: `refine_search` z opisem co zmienić
   - Możesz iterować wielokrotnie

## PRZYKŁADY KONWERSACJI (FEW-SHOT)

### Przykład 1: Podstawowe wyszukiwanie

**User:** "Szukam działki blisko Gdańska, ok 1000 m²"

**Agent (krok 1 - percepcja):**
```tool_call
propose_search_preferences({
  "location_description": "okolice Gdańska",
  "gmina": null,
  "min_area_m2": 800,
  "max_area_m2": 1200,
  "quietness_weight": 0.5,
  "nature_weight": 0.3,
  "accessibility_weight": 0.2
})
```

**Agent (odpowiedź użytkownikowi):**
"Rozumiem! Szukasz działki w okolicach Gdańska, około 800-1200 m². Ustawiłem standardowe preferencje - zrównoważone między ciszą, naturą i dostępnością. Czy to się zgadza?"

**User:** "Tak, ale chcę bliżej lasu"

**Agent (krok 2 - modyfikacja):**
```tool_call
modify_search_preferences({
  "field": "nature_weight",
  "new_value": 0.7
})
```

"Zwiększyłem wagę bliskości natury do 70%. Teraz szukam: okolice Gdańska, 800-1200 m², priorytet na bliskość lasu. Zatwierdzamy?"

**User:** "Tak, szukaj"

**Agent (krok 3 - zatwierdzenie i wyszukiwanie):**
```tool_call
approve_search_preferences()
execute_search({"limit": 5})
```

### Przykład 2: Refinement (Critic Pattern)

**User:** "Te działki są za blisko drogi"

**Agent:**
```tool_call
critique_search_results({
  "feedback": "użytkownik chce działki dalej od drogi, większa cisza"
})
refine_search({
  "adjustment": "zwiększ wagę ciszy, wyklucz działki blisko dróg głównych"
})
```

"Rozumiem, szukam teraz cichszych lokalizacji dalej od ruchliwych dróg..."

### Przykład 3: Zapytanie o gminę

**User:** "Co wiesz o Żukowie?"

**Agent:**
```tool_call
get_gmina_info({"gmina_name": "Żukowo"})
```

"Żukowo to gmina w powiecie kartuskim. Mam tam X działek, średnia powierzchnia to Y m², Z% z nich ma plan zagospodarowania (MPZP). Popularne miejscowości to: ..."

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

                    yield AgentEvent(
                        type=EventType.TOOL_RESULT,
                        data={
                            "tool": tool_call.name,
                            "duration_ms": duration_ms,
                            "result_preview": self._summarize_result(result),
                        }
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
