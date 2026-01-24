"""
Workflow Memory - Funnel State Machine.

Tracks progress through the sales funnel with explicit state.
Enables measuring conversion and identifying drop-off points.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    known_location: Optional[str] = None  # "Gdańsk", "Osowa", etc.
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

        We can search if we have at least location OR clear preferences OR
        preferences have been proposed (ready for approval/execution).
        """
        return (
            self.location_collected or
            self.preferences_collected or
            self.known_location is not None or
            self.preferences_proposed  # Can transition to search skill
        )

    def is_discovery_sufficient(self) -> bool:
        """Check if discovery has enough info to proceed."""
        # At minimum: location
        # Ideally: location + (budget OR size OR preferences)
        has_location = self.location_collected or self.known_location
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
