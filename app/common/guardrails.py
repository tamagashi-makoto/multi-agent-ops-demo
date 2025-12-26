"""Guardrails for safe agent execution."""

from pathlib import Path
from typing import Any, Callable

from app.common.config import get_settings
from app.common.logger import get_logger

logger = get_logger(__name__)


class GuardrailError(Exception):
    """Exception raised when a guardrail is violated."""

    pass


class Guardrails:
    """Guardrails for safe agent and tool execution."""

    # Default allowed tools
    DEFAULT_ALLOWLIST = frozenset({
        "retrieve",
        "write_draft",
        "critique",
        "summarize",
        "search_documents",
        "get_context",
    })

    def __init__(
        self,
        tool_allowlist: frozenset[str] | None = None,
        allowed_write_paths: list[Path] | None = None,
        max_steps: int | None = None,
        max_parallel: int | None = None,
    ):
        """Initialize guardrails.

        Args:
            tool_allowlist: Set of allowed tool names.
            allowed_write_paths: List of paths where writing is allowed.
            max_steps: Maximum steps per run.
            max_parallel: Maximum parallel executions.
        """
        settings = get_settings()

        self.tool_allowlist = tool_allowlist or self.DEFAULT_ALLOWLIST
        self.allowed_write_paths = allowed_write_paths or [settings.runs_path]
        self.max_steps = max_steps or settings.max_steps
        self.max_parallel = max_parallel or settings.max_parallel
        self._current_step = 0
        self._current_parallel = 0

    def validate_tool(self, tool_name: str) -> bool:
        """Check if a tool is in the allowlist.

        Args:
            tool_name: Name of the tool to validate.

        Returns:
            True if tool is allowed.

        Raises:
            GuardrailError: If tool is not in allowlist.
        """
        if tool_name not in self.tool_allowlist:
            msg = f"Tool '{tool_name}' is not in the allowlist. Allowed: {sorted(self.tool_allowlist)}"
            logger.warning(f"[red]Guardrail violation:[/red] {msg}")
            raise GuardrailError(msg)

        logger.debug(f"Tool '{tool_name}' validated successfully")
        return True

    def validate_write_path(self, path: str | Path) -> bool:
        """Check if writing to a path is allowed.

        Args:
            path: Path to validate for writing.

        Returns:
            True if path is allowed.

        Raises:
            GuardrailError: If path is not in allowed write paths.
        """
        target_path = Path(path).resolve()

        for allowed_path in self.allowed_write_paths:
            allowed_resolved = allowed_path.resolve()
            try:
                target_path.relative_to(allowed_resolved)
                logger.debug(f"Write path '{path}' validated (under {allowed_path})")
                return True
            except ValueError:
                continue

        msg = f"Writing to '{path}' is not allowed. Allowed paths: {self.allowed_write_paths}"
        logger.warning(f"[red]Guardrail violation:[/red] {msg}")
        raise GuardrailError(msg)

    def increment_step(self) -> int:
        """Increment and check step count.

        Returns:
            Current step number.

        Raises:
            GuardrailError: If max steps exceeded.
        """
        self._current_step += 1

        if self._current_step > self.max_steps:
            msg = f"Maximum steps ({self.max_steps}) exceeded"
            logger.warning(f"[red]Guardrail violation:[/red] {msg}")
            raise GuardrailError(msg)

        logger.debug(f"Step {self._current_step}/{self.max_steps}")
        return self._current_step

    def reset_steps(self) -> None:
        """Reset step counter."""
        self._current_step = 0
        logger.debug("Step counter reset")

    def check_parallel_limit(self) -> bool:
        """Check if parallel execution limit allows more tasks.

        Returns:
            True if more parallel tasks are allowed.

        Raises:
            GuardrailError: If max parallel exceeded.
        """
        if self._current_parallel >= self.max_parallel:
            msg = f"Maximum parallel executions ({self.max_parallel}) reached"
            logger.warning(f"[red]Guardrail violation:[/red] {msg}")
            raise GuardrailError(msg)

        return True

    def acquire_parallel_slot(self) -> None:
        """Acquire a parallel execution slot."""
        self.check_parallel_limit()
        self._current_parallel += 1
        logger.debug(f"Parallel slot acquired: {self._current_parallel}/{self.max_parallel}")

    def release_parallel_slot(self) -> None:
        """Release a parallel execution slot."""
        if self._current_parallel > 0:
            self._current_parallel -= 1
        logger.debug(f"Parallel slot released: {self._current_parallel}/{self.max_parallel}")

    def wrap_tool(self, tool_name: str, tool_func: Callable) -> Callable:
        """Wrap a tool function with guardrail validation.

        Args:
            tool_name: Name of the tool.
            tool_func: Tool function to wrap.

        Returns:
            Wrapped function with guardrail checks.
        """

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self.validate_tool(tool_name)
            self.increment_step()
            return tool_func(*args, **kwargs)

        wrapped.__name__ = tool_func.__name__
        wrapped.__doc__ = tool_func.__doc__
        return wrapped


# Global guardrails instance
_guardrails: Guardrails | None = None


def get_guardrails() -> Guardrails:
    """Get global guardrails instance."""
    global _guardrails
    if _guardrails is None:
        _guardrails = Guardrails()
    return _guardrails


def reset_guardrails() -> None:
    """Reset global guardrails instance."""
    global _guardrails
    _guardrails = None
