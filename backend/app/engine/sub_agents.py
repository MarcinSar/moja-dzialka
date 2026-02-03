"""
Sub-Agent Spawner - Multi-agent orchestration system.

Implements a hierarchical multi-agent architecture inspired by OpenClaw:

ROOT ORCHESTRATOR (Sonnet)
├── Discovery Agent (Haiku/configurable) - zbieranie preferencji
├── Search Agent (Haiku) - wykonywanie wyszukiwań
├── Analyst Agent (Sonnet) - analiza i porównania
├── Narrator Agent (Sonnet) - opisy i narracje
├── Feedback Agent (Haiku/configurable) - obsługa feedbacku
└── Lead Agent (Haiku) - zbieranie kontaktów

Each sub-agent has:
- Specialized tools
- Configured model (cost optimization)
- Isolated or selective context
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Set
from enum import Enum
from dataclasses import dataclass, field
import json
import time
import asyncio

from loguru import logger
from pydantic import BaseModel, Field

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from app.config import settings
from app.memory import AgentState


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

class ModelType(str, Enum):
    """Available model types for agents."""
    HAIKU = "claude-haiku-4-5"
    SONNET = "claude-sonnet-4-20250514"
    OPUS = "claude-opus-4-20250514"


# Default model assignments per agent type (can be overridden)
DEFAULT_MODEL_CONFIG = {
    "root": ModelType.SONNET,       # Orchestration needs reasoning
    "discovery": ModelType.HAIKU,   # Simple preference collection
    "search": ModelType.HAIKU,      # Tool execution, structured
    "analyst": ModelType.SONNET,    # Complex reasoning, comparisons
    "narrator": ModelType.SONNET,   # Creative descriptions
    "feedback": ModelType.HAIKU,    # Pattern matching
    "lead": ModelType.HAIKU,        # Simple data collection
}


# =============================================================================
# AGENT TYPE DEFINITIONS
# =============================================================================

class AgentType(str, Enum):
    """Types of specialized sub-agents."""
    DISCOVERY = "discovery"     # Preference collection
    SEARCH = "search"           # Search execution
    ANALYST = "analyst"         # Analysis and comparison
    NARRATOR = "narrator"       # Descriptive narratives
    FEEDBACK = "feedback"       # Feedback handling
    LEAD = "lead"               # Lead capture


@dataclass
class AgentConfig:
    """Configuration for a sub-agent type."""
    name: str
    description: str
    model: ModelType
    tools: List[str]                    # Available tool names
    system_prompt_template: str         # Jinja2 template for system prompt
    context_mode: str = "selective"     # "full", "selective", "minimal"
    max_tokens: int = 2048
    max_tool_iterations: int = 5


# Sub-agent configurations
AGENT_CONFIGS: Dict[AgentType, AgentConfig] = {
    AgentType.DISCOVERY: AgentConfig(
        name="Discovery Agent",
        description="Zbiera preferencje i wymagania użytkownika",
        model=DEFAULT_MODEL_CONFIG["discovery"],
        tools=[
            "resolve_location",
            "get_available_locations",
            "get_districts_in_miejscowosc",
            "propose_search_preferences",
            "count_matching_parcels_quick",
        ],
        system_prompt_template="""Jesteś agentem zbierającym preferencje dotyczące działki budowlanej.

Twoje zadanie:
1. Wyjaśnij niejasności w wymaganiach użytkownika
2. Rozwiąż lokalizacje na konkretne gminy/dzielnice
3. Zaproponuj preferencje wyszukiwania
4. Sprawdź ile działek pasuje do kryteriów

WAŻNE:
- Bądź zwięzły i konkretny
- Nie zadawaj zbyt wielu pytań naraz
- Preferuj działanie nad dyskusją

