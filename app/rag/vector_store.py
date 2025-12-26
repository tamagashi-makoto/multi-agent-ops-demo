"""FAISS-based vector store for document retrieval."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import pickle

import numpy as np

from app.common.logger import get_logger
from app.rag.embeddings import EmbeddingService, get_embedding_service

logger = get_logger(__name__)


@dataclass
class Document:
    """A document with content and metadata."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    embedding: list[float] | None = None

    def __post_init__(self):
        if not self.id:
            self.id = f"doc_{hash(self.content) % (2**31)}"


@dataclass
class SearchResult:
    """A search result with document and score."""

    document: Document
    score: float


class VectorStore:
    """FAISS-based vector store for semantic search."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        dimension: int | None = None,
    ):
        """Initialize vector store.

        Args:
            embedding_service: Embedding service to use.
            dimension: Embedding dimension (uses service dimension if not specified).
        """
        try:
            import faiss

            self.faiss = faiss
        except ImportError:
            raise ImportError("faiss-cpu package is required for VectorStore")

        self.embedding_service = embedding_service or get_embedding_service()
        self.dimension = dimension or self.embedding_service.dimension

        # Initialize FAISS index (using L2 distance)
        self.index = self.faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity

        # Document storage
        self.documents: dict[int, Document] = {}
        self._doc_count = 0

        logger.info(f"Initialized VectorStore with dimension={self.dimension}")

    def add_document(self, document: Document) -> int:
        """Add a single document to the store.

        Args:
            document: Document to add.

        Returns:
            Document index.
        """
        if document.embedding is None:
            document.embedding = self.embedding_service.embed(document.content)

        embedding_array = np.array([document.embedding], dtype=np.float32)
        # Normalize for cosine similarity
        embedding_array = embedding_array / np.linalg.norm(embedding_array, axis=1, keepdims=True)

        self.index.add(embedding_array)
        doc_idx = self._doc_count
        self.documents[doc_idx] = document
        self._doc_count += 1

        logger.debug(f"Added document {document.id} at index {doc_idx}")
        return doc_idx

    def add_documents(self, documents: list[Document]) -> list[int]:
        """Add multiple documents to the store.

        Args:
            documents: List of documents to add.

        Returns:
            List of document indices.
        """
        indices = []
        for doc in documents:
            idx = self.add_document(doc)
            indices.append(idx)
        logger.info(f"Added {len(documents)} documents to vector store")
        return indices

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query.
            top_k: Number of results to return.

        Returns:
            List of search results with scores.
        """
        if self._doc_count == 0:
            logger.warning("Vector store is empty, returning no results")
            return []

        # Get query embedding
        query_embedding = self.embedding_service.embed(query)
        query_array = np.array([query_embedding], dtype=np.float32)
        query_array = query_array / np.linalg.norm(query_array, axis=1, keepdims=True)

        # Search
        k = min(top_k, self._doc_count)
        scores, indices = self.index.search(query_array, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx in self.documents:
                results.append(
                    SearchResult(
                        document=self.documents[idx],
                        score=float(score),
                    )
                )

        logger.debug(f"Search for '{query[:50]}...' returned {len(results)} results")
        return results

    def clear(self) -> None:
        """Clear all documents from the store."""
        self.index = self.faiss.IndexFlatIP(self.dimension)
        self.documents.clear()
        self._doc_count = 0
        logger.info("Vector store cleared")

    def save(self, path: str | Path) -> None:
        """Save the vector store to disk.

        Args:
            path: Path to save to (without extension).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        self.faiss.write_index(self.index, str(path.with_suffix(".faiss")))

        # Save documents
        with open(path.with_suffix(".pkl"), "wb") as f:
            pickle.dump(
                {
                    "documents": self.documents,
                    "doc_count": self._doc_count,
                    "dimension": self.dimension,
                },
                f,
            )

        logger.info(f"Saved vector store to {path}")

    def load(self, path: str | Path) -> None:
        """Load the vector store from disk.

        Args:
            path: Path to load from (without extension).
        """
        path = Path(path)

        # Load FAISS index
        self.index = self.faiss.read_index(str(path.with_suffix(".faiss")))

        # Load documents
        with open(path.with_suffix(".pkl"), "rb") as f:
            data = pickle.load(f)
            self.documents = data["documents"]
            self._doc_count = data["doc_count"]
            self.dimension = data["dimension"]

        logger.info(f"Loaded vector store from {path} ({self._doc_count} documents)")

    @property
    def document_count(self) -> int:
        """Get number of documents in store."""
        return self._doc_count


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reset_vector_store() -> None:
    """Reset the vector store singleton."""
    global _vector_store
    _vector_store = None
