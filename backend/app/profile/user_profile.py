"""
UserProfile - Cross-session user data model.

Persisted in Redis (7d TTL) and PostgreSQL (permanent).
Loaded at session start, updated at session end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class UserProfile:
    """Cross-session user profile.

    Contains data that persists across sessions:
    - Contact info (from lead_capture)
    - Preferred locations and search history
    - Budget range
    - Family situation
    - Favorite parcels across sessions
    """
    user_id: str

    # Contact
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Preferences (aggregated across sessions)
    preferred_locations: List[str] = field(default_factory=list)  # e.g., ["Osowa", "Kokoszki"]
    preferred_size: Optional[str] = None  # e.g., "pod_dom"
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None

    # Context
    family_info: Optional[str] = None  # e.g., "2 dzieci w wieku szkolnym"
    purpose: Optional[str] = None  # e.g., "dom jednorodzinny"

    # History
    session_count: int = 0
    all_favorites: List[str] = field(default_factory=list)
    last_search_location: Optional[str] = None

    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "preferred_locations": self.preferred_locations,
            "preferred_size": self.preferred_size,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "family_info": self.family_info,
            "purpose": self.purpose,
            "session_count": self.session_count,
            "all_favorites": self.all_favorites,
            "last_search_location": self.last_search_location,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserProfile:
        """Deserialize from dict."""
        return cls(
            user_id=data["user_id"],
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone"),
            preferred_locations=data.get("preferred_locations", []),
            preferred_size=data.get("preferred_size"),
            budget_min=data.get("budget_min"),
            budget_max=data.get("budget_max"),
            family_info=data.get("family_info"),
            purpose=data.get("purpose"),
            session_count=data.get("session_count", 0),
            all_favorites=data.get("all_favorites", []),
            last_search_location=data.get("last_search_location"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def merge_session_data(self, notepad_dict: Dict[str, Any]) -> None:
        """Merge data from a completed session's notepad into profile.

        Only counts as a session if there was actual activity
        (favorites, validated location, or user facts).
        """
        from datetime import datetime

        if not notepad_dict or not isinstance(notepad_dict, dict):
            return

        # Check for actual session activity before counting
        location = notepad_dict.get("location") or {}
        facts = notepad_dict.get("user_facts") or {}

        has_favorites = bool(notepad_dict.get("favorites"))
        has_location = bool(location.get("validated"))
        has_facts = bool(facts)
        has_goal = bool(notepad_dict.get("user_goal"))
        has_search = bool(notepad_dict.get("search_results"))

        has_activity = has_favorites or has_location or has_facts or has_goal or has_search
        if has_activity:
            self.session_count += 1

        self.updated_at = datetime.now().isoformat()

        # Merge favorites
        favorites = notepad_dict.get("favorites") or []
        for fav in favorites:
            if fav not in self.all_favorites:
                self.all_favorites.append(fav)

        # Merge location
        if location.get("validated"):
            loc_name = location.get("dzielnica") or location.get("gmina")
            if loc_name:
                self.last_search_location = loc_name
                if loc_name not in self.preferred_locations:
                    self.preferred_locations.append(loc_name)

        # Merge user facts
        if isinstance(facts, dict):
            if facts.get("budget_min"):
                self.budget_min = facts["budget_min"]
            if facts.get("budget_max"):
                self.budget_max = facts["budget_max"]
            if facts.get("family"):
                self.family_info = facts["family"]
            if facts.get("email"):
                self.email = facts["email"]
            if facts.get("phone"):
                self.phone = facts["phone"]
            if facts.get("name"):
                self.name = facts["name"]
