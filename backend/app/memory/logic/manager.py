"""
Memory Manager - State Updates and Transitions.

Handles all state mutations in a centralized, predictable way.
Implements the state machine logic for funnel transitions.
"""

from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime, date
import uuid

from loguru import logger

from ..schemas import (
    AgentState,
    WorkingMemory,
    FunnelPhase,
    SearchState,
    SearchSession,
)
from ..schemas.workflow import LocationPreference


# =============================================================================
# FUNNEL PHASE TRANSITION RULES
# =============================================================================
# Define which transitions are allowed (from_phase -> set of allowed to_phases)

ALLOWED_TRANSITIONS: Dict[FunnelPhase, Set[FunnelPhase]] = {
    FunnelPhase.DISCOVERY: {
        FunnelPhase.SEARCH,      # Forward: enough info collected
        FunnelPhase.RETENTION,   # Return after abandonment
    },
    FunnelPhase.SEARCH: {
        FunnelPhase.EVALUATION,  # Forward: user liked a parcel
        FunnelPhase.DISCOVERY,   # Back: need more info
        FunnelPhase.RETENTION,   # Return after abandonment
    },
    FunnelPhase.EVALUATION: {
        FunnelPhase.NEGOTIATION, # Forward: property selected
        FunnelPhase.SEARCH,      # Back: search again
        FunnelPhase.LEAD_CAPTURE,# Skip: direct to lead capture
        FunnelPhase.RETENTION,   # Return after abandonment
    },
    FunnelPhase.NEGOTIATION: {
        FunnelPhase.LEAD_CAPTURE,# Forward: ready to capture
        FunnelPhase.EVALUATION,  # Back: reconsider options
        FunnelPhase.RETENTION,   # Return after abandonment
    },
    FunnelPhase.LEAD_CAPTURE: {
        FunnelPhase.EVALUATION,  # Back: want more options
        FunnelPhase.SEARCH,      # Back: new search
        FunnelPhase.RETENTION,   # Session end
    },
    FunnelPhase.RETENTION: {
        FunnelPhase.DISCOVERY,   # Start fresh
        FunnelPhase.SEARCH,      # Resume search
        FunnelPhase.EVALUATION,  # Resume evaluation
    },
}


class PhaseTransitionError(Exception):
    """Raised when an invalid phase transition is attempted."""

    def __init__(self, from_phase: FunnelPhase, to_phase: FunnelPhase):
        self.from_phase = from_phase
        self.to_phase = to_phase
        super().__init__(
            f"Invalid transition: {from_phase.value} -> {to_phase.value}. "
            f"Allowed: {[p.value for p in ALLOWED_TRANSITIONS.get(from_phase, set())]}"
        )


