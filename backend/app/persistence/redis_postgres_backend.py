"""
Redis + PostgreSQL Persistence Backend.

Hybrid backend:
- Redis: Hot cache (active sessions, TTL 24h)
- Postgres: Cold storage (persistent, queryable)

Write-through caching: writes go to both, reads prefer Redis.
"""

from typing import Optional, Dict, Any
import json
from datetime import datetime

from loguru import logger

from .backend import PersistenceBackend
from .redis_backend import RedisBackend

# SQLAlchemy is optional
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
    from sqlalchemy import text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.warning("sqlalchemy not installed - PostgreSQL storage unavailable")


class RedisPostgresBackend(PersistenceBackend):
    """Hybrid Redis + PostgreSQL backend.

    Uses Redis as hot cache with PostgreSQL as persistent storage.
    Provides both fast access and durability.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        postgres_url: Optional[str] = None,
        ttl_seconds: int = 86400,
    ):
        """Initialize hybrid backend.

        Args:
            redis_url: Redis connection URL
            postgres_url: PostgreSQL connection URL
            ttl_seconds: Redis TTL
        """
        # Redis cache
        self._redis = RedisBackend(redis_url=redis_url, ttl_seconds=ttl_seconds)

        # PostgreSQL storage
        self._db: Optional[AsyncEngine] = None
        if SQLALCHEMY_AVAILABLE and postgres_url:
            try:
                self._db = create_async_engine(postgres_url, echo=False)
                logger.info("Connected to PostgreSQL")
            except Exception as e:
                logger.warning(f"Could not connect to PostgreSQL: {e}")

    async def _ensure_table(self) -> None:
        """Ensure user_states table exists."""
        if not self._db:
            return

        create_sql = """
            CREATE TABLE IF NOT EXISTS user_states (
                user_id VARCHAR(255) PRIMARY KEY,
                state JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_user_states_updated
                ON user_states (updated_at);
        """

        try:
            async with self._db.begin() as conn:
                await conn.execute(text(create_sql))
        except Exception as e:
            logger.warning(f"Could not create table: {e}")

    async def save(self, user_id: str, state: Dict[str, Any]) -> None:
        """Save state to both Redis and PostgreSQL."""
        # 1. Write to Redis (hot cache)
        await self._redis.save(user_id, state)

        # 2. Write to PostgreSQL (persistent)
        if self._db:
            await self._ensure_table()
            state_json = json.dumps(state, ensure_ascii=False, default=str)

            upsert_sql = """
                INSERT INTO user_states (user_id, state, updated_at)
                VALUES (:user_id, :state::jsonb, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    updated_at = NOW()
            """

            try:
                async with self._db.begin() as conn:
                    await conn.execute(
                        text(upsert_sql),
                        {"user_id": user_id, "state": state_json}
                    )
                logger.debug(f"Saved state to PostgreSQL for user {user_id}")
            except Exception as e:
                logger.warning(f"PostgreSQL save failed: {e}")

    async def load(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load state, preferring Redis cache."""
        # 1. Try Redis first (fast path)
        state = await self._redis.load(user_id)
        if state:
            return state

        # 2. Fallback to PostgreSQL
        if self._db:
            await self._ensure_table()

            select_sql = """
                SELECT state FROM user_states
                WHERE user_id = :user_id
            """

            try:
                async with self._db.connect() as conn:
                    result = await conn.execute(
                        text(select_sql),
                        {"user_id": user_id}
                    )
                    row = result.first()

                    if row:
                        state = row[0]  # JSONB is auto-parsed
                        if isinstance(state, str):
                            state = json.loads(state)

                        # Refresh Redis cache
                        await self._redis.save(user_id, state)

                        logger.debug(f"Loaded state from PostgreSQL for user {user_id}")
                        return state

            except Exception as e:
                logger.warning(f"PostgreSQL load failed: {e}")

        return None

    async def exists(self, user_id: str) -> bool:
        """Check if state exists."""
        # Check Redis first
        if await self._redis.exists(user_id):
            return True

        # Check PostgreSQL
        if self._db:
            await self._ensure_table()

            check_sql = """
                SELECT 1 FROM user_states
                WHERE user_id = :user_id
                LIMIT 1
            """

            try:
                async with self._db.connect() as conn:
                    result = await conn.execute(
                        text(check_sql),
                        {"user_id": user_id}
                    )
                    return result.first() is not None
            except Exception as e:
                logger.warning(f"PostgreSQL exists check failed: {e}")

        return False

    async def delete(self, user_id: str) -> None:
        """Delete state from both Redis and PostgreSQL."""
        # Delete from Redis
        await self._redis.delete(user_id)

        # Delete from PostgreSQL
        if self._db:
            await self._ensure_table()

            delete_sql = """
                DELETE FROM user_states
                WHERE user_id = :user_id
            """

            try:
                async with self._db.begin() as conn:
                    await conn.execute(
                        text(delete_sql),
                        {"user_id": user_id}
                    )
                logger.debug(f"Deleted state from PostgreSQL for user {user_id}")
            except Exception as e:
                logger.warning(f"PostgreSQL delete failed: {e}")

    async def list_users(self) -> list:
        """List all user IDs from PostgreSQL."""
        if self._db:
            await self._ensure_table()

            select_sql = """
                SELECT user_id FROM user_states
                ORDER BY updated_at DESC
            """

            try:
                async with self._db.connect() as conn:
                    result = await conn.execute(text(select_sql))
                    return [row[0] for row in result.fetchall()]
            except Exception as e:
                logger.warning(f"PostgreSQL list failed: {e}")

        return await self._redis.list_users()

    async def clear_all(self) -> None:
        """Clear all state from both Redis and PostgreSQL."""
        await self._redis.clear_all()

        if self._db:
            await self._ensure_table()

            try:
                async with self._db.begin() as conn:
                    await conn.execute(text("TRUNCATE user_states"))
                logger.debug("Cleared all state from PostgreSQL")
            except Exception as e:
                logger.warning(f"PostgreSQL clear failed: {e}")

    async def close(self) -> None:
        """Close connections."""
        await self._redis.close()
        if self._db:
            await self._db.dispose()

    # Analytics queries (PostgreSQL-specific)
    async def get_active_users_count(self, hours: int = 24) -> int:
        """Count active users in the last N hours."""
        if not self._db:
            return len(await self._redis.list_users())

        await self._ensure_table()

        count_sql = """
            SELECT COUNT(*) FROM user_states
            WHERE updated_at > NOW() - INTERVAL ':hours hours'
        """

        try:
            async with self._db.connect() as conn:
                result = await conn.execute(
                    text(count_sql.replace(":hours", str(hours)))
                )
                return result.scalar() or 0
        except Exception as e:
            logger.warning(f"PostgreSQL count failed: {e}")
            return 0

    async def get_funnel_stats(self) -> Dict[str, int]:
        """Get funnel stage statistics."""
        if not self._db:
            return {}

        await self._ensure_table()

        stats_sql = """
            SELECT
                state->'working'->>'current_phase' as phase,
                COUNT(*) as count
            FROM user_states
            GROUP BY phase
        """

        try:
            async with self._db.connect() as conn:
                result = await conn.execute(text(stats_sql))
                return {row[0]: row[1] for row in result.fetchall()}
        except Exception as e:
            logger.warning(f"PostgreSQL stats failed: {e}")
            return {}
