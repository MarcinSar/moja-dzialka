"""
Database connection managers for all data stores.

Provides connection pooling and async support for:
- PostGIS (PostgreSQL with spatial extensions)
- Neo4j (Graph database)
- Milvus (Vector database)
- Redis (Cache)
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from neo4j import GraphDatabase, AsyncGraphDatabase
from pymilvus import connections, Collection, utility
import redis.asyncio as redis

from app.config import settings


# =============================================================================
# POSTGIS (SQLALCHEMY)
# =============================================================================

class PostGISManager:
    """PostgreSQL/PostGIS connection manager."""

    def __init__(self):
        self._engine = None
        self._async_engine = None
        self._session_factory = None

    def connect(self):
        """Create synchronous connection."""
        if self._engine is None:
            self._engine = create_engine(
                settings.postgres_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
            logger.info(f"PostGIS connected: {settings.postgres_host}:{settings.postgres_port}")
        return self._engine

    async def connect_async(self):
        """Create async connection."""
        if self._async_engine is None:
            async_url = settings.postgres_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            self._async_engine = create_async_engine(
                async_url,
                pool_size=5,
                max_overflow=10,
            )
            self._session_factory = sessionmaker(
                self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info("PostGIS async connected")
        return self._async_engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async session context manager."""
        if self._session_factory is None:
            await self.connect_async()
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def execute_sync(self, query: str, params: dict = None):
        """Execute synchronous query."""
        engine = self.connect()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchall()

    async def execute(self, query: str, params: dict = None):
        """Execute async query."""
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            return result.fetchall()

    async def health_check(self) -> bool:
        """Check database connection."""
        try:
            await self.connect_async()
            async with self.session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"PostGIS health check failed: {e}")
            return False

    async def close(self):
        """Close connections."""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._engine:
            self._engine.dispose()


# =============================================================================
# NEO4J
# =============================================================================

class Neo4jManager:
    """Neo4j connection manager."""

    def __init__(self):
        self._driver = None
        self._async_driver = None

    def connect(self):
        """Create synchronous driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            logger.info(f"Neo4j connected: {settings.neo4j_uri}")
        return self._driver

    async def connect_async(self):
        """Create async driver."""
        if self._async_driver is None:
            self._async_driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            logger.info("Neo4j async connected")
        return self._async_driver

    def run_sync(self, query: str, params: dict = None):
        """Execute synchronous Cypher query."""
        driver = self.connect()
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    async def run(self, query: str, params: dict = None):
        """Execute async Cypher query."""
        driver = await self.connect_async()
        async with driver.session() as session:
            result = await session.run(query, params or {})
            return [record.data() async for record in result]

    async def health_check(self) -> bool:
        """Check Neo4j connection."""
        try:
            driver = await self.connect_async()
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                return record["test"] == 1
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def close(self):
        """Close connections."""
        if self._async_driver:
            await self._async_driver.close()
        if self._driver:
            self._driver.close()


# =============================================================================
# MILVUS
# =============================================================================

class MilvusManager:
    """Milvus connection manager."""

    COLLECTION_NAME = "parcels"

    def __init__(self):
        self._connected = False
        self._collection = None

    def connect(self):
        """Connect to Milvus."""
        if not self._connected:
            connections.connect(
                alias="default",
                host=settings.milvus_host,
                port=settings.milvus_port,
            )
            self._connected = True
            logger.info(f"Milvus connected: {settings.milvus_host}:{settings.milvus_port}")

    def get_collection(self, fresh: bool = False) -> Optional[Collection]:
        """Get parcels collection."""
        self.connect()
        if utility.has_collection(self.COLLECTION_NAME):
            if fresh or self._collection is None:
                # Create fresh collection reference
                self._collection = Collection(self.COLLECTION_NAME)
                self._collection.load()
            return self._collection
        return None

    def refresh_collection(self):
        """Refresh collection reference - call if searches fail."""
        logger.info("Refreshing Milvus collection and reconnecting...")
        # Release collection
        if self._collection is not None:
            try:
                self._collection.release()
            except Exception as e:
                logger.warning(f"Failed to release collection: {e}")
        self._collection = None

        # Disconnect and reconnect
        try:
            connections.disconnect("default")
        except Exception:
            pass
        self._connected = False

        # Force reconnect and reload
        self.connect()
        self.get_collection()

    def search(
        self,
        query_vectors: list,
        top_k: int = 10,
        filter_expr: str = None,
        output_fields: list = None,
        fresh: bool = False,
    ) -> list:
        """
        Search for similar vectors.

        Args:
            query_vectors: List of query vectors
            top_k: Number of results per query
            filter_expr: Milvus filter expression (e.g., "area_m2 > 1000")
            output_fields: Fields to return
            fresh: If True, create fresh collection reference

        Returns:
            List of search results
        """
        # When filter is used, create completely fresh connection to avoid stale state
        if filter_expr is not None or fresh:
            logger.info(f"Creating fresh Milvus connection for search with filter: {filter_expr}")
            try:
                connections.disconnect("default")
                logger.info("Disconnected from Milvus")
            except Exception as e:
                logger.warning(f"Disconnect failed: {e}")
            self._connected = False
            self._collection = None

        collection = self.get_collection()
        if collection is None:
            return []

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16},
        }

        results = collection.search(
            data=query_vectors,
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=output_fields or ["gmina", "area_m2", "quietness_score"],
        )

        return results

    async def health_check(self) -> bool:
        """Check Milvus connection."""
        try:
            self.connect()
            return utility.has_collection(self.COLLECTION_NAME)
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")
            return False

    def close(self):
        """Disconnect from Milvus."""
        if self._connected:
            connections.disconnect("default")
            self._connected = False


# =============================================================================
# REDIS
# =============================================================================

class RedisManager:
    """Redis connection manager for caching."""

    def __init__(self):
        self._client = None

    async def connect(self) -> redis.Redis:
        """Get Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis connected")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        client = await self.connect()
        return await client.get(key)

    async def set(self, key: str, value: str, expire: int = 3600):
        """Set value in cache with expiration."""
        client = await self.connect()
        await client.set(key, value, ex=expire)

    async def delete(self, key: str):
        """Delete key from cache."""
        client = await self.connect()
        await client.delete(key)

    async def health_check(self) -> bool:
        """Check Redis connection."""
        try:
            client = await self.connect()
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self):
        """Close connection."""
        if self._client:
            await self._client.close()


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

postgis = PostGISManager()
neo4j = Neo4jManager()
milvus = MilvusManager()
redis_cache = RedisManager()


async def check_all_connections() -> dict:
    """Check health of all database connections."""
    import time
    results = {}

    # PostGIS
    start = time.time()
    try:
        connected = await postgis.health_check()
        results["postgis"] = {
            "connected": connected,
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        results["postgis"] = {"connected": False, "error": str(e)}

    # Neo4j
    start = time.time()
    try:
        connected = await neo4j.health_check()
        results["neo4j"] = {
            "connected": connected,
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        results["neo4j"] = {"connected": False, "error": str(e)}

    # Milvus
    start = time.time()
    try:
        connected = await milvus.health_check()
        results["milvus"] = {
            "connected": connected,
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        results["milvus"] = {"connected": False, "error": str(e)}

    # Redis
    start = time.time()
    try:
        connected = await redis_cache.health_check()
        results["redis"] = {
            "connected": connected,
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        results["redis"] = {"connected": False, "error": str(e)}

    return results


async def close_all_connections():
    """Close all database connections."""
    await postgis.close()
    await neo4j.close()
    milvus.close()
    await redis_cache.close()
    logger.info("All database connections closed")
