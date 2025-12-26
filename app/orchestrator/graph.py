"""LangGraph workflow definition."""

from typing import Literal, Any

from langgraph.graph import StateGraph, END

from app.common.logger import get_logger
from app.orchestrator.state import WorkflowState, WorkflowStatus, create_initial_state
from app.orchestrator.coordinator import Coordinator
from app.orchestrator.approval import get_approval_gate

logger = get_logger(__name__)


def create_workflow_graph(coordinator: Coordinator | None = None) -> StateGraph:
    """Create the LangGraph workflow for multi-agent coordination.

    The workflow follows this pattern:
    1. Plan -> Research -> Write -> Critique
    2. If revision needed: Revise -> Critique (loop)
    3. If approved: Finalize
    4. Request approval before finalization

    Args:
        coordinator: Coordinator instance.

    Returns:
        Configured StateGraph.
    """
    coord = coordinator or Coordinator()

    # Create the graph
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("plan", coord.execute_planning)
    graph.add_node("research", coord.execute_research)
    graph.add_node("write", coord.execute_writing)
    graph.add_node("critique", coord.execute_critique)
    graph.add_node("revise", coord.execute_revision)
    graph.add_node("request_approval", coord.request_approval)
    graph.add_node("finalize", coord.finalize)

    # Define routing functions
    def route_after_research(state: WorkflowState) -> Literal["write", "plan", END]:
        """Route after research based on sufficiency."""
        if state.get("status") == WorkflowStatus.FAILED.value:
            return END

        if not state.get("research_sufficient", True):
            # Check if we have any findings at all
            if not state.get("research_findings"):
                # No findings - need to update plan with questions
                logger.info("Research insufficient, returning to planning")
                return "plan"

        return "write"

    def route_after_critique(
        state: WorkflowState,
    ) -> Literal["revise", "request_approval", END]:
        """Route after critique based on approval."""
        if state.get("status") == WorkflowStatus.FAILED.value:
            return END

        # Check if revision is needed
        if state.get("revision_needed", False):
            # Limit revision cycles
            if state.get("draft_version", 0) >= 3:
                logger.info("Max revisions reached, proceeding to approval")
                return "request_approval"
            return "revise"

        return "request_approval"

    def route_after_approval(state: WorkflowState) -> Literal["finalize", END]:
        """Route after approval request."""
        if state.get("status") == WorkflowStatus.FAILED.value:
            return END

        if state.get("approved", False):
            return "finalize"

        # If not approved and not auto-approve, we pause here
        # The graph will be resumed after manual approval
        return END

    def should_continue(state: WorkflowState) -> bool:
        """Check if workflow should continue."""
        if state.get("status") == WorkflowStatus.FAILED.value:
            return False
        if state.get("current_step", 0) >= state.get("max_steps", 20):
            logger.warning("Max steps reached")
            return False
        return True

    # Add edges
    graph.add_edge("plan", "research")
    graph.add_conditional_edges(
        "research",
        route_after_research,
        {
            "write": "write",
            "plan": "plan",
            END: END,
        },
    )
    graph.add_edge("write", "critique")
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "revise": "revise",
            "request_approval": "request_approval",
            END: END,
        },
    )
    graph.add_edge("revise", "critique")
    graph.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "finalize": "finalize",
            END: END,
        },
    )
    graph.add_edge("finalize", END)

    # Set entry point
    graph.set_entry_point("plan")

    return graph


def run_workflow(
    request: str,
    customer_context: str = "",
    run_id: str | None = None,
    coordinator: Coordinator | None = None,
) -> WorkflowState:
    """Run the complete workflow.

    Args:
        request: User's request for the proposal.
        customer_context: Information about the customer.
        run_id: Optional run ID.
        coordinator: Optional coordinator instance.

    Returns:
        Final workflow state.
    """
    logger.info("Starting workflow execution")

    # Create initial state
    initial_state = create_initial_state(
        request=request,
        customer_context=customer_context,
        run_id=run_id,
    )

    # Create and compile the graph
    graph = create_workflow_graph(coordinator)
    workflow = graph.compile()

    # Run the workflow
    final_state = workflow.invoke(initial_state)

    logger.info(
        f"Workflow completed with status: {final_state.get('status')}, "
        f"run_id: {final_state.get('run_id')}"
    )

    return final_state


def run_workflow_with_approval_wait(
    request: str,
    customer_context: str = "",
    run_id: str | None = None,
    coordinator: Coordinator | None = None,
    approval_callback: Any | None = None,
) -> WorkflowState:
    """Run workflow with callback for approval waiting.

    This version allows the caller to handle the approval step asynchronously.

    Args:
        request: User's request.
        customer_context: Customer context.
        run_id: Optional run ID.
        coordinator: Optional coordinator.
        approval_callback: Callback when approval is needed.

    Returns:
        Workflow state (may be awaiting approval).
    """
    logger.info("Starting workflow with approval handling")

    # Run initial workflow
    state = run_workflow(
        request=request,
        customer_context=customer_context,
        run_id=run_id,
        coordinator=coordinator,
    )

    # Check if we're waiting for approval
    if state.get("status") == WorkflowStatus.AWAITING_APPROVAL.value:
        if approval_callback:
            # Call the callback with state info
            approval_callback(state)
        else:
            logger.info(
                f"Workflow paused for approval. Run ID: {state.get('run_id')}"
            )

    return state


def resume_after_approval(
    state: WorkflowState,
    coordinator: Coordinator | None = None,
) -> WorkflowState:
    """Resume workflow after approval.

    Args:
        state: Current state (should be APPROVED).
        coordinator: Optional coordinator.

    Returns:
        Final workflow state.
    """
    if state.get("status") != WorkflowStatus.APPROVED.value:
        logger.warning(f"Cannot resume: status is {state.get('status')}")
        return state

    coord = coordinator or Coordinator()

    # Just finalize
    return coord.finalize(state)
