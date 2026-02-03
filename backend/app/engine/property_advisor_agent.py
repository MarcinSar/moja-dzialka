"""
Property Advisor Agent - Root Orchestrator with Multi-Agent Support.

The Root Orchestrator:
1. Decides whether to use skill-based execution or multi-agent delegation
2. Routes tasks to specialized sub-agents when appropriate
3. Synthesizes responses from multiple agents
4. Falls back to direct skill execution for simple tasks

Architecture:
  ROOT ORCHESTRATOR (this class)
  ├── Direct Skill Execution (legacy mode, default)
  └── Multi-Agent Delegation (for complex tasks)
      ├── Discovery Agent
      ├── Search Agent
      ├── Analyst Agent
      ├── Narrator Agent
      ├── Feedback Agent
      └── Lead Agent
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json
import time
import asyncio

from loguru import logger
import anthropic

from app.config import settings
from app.memory import AgentState
from app.memory.templates import render_main_prompt
from app.skills import get_skill, SkillDefinition, SkillContext, get_skill_loader, GateEvaluator
from app.engine.tools_registry import AGENT_TOOLS
from app.engine.tool_executor import ToolExecutor


# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2.0

# Retryable error types
RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class ExecutionMode:
    """Execution mode for the orchestrator."""
    SKILL = "skill"              # Direct skill execution (legacy)
    MULTI_AGENT = "multi_agent"  # Delegate to sub-agents


# Mapping from skill name to agent type (for frontend display)
SKILL_TO_AGENT_TYPE = {
    "discovery": "discovery",
    "search": "search",
    "evaluation": "analyst",
    "narrator": "narrator",
    "market_analysis": "analyst",
    "lead_capture": "lead",
}


def get_agent_type_for_skill(skill_name: str) -> str:
    """Get the agent type for a given skill name."""
    return SKILL_TO_AGENT_TYPE.get(skill_name, "orchestrator")


class PropertyAdvisorAgent:
    """Root Orchestrator with skill execution and multi-agent delegation.

    This agent can work in two modes:
    1. SKILL mode: Direct skill execution (legacy, default)
    2. MULTI_AGENT mode: Delegate to specialized sub-agents

    The mode is automatically selected based on task complexity,
    or can be forced via configuration.
    """

    # Default model for skill execution (cost-optimized)
    MODEL = "claude-haiku-4-5"
    # Model for orchestration decisions (needs better reasoning)
    ORCHESTRATOR_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 8

    def __init__(
        self,
        execution_mode: str = ExecutionMode.SKILL,
        use_orchestrator_model: bool = False,
        model_overrides: Optional[Dict[str, str]] = None,
    ):
        """Initialize the Root Orchestrator.

        Args:
            execution_mode: Default execution mode (SKILL or MULTI_AGENT)
            use_orchestrator_model: Use Sonnet for orchestration decisions
            model_overrides: Override models for sub-agents
        """
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._last_response: Optional[str] = None
        self.default_mode = execution_mode
        self.use_orchestrator_model = use_orchestrator_model

        # Lazy-load sub-agent spawner only when needed
        self._sub_agent_spawner = None
        self._model_overrides = model_overrides

    @property
    def sub_agent_spawner(self):
        """Lazy initialization of sub-agent spawner."""
        if self._sub_agent_spawner is None:
            from app.engine.sub_agents import create_sub_agent_spawner
            self._sub_agent_spawner = create_sub_agent_spawner(self._model_overrides)
        return self._sub_agent_spawner

    async def _retry_with_backoff(
        self,
        coro_func,
        *args,
        max_retries: int = MAX_RETRIES,
        **kwargs
    ):
        """Execute a coroutine with exponential backoff retry.

        Args:
            coro_func: Async function to execute
            *args: Arguments for the function
            max_retries: Maximum number of retries
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the coroutine

        Raises:
            Last exception if all retries failed
        """
        backoff = INITIAL_BACKOFF_SECONDS
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            except RETRYABLE_ERRORS as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
                else:
                    logger.error(f"API call failed after {max_retries + 1} attempts: {e}")
                    raise
            except Exception as e:
                # Non-retryable error
                logger.error(f"Non-retryable API error: {e}")
                raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    def _should_use_multi_agent(
        self,
        skill_name: str,
        user_message: str,
        state: AgentState,
    ) -> bool:
        """Decide whether to use multi-agent mode.

        Returns True if the task benefits from specialized sub-agents.
        """
        # For now, use explicit mode setting
        # Future: Add heuristics based on message complexity
        if self.default_mode == ExecutionMode.MULTI_AGENT:
            return True

        # Heuristic: Complex analysis tasks benefit from multi-agent
        message_lower = user_message.lower()

        # Multi-agent for comparisons and deep analysis
        if any(word in message_lower for word in ["porównaj", "analiza", "która lepsza", "oceń"]):
            return True

        # Multi-agent for combined tasks (search + analysis)
        if skill_name == "evaluation" and state.working.search_state.favorited_parcels:
            return True

        return False

    async def execute(
        self,
        skill_name: str,
        user_message: str,
        state: AgentState,
        force_mode: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a skill with streaming.

        Automatically decides between skill execution and multi-agent delegation.

        Args:
            skill_name: Name of skill to execute
            user_message: User's message
            state: Current agent state
            force_mode: Force specific execution mode (None = auto-decide)

        Yields:
            Event dicts for UI updates
        """
        # Decide execution mode
        mode = force_mode or (
            ExecutionMode.MULTI_AGENT
            if self._should_use_multi_agent(skill_name, user_message, state)
            else ExecutionMode.SKILL
        )

        if mode == ExecutionMode.MULTI_AGENT:
            async for event in self._execute_multi_agent(user_message, state):
                yield event
            return

        # Standard skill execution (SKILL mode)
        # 1. Load skill definition
        skill = get_skill(skill_name)
        logger.info(f"Executing skill: {skill_name} (mode: {mode})")

        # 2. Validate gates
        passed, gate_error = GateEvaluator.evaluate_gates(skill.gates, state)
        if not passed:
            logger.warning(f"Skill gate failed: {gate_error}")
            # Don't block — just log, gates are advisory in v3

        # 3. Get available tools from skill definition + registry
        loader = get_skill_loader()
        skill_tool_names = loader.get_tools_for_skill(skill_name, state)
        if skill_tool_names:
            tools = [t for t in AGENT_TOOLS if t["name"] in skill_tool_names]
            if not tools:
                tools = AGENT_TOOLS  # fallback if no matching tools found
        else:
            tools = AGENT_TOOLS

        # 4. Build system prompt
        context = self._build_context(user_message, state, skill)
        system_prompt = self._build_system_prompt(skill, context, state)

        # 5. Build messages
        messages = self._build_messages(user_message, state)

        # 6. Execute with tool loop
        self._last_response = None
        agent_type = get_agent_type_for_skill(skill_name)

        async for event in self._execute_with_tools(
            system_prompt, messages, tools, skill, state, agent_type
        ):
            yield event

    def _build_context(
        self,
        user_message: str,
        state: AgentState,
        skill: SkillDefinition,
    ) -> SkillContext:
        """Build context for skill execution."""
        state_dict = state.to_context_dict()

        return SkillContext(
            core=state_dict["core"],
            working=state_dict["working"],
            semantic=state_dict["semantic"],
            episodic=state_dict["episodic"],
            workflow=state_dict["workflow"],
            preferences=state_dict["preferences"],
            user_message=user_message,
            skill_name=skill.name,
        )

    def _build_system_prompt(
        self,
        skill: SkillDefinition,
        context: SkillContext,
        state: AgentState,
    ) -> str:
        """Build system prompt from templates.

        v3: Uses skill.instructions (markdown body from SKILL.md) instead of Jinja2 templates.
        """
        # Render main prompt (core context)
        main_prompt = render_main_prompt(state.to_context_dict())

        # Use skill instructions directly (from SKILL.md markdown body)
        skill_prompt = skill.instructions if skill.instructions else ""

        return f"{main_prompt}\n\n{skill_prompt}"

    def _build_messages(
        self,
        user_message: str,
        state: AgentState,
    ) -> List[Dict[str, Any]]:
        """Build messages for Claude API."""
        # Get conversation history from working memory
        messages = state.working.get_messages_for_llm()

        # Ensure last message is the current user message
        if not messages or messages[-1].get("content") != user_message:
            messages.append({"role": "user", "content": user_message})

        return messages

    async def _create_stream_with_retry(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ):
        """Create a streaming response with retry logic.

        Returns context manager for the stream.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES + 1):
            try:
                return self.client.messages.stream(
                    model=self.MODEL,
                    max_tokens=self.MAX_TOKENS,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
            except RETRYABLE_ERRORS as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Stream creation failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {e}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
                else:
                    logger.error(f"Stream creation failed after {MAX_RETRIES + 1} attempts: {e}")
                    raise

        # Should not reach here
        raise RuntimeError("Unexpected state in _create_stream_with_retry")

    async def _execute_with_tools(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        skill: SkillDefinition,
        state: AgentState,
        agent_type: str = "orchestrator",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute with tool calling loop and retry logic.

        Uses ToolExecutor to handle tool execution with proper V2 state management.
        State updates from tools are applied directly to the state object.

        Args:
            agent_type: Type of agent executing (for frontend display)
        """
        # Create tool executor with current state
        tool_executor = ToolExecutor(state)
        iterations = 0

        while iterations < self.MAX_TOOL_ITERATIONS:
            iterations += 1

            # Stream response from Claude (with retry)
            assistant_content = []
            tool_calls = []
            current_text = ""
            current_tool_input = ""
            current_tool_id = None
            current_tool_name = None

            try:
                stream_context = await self._create_stream_with_retry(
                    system_prompt, messages, tools
                )
            except Exception as e:
                yield {
                    "type": "error",
                    "data": {"message": f"API error after retries: {str(e)}"}
                }
                return

            async with stream_context as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            current_text = ""
                        elif event.content_block.type == "tool_use":
                            current_tool_id = event.content_block.id
                            current_tool_name = event.content_block.name
                            current_tool_input = ""

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            delta_text = event.delta.text
                            current_text += delta_text
                            yield {
                                "type": "message",
                                "data": {"content": delta_text, "is_complete": False}
                            }
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_input += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_text:
                            assistant_content.append({
                                "type": "text",
                                "text": current_text,
                            })
                            self._last_response = current_text
                            yield {
                                "type": "message",
                                "data": {"content": "", "is_complete": True}
                            }
                            current_text = ""
                        elif current_tool_id:
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

            # Add assistant response to messages
            messages.append({
                "role": "assistant",
                "content": assistant_content,
            })

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Execute tool calls using ToolExecutor
            tool_results = []
            for tool_call in tool_calls:
                yield {
                    "type": "tool_call",
                    "data": {
                        "tool": tool_call["name"],
                        "params": tool_call["input"],
                        "agent_type": agent_type,
                    }
                }

                start_time = time.time()
                result, state_updates = await tool_executor.execute(
                    tool_call["name"], tool_call["input"]
                )
                duration_ms = int((time.time() - start_time) * 1000)

                # Apply state updates from tool execution
                self._apply_state_updates(state, state_updates)

                yield {
                    "type": "tool_result",
                    "data": {
                        "tool": tool_call["name"],
                        "duration_ms": duration_ms,
                        "result": result,
                        "result_preview": self._summarize_result(result),
                        "state_updates": list(state_updates.keys()) if state_updates else [],
                        "agent_type": agent_type,
                    }
                }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # Add tool results to messages
            messages.append({
                "role": "user",
                "content": tool_results,
            })

            yield {
                "type": "thinking",
                "data": {"message": "Przetwarzam wyniki...", "agent_type": agent_type}
            }

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Create brief summary of tool result."""
        if "error" in result:
            return f"Błąd: {result['error']}"

        if "status" in result:
            status = result["status"]
            if status == "proposed":
                return "Preferencje zaproponowane"
            elif status == "approved":
                return "Preferencje zatwierdzone"
            elif status in ("modified", "modified_and_approved"):
                return f"Zmieniono: {result.get('field')}"

        if "count" in result:
            count = result["count"]
            if "parcels" in result:
                return f"Znaleziono {count} działek"
            return f"Znaleziono {count} wyników"

        if "parcel" in result:
            p = result["parcel"]
            return f"Działka {p.get('id_dzialki', 'N/A')}"

        if "geojson" in result:
            return f"Mapa z {result.get('parcel_count', 0)} działkami"

        if "price_per_m2_min" in result:
            return f"Ceny: {result['price_per_m2_min']}-{result['price_per_m2_max']} zł/m²"

        if "estimated_value_min" in result:
            return f"Wartość: {result.get('estimated_range', 'N/A')}"

        return "Dane pobrane"

    def _apply_state_updates(
        self,
        state: AgentState,
        updates: Dict[str, Any]
    ) -> None:
        """Apply state updates from tool execution.

        Handles nested updates like 'search_state.perceived_preferences'.
        """
        if not updates:
            return

        for key, value in updates.items():
            if "." in key:
                # Handle nested updates (e.g., "search_state.perceived_preferences")
                parts = key.split(".")
                if parts[0] == "search_state" and len(parts) == 2:
                    search_state = state.working.search_state
                    attr = parts[1]
                    if hasattr(search_state, attr):
                        setattr(search_state, attr, value)
                        logger.debug(f"Updated search_state.{attr}")
            else:
                # Direct attribute update
                if hasattr(state, key):
                    setattr(state, key, value)
                    logger.debug(f"Updated state.{key}")

    def get_last_response(self) -> Optional[str]:
        """Get the last text response from the agent."""
        return self._last_response

    # =========================================================================
    # MULTI-AGENT EXECUTION
    # =========================================================================

    async def _execute_multi_agent(
        self,
        user_message: str,
        state: AgentState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute using multi-agent delegation.

        Routes the task to appropriate sub-agents and synthesizes results.

        Args:
            user_message: User's message
            state: Current agent state

        Yields:
            Events during execution
        """
        from app.engine.sub_agents import AgentRouter, AgentType

        # 1. Determine which sub-agents to use
        agent_types = AgentRouter.route(state, user_message)

        logger.info(f"Multi-agent routing: {[a.value for a in agent_types]}")

        yield {
            "type": "orchestrator_routing",
            "data": {
                "agents": [a.value for a in agent_types],
                "message": f"Deleguję zadanie do: {', '.join(a.value for a in agent_types)}"
            }
        }

        # 2. Execute sub-agents sequentially (could be parallelized for independent agents)
        all_responses = []
        all_state_updates = {}

        for agent_type in agent_types:
            yield {
                "type": "sub_agent_start",
                "data": {"agent": agent_type.value}
            }

            # Build task context for sub-agent
            task_context = self._build_task_context(agent_type, state, user_message)

            # Spawn and execute sub-agent
            async for event in self.sub_agent_spawner.spawn(
                agent_type, state, task_context, user_message
            ):
                # Forward events from sub-agent
                yield event

                # Collect state updates
                if event["type"] == "sub_agent_complete":
                    response = event["data"].get("response", "")
                    if response:
                        all_responses.append({
                            "agent": agent_type.value,
                            "response": response,
                        })

                # Apply state updates as they come
                if event["type"] == "tool_result":
                    state_updates = event["data"].get("state_updates", [])
                    for key in state_updates:
                        all_state_updates[key] = True

        # 3. Synthesize final response if multiple agents were used
        if len(all_responses) > 1:
            final_response = await self._synthesize_responses(all_responses, state)
            self._last_response = final_response

            yield {
                "type": "message",
                "data": {"content": final_response, "is_complete": True}
            }
        elif all_responses:
            self._last_response = all_responses[0]["response"]
        else:
            self._last_response = None

        yield {
            "type": "multi_agent_complete",
            "data": {
                "agents_used": [a.value for a in agent_types],
                "state_updates": list(all_state_updates.keys()),
            }
        }

    def _build_task_context(
        self,
        agent_type,
        state: AgentState,
        user_message: str,
    ) -> Dict[str, Any]:
        """Build task context for a sub-agent.

        Args:
            agent_type: Type of sub-agent
            state: Current agent state
            user_message: User's message

        Returns:
            Context dict for the sub-agent
        """
        from app.engine.sub_agents import AgentType

        context = {
            "user_message": user_message,
            "current_phase": state.working.current_phase.value,
        }

        if agent_type == AgentType.DISCOVERY:
            context["detected_hints"] = state.working.temp_vars.get("detected_hints", [])
            context["known_location"] = state.workflow.funnel_progress.known_location

        elif agent_type == AgentType.SEARCH:
            context["search_preferences"] = (
                state.working.search_state.approved_preferences or
                state.working.search_state.perceived_preferences
            )
            context["search_feedback"] = state.working.search_state.search_feedback
            context["search_iteration"] = state.working.search_state.search_iteration

        elif agent_type == AgentType.ANALYST:
            context["parcels_to_analyze"] = state.working.search_state.favorited_parcels
            context["current_results"] = state.working.search_state.current_results[:5]
            context["priorities"] = {
                "quietness": state.semantic.buyer_profile.priority_quietness,
                "nature": state.semantic.buyer_profile.priority_nature,
                "accessibility": state.semantic.buyer_profile.priority_accessibility,
                "schools": state.semantic.buyer_profile.priority_schools,
            }

        elif agent_type == AgentType.NARRATOR:
            # Get first parcel from results or favorites
            if state.working.search_state.favorited_parcels:
                context["parcel_id"] = state.working.search_state.favorited_parcels[0]
            elif state.working.search_state.current_results:
                context["parcel_id"] = state.working.search_state.current_results[0].get("id_dzialki")

        elif agent_type == AgentType.FEEDBACK:
            context["current_preferences"] = state.working.search_state.approved_preferences
            context["feedback"] = state.working.search_state.search_feedback or user_message
            context["rejected_parcels"] = state.working.search_state.rejected_parcels

        elif agent_type == AgentType.LEAD:
            context["favorited_parcels"] = state.working.search_state.favorited_parcels
            context["engagement_score"] = state.semantic.engagement_score

        return context

    async def _synthesize_responses(
        self,
        responses: List[Dict[str, Any]],
        state: AgentState,
    ) -> str:
        """Synthesize multiple sub-agent responses into a coherent final response.

        Args:
            responses: List of {agent, response} dicts
            state: Current agent state

        Returns:
            Synthesized response string
        """
        # For simple cases, just concatenate with attribution
        if len(responses) <= 2:
            parts = []
            for r in responses:
                if r["response"].strip():
                    parts.append(r["response"])
            return "\n\n".join(parts)

        # For complex cases, use LLM to synthesize
        synthesis_prompt = """Połącz poniższe odpowiedzi od różnych specjalistów w jedną spójną odpowiedź dla użytkownika.

ODPOWIEDZI:
"""
        for r in responses:
            synthesis_prompt += f"\n[{r['agent']}]: {r['response']}\n"

        synthesis_prompt += """
WYMAGANIA:
- Usuń powtórzenia
- Zachowaj najważniejsze informacje
- Stwórz naturalny flow
- Odpowiedź powinna brzmieć jak od jednej osoby
- Nie wspominaj o "specjalistach" ani "agentach"
"""

        try:
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": synthesis_prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback to simple concatenation
            return "\n\n".join(r["response"] for r in responses if r["response"].strip())
