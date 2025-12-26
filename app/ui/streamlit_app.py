"""Streamlit application for Multi-Agent Ops Demo."""

import streamlit as st
import time
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.orchestrator.graph import run_workflow
from app.orchestrator.state import WorkflowStatus
from app.orchestrator.approval import get_approval_gate
from app.observability.run_manager import get_run_manager
from app.observability.tracer import get_tracer
from app.rag.retriever import get_retriever
from app.ui.components import (
    render_status_badge,
    render_score_gauge,
    render_trace_timeline,
    render_findings_cards,
    render_critique_report,
    render_markdown_preview,
    render_run_card,
)


def init_session_state():
    """Initialize session state variables."""
    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None
    if "is_running" not in st.session_state:
        st.session_state.is_running = False


def load_sample_documents():
    """Load sample documents into RAG."""
    retriever = get_retriever()
    if retriever.document_count == 0:
        data_dir = Path(__file__).parent.parent.parent / "data" / "documents"
        if data_dir.exists():
            count = retriever.load_documents_from_directory(data_dir)
            return count
    return retriever.document_count


def run_workflow_sync(request: str, customer_context: str) -> dict:
    """Run workflow synchronously for Streamlit.

    Args:
        request: User request.
        customer_context: Customer context.

    Returns:
        Final workflow state.
    """
    state = run_workflow(
        request=request,
        customer_context=customer_context,
    )

    # Save state
    run_manager = get_run_manager()
    run_manager.save_state(state)

    return state


def render_sidebar():
    """Render sidebar with run history."""
    st.sidebar.title("🤖 Run History")

    run_manager = get_run_manager()
    runs = run_manager.list_runs()

    if not runs:
        st.sidebar.info("No run history")
        return

    for run in runs[:10]:  # Show last 10
        status = run.get("status", "unknown")
        status_emoji = {
            "completed": "✅",
            "approved": "✅",
            "failed": "❌",
            "awaiting_approval": "⏳",
        }.get(status, "🔄")

        if st.sidebar.button(
            f"{status_emoji} {run['run_id']}",
            key=f"run_{run['run_id']}",
            use_container_width=True,
        ):
            st.session_state.current_run_id = run["run_id"]
            st.rerun()


def render_new_run_form():
    """Render form for starting a new run."""
    st.header("🚀 Create New Proposal")

    with st.form("new_run_form"):
        request = st.text_area(
            "Request",
            value="Please create a proposal for introducing an AI quality control system to a medium-sized manufacturing company.",
            height=100,
            help="Describe the content and purpose of the proposal",
        )

        customer_context = st.text_area(
            "Customer Context",
            value="Manufacturing company with 500 employees. Considering automation of quality inspection. Budget is around 5 million yen per year.",
            height=100,
            help="Describe the customer's background information",
        )

        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.form_submit_button("🎯 Run", type="primary")

        if submitted:
            st.session_state.is_running = True

            # Progress display
            with st.spinner("Agents are working..."):
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Update progress during execution
                status_text.text("📋 Planning...")
                progress_bar.progress(10)

                try:
                    state = run_workflow_sync(request, customer_context)

                    progress_bar.progress(100)
                    status_text.text("✅ Complete!")

                    st.session_state.current_run_id = state.get("run_id")
                    st.session_state.is_running = False

                    if state.get("status") == WorkflowStatus.FAILED.value:
                        st.error(f"Error: {state.get('error', 'Unknown error')}")
                    else:
                        st.success(f"Created Run ID: {state.get('run_id')}")

                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    st.error(f"Execution Error: {e}")
                    st.session_state.is_running = False


