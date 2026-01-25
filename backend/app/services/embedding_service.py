"""
Embedding Service - Lazy-loading sentence-transformers for entity resolution.

This service provides semantic embeddings for entity names (locations, categories, etc.)
using a multilingual model that supports Polish and English.

Model: distiluse-base-multilingual-cased
- 512 dimensions
- Supports 50+ languages including Polish
- Good balance of quality and speed

Usage:
    from app.services.embedding_service import EmbeddingService

    # Single text
    embedding = EmbeddingService.encode("Matemblewo")

    # Batch encoding (more efficient)
    embeddings = EmbeddingService.encode_batch(["Osowa", "Matarnia", "Wrzeszcz"])
"""

from typing import List, Optional
from loguru import logger


class EmbeddingService:
    """Lazy-loading embedding service using sentence-transformers."""

    _model = None
    _model_name = "distiluse-base-multilingual-cased"

    @classmethod
    def get_model(cls):
        """Get or initialize the sentence-transformers model (lazy loading).

        Returns:
            SentenceTransformer model instance
        """
        if cls._model is None:
            logger.info(f"Loading sentence-transformers model: {cls._model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer(cls._model_name)
                logger.info(f"Model loaded successfully. Embedding dimension: {cls._model.get_sentence_embedding_dimension()}")
            except ImportError:
                logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise
        return cls._model

    @classmethod
    def encode(cls, text: str, normalize: bool = True) -> List[float]:
        """Encode a single text into a 384-dimensional embedding.

        Args:
            text: Text to encode (e.g., "Matemblewo")
            normalize: Whether to L2-normalize the embedding (default: True)
                       Normalized embeddings allow using dot product for cosine similarity

        Returns:
            List of 384 floats representing the embedding
        """
        model = cls.get_model()
        embedding = model.encode(
            text.lower().strip(),
            normalize_embeddings=normalize,
            convert_to_numpy=True
        )
        return embedding.tolist()

    @classmethod
    def encode_batch(cls, texts: List[str], normalize: bool = True, show_progress: bool = False) -> List[List[float]]:
        """Encode multiple texts into embeddings (batch processing is more efficient).

        Args:
            texts: List of texts to encode
            normalize: Whether to L2-normalize embeddings (default: True)
            show_progress: Whether to show progress bar (default: False)

        Returns:
            List of embeddings (each is a list of 384 floats)
        """
        model = cls.get_model()
        # Lowercase and strip all texts
        cleaned_texts = [t.lower().strip() for t in texts]
        embeddings = model.encode(
            cleaned_texts,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=show_progress
        )
        return embeddings.tolist()

    @classmethod
    def get_dimension(cls) -> int:
        """Get the embedding dimension (512 for distiluse-base-multilingual-cased).

        Returns:
            Integer dimension of embeddings
        """
        model = cls.get_model()
        return model.get_sentence_embedding_dimension()

    @classmethod
    def compute_similarity(cls, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding (384-dim)
            embedding2: Second embedding (384-dim)

        Returns:
            Cosine similarity score (0-1 for normalized embeddings)
        """
        import numpy as np
        e1 = np.array(embedding1)
        e2 = np.array(embedding2)
        # For normalized embeddings, dot product = cosine similarity
        return float(np.dot(e1, e2))

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if the model is already loaded.

        Returns:
            True if model is loaded, False otherwise
        """
        return cls._model is not None

    @classmethod
    def unload(cls) -> None:
        """Unload the model to free memory."""
        if cls._model is not None:
            logger.info("Unloading embedding model")
            cls._model = None


# Convenience functions for direct imports
def encode(text: str) -> List[float]:
    """Encode a single text into an embedding."""
    return EmbeddingService.encode(text)


def encode_batch(texts: List[str]) -> List[List[float]]:
    """Encode multiple texts into embeddings."""
    return EmbeddingService.encode_batch(texts)