{% if context.detected_hints %}
WYKRYTE WSKAZÓWKI do doprecyzowania:
{% for hint in context.detected_hints %}
- {{ hint }}
{% endfor %}
{% endif %}
""",
        context_mode="selective",
        max_tokens=1024,
    ),

    AgentType.SEARCH: AgentConfig(
        name="Search Agent",
        description="Wykonuje wyszukiwania działek",
        model=DEFAULT_MODEL_CONFIG["search"],
        tools=[
            "execute_search",
            "search_by_water_type",
            "search_similar_parcels",
            "search_by_criteria",
            "refine_search",
            "approve_search_preferences",
            "refine_search_preferences",
            "find_adjacent_parcels",
            "search_near_specific_poi",
            "find_similar_by_graph",
        ],
        system_prompt_template="""Jesteś agentem wyszukującym działki budowlane.

Twoje zadanie:
1. Wykonaj wyszukiwanie według zatwierdzonych preferencji
2. Zastosuj odpowiednie filtry (własność, zabudowa, rozmiar)
3. Użyj wyszukiwania hybrydowego (graf + wektor)
4. Zwróć uporządkowane wyniki

PREFERENCJE DO WYSZUKANIA:
{{ context.search_preferences | tojson }}

{% if context.search_feedback %}
FEEDBACK OD UŻYTKOWNIKA:
{{ context.search_feedback }}
{% endif %}

PAMIĘTAJ:
- Używaj ownership_type="prywatna" dla działek do kupienia
- Używaj build_status="niezabudowana" dla działek pod budowę
- Sortuj wyniki według dopasowania do preferencji
""",
        context_mode="selective",
        max_tokens=2048,
    ),

    AgentType.ANALYST: AgentConfig(
        name="Analyst Agent",
        description="Analizuje i porównuje działki",
        model=DEFAULT_MODEL_CONFIG["analyst"],
        tools=[
            "get_parcel_full_context",
            "get_parcel_neighborhood",
            "compare_parcels",
            "get_water_info",
            "get_zoning_info",
            "market_analysis",
            "get_district_prices",
            "estimate_parcel_value",
            "find_adjacent_parcels",
        ],
        system_prompt_template="""Jesteś analitykiem nieruchomości specjalizującym się w działkach budowlanych.

Twoje zadanie:
1. Przeprowadź głęboką analizę wskazanych działek
2. Porównaj działki pod kątem preferencji użytkownika
3. Zidentyfikuj zalety i wady każdej opcji
4. Oceń potencjał inwestycyjny

PRIORYTETY UŻYTKOWNIKA:
- Cisza: {{ context.priorities.quietness | default(0.5) | round(2) }}
- Natura: {{ context.priorities.nature | default(0.3) | round(2) }}
- Dostępność: {{ context.priorities.accessibility | default(0.2) | round(2) }}
{% if context.priorities.schools %}
- Szkoły: WAŻNE (ma dzieci)
{% endif %}

{% if context.parcels_to_analyze %}
DZIAŁKI DO ANALIZY:
{% for parcel_id in context.parcels_to_analyze %}
- {{ parcel_id }}
{% endfor %}
{% endif %}

ANALIZA POWINNA ZAWIERAĆ:
1. Podsumowanie lokalizacji i charakteru
2. Zgodność z preferencjami użytkownika
3. Potencjalne problemy lub ryzyka
4. Rekomendację (jeśli są podstawy)
""",
        context_mode="selective",
        max_tokens=4096,
    ),

    AgentType.NARRATOR: AgentConfig(
        name="Narrator Agent",
        description="Tworzy opisy i narracje o działkach",
        model=DEFAULT_MODEL_CONFIG["narrator"],
        tools=[
            "get_parcel_full_context",
            "get_parcel_neighborhood",
            "get_water_info",
        ],
        system_prompt_template="""Jesteś kreatywnym narratorem opisującym działki budowlane.

Twoje zadanie:
1. Stwórz angażujący opis działki lub okolicy
2. Podkreśl unikalne cechy i atmosferę miejsca
3. Pomóż użytkownikowi wyobrazić sobie życie w tej lokalizacji

STYL:
- Naturalny, konwersacyjny język
- Konkretne szczegóły zamiast ogólników
- Emocjonalne, ale oparte na faktach
- Unikaj przesady i marketingowego żargonu

{% if context.parcel_data %}
DANE DZIAŁKI:
{{ context.parcel_data | tojson }}
{% endif %}

