"""Intent name extraction helpers for OVOS bus messages."""

from __future__ import annotations

from typing import Any


def resolve_intent_name(message: Any) -> str:
    """Extract normalized KPI intent name from message payload.

    Args:
        message: OVOS bus message object.

    Returns:
        Normalized intent name without ``.intent`` suffix, or empty string.
    """
    data = getattr(message, "data", {}) or {}

    candidates: list[Any] = [
        data.get("__intent__"),
        data.get("intent_name"),
        data.get("intent_type"),
        data.get("intent"),
        getattr(message, "msg_type", None),
    ]

    for candidate in candidates:
        name = _normalize_intent_candidate(candidate)
        if name:
            return name

    return ""


def _normalize_intent_candidate(candidate: Any) -> str:
    """Normalize intent value from dict/string payloads."""
    if not candidate:
        return ""

    if isinstance(candidate, dict):
        for key in ("intent_name", "name", "intent_type"):
            value = _normalize_intent_candidate(candidate.get(key))
            if value:
                return value
        return ""

    if not isinstance(candidate, str):
        return ""

    value = candidate.strip()
    if not value:
        return ""

    if ":" in value:
        value = value.split(":", 1)[1]

    if value.endswith(".intent"):
        value = value[:-7]

    if not value.startswith("kpi."):
        return ""

    return value
