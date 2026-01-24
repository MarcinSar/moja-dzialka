"""
Persistence Layer - State storage backends.

Supports multiple backends:
- InMemoryBackend: For development/testing
- RedisBackend: For production hot cache
- RedisPostgresBackend: For production with cold storage
"""

import os
from typing import Optional

from .backend import PersistenceBackend
from .memory_backend import InMemoryBackend
from .redis_backend import RedisBackend
from .redis_postgres_backend import RedisPostgresBackend

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Default backend instance (singleton)
_default_backend: Optional[PersistenceBackend] = None


def get_persistence_backend(backend_type: str = "memory") -> PersistenceBackend:
    """Get or create a persistence backend.

    Args:
        backend_type: One of "memory", "redis", "redis_postgres"

    Returns:
        PersistenceBackend instance
    """
    global _default_backend

    if _default_backend is not None:
        return _default_backend

    if backend_type == "memory":
        _default_backend = InMemoryBackend()
    elif backend_type == "redis":
        _default_backend = RedisBackend(redis_url=REDIS_URL)
    elif backend_type == "redis_postgres":
        _default_backend = RedisPostgresBackend(redis_url=REDIS_URL)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

    return _default_backend


def reset_persistence_backend() -> None:
    """Reset the default backend (for testing)."""
    global _default_backend
    _default_backend = None


# Alias for convenience
create_backend = get_persistence_backend

__all__ = [
    "PersistenceBackend",
    "InMemoryBackend",
    "RedisBackend",
    "RedisPostgresBackend",
    "get_persistence_backend",
    "create_backend",
    "reset_persistence_backend",
]
