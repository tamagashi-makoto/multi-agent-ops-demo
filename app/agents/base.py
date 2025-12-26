"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import json

from app.common.config import get_settings
from app.common.logger import get_logger

logger = get_logger(__name__)


class AgentRole(str, Enum):
    """Agent roles in the system."""

    PLANNER = "planner"
    RESEARCHER = "researcher"
    WRITER = "writer"
    CRITIC = "critic"
    COORDINATOR = "coordinator"


@dataclass
class AgentResponse:
    """Response from an agent execution."""

    role: AgentRole
    content: Any
    raw_output: str
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "raw_output": self.raw_output,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class LLMClient:
    """Unified LLM client supporting multiple backends."""

    def __init__(self):
        """Initialize LLM client based on settings."""
        self.settings = get_settings()
        self.mode = self.settings.llm_mode
        self._client = None

        if self.mode == "openai":
            self._init_openai()
        elif self.mode == "ollama":
            self._init_ollama()
        else:
            logger.info("Using stub LLM mode")

    def _init_openai(self) -> None:
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.settings.openai_api_key)
            self._model = self.settings.openai_model
            logger.info(f"Initialized OpenAI client with model={self._model}")
        except ImportError:
            logger.warning("OpenAI package not installed, falling back to stub mode")
            self.mode = "stub"

    def _init_ollama(self) -> None:
        """Initialize Ollama client."""
        try:
            import httpx

            self._client = httpx.Client(base_url=self.settings.ollama_base_url)
            self._model = self.settings.ollama_model
            logger.info(f"Initialized Ollama client with model={self._model}")
        except ImportError:
            logger.warning("httpx package not installed, falling back to stub mode")
            self.mode = "stub"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from LLM.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            Generated text.
        """
        if self.mode == "stub":
            return self._stub_generate(system_prompt, user_prompt)
        elif self.mode == "openai":
            return self._openai_generate(system_prompt, user_prompt)
        elif self.mode == "ollama":
            return self._ollama_generate(system_prompt, user_prompt)
        else:
            return self._stub_generate(system_prompt, user_prompt)

    def _stub_generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate stub response for testing."""
        logger.debug("Using stub LLM generation")

        # Extract keywords from prompt to create contextual stub response
        if "plan" in system_prompt.lower() or "planner" in system_prompt.lower():
            return json.dumps(
                {
                    "requirements": ["Provide product info", "Present pricing", "Introduce case studies"],
                    "tasks": [
                        {
                            "id": 1,
                            "description": "Research product overview",
                            "priority": "high",
                            "required_info": ["Product features", "Tech specs"],
                        },
                        {
                            "id": 2,
                            "description": "Research pricing plans",
                            "priority": "high",
                            "required_info": ["Pricing structure", "Discounts"],
                        },
                        {
                            "id": 3,
                            "description": "Collect case studies",
                            "priority": "medium",
                            "required_info": ["Success stories", "ROI"],
                        },
                    ],
                    "questions": [],
                    "summary": "Created a plan for the proposal.",
                },
                ensure_ascii=False,
                indent=2,
            )

        elif "research" in system_prompt.lower() or "researcher" in system_prompt.lower():
            return json.dumps(
                {
                    "findings": [
                        {
                            "topic": "Product Overview",
                            "content": "IntelliFlow AI Platform is an integrated AI solution for enterprises.",
                            "source": "product_overview.md",
                            "relevance_score": 0.95,
                            "is_sufficient": True,
                        },
                        {
                            "topic": "Pricing",
                            "content": "Starter plan from $1,000/month, Enterprise is custom quote.",
                            "source": "pricing.md",
                            "relevance_score": 0.92,
                            "is_sufficient": True,
                        },
                    ],
                    "missing_info": [],
                    "summary": "Collected necessary information.",
                    "overall_sufficient": True,
                },
                ensure_ascii=False,
                indent=2,
            )

        elif "writer" in system_prompt.lower():
            return """# Proposal

## Executive Summary

We propose IntelliFlow AI Platform for your AI implementation needs.
[Source: product_overview.md]

## Product Overview

IntelliFlow AI Platform is an enterprise AI solution supporting end-to-end
machine learning model development to production.
[Source: product_overview.md]

## Proposed Plan

We recommend the Professional Plan ($5,000/month).
[Source: pricing.md]

## Case Studies

A major retail chain achieved 35% reduction in inventory waste.
[Source: case_studies.md]

## Next Steps

You can start with a 14-day free trial.
"""

        elif "critic" in system_prompt.lower():
            return json.dumps(
                {
                    "overall_score": 85,
                    "issues": [
                        {
                            "type": "completeness",
                            "severity": "low",
                            "location": "Next Steps",
                            "description": "No specific schedule presented",
                            "suggestion": "Add estimated implementation schedule",
                        }
                    ],
                    "verified_claims": [
                        "Product overview is accurate",
                        "Pricing info is accurate",
                        "Case studies are accurate",
                    ],
                    "unverified_claims": [],
                    "summary": "Overall good proposal. Minor improvements needed.",
                    "approved": True,
                    "revision_needed": False,
                },
                ensure_ascii=False,
                indent=2,
            )

        else:
            return "Stub response: This response was generated in test mode."

    def _openai_generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response using OpenAI."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content

    def _ollama_generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response using Ollama."""
        response = self._client.post(
            "/api/generate",
            json={
                "model": self._model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["response"]


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        role: AgentRole,
        llm_client: LLMClient | None = None,
    ):
        """Initialize base agent.

        Args:
            role: Agent role.
            llm_client: LLM client instance.
        """
        self.role = role
        self.llm_client = llm_client or LLMClient()
        self.logger = get_logger(f"agent.{role.value}")

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    @abstractmethod
    def build_task_prompt(self, **kwargs: Any) -> str:
        """Build task-specific prompt.

        Args:
            **kwargs: Task-specific arguments.

        Returns:
            Formatted task prompt.
        """
        pass

    @abstractmethod
    def parse_response(self, raw_output: str) -> Any:
        """Parse the raw LLM output into structured data.

        Args:
            raw_output: Raw text from LLM.

        Returns:
            Parsed structured data.
        """
        pass

    def execute(self, **kwargs: Any) -> AgentResponse:
        """Execute the agent with given inputs.

        Args:
            **kwargs: Task-specific arguments.

        Returns:
            AgentResponse with results.
        """
        self.logger.info(f"Executing {self.role.value} agent")

        try:
            # Build prompt
            task_prompt = self.build_task_prompt(**kwargs)

            # Generate response
            raw_output = self.llm_client.generate(self.system_prompt, task_prompt)

            # Parse response
            content = self.parse_response(raw_output)

            self.logger.info(f"{self.role.value} agent completed successfully")

            return AgentResponse(
                role=self.role,
                content=content,
                raw_output=raw_output,
                success=True,
                metadata={"input_kwargs": {k: str(v)[:100] for k, v in kwargs.items()}},
            )

        except Exception as e:
            self.logger.error(f"{self.role.value} agent failed: {e}")
            return AgentResponse(
                role=self.role,
                content=None,
                raw_output="",
                success=False,
                error=str(e),
            )

    def _parse_json_response(self, raw_output: str) -> dict[str, Any]:
        """Helper to parse JSON from LLM output.

        Args:
            raw_output: Raw text that may contain JSON.

        Returns:
            Parsed JSON as dict.
        """
        # Try to extract JSON from markdown code blocks
        if "```json" in raw_output:
            start = raw_output.find("```json") + 7
            end = raw_output.find("```", start)
            if end > start:
                raw_output = raw_output[start:end].strip()
        elif "```" in raw_output:
            start = raw_output.find("```") + 3
            end = raw_output.find("```", start)
            if end > start:
                raw_output = raw_output[start:end].strip()

        # Try to find JSON object
        if "{" in raw_output:
            start = raw_output.find("{")
            # Find matching closing brace
            depth = 0
            for i, c in enumerate(raw_output[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        raw_output = raw_output[start : i + 1]
                        break

        return json.loads(raw_output)
