"""
In-Memory Persistence Backend.

Simple dict-based storage for development and testing.
State is lost when the process restarts.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from loguru import logger

from .backend import PersistenceBackend


class InMemoryBackend(PersistenceBackend):
    """In-memory persistence backend.

    Uses a simple dict for storage. Good for development.
    Optionally supports TTL for automatic cleanup.
    """

    def __init__(self, ttl_hours: int = 24):
        """Initialize in-memory backend.

        Args:
            ttl_hours: Hours before state expires (0 = no expiry)
        """
        self._store: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = timedelta(hours=ttl_hours) if ttl_hours > 0 else None

    async def save(self, user_id: str, state: Dict[str, Any]) -> None:
        """Save state to memory."""
        self._store[user_id] = state.copy()
        self._timestamps[user_id] = datetime.utcnow()
        logger.debug(f"Saved state for user {user_id}")

    async def load(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load state from memory."""
        # Check TTL
        if self._ttl and user_id in self._timestamps:
            age = datetime.utcnow() - self._timestamps[user_id]
            if age > self._ttl:
                await self.delete(user_id)
                return None

        state = self._store.get(user_id)
        if state:
            logger.debug(f"Loaded state for user {user_id}")
            return state.copy()
        return None

    async def exists(self, user_id: str) -> bool:
        """Check if state exists."""
        # Check TTL
        if self._ttl and user_id in self._timestamps:
            age = datetime.utcnow() - self._timestamps[user_id]
            if age > self._ttl:
                await self.delete(user_id)
                return False

        return user_id in self._store

    async def delete(self, user_id: str) -> None:
        """Delete state from memory."""
        self._store.pop(user_id, None)
        self._timestamps.pop(user_id, None)
        logger.debug(f"Deleted state for user {user_id}")

    async def list_users(self) -> list:
        """List all stored user IDs."""
        # Clean expired entries first
        if self._ttl:
            now = datetime.utcnow()
            expired = [
                uid for uid, ts in self._timestamps.items()
                if now - ts > self._ttl
            ]
            for uid in expired:
                await self.delete(uid)

        return list(self._store.keys())

    async def clear_all(self) -> None:
        """Clear all stored state."""
        self._store.clear()
        self._timestamps.clear()
        logger.debug("Cleared all state")
