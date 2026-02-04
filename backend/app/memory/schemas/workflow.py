"""
Workflow Memory - Funnel State Machine.

Tracks progress through the sales funnel with explicit state.
Enables measuring conversion and identifying drop-off points.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


# =============================================================================
# LOCATION PREFERENCE (2026-01-25)
# Hierarchical location structure for Polish administrative units
# =============================================================================

class LocationPreference(BaseModel):
    """
    Hierarchical location preference - scalable for Polish administrative structure.

    IMPORTANT: Dzielnica belongs to MIEJSCOWOŚĆ, not directly to gmina!

    Hierarchy: województwo → powiat → gmina → miejscowość → dzielnica

    In Trójmiasto MVP:
    - gmina = miejscowość (Gdańsk, Gdynia, Sopot are both gmina and miejscowość)
    - dzielnica belongs to miejscowość

    In future (when adding gminy wiejskie like Żukowo):
    - gmina "Żukowo" contains miejscowości "Żukowo", "Chwaszczyno", "Banino"
    - dzielnica belongs to miejscowość (if any)
    """
    # Full administrative hierarchy
    wojewodztwo: Optional[str] = None
    powiat: Optional[str] = None
    gmina: Optional[str] = None           # Administrative unit
    miejscowosc: Optional[str] = None     # Settlement/town - DZIELNICA BELONGS HERE!
    dzielnica: Optional[str] = None

    # Textual description (e.g., "near the sea", "close to city center")
    description: Optional[str] = None

    # Validation status
    validated: bool = False

    def to_search_params(self) -> Dict[str, str]:
        """Convert to search parameters for graph_service."""
        params = {}
        if self.gmina:
            params["gmina"] = self.gmina
        if self.miejscowosc:
            # NOTE: miejscowosc maps to dzielnica field in Parcel nodes (MVP structure)
            params["miejscowosc"] = self.miejscowosc
        if self.dzielnica:
            params["dzielnica"] = self.dzielnica
        return params

    def set_dzielnica(self, dzielnica: str, miejscowosc: str, gmina: Optional[str] = None):
        """
        Set dzielnica along with miejscowość (required!).
        Dzielnica MUST have an associated miejscowość.

        Args:
            dzielnica: District name (e.g., "Osowa")
            miejscowosc: Settlement name (e.g., "Gdańsk") - REQUIRED
            gmina: Optional gmina for context (defaults to miejscowość in MVP)
        """
        self.dzielnica = dzielnica
        self.miejscowosc = miejscowosc
        if gmina:
            self.gmina = gmina
        elif not self.gmina and miejscowosc:
            # In MVP: gmina = miejscowość
            self.gmina = miejscowosc

    def clear_dzielnica(self):
        """Clear dzielnica when miejscowość changes."""
        self.dzielnica = None

    def update_from_resolved(self, resolved: Dict) -> None:
        """Update from resolve_location() result."""
        if resolved.get("resolved"):
            if resolved.get("gmina"):
                self.gmina = resolved["gmina"]
            if resolved.get("miejscowosc"):
                self.miejscowosc = resolved["miejscowosc"]
            if resolved.get("dzielnica"):
                self.dzielnica = resolved["dzielnica"]
            self.validated = True

    def __str__(self) -> str:
        parts = []
        if self.dzielnica:
            parts.append(self.dzielnica)
        if self.miejscowosc:
            parts.append(self.miejscowosc)
        elif self.gmina:
            parts.append(self.gmina)
        return ", ".join(parts) if parts else self.description or "brak"

    def to_display_string(self) -> str:
        """Human-readable location string."""
        if self.dzielnica and self.miejscowosc:
            return f"{self.dzielnica}, {self.miejscowosc}"
        elif self.miejscowosc:
            return self.miejscowosc
        elif self.gmina:
            return self.gmina
        elif self.description:
            return self.description
        return "nie określono"


class FunnelProgress(BaseModel):
    """Funnel stage completion tracking.

    Tracks which steps in each phase have been completed.
    """
    # === DISCOVERY PHASE ===
    discovery_started: bool = False
    greeting_done: bool = False
    location_collected: bool = False
    budget_collected: bool = False
    size_collected: bool = False
    preferences_collected: bool = False
    discovery_complete: bool = False

    # Partial info (what we know so far)
    # CHANGED 2026-01-25: Use LocationPreference instead of simple string
    known_location: Optional[str] = None  # DEPRECATED - use location instead
    location: Optional[LocationPreference] = None  # Full hierarchical location
    location_history: List[LocationPreference] = Field(default_factory=list)  # For "show other in same area"

    known_budget_max: Optional[int] = None
    known_size_range: Optional[str] = None  # "1000m2", "500-1000m2"

    # === SEARCH PHASE ===
    search_initiated: bool = False
    preferences_proposed: bool = False
    preferences_approved: bool = False
    first_results_shown: bool = False
    parcels_shown_count: int = 0

    # === EVALUATION PHASE ===
    evaluation_started: bool = False
    favorites_count: int = 0
    comparison_requested: bool = False
    details_requested: bool = False
    map_viewed: bool = False
    neighborhood_checked: bool = False

    # === NEGOTIATION PHASE ===
    property_selected: bool = False
    price_discussed: bool = False
    value_estimated: bool = False

    # === LEAD CAPTURE PHASE ===
    contact_requested: bool = False
    contact_captured: bool = False
    follow_up_scheduled: bool = False

    # === SCORING ===
    engagement_level: str = "low"  # "low", "medium", "high", "hot"
    intent_confidence: float = 0.1  # 0.0-1.0

    def is_ready_for_search(self) -> bool:
        """Check if enough info collected for search.

        Approved preferences are always sufficient.
        Proposed preferences + location can transition to SEARCH phase,
        but the search skill gate will still require approval before execute_search.
        """
        if self.preferences_approved:
            return True

        has_location = (
            self.location_collected or
            self.known_location is not None or
            (self.location is not None and (self.location.gmina or self.location.miejscowosc))
        )
        return (
            (has_location and self.preferences_collected) or
            (has_location and self.preferences_proposed)
        )

    def is_discovery_sufficient(self) -> bool:
        """Check if discovery has enough info to proceed."""
        # At minimum: location
        # Ideally: location + (budget OR size OR preferences)
        # CHANGED 2026-01-25: Check new location field too
        has_location = (
            self.location_collected or
            self.known_location or
            (self.location is not None and (self.location.gmina or self.location.miejscowosc))
        )
        has_criteria = self.budget_collected or self.size_collected or self.preferences_collected
        return has_location and has_criteria

    def update_engagement(self) -> None:
        """Update engagement level based on progress."""
        score = 0

        # Discovery signals
        if self.discovery_started:
            score += 0.1
        if self.location_collected:
            score += 0.1
        if self.budget_collected:
            score += 0.15

        # Search signals
        if self.first_results_shown:
            score += 0.1
        if self.parcels_shown_count > 5:
            score += 0.1

        # Evaluation signals (strong)
        if self.favorites_count > 0:
            score += 0.15
        if self.details_requested:
            score += 0.1
        if self.map_viewed:
            score += 0.05

        # Negotiation signals (very strong)
        if self.property_selected:
            score += 0.2
        if self.price_discussed:
            score += 0.1

        # Update level
        self.intent_confidence = min(score, 1.0)

        if score >= 0.7:
            self.engagement_level = "hot"
        elif score >= 0.5:
            self.engagement_level = "high"
        elif score >= 0.3:
            self.engagement_level = "medium"
        else:
            self.engagement_level = "low"


class WorkflowMemory(BaseModel):
    """Funnel state machine.

    Tracks the user's journey through the sales funnel.
    """
    funnel_progress: FunnelProgress = Field(default_factory=FunnelProgress)

    # Visitor identification
    visitor_id: str
    first_visit: datetime
    last_activity: datetime

    # Session tracking
    current_session_number: int = 1
    total_visits: int = 1

    # Phase history (for analytics)
    phase_history: List[str] = Field(default_factory=list)
    # e.g., ["DISCOVERY", "SEARCH", "EVALUATION", "SEARCH"]  # user went back

    # Blockers and drop-off signals
    blockers_encountered: List[str] = Field(default_factory=list)
    # e.g., ["no_matching_parcels", "budget_too_low"]

    def record_phase_transition(self, from_phase: str, to_phase: str) -> None:
        """Record a phase transition for analytics."""
        self.phase_history.append(to_phase)
        self.last_activity = datetime.utcnow()
        self.funnel_progress.update_engagement()

    def record_blocker(self, blocker: str) -> None:
        """Record a blocker that prevented progress."""
        if blocker not in self.blockers_encountered:
            self.blockers_encountered.append(blocker)

    def increment_visit(self) -> None:
        """Called when user starts a new visit."""
        self.total_visits += 1
        self.current_session_number += 1
        self.last_activity = datetime.utcnow()

    def get_funnel_stage(self) -> str:
        """Get current funnel stage as string."""
        progress = self.funnel_progress

        if progress.contact_captured:
            return "CONVERTED"
        elif progress.property_selected:
            return "NEGOTIATION"
        elif progress.favorites_count > 0:
            return "EVALUATION"
        elif progress.first_results_shown:
            return "SEARCH"
        elif progress.discovery_started:
            return "DISCOVERY"
        else:
            return "NEW"

    def get_next_action_hint(self) -> str:
        """Get hint for what to do next."""
        progress = self.funnel_progress

        if not progress.discovery_started:
            return "Start discovery: ask about location"
        elif not progress.location_collected:
            return "Collect location preference"
        elif not progress.is_ready_for_search():
            return "Collect more criteria (budget, size, or preferences)"
        elif not progress.first_results_shown:
            return "Show search results"
        elif progress.favorites_count == 0:
            return "Help user find parcels they like"
        elif not progress.property_selected:
            return "Help user select a property"
        elif not progress.contact_captured:
            return "Capture contact information"
        else:
            return "Follow up with user"