OPIS POWINIEN:
- Być zwięzły (2-3 akapity)
- Zawierać konkretne odległości i fakty
- Malować obraz codziennego życia
""",
        context_mode="minimal",
        max_tokens=1024,
    ),

    AgentType.FEEDBACK: AgentConfig(
        name="Feedback Agent",
        description="Przetwarza feedback użytkownika",
        model=DEFAULT_MODEL_CONFIG["feedback"],
        tools=[
            "refine_search_preferences",
            "propose_filter_refinement",
        ],
        system_prompt_template="""Jesteś agentem przetwarzającym feedback użytkownika.

Twoje zadanie:
1. Zrozum co użytkownikowi się nie podoba
2. Zaproponuj modyfikacje kryteriów wyszukiwania
3. Wyjaśnij jak zmienisz wyszukiwanie

OBECNE KRYTERIA:
{{ context.current_preferences | tojson }}

FEEDBACK UŻYTKOWNIKA:
{{ context.feedback }}

{% if context.rejected_parcels %}
ODRZUCONE DZIAŁKI:
{% for parcel in context.rejected_parcels %}
- {{ parcel }}
{% endfor %}
{% endif %}

ZAPROPONUJ KONKRETNE ZMIANY:
- Jakie filtry dodać/usunąć
- Jakie priorytety zmienić
- Jak zawęzić/poszerzyć wyszukiwanie
""",
        context_mode="selective",
        max_tokens=1024,
    ),

    AgentType.LEAD: AgentConfig(
        name="Lead Agent",
        description="Zbiera dane kontaktowe",
        model=DEFAULT_MODEL_CONFIG["lead"],
        tools=[
            "capture_contact_info",
        ],
        system_prompt_template="""Jesteś agentem zbierającym dane kontaktowe zainteresowanych kupujących.

Twoje zadanie:
1. Zachęć użytkownika do pozostawienia kontaktu
2. Zbierz email i/lub telefon
3. Wyjaśnij korzyści (powiadomienia o nowych działkach, kontakt z ekspertem)

STYL:
- Nie bądź nachalny
- Podkreśl wartość dla użytkownika
- Szanuj prywatność

{% if context.favorited_parcels %}
POLUBIONE DZIAŁKI:
{% for parcel in context.favorited_parcels %}
- {{ parcel }}
{% endfor %}
{% endif %}

