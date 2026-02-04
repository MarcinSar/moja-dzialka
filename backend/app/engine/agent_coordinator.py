"""
Agent Coordinator - Routing + State Management.

The coordinator is the master orchestrator that:
1. Loads/saves state via persistence backend
2. Decides which skill to use (state machine routing)
3. Delegates execution to PropertyAdvisorAgent
4. Updates state based on results
5. Advances funnel phase when appropriate
"""

from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import uuid

from loguru import logger

from app.memory import (
    AgentState,
    FunnelPhase,
    MemoryManager,
    SessionCompressor,
    get_flush_manager,
    get_workspace_manager,
)
from app.skills import get_skill, list_skills
from app.persistence import get_persistence_backend

from .property_advisor_agent import PropertyAdvisorAgent, get_agent_type_for_skill


class AgentCoordinator:
    """Master coordinator: routing + state management.

    This is the main entry point for processing user messages.
    It implements the state machine logic for funnel transitions.
    """

    def __init__(self, persistence_backend: str = "memory"):
        """Initialize coordinator.

        Args:
            persistence_backend: Backend for state persistence
                                ("memory", "redis", "redis_postgres")
        """
        self.persistence = get_persistence_backend(persistence_backend)
        self.memory_manager = MemoryManager()
        self.session_compressor = SessionCompressor()
        self.executor = PropertyAdvisorAgent()
        self.flush_manager = get_flush_manager()
        self.workspace_manager = get_workspace_manager()

    async def process_message(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main entry point for processing user messages.

        This is an async generator that yields events during processing.

        Args:
            user_id: Unique user identifier
            message: User's message
            session_id: Optional session ID (for resuming sessions)

        Yields:
            Event dicts with type and data
        """
        # 1. Load or create state
        state = await self._load_or_create_state(user_id, session_id)

        yield {
            "type": "thinking",
            "data": {"message": "Analizuję Twoje zapytanie..."}
        }

        try:
            # 1b. Check if memory flush is needed (before adding new message)
            if self.flush_manager.should_flush(state):
                logger.info(f"Memory flush triggered for user {user_id}")
                yield {
                    "type": "thinking",
                    "data": {"message": "Zapisuję ważne informacje..."}
                }
                await self.flush_manager.flush(state)
            # 2. Add user message to state
            state = self.memory_manager.add_user_message(state, message)

            # 3. Decide which skill to use
            skill_name = self.decide_next_skill(state)
            state.working.active_skill = skill_name

            logger.info(
                f"User {user_id}: phase={state.working.current_phase.value}, "
                f"skill={skill_name}"
            )

            agent_type = get_agent_type_for_skill(skill_name)
            yield {
                "type": "skill_selected",
                "data": {
                    "skill": skill_name,
                    "phase": state.working.current_phase.value,
                    "agent_type": agent_type,
                }
            }

            # 4. Execute skill (yields events)
            # Note: State updates are now handled internally by ToolExecutor
            # and applied in PropertyAdvisorAgent._apply_state_updates()
            async for event in self.executor.execute(skill_name, message, state):
                yield event

                # Emit activity events for frontend tracking
                if event["type"] == "tool_call":
                    tool_name = event["data"].get("tool", "")
                    yield {
                        "type": "activity",
                        "data": {
                            "action": f"Używam narzędzia: {tool_name}",
                            "details": f"Skill: {skill_name}, Tool: {tool_name}",
                        }
                    }
                elif event["type"] == "thinking":
                    yield {
                        "type": "activity",
                        "data": {
                            "action": "Analizuję...",
                            "details": f"Skill: {skill_name}",
                        }
                    }

                # Track funnel progress based on tool results
                if event["type"] == "tool_result":
                    tool_name = event["data"].get("tool")
                    result = event["data"].get("result", {})
                    self._update_funnel_from_tool(state, tool_name, result)

            # 5. Get final response from executor
            final_response = self.executor.get_last_response()
            if final_response:
                state = self.memory_manager.add_assistant_message(
                    state, final_response
                )

            # 6. Maybe advance funnel phase
            state = self._maybe_advance_phase(state)

            # 7. Save state
            await self.persistence.save(user_id, state.model_dump())

            yield {
                "type": "done",
                "data": {
                    "phase": state.working.current_phase.value,
                    "engagement": state.workflow.funnel_progress.engagement_level,
                }
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            yield {
                "type": "error",
                "data": {"message": str(e)}
            }

    async def _load_or_create_state(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> AgentState:
        """Load existing state or create new one."""
        # Try to load existing state
        state_dict = await self.persistence.load(user_id)

        if state_dict:
            # Reconstruct state from dict
            state = AgentState.model_validate(state_dict)

            # Check if this is a new session
            if session_id and session_id != state.session_id:
                # Compress old session and start new
                self.session_compressor.finalize_session(state)
                state = self.memory_manager.start_new_session(state)
            elif not session_id:
                # Check if session is stale (> 30 minutes inactive)
                last_activity = state.workflow.last_activity
                if (datetime.utcnow() - last_activity).total_seconds() > 1800:
                    # Compress old session and start new
                    self.session_compressor.finalize_session(state)
                    state = self.memory_manager.start_new_session(state)

            logger.info(f"Loaded state for user {user_id}, session {state.session_id}")
        else:
            # Create new state with the session_id from the API layer
            state = self.memory_manager.create_initial_state(user_id, session_id)
            logger.info(f"Created new state for user {user_id}")

            # Try to restore profile from workspace (returning user with expired Redis)
            state = await self.flush_manager.restore_from_workspace(state)

        return state

    def decide_next_skill(self, state: AgentState) -> str:
        """Explicit state machine routing.

        Decides which skill to use based on current phase and progress.
        """
        phase = state.working.current_phase
        funnel = state.workflow.funnel_progress
        search = state.working.search_state

        # RETENTION phase - check what returning user needs
        if phase == FunnelPhase.RETENTION:
            if funnel.favorites_count > 0:
                return "evaluation"
            else:
                return "discovery"

        # DISCOVERY phase
        if phase == FunnelPhase.DISCOVERY:
            if funnel.preferences_approved and funnel.is_ready_for_search():
                # Preferences approved - ready for search
                return "search"
            else:
                return "discovery"

        # SEARCH phase
        if phase == FunnelPhase.SEARCH:
            if not search.preferences_approved:
                # Can't search without approved preferences - go back to discovery
                return "discovery"
            if not search.search_executed:
                return "search"
            elif funnel.favorites_count > 0:
                # User liked something, move to evaluation
                return "evaluation"
            elif search.search_feedback:
                # User gave feedback, refine search
                return "search"
            else:
                # Show results and wait for reaction
                return "search"

        # EVALUATION phase
        if phase == FunnelPhase.EVALUATION:
            if funnel.property_selected:
                return "lead_capture"
            elif funnel.price_discussed:
                return "market_analysis"
            else:
                return "evaluation"

        # NEGOTIATION phase
        if phase == FunnelPhase.NEGOTIATION:
            if funnel.price_discussed:
                return "lead_capture"
            else:
                return "market_analysis"

        # LEAD_CAPTURE phase
        if phase == FunnelPhase.LEAD_CAPTURE:
            return "lead_capture"

        # Default to discovery
        return "discovery"

    def _update_funnel_from_tool(
        self,
        state: AgentState,
        tool_name: str,
        result: Dict[str, Any]
    ) -> None:
        """Update funnel progress based on tool result.

        Synchronizes both workflow.funnel_progress and working.search_state
        to prevent state divergence between the two tracking paths.
        """
        if not result or "error" in result:
            return

        funnel = state.workflow.funnel_progress
        search = state.working.search_state

        # Search tools - track funnel progress + sync working state
        if tool_name == "propose_search_preferences":
            funnel.preferences_proposed = True
            if not search.preferences_proposed:
                search.preferences_proposed = True

        elif tool_name == "approve_search_preferences":
            funnel.preferences_approved = True
            if not search.preferences_approved:
                search.preferences_approved = True

        elif tool_name == "execute_search":
            parcels = result.get("parcels", [])
            funnel.search_initiated = True
            funnel.first_results_shown = True
            funnel.parcels_shown_count += len(parcels)
            if not search.search_executed:
                search.search_executed = True

        # Price tools
        elif tool_name == "get_district_prices":
            if result.get("price_per_m2_min"):
                funnel.price_discussed = True

        elif tool_name == "estimate_parcel_value":
            if result.get("estimated_value_min"):
                funnel.price_discussed = True
                funnel.value_estimated = True

        # Detail tools
        elif tool_name == "get_parcel_details":
            funnel.details_requested = True
            funnel.evaluation_started = True

        elif tool_name == "get_parcel_neighborhood":
            funnel.neighborhood_checked = True

        elif tool_name == "generate_map_data":
            funnel.map_viewed = True

        # Update engagement after any tool call
        funnel.update_engagement()

    def _maybe_advance_phase(self, state: AgentState) -> AgentState:
        """Advance funnel phase if conditions are met."""
        current = state.working.current_phase
        next_phase = self.memory_manager.decide_next_phase(state)

        if next_phase != current:
            state = self.memory_manager.transition_phase(state, next_phase)

        return state

    async def get_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current state for a user."""
        return await self.persistence.load(user_id)

    async def clear_state(self, user_id: str) -> None:
        """Clear state for a user (reset conversation)."""
        await self.persistence.delete(user_id)
        logger.info(f"Cleared state for user {user_id}")

    async def finalize_session(self, user_id: str) -> None:
        """Finalize and compress current session."""
        state_dict = await self.persistence.load(user_id)
        if state_dict:
            state = AgentState.model_validate(state_dict)

            # Flush memory before finalization
            await self.flush_manager.flush(state)

            # Archive session to workspace
            workspace = self.workspace_manager.get_user_workspace(user_id)
            messages = [
                {"role": m.role, "content": m.content}
                for m in state.working.conversation_buffer
            ]
            if messages:
                workspace.save_session(state.session_id, messages)

            # Compress session
            state = self.session_compressor.finalize_session(state)
            await self.persistence.save(user_id, state.model_dump())
            logger.info(f"Finalized session for user {user_id}")
