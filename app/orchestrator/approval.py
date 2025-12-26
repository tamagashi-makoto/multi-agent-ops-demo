"""Human approval gate for workflow control."""

from enum import Enum
from datetime import datetime
from typing import Any
import threading

from app.common.config import get_settings
from app.common.logger import get_logger

logger = get_logger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalRequest:
    """A request for human approval."""

    def __init__(
        self,
        run_id: str,
        content: str,
        context: dict[str, Any],
    ):
        """Initialize approval request.

        Args:
            run_id: Run ID.
            content: Content requiring approval.
            context: Additional context.
        """
        self.run_id = run_id
        self.content = content
        self.context = context
        self.status = ApprovalStatus.PENDING
        self.created_at = datetime.utcnow().isoformat()
        self.resolved_at: str | None = None
        self.resolver: str | None = None
        self.comments: str | None = None


class ApprovalGate:
    """Gate for managing human approvals.

    This class manages the approval workflow, allowing runs to pause
    and wait for human approval before proceeding.
    """

    def __init__(self):
        """Initialize approval gate."""
        self.settings = get_settings()
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()
        logger.info(
            f"Initialized ApprovalGate (auto_approve={self.settings.auto_approve})"
        )

    @property
    def auto_approve(self) -> bool:
        """Check if auto-approval is enabled."""
        return self.settings.auto_approve

    def request_approval(
        self,
        run_id: str,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Request approval for content.

        Args:
            run_id: Run ID.
            content: Content requiring approval.
            context: Additional context.

        Returns:
            ApprovalRequest object.
        """
        if self.auto_approve:
            logger.info(f"Auto-approving run {run_id}")
            request = ApprovalRequest(run_id, content, context or {})
            request.status = ApprovalStatus.APPROVED
            request.resolved_at = datetime.utcnow().isoformat()
            request.resolver = "auto"
            return request

        with self._lock:
            request = ApprovalRequest(run_id, content, context or {})
            self._pending_approvals[run_id] = request
            logger.info(f"Approval requested for run {run_id}")

        return request

    def approve(
        self,
        run_id: str,
        resolver: str = "human",
        comments: str | None = None,
    ) -> bool:
        """Approve a pending request.

        Args:
            run_id: Run ID to approve.
            resolver: Who approved.
            comments: Optional comments.

        Returns:
            True if approved, False if not found.
        """
        with self._lock:
            request = self._pending_approvals.get(run_id)
            if request is None:
                logger.warning(f"No pending approval for run {run_id}")
                return False

            request.status = ApprovalStatus.APPROVED
            request.resolved_at = datetime.utcnow().isoformat()
            request.resolver = resolver
            request.comments = comments

            logger.info(f"Run {run_id} approved by {resolver}")
            return True

    def reject(
        self,
        run_id: str,
        resolver: str = "human",
        comments: str | None = None,
    ) -> bool:
        """Reject a pending request.

        Args:
            run_id: Run ID to reject.
            resolver: Who rejected.
            comments: Optional comments.

        Returns:
            True if rejected, False if not found.
        """
        with self._lock:
            request = self._pending_approvals.get(run_id)
            if request is None:
                logger.warning(f"No pending approval for run {run_id}")
                return False

            request.status = ApprovalStatus.REJECTED
            request.resolved_at = datetime.utcnow().isoformat()
            request.resolver = resolver
            request.comments = comments

            logger.info(f"Run {run_id} rejected by {resolver}")
            return True

    def get_status(self, run_id: str) -> ApprovalStatus | None:
        """Get approval status for a run.

        Args:
            run_id: Run ID.

        Returns:
            Approval status or None if not found.
        """
        with self._lock:
            request = self._pending_approvals.get(run_id)
            return request.status if request else None

    def get_request(self, run_id: str) -> ApprovalRequest | None:
        """Get approval request for a run.

        Args:
            run_id: Run ID.

        Returns:
            ApprovalRequest or None if not found.
        """
        with self._lock:
            return self._pending_approvals.get(run_id)

    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests.

        Returns:
            List of pending requests.
        """
        with self._lock:
            return [
                req
                for req in self._pending_approvals.values()
                if req.status == ApprovalStatus.PENDING
            ]

    def clear(self, run_id: str | None = None) -> None:
        """Clear approval requests.

        Args:
            run_id: Specific run to clear, or None to clear all.
        """
        with self._lock:
            if run_id:
                self._pending_approvals.pop(run_id, None)
            else:
                self._pending_approvals.clear()

    def is_approved(self, run_id: str) -> bool:
        """Check if a run is approved.

        Args:
            run_id: Run ID.

        Returns:
            True if approved.
        """
        status = self.get_status(run_id)
        return status == ApprovalStatus.APPROVED

    def is_pending(self, run_id: str) -> bool:
        """Check if a run is pending approval.

        Args:
            run_id: Run ID.

        Returns:
            True if pending.
        """
        status = self.get_status(run_id)
        return status == ApprovalStatus.PENDING


# Global approval gate instance
_approval_gate: ApprovalGate | None = None


def get_approval_gate() -> ApprovalGate:
    """Get or create the approval gate instance."""
    global _approval_gate
    if _approval_gate is None:
        _approval_gate = ApprovalGate()
    return _approval_gate


def reset_approval_gate() -> None:
    """Reset the approval gate singleton."""
    global _approval_gate
    _approval_gate = None
