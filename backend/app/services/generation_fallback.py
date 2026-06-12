"""Shared labels for deterministic pipeline fallbacks when live AI inference is unavailable."""

from __future__ import annotations

DUMMY_GENERATION_NOTICE = (
    "DETERMINISTIC_FALLBACK: This output was not produced by a live AI inference. "
    "For development/testing only — not submission-ready."
)

NO_API_KEY_FALLBACK_REASON = "No Anthropic API key configured"


def apply_dummy_generation_labels(
    content: dict,
    *,
    fallback_reason: str,
) -> dict:
    """Mark artifact content as a deterministic dummy fallback (mutates and returns content)."""
    content["derivation_method"] = "deterministic_fallback"
    content["generation_mode"] = "DUMMY"
    content["generation_notice"] = DUMMY_GENERATION_NOTICE
    content["fallback_reason"] = fallback_reason
    return content


def format_fallback_reasoning(base_reasoning: str, fallback_reason: str | None) -> str:
    """Append fallback context to AI decision reasoning when deterministic path was used."""
    if not fallback_reason:
        return base_reasoning
    return f"{base_reasoning} DETERMINISTIC_FALLBACK: {fallback_reason}"
