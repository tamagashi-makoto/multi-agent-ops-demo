"""Retrieve tool for RAG-based document retrieval."""

from typing import Any

from app.common.logger import get_logger
from app.rag.retriever import Retriever, get_retriever, RetrievalResult

logger = get_logger(__name__)


def retrieve_tool(
    query: str,
    top_k: int = 5,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """Retrieve relevant documents for a query.

    This tool searches the vector store for documents relevant to the query
    and returns them with relevance scores.

    Args:
        query: Search query.
        top_k: Number of results to return.
        retriever: Optional retriever instance.

    Returns:
        Dictionary with retrieval results.
    """
    logger.info(f"Retrieve tool called with query: {query[:50]}...")

    retriever = retriever or get_retriever()
    result = retriever.retrieve(query, top_k=top_k)

    return {
        "query": result.query,
        "documents": [
            {
                "content": r.document.content,
                "source": r.document.metadata.get("filename", r.document.id),
                "score": r.score,
            }
            for r in result.results
        ],
        "total_found": result.total_found,
        "is_sufficient": result.is_sufficient,
        "message": result.message,
    }


def search_documents_tool(
    topics: list[str],
    top_k_per_topic: int = 3,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """Search documents for multiple topics.

    Args:
        topics: List of topics to search for.
        top_k_per_topic: Results per topic.
        retriever: Optional retriever instance.

    Returns:
        Dictionary with search results per topic.
    """
    logger.info(f"Search documents tool called with {len(topics)} topics")

    retriever = retriever or get_retriever()
    results = {}
    all_sufficient = True

    for topic in topics:
        result = retriever.retrieve(topic, top_k=top_k_per_topic)
        results[topic] = {
            "documents": [
                {
                    "content": r.document.content[:500],  # Truncate for overview
                    "source": r.document.metadata.get("filename", r.document.id),
                    "score": r.score,
                }
                for r in result.results
            ],
            "is_sufficient": result.is_sufficient,
        }
        if not result.is_sufficient:
            all_sufficient = False

    return {
        "topics": results,
        "overall_sufficient": all_sufficient,
        "total_topics": len(topics),
    }
