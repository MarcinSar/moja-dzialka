"""
Conversation API v2 - Using new Software 3.0 architecture.

WebSocket for streaming agent events and REST for session management.
Uses the new AgentCoordinator with 7-layer memory model.
"""

import asyncio
import json
import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger

from app.engine import AgentCoordinator
from app.memory import AgentState
from app.models.schemas import (
    ChatMessage,
    ChatResponse,
    SessionInfo,
)

# Redis connection for LiDAR progress events
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Persistence backend setting
PERSISTENCE_BACKEND = os.getenv("PERSISTENCE_BACKEND", "memory")

router = APIRouter(prefix="/v2/conversation", tags=["conversation_v2"])

# Global coordinator instance
_coordinator: Optional[AgentCoordinator] = None


def get_coordinator() -> AgentCoordinator:
    """Get or create the agent coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator(persistence_backend=PERSISTENCE_BACKEND)
        logger.info(f"Created AgentCoordinator with backend: {PERSISTENCE_BACKEND}")
    return _coordinator


async def lidar_progress_listener(session_id: str, websocket: WebSocket):
    """Listen for LiDAR progress events and forward to WebSocket."""
    try:
        redis_client = aioredis.from_url(REDIS_URL)
        pubsub = redis_client.pubsub()
        channel = f"lidar:progress:{session_id}"

        await pubsub.subscribe(channel)
        logger.debug(f"Subscribed to LiDAR progress channel: {channel}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception as e:
                    logger.error(f"Error forwarding LiDAR event: {e}")
                    break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"LiDAR listener error: {e}")
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
        except:
            pass


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws")
async def websocket_chat_v2(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agent conversation (v2 architecture).

    Protocol:
    1. Client connects
    2. Client sends: {"type": "init", "user_id": "optional-id", "session_id": "optional"}
    3. Server responds: {"type": "session", "user_id": "xxx", "session_id": "xxx", "state": {...}}
    4. Client sends: {"type": "message", "content": "user message"}
    5. Server streams events: {"type": "thinking|skill_selected|tool_call|tool_result|message|done|error", "data": {...}}
    6. Repeat 4-5
    """
    await websocket.accept()

    user_id = None
    session_id = None
    coordinator = get_coordinator()

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

        # Get or create user/session
        user_id = init_data.get("user_id") or str(uuid.uuid4())
        session_id = init_data.get("session_id")

        # Load state to get session info
        state_dict = await coordinator.get_state(user_id)
        if state_dict:
            session_id = state_dict.get("session_id", session_id)
        else:
            session_id = session_id or str(uuid.uuid4())

        # Send session info
        await websocket.send_json({
            "type": "session",
            "user_id": user_id,
            "session_id": session_id,
            "state": state_dict or {},
        })

        logger.info(f"WebSocket v2 connected: user={user_id}, session={session_id}")

        # Start LiDAR progress listener
        lidar_listener_task = asyncio.create_task(
            lidar_progress_listener(session_id, websocket)
        )

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

                    # Process message through coordinator
                    async for event in coordinator.process_message(
                        user_id=user_id,
                        message=content,
                        session_id=session_id,
                    ):
                        await websocket.send_json(event)

                elif data.get("type") == "clear":
                    # Clear user state
                    await coordinator.clear_state(user_id)
                    await websocket.send_json({
                        "type": "cleared",
                        "user_id": user_id,
                    })

                elif data.get("type") == "get_state":
                    # Return current state
                    state = await coordinator.get_state(user_id)
                    await websocket.send_json({
                        "type": "state",
                        "state": state or {},
                    })

                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                elif data.get("type") == "request_lidar":
                    # Start LiDAR processing for a parcel
                    from app.tasks.lidar_tasks import process_lidar_for_parcel

                    parcel_id = data.get("parcel_id")
                    lat = data.get("lat")
                    lon = data.get("lon")
                    parcel_bbox = data.get("parcel_bbox")

                    if not all([parcel_id, lat, lon]):
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "Missing parcel_id, lat, or lon"}
                        })
                        continue

                    task = process_lidar_for_parcel.delay(
                        parcel_id=parcel_id,
                        lat=lat,
                        lon=lon,
                        session_id=session_id,
                        parcel_bbox=parcel_bbox,
                    )

                    await websocket.send_json({
                        "type": "lidar_started",
                        "job_id": task.id,
                        "parcel_id": parcel_id,
                    })

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
        logger.info(f"WebSocket v2 disconnected: user={user_id}")

    except Exception as e:
        logger.error(f"WebSocket v2 error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass

    finally:
        if 'lidar_listener_task' in locals():
            lidar_listener_task.cancel()
            try:
                await lidar_listener_task
            except asyncio.CancelledError:
                pass


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_v2(message: ChatMessage):
    """
    Non-streaming chat endpoint (v2 architecture).

    For clients that don't support WebSocket.
    """
    coordinator = get_coordinator()

    # Use session_id as user_id for REST API compatibility
    user_id = message.session_id or str(uuid.uuid4())

    # Collect events
    response_text = ""
    tool_calls = []
    phase = None

    async for event in coordinator.process_message(
        user_id=user_id,
        message=message.content,
    ):
        event_type = event.get("type")
        event_data = event.get("data", {})

        if event_type == "message":
            if event_data.get("is_complete"):
                pass  # Complete signal
            else:
                response_text += event_data.get("content", "")

        elif event_type == "tool_call":
            tool_calls.append(event_data)

        elif event_type == "done":
            phase = event_data.get("phase")

        elif event_type == "error":
            raise HTTPException(
                status_code=500,
                detail=event_data.get("message", "Agent error")
            )

    return ChatResponse(
        session_id=user_id,
        message=response_text,
        tool_calls=tool_calls,
        map_data=None,
    )


@router.get("/user/{user_id}/state")
async def get_user_state(user_id: str):
    """Get current state for a user."""
    coordinator = get_coordinator()
    state = await coordinator.get_state(user_id)

    if not state:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "state": state,
    }


