"""Planner Agent - Responsible for requirement analysis and task decomposition."""

from dataclasses import dataclass
from typing import Any

from app.agents.base import BaseAgent, AgentRole, LLMClient
from app.agents.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_TASK_PROMPT


@dataclass
class PlanResult:
    """Result from planner agent."""

    requirements: list[str]
    tasks: list[dict[str, Any]]
    questions: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "requirements": self.requirements,
            "tasks": self.tasks,
            "questions": self.questions,
            "summary": self.summary,
        }

    @property
    def has_questions(self) -> bool:
        """Check if there are unanswered questions."""
        return len(self.questions) > 0

    @property
    def high_priority_tasks(self) -> list[dict[str, Any]]:
        """Get high priority tasks."""
        return [t for t in self.tasks if t.get("priority") == "high"]


class PlannerAgent(BaseAgent):
    """Planner agent for requirement analysis and task decomposition."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize planner agent."""
        super().__init__(role=AgentRole.PLANNER, llm_client=llm_client)

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return PLANNER_SYSTEM_PROMPT

    def build_task_prompt(
        self,
        request: str,
        available_docs: str = "Internal documents (Product Overview, Pricing, FAQ, Case Studies)",
        **kwargs: Any,
    ) -> str:
        """Build task prompt for planning.

        Args:
            request: User's request for proposal.
            available_docs: Description of available documents.
            **kwargs: Additional context.

        Returns:
            Formatted prompt.
        """
        return PLANNER_TASK_PROMPT.format(
            request=request,
            available_docs=available_docs,
        )

    def parse_response(self, raw_output: str) -> PlanResult:
        """Parse planner response into PlanResult.

        Args:
            raw_output: Raw LLM output.

        Returns:
            Parsed PlanResult.
        """
        try:
            data = self._parse_json_response(raw_output)
            return PlanResult(
                requirements=data.get("requirements", []),
                tasks=data.get("tasks", []),
                questions=data.get("questions", []),
                summary=data.get("summary", ""),
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse planner response as JSON: {e}")
            # Return a minimal result with the raw output as summary
            return PlanResult(
                requirements=[],
                tasks=[],
                questions=[],
                summary=raw_output[:500],
            )

    def create_additional_questions(
        self,
        missing_info: list[str],
        context: str = "",
    ) -> list[str]:
        """Generate additional questions when information is insufficient.

        Args:
            missing_info: List of missing information items.
            context: Additional context.

        Returns:
            List of questions to ask.
        """
        if not missing_info:
            return []

        prompt = f"""
Generate questions to fill in the missing information below.

## Missing Information
{chr(10).join(f"- {info}" for info in missing_info)}

## Context
{context}

Output the list of questions as a JSON array:
["Question 1", "Question 2", ...]
"""

        raw_output = self.llm_client.generate(
            "You are an assistant that generates questions for information gathering.",
            prompt,
        )

        try:
            import json

            # Extract JSON array
            if "[" in raw_output:
                start = raw_output.find("[")
                end = raw_output.rfind("]") + 1
                questions = json.loads(raw_output[start:end])
                return questions
        except Exception:
            pass

        # Fallback: generate simple questions
        return [f"Please tell me more about {info}." for info in missing_info]