class MemoryManager:
    """Centralized state management for the agent.

    All state mutations go through this class to ensure consistency.
    """

    def __init__(self):
        pass

    def create_initial_state(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AgentState:
        """Create initial state for a new user/session."""
        uid = user_id or str(uuid.uuid4())
        sid = session_id or str(uuid.uuid4())
        now = datetime.utcnow()

        state = AgentState(
            user_id=uid,
            session_id=sid,
            created_at=now,
            updated_at=now,
        )

        # Initialize working memory with session ID
        state.working = WorkingMemory(session_id=sid)

        # Initialize workflow with visitor info
        state.workflow.visitor_id = uid
        state.workflow.first_visit = now
        state.workflow.last_activity = now

        # Mark first session in semantic memory
        state.semantic.increment_session()
        state.semantic.first_visit = date.today()

        logger.info(f"Created initial state for user {uid}, session {sid}")
        return state

    def start_new_session(self, state: AgentState) -> AgentState:
        """Start a new session for existing user (preserves semantic/episodic)."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Reset working memory (new session)
        state.working = WorkingMemory(session_id=session_id)
        state.session_id = session_id
        state.updated_at = now

        # Update session counters
        state.semantic.increment_session()
        state.workflow.increment_visit()

        # Keep workflow progress for returning users
        if state.workflow.funnel_progress.favorites_count > 0:
            state.working.current_phase = FunnelPhase.RETENTION

        logger.info(f"Started new session {session_id} for user {state.user_id}")
        return state

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    def add_user_message(self, state: AgentState, content: str) -> AgentState:
        """Add user message and extract information."""
        state.working.add_message("user", content)
        state.touch()

        # Adapt preferences based on message
        state.preferences.adapt_to_user_message(content)

        # Mark discovery started
        if not state.workflow.funnel_progress.discovery_started:
            state.workflow.funnel_progress.discovery_started = True

        # Extract information from message
        self._extract_info_from_message(state, content)

        return state

    def add_assistant_message(
        self,
        state: AgentState,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AgentState:
        """Add assistant message."""
        state.working.add_message("assistant", content, tool_calls=tool_calls)
        state.touch()
        return state

    def _extract_info_from_message(self, state: AgentState, content: str) -> None:
        """Extract structured information from user message.

        LOCATION: Not extracted here — the agent handles it via search_locations +
        confirm_location tools. Passive regex extraction of locations from chat
        text is too error-prone (false positives).

        This method only extracts simple numeric patterns (budget, size) and
        preference keywords that are unambiguous.
        """
        content_lower = content.lower()
        progress = state.workflow.funnel_progress
        profile = state.semantic.buyer_profile

        # Initialize LocationPreference if not exists
        if progress.location is None:
            progress.location = LocationPreference()

        # Budget extraction (simple patterns)
        import re
        budget_patterns = [
            r'(\d+)\s*(?:tys|k|tyś)',  # "500 tys", "500k"
            r'(\d+)\s*(?:000|złotych|zł)',  # "500000 zł"
            r'budżet[^\d]*(\d+)',  # "budżet 500000"
            r'do\s*(\d+)\s*(?:tys|k)',  # "do 700k"
        ]
        for pattern in budget_patterns:
            match = re.search(pattern, content_lower)
            if match:
                value = int(match.group(1))
                # Normalize to PLN
                if value < 10000:  # Probably in thousands
                    value *= 1000
                progress.known_budget_max = value
                progress.budget_collected = True
                profile.budget_max = value
                break

        # Size extraction
        size_patterns = [
            r'(\d+)\s*m[²2]',  # "1000 m²"
            r'(\d+)\s*metr',  # "1000 metrów"
            r'(\d{3,4})',  # Just a number in the right range
        ]
        for pattern in size_patterns:
            match = re.search(pattern, content_lower)
            if match:
                value = int(match.group(1))
                if 100 <= value <= 10000:  # Reasonable parcel size
                    progress.known_size_range = f"{value}m²"
                    progress.size_collected = True
                    profile.size_m2_min = int(value * 0.8)
                    profile.size_m2_max = int(value * 1.2)
                    break

        # Preference extraction with hints system
        # hint_* prefixes mean we suggest to user, NOT auto-assign
        preference_keywords = {
            # Cisza (auto-set priority)
            "cicho": ("quietness", 0.8),
            "cisza": ("quietness", 0.8),
            "spokój": ("quietness", 0.7),
            "spokojna": ("quietness", 0.7),
            "spokojne": ("quietness", 0.7),
            "spokojny": ("quietness", 0.7),

            # Natura (auto-set priority)
            "las": ("nature", 0.8),
            "lasu": ("nature", 0.8),
            "lasem": ("nature", 0.8),
            "natura": ("nature", 0.8),
            "natury": ("nature", 0.8),
            "zieleń": ("nature", 0.7),
            "zielona": ("nature", 0.7),
            "zielone": ("nature", 0.7),
            "zieleni": ("nature", 0.7),

            # Szkoły (auto-set, also set hint)
            "szkoła": ("schools", True),
            "szkoły": ("schools", True),
            "szkole": ("schools", True),

            # Dostępność (auto-set priority)
            "sklep": ("accessibility", 0.6),
            "sklepu": ("accessibility", 0.6),
            "komunikacja": ("accessibility", 0.7),
            "komunikacji": ("accessibility", 0.7),
            "autobus": ("accessibility", 0.6),
            "tramwaj": ("accessibility", 0.6),

            # HINTS - NOT auto-assigned, agent should propose
            "rodzina": ("hint_schools", "Wspomniałeś o rodzinie - czy bliskość szkół jest dla Ciebie ważna?"),
            "rodziny": ("hint_schools", "Wspomniałeś o rodzinie - czy bliskość szkół jest dla Ciebie ważna?"),
            "rodzinę": ("hint_schools", "Wspomniałeś o rodzinie - czy bliskość szkół jest dla Ciebie ważna?"),
            "dzieci": ("hint_schools", "Masz dzieci - czy szkoły i przedszkola są ważne?"),
            "dziecko": ("hint_schools", "Masz dziecko - czy szkoły i przedszkola są ważne?"),

            "wsi": ("hint_rural", "Wspomniałeś o wsi - szukasz rzadkiej zabudowy na obrzeżach?"),
            "wieś": ("hint_rural", "Wspomniałeś o wsi - szukasz rzadkiej zabudowy na obrzeżach?"),
            "wiejska": ("hint_rural", "Wspomniałeś o charakterze wiejskim - szukasz rzadkiej zabudowy?"),
            "wiejski": ("hint_rural", "Wspomniałeś o charakterze wiejskim - szukasz rzadkiej zabudowy?"),

            "podmiejska": ("hint_suburban", "Wspomniałeś o charakterze podmiejskim - umiarkowana zabudowa?"),
            "podmiejski": ("hint_suburban", "Wspomniałeś o charakterze podmiejskim - umiarkowana zabudowa?"),

            "inwestycja": ("hint_investment", "Szukasz działki inwestycyjnej - czy ma być budowlana (MN/U)?"),
            "inwestycji": ("hint_investment", "Szukasz działki inwestycyjnej - czy ma być budowlana (MN/U)?"),
            "inwestycyjne": ("hint_investment", "Szukasz działki inwestycyjnej - czy ma być budowlana (MN/U)?"),
            "inwestycyjną": ("hint_investment", "Szukasz działki inwestycyjnej - czy ma być budowlana (MN/U)?"),
        }

        # Initialize detected_hints if not exists
        if "detected_hints" not in state.working.temp_vars:
            state.working.temp_vars["detected_hints"] = []

        for keyword, (pref, value) in preference_keywords.items():
            if keyword in content_lower:
                # Handle hints (NOT auto-assigned)
                if pref.startswith("hint_"):
                    hint_msg = value
                    if hint_msg not in state.working.temp_vars["detected_hints"]:
                        state.working.temp_vars["detected_hints"].append(hint_msg)
                    continue

                # Handle regular preferences (auto-assigned)
                progress.preferences_collected = True
                if pref == "quietness":
                    profile.priority_quietness = max(profile.priority_quietness, value)
                elif pref == "nature":
                    profile.priority_nature = max(profile.priority_nature, value)
                elif pref == "accessibility":
                    profile.priority_accessibility = max(profile.priority_accessibility, value)
                elif pref == "schools":
                    profile.priority_schools = True
                    state.semantic.add_known_fact("has_children")

        # Update engagement based on progress
        progress.update_engagement()

    # =========================================================================
    # SEARCH STATE MANAGEMENT
    # =========================================================================

    def propose_preferences(
        self,
        state: AgentState,
        preferences: Dict[str, Any]
    ) -> AgentState:
        """Record proposed search preferences."""
        state.working.search_state.perceived_preferences = preferences
        state.working.search_state.preferences_proposed = True
        state.workflow.funnel_progress.preferences_proposed = True
        state.touch()
        return state

    def approve_preferences(self, state: AgentState) -> AgentState:
        """Approve proposed preferences."""
        if state.working.search_state.perceived_preferences is None:
            raise ValueError("No preferences to approve")

        state.working.search_state.approved_preferences = (
            state.working.search_state.perceived_preferences.copy()
        )
        state.working.search_state.preferences_approved = True
        state.working.search_state.search_iteration = 0
        state.working.search_state.current_results = []

        state.workflow.funnel_progress.preferences_approved = True
        state.touch()
        return state

    def record_search_results(
        self,
        state: AgentState,
        results: List[Dict[str, Any]]
    ) -> AgentState:
        """Record search results."""
        state.working.search_state.current_results = results
        state.working.search_state.search_executed = True
        state.working.search_state.results_shown = len(results)
        state.working.search_state.search_iteration += 1

        # Update workflow progress
        progress = state.workflow.funnel_progress
        progress.search_initiated = True
        progress.first_results_shown = True
        progress.parcels_shown_count += len(results)

        # Update semantic memory
        state.semantic.total_searches += 1

        # Transition to SEARCH phase if in DISCOVERY
        if state.working.current_phase == FunnelPhase.DISCOVERY:
            self.transition_phase(state, FunnelPhase.SEARCH)

        state.touch()
        return state

    def record_favorite(self, state: AgentState, parcel_id: str) -> AgentState:
        """Record a favorited parcel."""
        if parcel_id not in state.working.search_state.favorited_parcels:
            state.working.search_state.favorited_parcels.append(parcel_id)

        # Update workflow
        state.workflow.funnel_progress.favorites_count += 1
        state.workflow.funnel_progress.evaluation_started = True

        # Update episodic memory
        state.episodic.add_favorite(parcel_id)

        # Add intent signal
        state.semantic.add_intent_signal("favorited_parcel")

        # Transition to EVALUATION if in SEARCH
        if state.working.current_phase == FunnelPhase.SEARCH:
            self.transition_phase(state, FunnelPhase.EVALUATION)

        state.touch()
        return state

    def record_rejection(self, state: AgentState, parcel_id: str) -> AgentState:
        """Record a rejected parcel."""
        if parcel_id not in state.working.search_state.rejected_parcels:
            state.working.search_state.rejected_parcels.append(parcel_id)

        # Update episodic memory
        state.episodic.add_rejection(parcel_id)

        state.touch()
        return state

    def record_feedback(self, state: AgentState, feedback: str) -> AgentState:
        """Record search feedback."""
        state.working.search_state.search_feedback = feedback
        state.touch()
        return state

    # =========================================================================
    # PHASE TRANSITIONS
    # =========================================================================

    def is_transition_allowed(
        self,
        from_phase: FunnelPhase,
        to_phase: FunnelPhase
    ) -> bool:
        """Check if a phase transition is allowed.

        Returns:
            True if transition is allowed, False otherwise.
        """
        if from_phase == to_phase:
            return True  # No-op is always allowed

        allowed = ALLOWED_TRANSITIONS.get(from_phase, set())
        return to_phase in allowed

    def get_allowed_transitions(self, phase: FunnelPhase) -> List[FunnelPhase]:
        """Get list of phases that can be transitioned to from the given phase.

        Returns:
            List of allowed target phases.
        """
        return list(ALLOWED_TRANSITIONS.get(phase, set()))

    def transition_phase(
        self,
        state: AgentState,
        new_phase: FunnelPhase,
        force: bool = False
    ) -> AgentState:
        """Transition to a new funnel phase.

        Args:
            state: Current agent state
            new_phase: Target phase
            force: If True, skip validation (use with caution)

        Returns:
            Updated state

        Raises:
            PhaseTransitionError: If transition is not allowed and force=False
        """
        old_phase = state.working.current_phase

        if old_phase == new_phase:
            return state

        # Validate transition unless forced
        if not force and not self.is_transition_allowed(old_phase, new_phase):
            logger.warning(
                f"Invalid phase transition attempted: {old_phase.value} -> {new_phase.value}"
            )
            raise PhaseTransitionError(old_phase, new_phase)

        logger.info(f"Phase transition: {old_phase.value} -> {new_phase.value}")

        state.working.transition_to(new_phase)
        state.workflow.record_phase_transition(old_phase.value, new_phase.value)

        state.touch()
        return state

    def decide_next_phase(self, state: AgentState) -> FunnelPhase:
        """Decide what phase should be next based on current state."""
        current = state.working.current_phase
        progress = state.workflow.funnel_progress

        # Discovery → Search (only when preferences are approved)
        if current == FunnelPhase.DISCOVERY:
            if progress.preferences_approved and progress.is_ready_for_search():
                return FunnelPhase.SEARCH
            return FunnelPhase.DISCOVERY

        # Search → Evaluation (when user shows interest)
        if current == FunnelPhase.SEARCH:
            if progress.favorites_count > 0:
                return FunnelPhase.EVALUATION
            return FunnelPhase.SEARCH

        # Evaluation → Negotiation (when property selected)
        if current == FunnelPhase.EVALUATION:
            if progress.property_selected:
                return FunnelPhase.NEGOTIATION
            return FunnelPhase.EVALUATION

        # Negotiation → Lead Capture
        if current == FunnelPhase.NEGOTIATION:
            if progress.price_discussed:
                return FunnelPhase.LEAD_CAPTURE
            return FunnelPhase.NEGOTIATION

        # Retention stays retention
        if current == FunnelPhase.RETENTION:
            return FunnelPhase.RETENTION

        return current

    # =========================================================================
    # SKILL OUTPUT PROCESSING
    # =========================================================================

    def update_from_skill_output(
        self,
        state: AgentState,
        skill_name: str,
        output: Dict[str, Any]
    ) -> AgentState:
        """Update state based on skill output."""
        if skill_name == "discovery":
            return self._process_discovery_output(state, output)
        elif skill_name == "search":
            return self._process_search_output(state, output)
        elif skill_name == "evaluation":
            return self._process_evaluation_output(state, output)
        elif skill_name == "lead_capture":
            return self._process_lead_capture_output(state, output)
        return state

    def _process_discovery_output(
        self,
        state: AgentState,
        output: Dict[str, Any]
    ) -> AgentState:
        """Process output from discovery skill."""
        # Update profile from extracted info
        if output.get("location_extracted"):
            state.workflow.funnel_progress.location_collected = True
            state.workflow.funnel_progress.known_location = output["location_extracted"]

        if output.get("budget_extracted"):
            state.workflow.funnel_progress.budget_collected = True
            state.semantic.buyer_profile.budget_max = output["budget_extracted"]

        if output.get("size_extracted"):
            state.workflow.funnel_progress.size_collected = True

        if output.get("priorities_extracted"):
            state.workflow.funnel_progress.preferences_collected = True

        # Check if ready for search
        if output.get("ready_for_search"):
            state.workflow.funnel_progress.discovery_complete = True

        return state

    def _process_search_output(
        self,
        state: AgentState,
        output: Dict[str, Any]
    ) -> AgentState:
        """Process output from search skill."""
        if output.get("results"):
            self.record_search_results(state, output["results"])
        return state

    def _process_evaluation_output(
        self,
        state: AgentState,
        output: Dict[str, Any]
    ) -> AgentState:
        """Process output from evaluation skill."""
        if output.get("selected_parcel"):
            state.workflow.funnel_progress.property_selected = True
            state.workflow.funnel_progress.evaluation_started = True

        if output.get("favorited_parcels"):
            for parcel_id in output["favorited_parcels"]:
                self.record_favorite(state, parcel_id)

        return state

    def _process_lead_capture_output(
        self,
        state: AgentState,
        output: Dict[str, Any]
    ) -> AgentState:
        """Process output from lead capture skill."""
        profile = state.semantic.buyer_profile

        if output.get("email"):
            profile.contact_email = output["email"]
            state.workflow.funnel_progress.contact_captured = True

        if output.get("phone"):
            profile.contact_phone = output["phone"]
            state.workflow.funnel_progress.contact_captured = True

        if output.get("name"):
            profile.name = output["name"]

        return state

    # =========================================================================
    # SESSION COMPRESSION
    # =========================================================================

    def compress_session(self, state: AgentState) -> SearchSession:
        """Compress current session into episodic memory."""
        search_state = state.working.search_state

        session = SearchSession(
            session_id=state.session_id,
            date=date.today(),
            summary=self._generate_session_summary(state),
            search_criteria=search_state.approved_preferences or {},
            parcels_shown=[r.get("id", "") for r in search_state.current_results],
            user_reactions={},
            favorites=search_state.favorited_parcels.copy(),
            max_phase_reached=state.working.current_phase.value,
            message_count=len(state.working.conversation_buffer),
        )

        # Build reactions from favorites/rejections
        for parcel_id in search_state.favorited_parcels:
            session.user_reactions[parcel_id] = "liked"
        for parcel_id in search_state.rejected_parcels:
            session.user_reactions[parcel_id] = "rejected"

        return session

    def _generate_session_summary(self, state: AgentState) -> str:
        """Generate a brief summary of the session."""
        parts = []

        # Location (prefer new LocationPreference, fallback to known_location)
        progress = state.workflow.funnel_progress
        if progress.location:
            loc_str = progress.location.to_display_string()
            if loc_str and loc_str != "nie określono":
                parts.append(f"Szukano w: {loc_str}")
        elif progress.known_location:
            parts.append(f"Szukano w: {progress.known_location}")

        # Results
        shown = state.workflow.funnel_progress.parcels_shown_count
        if shown > 0:
            parts.append(f"Pokazano {shown} działek")

        # Favorites
        favs = state.workflow.funnel_progress.favorites_count
        if favs > 0:
            parts.append(f"Polubiono {favs}")

        # Phase
        phase = state.working.current_phase.value
        parts.append(f"Faza: {phase}")

        return ". ".join(parts) if parts else "Sesja bez aktywności."
