"""
Conversation API v4 - Single agent with notepad-driven flow.

Replaces conversation_v2.py (AgentCoordinator + multi-agent).
Uses the new Agent + Session + Notepad architecture.

WebSocket for streaming, REST for non-streaming and session management.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger

from app.engine.agent import Agent
from app.engine.session import Session
from app.engine.notepad import Notepad
from app.profile import ProfileManager
from app.models.schemas import ChatMessage, ChatResponse
from app.services.database import redis_cache
from app.config import settings


router = APIRouter(prefix="/v4/conversation", tags=["conversation_v4"])

# Redis keys
SESSION_PREFIX = "session:"
SESSION_TTL = 24 * 3600  # 24 hours

# Singleton instances
_agent: Optional[Agent] = None
_profile_manager: Optional[ProfileManager] = None


def get_agent() -> Agent:
    """Get or create the Agent singleton."""
    global _agent
    if _agent is None:
        _agent = Agent()
        logger.info(f"Created Agent (model={_agent.model})")
    return _agent


def get_profile_manager() -> ProfileManager:
    """Get or create the ProfileManager singleton."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


async def load_session(user_id: str, session_id: Optional[str] = None) -> Session:
    """Load session from Redis or create a new one."""
    if session_id:
        try:
            data = await redis_cache.get(f"{SESSION_PREFIX}{session_id}")
            if data:
                session = Session.from_dict(json.loads(data))
                logger.debug(f"Loaded session {session_id} for user {user_id}")
                return session
        except Exception as e:
            logger.warning(f"Failed to load session from Redis: {e}")

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    session = Session(session_id=new_session_id, user_id=user_id)

    # Load user profile and seed notepad with cross-session data
    pm = get_profile_manager()
    profile = await pm.load(user_id)
    if profile.session_count > 0:
        # Returning user: seed notepad with known facts
        if profile.preferred_locations:
            session.notepad.set_user_fact("preferred_locations", profile.preferred_locations)
        if profile.budget_min:
            session.notepad.set_user_fact("budget_min", profile.budget_min)
        if profile.budget_max:
            session.notepad.set_user_fact("budget_max", profile.budget_max)
        if profile.family_info:
            session.notepad.set_user_fact("family", profile.family_info)
        if profile.name:
            session.notepad.set_user_fact("name", profile.name)
        if profile.all_favorites:
            session.notepad.favorites = list(profile.all_favorites)

        logger.info(f"Seeded session for returning user {user_id} (sessions: {profile.session_count})")

    return session


async def save_session(session: Session) -> None:
    """Save session to Redis."""
    try:
        data = json.dumps(session.to_dict(), ensure_ascii=False, default=str)
        await redis_cache.set(
            f"{SESSION_PREFIX}{session.session_id}",
            data,
            expire=SESSION_TTL,
        )
    except Exception as e:
        logger.warning(f"Failed to save session to Redis: {e}")


