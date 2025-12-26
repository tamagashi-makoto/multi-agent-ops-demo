"""Retriever for fetching relevant documents from vector store."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.common.logger import get_logger
from app.rag.vector_store import VectorStore, SearchResult, Document, get_vector_store

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""

    query: str
    results: list[SearchResult]
    total_found: int
    is_sufficient: bool
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "results": [
                {
                    "content": r.document.content,
                    "metadata": r.document.metadata,
                    "score": r.score,
                    "id": r.document.id,
                }
                for r in self.results
            ],
            "total_found": self.total_found,
            "is_sufficient": self.is_sufficient,
            "message": self.message,
        }


class Retriever:
    """High-level retriever with relevance checking."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        min_score: float = 0.3,
        min_results: int = 1,
        top_k: int = 5,
    ):
        """Initialize retriever.

        Args:
            vector_store: Vector store to use.
            min_score: Minimum relevance score threshold.
            min_results: Minimum number of results for "sufficient" retrieval.
            top_k: Default number of results to retrieve.
        """
        self.vector_store = vector_store or get_vector_store()
        self.min_score = min_score
        self.min_results = min_results
        self.top_k = top_k
        logger.info(
            f"Initialized Retriever with min_score={min_score}, "
            f"min_results={min_results}, top_k={top_k}"
        )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant documents for a query.

        Args:
            query: Search query.
            top_k: Number of results (defaults to instance top_k).
            filter_metadata: Optional metadata filter.

        Returns:
            RetrievalResult with documents and sufficiency check.
        """
        k = top_k or self.top_k
        raw_results = self.vector_store.search(query, top_k=k)

        # Filter by score
        filtered_results = [r for r in raw_results if r.score >= self.min_score]

        # Filter by metadata if specified
        if filter_metadata:
            filtered_results = [
                r
                for r in filtered_results
                if all(
                    r.document.metadata.get(key) == value
                    for key, value in filter_metadata.items()
                )
            ]

        # Check sufficiency
        is_sufficient = len(filtered_results) >= self.min_results

        if not filtered_results:
            message = (
                f"No relevant documents found for query: '{query[:100]}...'. "
                "Consider rephrasing the query or adding more documents."
            )
        elif not is_sufficient:
            message = (
                f"Only {len(filtered_results)} document(s) found, "
                f"which is less than the minimum of {self.min_results}. "
                "Results may be incomplete."
            )
        else:
            message = f"Found {len(filtered_results)} relevant document(s)."

        result = RetrievalResult(
            query=query,
            results=filtered_results,
            total_found=len(filtered_results),
            is_sufficient=is_sufficient,
            message=message,
        )

        logger.info(
            f"Retrieved {len(filtered_results)} documents for query "
            f"(sufficient: {is_sufficient})"
        )

        return result

    def load_documents_from_directory(
        self,
        directory: str | Path,
        glob_pattern: str = "*.md",
    ) -> int:
        """Load documents from a directory.

        Args:
            directory: Directory path.
            glob_pattern: Glob pattern for files.

        Returns:
            Number of documents loaded.
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory {directory} does not exist")
            return 0

        documents = []
        for file_path in directory.glob(glob_pattern):
            content = file_path.read_text(encoding="utf-8")
            doc = Document(
                content=content,
                metadata={
                    "source": str(file_path),
                    "filename": file_path.name,
                },
                id=file_path.stem,
            )
            documents.append(doc)

        if documents:
            self.vector_store.add_documents(documents)
            logger.info(f"Loaded {len(documents)} documents from {directory}")

        return len(documents)

    def add_document(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Add a single document to the store.

        Args:
            content: Document content.
            metadata: Optional metadata.

        Returns:
            Document ID.
        """
        doc = Document(content=content, metadata=metadata or {})
        self.vector_store.add_document(doc)
        return doc.id

    def clear(self) -> None:
        """Clear all documents."""
        self.vector_store.clear()

    @property
    def document_count(self) -> int:
        """Get number of documents."""
        return self.vector_store.document_count


# Singleton instance
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Get or create the retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def reset_retriever() -> None:
    """Reset the retriever singleton."""
    global _retriever
    _retriever = None
