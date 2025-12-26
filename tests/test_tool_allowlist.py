"""Tests for tool allowlist functionality."""

import pytest

from app.common.guardrails import Guardrails, GuardrailError
from app.tools.registry import ToolRegistry, Tool


class TestToolAllowlist:
    """Tests for tool allowlist enforcement."""

    def test_allowed_tool_executes(self, guardrails):
        """Test that tools in allowlist can execute."""
        # Default allowlist includes 'retrieve'
        result = guardrails.validate_tool("retrieve")
        assert result is True

    def test_disallowed_tool_blocked(self, guardrails):
        """Test that tools not in allowlist are blocked."""
        with pytest.raises(GuardrailError) as exc_info:
            guardrails.validate_tool("dangerous_tool")

        assert "not in the allowlist" in str(exc_info.value)
        assert "dangerous_tool" in str(exc_info.value)

    def test_custom_allowlist(self):
        """Test custom allowlist configuration."""
        custom_allowlist = frozenset({"tool_a", "tool_b"})
        guardrails = Guardrails(tool_allowlist=custom_allowlist)

        # Allowed
        assert guardrails.validate_tool("tool_a") is True
        assert guardrails.validate_tool("tool_b") is True

        # Not allowed
        with pytest.raises(GuardrailError):
            guardrails.validate_tool("tool_c")

    def test_default_allowlist_contents(self, guardrails):
        """Test default allowlist contains expected tools."""
        expected_tools = {
            "retrieve",
            "write_draft",
            "critique",
            "summarize",
            "search_documents",
            "get_context",
        }

        for tool in expected_tools:
            assert guardrails.validate_tool(tool) is True


class TestToolRegistry:
    """Tests for tool registry with allowlist."""

    def test_registry_validates_on_execute(self, guardrails):
        """Test that registry validates tools before execution."""
        registry = ToolRegistry(guardrails=guardrails)

        # Register a tool
        @registry.register("retrieve", "Test retrieve tool")
        def test_retrieve(query: str) -> str:
            return f"Result: {query}"

        # Should work
        result = registry.execute("retrieve", "test query")
        assert result == "Result: test query"

    def test_registry_blocks_unregistered_tool(self, guardrails):
        """Test that registry blocks execution of unregistered tools."""
        registry = ToolRegistry(guardrails=guardrails)

        with pytest.raises(ValueError) as exc_info:
            registry.execute("retrieve", "test")  # Not registered

        assert "not registered" in str(exc_info.value)

    def test_registry_blocks_not_in_allowlist(self, guardrails):
        """Test that registry blocks tools not in allowlist."""
        registry = ToolRegistry(guardrails=guardrails)

        # Register a tool that's not in allowlist
        @registry.register("dangerous_tool", "Dangerous tool")
        def dangerous_func():
            return "danger!"

        with pytest.raises(GuardrailError):
            registry.execute("dangerous_tool")

    def test_list_allowed_tools(self, guardrails):
        """Test listing only allowed tools."""
        registry = ToolRegistry(guardrails=guardrails)

        # Register tools - some allowed, some not
        @registry.register("retrieve", "Allowed")
        def retrieve():
            pass

        @registry.register("write_draft", "Allowed")
        def write_draft():
            pass

        @registry.register("not_allowed", "Not allowed")
        def not_allowed():
            pass

        allowed = registry.list_allowed_tools()

        assert "retrieve" in allowed
        assert "write_draft" in allowed
        assert "not_allowed" not in allowed

    def test_tool_metadata(self, guardrails):
        """Test tool metadata is preserved."""
        registry = ToolRegistry(guardrails=guardrails)

        @registry.register(
            "retrieve",
            "Retrieve documents",
            requires_approval=False,
            metadata={"category": "rag"},
        )
        def retrieve():
            pass

        tool = registry.get("retrieve")
        assert tool is not None
        assert tool.description == "Retrieve documents"
        assert tool.requires_approval is False
        assert tool.metadata["category"] == "rag"


class TestStepLimits:
    """Tests for step limit enforcement."""

    def test_step_limit_reached(self):
        """Test that max steps limit is enforced."""
        guardrails = Guardrails(max_steps=3)

        guardrails.increment_step()  # 1
        guardrails.increment_step()  # 2
        guardrails.increment_step()  # 3

        with pytest.raises(GuardrailError) as exc_info:
            guardrails.increment_step()  # 4 - should fail

        assert "Maximum steps" in str(exc_info.value)

    def test_step_counter_reset(self):
        """Test that step counter can be reset."""
        guardrails = Guardrails(max_steps=2)

        guardrails.increment_step()
        guardrails.increment_step()

        guardrails.reset_steps()

        # Should work again
        step = guardrails.increment_step()
        assert step == 1