@router.delete("/user/{user_id}")
async def delete_user(user_id: str):
    """Delete user state."""
    coordinator = get_coordinator()
    await coordinator.clear_state(user_id)

    return {"status": "deleted", "user_id": user_id}


@router.post("/user/{user_id}/finalize")
async def finalize_session(user_id: str):
    """Finalize and compress current session."""
    coordinator = get_coordinator()
    await coordinator.finalize_session(user_id)

    return {"status": "finalized", "user_id": user_id}


@router.get("/user/{user_id}/history")
async def get_user_history(user_id: str):
    """Get conversation history for a user."""
    coordinator = get_coordinator()
    state = await coordinator.get_state(user_id)

    if not state:
        raise HTTPException(status_code=404, detail="User not found")

    # Extract history from working memory
    working = state.get("working", {})
    buffer = working.get("conversation_buffer", [])

    history = []
    for msg in buffer:
        history.append({
            "role": msg.get("role"),
            "content": msg.get("content"),
            "timestamp": msg.get("timestamp"),
        })

    return {"user_id": user_id, "history": history}


@router.get("/user/{user_id}/funnel")
async def get_funnel_progress(user_id: str):
    """Get funnel progress for a user."""
    coordinator = get_coordinator()
    state = await coordinator.get_state(user_id)

    if not state:
        raise HTTPException(status_code=404, detail="User not found")

    workflow = state.get("workflow", {})
    progress = workflow.get("funnel_progress", {})
    phase = state.get("working", {}).get("current_phase", "DISCOVERY")

    return {
        "user_id": user_id,
        "current_phase": phase,
        "progress": progress,
        "engagement_level": progress.get("engagement_level", "low"),
        "intent_confidence": progress.get("intent_confidence", 0.0),
    }
