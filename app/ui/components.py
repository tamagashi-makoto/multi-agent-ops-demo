"""UI components for Streamlit app."""

import streamlit as st
from typing import Any
import json


def render_status_badge(status: str) -> str:
    """Render status as a colored badge.

    Args:
        status: Status string.

    Returns:
        HTML for status badge.
    """
    colors = {
        "pending": "#6c757d",
        "planning": "#17a2b8",
        "researching": "#007bff",
        "writing": "#28a745",
        "critiquing": "#ffc107",
        "revising": "#fd7e14",
        "awaiting_approval": "#e83e8c",
        "approved": "#20c997",
        "completed": "#28a745",
        "failed": "#dc3545",
    }
    color = colors.get(status, "#6c757d")
    return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">{status.upper()}</span>'


def render_score_gauge(score: int, label: str = "Score") -> None:
    """Render a score gauge.

    Args:
        score: Score value (0-100).
        label: Label for the gauge.
    """
    color = "#28a745" if score >= 70 else "#ffc107" if score >= 40 else "#dc3545"
    st.markdown(
        f"""
        <div style="text-align: center;">
            <div style="font-size: 2em; font-weight: bold; color: {color};">{score}</div>
            <div style="font-size: 0.8em; color: #6c757d;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trace_timeline(trace: list[dict[str, Any]]) -> None:
    """Render trace as a timeline.

    Args:
        trace: List of trace entries.
    """
    for entry in trace:
        icon = "✅" if entry.get("success", True) else "❌"
        agent = entry.get("agent", "unknown")
        action = entry.get("action", "unknown")
        step = entry.get("step", 0)

        with st.expander(f"{icon} Step {step}: {agent}.{action}"):
            col1, col2 = st.columns(2)
            with col1:
                st.caption("Timestamp")
                st.text(entry.get("timestamp", ""))
            with col2:
                st.caption("Success")
                st.text("Yes" if entry.get("success", True) else "No")

            if entry.get("error"):
                st.error(entry["error"])


def render_requirements_list(requirements: list[str]) -> None:
    """Render requirements as a checklist.

    Args:
        requirements: List of requirements.
    """
    for req in requirements:
        st.markdown(f"- [ ] {req}")


def render_findings_cards(findings: list[dict[str, Any]]) -> None:
    """Render research findings as cards.

    Args:
        findings: List of finding dictionaries.
    """
    for finding in findings:
        with st.container():
            st.markdown(f"### {finding.get('topic', 'Topic')}")
            st.caption(f"Source: {finding.get('source', 'Unknown')} | Score: {finding.get('relevance_score', 0):.2f}")
            st.markdown(finding.get("content", "")[:500] + "...")
            st.divider()


def render_critique_report(critique: dict[str, Any]) -> None:
    """Render critique report.

    Args:
        critique: Critique dictionary.
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        render_score_gauge(critique.get("overall_score", 0), "Overall Score")

    with col2:
        approved = critique.get("approved", False)
        st.markdown(
            f"""
            <div style="text-align: center;">
                <div style="font-size: 2em;">{"✅" if approved else "❌"}</div>
                <div style="font-size: 0.8em; color: #6c757d;">Approved</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        revision_needed = critique.get("revision_needed", False)
        st.markdown(
            f"""
            <div style="text-align: center;">
                <div style="font-size: 2em;">{"🔄" if revision_needed else "✨"}</div>
                <div style="font-size: 0.8em; color: #6c757d;">Revision Needed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Summary
    if critique.get("summary"):
        st.markdown("### Summary")
        st.info(critique["summary"])

    # Issues
    issues = critique.get("issues", [])
    if issues:
        st.markdown("### Issues")
        for issue in issues:
            severity = issue.get("severity", "medium")
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
            with st.expander(f"{severity_emoji} {issue.get('location', 'Unknown')} ({issue.get('type', '')})"):
                st.markdown(f"**Description**: {issue.get('description', '')}")
                st.markdown(f"**Suggestion**: {issue.get('suggestion', '')}")


def render_json_viewer(data: Any, title: str = "Data") -> None:
    """Render JSON data in an expandable viewer.

    Args:
        data: Data to display.
        title: Title for the section.
    """
    with st.expander(f"📄 {title} (JSON)"):
        st.json(data)


def render_markdown_preview(content: str, title: str = "Preview") -> None:
    """Render markdown content with preview.

    Args:
        content: Markdown content.
        title: Title for the section.
    """
    tab1, tab2 = st.tabs(["Preview", "Source"])

    with tab1:
        st.markdown(content)

    with tab2:
        st.code(content, language="markdown")


def render_run_card(run: dict[str, Any]) -> None:
    """Render a run summary card.

    Args:
        run: Run summary dictionary.
    """
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

    with col1:
        st.markdown(f"**{run.get('run_id', 'unknown')}**")

    with col2:
        st.markdown(
            render_status_badge(run.get("status", "unknown")),
            unsafe_allow_html=True,
        )

    with col3:
        created = run.get("created_at", "")
        if created:
            st.caption(created[:19])

    with col4:
        if run.get("has_final"):
            st.markdown("📄")
        if run.get("approved"):
            st.markdown("✅")
