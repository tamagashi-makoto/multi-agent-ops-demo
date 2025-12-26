"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path
import pytest

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["LLM_MODE"] = "stub"
os.environ["EMBEDDING_MODE"] = "stub"
os.environ["AUTO_APPROVE"] = "false"
os.environ["TRACE_ENABLED"] = "true"
os.environ["RUNS_DIR"] = "test_runs"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton instances before each test."""
    from app.common.config import get_settings
    from app.common.guardrails import reset_guardrails
    from app.rag.embeddings import reset_embedding_service
    from app.rag.vector_store import reset_vector_store
    from app.rag.retriever import reset_retriever
    from app.tools.registry import reset_tool_registry
    from app.orchestrator.approval import reset_approval_gate
    from app.observability.tracer import reset_tracer
    from app.observability.run_manager import reset_run_manager

    # Reset before test
    reset_guardrails()
    reset_embedding_service()
    reset_vector_store()
    reset_retriever()
    reset_tool_registry()
    reset_approval_gate()
    reset_tracer()
    reset_run_manager()

    yield

    # Reset after test
    reset_guardrails()
    reset_embedding_service()
    reset_vector_store()
    reset_retriever()
    reset_tool_registry()
    reset_approval_gate()
    reset_tracer()
    reset_run_manager()


@pytest.fixture
def test_runs_dir(tmp_path):
    """Create temporary runs directory."""
    runs_dir = tmp_path / "test_runs"
    runs_dir.mkdir()
    os.environ["RUNS_DIR"] = str(runs_dir)
    return runs_dir


@pytest.fixture
def sample_documents(tmp_path):
    """Create sample documents for testing."""
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()

    # Create test documents
    (docs_dir / "test_doc1.md").write_text(
        "# テスト製品\n\nこれはテスト製品の説明です。価格は100万円です。",
        encoding="utf-8",
    )
    (docs_dir / "test_doc2.md").write_text(
        "# 導入事例\n\nA社では生産性が30%向上しました。",
        encoding="utf-8",
    )

    return docs_dir


@pytest.fixture
def llm_client():
    """Create LLM client in stub mode."""
    from app.agents.base import LLMClient

    return LLMClient()


@pytest.fixture
def guardrails():
    """Create guardrails instance."""
    from app.common.guardrails import Guardrails

    return Guardrails()


@pytest.fixture
def approval_gate():
    """Create approval gate instance."""
    from app.orchestrator.approval import ApprovalGate

    return ApprovalGate()
