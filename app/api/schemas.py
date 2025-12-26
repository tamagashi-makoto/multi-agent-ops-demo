"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class RunRequest(BaseModel):
    """Request to start a new run."""

    request: str = Field(..., description="User's request for the proposal")
    customer_context: str = Field(
        default="",
        description="Information about the customer",
    )
    run_id: str | None = Field(
        default=None,
        description="Optional custom run ID",
    )

    model_config = {"json_schema_extra": {"examples": [{"request": "Please create a proposal for AI implementation for a medium-sized manufacturing company", "customer_context": "500 employees, manufacturing, issues with quality control"}]}}


class ApprovalRequest(BaseModel):
    """Request to approve or reject a run."""

    approved: bool = Field(..., description="Whether to approve the run")
    comments: str | None = Field(
        default=None,
        description="Optional comments",
    )
    resolver: str = Field(
        default="human",
        description="Who is approving/rejecting",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class RunStatusResponse(BaseModel):
    """Response with run status."""

    run_id: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    current_step: int = 0
    approved: bool = False
    error: str | None = None


class RunDetailResponse(BaseModel):
    """Detailed response for a run."""

    run_id: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None

    # Input
    request: str = ""
    customer_context: str = ""

    # Outputs
    requirements: list[str] = []
    tasks: list[dict[str, Any]] = []
    research_findings: list[dict[str, Any]] = []
    draft: str = ""
    draft_version: int = 0
    citation_count: int = 0
    critique_score: int = 0
    revision_needed: bool = False
    final_draft: str = ""

    # Status
    approved: bool = False
    approval_timestamp: str = ""
    current_step: int = 0
    error: str | None = None


class RunListItem(BaseModel):
    """Item in runs list."""

    run_id: str
    created_at: str | None = None
    status: str
    approved: bool = False
    has_final: bool = False


class RunListResponse(BaseModel):
    """Response with list of runs."""

    runs: list[RunListItem]
    total: int


class ApprovalStatusResponse(BaseModel):
    """Response with approval status."""

    run_id: str
    status: str
    approved: bool


class TraceEntryResponse(BaseModel):
    """A single trace entry."""

    timestamp: str
    step: int
    agent: str
    action: str
    success: bool
    error: str | None = None
    duration_ms: float | None = None


class TraceResponse(BaseModel):
    """Response with trace entries."""

    run_id: str
    entries: list[TraceEntryResponse]
    total: int


class FilesResponse(BaseModel):
    """Response with run files."""

    run_id: str
    files: dict[str, str | None]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