PROPOZYCJA WARTOŚCI:
- Powiadomimy Cię o nowych działkach w tej okolicy
- Możemy pomóc w kontakcie z właścicielem
- Ekspert może doradzić w kwestiach prawnych
""",
        context_mode="minimal",
        max_tokens=512,
    ),
}


# =============================================================================
# SUB-AGENT RESULT
# =============================================================================

class SubAgentResult(BaseModel):
    """Result from sub-agent execution."""
    agent_type: AgentType
    response: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    state_updates: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: int = 0
    tokens_used: int = 0
    model_used: str = ""


# =============================================================================
# SUB-AGENT SPAWNER
# =============================================================================

class SubAgentSpawner:
    """Spawns and manages specialized sub-agents.

    Responsible for:
    1. Creating sub-agents with appropriate configuration
    2. Building context for sub-agents (selective sharing)
    3. Executing sub-agents with tool calling
    4. Aggregating results back to orchestrator
    """

    def __init__(self, model_overrides: Optional[Dict[str, ModelType]] = None):
        """Initialize spawner.

        Args:
            model_overrides: Override default model assignments per agent type
        """
        self.model_overrides = model_overrides or {}

        if ANTHROPIC_AVAILABLE:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = None
            logger.warning("Anthropic client not available")

    def get_model_for_agent(self, agent_type: AgentType) -> str:
        """Get the model to use for an agent type."""
        if agent_type.value in self.model_overrides:
            return self.model_overrides[agent_type.value].value
        return AGENT_CONFIGS[agent_type].model.value

    async def spawn(
        self,
        agent_type: AgentType,
        state: AgentState,
        task_context: Dict[str, Any],
        user_message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Spawn a sub-agent and execute its task.

        Args:
            agent_type: Type of sub-agent to spawn
            state: Current agent state
            task_context: Additional context for the task
            user_message: Original user message

        Yields:
            Events during execution (tool_call, tool_result, message, etc.)
        """
        if not self._client:
            yield {"type": "error", "data": {"message": "Anthropic client not available"}}
            return

        config = AGENT_CONFIGS[agent_type]
        model = self.get_model_for_agent(agent_type)

        logger.info(f"Spawning {config.name} with model {model}")

        start_time = time.time()

        # Build system prompt
        system_prompt = self._build_system_prompt(config, state, task_context)

        # Build messages
        messages = self._build_messages(config, state, user_message, task_context)

        # Get tools
        tools = self._get_tools_for_agent(config)

        # Execute with tool loop
        result = SubAgentResult(
            agent_type=agent_type,
            model_used=model,
        )

        async for event in self._execute_with_tools(
            model, system_prompt, messages, tools, config, state, result
        ):
            yield event

        result.execution_time_ms = int((time.time() - start_time) * 1000)

        yield {
            "type": "sub_agent_complete",
            "data": {
                "agent_type": agent_type.value,
                "response": result.response,
                "tool_calls_count": len(result.tool_calls),
                "execution_time_ms": result.execution_time_ms,
                "model": model,
            }
        }

    def _build_system_prompt(
        self,
        config: AgentConfig,
        state: AgentState,
        task_context: Dict[str, Any]
    ) -> str:
        """Build system prompt for sub-agent."""
        from jinja2 import Template

        # Build context for template
        context = {
            "context": task_context,
            "user_profile": state.semantic.buyer_profile.model_dump(),
            "priorities": {
                "quietness": state.semantic.buyer_profile.priority_quietness,
                "nature": state.semantic.buyer_profile.priority_nature,
                "accessibility": state.semantic.buyer_profile.priority_accessibility,
                "schools": state.semantic.buyer_profile.priority_schools,
            },
            "search_preferences": state.working.search_state.approved_preferences,
            "favorited_parcels": state.working.search_state.favorited_parcels,
            "rejected_parcels": state.working.search_state.rejected_parcels,
            "detected_hints": state.working.temp_vars.get("detected_hints", []),
        }

        # Merge task_context
        context["context"].update({
            "search_preferences": state.working.search_state.approved_preferences or
                                  state.working.search_state.perceived_preferences,
            "current_preferences": state.working.search_state.approved_preferences,
            "feedback": state.working.search_state.search_feedback,
        })

        template = Template(config.system_prompt_template)
        return template.render(**context)

    def _build_messages(
        self,
        config: AgentConfig,
        state: AgentState,
        user_message: str,
        task_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Build messages for sub-agent based on context mode."""
        messages = []

        if config.context_mode == "full":
            # Include full conversation history
            messages = state.working.get_messages_for_llm()
        elif config.context_mode == "selective":
            # Include last few relevant messages
            recent = state.working.conversation_buffer[-5:]
            for msg in recent:
                messages.append({"role": msg.role, "content": msg.content})
        # "minimal" mode - no history

        # Always include current user message
        if not messages or messages[-1].get("content") != user_message:
            messages.append({"role": "user", "content": user_message})

        return messages

    def _get_tools_for_agent(self, config: AgentConfig) -> List[Dict[str, Any]]:
        """Get tool definitions for sub-agent."""
        from app.engine.tools_registry import AGENT_TOOLS

        return [
            tool for tool in AGENT_TOOLS
            if tool["name"] in config.tools
        ]

    async def _execute_with_tools(
        self,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: AgentConfig,
        state: AgentState,
        result: SubAgentResult,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute sub-agent with tool calling loop."""
        from app.engine.tool_executor import ToolExecutor

        tool_executor = ToolExecutor(state)
        iterations = 0

        while iterations < config.max_tool_iterations:
            iterations += 1

            # Call Claude
            try:
                response = await self._client.messages.create(
                    model=model,
                    max_tokens=config.max_tokens,
                    system=system_prompt,
                    tools=tools if tools else None,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"Sub-agent API error: {e}")
                yield {"type": "error", "data": {"message": str(e)}}
                return

            result.tokens_used += response.usage.input_tokens + response.usage.output_tokens

            # Process response
            assistant_content = []
            tool_calls = []
            text_response = ""

            for block in response.content:
                if block.type == "text":
                    text_response = block.text
                    assistant_content.append({"type": "text", "text": block.text})
                    yield {
                        "type": "message",
                        "data": {"content": block.text, "is_complete": True}
                    }
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            result.response = text_response

            # Add assistant response to messages
            messages.append({"role": "assistant", "content": assistant_content})

            # If no tool calls or stop reason is end_turn, we're done
            if not tool_calls or response.stop_reason == "end_turn":
                break

            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                yield {
                    "type": "tool_call",
                    "data": {"tool": tool_call["name"], "params": tool_call["input"]}
                }

                tool_result, state_updates = await tool_executor.execute(
                    tool_call["name"], tool_call["input"]
                )

                result.tool_calls.append(tool_call)
                result.tool_results.append(tool_result)
                if state_updates:
                    result.state_updates.update(state_updates)

                yield {
                    "type": "tool_result",
                    "data": {
                        "tool": tool_call["name"],
                        "result": tool_result,
                        "state_updates": list(state_updates.keys()) if state_updates else [],
                    }
                }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})


