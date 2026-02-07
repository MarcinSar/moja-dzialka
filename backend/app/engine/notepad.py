"""
Notepad - Session state shared between agent and backend.

The notepad is the single source of truth for session state.
Backend-managed fields are updated by tool execution.
Agent-managed fields are updated via notepad_update tool.
Injected at the end of each user message (recitation pattern).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class LocationState:
    """Validated location from location_confirm."""
    gmina: Optional[str] = None
    powiat: Optional[str] = None
    dzielnica: Optional[str] = None
    miejscowosc: Optional[str] = None
    wojewodztwo: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: int = 5000
    parcel_count: Optional[int] = None
    validated: bool = False


@dataclass
class SearchResults:
    """Summary of last search execution."""
    total_count: int = 0
    file_path: Optional[str] = None  # JSONL file with full results
    page_size: int = 10
    current_page: int = 0
    query_text: Optional[str] = None
    filters_used: Optional[Dict[str, Any]] = None
    executed_at: Optional[str] = None


@dataclass
class Notepad:
    """Session notepad - injected at end of each user message.

    Backend-managed fields (read-only for agent):
        location: Set by location_confirm tool
        search_results: Set by search_execute tool
        favorites: Set by parcel_details + user actions
        user_facts: Extracted from conversation (budget, contact, family)

    Agent-managed fields (via notepad_update tool):
        user_goal: What user is looking for
        preferences: Search criteria being built
        next_step: What to do next
        notes: Free-form agent notes
    """
    # Backend-managed
    location: Optional[LocationState] = None
    search_results: Optional[SearchResults] = None
    favorites: List[str] = field(default_factory=list)
    user_facts: Dict[str, Any] = field(default_factory=dict)

    # Agent-managed
    user_goal: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    next_step: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON."""
        d = {}
        d["location"] = asdict(self.location) if self.location else None
        d["search_results"] = asdict(self.search_results) if self.search_results else None
        d["favorites"] = self.favorites
        d["user_facts"] = self.user_facts
        d["user_goal"] = self.user_goal
        d["preferences"] = self.preferences
        d["next_step"] = self.next_step
        d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Notepad:
        """Deserialize from dict."""
        np = cls()
        if data.get("location"):
            np.location = LocationState(**data["location"])
        if data.get("search_results"):
            np.search_results = SearchResults(**data["search_results"])
        np.favorites = data.get("favorites", [])
        np.user_facts = data.get("user_facts", {})
        np.user_goal = data.get("user_goal")
        np.preferences = data.get("preferences", {})
        np.next_step = data.get("next_step")
        np.notes = data.get("notes", [])
        return np

    def to_injection(self) -> str:
        """Render notepad for injection into user messages."""
        return f"<notepad>{json.dumps(self.to_dict(), ensure_ascii=False)}</notepad>"

    def update_agent_fields(self, updates: Dict[str, Any]) -> None:
        """Update agent-managed fields only."""
        if "user_goal" in updates:
            self.user_goal = updates["user_goal"]
        if "preferences" in updates:
            self.preferences.update(updates["preferences"])
        if "next_step" in updates:
            self.next_step = updates["next_step"]
        if "notes" in updates:
            if isinstance(updates["notes"], list):
                self.notes = updates["notes"]
            elif isinstance(updates["notes"], str):
                self.notes.append(updates["notes"])

    def update_backend_location(self, location: LocationState) -> None:
        """Backend sets validated location."""
        self.location = location

    def update_backend_search(self, results: SearchResults) -> None:
        """Backend sets search results."""
        self.search_results = results

    def add_favorite(self, parcel_id: str) -> None:
        """Add parcel to favorites."""
        if parcel_id not in self.favorites:
            self.favorites.append(parcel_id)

    def set_user_fact(self, key: str, value: Any) -> None:
        """Set a user fact (budget, contact, children, etc.)."""
        self.user_facts[key] = value
