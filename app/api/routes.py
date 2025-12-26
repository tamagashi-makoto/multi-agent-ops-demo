"""API routes for multi-agent workflow."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Any

from app.api.schemas import (
    RunRequest,
    RunStatusResponse,
    RunDetailResponse,
    RunListResponse,
    RunListItem,
    ApprovalRequest,
    ApprovalStatusResponse,
    TraceResponse,
    TraceEntryResponse,
    FilesResponse,
)
from app.common.logger import get_logger
from app.orchestrator.graph import run_workflow
from app.orchestrator.approval import get_approval_gate, ApprovalStatus
from app.orchestrator.state import WorkflowStatus
from app.observability.run_manager import get_run_manager
from app.observability.tracer import get_tracer

logger = get_logger(__name__)

router = APIRouter()


def run_workflow_task(request: str, customer_context: str, run_id: str | None) -> None:
    """Background task to run workflow."""
    try:
        state = run_workflow(
            request=request,
            customer_context=customer_context,
            run_id=run_id,
        )
        # Save state
        run_manager = get_run_manager()
        run_manager.save_state(state)
    except Exception as e:
        logger.exception(f"Workflow failed: {e}")


@router.post("/run", response_model=RunStatusResponse)
async def start_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
) -> RunStatusResponse:
    """Start a new workflow run.

    This starts the multi-agent workflow in the background.
    Use the /status/{run_id} endpoint to check progress.
    """
    import uuid

    run_id = request.run_id or str(uuid.uuid4())[:8]

    logger.info(f"Starting run {run_id}")

    # Start workflow in background
    background_tasks.add_task(
        run_workflow_task,
        request.request,
        request.customer_context,
        run_id,
    )

    return RunStatusResponse(
        run_id=run_id,
        status=WorkflowStatus.PENDING.value,
        current_step=0,
        approved=False,
    )


@router.get("/status/{run_id}", response_model=RunStatusResponse)
async def get_status(run_id: str) -> RunStatusResponse:
    """Get the status of a run."""
    run_manager = get_run_manager()
    state = run_manager.load_state(run_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return RunStatusResponse(
        run_id=run_id,
        status=state.get("status", "unknown"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
        current_step=state.get("current_step", 0),
        approved=state.get("approved", False),
        error=state.get("error"),
    )


@router.get("/run/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(run_id: str) -> RunDetailResponse:
    """Get detailed information about a run."""
    run_manager = get_run_manager()
    state = run_manager.load_state(run_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return RunDetailResponse(
        run_id=run_id,
        status=state.get("status", "unknown"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
        request=state.get("request", ""),
        customer_context=state.get("customer_context", ""),
        requirements=state.get("requirements", []),
        tasks=state.get("tasks", []),
        research_findings=state.get("research_findings", []),
        draft=state.get("draft", ""),
        draft_version=state.get("draft_version", 0),
        citation_count=state.get("citation_count", 0),
        critique_score=state.get("critique_score", 0),
        revision_needed=state.get("revision_needed", False),
        final_draft=state.get("final_draft", ""),
        approved=state.get("approved", False),
        approval_timestamp=state.get("approval_timestamp", ""),
        current_step=state.get("current_step", 0),
        error=state.get("error"),
    )


@router.get("/runs", response_model=RunListResponse)
async def list_runs() -> RunListResponse:
    """List all runs."""
    run_manager = get_run_manager()
    runs = run_manager.list_runs()

    return RunListResponse(
        runs=[
            RunListItem(
                run_id=r["run_id"],
                created_at=r.get("created_at"),
                status=r.get("status", "unknown"),
                approved=r.get("approved", False),
                has_final=r.get("has_final", False),
            )
            for r in runs
        ],
        total=len(runs),
    )


@router.post("/approve/{run_id}", response_model=ApprovalStatusResponse)
async def approve_run(run_id: str, request: ApprovalRequest) -> ApprovalStatusResponse:
    """Approve or reject a run."""
    approval_gate = get_approval_gate()
    run_manager = get_run_manager()

    # Check if run exists
    state = run_manager.load_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if request.approved:
        success = approval_gate.approve(run_id, request.resolver, request.comments)
        if success:
            # Update state
            state["approved"] = True
            state["status"] = WorkflowStatus.APPROVED.value
            state["final_draft"] = state.get("draft", "")
            run_manager.save_state(state)
    else:
        success = approval_gate.reject(run_id, request.resolver, request.comments)

    if not success:
        logger.warning(f"No pending approval for {run_id}, updating state directly")
        # Directly update state if no pending approval exists
        if request.approved:
            state["approved"] = True
            state["status"] = WorkflowStatus.APPROVED.value
            state["final_draft"] = state.get("draft", "")
            run_manager.save_state(state)

    return ApprovalStatusResponse(
        run_id=run_id,
        status=state.get("status", "unknown"),
        approved=request.approved,
    )


@router.get("/trace/{run_id}", response_model=TraceResponse)
async def get_trace(run_id: str) -> TraceResponse:
    """Get trace entries for a run."""
    tracer = get_tracer()
    entries = tracer.get_trace(run_id)

    if not entries:
        # Check if run exists
        run_manager = get_run_manager()
        if not run_manager.load_state(run_id):
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return TraceResponse(
        run_id=run_id,
        entries=[
            TraceEntryResponse(
                timestamp=e.timestamp,
                step=e.step,
                agent=e.agent,
                action=e.action,
                success=e.success,
                error=e.error,
                duration_ms=e.duration_ms,
            )
            for e in entries
        ],
        total=len(entries),
    )


@router.get("/files/{run_id}", response_model=FilesResponse)
async def get_run_files(run_id: str) -> FilesResponse:
    """Get file paths for a run."""
    run_manager = get_run_manager()

    # Check if run exists
    if not run_manager.load_state(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    files = run_manager.get_run_files(run_id)

    return FilesResponse(
        run_id=run_id,
        files={k: str(v) if v else None for k, v in files.items()},
    )


@router.get("/file/{run_id}/{filename}")
async def get_file_content(run_id: str, filename: str) -> dict[str, Any]:
    """Get content of a specific file."""
    run_manager = get_run_manager()
    run_dir = run_manager.runs_dir / run_id

    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    file_path = run_dir / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {filename} not found in run {run_id}",
        )

    # Security check
    if not file_path.resolve().is_relative_to(run_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")

    content = file_path.read_text(encoding="utf-8")

    return {
        "run_id": run_id,
        "filename": filename,
        "content": content,
        "size_bytes": len(content),
    }


@router.delete("/run/{run_id}")
async def delete_run(run_id: str) -> dict[str, Any]:
    """Delete a run and all its files."""
    run_manager = get_run_manager()

    if not run_manager.delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {"deleted": True, "run_id": run_id}
