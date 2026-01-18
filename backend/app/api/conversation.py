"""
Conversation API endpoints.

WebSocket for streaming agent events and REST for session management.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger

from app.agent import ParcelAgent, AgentEvent, EventType
from app.agent.tools import reset_state, get_state
from app.models.schemas import (
    ChatMessage,
    ChatResponse,
    SessionInfo,
    ErrorResponse,
)


router = APIRouter(prefix="/conversation", tags=["conversation"])


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

# In-memory session storage (use Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}


def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, ParcelAgent]:
    """Get existing session or create new one."""
    if session_id and session_id in sessions:
        session = sessions[session_id]
        session["last_access"] = datetime.utcnow()
        return session_id, session["agent"]

    # Create new session
    new_id = str(uuid.uuid4())
    agent = ParcelAgent()
    sessions[new_id] = {
        "agent": agent,
        "created_at": datetime.utcnow(),
        "last_access": datetime.utcnow(),
        "message_count": 0,
    }

    logger.info(f"Created new session: {new_id}")
    return new_id, agent


def cleanup_old_sessions(max_age_hours: int = 24):
    """Remove sessions older than max_age_hours."""
    now = datetime.utcnow()
    to_remove = []

    for session_id, session in sessions.items():
        age = (now - session["last_access"]).total_seconds() / 3600
        if age > max_age_hours:
            to_remove.append(session_id)

    for session_id in to_remove:
        del sessions[session_id]
        logger.info(f"Cleaned up session: {session_id}")


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agent conversation.

    Protocol:
    1. Client connects
    2. Client sends: {"type": "init", "session_id": "optional-id"}
    3. Server responds: {"type": "session", "session_id": "xxx"}
    4. Client sends: {"type": "message", "content": "user message"}
    5. Server streams events: {"type": "thinking|tool_call|tool_result|message|done|error", "data": {...}}
    6. Repeat 4-5
    """
    await websocket.accept()

    session_id = None
    agent = None

    try:
        # Wait for init message
        init_data = await websocket.receive_json()

        if init_data.get("type") != "init":
            await websocket.send_json({
                "type": "error",
                "data": {"message": "First message must be init"}
            })
            await websocket.close()
            return

        # Get or create session
        requested_session_id = init_data.get("session_id")
        session_id, agent = get_or_create_session(requested_session_id)

        # Send session info
        await websocket.send_json({
            "type": "session",
            "session_id": session_id,
            "state": get_state().to_dict(),
        })

        logger.info(f"WebSocket connected: {session_id}")

        # Message loop
        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "message":
                    content = data.get("content", "").strip()
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "Empty message"}
                        })
                        continue

                    # Update session stats
                    sessions[session_id]["message_count"] += 1
                    sessions[session_id]["last_access"] = datetime.utcnow()

                    # Stream agent events
                    async for event in agent.chat(content):
                        await websocket.send_json(event.to_dict())

                elif data.get("type") == "clear":
                    # Clear conversation history
                    agent.clear_history()
                    await websocket.send_json({
                        "type": "cleared",
                        "state": get_state().to_dict(),
                    })

                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": f"Unknown message type: {data.get('type')}"}
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Invalid JSON"}
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Non-streaming chat endpoint.

    For clients that don't support WebSocket.
    Returns full response after processing.
    """
    session_id, agent = get_or_create_session(message.session_id)

    # Update session stats
    sessions[session_id]["message_count"] += 1
    sessions[session_id]["last_access"] = datetime.utcnow()

    # Collect events
    response_text = ""
    tool_calls = []
    map_data = None

    async for event in agent.chat(message.content):
        if event.type == EventType.MESSAGE:
            response_text = event.data.get("content", "")
        elif event.type == EventType.TOOL_CALL:
            tool_calls.append(event.data)
            # Check for map data
            if event.data.get("tool") == "generate_map_data":
                # Will be in tool_result
                pass
        elif event.type == EventType.TOOL_RESULT:
            if "geojson" in str(event.data.get("result_preview", "")):
                # Map data was generated
                pass
        elif event.type == EventType.ERROR:
            raise HTTPException(
                status_code=500,
                detail=event.data.get("message", "Agent error")
            )

    return ChatResponse(
        session_id=session_id,
        message=response_text,
        tool_calls=tool_calls,
        map_data=map_data,
    )


@router.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session information."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    agent: ParcelAgent = session["agent"]

    return SessionInfo(
        session_id=session_id,
        created_at=session["created_at"],
        message_count=session["message_count"],
        agent_state=get_state().to_dict(),
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    reset_state()

    return {"status": "deleted", "session_id": session_id}


@router.get("/session/{session_id}/history")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    agent: ParcelAgent = sessions[session_id]["agent"]

    # Filter out tool results for cleaner history
    history = []
    for msg in agent.get_history():
        if msg["role"] == "user":
            # Check if it's a tool result
            if isinstance(msg["content"], list):
                continue  # Skip tool results
            history.append({
                "role": "user",
                "content": msg["content"],
            })
        elif msg["role"] == "assistant":
            # Extract text content
            text = ""
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
            if text:
                history.append({
                    "role": "assistant",
                    "content": text,
                })

    return {"session_id": session_id, "history": history}
