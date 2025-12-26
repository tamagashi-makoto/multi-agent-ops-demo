"""Writer Agent - Responsible for generating proposal drafts."""

from dataclasses import dataclass
from typing import Any

from app.agents.base import BaseAgent, AgentRole, LLMClient
from app.agents.prompts import WRITER_SYSTEM_PROMPT, WRITER_TASK_PROMPT


@dataclass
class DraftResult:
    """Result from writer agent."""

    content: str
    sections: list[str]
    citation_count: int
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "sections": self.sections,
            "citation_count": self.citation_count,
            "word_count": self.word_count,
        }


class WriterAgent(BaseAgent):
    """Writer agent for generating proposal drafts."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize writer agent."""
        super().__init__(role=AgentRole.WRITER, llm_client=llm_client)

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return WRITER_SYSTEM_PROMPT

    def build_task_prompt(
        self,
        requirements: list[str] | str,
        research_findings: str,
        customer_context: str = "General Corporate Customer",
        **kwargs: Any,
    ) -> str:
        """Build task prompt for writing.

        Args:
            requirements: List of requirements or formatted string.
            research_findings: Research findings from researcher.
            customer_context: Information about the customer.
            **kwargs: Additional context.

        Returns:
            Formatted prompt.
        """
        if isinstance(requirements, list):
            requirements = "\n".join(f"- {r}" for r in requirements)

        return WRITER_TASK_PROMPT.format(
            requirements=requirements,
            research_findings=research_findings,
            customer_context=customer_context,
        )

    def parse_response(self, raw_output: str) -> DraftResult:
        """Parse writer response into DraftResult.

        Args:
            raw_output: Raw LLM output (markdown).

        Returns:
            Parsed DraftResult.
        """
        # Extract sections from markdown headers
        sections = []
        for line in raw_output.split("\n"):
            if line.startswith("##") and not line.startswith("###"):
                section_title = line.lstrip("#").strip()
                sections.append(section_title)
            elif line.startswith("# ") and not sections:
                # Main title
                sections.append(line.lstrip("#").strip())

        # Count citations (look for [Source: ...] pattern)
        import re

        citation_pattern = r"\[Source:\s*[^\]]+\]"
        citations = re.findall(citation_pattern, raw_output)
        citation_count = len(citations)

        # Count words (Japanese character + space-separated words)
        # Simple approximation for Japanese text
        word_count = len(raw_output)

        return DraftResult(
            content=raw_output,
            sections=sections,
            citation_count=citation_count,
            word_count=word_count,
        )

    def revise_draft(
        self,
        original_draft: str,
        critique_feedback: str,
        **kwargs: Any,
    ) -> DraftResult:
        """Revise a draft based on critique feedback.

        Args:
            original_draft: Original draft content.
            critique_feedback: Feedback from critic agent.
            **kwargs: Additional context.

        Returns:
            Revised draft result.
        """
        revision_prompt = f"""
Revise the following proposal draft based on the feedback.

## Original Draft
{original_draft}

## Feedback
{critique_feedback}

## Instructions
1. Fix the pointed out issues.
2. Keep the good parts of the original.
3. Maintain accurate citations.

Output the revised version in Markdown format.
"""

        raw_output = self.llm_client.generate(self.system_prompt, revision_prompt)
        return self.parse_response(raw_output)

    def format_research_for_writing(
        self,
        findings: list[dict[str, Any]],
    ) -> str:
        """Format research findings for the writer prompt.

        Args:
            findings: List of finding dictionaries.

        Returns:
            Formatted research findings string.
        """
        formatted = []
        for finding in findings:
            formatted.append(f"### {finding.get('topic', 'Topic')}")
            formatted.append(f"**Source**: {finding.get('source', 'Unknown')}")
            formatted.append(f"{finding.get('content', '')}")
            formatted.append("")

        return "\n".join(formatted)