async def finalize_session_profile(session: Session) -> None:
    """Merge session data into user profile on disconnect.

    Only finalizes if the session had actual activity (messages exchanged).
    Skips empty sessions from rapid connect/disconnect cycles.
    """
    try:
        # Skip empty sessions — no messages means no useful data to merge
        if not session.messages:
            return

        pm = get_profile_manager()
        notepad_dict = session.notepad.to_dict()
        if not notepad_dict:
            return
        await pm.finalize_session(session.user_id, notepad_dict)
    except Exception as e:
        logger.warning(f"Failed to finalize session profile: {e}")


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agent conversation.

    Protocol:
    1. Client connects
    2. Client sends: {"type": "init", "user_id": "optional-id", "session_id": "optional"}
    3. Server responds: {"type": "session", "user_id": "xxx", "session_id": "xxx", "notepad": {...}}
    4. Client sends: {"type": "message", "content": "user message"}
    5. Server streams events:
       - {"type": "message", "data": {"text": "...", "delta": true/false}}
       - {"type": "tool_call", "data": {"name": "...", "id": "...", ...}}
       - {"type": "tool_result", "data": {"name": "...", "result": {...}, "duration_ms": N}}
       - {"type": "done", "data": {"session_id": "..."}}
       - {"type": "error", "data": {"message": "..."}}
    6. Repeat 4-5
    """
    await websocket.accept()

    session: Optional[Session] = None
    agent = get_agent()

    try:
        # Wait for init message
        init_data = await websocket.receive_json()

        if init_data.get("type") != "init":
            await websocket.send_json({
                "type": "error",
                "data": {"message": "First message must be type 'init'"},
            })
            await websocket.close()
            return

        # Get or create user/session
        user_id = init_data.get("user_id") or str(uuid.uuid4())
        session_id = init_data.get("session_id")

        session = await load_session(user_id, session_id)

        # Send session info
        await websocket.send_json({
            "type": "session",
            "user_id": user_id,
            "session_id": session.session_id,
            "notepad": session.notepad.to_dict(),
        })

        logger.info(f"WebSocket connected: user={user_id}, session={session.session_id}")

        # Message loop
        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "message":
                    content = data.get("content", "").strip()
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "Empty message"},
                        })
                        continue

                    # Process message through agent with streaming
                    async for event in agent.run_streaming(session, content):
                        await websocket.send_json(event)

                    # Save session after each turn
                    await save_session(session)

                elif data.get("type") == "get_notepad":
                    await websocket.send_json({
                        "type": "notepad",
                        "data": session.notepad.to_dict(),
                    })

                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": f"Unknown message type: {data.get('type')}"},
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Invalid JSON"},
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={session.user_id if session else 'unknown'}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)},
            })
        except Exception:
            pass

    finally:
        # Finalize: save session and merge into profile
        if session:
            await save_session(session)
            await finalize_session_profile(session)


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Non-streaming chat endpoint.

    For clients that don't support WebSocket.
    """
    user_id = message.session_id or str(uuid.uuid4())
    agent = get_agent()

    session = await load_session(user_id, message.session_id)

    # Collect events
    response_text = ""
    tool_calls = []

    async for event in agent.run(session, message.content):
        event_type = event.get("type")
        event_data = event.get("data", {})

        if event_type == "message":
            response_text += event_data.get("text", "")
        elif event_type == "tool_call":
            tool_calls.append(event_data)
        elif event_type == "error":
            raise HTTPException(
                status_code=500,
                detail=event_data.get("message", "Agent error"),
            )

    # Save session
    await save_session(session)

    return ChatResponse(
        session_id=session.session_id,
        message=response_text,
        tool_calls=tool_calls,
        map_data=None,
    )


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get session state including notepad."""
    try:
        data = await redis_cache.get(f"{SESSION_PREFIX}{session_id}")
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")

        session_data = json.loads(data)
        return {
            "session_id": session_data["session_id"],
            "user_id": session_data["user_id"],
            "notepad": session_data.get("notepad", {}),
            "message_count": len(session_data.get("messages", [])),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at"),
            "compaction_count": session_data.get("compaction_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a session."""
    try:
        data = await redis_cache.get(f"{SESSION_PREFIX}{session_id}")
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")

        session_data = json.loads(data)
        messages = session_data.get("messages", [])

        history = []
        for msg in messages:
            history.append({
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": msg.get("timestamp"),
                "has_tool_calls": bool(msg.get("tool_calls")),
            })

        return {
            "session_id": session_id,
            "history": history,
            "compaction_summary": session_data.get("compaction_summary"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        await redis_cache.delete(f"{SESSION_PREFIX}{session_id}")
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/finalize")
async def finalize_session(session_id: str):
    """Finalize session and merge data into user profile."""
    try:
        data = await redis_cache.get(f"{SESSION_PREFIX}{session_id}")
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = Session.from_dict(json.loads(data))
        await finalize_session_profile(session)

        return {
            "status": "finalized",
            "session_id": session_id,
            "user_id": session.user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
