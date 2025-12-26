"""Coordinator for managing agent execution flow."""

from typing import Any

from app.agents import PlannerAgent, ResearcherAgent, WriterAgent, CriticAgent
from app.agents.base import LLMClient, AgentResponse
from app.common.guardrails import get_guardrails, GuardrailError
from app.common.logger import get_logger
from app.orchestrator.state import (
    WorkflowState,
    WorkflowStatus,
    update_state,
    add_trace_entry,
)
from app.orchestrator.approval import ApprovalGate, get_approval_gate, ApprovalStatus
from app.rag.retriever import get_retriever

logger = get_logger(__name__)


class Coordinator:
    """Coordinator for managing multi-agent workflow execution.

    The Coordinator implements the Coordinator-Worker pattern where it:
    1. Dispatches tasks to appropriate agents
    2. Manages state transitions
    3. Handles failures and retries
    4. Enforces guardrails
    5. Manages human approval checkpoints
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        approval_gate: ApprovalGate | None = None,
    ):
        """Initialize coordinator.

        Args:
            llm_client: Shared LLM client.
            approval_gate: Approval gate instance.
        """
        self.llm_client = llm_client or LLMClient()
        self.approval_gate = approval_gate or get_approval_gate()
        self.guardrails = get_guardrails()

        # Initialize agents
        self.planner = PlannerAgent(self.llm_client)
        self.researcher = ResearcherAgent(self.llm_client)
        self.writer = WriterAgent(self.llm_client)
        self.critic = CriticAgent(self.llm_client)

        logger.info("Initialized Coordinator with all agents")

    def execute_planning(self, state: WorkflowState) -> WorkflowState:
        """Execute planning phase.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with plan.
        """
        logger.info(f"[{state['run_id']}] Starting planning phase")

        state = update_state(state, status=WorkflowStatus.PLANNING.value)

        try:
            response = self.planner.execute(
                request=state["request"],
                available_docs="Internal documents (Product Overview, Pricing, FAQ, Case Studies)",
            )

            if not response.success:
                return self._handle_agent_error(state, "planner", response)

            plan_result = response.content

            state = add_trace_entry(
                state,
                agent="planner",
                action="create_plan",
                input_data={"request": state["request"]},
                output_data=plan_result.to_dict() if hasattr(plan_result, 'to_dict') else plan_result,
            )

            state = update_state(
                state,
                plan=plan_result.to_dict() if hasattr(plan_result, 'to_dict') else {},
                requirements=plan_result.requirements if hasattr(plan_result, 'requirements') else [],
                tasks=plan_result.tasks if hasattr(plan_result, 'tasks') else [],
                questions=plan_result.questions if hasattr(plan_result, 'questions') else [],
            )

            logger.info(
                f"[{state['run_id']}] Planning complete: "
                f"{len(state['requirements'])} requirements, "
                f"{len(state['tasks'])} tasks"
            )

            return state

        except GuardrailError as e:
            return self._handle_guardrail_error(state, "planner", e)
        except Exception as e:
            return self._handle_exception(state, "planner", e)

    def execute_research(self, state: WorkflowState) -> WorkflowState:
        """Execute research phase.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with research findings.
        """
        logger.info(f"[{state['run_id']}] Starting research phase")

        state = update_state(state, status=WorkflowStatus.RESEARCHING.value)

        try:
            # Extract search topics from tasks
            search_topics = []
            for task in state.get("tasks", []):
                for info in task.get("required_info", []):
                    search_topics.append(info)

            if not search_topics:
                # Default fallback
                search_topics = state.get("requirements", ["Product Information"])

            # Load documents if retriever is empty
            retriever = get_retriever()
            if retriever.document_count == 0:
                retriever.load_documents_from_directory("data/documents")

            # Execute research with RAG
            research_result = self.researcher.execute_with_rag(
                search_topics=search_topics,
                plan_context=state.get("plan", {}).get("summary", ""),
            )

            state = add_trace_entry(
                state,
                agent="researcher",
                action="research",
                input_data={"topics": search_topics},
                output_data=research_result.to_dict(),
            )

            state = update_state(
                state,
                research_findings=[f.to_dict() for f in research_result.findings],
                missing_info=research_result.missing_info,
                research_sufficient=research_result.overall_sufficient,
            )

            logger.info(
                f"[{state['run_id']}] Research complete: "
                f"{len(state['research_findings'])} findings, "
                f"sufficient={state['research_sufficient']}"
            )

            return state

        except GuardrailError as e:
            return self._handle_guardrail_error(state, "researcher", e)
        except Exception as e:
            return self._handle_exception(state, "researcher", e)

    def execute_writing(self, state: WorkflowState) -> WorkflowState:
        """Execute writing phase.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with draft.
        """
        logger.info(f"[{state['run_id']}] Starting writing phase")

        state = update_state(state, status=WorkflowStatus.WRITING.value)

        try:
            # Format research findings
            research_text = self.writer.format_research_for_writing(
                state.get("research_findings", [])
            )

            response = self.writer.execute(
                requirements=state.get("requirements", []),
                research_findings=research_text,
                customer_context=state.get("customer_context", "General Corporate Customer"),
            )

            if not response.success:
                return self._handle_agent_error(state, "writer", response)

            draft_result = response.content

            state = add_trace_entry(
                state,
                agent="writer",
                action="write_draft",
                input_data={
                    "requirements": state.get("requirements", []),
                    "findings_count": len(state.get("research_findings", [])),
                },
                output_data={
                    "sections": draft_result.sections if hasattr(draft_result, 'sections') else [],
                    "citation_count": draft_result.citation_count if hasattr(draft_result, 'citation_count') else 0,
                },
            )

            state = update_state(
                state,
                draft=draft_result.content if hasattr(draft_result, 'content') else str(draft_result),
                draft_version=state.get("draft_version", 0) + 1,
                citation_count=draft_result.citation_count if hasattr(draft_result, 'citation_count') else 0,
            )

            logger.info(
                f"[{state['run_id']}] Writing complete: "
                f"version {state['draft_version']}, "
                f"{state['citation_count']} citations"
            )

            return state

        except GuardrailError as e:
            return self._handle_guardrail_error(state, "writer", e)
        except Exception as e:
            return self._handle_exception(state, "writer", e)

    def execute_critique(self, state: WorkflowState) -> WorkflowState:
        """Execute critique phase.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with critique results.
        """
        logger.info(f"[{state['run_id']}] Starting critique phase")

        state = update_state(state, status=WorkflowStatus.CRITIQUING.value)

        try:
            # Format research findings for critique verification
            research_text = "\n".join(
                f"- {f['topic']}: {f['content'][:200]}..."
                for f in state.get("research_findings", [])
            )

            response = self.critic.execute(
                draft=state.get("draft", ""),
                requirements=state.get("requirements", []),
                research_findings=research_text,
            )

            if not response.success:
                return self._handle_agent_error(state, "critic", response)

            critique_result = response.content

            state = add_trace_entry(
                state,
                agent="critic",
                action="critique",
                input_data={"draft_version": state.get("draft_version", 0)},
                output_data=critique_result.to_dict() if hasattr(critique_result, 'to_dict') else critique_result,
            )

            state = update_state(
                state,
                critique=critique_result.to_dict() if hasattr(critique_result, 'to_dict') else {},
                critique_score=critique_result.overall_score if hasattr(critique_result, 'overall_score') else 0,
                revision_needed=critique_result.revision_needed if hasattr(critique_result, 'revision_needed') else False,
            )

            logger.info(
                f"[{state['run_id']}] Critique complete: "
                f"score={state['critique_score']}, "
                f"revision_needed={state['revision_needed']}"
            )

            return state

        except GuardrailError as e:
            return self._handle_guardrail_error(state, "critic", e)
        except Exception as e:
            return self._handle_exception(state, "critic", e)

    def execute_revision(self, state: WorkflowState) -> WorkflowState:
        """Execute revision phase.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with revised draft.
        """
        logger.info(f"[{state['run_id']}] Starting revision phase")

        state = update_state(state, status=WorkflowStatus.REVISING.value)

        try:
            # Generate revision instructions from critique
            critique_result = state.get("critique", {})
            revision_instructions = self.critic.generate_revision_instructions(
                type("CritiqueResult", (), critique_result)()
                if isinstance(critique_result, dict)
                else critique_result
            )

            # Revise the draft
            revised_result = self.writer.revise_draft(
                original_draft=state.get("draft", ""),
                critique_feedback=revision_instructions,
            )

            state = add_trace_entry(
                state,
                agent="writer",
                action="revise_draft",
                input_data={"original_version": state.get("draft_version", 0)},
                output_data={
                    "new_version": state.get("draft_version", 0) + 1,
                    "citation_count": revised_result.citation_count,
                },
            )

            state = update_state(
                state,
                draft=revised_result.content,
                draft_version=state.get("draft_version", 0) + 1,
                citation_count=revised_result.citation_count,
            )

            logger.info(
                f"[{state['run_id']}] Revision complete: version {state['draft_version']}"
            )

            return state

        except GuardrailError as e:
            return self._handle_guardrail_error(state, "writer", e)
        except Exception as e:
            return self._handle_exception(state, "writer", e)

    def request_approval(self, state: WorkflowState) -> WorkflowState:
        """Request human approval for final draft.

        Args:
            state: Current workflow state.

        Returns:
            Updated state awaiting approval.
        """
        logger.info(f"[{state['run_id']}] Requesting approval")

        state = update_state(state, status=WorkflowStatus.AWAITING_APPROVAL.value)

        approval_request = self.approval_gate.request_approval(
            run_id=state["run_id"],
            content=state.get("draft", ""),
            context={
                "requirements": state.get("requirements", []),
                "critique_score": state.get("critique_score", 0),
                "draft_version": state.get("draft_version", 0),
            },
        )

        state = add_trace_entry(
            state,
            agent="coordinator",
            action="request_approval",
            input_data={"draft_version": state.get("draft_version", 0)},
            output_data={"status": approval_request.status.value},
        )

        if approval_request.status == ApprovalStatus.APPROVED:
            state = update_state(
                state,
                approved=True,
                approval_timestamp=approval_request.resolved_at or "",
                final_draft=state.get("draft", ""),
                status=WorkflowStatus.APPROVED.value,
            )
        else:
            state = update_state(state, approved=False)

        return state

    def finalize(self, state: WorkflowState) -> WorkflowState:
        """Finalize the workflow.

        Args:
            state: Current workflow state.

        Returns:
            Final state.
        """
        logger.info(f"[{state['run_id']}] Finalizing workflow")

        state = update_state(
            state,
            status=WorkflowStatus.COMPLETED.value,
            final_draft=state.get("draft", ""),
        )

        state = add_trace_entry(
            state,
            agent="coordinator",
            action="finalize",
            input_data={},
            output_data={
                "final_version": state.get("draft_version", 0),
                "approved": state.get("approved", False),
            },
        )

        logger.info(f"[{state['run_id']}] Workflow completed successfully")

        return state

    def _handle_agent_error(
        self,
        state: WorkflowState,
        agent: str,
        response: AgentResponse,
    ) -> WorkflowState:
        """Handle agent execution error.

        Args:
            state: Current state.
            agent: Agent name.
            response: Failed response.

        Returns:
            Updated state with error.
        """
        logger.error(f"[{state['run_id']}] {agent} failed: {response.error}")

        state = add_trace_entry(
            state,
            agent=agent,
            action="error",
            input_data={},
            output_data={},
            success=False,
            error=response.error,
        )

        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            state = update_state(state, retry_count=retry_count + 1)
            logger.info(f"[{state['run_id']}] Retry {retry_count + 1}/3")
        else:
            state = update_state(
                state,
                status=WorkflowStatus.FAILED.value,
                error=f"Agent {agent} failed after 3 retries: {response.error}",
            )

        return state

    def _handle_guardrail_error(
        self,
        state: WorkflowState,
        agent: str,
        error: GuardrailError,
    ) -> WorkflowState:
        """Handle guardrail violation.

        Args:
            state: Current state.
            agent: Agent name.
            error: Guardrail error.

        Returns:
            Updated state with error.
        """
        logger.error(f"[{state['run_id']}] Guardrail violation in {agent}: {error}")

        state = add_trace_entry(
            state,
            agent=agent,
            action="guardrail_violation",
            input_data={},
            output_data={},
            success=False,
            error=str(error),
        )

        return update_state(
            state,
            status=WorkflowStatus.FAILED.value,
            error=f"Guardrail violation: {error}",
        )

    def _handle_exception(
        self,
        state: WorkflowState,
        agent: str,
        error: Exception,
    ) -> WorkflowState:
        """Handle unexpected exception.

        Args:
            state: Current state.
            agent: Agent name.
            error: Exception.

        Returns:
            Updated state with error.
        """
        logger.exception(f"[{state['run_id']}] Unexpected error in {agent}")

        state = add_trace_entry(
            state,
            agent=agent,
            action="exception",
            input_data={},
            output_data={},
            success=False,
            error=str(error),
        )

        return update_state(
            state,
            status=WorkflowStatus.FAILED.value,
            error=f"Unexpected error in {agent}: {error}",
        )
