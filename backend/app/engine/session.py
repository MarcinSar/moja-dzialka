"""
Session - Manages conversation state, compaction, and notepad injection.

Replaces the 7-layer memory system with a pragmatic 4-layer approach:
- Layer 1: Static system prompt (compiled once)
- Layer 2: Session state (messages + notepad)
- Layer 3: User profile (cross-session, Redis/PG)
- Layer 4: Knowledge base (Neo4j + PostGIS, accessed via tools)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

from loguru import logger

from app.engine.notepad import Notepad


@dataclass
class Message:
    """A single conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


@dataclass
class Session:
    """Session state for a single user conversation.

    Contains:
    - Conversation messages (with compaction)
    - Notepad (source of truth for session state)
    - Session metadata
    """
    session_id: str
    user_id: str
    notepad: Notepad = field(default_factory=Notepad)
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Compaction state
    compaction_summary: Optional[str] = None
    compaction_count: int = 0

    # Constants
    MAX_MESSAGES_BEFORE_COMPACT: int = 20
    KEEP_RECENT_MESSAGES: int = 8  # Keep last 4 exchanges (8 messages)

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.messages.append(Message(role="user", content=content))
        self.updated_at = time.time()

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add an assistant message with optional tool usage."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
        ))
        self.updated_at = time.time()

    def should_compact(self) -> bool:
        """Check if conversation should be compacted."""
        return len(self.messages) >= self.MAX_MESSAGES_BEFORE_COMPACT

    def compact(self) -> None:
        """Compact older messages into summary.

        Rule-based (no LLM call): Uses notepad as source of truth.
        Keeps the last KEEP_RECENT_MESSAGES messages intact.
        Older messages are summarized and removed.
        """
        if len(self.messages) < self.MAX_MESSAGES_BEFORE_COMPACT:
            return

        old_messages = self.messages[:-self.KEEP_RECENT_MESSAGES]
        recent_messages = self.messages[-self.KEEP_RECENT_MESSAGES:]

        # Build summary from notepad state (source of truth)
        summary_parts = ["[Podsumowanie wcześniejszej rozmowy]"]

        if self.notepad.user_goal:
            summary_parts.append(f"Cel: {self.notepad.user_goal}")

        if self.notepad.location and self.notepad.location.validated:
            loc = self.notepad.location
            loc_str = loc.dzielnica or loc.gmina or loc.miejscowosc or "nieznana"
            summary_parts.append(f"Lokalizacja: {loc_str} ({loc.gmina})")

        if self.notepad.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in self.notepad.preferences.items() if v)
            if prefs:
                summary_parts.append(f"Preferencje: {prefs}")

        if self.notepad.search_results:
            sr = self.notepad.search_results
            summary_parts.append(f"Wyniki: {sr.total_count} działek znalezionych")

        if self.notepad.favorites:
            summary_parts.append(f"Ulubione: {', '.join(self.notepad.favorites[:5])}")

        if self.notepad.user_facts:
            facts = ", ".join(f"{k}: {v}" for k, v in self.notepad.user_facts.items())
            summary_parts.append(f"Fakty: {facts}")

        if self.notepad.notes:
            summary_parts.append(f"Notatki: {'; '.join(self.notepad.notes[-3:])}")

        # Extract key exchanges from old messages
        key_exchanges = []
        for msg in old_messages:
            if msg.role == "user" and len(msg.content) > 20:
                key_exchanges.append(f"User: {msg.content[:100]}")
        if key_exchanges:
            summary_parts.append(f"Kluczowe pytania: {'; '.join(key_exchanges[-3:])}")

        self.compaction_summary = "\n".join(summary_parts)
        self.compaction_count += 1
        self.messages = recent_messages

        logger.info(
            f"Session {self.session_id}: compacted {len(old_messages)} messages "
            f"(kept {len(recent_messages)}, compaction #{self.compaction_count})"
        )

    def build_messages_for_api(self, user_message: str) -> List[Dict[str, Any]]:
        """Build messages array for Claude API call.

        Injects notepad at the end of the user message.
        Includes compaction summary if available.
        """
        api_messages = []

        # Include compaction summary as first message if available
        if self.compaction_summary:
            api_messages.append({
                "role": "user",
                "content": self.compaction_summary,
            })
            api_messages.append({
                "role": "assistant",
                "content": "Rozumiem, kontynuujmy rozmowę. Mam w pamięci Twoje preferencje i dotychczasowe wyniki.",
            })

        # Include existing messages
        for msg in self.messages:
            api_msg = {"role": msg.role, "content": msg.content}

            # For assistant messages with tool calls, include tool_use blocks
            # AND a synthetic tool_result user message right after
            if msg.role == "assistant" and msg.tool_calls:
                # Claude API format: content can be a list with text + tool_use blocks
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": tc.get("input", {}),
                    })
                if content_blocks:
                    api_msg["content"] = content_blocks

                api_messages.append(api_msg)

                # Every tool_use MUST be followed by tool_result in next user message
                tool_result_blocks = []
                results_by_name = {}
                if msg.tool_results:
                    for tr in msg.tool_results:
                        results_by_name[tr.get("name", "")] = tr.get("result", {})

                for tc in msg.tool_calls:
                    tc_name = tc.get("name", "")
                    tc_id = tc.get("id", "")
                    result = results_by_name.get(tc_name, {"status": "ok"})
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:5000],
                    })

                if tool_result_blocks:
                    api_messages.append({"role": "user", "content": tool_result_blocks})
            else:
                api_messages.append(api_msg)

        # Add current user message with notepad injection
        notepad_injection = self.notepad.to_injection()
        api_messages.append({
            "role": "user",
            "content": f"{user_message}\n\n{notepad_injection}",
        })

        return api_messages

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session for persistence."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "notepad": self.notepad.to_dict(),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "tool_calls": m.tool_calls,
                    "tool_results": m.tool_results,
                }
                for m in self.messages
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "compaction_summary": self.compaction_summary,
            "compaction_count": self.compaction_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Session:
        """Deserialize session from persistence."""
        session = cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
        )
        session.notepad = Notepad.from_dict(data.get("notepad", {}))
        session.messages = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=m.get("timestamp", 0),
                tool_calls=m.get("tool_calls"),
                tool_results=m.get("tool_results"),
            )
            for m in data.get("messages", [])
        ]
        session.created_at = data.get("created_at", time.time())
        session.updated_at = data.get("updated_at", time.time())
        session.compaction_summary = data.get("compaction_summary")
        session.compaction_count = data.get("compaction_count", 0)
        return session
