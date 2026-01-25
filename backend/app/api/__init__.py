"""
API routers for moja-dzialka.

Routers:
- conversation: WebSocket and REST endpoints for agent chat (v2 architecture)
- search: REST endpoints for parcel search
- lidar: REST endpoints for LiDAR 3D visualization
- leads: REST endpoints for lead capture
"""

from app.api.conversation_v2 import router as conversation_router
from app.api.search import router as search_router
from app.api.lidar import router as lidar_router
from app.api.leads import router as leads_router

__all__ = [
    "conversation_router",
    "search_router",
    "lidar_router",
    "leads_router",
]
