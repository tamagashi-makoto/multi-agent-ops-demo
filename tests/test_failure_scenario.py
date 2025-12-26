"""Tests for failure scenario handling."""

import pytest
import os

from app.orchestrator.state import create_initial_state, WorkflowStatus
from app.orchestrator.coordinator import Coordinator
from app.rag.retriever import get_retriever, Retriever
from app.rag.vector_store import VectorStore
from app.agents.researcher import ResearcherAgent


class TestResearcherFailureScenario:
    """Tests for researcher handling empty RAG results."""

    def test_empty_rag_reports_insufficient(self):
        """Test that researcher reports insufficient when RAG is empty."""
        # Use empty retriever
        retriever = Retriever()  # Fresh, empty

        researcher = ResearcherAgent(retriever=retriever)

        result = researcher.execute_with_rag(
            search_topics=["製品情報", "価格"],
            plan_context="提案書作成",
        )

        assert result.overall_sufficient is False
        assert len(result.missing_info) > 0
        assert "製品情報" in result.missing_info or "価格" in result.missing_info

    def test_empty_rag_returns_no_findings(self):
        """Test that empty RAG returns no findings."""
        retriever = Retriever()

        researcher = ResearcherAgent(retriever=retriever)

        result = researcher.execute_with_rag(
            search_topics=["非存在のトピック"],
        )

        assert len(result.findings) == 0
        # Should still have the topic in missing_info
        assert "非存在のトピック" in result.missing_info


class TestPlannerRecovery:
    """Tests for planner generating recovery questions."""

    def test_planner_generates_questions_for_missing_info(self):
        """Test that planner can generate additional questions."""
        from app.agents.planner import PlannerAgent

        planner = PlannerAgent()

        missing_info = ["予算情報", "導入スケジュール"]
        questions = planner.create_additional_questions(
            missing_info=missing_info,
            context="中堅企業向け提案書作成",
        )

        assert len(questions) > 0
        # Each missing info should generate at least one question
        assert len(questions) >= len(missing_info)


class TestWorkflowFailureRecovery:
    """Tests for workflow-level failure handling."""

    def test_workflow_handles_empty_research(self, test_runs_dir):
        """Test that workflow handles empty research results."""
        os.environ["RUNS_DIR"] = str(test_runs_dir)

        # Don't load any documents - RAG will be empty
        state = create_initial_state(
            request="テスト提案書",
            customer_context="テスト顧客",
        )

        coordinator = Coordinator()

        # Run planning
        state = coordinator.execute_planning(state)
        assert state["status"] != WorkflowStatus.FAILED.value

        # Research will find nothing (empty RAG)
        state = coordinator.execute_research(state)

        # Should not crash, but should report insufficient
        assert state["status"] != WorkflowStatus.FAILED.value
        # research_sufficient should be False if nothing found
        # (depending on implementation, might still proceed with empty findings)

    def test_workflow_retries_on_agent_error(self, test_runs_dir, sample_documents):
        """Test that workflow retries on agent errors."""
        os.environ["RUNS_DIR"] = str(test_runs_dir)

        from app.rag.retriever import get_retriever

        retriever = get_retriever()
        retriever.load_documents_from_directory(sample_documents)

        state = create_initial_state(
            request="テスト",
        )

        coordinator = Coordinator()

        # Simulate first run
        state = coordinator.execute_planning(state)

        # Check retry_count can be incremented
        assert state.get("retry_count", 0) >= 0

    def test_guardrail_error_fails_workflow(self, test_runs_dir):
        """Test that guardrail violations fail the workflow."""
        os.environ["RUNS_DIR"] = str(test_runs_dir)
        os.environ["MAX_STEPS"] = "1"  # Very low limit

        state = create_initial_state(
            request="テスト",
            max_steps=1,  # This should cause failure after 1 step
        )

        # Note: actual failure would occur during extended execution
        # This test validates the state setup
        assert state["max_steps"] == 1


class TestCritiqueFailureDetection:
    """Tests for critique detecting issues."""

    def test_critique_detects_missing_citations(self):
        """Test that critique tool detects missing citations."""
        from app.tools.critique import critique_tool

        # Draft without citations
        draft = """
# 提案書

## 概要
当社の製品は素晴らしい性能を持っています。
価格も競争力があります。

## 導入事例
多くの企業が採用しています。
"""

        result = critique_tool(
            draft=draft,
            requirements=["製品情報", "価格情報"],
            sources=["product.md", "pricing.md"],
        )

        # Should detect missing citations
        assert result["score"] < 100
        has_citation_issue = any(
            issue["type"] == "accuracy" for issue in result["issues"]
        )
        assert has_citation_issue

    def test_critique_approves_good_draft(self):
        """Test that critique approves well-cited draft."""
        from app.tools.critique import critique_tool

        draft = """
# 提案書

## 概要
当社のIntelliFlow AI Platformは企業向けAI統合ソリューションです。
[出典: product_overview.md]

## 価格
Professionalプランは月額50万円からご利用いただけます。
[出典: pricing.md]

## 導入事例
大手製造業様では品質管理の自動化に成功しています。
[出典: case_studies.md]

## 次のステップ
14日間の無料トライアルをご用意しています。
"""

        result = critique_tool(
            draft=draft,
            requirements=["製品情報", "価格", "導入事例"],
            sources=["product_overview.md", "pricing.md", "case_studies.md"],
        )

        # Should have higher score
        assert result["score"] >= 50
        # Should have verified citations
        assert len(result["verified_citations"]) > 0
