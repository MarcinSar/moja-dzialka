"""
Memory Flush Manager - Intelligent fact extraction before context compaction.

Uses Haiku model for intelligent extraction of important facts from
working memory before the context is compacted or lost.

This implements the "silent agent turn" pattern from OpenClaw:
When token count exceeds threshold, extract and persist important facts
before compacting the conversation buffer.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from loguru import logger
from pydantic import BaseModel, Field

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic not installed - LLM-based flush unavailable")

from app.config import settings
from app.memory.schemas import AgentState, BuyerProfile
from app.memory.workspace import get_workspace_manager, UserWorkspace


# Flush configuration
FLUSH_TOKEN_THRESHOLD = 0.80  # Flush when context is 80% full
MAX_CONTEXT_TOKENS = 100_000  # Approximate max tokens (Claude context)
HAIKU_MODEL = "claude-haiku-4-5"


class ExtractedFacts(BaseModel):
    """Facts extracted from a conversation segment."""

    # User profile updates
    profile_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Updates to apply to BuyerProfile"
    )

    # Important facts to remember
    facts: List[str] = Field(
        default_factory=list,
        description="Key facts about the user (e.g., 'has two children', 'works in Gdynia')"
    )

    # Search preferences learned
    search_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Learned search preferences"
    )

    # Intent signals detected
    intent_signals: List[str] = Field(
        default_factory=list,
        description="Purchase intent signals (e.g., 'asked_about_mortgage', 'urgent_timeline')"
    )

    # Confidence score for this extraction
    confidence: float = Field(
        default=0.0,
        description="Confidence in the extraction (0-1)"
    )


class MemoryFlushManager:
    """Manages intelligent memory flush before context compaction.

    Two modes:
    1. LLM-powered (Haiku) - intelligent extraction, ~$0.01 per flush
    2. Rule-based - pattern matching, free but less accurate

    The hybrid approach uses rules for simple facts and LLM for complex ones.
    """

    def __init__(self, use_llm: bool = True):
        """Initialize flush manager.

        Args:
            use_llm: Whether to use LLM for extraction (more accurate but costs $)
        """
        self.use_llm = use_llm and ANTHROPIC_AVAILABLE
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self.workspace_manager = get_workspace_manager()

        if self.use_llm:
            try:
                self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Anthropic client: {e}")
                self.use_llm = False

    def should_flush(self, state: AgentState) -> bool:
        """Check if memory should be flushed based on context size.

        Uses a simple heuristic: ~4 chars per token on average.
        """
        # Estimate total context size
        total_chars = 0

        # Conversation buffer
        for msg in state.working.conversation_buffer:
            total_chars += len(msg.content)

        # Search results (can be large)
        if state.working.search_state.current_results:
            total_chars += len(json.dumps(state.working.search_state.current_results))

        # Estimate tokens (rough: 4 chars per token)
        estimated_tokens = total_chars / 4

        # Check threshold
        return estimated_tokens > (MAX_CONTEXT_TOKENS * FLUSH_TOKEN_THRESHOLD)

    async def flush(self, state: AgentState) -> Tuple[ExtractedFacts, bool]:
        """Perform memory flush - extract facts and persist.

        Returns:
            Tuple of (extracted facts, whether flush was successful)
        """
        logger.info(f"Starting memory flush for user {state.user_id}")

        # Get user workspace
        workspace = self.workspace_manager.get_user_workspace(state.user_id)

        # Extract facts (LLM or rules)
        if self.use_llm and self._client:
            facts = await self._extract_with_llm(state)
        else:
            facts = self._extract_with_rules(state)

        if not facts.facts and not facts.profile_updates:
            logger.debug("No facts extracted during flush")
            return facts, True

        # Persist to workspace
        try:
            # Update profile if we have updates
            if facts.profile_updates:
                current_profile = workspace.load_profile() or BuyerProfile()
                updated_profile = self._apply_profile_updates(current_profile, facts.profile_updates)
                workspace.save_profile(updated_profile)

            # Append facts to daily memory file
            if facts.facts:
                workspace.append_memory_extract(facts.facts, state.session_id)

            # Save search patterns if we have preferences
            if facts.search_preferences:
                workspace.save_search_pattern(facts.search_preferences)

            logger.info(f"Flushed {len(facts.facts)} facts, {len(facts.profile_updates)} profile updates")
            return facts, True

        except Exception as e:
            logger.error(f"Failed to persist flush results: {e}")
            return facts, False

    async def _extract_with_llm(self, state: AgentState) -> ExtractedFacts:
        """Use Haiku to intelligently extract facts from conversation."""

        # Build conversation summary for extraction
        messages_text = "\n".join([
            f"{'User' if m.role == 'user' else 'Agent'}: {m.content}"
            for m in state.working.conversation_buffer[-20:]  # Last 20 messages
        ])

        # Current profile for context
        profile_summary = json.dumps(state.semantic.buyer_profile.model_dump(exclude_none=True), ensure_ascii=False)

        extraction_prompt = f"""Przeanalizuj poniższą rozmowę i wyodrębnij kluczowe informacje o użytkowniku szukającym działki.

