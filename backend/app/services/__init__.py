"""
Backend services for moja-dzialka.

Services:
- database: Connection managers for all data stores
- spatial_service: PostGIS spatial queries
- graph_service: Neo4j knowledge graph (with vector indexes)
- parcel_search: Hybrid search combining graph, spatial, and semantic sources
- diversity: Diverse proposal selection for search results
"""

from app.services.database import (
    postgis,
    neo4j,
    redis_cache,
    check_all_connections,
    close_all_connections,
)
from app.services.spatial_service import spatial_service, SpatialSearchParams, BBoxSearchParams
from app.services.graph_service import graph_service
from app.services.parcel_search import hybrid_search, SearchPreferences, SearchResult
from app.services.diversity import (
    select_diverse_proposals,
    parse_user_feedback,
    format_proposal_for_display,
    DiverseProposal,
    UserFeedback,
)
from app.services.embedding_service import EmbeddingService

__all__ = [
    # Database connections
    "postgis",
    "neo4j",
    "redis_cache",
    "check_all_connections",
    "close_all_connections",

    # Services
    "spatial_service",
    "graph_service",
    "hybrid_search",

    # Diversity
    "select_diverse_proposals",
    "parse_user_feedback",
    "format_proposal_for_display",

    # Types
    "SpatialSearchParams",
    "BBoxSearchParams",
    "SearchPreferences",
    "SearchResult",
    "DiverseProposal",
    "UserFeedback",

    # Embeddings
    "EmbeddingService",
]
