"""Embedding service for generating text embeddings."""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.common.config import get_settings
from app.common.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService(ABC):
    """Abstract base class for embedding services."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Get embedding dimension."""
        pass


class StubEmbeddingService(EmbeddingService):
    """Stub embedding service for testing without API calls."""

    def __init__(self, dimension: int = 1536, seed: int | None = None):
        """Initialize stub embedding service.

        Args:
            dimension: Embedding vector dimension.
            seed: Random seed for reproducibility.
        """
        self._dimension = dimension
        self._rng = np.random.default_rng(seed)
        logger.info(f"Initialized StubEmbeddingService with dimension={dimension}")

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    def embed(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-random embedding based on text hash.

        Args:
            text: Input text.

        Returns:
            Pseudo-random embedding vector.
        """
        # Use text hash for deterministic embeddings
        text_hash = hash(text) % (2**31)
        rng = np.random.default_rng(text_hash)
        embedding = rng.random(self._dimension).astype(np.float32)
        # Normalize to unit vector
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        return [self.embed(text) for text in texts]


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding service."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ):
        """Initialize OpenAI embedding service.

        Args:
            api_key: OpenAI API key.
            model: Embedding model name.
            dimension: Embedding dimension.
        """
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)
            self.model = model
            self._dimension = dimension
            logger.info(f"Initialized OpenAIEmbeddingService with model={model}")
        except ImportError:
            raise ImportError("openai package is required for OpenAIEmbeddingService")

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API.

        Args:
            text: Input text.

        Returns:
            Embedding vector.
        """
        response = self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service instance.

    Returns:
        Configured embedding service.
    """
    global _embedding_service

    if _embedding_service is not None:
        return _embedding_service

    settings = get_settings()

    if settings.embedding_mode == "openai":
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not set, falling back to stub mode")
            _embedding_service = StubEmbeddingService(dimension=settings.embedding_dimension)
        else:
            _embedding_service = OpenAIEmbeddingService(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
    else:
        _embedding_service = StubEmbeddingService(dimension=settings.embedding_dimension)

    return _embedding_service


def reset_embedding_service() -> None:
    """Reset the embedding service singleton."""
    global _embedding_service
    _embedding_service = None
