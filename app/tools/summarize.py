"""Summarize tool for content summarization."""

from typing import Any

from app.common.logger import get_logger
from app.agents.base import LLMClient

logger = get_logger(__name__)


def summarize_tool(
    content: str,
    max_length: int = 500,
    style: str = "concise",
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Summarize content using LLM.

    Args:
        content: Content to summarize.
        max_length: Maximum summary length.
        style: Summary style (concise, detailed, bullet_points).
        llm_client: Optional LLM client.

    Returns:
        Dictionary with summary.
    """
    logger.info(f"Summarize tool called with style={style}")

    client = llm_client or LLMClient()

    style_instructions = {
        "concise": "Summarize concisely in 1-2 sentences.",
        "detailed": "Create a detailed summary including main points.",
        "bullet_points": "Summarize main points in bullet points.",
    }

    instruction = style_instructions.get(style, style_instructions["concise"])

    prompt = f"""
Summarize the following content within {max_length} characters.
{instruction}

## Content
{content}

## Summary
"""

    summary = client.generate(
        "You are a document summarization assistant.",
        prompt,
    )

    # Truncate if too long
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."

    return {
        "original_length": len(content),
        "summary": summary,
        "summary_length": len(summary),
        "style": style,
        "compression_ratio": len(summary) / len(content) if content else 0,
    }


def extract_key_points_tool(
    content: str,
    max_points: int = 5,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Extract key points from content.

    Args:
        content: Content to extract from.
        max_points: Maximum number of points.
        llm_client: Optional LLM client.

    Returns:
        Dictionary with key points.
    """
    logger.info(f"Extract key points tool called, max_points={max_points}")

    client = llm_client or LLMClient()

    prompt = f"""
Extract up to {max_points} key points from the following content.
Each point should be a concise single sentence.

## Content
{content}

Output in JSON format:
{{"key_points": ["Point 1", "Point 2", ...]}}
"""

    raw_output = client.generate(
        "You are an assistant that extracts key points from documents.",
        prompt,
    )

    # Parse JSON
    try:
        import json

        if "{" in raw_output:
            start = raw_output.find("{")
            end = raw_output.rfind("}") + 1
            data = json.loads(raw_output[start:end])
            key_points = data.get("key_points", [])[:max_points]
        else:
            # Fallback: split by newlines
            key_points = [
                line.strip().lstrip("•-1234567890.)")
                for line in raw_output.split("\n")
                if line.strip()
            ][:max_points]
    except Exception:
        key_points = [raw_output[:200]]

    return {
        "key_points": key_points,
        "count": len(key_points),
        "original_length": len(content),
    }
