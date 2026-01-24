"""
Persistence Backend Interface.

All persistence backends implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class PersistenceBackend(ABC):
    """Abstract base class for persistence backends.

    Provides a simple key-value interface for storing agent state.
    Keys are user IDs, values are serialized state dicts.
    """

    @abstractmethod
    async def save(self, user_id: str, state: Dict[str, Any]) -> None:
        """Save state for a user.

        Args:
            user_id: Unique user identifier
            state: State dict to save
        """
        pass

    @abstractmethod
    async def load(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load state for a user.

        Args:
            user_id: Unique user identifier

        Returns:
            State dict if exists, None otherwise
        """
        pass

    @abstractmethod
    async def exists(self, user_id: str) -> bool:
        """Check if state exists for a user.

        Args:
            user_id: Unique user identifier

        Returns:
            True if state exists
        """
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> None:
        """Delete state for a user.

        Args:
            user_id: Unique user identifier
        """
        pass

    async def list_users(self) -> list:
        """List all user IDs with stored state.

        Returns:
            List of user IDs
        """
        return []

    async def clear_all(self) -> None:
        """Clear all stored state (for testing)."""
        pass
