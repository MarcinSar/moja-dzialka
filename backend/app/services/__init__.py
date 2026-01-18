"""
Backend services for moja-dzialka.

Services:
- database: Connection managers for all data stores
- spatial_service: PostGIS spatial queries
- vector_service: Milvus similarity search
- graph_service: Neo4j knowledge graph
- parcel_search: Hybrid search combining all sources
"""

from app.services.database import (
    postgis,
    neo4j,
    milvus,
    redis_cache,
    check_all_connections,
    close_all_connections,
)
from app.services.spatial_service import spatial_service, SpatialSearchParams
from app.services.vector_service import vector_service
from app.services.graph_service import graph_service
from app.services.parcel_search import hybrid_search, SearchPreferences, SearchResult

__all__ = [
    # Database connections
    "postgis",
    "neo4j",
    "milvus",
    "redis_cache",
    "check_all_connections",
    "close_all_connections",

    # Services
    "spatial_service",
    "vector_service",
    "graph_service",
    "hybrid_search",

    # Types
    "SpatialSearchParams",
    "SearchPreferences",
    "SearchResult",
]
