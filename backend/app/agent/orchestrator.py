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
    MESSAGE = "message"  # Streaming text - partial content
    MESSAGE_COMPLETE = "message_complete"  # Final message with is_complete=true
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

SYSTEM_PROMPT = """Jesteś ekspertem od nieruchomości w Polsce. Pomagasz znajdować działki budowlane.

## STYL ROZMOWY

Prowadzisz NATURALNĄ rozmowę - jak doświadczony doradca nieruchomości. Nie robisz wywiadu, tylko rozmawiasz i doradzasz.

**NIE RÓB:**
- Nie zadawaj listy pytań
- Nie bądź formalny
- Nie powtarzaj "świetnie!", "rozumiem"
- Nie pytaj o rzeczy które użytkownik już powiedział
- **NIE SUGERUJ konkretnych lokalizacji** - pytaj użytkownika gdzie szuka

**RÓB:**
- Bądź konkretny i pomocny
- Proponuj opcje i doradzaj (np. "Warto też sprawdzić MPZP...")
- Jak masz minimum info - szukaj od razu
- Informuj o możliwościach (np. "Mogę też szukać blisko przystanku")
- Użyj `list_gminy` żeby sprawdzić dostępne lokalizacje w bazie

## BOGATA BAZA DANYCH

Twoja baza to nie tylko lokalizacja i cisza! Masz dostęp do wielu wymiarów:

### LOKALIZACJA
- **Gminy, miejscowości, powiaty** - użyj `list_gminy` aby poznać dostępne
- **Charakter terenu**: wiejski, podmiejski, miejski, leśny, mieszany

### POWIERZCHNIA
- Dokładna wielkość (m²)
- Kategorie: mała (<800m²), średnia (800-1500), duża (1500-3000), bardzo duża (>3000)

### OTOCZENIE I CISZA
- **Cisza** (wskaźnik 0-100): bardzo_cicha, cicha, umiarkowana, głośna
- **Gęstość zabudowy**: bardzo_gęsta, gęsta, umiarkowana, rzadka, bardzo_rzadka
- **Odległość od przemysłu** (metry) - ważne dla ciszy
- **Budynki w promieniu 500m** - liczba

### NATURA
- **Natura** (wskaźnik 0-100): bardzo_zielona, zielona, umiarkowana, zurbanizowana
- **Odległość do lasu** (metry)
- **Odległość do wody** (jeziora, rzeki)
- **Procent lasu w promieniu 500m**

### DOSTĘPNOŚĆ I INFRASTRUKTURA
- **Dostępność** (wskaźnik 0-100): doskonała, dobra, umiarkowana, ograniczona
- **Odległość do szkoły** (metry)
- **Odległość do sklepu** (metry)
- **Odległość do przystanku** (metry)
- **Dostęp do drogi publicznej** (boolean)

### MPZP (Plan Zagospodarowania)
- **has_mpzp**: czy działka ma plan miejscowy
- **Symbole budowlane**: MN (jednorodzinne), MN/U (jednorodzinne+usługi), MW (wielorodzinne), U (usługi)
- **Symbole niebudowlane**: R (rolne), ZL (leśne), ZP (zieleń), W (wody)

**WAŻNE:** Działka z MPZP = łatwiejsze pozwolenie na budowę!

## JAK MAPOWAĆ POTRZEBY NA KRYTERIA

| Użytkownik mówi | Ustaw kryteria |
|-----------------|----------------|
| "cicha okolica" | quietness_categories: ["bardzo_cicha", "cicha"] |
| "blisko lasu" | max_dist_to_forest_m: 300 LUB nature_categories: ["bardzo_zielona"] |
| "na wsi" | charakter_terenu: ["wiejski"] |
| "podmiejskie" | charakter_terenu: ["podmiejski"] |
| "dobry dojazd" | accessibility_categories: ["doskonały", "dobry"] |
| "blisko szkoły" | max_dist_to_school_m: 1000 |
| "blisko sklepu" | max_dist_to_shop_m: 500 |
| "bez sąsiadów" | building_density: ["bardzo_rzadka", "rzadka"] |
| "duża działka" | area_category: ["duza", "bardzo_duza"] |
| "pod budowę" | mpzp_budowlane: true |
| "z planem" | has_mpzp: true |

## NARZĘDZIA

1. `propose_search_preferences` - proponujesz kryteria (UŻYJ NOWYCH PÓL!)
2. `approve_search_preferences` - zatwierdzasz po zgodzie
3. `execute_search` - wyszukujesz
4. `modify_search_preferences` - zmieniasz pojedyncze pole
5. `generate_map_data` - generujesz mapę (PO WYSZUKANIU!)
6. `find_similar_parcels` - znajdź podobne
7. `critique_search_results` / `refine_search` - popraw wyniki
8. `get_parcel_details`, `get_gmina_info`, `list_gminy` - szczegóły

## FLOW

1. Zbierz minimum info przez naturalną rozmowę (lokalizacja + wielkość + 1-2 preferencje)
2. Jak masz podstawy → propose_search_preferences z WSZYSTKIMI zebranymi preferencjami
3. Użytkownik potwierdza → approve + execute_search
4. Pokaż wyniki → generate_map_data
5. Dopytuj/poprawiaj jeśli trzeba

**Nie przedłużaj niepotrzebnie. Masz bogatą bazę - jak masz ogólny obraz, szukaj od razu!**

## PRZYKŁADY ROZMOWY

**User:** "Szukam działki na dom"
**Ty:** "Jasne! W jakim regionie szukasz?"

**User:** "Gdzieś pod miastem, spokojnie"
**Ty:** "Rozumiem - podmiejskie, ciche okolice. Jakiej wielkości działki szukasz? I co jest dla Ciebie ważniejsze - bliskość lasu czy dobra infrastruktura (szkoła, sklepy)?"

**User:** "Około 1500m2, las ważniejszy"
**Ty:** "Zielono i spokojnie - sprawdzę działki 1200-2000m² w zielonych, cichych miejscach z charakterem podmiejskim. Mogę od razu filtrować te z planem zagospodarowania (MPZP) - łatwiej wtedy o pozwolenie. Szukam?"

[propose_search_preferences z: charakter_terenu=["podmiejski"], area_category=["srednia","duza"], nature_categories=["bardzo_zielona","zielona"], quietness_categories=["bardzo_cicha","cicha"], has_mpzp=true]

PAMIĘTAJ:
- Zawsze używaj narzędzi - nie wymyślaj danych!
- NIE sugeruj konkretnych gmin/miejscowości - pytaj użytkownika!
- Użyj `list_gminy` jeśli chcesz sprawdzić co jest w bazie.
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
        # Use async client for proper async streaming
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.conversation_history: List[Dict[str, Any]] = []

    async def chat(
        self,
        user_message: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Process user message and yield events with real streaming.

        Args:
            user_message: User's input message

        Yields:
            AgentEvent objects for UI updates (including streaming text)
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

                # Use streaming API
                assistant_content = []
                tool_calls = []
                current_text = ""
                current_tool_input = ""
                current_tool_id = None
                current_tool_name = None

                async with self.client.messages.stream(
                    model=self.MODEL,
                    max_tokens=self.MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=AGENT_TOOLS,
                    messages=self.conversation_history,
                ) as stream:
                    async for event in stream:
                        # Handle different event types
                        if event.type == "content_block_start":
                            if event.content_block.type == "text":
                                current_text = ""
                            elif event.content_block.type == "tool_use":
                                current_tool_id = event.content_block.id
                                current_tool_name = event.content_block.name
                                current_tool_input = ""

                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                # Stream text delta to frontend
                                delta_text = event.delta.text
                                current_text += delta_text
                                yield AgentEvent(
                                    type=EventType.MESSAGE,
                                    data={
                                        "content": delta_text,
                                        "is_complete": False
                                    }
                                )
                            elif hasattr(event.delta, "partial_json"):
                                # Accumulate tool input JSON
                                current_tool_input += event.delta.partial_json

                        elif event.type == "content_block_stop":
                            if current_text:
                                assistant_content.append({
                                    "type": "text",
                                    "text": current_text,
                                })
                                # Signal text block complete
                                yield AgentEvent(
                                    type=EventType.MESSAGE,
                                    data={
                                        "content": "",
                                        "is_complete": True
                                    }
                                )
                                current_text = ""
                            elif current_tool_id:
                                # Parse complete tool input
                                try:
                                    tool_input = json.loads(current_tool_input) if current_tool_input else {}
                                except json.JSONDecodeError:
                                    tool_input = {}

                                tool_calls.append({
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": tool_input,
                                })
                                assistant_content.append({
                                    "type": "tool_use",
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": tool_input,
                                })
                                current_tool_id = None
                                current_tool_name = None
                                current_tool_input = ""

                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_content,
                })

                # If no tool calls, we're done
                if not tool_calls:
                    break

                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    yield AgentEvent(
                        type=EventType.TOOL_CALL,
                        data={
                            "tool": tool_call["name"],
                            "params": tool_call["input"],
                        }
                    )

                    # Execute tool
                    start_time = time.time()
                    result = await execute_tool(tool_call["name"], tool_call["input"])
                    duration_ms = int((time.time() - start_time) * 1000)

                    # For map tools, include full result for frontend visualization
                    event_data = {
                        "tool": tool_call["name"],
                        "duration_ms": duration_ms,
                        "result_preview": self._summarize_result(result),
                    }

                    # Include full result for visualization tools
                    if tool_call["name"] in ("generate_map_data", "execute_search"):
                        event_data["result"] = result

                    yield AgentEvent(
                        type=EventType.TOOL_RESULT,
                        data=event_data
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
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
