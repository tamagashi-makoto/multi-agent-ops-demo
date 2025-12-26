"""Tests for trace saving functionality."""

import pytest
import json
from pathlib import Path

from app.observability.tracer import Tracer, TraceEntry
from app.observability.run_manager import RunManager
from app.orchestrator.state import create_initial_state


class TestTracer:
    """Tests for trace logging."""

    def test_trace_entry_creation(self, test_runs_dir):
        """Test creating trace entries."""
        tracer = Tracer(runs_dir=test_runs_dir)

        entry = tracer.trace(
            run_id="test-run",
            agent="planner",
            action="create_plan",
            input_data={"request": "Test request"},
            output_data={"plan": "Test plan"},
        )

        assert entry.run_id == "test-run"
        assert entry.agent == "planner"
        assert entry.action == "create_plan"
        assert entry.success is True

    def test_trace_saved_to_file(self, test_runs_dir):
        """Test that trace entries are saved to JSONL file."""
        tracer = Tracer(runs_dir=test_runs_dir)

        # Create entries
        tracer.trace("run-1", "agent1", "action1", {}, {})
        tracer.trace("run-1", "agent2", "action2", {}, {})

        # Check file exists
        trace_file = test_runs_dir / "run-1" / "trace.jsonl"
        assert trace_file.exists()

        # Check content
        lines = trace_file.read_text().strip().split("\n")
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["agent"] == "agent1"

        entry2 = json.loads(lines[1])
        assert entry2["agent"] == "agent2"

    def test_trace_retrieval(self, test_runs_dir):
        """Test retrieving trace entries."""
        tracer = Tracer(runs_dir=test_runs_dir)

        # Create entries
        tracer.trace("run-2", "planner", "plan", {"x": 1}, {"y": 2})
        tracer.trace("run-2", "researcher", "search", {"q": "test"}, {"results": []})

        # Retrieve
        entries = tracer.get_trace("run-2")

        assert len(entries) == 2
        assert entries[0].agent == "planner"
        assert entries[1].agent == "researcher"

    def test_pii_masking(self, test_runs_dir):
        """Test that PII is masked in traces."""
        tracer = Tracer(runs_dir=test_runs_dir, mask_pii=True)

        # Input with email
        tracer.trace(
            run_id="pii-test",
            agent="agent",
            action="process",
            input_data={"email": "test@example.com"},
            output_data={"message": "Contact: user@domain.com"},
        )

        # Check trace file
        trace_file = test_runs_dir / "pii-test" / "trace.jsonl"
        content = trace_file.read_text()
        entry = json.loads(content.strip())

        # Emails should be masked
        assert "test@example.com" not in str(entry)
        assert "user@domain.com" not in str(entry)
        assert "[MASKED]" in str(entry)

    def test_error_trace(self, test_runs_dir):
        """Test tracing errors."""
        tracer = Tracer(runs_dir=test_runs_dir)

        entry = tracer.trace(
            run_id="error-run",
            agent="writer",
            action="write",
            input_data={},
            output_data={},
            success=False,
            error="Test error message",
        )

        assert entry.success is False
        assert entry.error == "Test error message"

        # Verify in file
        entries = tracer.get_trace("error-run")
        assert len(entries) == 1
        assert entries[0].success is False


class TestRunManager:
    """Tests for run output management."""

    def test_save_plan(self, test_runs_dir):
        """Test saving plan output."""
        manager = RunManager(runs_dir=test_runs_dir)

        plan = {
            "requirements": ["req1", "req2"],
            "tasks": [{"id": 1, "description": "Task 1"}],
        }

        path = manager.save_plan("run-plan", plan)

        assert path.exists()
        saved = json.loads(path.read_text())
        assert saved["requirements"] == ["req1", "req2"]

    def test_save_draft(self, test_runs_dir):
        """Test saving draft with versioning."""
        manager = RunManager(runs_dir=test_runs_dir)

        # Save v1
        manager.save_draft("run-draft", "Draft content v1", version=1)

        # Save v2
        manager.save_draft("run-draft", "Draft content v2", version=2)

        run_dir = test_runs_dir / "run-draft"

        # Check current draft
        assert (run_dir / "draft.md").exists()

        # Check versioned copies
        assert (run_dir / "draft_v1.md").exists()
        assert (run_dir / "draft_v2.md").exists()

        # Current should be v2
        content = (run_dir / "draft.md").read_text()
        assert "Draft content v2" in content
        assert "Version: 2" in content

    def test_save_critique(self, test_runs_dir):
        """Test saving critique report."""
        manager = RunManager(runs_dir=test_runs_dir)

        critique = {
            "overall_score": 85,
            "approved": True,
            "issues": [
                {"type": "clarity", "severity": "low", "description": "Minor issue"}
            ],
            "summary": "Good draft",
        }

        path = manager.save_critique("run-critique", critique)

        assert path.exists()
        content = path.read_text()
        assert "85" in content
        assert "Good draft" in content

    def test_save_complete_state(self, test_runs_dir):
        """Test saving complete workflow state."""
        manager = RunManager(runs_dir=test_runs_dir)

        state = create_initial_state(
            request="Test request",
            customer_context="Test context",
            run_id="state-run",
        )
        state["requirements"] = ["req1"]
        state["draft"] = "# Draft\n\nContent"
        state["critique"] = {"overall_score": 80}

        manager.save_state(state)

        # Check all files created
        run_dir = test_runs_dir / "state-run"
        assert (run_dir / "state.json").exists()

    def test_list_runs(self, test_runs_dir):
        """Test listing all runs."""
        manager = RunManager(runs_dir=test_runs_dir)

        # Create some runs
        manager.save_plan("run-1", {"test": 1})
        manager.save_plan("run-2", {"test": 2})
        manager.save_plan("run-3", {"test": 3})

        runs = manager.list_runs()

        run_ids = [r["run_id"] for r in runs]
        assert "run-1" in run_ids
        assert "run-2" in run_ids
        assert "run-3" in run_ids

    def test_delete_run(self, test_runs_dir):
        """Test deleting a run."""
        manager = RunManager(runs_dir=test_runs_dir)

        # Create a run
        manager.save_plan("to-delete", {"test": 1})
        manager.save_draft("to-delete", "Draft content", 1)

        assert (test_runs_dir / "to-delete").exists()

        # Delete
        result = manager.delete_run("to-delete")

        assert result is True
        assert not (test_runs_dir / "to-delete").exists()
