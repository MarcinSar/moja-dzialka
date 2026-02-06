"""
Database connection managers for all data stores.

Provides connection pooling and async support for:
- PostGIS (PostgreSQL with spatial extensions)
- Neo4j (Graph database with Vector Index)
- Redis (Cache)
- MongoDB (Leads)
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from neo4j import GraphDatabase, AsyncGraphDatabase
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
# MONGODB
# =============================================================================

class MongoDBManager:
    """MongoDB connection manager for leads and other collections."""

    def __init__(self):
        self._client = None
        self._db = None

    async def connect(self):
        """Get MongoDB client and database."""
        if self._client is None:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                self._client = AsyncIOMotorClient(settings.mongodb_uri)
                # Extract database name from URI or use default
                db_name = settings.mongodb_uri.split("/")[-1].split("?")[0]
                if not db_name:
                    db_name = "moja_dzialka"
                self._db = self._client[db_name]
                logger.info(f"MongoDB connected: {db_name}")
            except ImportError:
                logger.warning("motor not installed - MongoDB not available")
                return None
        return self._db

    async def get_collection(self, name: str):
        """Get a collection."""
        db = await self.connect()
        if db is None:
            return None
        return db[name]

    async def health_check(self) -> bool:
        """Check MongoDB connection."""
        try:
            db = await self.connect()
            if db is None:
                return False
            # Ping the server
            await self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False

    async def close(self):
        """Close connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


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
mongodb = MongoDBManager()
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

    # MongoDB
    start = time.time()
    try:
        connected = await mongodb.health_check()
        results["mongodb"] = {
            "connected": connected,
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        results["mongodb"] = {"connected": False, "error": str(e)}

    return results


async def close_all_connections():
    """Close all database connections."""
    await postgis.close()
    await neo4j.close()
    await mongodb.close()
    await redis_cache.close()
    logger.info("All database connections closed")
