"""Workflow state management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
import uuid


class WorkflowStatus(str, Enum):
    """Status of the workflow."""

    PENDING = "pending"
    PLANNING = "planning"
    RESEARCHING = "researching"
    WRITING = "writing"
    CRITIQUING = "critiquing"
    REVISING = "revising"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowState(TypedDict, total=False):
    """State passed through the LangGraph workflow.

    This TypedDict defines the schema for state that flows through
    the multi-agent workflow graph.
    """

    # Run identification
    run_id: str
    created_at: str
    updated_at: str

    # Status tracking
    status: str
    current_step: int
    max_steps: int

    # Input
    request: str
    customer_context: str

    # Planner output
    plan: dict[str, Any]
    requirements: list[str]
    tasks: list[dict[str, Any]]
    questions: list[str]

    # Researcher output
    research_findings: list[dict[str, Any]]
    missing_info: list[str]
    research_sufficient: bool

    # Writer output
    draft: str
    draft_version: int
    citation_count: int

    # Critic output
    critique: dict[str, Any]
    critique_score: int
    revision_needed: bool

    # Final output
    final_draft: str
    approved: bool
    approval_timestamp: str

    # Error handling
    error: str | None
    retry_count: int

    # Trace
    trace: list[dict[str, Any]]


def create_initial_state(
    request: str,
    customer_context: str = "",
    run_id: str | None = None,
    max_steps: int = 20,
) -> WorkflowState:
    """Create initial workflow state.

    Args:
        request: User's request for the proposal.
        customer_context: Information about the customer.
        run_id: Optional run ID (generated if not provided).
        max_steps: Maximum steps allowed.

    Returns:
        Initial workflow state.
    """
    now = datetime.utcnow().isoformat()

    return WorkflowState(
        # Run identification
        run_id=run_id or str(uuid.uuid4())[:8],
        created_at=now,
        updated_at=now,
        # Status
        status=WorkflowStatus.PENDING.value,
        current_step=0,
        max_steps=max_steps,
        # Input
        request=request,
        customer_context=customer_context,
        # Planner
        plan={},
        requirements=[],
        tasks=[],
        questions=[],
        # Researcher
        research_findings=[],
        missing_info=[],
        research_sufficient=False,
        # Writer
        draft="",
        draft_version=0,
        citation_count=0,
        # Critic
        critique={},
        critique_score=0,
        revision_needed=False,
        # Final
        final_draft="",
        approved=False,
        approval_timestamp="",
        # Error handling
        error=None,
        retry_count=0,
        # Trace
        trace=[],
    )


def update_state(state: WorkflowState, **updates: Any) -> WorkflowState:
    """Update state with new values.

    Args:
        state: Current state.
        **updates: Values to update.

    Returns:
        Updated state.
    """
    new_state = dict(state)
    new_state.update(updates)
    new_state["updated_at"] = datetime.utcnow().isoformat()
    return WorkflowState(**new_state)


def add_trace_entry(
    state: WorkflowState,
    agent: str,
    action: str,
    input_data: Any,
    output_data: Any,
    success: bool = True,
    error: str | None = None,
) -> WorkflowState:
    """Add a trace entry to the state.

    Args:
        state: Current state.
        agent: Agent name.
        action: Action performed.
        input_data: Input to the action.
        output_data: Output from the action.
        success: Whether action succeeded.
        error: Error message if failed.

    Returns:
        Updated state with new trace entry.
    """
    trace_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "step": state.get("current_step", 0),
        "agent": agent,
        "action": action,
        "input": _sanitize_for_trace(input_data),
        "output": _sanitize_for_trace(output_data),
        "success": success,
        "error": error,
    }

    trace = list(state.get("trace", []))
    trace.append(trace_entry)

    return update_state(state, trace=trace, current_step=state.get("current_step", 0) + 1)


def _sanitize_for_trace(data: Any, max_length: int = 1000) -> Any:
    """Sanitize data for trace storage.

    Args:
        data: Data to sanitize.
        max_length: Maximum string length.

    Returns:
        Sanitized data.
    """
    if isinstance(data, str):
        if len(data) > max_length:
            return data[:max_length] + "...[truncated]"
        return data
    elif isinstance(data, dict):
        return {k: _sanitize_for_trace(v, max_length) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_for_trace(item, max_length) for item in data[:10]]
    else:
        return data
