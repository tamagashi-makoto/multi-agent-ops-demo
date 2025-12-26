"""Critique tool for draft evaluation."""

from typing import Any
import re

from app.common.logger import get_logger

logger = get_logger(__name__)


def critique_tool(
    draft: str,
    requirements: list[str],
    sources: list[str],
) -> dict[str, Any]:
    """Evaluate a draft for quality and accuracy.

    This tool performs basic quality checks on a draft document.
    For more sophisticated evaluation, use the CriticAgent.

    Args:
        draft: Draft content to evaluate.
        requirements: List of requirements to check against.
        sources: List of available source names.

    Returns:
        Dictionary with critique results.
    """
    logger.info("Critique tool called")

    issues = []
    metrics = {}

    # Check draft length
    word_count = len(draft)
    metrics["word_count"] = word_count
    if word_count < 500:
        issues.append({
            "type": "completeness",
            "severity": "medium",
            "description": "Draft is too short (less than 500 characters)",
        })

    # Check for citations
    citation_pattern = r"\[Source:\s*([^\]]+)\]"
    citations = re.findall(citation_pattern, draft)
    metrics["citation_count"] = len(citations)

    if not citations:
        issues.append({
            "type": "accuracy",
            "severity": "high",
            "description": "No citations found. Claims must be supported by evidence.",
        })

    # Verify citations against sources
    verified_citations = []
    unverified_citations = []
    for citation in citations:
        citation_clean = citation.strip()
        if any(
            src.lower() in citation_clean.lower()
            or citation_clean.lower() in src.lower()
            for src in sources
        ):
            verified_citations.append(citation_clean)
        else:
            unverified_citations.append(citation_clean)
            issues.append({
                "type": "accuracy",
                "severity": "high",
                "description": f"Unknown source: {citation_clean}",
            })

    metrics["verified_citations"] = len(verified_citations)
    metrics["unverified_citations"] = len(unverified_citations)

    # Check for required sections (basic structure check)
    required_sections = ["Overview", "Proposal", "Case Studies", "Next Steps"]
    found_sections = []
    missing_sections = []

    for section in required_sections:
        if section in draft:
            found_sections.append(section)
        else:
            missing_sections.append(section)

    metrics["found_sections"] = len(found_sections)
    if missing_sections:
        issues.append({
            "type": "completeness",
            "severity": "low",
            "description": f"Missing recommended sections: {', '.join(missing_sections)}",
        })

    # Check for requirement coverage
    covered_requirements = []
    uncovered_requirements = []

    for req in requirements:
        # Simple keyword matching
        req_keywords = req.lower().split()
        if any(kw in draft.lower() for kw in req_keywords if len(kw) > 2):
            covered_requirements.append(req)
        else:
            uncovered_requirements.append(req)

    metrics["requirement_coverage"] = (
        len(covered_requirements) / len(requirements) * 100
        if requirements
        else 100
    )

    if uncovered_requirements:
        issues.append({
            "type": "completeness",
            "severity": "medium",
            "description": f"Uncovered requirements: {', '.join(uncovered_requirements)}",
        })

    # Calculate overall score
    score = 100
    for issue in issues:
        if issue["severity"] == "high":
            score -= 20
        elif issue["severity"] == "medium":
            score -= 10
        else:
            score -= 5

    score = max(0, score)
    metrics["overall_score"] = score

    # Determine if revision is needed
    high_severity_count = sum(1 for i in issues if i["severity"] == "high")
    revision_needed = high_severity_count > 0 or score < 70

    logger.info(f"Critique complete: score={score}, issues={len(issues)}")

    return {
        "score": score,
        "issues": issues,
        "metrics": metrics,
        "verified_citations": verified_citations,
        "unverified_citations": unverified_citations,
        "revision_needed": revision_needed,
        "approved": score >= 70 and high_severity_count == 0,
    }
