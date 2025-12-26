"""Run manager for organizing workflow outputs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.common.config import get_settings
from app.common.logger import get_logger
from app.orchestrator.state import WorkflowState

logger = get_logger(__name__)


class RunManager:
    """Manager for organizing and persisting run outputs.

    Each run is stored in runs/<run_id>/ with the following files:
    - plan.json: Planning phase output
    - retrieved.json: Research findings
    - draft.md: Draft proposal
    - critique.md: Critique feedback
    - final.md: Final approved proposal
    - trace.jsonl: Full execution trace
    """

    def __init__(self, runs_dir: Path | None = None):
        """Initialize run manager.

        Args:
            runs_dir: Directory for run outputs.
        """
        settings = get_settings()
        self.runs_dir = runs_dir or settings.runs_path
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized RunManager with runs_dir={self.runs_dir}")

    def get_run_dir(self, run_id: str) -> Path:
        """Get the directory for a specific run.

        Args:
            run_id: Run ID.

        Returns:
            Path to run directory.
        """
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_plan(self, run_id: str, plan: dict[str, Any]) -> Path:
        """Save planning output.

        Args:
            run_id: Run ID.
            plan: Plan data.

        Returns:
            Path to saved file.
        """
        run_dir = self.get_run_dir(run_id)
        file_path = run_dir / "plan.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

        logger.debug(f"Saved plan to {file_path}")
        return file_path

    def save_retrieved(self, run_id: str, findings: list[dict[str, Any]]) -> Path:
        """Save research findings.

        Args:
            run_id: Run ID.
            findings: Research findings.

        Returns:
            Path to saved file.
        """
        run_dir = self.get_run_dir(run_id)
        file_path = run_dir / "retrieved.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"findings": findings, "count": len(findings)}, f, ensure_ascii=False, indent=2)

        logger.debug(f"Saved retrieved to {file_path}")
        return file_path

    def save_draft(self, run_id: str, draft: str, version: int = 1) -> Path:
        """Save draft proposal.

        Args:
            run_id: Run ID.
            draft: Draft content.
            version: Draft version.

        Returns:
            Path to saved file.
        """
        run_dir = self.get_run_dir(run_id)

        # Save current version
        file_path = run_dir / "draft.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- Draft Version: {version} -->\n")
            f.write(f"<!-- Updated: {datetime.utcnow().isoformat()} -->\n\n")
            f.write(draft)

        # Also save versioned copy
        versioned_path = run_dir / f"draft_v{version}.md"
        with open(versioned_path, "w", encoding="utf-8") as f:
            f.write(draft)

        logger.debug(f"Saved draft v{version} to {file_path}")
        return file_path

    def save_critique(self, run_id: str, critique: dict[str, Any]) -> Path:
        """Save critique feedback.

        Args:
            run_id: Run ID.
            critique: Critique data.

        Returns:
            Path to saved file.
        """
        run_dir = self.get_run_dir(run_id)
        file_path = run_dir / "critique.md"

        # Format critique as markdown
        content = ["# Critique Report\n"]
        content.append(f"**Score**: {critique.get('overall_score', 0)}/100\n")
        content.append(f"**Approved**: {'Yes' if critique.get('approved') else 'No'}\n")
        content.append(f"**Revision Needed**: {'Yes' if critique.get('revision_needed') else 'No'}\n")

        if critique.get("summary"):
            content.append(f"\n## Summary\n{critique.get('summary')}\n")

        issues = critique.get("issues", [])
        if issues:
            content.append("\n## Issues\n")
            for issue in issues:
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    issue.get("severity", "medium"), "⚪"
                )
                content.append(f"### {severity_emoji} {issue.get('location', 'Unknown')}\n")
                content.append(f"- **Type**: {issue.get('type', 'Unknown')}\n")
                content.append(f"- **Description**: {issue.get('description', '')}\n")
                content.append(f"- **Suggestion**: {issue.get('suggestion', '')}\n")

        verified = critique.get("verified_claims", [])
        if verified:
            content.append("\n## Verified Claims\n")
            for claim in verified:
                content.append(f"- ✅ {claim}\n")

        unverified = critique.get("unverified_claims", [])
        if unverified:
            content.append("\n## Unverified Claims\n")
            for claim in unverified:
                content.append(f"- ⚠️ {claim}\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("".join(content))

        # Also save JSON
        json_path = run_dir / "critique.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(critique, f, ensure_ascii=False, indent=2)

        logger.debug(f"Saved critique to {file_path}")
        return file_path

    def save_final(self, run_id: str, final_draft: str) -> Path:
        """Save final approved proposal.

        Args:
            run_id: Run ID.
            final_draft: Final content.

        Returns:
            Path to saved file.
        """
        run_dir = self.get_run_dir(run_id)
        file_path = run_dir / "final.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- Final Version -->\n")
            f.write(f"<!-- Approved: {datetime.utcnow().isoformat()} -->\n\n")
            f.write(final_draft)

        logger.info(f"Saved final proposal to {file_path}")
        return file_path

    def save_state(self, state: WorkflowState) -> None:
        """Save complete workflow state and outputs.

        Args:
            state: Workflow state to save.
        """
        run_id = state.get("run_id", "unknown")
        run_dir = self.get_run_dir(run_id)

        # Save plan
        if state.get("plan"):
            self.save_plan(run_id, state["plan"])

        # Save research findings
        if state.get("research_findings"):
            self.save_retrieved(run_id, state["research_findings"])

        # Save draft
        if state.get("draft"):
            self.save_draft(run_id, state["draft"], state.get("draft_version", 1))

        # Save critique
        if state.get("critique"):
            self.save_critique(run_id, state["critique"])

        # Save final
        if state.get("final_draft") and state.get("approved"):
            self.save_final(run_id, state["final_draft"])

        # Save complete state
        state_path = run_dir / "state.json"
        with open(state_path, "w", encoding="utf-8") as f:
            # Convert state to serializable dict
            state_dict = dict(state)
            json.dump(state_dict, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Saved complete state for run {run_id}")

    def load_state(self, run_id: str) -> dict[str, Any] | None:
        """Load workflow state for a run.

        Args:
            run_id: Run ID.

        Returns:
            State dict or None if not found.
        """
        state_path = self.runs_dir / run_id / "state.json"
        if not state_path.exists():
            return None

        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs.

        Returns:
            List of run summaries.
        """
        runs = []

        for run_dir in self.runs_dir.iterdir():
            if run_dir.is_dir() and not run_dir.name.startswith("."):
                state = self.load_state(run_dir.name)
                runs.append({
                    "run_id": run_dir.name,
                    "created_at": state.get("created_at") if state else None,
                    "status": state.get("status") if state else "unknown",
                    "approved": state.get("approved", False) if state else False,
                    "has_final": (run_dir / "final.md").exists(),
                })

        # Sort by creation time
        runs.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        return runs

    def get_run_files(self, run_id: str) -> dict[str, Path | None]:
        """Get all files for a run.

        Args:
            run_id: Run ID.

        Returns:
            Dictionary of file types to paths.
        """
        run_dir = self.runs_dir / run_id

        files = {
            "plan": run_dir / "plan.json" if (run_dir / "plan.json").exists() else None,
            "retrieved": run_dir / "retrieved.json" if (run_dir / "retrieved.json").exists() else None,
            "draft": run_dir / "draft.md" if (run_dir / "draft.md").exists() else None,
            "critique": run_dir / "critique.md" if (run_dir / "critique.md").exists() else None,
            "final": run_dir / "final.md" if (run_dir / "final.md").exists() else None,
            "trace": run_dir / "trace.jsonl" if (run_dir / "trace.jsonl").exists() else None,
            "state": run_dir / "state.json" if (run_dir / "state.json").exists() else None,
        }

        return files

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and all its files.

        Args:
            run_id: Run ID.

        Returns:
            True if deleted.
        """
        import shutil

        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            return False

        shutil.rmtree(run_dir)
        logger.info(f"Deleted run {run_id}")
        return True


# Singleton instance
_run_manager: RunManager | None = None


def get_run_manager() -> RunManager:
    """Get or create the run manager instance."""
    global _run_manager
    if _run_manager is None:
        _run_manager = RunManager()
    return _run_manager


def reset_run_manager() -> None:
    """Reset the run manager singleton."""
    global _run_manager
    _run_manager = None
