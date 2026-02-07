"""
Agent - Single agent loop with streaming and notepad-driven flow.

Replaces the 3-layer orchestration (coordinator + advisor + sub_agents)
with a single agent that uses tools directly.

Architecture:
    USER MESSAGE
        │
        ▼
    Session.build_messages_for_api(msg)  ← notepad injected
        │
        ▼
    Claude API (Sonnet 4.5) with 16 tools
        │
        ├─ text → stream to frontend
        ├─ tool_use → check gates → execute → return result
        └─ stop → save session
"""

from __future__ import annotations

import json
import time
import uuid
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator

from loguru import logger
import anthropic

from app.config import settings
from app.engine.session import Session
from app.engine.notepad import Notepad, LocationState, SearchResults
from app.engine.prompt_compiler import get_system_prompt
from app.engine.tool_definitions import get_tool_definitions
from app.engine.tool_gates import check_gates
from app.engine.tool_executor_v4 import ToolExecutorV4


# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0

RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class Agent:
    """Single agent with tool calling and streaming.

    Usage:
        agent = Agent()
        session = Session(session_id="...", user_id="...")

        async for event in agent.run(session, "Szukam działki w Osowej"):
            # event: {"type": "message"|"tool_call"|"tool_result"|"done", "data": {...}}
            pass
    """

    MODEL = "claude-sonnet-4-5-20250929"
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 10

    def __init__(self, model: Optional[str] = None):
        self.model = model or self.MODEL
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.system_prompt = get_system_prompt()
        self.tools = get_tool_definitions()

    async def run(
        self,
        session: Session,
        user_message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the agent loop for a single user message.

        Yields events:
        - {"type": "thinking", "data": {"text": "..."}}
        - {"type": "message", "data": {"text": "...", "delta": true}}
        - {"type": "tool_call", "data": {"name": "...", "input": {...}, "id": "..."}}
        - {"type": "tool_result", "data": {"name": "...", "result": {...}, "duration_ms": N}}
        - {"type": "done", "data": {"session_id": "..."}}
        - {"type": "error", "data": {"message": "..."}}
        """
        # Check compaction before processing
        if session.should_compact():
            session.compact()

        # Build messages for API
        api_messages = session.build_messages_for_api(user_message)

        # Create tool executor for this turn
        executor = ToolExecutorV4(session.notepad, session.session_id)

        # Tool loop: agent may call tools multiple times
        collected_text = ""
        collected_tool_calls = []
        collected_tool_results = []
        iteration = 0

        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1

            # Call Claude API with retry
            try:
                response = await self._call_api_with_retry(api_messages)
            except Exception as e:
                yield {"type": "error", "data": {"message": str(e)}}
                return

            # Process response
            text_parts = []
            tool_uses = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    yield {"type": "message", "data": {"text": block.text, "delta": False}}
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    yield {
                        "type": "tool_call",
                        "data": {
                            "name": block.name,
                            "input": block.input,
                            "id": block.id,
                        },
                    }

            turn_text = "".join(text_parts)
            collected_text += turn_text

            # If no tool calls, we're done
            if not tool_uses:
                break

            # Process tool calls
            # Build assistant message with tool uses
            assistant_content = []
            if turn_text:
                assistant_content.append({"type": "text", "text": turn_text})
            for tu in tool_uses:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu.id,
                    "name": tu.name,
                    "input": tu.input,
                })

            api_messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and build tool_result messages
            tool_result_blocks = []
            for tu in tool_uses:
                start_time = time.time()

                # Check gates first
                gate_error = check_gates(tu.name, session.notepad, tu.input)
                if gate_error:
                    result = gate_error
                    logger.info(f"Gate blocked {tu.name}: {gate_error['error']}")
                else:
                    # Execute tool
                    result, notepad_updates = await executor.execute(tu.name, tu.input)

                    # Apply notepad updates
                    self._apply_notepad_updates(session.notepad, notepad_updates)

                duration_ms = int((time.time() - start_time) * 1000)

                yield {
                    "type": "tool_result",
                    "data": {
                        "name": tu.name,
                        "result": result,
                        "duration_ms": duration_ms,
                    },
                }

                collected_tool_calls.append({"name": tu.name, "input": tu.input, "id": tu.id})
                collected_tool_results.append({"name": tu.name, "result": result})

                # Build tool_result block for API
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:10000],
                })

            # Add tool results to messages for next iteration
            api_messages.append({"role": "user", "content": tool_result_blocks})

            # If stop_reason is end_turn (not tool_use), break
            if response.stop_reason != "tool_use":
                break

        # Save messages to session
        session.add_user_message(user_message)
        session.add_assistant_message(
            content=collected_text,
            tool_calls=collected_tool_calls if collected_tool_calls else None,
            tool_results=collected_tool_results if collected_tool_results else None,
        )

        yield {"type": "done", "data": {"session_id": session.session_id}}

    def _apply_notepad_updates(self, notepad: Notepad, updates: Dict[str, Any]) -> None:
        """Apply updates from tool execution to notepad."""
        if not updates:
            return

        if "location" in updates:
            loc = updates["location"]
            if isinstance(loc, LocationState):
                notepad.update_backend_location(loc)
            elif isinstance(loc, dict):
                notepad.update_backend_location(LocationState(**loc))

        if "search_results" in updates:
            sr = updates["search_results"]
            if isinstance(sr, SearchResults):
                notepad.update_backend_search(sr)
            elif isinstance(sr, dict):
                notepad.update_backend_search(SearchResults(**sr))

        if "add_favorite" in updates:
            notepad.add_favorite(updates["add_favorite"])

        if "user_fact" in updates:
            for key, value in updates["user_fact"].items():
                notepad.set_user_fact(key, value)

    async def _call_api_with_retry(
        self,
        messages: List[Dict[str, Any]],
    ) -> anthropic.types.Message:
        """Call Claude API with exponential backoff retry."""
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.MAX_TOKENS,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages,
                )
                return response

            except RETRYABLE_ERRORS as e:
                if attempt == MAX_RETRIES:
                    logger.error(f"API call failed after {MAX_RETRIES} retries: {e}")
                    raise

                logger.warning(f"API call attempt {attempt + 1} failed: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

            except anthropic.APIError as e:
                logger.error(f"Non-retryable API error: {e}")
                raise

        raise RuntimeError("Unexpected: retry loop exhausted without returning or raising")

    async def run_streaming(
        self,
        session: Session,
        user_message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run agent with true streaming (token-by-token).

        Similar to run() but uses the streaming API for text generation,
        yielding individual text deltas as they arrive.
        """
        if session.should_compact():
            session.compact()

        api_messages = session.build_messages_for_api(user_message)
        executor = ToolExecutorV4(session.notepad, session.session_id)

        collected_text = ""
        collected_tool_calls = []
        collected_tool_results = []
        iteration = 0

        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1

            # Streaming API call
            try:
                stream = self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.MAX_TOKENS,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=api_messages,
                )
            except Exception as e:
                yield {"type": "error", "data": {"message": str(e)}}
                return

            turn_text = ""
            tool_uses = []

            try:
                async with stream as s:
                    async for event in s:
                        if event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    tool_uses.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input_json": "",
                                    })
                                    yield {
                                        "type": "tool_call",
                                        "data": {
                                            "name": event.content_block.name,
                                            "id": event.content_block.id,
                                            "status": "started",
                                        },
                                    }
                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                turn_text += event.delta.text
                                yield {
                                    "type": "message",
                                    "data": {"text": event.delta.text, "delta": True},
                                }
                            elif hasattr(event.delta, "partial_json"):
                                if tool_uses:
                                    tool_uses[-1]["input_json"] += event.delta.partial_json

                    # Get the final message
                    response = await s.get_final_message()
            except RETRYABLE_ERRORS as e:
                logger.warning(f"Streaming error: {e}")
                yield {"type": "error", "data": {"message": str(e)}}
                return

            collected_text += turn_text

            # If no tool calls, we're done
            if not tool_uses:
                break

            # Parse tool inputs and execute
            assistant_content = []
            if turn_text:
                assistant_content.append({"type": "text", "text": turn_text})

            parsed_tool_uses = []
            for tu in tool_uses:
                try:
                    input_data = json.loads(tu["input_json"]) if tu["input_json"] else {}
                except json.JSONDecodeError:
                    input_data = {}

                assistant_content.append({
                    "type": "tool_use",
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": input_data,
                })
                parsed_tool_uses.append({
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": input_data,
                })

            api_messages.append({"role": "assistant", "content": assistant_content})

            # Execute tools
            tool_result_blocks = []
            for tu in parsed_tool_uses:
                start_time = time.time()

                gate_error = check_gates(tu["name"], session.notepad, tu["input"])
                if gate_error:
                    result = gate_error
                else:
                    result, notepad_updates = await executor.execute(tu["name"], tu["input"])
                    self._apply_notepad_updates(session.notepad, notepad_updates)

                duration_ms = int((time.time() - start_time) * 1000)

                yield {
                    "type": "tool_result",
                    "data": {
                        "name": tu["name"],
                        "result": result,
                        "duration_ms": duration_ms,
                    },
                }

                collected_tool_calls.append(tu)
                collected_tool_results.append({"name": tu["name"], "result": result})

                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:10000],
                })

            api_messages.append({"role": "user", "content": tool_result_blocks})

            if response.stop_reason != "tool_use":
                break

        # Save to session
        session.add_user_message(user_message)
        session.add_assistant_message(
            content=collected_text,
            tool_calls=collected_tool_calls if collected_tool_calls else None,
            tool_results=collected_tool_results if collected_tool_results else None,
        )

        yield {"type": "done", "data": {"session_id": session.session_id}}