AKTUALNE DANE PROFILU:
{profile_summary}

ROZMOWA:
{messages_text}

Wyodrębnij:
1. AKTUALIZACJE PROFILU - nowe informacje do dodania/zaktualizowania (budżet, lokalizacja, priorytety)
2. FAKTY - ważne informacje o użytkowniku (ma dzieci, pracuje w X, szuka pod dom)
3. PREFERENCJE WYSZUKIWANIA - kryteria jakie preferuje (cisza, blisko lasu, duża działka)
4. SYGNAŁY INTENCJI - wskazówki dotyczące zamiarów zakupu (pilne, pytał o kredyt, porównuje oferty)

Odpowiedz TYLKO w formacie JSON:
{{
  "profile_updates": {{
    "budget_max": null,  // liczba w PLN jeśli wspomniano
    "preferred_cities": [],  // lista miast jeśli wspomniano
    "preferred_districts": [],  // lista dzielnic
    "priority_quietness": null,  // 0.0-1.0 jeśli można wywnioskować
    "priority_nature": null,
    "priority_schools": null  // true/false
  }},
  "facts": [
    // Lista faktów, np. "ma dwoje dzieci w wieku szkolnym"
  ],
  "search_preferences": {{
    // Preferencje wyszukiwania jeśli są nowe
  }},
  "intent_signals": [
    // Lista sygnałów intencji
  ],
  "confidence": 0.8  // Twoja pewność co do ekstrakcji 0-1
}}

