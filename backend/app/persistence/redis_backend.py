"""
Redis Persistence Backend.

Hot cache for active sessions. Fast reads/writes with TTL.
"""

from typing import Optional, Dict, Any
import json

from loguru import logger

from .backend import PersistenceBackend

# Redis is optional - fall back to memory if not available
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed - RedisBackend will fall back to memory")


class RedisBackend(PersistenceBackend):
    """Redis persistence backend.

    Uses Redis for fast hot cache with automatic TTL.
    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 86400,  # 24 hours
        key_prefix: str = "state:",
    ):
        """Initialize Redis backend.

        Args:
            redis_url: Redis connection URL (default: localhost)
            ttl_seconds: TTL for cached state
            key_prefix: Prefix for Redis keys
        """
        self._ttl = ttl_seconds
        self._prefix = key_prefix
        self._redis: Optional[redis.Redis] = None
        self._fallback: Dict[str, Dict[str, Any]] = {}

        if REDIS_AVAILABLE:
            redis_url = redis_url or "redis://localhost:6379/0"
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                logger.info(f"Connected to Redis at {redis_url}")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
                self._redis = None

    def _key(self, user_id: str) -> str:
        """Generate Redis key for user."""
        return f"{self._prefix}{user_id}"

    async def save(self, user_id: str, state: Dict[str, Any]) -> None:
        """Save state to Redis."""
        key = self._key(user_id)
        state_json = json.dumps(state, ensure_ascii=False, default=str)

        if self._redis:
            try:
                await self._redis.setex(key, self._ttl, state_json)
                logger.debug(f"Saved state to Redis for user {user_id}")
                return
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")

        # Fallback to memory
        self._fallback[user_id] = state.copy()

    async def load(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load state from Redis."""
        key = self._key(user_id)

        if self._redis:
            try:
                state_json = await self._redis.get(key)
                if state_json:
                    logger.debug(f"Loaded state from Redis for user {user_id}")
                    return json.loads(state_json)
                return None
            except Exception as e:
                logger.warning(f"Redis load failed: {e}")

        # Fallback to memory
        return self._fallback.get(user_id)

    async def exists(self, user_id: str) -> bool:
        """Check if state exists in Redis."""
        key = self._key(user_id)

        if self._redis:
            try:
                return await self._redis.exists(key) > 0
            except Exception as e:
                logger.warning(f"Redis exists check failed: {e}")

        return user_id in self._fallback

    async def delete(self, user_id: str) -> None:
        """Delete state from Redis."""
        key = self._key(user_id)

        if self._redis:
            try:
                await self._redis.delete(key)
                logger.debug(f"Deleted state from Redis for user {user_id}")
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        self._fallback.pop(user_id, None)

    async def list_users(self) -> list:
        """List all user IDs in Redis."""
        if self._redis:
            try:
                keys = await self._redis.keys(f"{self._prefix}*")
                return [k.replace(self._prefix, "") for k in keys]
            except Exception as e:
                logger.warning(f"Redis keys failed: {e}")

        return list(self._fallback.keys())

    async def clear_all(self) -> None:
        """Clear all state in Redis."""
        if self._redis:
            try:
                keys = await self._redis.keys(f"{self._prefix}*")
                if keys:
                    await self._redis.delete(*keys)
                logger.debug("Cleared all state from Redis")
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        self._fallback.clear()

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
