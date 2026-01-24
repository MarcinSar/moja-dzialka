"""
Session Compressor - ETL for Episodic Memory.

Compresses full session transcripts into concise summaries.
Implements the "1000 tokens → 50 tokens" pattern from Software 3.0.
"""

from typing import List, Dict, Any, Optional
from datetime import date

from loguru import logger

from ..schemas import (
    AgentState,
    SearchSession,
    SearchPattern,
)


class SessionCompressor:
    """Compresses sessions into episodic memory.

    Instead of storing full conversation history, we extract:
    - Key decisions and preferences
    - Search patterns
    - User reactions
    - Important moments
    """

    def __init__(self):
        pass

    def compress_session(
        self,
        state: AgentState,
        summary: Optional[str] = None
    ) -> SearchSession:
        """Compress current session into a SearchSession record."""
        search_state = state.working.search_state
        working = state.working
        workflow = state.workflow

        # Generate summary if not provided
        if summary is None:
            summary = self._generate_summary(state)

        session = SearchSession(
            session_id=state.session_id,
            date=date.today(),
            summary=summary,
            search_criteria=search_state.approved_preferences or {},
            parcels_shown=[
                r.get("id", r.get("parcel_id", ""))
                for r in search_state.current_results
            ],
            user_reactions=self._build_reactions(search_state),
            favorites=search_state.favorited_parcels.copy(),
            feedback_summary=search_state.search_feedback,
            max_phase_reached=working.current_phase.value,
            duration_minutes=self._calculate_duration(working),
            message_count=len(working.conversation_buffer),
        )

        return session

    def finalize_session(self, state: AgentState) -> AgentState:
        """Finalize session and store in episodic memory."""
        # Compress current session
        session = self.compress_session(state)

        # Add to episodic memory
        state.episodic.add_session(session)

        # Extract key moments
        key_moments = self._extract_key_moments(state)
        for moment in key_moments:
            state.episodic.add_key_moment(moment)

        # Update patterns
        self._update_patterns(state, session)

        logger.info(f"Finalized session {state.session_id}: {session.summary}")
        return state

    def _generate_summary(self, state: AgentState) -> str:
        """Generate a concise session summary (2-3 sentences)."""
        parts = []
        progress = state.workflow.funnel_progress
        profile = state.semantic.buyer_profile

        # What was searched
        location = progress.known_location
        if location:
            budget_info = ""
            if profile.budget_max:
                budget_k = profile.budget_max // 1000
                budget_info = f" z budżetem do {budget_k}k"
            parts.append(f"Szukano działki w {location}{budget_info}.")

        # What was shown
        shown = progress.parcels_shown_count
        favs = progress.favorites_count
        if shown > 0:
            if favs > 0:
                parts.append(f"Pokazano {shown} działek, {favs} polubiono.")
            else:
                parts.append(f"Pokazano {shown} działek.")

        # Phase reached
        phase = state.working.current_phase.value
        if phase not in ["DISCOVERY", "SEARCH"]:
            parts.append(f"Dotarto do fazy {phase}.")

        # Engagement
        engagement = progress.engagement_level
        if engagement in ["high", "hot"]:
            parts.append(f"Wysokie zaangażowanie ({engagement}).")

        return " ".join(parts) if parts else "Krótka sesja bez znaczących interakcji."

    def _build_reactions(self, search_state) -> Dict[str, str]:
        """Build reactions dict from favorites/rejections."""
        reactions = {}

        for parcel_id in search_state.favorited_parcels:
            reactions[parcel_id] = "liked"

        for parcel_id in search_state.rejected_parcels:
            reactions[parcel_id] = "rejected"

        return reactions

    def _calculate_duration(self, working) -> Optional[int]:
        """Calculate session duration in minutes."""
        if working.last_message and working.session_start:
            delta = working.last_message - working.session_start
            return int(delta.total_seconds() / 60)
        return None

    def _extract_key_moments(self, state: AgentState) -> List[str]:
        """Extract key moments to remember from the session."""
        moments = []
        progress = state.workflow.funnel_progress
        profile = state.semantic.buyer_profile

        # Budget mentioned
        if profile.budget_max and progress.budget_collected:
            moments.append(f"Budżet: {profile.budget_max // 1000}k zł")

        # Location preference
        if progress.known_location:
            moments.append(f"Preferowana lokalizacja: {progress.known_location}")

        # Feature priorities
        if profile.priority_schools:
            moments.append("Ma dzieci - ważne szkoły")
        if profile.priority_quietness > 0.7:
            moments.append("Priorytet: cisza")
        if profile.priority_nature > 0.7:
            moments.append("Priorytet: bliskość natury")

        # Strong reactions
        if len(state.working.search_state.favorited_parcels) > 0:
            favs = state.working.search_state.favorited_parcels[:3]
            moments.append(f"Polubione działki: {', '.join(favs)}")

        # Contact captured
        if profile.contact_email or profile.contact_phone:
            moments.append("Kontakt zostawiony")

        return moments

    def _update_patterns(self, state: AgentState, session: SearchSession) -> None:
        """Update search patterns based on session."""
        criteria = session.search_criteria
        if not criteria:
            return

        # Find or create pattern
        pattern = self._find_or_create_pattern(state.episodic, criteria)

        # Update pattern from session
        pattern.count += 1
        pattern.last_seen = session.date

        # Update confidence based on consistency
        if pattern.count >= 3:
            pattern.confidence = min(0.9, pattern.confidence + 0.1)

        # Learn from reactions
        for parcel_id, reaction in session.user_reactions.items():
            # In a real implementation, we'd look up parcel features
            # and update pattern.feature_importance accordingly
            if reaction == "liked":
                pattern.feature_importance["general"] = (
                    pattern.feature_importance.get("general", 0.5) + 0.05
                )

    def _find_or_create_pattern(
        self,
        episodic,
        criteria: Dict[str, Any]
    ) -> SearchPattern:
        """Find existing pattern or create new one."""
        # Simple matching by location
        location = criteria.get("gmina") or criteria.get("location_description")

        for pattern in episodic.search_patterns:
            if location and location in pattern.preferred_districts:
                return pattern

        # Create new pattern
        pattern = SearchPattern(
            location_preference=location,
            preferred_districts=[location] if location else [],
            last_seen=date.today(),
            count=0,
            confidence=0.3,
        )

        # Set area range if available
        if criteria.get("min_area_m2") and criteria.get("max_area_m2"):
            pattern.area_range = (criteria["min_area_m2"], criteria["max_area_m2"])

        episodic.search_patterns.append(pattern)
        return pattern

    def get_context_for_returning_user(self, state: AgentState) -> str:
        """Generate context summary for returning user.

        This is injected into the prompt to give agent context about past sessions.
        """
        parts = []

        # Session count
        total = state.semantic.total_sessions
        if total > 1:
            parts.append(f"Powracający użytkownik ({total} sesji).")

        # Key facts
        facts = state.semantic.known_facts
        if facts:
            parts.append(f"Znane fakty: {', '.join(facts[:5])}")

        # Recent sessions summary
        recent = state.episodic.get_recent_summary(3)
        if recent and "Brak" not in recent:
            parts.append(f"Ostatnie sesje:\n{recent}")

        # Favorites
        favs = state.episodic.all_time_favorites
        if favs:
            parts.append(f"Ulubione działki: {', '.join(favs[:5])}")

        # Patterns
        patterns = state.episodic.search_patterns
        if patterns:
            top_pattern = max(patterns, key=lambda p: p.count)
            if top_pattern.preferred_districts:
                parts.append(
                    f"Najczęściej szukane: {', '.join(top_pattern.preferred_districts[:3])}"
                )

        return "\n".join(parts) if parts else ""
