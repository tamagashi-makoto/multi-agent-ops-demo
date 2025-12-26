"""Tracer for recording agent actions and events."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.common.config import get_settings
from app.common.logger import get_logger, PIIMasker

logger = get_logger(__name__)


class TraceEntry:
    """A single trace entry."""

    def __init__(
        self,
        run_id: str,
        agent: str,
        action: str,
        input_data: Any,
        output_data: Any,
        success: bool = True,
        error: str | None = None,
        step: int = 0,
        duration_ms: float | None = None,
    ):
        """Initialize trace entry.

        Args:
            run_id: Run ID.
            agent: Agent name.
            action: Action performed.
            input_data: Input data.
            output_data: Output data.
            success: Whether action succeeded.
            error: Error message if failed.
            step: Step number.
            duration_ms: Duration in milliseconds.
        """
        self.run_id = run_id
        self.timestamp = datetime.utcnow().isoformat()
        self.agent = agent
        self.action = action
        self.input_data = input_data
        self.output_data = output_data
        self.success = success
        self.error = error
        self.step = step
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "action": self.action,
            "input": self.input_data,
            "output": self.output_data,
            "success": self.success,
            "error": self.error,
            "step": self.step,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class Tracer:
    """Tracer for recording and persisting trace data."""

    def __init__(
        self,
        runs_dir: Path | None = None,
        mask_pii: bool = True,
    ):
        """Initialize tracer.

        Args:
            runs_dir: Directory for run outputs.
            mask_pii: Whether to mask PII in traces.
        """
        settings = get_settings()
        self.runs_dir = runs_dir or settings.runs_path
        self.mask_pii = mask_pii
        self.enabled = settings.trace_enabled

        if self.mask_pii:
            self.pii_masker = PIIMasker()
        else:
            self.pii_masker = None

        # In-memory buffer per run
        self._buffers: dict[str, list[TraceEntry]] = {}

        logger.info(
            f"Initialized Tracer (enabled={self.enabled}, mask_pii={mask_pii})"
        )

    def trace(
        self,
        run_id: str,
        agent: str,
        action: str,
        input_data: Any,
        output_data: Any,
        success: bool = True,
        error: str | None = None,
        step: int = 0,
        duration_ms: float | None = None,
    ) -> TraceEntry:
        """Record a trace entry.

        Args:
            run_id: Run ID.
            agent: Agent name.
            action: Action performed.
            input_data: Input data.
            output_data: Output data.
            success: Whether action succeeded.
            error: Error message if failed.
            step: Step number.
            duration_ms: Duration in milliseconds.

        Returns:
            Created trace entry.
        """
        if not self.enabled:
            return TraceEntry(run_id, agent, action, input_data, output_data, success, error, step, duration_ms)

        # Mask PII if enabled
        if self.pii_masker:
            if isinstance(input_data, dict):
                input_data = self.pii_masker.mask_dict(input_data)
            elif isinstance(input_data, str):
                input_data = self.pii_masker.mask(input_data)

            if isinstance(output_data, dict):
                output_data = self.pii_masker.mask_dict(output_data)
            elif isinstance(output_data, str):
                output_data = self.pii_masker.mask(output_data)

            if error:
                error = self.pii_masker.mask(error)

        entry = TraceEntry(
            run_id=run_id,
            agent=agent,
            action=action,
            input_data=input_data,
            output_data=output_data,
            success=success,
            error=error,
            step=step,
            duration_ms=duration_ms,
        )

        # Add to buffer
        if run_id not in self._buffers:
            self._buffers[run_id] = []
        self._buffers[run_id].append(entry)

        # Write to file
        self._write_entry(entry)

        logger.debug(f"Traced: {agent}.{action} (run={run_id}, step={step})")

        return entry

    def _write_entry(self, entry: TraceEntry) -> None:
        """Write a trace entry to the trace file.

        Args:
            entry: Trace entry to write.
        """
        run_dir = self.runs_dir / entry.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        trace_file = run_dir / "trace.jsonl"
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

    def get_trace(self, run_id: str) -> list[TraceEntry]:
        """Get all trace entries for a run.

        Args:
            run_id: Run ID.

        Returns:
            List of trace entries.
        """
        # Check buffer first
        if run_id in self._buffers:
            return self._buffers[run_id].copy()

        # Read from file
        trace_file = self.runs_dir / run_id / "trace.jsonl"
        if not trace_file.exists():
            return []

        entries = []
        with open(trace_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(
                        TraceEntry(
                            run_id=data["run_id"],
                            agent=data["agent"],
                            action=data["action"],
                            input_data=data["input"],
                            output_data=data["output"],
                            success=data.get("success", True),
                            error=data.get("error"),
                            step=data.get("step", 0),
                            duration_ms=data.get("duration_ms"),
                        )
                    )

        return entries

    def flush(self, run_id: str | None = None) -> None:
        """Flush buffer to disk.

        Args:
            run_id: Specific run to flush, or None for all.
        """
        if run_id:
            self._buffers.pop(run_id, None)
        else:
            self._buffers.clear()

    def clear_run(self, run_id: str) -> None:
        """Clear all trace data for a run.

        Args:
            run_id: Run ID to clear.
        """
        self._buffers.pop(run_id, None)

        trace_file = self.runs_dir / run_id / "trace.jsonl"
        if trace_file.exists():
            trace_file.unlink()


# Singleton instance
_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Get or create the tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def reset_tracer() -> None:
    """Reset the tracer singleton."""
    global _tracer
    _tracer = None
