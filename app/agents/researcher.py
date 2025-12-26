"""Researcher Agent - Responsible for RAG-based information retrieval."""

from dataclasses import dataclass, field
from typing import Any

from app.agents.base import BaseAgent, AgentRole, LLMClient
from app.agents.prompts import RESEARCHER_SYSTEM_PROMPT, RESEARCHER_TASK_PROMPT
from app.rag.retriever import Retriever, get_retriever, RetrievalResult


@dataclass
class Finding:
    """A single research finding."""

    topic: str
    content: str
    source: str
    relevance_score: float
    is_sufficient: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "topic": self.topic,
            "content": self.content,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "is_sufficient": self.is_sufficient,
        }


@dataclass
class ResearchResult:
    """Result from researcher agent."""

    findings: list[Finding]
    missing_info: list[str]
    summary: str
    overall_sufficient: bool
    raw_retrievals: list[RetrievalResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "missing_info": self.missing_info,
            "summary": self.summary,
            "overall_sufficient": self.overall_sufficient,
        }

    @property
    def citation_count(self) -> int:
        """Get number of citations/sources."""
        return len(set(f.source for f in self.findings))


class ResearcherAgent(BaseAgent):
    """Researcher agent for RAG-based information retrieval."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        retriever: Retriever | None = None,
    ):
        """Initialize researcher agent.

        Args:
            llm_client: LLM client instance.
            retriever: Retriever instance for RAG.
        """
        super().__init__(role=AgentRole.RESEARCHER, llm_client=llm_client)
        self.retriever = retriever or get_retriever()

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return RESEARCHER_SYSTEM_PROMPT

    def build_task_prompt(
        self,
        search_topics: list[str],
        plan_context: str = "",
        **kwargs: Any,
    ) -> str:
        """Build task prompt for research.

        Args:
            search_topics: List of topics to search for.
            plan_context: Context from the planner.
            **kwargs: Additional context.

        Returns:
            Formatted prompt.
        """
        topics_str = "\n".join(f"- {topic}" for topic in search_topics)
        return RESEARCHER_TASK_PROMPT.format(
            search_topics=topics_str,
            plan_context=plan_context,
        )

    def retrieve_documents(self, topics: list[str]) -> list[RetrievalResult]:
        """Retrieve documents for given topics.

        Args:
            topics: List of search topics.

        Returns:
            List of retrieval results.
        """
        results = []
        for topic in topics:
            result = self.retriever.retrieve(topic)
            results.append(result)
            self.logger.debug(
                f"Retrieved {result.total_found} documents for '{topic}' "
                f"(sufficient: {result.is_sufficient})"
            )
        return results

    def parse_response(self, raw_output: str) -> ResearchResult:
        """Parse researcher response into ResearchResult.

        Args:
            raw_output: Raw LLM output.

        Returns:
            Parsed ResearchResult.
        """
        try:
            data = self._parse_json_response(raw_output)

            findings = [
                Finding(
                    topic=f.get("topic", ""),
                    content=f.get("content", ""),
                    source=f.get("source", ""),
                    relevance_score=f.get("relevance_score", 0.0),
                    is_sufficient=f.get("is_sufficient", False),
                )
                for f in data.get("findings", [])
            ]

            return ResearchResult(
                findings=findings,
                missing_info=data.get("missing_info", []),
                summary=data.get("summary", ""),
                overall_sufficient=data.get("overall_sufficient", True),
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse researcher response: {e}")
            return ResearchResult(
                findings=[],
                missing_info=["Parse failure"],
                summary=raw_output[:500],
                overall_sufficient=False,
            )

    def execute_with_rag(
        self,
        search_topics: list[str],
        plan_context: str = "",
        **kwargs: Any,
    ) -> ResearchResult:
        """Execute research with RAG retrieval.

        Args:
            search_topics: Topics to research.
            plan_context: Context from planner.
            **kwargs: Additional arguments.

        Returns:
            Research result with findings.
        """
        # First, retrieve documents
        retrieval_results = self.retrieve_documents(search_topics)

        # Check if we have sufficient information
        insufficient_topics = [
            r.query for r in retrieval_results if not r.is_sufficient
        ]

        if not any(r.results for r in retrieval_results):
            # No documents found - report failure
            self.logger.warning("No documents retrieved for any topic")
            return ResearchResult(
                findings=[],
                missing_info=search_topics,
                summary="No documents found. Please add documents to the RAG database.",
                overall_sufficient=False,
                raw_retrievals=retrieval_results,
            )

        # Build context from retrieved documents
        rag_context = self._format_retrieval_results(retrieval_results)

        # Generate research summary using LLM
        enhanced_prompt = self.build_task_prompt(
            search_topics=search_topics,
            plan_context=f"{plan_context}\n\n## Search Results\n{rag_context}",
        )

        raw_output = self.llm_client.generate(self.system_prompt, enhanced_prompt)
        result = self.parse_response(raw_output)
        result.raw_retrievals = retrieval_results

        # Add any insufficient topics to missing info
        if insufficient_topics:
            result.missing_info.extend(insufficient_topics)
            result.overall_sufficient = False

        return result

    def _format_retrieval_results(self, results: list[RetrievalResult]) -> str:
        """Format retrieval results for LLM context.

        Args:
            results: List of retrieval results.

        Returns:
            Formatted string.
        """
        formatted = []
        for result in results:
            formatted.append(f"### Topic: {result.query}")
            if not result.results:
                formatted.append("(No relevant documents)")
            else:
                for sr in result.results[:3]:  # Top 3 per topic
                    source = sr.document.metadata.get("filename", sr.document.id)
                    content_preview = sr.document.content[:500]
                    formatted.append(f"- **Source**: {source} (Score: {sr.score:.2f})")
                    formatted.append(f"  {content_preview}...")
            formatted.append("")

        return "\n".join(formatted)
