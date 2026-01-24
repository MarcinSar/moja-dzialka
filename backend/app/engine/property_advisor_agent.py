"""
Property Advisor Agent - Skill Executor.

The executor:
1. Loads the appropriate skill
2. Renders the prompt with Jinja2 templates
3. Calls Claude API (with tool calling)
4. Returns structured output
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
from app.skills import get_skill, Skill, SkillContext
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


class PropertyAdvisorAgent:
    """Skill executor using Claude with tool calling.

    This agent executes skills by:
    1. Loading the skill and its template
    2. Building context from agent state
    3. Calling Claude API with appropriate tools
    4. Processing the response
    """

    MODEL = "claude-haiku-4-5"
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 8

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._last_response: Optional[str] = None

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

    async def execute(
        self,
        skill_name: str,
        user_message: str,
        state: AgentState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a skill with streaming.

        Args:
            skill_name: Name of skill to execute
            user_message: User's message
            state: Current agent state

        Yields:
            Event dicts for UI updates
        """
        # 1. Load skill
        skill = get_skill(skill_name)
        logger.info(f"Executing skill: {skill_name}")

        # 2. Build context
        context = self._build_context(user_message, state, skill)

        # 3. Validate context
        error = skill.validate_context(context)
        if error:
            yield {"type": "error", "data": {"message": error}}
            return

        # 4. Get available tools
        tools = skill.get_tools()
        if not tools:
            # Use all agent tools if skill doesn't specify
            tools = AGENT_TOOLS

        # 5. Render system prompt
        system_prompt = self._build_system_prompt(skill, context, state)

        # 6. Build messages
        messages = self._build_messages(user_message, state)

        # 7. Execute with tool loop
        self._last_response = None

        async for event in self._execute_with_tools(
            system_prompt, messages, tools, skill, state
        ):
            yield event

    def _build_context(
        self,
        user_message: str,
        state: AgentState,
        skill: Skill,
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
        skill: Skill,
        context: SkillContext,
        state: AgentState,
    ) -> str:
        """Build system prompt from templates."""
        # Render main prompt (core context)
        main_prompt = render_main_prompt(state.to_context_dict())

        # Render skill-specific prompt
        skill_prompt = skill.prepare_prompt(context)

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
        skill: Skill,
        state: AgentState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute with tool calling loop and retry logic.

        Uses ToolExecutor to handle tool execution with proper V2 state management.
        State updates from tools are applied directly to the state object.
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
                    "data": {"tool": tool_call["name"], "params": tool_call["input"]}
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
                "data": {"message": "Przetwarzam wyniki..."}
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
