"""
Feedback API endpoints (v3.0).

Handles user feedback on parcels (favorites, rejections) for re-ranking.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header
from loguru import logger

from app.models.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    UserFeedbackHistory,
)
from app.services.feedback_learning import get_feedback_learning_service
from app.persistence import get_persistence_backend


router = APIRouter(prefix="/feedback", tags=["feedback"])


# =============================================================================
# FEEDBACK SUBMISSION
# =============================================================================

@router.post("/{parcel_id:path}", response_model=FeedbackResponse)
async def submit_feedback(
    parcel_id: str,
    request: FeedbackRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Submit feedback on a parcel.

    Actions:
    - favorite: Mark parcel as liked (boosts similar parcels)
    - reject: Mark parcel as disliked (penalizes similar parcels)
    - view: Track that user viewed this parcel
    - compare: Track that parcel was included in comparison

    The feedback is used to:
    1. Re-rank future search results
    2. Extract preference patterns
    3. Improve recommendations

    Headers:
    - X-User-ID: User identifier (from session)
    - X-Session-ID: Session identifier

    Returns:
        FeedbackResponse with confirmation and pattern count
    """
    try:
        # Get user/session from headers or request
        user_id = x_user_id or "anonymous"
        session_id = request.session_id or x_session_id

        logger.info(
            f"Feedback received: {request.action} on {parcel_id} "
            f"from user {user_id}, session {session_id}"
        )

        # Get persistence backend to access agent state
        persistence = get_persistence_backend()

        # Import AgentState for type conversion
        from app.memory import AgentState

        # Try to get existing state
        state = None
        if user_id != "anonymous":
            state_dict = await persistence.load(user_id)
            if state_dict:
                state = AgentState.model_validate(state_dict)

        patterns_extracted = 0

        if state:
            # Update state with feedback
            if request.action == "favorite":
                if parcel_id not in state.working.search_state.favorited_parcels:
                    state.working.search_state.favorited_parcels.append(parcel_id)
                # Remove from rejections if present
                if parcel_id in state.working.search_state.rejected_parcels:
                    state.working.search_state.rejected_parcels.remove(parcel_id)

            elif request.action == "reject":
                if parcel_id not in state.working.search_state.rejected_parcels:
                    state.working.search_state.rejected_parcels.append(parcel_id)
                # Remove from favorites if present
                if parcel_id in state.working.search_state.favorited_parcels:
                    state.working.search_state.favorited_parcels.remove(parcel_id)

            # Save updated state
            await persistence.save(user_id, state.model_dump())

            # Extract patterns using feedback learning service
            feedback_service = get_feedback_learning_service()
            patterns = feedback_service.extract_preference_patterns(state)
            patterns_extracted = len(patterns.get("patterns", []))

            # Save patterns to workspace
            if patterns_extracted > 0:
                feedback_service.save_feedback_to_workspace(state)

        # Generate response message
        action_messages = {
            "favorite": "Działka dodana do ulubionych",
            "reject": "Działka odrzucona",
            "view": "Wyświetlenie zapisane",
            "compare": "Porównanie zapisane",
        }

        return FeedbackResponse(
            success=True,
            message=action_messages.get(request.action, "Feedback zapisany"),
            parcel_id=parcel_id,
            action=request.action,
            patterns_extracted=patterns_extracted,
        )

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEEDBACK HISTORY
# =============================================================================

@router.get("/history", response_model=UserFeedbackHistory)
async def get_feedback_history(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Get user's feedback history.

    Returns lists of favorited and rejected parcels,
    plus extracted preference patterns.
    """
    try:
        user_id = x_user_id or "anonymous"

        if user_id == "anonymous":
            return UserFeedbackHistory(
                user_id=user_id,
                favorites=[],
                rejections=[],
                total_views=0,
                patterns={},
            )

        # Get state
        from app.memory import AgentState
        persistence = get_persistence_backend()
        state_dict = await persistence.load(user_id)
        state = AgentState.model_validate(state_dict) if state_dict else None

        if not state:
            return UserFeedbackHistory(
                user_id=user_id,
                favorites=[],
                rejections=[],
                total_views=0,
                patterns={},
            )

        # Get historical patterns
        feedback_service = get_feedback_learning_service()
        historical = feedback_service.get_historical_preferences(user_id)

        return UserFeedbackHistory(
            user_id=user_id,
            favorites=state.working.search_state.favorited_parcels,
            rejections=state.working.search_state.rejected_parcels,
            total_views=len(state.working.search_state.current_results),
            patterns=historical.get("patterns", {}),
        )

    except Exception as e:
        logger.error(f"Get feedback history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CLEAR FEEDBACK
# =============================================================================

@router.delete("/", response_model=FeedbackResponse)
async def clear_feedback(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Clear all user feedback (favorites and rejections).

    Useful for starting fresh or testing.
    """
    try:
        user_id = x_user_id or "anonymous"

        if user_id == "anonymous":
            return FeedbackResponse(
                success=True,
                message="No feedback to clear for anonymous user",
                parcel_id="",
                action="clear",
            )

        # Get and update state
        from app.memory import AgentState
        persistence = get_persistence_backend()
        state_dict = await persistence.load(user_id)

        if state_dict:
            state = AgentState.model_validate(state_dict)
            state.working.search_state.favorited_parcels = []
            state.working.search_state.rejected_parcels = []
            await persistence.save(user_id, state.model_dump())

        return FeedbackResponse(
            success=True,
            message="Feedback wyczyszczony",
            parcel_id="",
            action="clear",
        )

    except Exception as e:
        logger.error(f"Clear feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
