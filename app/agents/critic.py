"""Critic Agent - Responsible for quality assurance and hallucination detection."""

from dataclasses import dataclass, field
from typing import Any

from app.agents.base import BaseAgent, AgentRole, LLMClient
from app.agents.prompts import CRITIC_SYSTEM_PROMPT, CRITIC_TASK_PROMPT


@dataclass
class Issue:
    """A single issue found in the draft."""

    type: str  # accuracy, logic, completeness, clarity
    severity: str  # high, medium, low
    location: str
    description: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "severity": self.severity,
            "location": self.location,
            "description": self.description,
            "suggestion": self.suggestion,
        }


@dataclass
class CritiqueResult:
    """Result from critic agent."""

    overall_score: int  # 0-100
    issues: list[Issue]
    verified_claims: list[str]
    unverified_claims: list[str]
    summary: str
    approved: bool
    revision_needed: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_score": self.overall_score,
            "issues": [i.to_dict() for i in self.issues],
            "verified_claims": self.verified_claims,
            "unverified_claims": self.unverified_claims,
            "summary": self.summary,
            "approved": self.approved,
            "revision_needed": self.revision_needed,
        }

    @property
    def high_severity_issues(self) -> list[Issue]:
        """Get high severity issues."""
        return [i for i in self.issues if i.severity == "high"]

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are issues that should block approval."""
        return bool(self.high_severity_issues) or len(self.unverified_claims) > 2


class CriticAgent(BaseAgent):
    """Critic agent for quality assurance and hallucination detection."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize critic agent."""
        super().__init__(role=AgentRole.CRITIC, llm_client=llm_client)

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return CRITIC_SYSTEM_PROMPT

    def build_task_prompt(
        self,
        draft: str,
        requirements: list[str] | str,
        research_findings: str,
        **kwargs: Any,
    ) -> str:
        """Build task prompt for critique.

        Args:
            draft: Draft to evaluate.
            requirements: Original requirements.
            research_findings: Research findings used in draft.
            **kwargs: Additional context.

        Returns:
            Formatted prompt.
        """
        if isinstance(requirements, list):
            requirements = "\n".join(f"- {r}" for r in requirements)

        return CRITIC_TASK_PROMPT.format(
            draft=draft,
            requirements=requirements,
            research_findings=research_findings,
        )

    def parse_response(self, raw_output: str) -> CritiqueResult:
        """Parse critic response into CritiqueResult.

        Args:
            raw_output: Raw LLM output.

        Returns:
            Parsed CritiqueResult.
        """
        try:
            data = self._parse_json_response(raw_output)

            issues = [
                Issue(
                    type=i.get("type", "unknown"),
                    severity=i.get("severity", "medium"),
                    location=i.get("location", ""),
                    description=i.get("description", ""),
                    suggestion=i.get("suggestion", ""),
                )
                for i in data.get("issues", [])
            ]

            return CritiqueResult(
                overall_score=data.get("overall_score", 0),
                issues=issues,
                verified_claims=data.get("verified_claims", []),
                unverified_claims=data.get("unverified_claims", []),
                summary=data.get("summary", ""),
                approved=data.get("approved", False),
                revision_needed=data.get("revision_needed", True),
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse critic response: {e}")
            return CritiqueResult(
                overall_score=0,
                issues=[],
                verified_claims=[],
                unverified_claims=[],
                summary=f"Parse failure: {raw_output[:300]}",
                approved=False,
                revision_needed=True,
            )

    def verify_citations(
        self,
        draft: str,
        available_sources: list[str],
    ) -> tuple[list[str], list[str]]:
        """Verify citations in the draft against available sources.

        Args:
            draft: Draft content.
            available_sources: List of available source names.

        Returns:
            Tuple of (verified_citations, unverified_citations).
        """
        import re

        # Extract citations from draft
        citation_pattern = r"\[Source:\s*[^\]]+\]"
        cited_sources = re.findall(citation_pattern, draft)

        verified = []
        unverified = []

        for citation in cited_sources:
            citation_clean = citation.strip()
            # Check if source exists (fuzzy match)
            if any(
                src.lower() in citation_clean.lower()
                or citation_clean.lower() in src.lower()
                for src in available_sources
            ):
                verified.append(citation_clean)
            else:
                unverified.append(citation_clean)

        return verified, unverified

    def generate_revision_instructions(
        self,
        critique_result: CritiqueResult,
    ) -> str:
        """Generate revision instructions from critique result.

        Args:
            critique_result: Critique result to base instructions on.

        Returns:
            Formatted revision instructions.
        """
        instructions = ["## Revision Instructions\n"]

        if critique_result.high_severity_issues:
            instructions.append("### Critical Issues (Must Fix)")
            for issue in critique_result.high_severity_issues:
                instructions.append(
                    f"- **{issue.location}**: {issue.description}\n  → {issue.suggestion}"
                )
            instructions.append("")

        other_issues = [i for i in critique_result.issues if i.severity != "high"]
        if other_issues:
            instructions.append("### Other Improvements")
            for issue in other_issues:
                instructions.append(f"- {issue.location}: {issue.suggestion}")
            instructions.append("")

        if critique_result.unverified_claims:
            instructions.append("### Unverified Claims")
            for claim in critique_result.unverified_claims:
                instructions.append(f"- {claim}")

        return "\n".join(instructions)
