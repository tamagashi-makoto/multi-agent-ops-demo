"""Tool registry with allowlist enforcement."""

from typing import Any, Callable
from dataclasses import dataclass, field

from app.common.guardrails import Guardrails, get_guardrails, GuardrailError
from app.common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Tool:
    """A registered tool."""

    name: str
    description: str
    func: Callable
    requires_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool."""
        return self.func(*args, **kwargs)


class ToolRegistry:
    """Registry for managing tools with allowlist enforcement."""

    def __init__(self, guardrails: Guardrails | None = None):
        """Initialize tool registry.

        Args:
            guardrails: Guardrails instance for validation.
        """
        self.guardrails = guardrails or get_guardrails()
        self._tools: dict[str, Tool] = {}
        logger.info("Initialized ToolRegistry")

    def register(
        self,
        name: str,
        description: str,
        requires_approval: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Callable:
        """Decorator to register a tool.

        Args:
            name: Tool name (must be in allowlist).
            description: Tool description.
            requires_approval: Whether tool requires human approval.
            metadata: Additional metadata.

        Returns:
            Decorator function.
        """

        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                description=description,
                func=func,
                requires_approval=requires_approval,
                metadata=metadata or {},
            )
            self._tools[name] = tool
            logger.debug(f"Registered tool: {name}")
            return func

        return decorator

    def register_tool(self, tool: Tool) -> None:
        """Register an existing Tool instance.

        Args:
            tool: Tool to register.
        """
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool if found, None otherwise.
        """
        return self._tools.get(name)

    def execute(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a tool with guardrail validation.

        Args:
            name: Tool name.
            *args: Tool arguments.
            **kwargs: Tool keyword arguments.

        Returns:
            Tool result.

        Raises:
            GuardrailError: If tool is not in allowlist.
            ValueError: If tool is not registered.
        """
        # Validate against allowlist
        self.guardrails.validate_tool(name)

        # Get the tool
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' is not registered")

        # Increment step counter
        self.guardrails.increment_step()

        logger.info(f"Executing tool: {name}")
        result = tool(*args, **kwargs)
        logger.debug(f"Tool {name} completed")

        return result

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools.

        Returns:
            List of tool information dictionaries.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "requires_approval": tool.requires_approval,
                "metadata": tool.metadata,
            }
            for tool in self._tools.values()
        ]

    def list_allowed_tools(self) -> list[str]:
        """List tools that are both registered and in allowlist.

        Returns:
            List of allowed tool names.
        """
        return [
            name
            for name in self._tools.keys()
            if name in self.guardrails.tool_allowlist
        ]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.debug("Cleared all tools")


# Singleton instance
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the tool registry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def reset_tool_registry() -> None:
    """Reset the tool registry singleton."""
    global _registry
    _registry = None