# =============================================================================
# AGENT ROUTER
# =============================================================================

class AgentRouter:
    """Routes requests to appropriate sub-agents based on intent.

    Used by the Root Orchestrator to decide which sub-agent(s) to spawn.
    """

    @staticmethod
    def route(state: AgentState, user_message: str) -> List[AgentType]:
        """Determine which sub-agent(s) to use.

        Args:
            state: Current agent state
            user_message: User's message

        Returns:
            List of agent types to spawn (in order)
        """
        message_lower = user_message.lower()
        phase = state.working.current_phase

        agents: List[AgentType] = []

        # Intent-based routing
        if any(word in message_lower for word in ["szukaj", "znajdź", "wyszukaj", "pokaż działki"]):
            if not state.working.search_state.preferences_approved:
                agents.append(AgentType.DISCOVERY)
            agents.append(AgentType.SEARCH)

        elif any(word in message_lower for word in ["porównaj", "analiza", "która lepsza", "oceń"]):
            agents.append(AgentType.ANALYST)

        elif any(word in message_lower for word in ["opowiedz", "opisz", "jak tam", "atmosfera"]):
            agents.append(AgentType.NARRATOR)

        elif any(word in message_lower for word in ["nie podoba", "za mało", "za dużo", "zmień", "inaczej"]):
            agents.append(AgentType.FEEDBACK)
            agents.append(AgentType.SEARCH)

        elif any(word in message_lower for word in ["kontakt", "email", "telefon", "zadzwoń"]):
            agents.append(AgentType.LEAD)

        # Phase-based fallback
        elif not agents:
            from app.memory import FunnelPhase

            if phase == FunnelPhase.DISCOVERY:
                agents.append(AgentType.DISCOVERY)
            elif phase == FunnelPhase.SEARCH:
                agents.append(AgentType.SEARCH)
            elif phase == FunnelPhase.EVALUATION:
                agents.append(AgentType.ANALYST)
            elif phase == FunnelPhase.LEAD_CAPTURE:
                agents.append(AgentType.LEAD)
            else:
                agents.append(AgentType.DISCOVERY)

        return agents


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_sub_agent_spawner(
    model_overrides: Optional[Dict[str, str]] = None
) -> SubAgentSpawner:
    """Factory function to create a sub-agent spawner.

    Args:
        model_overrides: Dict mapping agent type name to model name

    Returns:
        Configured SubAgentSpawner
    """
    overrides = {}
    if model_overrides:
        for agent_name, model_name in model_overrides.items():
            try:
                overrides[agent_name] = ModelType(model_name)
            except ValueError:
                logger.warning(f"Unknown model {model_name} for {agent_name}")

    return SubAgentSpawner(model_overrides=overrides)
