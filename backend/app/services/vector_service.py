"""
Vector search service using Milvus.

Handles embedding-based similarity search for parcels.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json

import numpy as np
from loguru import logger

from app.services.database import milvus, redis_cache


@dataclass
class VectorSearchResult:
    """Result from vector similarity search."""
    parcel_id: str
    similarity_score: float
    gmina: Optional[str] = None
    area_m2: Optional[float] = None
    quietness_score: Optional[float] = None
    nature_score: Optional[float] = None
    accessibility_score: Optional[float] = None


class VectorService:
    """Service for vector similarity search using Milvus."""

    # Cache TTL for embeddings
    EMBEDDING_CACHE_TTL = 3600  # 1 hour

    async def search_similar(
        self,
        parcel_id: str,
        top_k: int = 20,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        gmina: Optional[str] = None,
        has_mpzp: Optional[bool] = None,
    ) -> List[VectorSearchResult]:
        """
        Find parcels similar to a given parcel.

        Args:
            parcel_id: Reference parcel ID
            top_k: Number of similar parcels to return
            min_area: Minimum area filter
            max_area: Maximum area filter
            gmina: Filter by gmina
            has_mpzp: Filter by MPZP status

        Returns:
            List of similar parcels with scores
        """
        # Get embedding for reference parcel
        embedding = await self._get_parcel_embedding(parcel_id)
        if embedding is None:
            logger.warning(f"No embedding found for parcel: {parcel_id}")
            return []

        return await self.search_by_vector(
            query_vector=embedding,
            top_k=top_k,
            min_area=min_area,
            max_area=max_area,
            gmina=gmina,
            has_mpzp=has_mpzp,
            exclude_ids=[parcel_id],  # Exclude the reference parcel
        )

    async def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 20,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        gmina: Optional[str] = None,
        has_mpzp: Optional[bool] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[VectorSearchResult]:
        """
        Search for similar parcels using a query vector.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results
            Various filters

        Returns:
            List of similar parcels with scores
        """
        # Build filter expression
        filter_parts = []

        if min_area is not None:
            filter_parts.append(f"area_m2 >= {min_area}")

        if max_area is not None:
            filter_parts.append(f"area_m2 <= {max_area}")

        if gmina is not None:
            filter_parts.append(f'gmina == "{gmina}"')

        if has_mpzp is not None:
            filter_parts.append(f"has_mpzp == {str(has_mpzp).lower()}")

        if exclude_ids:
            # Milvus uses 'not in' for exclusion
            ids_str = ", ".join([f'"{id}"' for id in exclude_ids])
            filter_parts.append(f"id not in [{ids_str}]")

        filter_expr = " and ".join(filter_parts) if filter_parts else None

        # Search in Milvus (with retry on failure)
        for attempt in range(2):
            try:
                # On retry, use fresh collection reference
                results = milvus.search(
                    query_vectors=[query_vector],
                    top_k=top_k,
                    filter_expr=filter_expr,
                    output_fields=["gmina", "area_m2", "quietness_score", "nature_score", "accessibility_score"],
                    fresh=(attempt > 0),  # Fresh on retry
                )

                if not results or len(results) == 0:
                    return []

                # Convert to result objects
                search_results = []
                for hit in results[0]:
                    result = VectorSearchResult(
                        parcel_id=hit.id,
                        similarity_score=float(hit.score),
                        gmina=hit.entity.get("gmina"),
                        area_m2=hit.entity.get("area_m2"),
                        quietness_score=hit.entity.get("quietness_score"),
                        nature_score=hit.entity.get("nature_score"),
                        accessibility_score=hit.entity.get("accessibility_score"),
                    )
                    search_results.append(result)

                return search_results

            except Exception as e:
                logger.error(f"Vector search error (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    # Refresh collection and retry with fresh reference
                    logger.info("Refreshing Milvus connection and retrying...")
                    milvus.refresh_collection()
                else:
                    return []
        return []

    async def search_by_preferences(
        self,
        preferences: Dict[str, float],
        top_k: int = 20,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        gmina: Optional[str] = None,
    ) -> List[VectorSearchResult]:
        """
        Search for parcels matching user preferences.

        Creates a synthetic query vector from preference weights.

        Args:
            preferences: Dict of preference weights (e.g., {"quietness": 0.8, "nature": 0.6})
            top_k: Number of results
            Various filters

        Returns:
            List of matching parcels
        """
        # Create synthetic query vector from preferences
        # This is a simplified approach - in production, you'd use a trained model
        query_vector = self._create_preference_vector(preferences)

        return await self.search_by_vector(
            query_vector=query_vector,
            top_k=top_k,
            min_area=min_area,
            max_area=max_area,
            gmina=gmina,
        )

    def _create_preference_vector(self, preferences: Dict[str, float]) -> List[float]:
        """
        Create a synthetic query vector from user preferences.

        Uses alternating positive/negative values to avoid Milvus "Unsupported field type: 0"
        error which occurs with all-positive sparse vectors.
        """
        # Default embedding dimension (should match your embeddings)
        dim = 64

        # Start with small random noise to ensure mixed +/- values
        # This prevents the "Unsupported field type: 0" Milvus error
        np.random.seed(42)  # Deterministic for reproducibility
        vector = np.random.randn(dim) * 0.01  # Small random noise

        # Map preferences to vector dimensions
        # These indices should align with your embedding training
        preference_mapping = {
            "quietness": (0, 5),      # Dimensions 0-4
            "nature": (5, 10),        # Dimensions 5-9
            "accessibility": (10, 15), # Dimensions 10-14
            "area": (15, 20),         # Dimensions 15-19
        }

        for pref_name, weight in preferences.items():
            if pref_name in preference_mapping:
                start, end = preference_mapping[pref_name]
                # Use alternating signs to create mixed +/- pattern
                for i in range(start, end):
                    sign = 1 if (i - start) % 2 == 0 else -1
                    vector[i] = sign * weight

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    async def _get_parcel_embedding(self, parcel_id: str) -> Optional[List[float]]:
        """
        Get embedding vector for a parcel.

        Uses Redis cache for frequently accessed embeddings.
        """
        # Try cache first
        cache_key = f"embedding:{parcel_id}"
        cached = await redis_cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query from Milvus
        try:
            collection = milvus.get_collection()
            if collection is None:
                return None

            # Query by ID
            results = collection.query(
                expr=f'id == "{parcel_id}"',
                output_fields=["embedding"],
            )

            if results and len(results) > 0:
                embedding = results[0]["embedding"]
                # Cache for future use
                await redis_cache.set(
                    cache_key,
                    json.dumps(embedding),
                    expire=self.EMBEDDING_CACHE_TTL
                )
                return embedding

            return None

        except Exception as e:
            logger.error(f"Get parcel embedding error: {e}")
            return None

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        try:
            collection = milvus.get_collection()
            if collection is None:
                return {"status": "not_found", "count": 0}

            return {
                "status": "ok",
                "name": collection.name,
                "count": collection.num_entities,
                "schema": [f.name for f in collection.schema.fields],
            }
        except Exception as e:
            logger.error(f"Get collection stats error: {e}")
            return {"status": "error", "error": str(e)}


# Global instance
vector_service = VectorService()