Zwróć TYLKO JSON, bez żadnego dodatkowego tekstu."""

        try:
            response = await self._client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": extraction_prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            # Handle case where LLM might add markdown code block
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            data = json.loads(response_text)

            return ExtractedFacts(
                profile_updates={k: v for k, v in data.get("profile_updates", {}).items() if v is not None},
                facts=data.get("facts", []),
                search_preferences=data.get("search_preferences", {}),
                intent_signals=data.get("intent_signals", []),
                confidence=data.get("confidence", 0.5)
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM extraction response: {e}")
            # Fallback to rules
            return self._extract_with_rules(state)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return self._extract_with_rules(state)

    def _extract_with_rules(self, state: AgentState) -> ExtractedFacts:
        """Rule-based fact extraction (fallback when LLM unavailable)."""

        facts: List[str] = []
        profile_updates: Dict[str, Any] = {}
        intent_signals: List[str] = []

        # Analyze conversation buffer
        for msg in state.working.conversation_buffer:
            if msg.role != "user":
                continue

            content = msg.content.lower()

            # Detect children
            if any(word in content for word in ["dzieci", "dziecko", "syn", "córka", "szkoła", "przedszkole"]):
                facts.append("ma dzieci")
                profile_updates["priority_schools"] = True

            # Detect work location
            for city in ["gdańsk", "gdynia", "sopot"]:
                if f"pracuję w {city}" in content or f"pracuje w {city}" in content:
                    facts.append(f"pracuje w {city.title()}")

            # Detect urgency
            if any(word in content for word in ["pilne", "szybko", "jak najszybciej", "w tym miesiącu"]):
                intent_signals.append("urgent_timeline")
                profile_updates["urgency"] = "pilne"

            # Detect budget mentions (already handled by MemoryManager, but add signal)
            if any(word in content for word in ["kredyt", "hipoteka", "finansowanie"]):
                intent_signals.append("financing_inquiry")

            # Detect comparison behavior
            if any(phrase in content for phrase in ["porównaj", "która lepsza", "vs", "versus"]):
                intent_signals.append("comparing_options")

            # Detect nature preferences
            if any(word in content for word in ["las", "natura", "zieleń", "spokój", "cisza"]):
                if "priority_nature" not in profile_updates:
                    profile_updates["priority_nature"] = 0.7
                if "priority_quietness" not in profile_updates:
                    profile_updates["priority_quietness"] = 0.7

        # Extract from search state if available
        if state.working.search_state.approved_preferences:
            prefs = state.working.search_state.approved_preferences

            if gmina := prefs.get("gmina"):
                if gmina not in (profile_updates.get("preferred_cities") or []):
                    profile_updates.setdefault("preferred_cities", []).append(gmina)

            if dzielnica := prefs.get("dzielnica"):
                if dzielnica not in (profile_updates.get("preferred_districts") or []):
                    profile_updates.setdefault("preferred_districts", []).append(dzielnica)

        # Extract from favorites (strong intent signal)
        if state.working.search_state.favorited_parcels:
            intent_signals.append("saved_parcels")
            facts.append(f"polubił {len(state.working.search_state.favorited_parcels)} działek")

        return ExtractedFacts(
            profile_updates=profile_updates,
            facts=facts,
            search_preferences=state.working.search_state.approved_preferences or {},
            intent_signals=intent_signals,
            confidence=0.6  # Rules are less confident
        )

    def _apply_profile_updates(self, profile: BuyerProfile, updates: Dict[str, Any]) -> BuyerProfile:
        """Apply extracted updates to profile."""

        profile_dict = profile.model_dump()

        for key, value in updates.items():
            if value is None:
                continue

            # Handle list fields (append, don't replace)
            if key in ["preferred_cities", "preferred_districts", "avoided_districts"]:
                existing = profile_dict.get(key, [])
                if isinstance(value, list):
                    for item in value:
                        if item not in existing:
                            existing.append(item)
                else:
                    if value not in existing:
                        existing.append(value)
                profile_dict[key] = existing
            else:
                # For scalar values, only update if new value is more informative
                current = profile_dict.get(key)

                # For priorities, take the higher value
                if key.startswith("priority_") and isinstance(value, (int, float)):
                    if current is None or value > current:
                        profile_dict[key] = value
                # For budget, only update if not already set or more specific
                elif key in ["budget_min", "budget_max"] and current is None:
                    profile_dict[key] = value
                # For boolean flags, set to True if evidence found
                elif isinstance(value, bool) and value:
                    profile_dict[key] = value
                # For other fields, only update if not set
                elif current is None:
                    profile_dict[key] = value

        return BuyerProfile.model_validate(profile_dict)

    async def restore_from_workspace(self, state: AgentState) -> AgentState:
        """Restore profile data from workspace for returning user.

        Called when a user returns after session expiry to restore their profile.
        """
        workspace = self.workspace_manager.get_user_workspace(state.user_id)

        if not workspace.exists():
            return state

        # Load profile from workspace
        saved_profile = workspace.load_profile()
        if saved_profile:
            # Merge with current profile (workspace is source of truth for persisted data)
            current = state.semantic.buyer_profile

            # Copy non-empty fields from saved profile
            for field in saved_profile.model_fields:
                saved_value = getattr(saved_profile, field)
                current_value = getattr(current, field)

                # Prefer saved value if current is empty/default
                if saved_value and not current_value:
                    setattr(current, field, saved_value)
                # For lists, merge
                elif isinstance(saved_value, list) and saved_value:
                    current_list = current_value or []
                    for item in saved_value:
                        if item not in current_list:
                            current_list.append(item)
                    setattr(current, field, current_list)

            logger.info(f"Restored profile from workspace for user {state.user_id}")

        # Load recent facts
        recent_facts = workspace.get_recent_memory(days=7)
        for fact in recent_facts:
            state.semantic.add_known_fact(fact)

        # Load frequent locations as hints
        frequent_locations = workspace.get_frequent_locations()
        if frequent_locations:
            state.working.temp_vars["frequent_locations"] = frequent_locations

        return state


# Singleton instance
_flush_manager: Optional[MemoryFlushManager] = None


def get_flush_manager(use_llm: bool = True) -> MemoryFlushManager:
    """Get the global flush manager instance."""
    global _flush_manager
    if _flush_manager is None:
        _flush_manager = MemoryFlushManager(use_llm=use_llm)
    return _flush_manager