def render_run_detail(run_id: str):
    """Render details for a specific run.

    Args:
        run_id: Run ID to display.
    """
    run_manager = get_run_manager()
    state = run_manager.load_state(run_id)

    if not state:
        st.error(f"Run {run_id} not found")
        return

    # Header
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.header(f"📄 Run: {run_id}")
    with col2:
        st.markdown(
            render_status_badge(state.get("status", "unknown")),
            unsafe_allow_html=True,
        )
    with col3:
        if st.button("🔙 Back"):
            st.session_state.current_run_id = None
            st.rerun()

    # Tabs for different views
    tabs = st.tabs(["📊 Overview", "📋 Plan", "🔍 Research", "✍️ Draft", "🔬 Critique", "📜 Trace"])

    # Overview tab
    with tabs[0]:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Request")
            st.info(state.get("request", ""))

            st.subheader("Customer Context")
            st.info(state.get("customer_context", "") or "None")

        with col2:
            st.subheader("Status")
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            with metrics_col1:
                st.metric("Step", state.get("current_step", 0))
            with metrics_col2:
                st.metric("Draft Version", state.get("draft_version", 0))
            with metrics_col3:
                st.metric("Citations", state.get("citation_count", 0))

            # Approval section
            if state.get("status") == WorkflowStatus.AWAITING_APPROVAL.value:
                st.subheader("⏳ Awaiting Approval")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Approve", type="primary", use_container_width=True):
                        approval_gate = get_approval_gate()
                        approval_gate.approve(run_id, "human")
                        state["approved"] = True
                        state["status"] = WorkflowStatus.APPROVED.value
                        state["final_draft"] = state.get("draft", "")
                        run_manager.save_state(state)
                        st.success("Approved!")
                        st.rerun()
                with col_b:
                    if st.button("❌ Reject", use_container_width=True):
                        approval_gate = get_approval_gate()
                        approval_gate.reject(run_id, "human")
                        st.warning("Rejected")
                        st.rerun()

            elif state.get("approved"):
                st.success("✅ Approved")

    # Plan tab
    with tabs[1]:
        st.subheader("Requirements")
        for req in state.get("requirements", []):
            st.markdown(f"- {req}")

        st.subheader("Tasks")
        for task in state.get("tasks", []):
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                task.get("priority", "medium"), "⚪"
            )
            with st.expander(f"{priority_emoji} {task.get('description', '')}"):
                st.write("Required Info:")
                for info in task.get("required_info", []):
                    st.markdown(f"  - {info}")

        if state.get("questions"):
            st.subheader("Additional Questions")
            for q in state.get("questions", []):
                st.warning(f"❓ {q}")

    # Research tab
    with tabs[2]:
        findings = state.get("research_findings", [])
        if findings:
            render_findings_cards(findings)
        else:
            st.info("No research findings")

        if state.get("missing_info"):
            st.subheader("Missing Info")
            for info in state.get("missing_info", []):
                st.warning(f"⚠️ {info}")

    # Draft tab
    with tabs[3]:
        draft = state.get("draft", "")
        if draft:
            render_markdown_preview(draft, "Proposal Draft")
        else:
            st.info("No draft available")

        final = state.get("final_draft", "")
        if final and state.get("approved"):
            st.divider()
            st.subheader("✅ Final Version")
            render_markdown_preview(final, "Final Proposal")

    # Critique tab
    with tabs[4]:
        critique = state.get("critique", {})
        if critique:
            render_critique_report(critique)
        else:
            st.info("No critique results")

    # Trace tab
    with tabs[5]:
        trace = state.get("trace", [])
        if trace:
            render_trace_timeline(trace)
        else:
            # Try loading from file
            tracer = get_tracer()
            entries = tracer.get_trace(run_id)
            if entries:
                render_trace_timeline([e.__dict__ for e in entries])
            else:
                st.info("No trace available")


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Multi-Agent Ops Demo",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown(
        """
        <style>
        .stApp {
            max-width: 1400px;
            margin: 0 auto;
        }
        .stButton button {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    init_session_state()

    # Load sample documents
    doc_count = load_sample_documents()

    # Header
    st.title("🤖 Multi-Agent Ops Demo")
    st.caption(f"RAG Database: {doc_count} documents")

    # Sidebar
    render_sidebar()

    # Main content
    if st.session_state.current_run_id:
        render_run_detail(st.session_state.current_run_id)
    else:
        render_new_run_form()

        # Quick info
        st.divider()
        with st.expander("ℹ️ About this Demo"):
            st.markdown(
                """
                ## Multi-Agent System Demo

                This demo creates proposals using multiple collaborative AI agents.

                ### Agent Roles
                - **Planner**: Requirements organization and task decomposition
                - **Researcher**: Evidence gathering via RAG search
                - **Writer**: Draft generation
                - **Critic**: Quality check and improvement suggestions

                ### Guardrails
                - Tool execution limited by allowlist
                - File writing restricted to runs/ directory
                - Human approval required before final output (AUTO_APPROVE=false)
                - PII automatically masked

                ### Tech Stack
                - Python 3.11+ / FastAPI / Streamlit
                - LangGraph (Orchestration)
                - FAISS (Vector Search)
                """
            )


if __name__ == "__main__":
    main()
