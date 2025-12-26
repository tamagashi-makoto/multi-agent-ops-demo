"""Write draft tool for saving draft documents."""

from pathlib import Path
from datetime import datetime
from typing import Any

from app.common.config import get_settings
from app.common.guardrails import get_guardrails
from app.common.logger import get_logger

logger = get_logger(__name__)


def write_draft_tool(
    content: str,
    filename: str,
    run_id: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a draft document to the runs directory.

    This tool writes content to a file within the runs/<run_id>/ directory.
    Writing to any other location is blocked by guardrails.

    Args:
        content: Content to write.
        filename: Filename (without path).
        run_id: Run ID for directory organization.
        overwrite: Whether to overwrite existing file.

    Returns:
        Dictionary with write result.
    """
    settings = get_settings()
    guardrails = get_guardrails()

    # Construct the full path
    run_dir = settings.runs_path / run_id
    file_path = run_dir / filename

    # Validate the path is allowed
    guardrails.validate_write_path(file_path)

    logger.info(f"Writing draft to: {file_path}")

    # Create directory if it doesn't exist
    run_dir.mkdir(parents=True, exist_ok=True)

    # Check if file exists
    if file_path.exists() and not overwrite:
        logger.warning(f"File already exists: {file_path}")
        return {
            "success": False,
            "error": f"File already exists: {filename}. Set overwrite=True to replace.",
            "path": str(file_path),
        }

    # Write the content
    try:
        file_path.write_text(content, encoding="utf-8")
        file_size = file_path.stat().st_size

        logger.info(f"Successfully wrote {file_size} bytes to {file_path}")

        return {
            "success": True,
            "path": str(file_path),
            "filename": filename,
            "size_bytes": file_size,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": str(file_path),
        }


def append_to_draft_tool(
    content: str,
    filename: str,
    run_id: str,
) -> dict[str, Any]:
    """Append content to an existing draft file.

    Args:
        content: Content to append.
        filename: Filename (without path).
        run_id: Run ID for directory organization.

    Returns:
        Dictionary with append result.
    """
    settings = get_settings()
    guardrails = get_guardrails()

    # Construct the full path
    run_dir = settings.runs_path / run_id
    file_path = run_dir / filename

    # Validate the path is allowed
    guardrails.validate_write_path(file_path)

    logger.info(f"Appending to draft: {file_path}")

    # Create directory if it doesn't exist
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Append content
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

        file_size = file_path.stat().st_size

        return {
            "success": True,
            "path": str(file_path),
            "filename": filename,
            "size_bytes": file_size,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to append to file: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": str(file_path),
        }


def list_run_files_tool(run_id: str) -> dict[str, Any]:
    """List all files in a run directory.

    Args:
        run_id: Run ID.

    Returns:
        Dictionary with file list.
    """
    settings = get_settings()
    run_dir = settings.runs_path / run_id

    if not run_dir.exists():
        return {
            "success": False,
            "error": f"Run directory does not exist: {run_id}",
            "files": [],
        }

    files = []
    for file_path in run_dir.iterdir():
        if file_path.is_file():
            files.append({
                "name": file_path.name,
                "size_bytes": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            })

    return {
        "success": True,
        "run_id": run_id,
        "files": files,
        "total_files": len(files),
    }
