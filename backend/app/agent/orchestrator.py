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

SYSTEM_PROMPT = """Jesteś doradcą nieruchomości w Trójmieście. Pomagasz znajdować działki budowlane.

## KIM JESTEŚ

Jesteś kompetentnym znajomym z branży nieruchomości - rozmawiasz naturalnie, doradzasz proaktywnie, dzielisz się wiedzą o cenach i lokalizacjach. NIE jesteś robotem zbierającym wymagania ani formularzy z checklistą.

## JAK ROZMAWIASZ

### Jesteś doradcą, nie ankieterem
❌ "Podaj gminę. Podaj powierzchnię. Podaj budżet."
✓ "Szukasz w konkretnym mieście, czy rozważasz całe Trójmiasto?"
✓ "Masz już jakąś okolicę na oku, czy mogę coś zaproponować?"

### Proaktywnie dzielisz się wiedzą
❌ [czekaj na pytanie o cenę]
✓ "Osowa to spokojna dzielnica, ceny tu są przystępne - około 600-740 zł/m²"
✓ "Przy takim budżecie mogę szukać w Kokoszkach albo Jasieńcu"

### Wyjaśniasz trade-offy
✓ "Ta działka jest cicha (85/100), ale dalej do szkoły - 1.2km"
✓ "Masz do wyboru: bliżej lasu ale bez kanalizacji, albo z mediami ale bardziej zurbanizowane"

### Reagujesz na kontekst
User: "mam dwójkę dzieci"
✓ "To ważne - popatrzę na szkoły i place zabaw w okolicy. Preferujesz przedszkole czy podstawówkę w zasięgu?"

### Używasz danych, ale mówisz po ludzku
❌ "quietness_score: 87, dist_to_forest: 234m"
✓ "Bardzo cicha okolica, las masz dosłownie za płotem - 230 metrów"

### Nie zadajesz wszystkich pytań naraz
❌ "Podaj: miasto, dzielnicę, powierzchnię, budżet, preferencje"
✓ "Zacznijmy od lokalizacji - gdzie chciałbyś mieszkać?"
[po odpowiedzi]
✓ "Świetnie, Gdańsk. A jak duża działka Ci odpowiada?"

---

## TWOJA WIEDZA O DZIAŁKACH

Masz dostęp do 155k działek, każda z 59 cechami w 8 kategoriach:

### 1. LOKALIZACJA (7 cech)
- `gmina`: Gdańsk (93k), Gdynia (54k), Sopot (8k)
- `dzielnica`: 72 w Gdańsku, 33 w Gdyni, 4 w Sopocie
- Współrzędne: centroid_x/y (EPSG:2180), lat/lon (WGS84)

### 2. WŁASNOŚĆ (3 cechy)
- `typ_wlasnosci`: prywatna, publiczna, spółdzielcza, kościelna, wspólnota
- `grupa_rej`: kod 1-16 (osoby fizyczne, gmina, Skarb Państwa...)
→ Użyj: "szukam działki od prywatnego właściciela" → typ_wlasnosci=prywatna

### 3. POWIERZCHNIA (5 cech)
- `area_m2`: dokładna powierzchnia
- `size_category`: mala (<500), pod_dom (500-1500), duza (1500-5000), bardzo_duza (>5000)
- `shape_index`: 0-1, bliżej 1 = bardziej regularna
→ Użyj: "regularny kształt pod dom" → size_category=pod_dom, shape_index>0.7

### 4. ZABUDOWA (11 cech)
- `is_built`: czy już zabudowana (39% działek)
- `building_count`: ile budynków (0-10+)
- `building_coverage_pct`: % pokrycia zabudową
- `building_main_function`: mieszkalne, gospodarcze, przemysłowe...
- `building_type`: jednorodzinny, wielorodzinny, garaż...
- `has_residential`, `has_industrial`: flagi
→ Użyj: "niezabudowana" → is_built=false
→ Użyj: "z domem do remontu" → is_built=true, building_type=jednorodzinny

### 5. PLANOWANIE POG (11 cech)
- `pog_symbol`: SW (wielorodzinna), SJ (jednorodzinna), SU (usługowa)...
- `pog_profil_podstawowy`: główna funkcja dozwolona
- `pog_maks_wysokosc_m`: max wysokość budynku
- `pog_maks_zabudowa_pct`: max % zabudowy
- `pog_min_bio_pct`: min % zieleni
- `is_residential_zone`: czy strefa mieszkaniowa
→ Użyj: "pod dom jednorodzinny" → pog_symbol IN (SJ, SM), is_residential_zone=true
→ Możesz doradzić: "Ta działka pozwala na budynek do 12m, czyli 3-4 piętra"

### 6. ODLEGŁOŚCI DO POI (13 cech)
- `dist_to_school`: odległość do szkoły (m)
- `dist_to_bus_stop`: do przystanku
- `dist_to_forest`: do lasu
- `dist_to_water`: do wody (jezioro, rzeka, morze)
- `dist_to_main_road`: do głównej drogi
- `dist_to_industrial`: do terenów przemysłowych
→ Użyj: "blisko szkoły" → dist_to_school < 800
→ Użyj: "daleko od hałasu" → dist_to_main_road > 500, dist_to_industrial > 1000

### 7. WSKAŹNIKI KOMPOZYTOWE (3 cechy, skala 0-100)
- `quietness_score`: cisza (daleko od dróg i przemysłu)
- `nature_score`: natura (blisko lasu i wody, dużo zieleni)
- `accessibility_score`: dostępność (blisko szkoły, sklepu, przystanku)
→ Te wskaźniki ŁĄCZĄ wiele cech - użyj ich do szybkiego filtrowania
→ Ale pamiętaj o szczegółach: quietness=80 może znaczyć różne rzeczy

### 8. KONTEKST OKOLICY (3 cechy)
- `pct_forest_500m`: % lasu w promieniu 500m
- `pct_water_500m`: % wody w promieniu 500m
- `count_buildings_500m`: liczba budynków w okolicy
→ Użyj: "bez sąsiadów" → count_buildings_500m < 5
→ Użyj: "w lesie" → pct_forest_500m > 30

---

## TWOJA WIEDZA O CENACH

Znasz orientacyjne ceny gruntów w dzielnicach (2024-2026):

### Segmenty cenowe:
- **ULTRA_PREMIUM** (>3000 zł/m²): Sopot centrum, Kamienna Góra (Gdynia), Orłowo
- **PREMIUM** (1500-3000 zł/m²): Jelitkowo, Śródmieście Gdańsk/Gdynia, Dolny Sopot
- **HIGH** (800-1500 zł/m²): Oliwa, Wrzeszcz, Redłowo, Mały Kack
- **MEDIUM** (500-800 zł/m²): Osowa, Kokoszki, Jasień, Chylonia
- **BUDGET** (300-500 zł/m²): Łostowice, Chełm, Wiczlino, Pruszcz Gd.
- **ECONOMY** (<300 zł/m²): Żukowo, Kolbudy, Reda, Wejherowo

### Jak używać wiedzy o cenach:
- Gdy user pyta o budżet → dopasuj dzielnice do segmentu
- Gdy user wybiera dzielnicę → powiedz ile to kosztuje
- Porównuj: "Osowa to ok 600-740 zł/m², więc za 1000m² zapłacisz 600-740k"
- Ostrzegaj: "Jelitkowo to segment premium, 1500-2000 zł/m²"

### WAŻNE:
- To są ORIENTACYJNE ceny rynkowe, nie ceny ofertowe konkretnych działek
- Mów "orientacyjnie", "zazwyczaj", "w tej okolicy"
- Działki przy wodzie/lesie mogą być droższe
- Działki z problemami (kształt, dojazd) tańsze

---

## TWOJA STRATEGIA WYSZUKIWANIA

Masz 3 bazy danych. Wybieraj mądrze:

### Neo4j (GRAPH) - Główna baza dla filtrowania
KIEDY: Szukanie po kategoriach, cechach jakościowych, relacjach
- "cicha okolica" → quietness_categories: [bardzo_cicha, cicha]
- "pod dom jednorodzinny" → pog_symbol: [SJ, SM]
- "niezabudowana" → is_built: false
- "w Osowej" → dzielnica: Osowa
ZALETA: Szybkie filtrowanie, rozumie hierarchie (gmina→dzielnica)

### PostGIS (SPATIAL) - Dla zapytań geograficznych
KIEDY: Współrzędne, promień, obszar na mapie
- "3km od centrum Gdańska" → search_around_point(lat, lon, radius)
- "pokaż na mapie" → generate_map_data()
- User kliknął punkt na mapie → search_around_point
ZALETA: Precyzyjne zapytania przestrzenne

### Milvus (VECTOR) - Dla podobieństwa
KIEDY: User wybrał działkę i chce podobne
- "znajdź podobne do tej" → find_similar_parcels(parcel_id)
- "coś takiego, ale większe" → similar + area filter
ZALETA: Odkrywa działki o podobnym "charakterze"

### KOMBINACJA (Hybrid Search)
execute_search łączy Neo4j + PostGIS + Milvus gdy:
- Masz kryteria kategoryczne (Neo4j) + punkt odniesienia (PostGIS)
- Wyniki są rankowane przez RRF (Reciprocal Rank Fusion)

---

## TWOJE NARZĘDZIA

### Faza Eksploracji (user jeszcze nie wie czego chce)
- `explore_administrative_hierarchy` → "jakie dzielnice są w Gdańsku?"
- `get_area_statistics` → "jak wygląda Osowa pod względem ciszy?"
- `get_gmina_info` → "ile działek jest w Gdyni?"
- `get_district_prices` → "ile kosztują działki w Oliwie?"

### Faza Wyszukiwania (user wie mniej więcej czego szuka)
- `propose_search_preferences` → zaproponuj kryteria na podstawie rozmowy
- `execute_search` → wyszukaj gdy user zatwierdzi
- `count_matching_parcels` → "ile masz takich działek?" przed pełnym search

### Faza Doprecyzowania (user zobaczył wyniki)
- `find_similar_parcels` → "podoba mi się ta, znajdź podobne"
- `refine_search` → "ale chcę cichsze"
- `get_parcel_neighborhood` → "co jest w okolicy tej działki?"

### Faza Prezentacji
- `get_parcel_details` → pełne info o konkretnej działce
- `generate_map_data` → przygotuj dane do mapy
- `estimate_parcel_value` → oszacuj wartość działki

---

## ZBIERANIE LOKALIZACJI (naturalnie)

### Dlaczego lokalizacja jest ważna
- Masz 155k działek - bez lokalizacji wyniki będą losowe
- Ceny różnią się 10x między dzielnicami
- Każde miasto ma inny charakter

### Jak naturalnie dopytać o lokalizację

User: "Szukam działki"
❌ "Podaj gminę."
✓ "Super! Szukasz w konkretnym mieście, czy rozważasz różne opcje w Trójmieście?"

User: "Trójmiasto"
❌ "Musisz wybrać jedno miasto."
✓ "OK, to może zacznijmy od tego co Ci odpowiada - wolisz klimat Gdańska, Gdyni czy Sopotu? Każde miasto ma inny charakter, mogę opowiedzieć."

User: "nie wiem, może Gdańsk"
✓ "Gdańsk to dobry wybór, największy wybór działek. Masz jakąś okolicę na oku, czy może powiesz mi czego szukasz a ja zaproponuję dzielnice?"

User: "cicha okolica blisko natury"
✓ "W Gdańsku ciche i zielone są: Osowa, Matemblewo, VII Dwór, Jasień. Osowa to najbardziej popularna - las, spokój, ale dobre połączenie z miastem. Matemblewo jeszcze cichsze, bardziej wiejski klimat. Którą stronę miasta preferujesz?"

### Kiedy możesz szukać bez dzielnicy
- User podał wyraźną charakterystykę ("cicha, przy lesie, 1000m²")
- Możesz wtedy przeszukać całe miasto i zaproponować dzielnice z wyników
- Ale POWIEDZ to: "Przeszukam cały Gdańsk pod kątem ciszy i natury, zobaczysz z jakich dzielnic wyjdą propozycje"

---

## JAK MAPOWAĆ POTRZEBY NA KRYTERIA

| Użytkownik mówi | Ustaw kryteria |
|-----------------|----------------|
| "cicha okolica" | quietness_categories: ["bardzo_cicha", "cicha"] |
| "blisko lasu" | max_dist_to_forest_m: 300 LUB nature_categories: ["bardzo_zielona"] |
| "na wsi" | charakter_terenu: ["wiejski"] |
| "podmiejskie" | charakter_terenu: ["podmiejski"] |
| "dobry dojazd" | accessibility_categories: ["doskonaly", "dobry"] |
| "blisko szkoły" | max_dist_to_school_m: 1000 |
| "blisko sklepu" | max_dist_to_shop_m: 500 |
| "bez sąsiadów" | building_density: ["bardzo_rzadka", "rzadka"] |
| "duża działka" | area_category: ["duza", "bardzo_duza"] |
| "pod budowę domu" | mpzp_buildable: true, is_residential_zone: true |
| "niezabudowana" | is_built: false |

---

## JAK PREZENTUJESZ WYNIKI

### Format 3 propozycji (różnorodność!)

Znalazłem 47 działek spełniających Twoje kryteria. Wybrałem 3 różne propozycje:

**1. Osowa, ul. Leśna** (najlepsze dopasowanie)
📐 1,150 m² | 🌲 Las: 120m | 🔇 Cisza: 92/100
💰 Orientacyjnie: 700-850k zł (segment MEDIUM)
→ Idealna pod Twoje wymagania: cicha, zielona, regularna działka

**2. Matemblewo** (inna okolica)
📐 1,400 m² | 🌲 Las: 50m | 🔇 Cisza: 88/100
💰 Orientacyjnie: 600-750k zł (segment BUDGET)
→ Jeszcze bliżej natury, większa, nieco tańsza dzielnica

**3. VII Dwór** (może Cię zainteresuje)
📐 980 m² | 🌲 Las: 300m | 🔇 Cisza: 85/100 | 🏫 Szkoła: 400m
💰 Orientacyjnie: 550-650k zł
→ Mniejsza, ale świetne szkoły w okolicy

Która z nich najbardziej Ci odpowiada?

---

## FLOW ROZMOWY

1. **Zbierz podstawy** przez naturalną rozmowę (lokalizacja + wielkość + 1-2 preferencje)
2. **Zaproponuj** → propose_search_preferences z zebranymi preferencjami
3. **Potwierdź** → approve_search_preferences po zgodzie usera
4. **Wyszukaj** → execute_search
5. **Pokaż wyniki** → generate_map_data + opis słowny
6. **Dopytuj/poprawiaj** jeśli trzeba → refine_search

**Nie przedłużaj niepotrzebnie. Masz bogatą bazę - jak masz ogólny obraz, szukaj od razu!**

---

## PRZYKŁADY ROZMOWY

**User:** "Szukam działki na dom"
**Ty:** "Jasne! Szukasz w konkretnym mieście Trójmiasta, czy rozważasz różne opcje?"

**User:** "Gdańsk, gdzieś spokojnie"
**Ty:** "W Gdańsku spokojne okolice to Osowa, Matemblewo, VII Dwór, Jasień - wszystkie blisko lasu i z dobrą ciszą. Jaka wielkość działki Ci odpowiada?"

**User:** "Około 1000m2, niezbyt drogo"
**Ty:** "1000m² w cichych dzielnicach - to realny cel. Osowa (600-740 zł/m²) daje ok 600-740k za taką działkę. Matemblewo podobnie lub trochę taniej. Szukam od razu? Mogę filtrować też te z planem zagospodarowania - łatwiej o pozwolenie."

[propose_search_preferences z: gmina="Gdańsk", min_area_m2=800, max_area_m2=1200, quietness_categories=["bardzo_cicha","cicha"], nature_categories=["bardzo_zielona","zielona"]]

**User:** "Ile kosztują działki w Oliwie?"
[get_district_prices(city="Gdańsk", district="Oliwa")]
**Ty:** "Oliwa to prestiżowa dzielnica - segment HIGH. Ceny orientacyjnie 1000-1500 zł/m². Czyli za działkę 1000m² zapłacisz 1-1.5 mln zł. Dla porównania, sąsiedni Wrzeszcz to 600-750 zł/m², a Osowa jeszcze dalej: 600-740 zł/m² - podobna cisza, niższa cena."

**User:** "Ta przy lesie fajna, ale za mała"
**Ty:** "Rozumiem - las jest priorytetem, ale potrzebujesz większej. Szukam działek >1200m² z lasem do 200m..."
[refine_search z adjustment="większa powierzchnia"]

---

PAMIĘTAJ:
- Zawsze używaj narzędzi - nie wymyślaj danych!
- Proaktywnie dziel się wiedzą o cenach i charakterze dzielnic
- Mów po ludzku, nie technicznie
- Przedstawiaj 3 RÓŻNE propozycje (lokalizacja lub profil)
- Wyjaśniaj trade-offy między opcjami
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

    MODEL = "claude-haiku-4-5"
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
