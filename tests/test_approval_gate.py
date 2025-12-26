"""Tests for approval gate functionality."""

import pytest
import os

from app.orchestrator.approval import ApprovalGate, ApprovalStatus, get_approval_gate
from app.orchestrator.state import create_initial_state, WorkflowStatus
from app.orchestrator.coordinator import Coordinator


class TestApprovalGate:
    """Tests for approval gate."""

    def test_approval_gate_blocks_without_approval(self, approval_gate):
        """Test that final output requires approval when AUTO_APPROVE=false."""
        os.environ["AUTO_APPROVE"] = "false"

        # Request approval
        request = approval_gate.request_approval(
            run_id="test-123",
            content="Test draft content",
            context={"version": 1},
        )

        # Should be pending
        assert request.status == ApprovalStatus.PENDING
        assert approval_gate.is_pending("test-123")
        assert not approval_gate.is_approved("test-123")

    def test_approval_gate_allows_with_approval(self, approval_gate):
        """Test that approval allows final output."""
        os.environ["AUTO_APPROVE"] = "false"

        # Request approval
        approval_gate.request_approval(
            run_id="test-456",
            content="Test draft content",
        )

        # Approve
        result = approval_gate.approve("test-456", resolver="test_user")

        assert result is True
        assert approval_gate.is_approved("test-456")

    def test_auto_approve_mode(self):
        """Test that AUTO_APPROVE=true auto-approves."""
        os.environ["AUTO_APPROVE"] = "true"

        gate = ApprovalGate()

        request = gate.request_approval(
            run_id="test-789",
            content="Test content",
        )

        # Should be auto-approved
        assert request.status == ApprovalStatus.APPROVED
        assert request.resolver == "auto"

    def test_rejection(self, approval_gate):
        """Test rejection flow."""
        approval_gate.request_approval(
            run_id="test-reject",
            content="Content to reject",
        )

        result = approval_gate.reject("test-reject", comments="Needs revision")

        assert result is True

        request = approval_gate.get_request("test-reject")
        assert request.status == ApprovalStatus.REJECTED
        assert request.comments == "Needs revision"

    def test_list_pending(self, approval_gate):
        """Test listing pending approvals."""
        # Create multiple requests
        approval_gate.request_approval("run-1", "Content 1")
        approval_gate.request_approval("run-2", "Content 2")
        approval_gate.request_approval("run-3", "Content 3")

        # Approve one
        approval_gate.approve("run-2")

        pending = approval_gate.list_pending()

        assert len(pending) == 2
        run_ids = [p.run_id for p in pending]
        assert "run-1" in run_ids
        assert "run-3" in run_ids
        assert "run-2" not in run_ids


class TestApprovalInWorkflow:
    """Tests for approval gate in workflow context."""

    def test_workflow_pauses_for_approval(self, test_runs_dir, sample_documents):
        """Test that workflow pauses at approval point."""
        os.environ["AUTO_APPROVE"] = "false"
        os.environ["RUNS_DIR"] = str(test_runs_dir)

        from app.rag.retriever import get_retriever

        # Load sample docs
        retriever = get_retriever()
        retriever.load_documents_from_directory(sample_documents)

        # Create initial state
        state = create_initial_state(
            request="テスト提案書を作成してください",
            customer_context="テスト顧客",
        )

        # Run coordinator steps
        coordinator = Coordinator()

        state = coordinator.execute_planning(state)
        assert state["status"] != WorkflowStatus.FAILED.value

        state = coordinator.execute_research(state)
        state = coordinator.execute_writing(state)
        state = coordinator.execute_critique(state)

        # Now request approval
        state = coordinator.request_approval(state)

        # Should be awaiting approval
        assert state["status"] == WorkflowStatus.AWAITING_APPROVAL.value
        assert not state.get("approved", False)

    def test_workflow_finalizes_after_approval(self, test_runs_dir, sample_documents):
        """Test that workflow finalizes after approval."""
        os.environ["AUTO_APPROVE"] = "true"
        os.environ["RUNS_DIR"] = str(test_runs_dir)

        from app.rag.retriever import get_retriever

        # Load sample docs
        retriever = get_retriever()
        retriever.load_documents_from_directory(sample_documents)

        # Create state
        state = create_initial_state(
            request="テスト提案書",
            customer_context="",
        )

        coordinator = Coordinator()

        # Run through workflow
        state = coordinator.execute_planning(state)
        state = coordinator.execute_research(state)
        state = coordinator.execute_writing(state)
        state = coordinator.execute_critique(state)
        state = coordinator.request_approval(state)

        # With auto-approve, should be approved
        assert state.get("approved", False) is True
        assert state["status"] == WorkflowStatus.APPROVED.value

        # Finalize
        state = coordinator.finalize(state)
        assert state["status"] == WorkflowStatus.COMPLETED.value
        assert state.get("final_draft", "") != ""
