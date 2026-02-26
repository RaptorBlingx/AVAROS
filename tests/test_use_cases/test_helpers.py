"""Unit tests for extracted helper utilities in skill._helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skill._helpers import (
    canonicalize_asset_id,
    extract_intent_name,
    resolve_metric_from_utterance,
)
from skill.domain.models import CanonicalMetric


@dataclass
class DummyMessage:
    """Minimal message stub for helper tests."""

    data: dict[str, Any] = field(default_factory=dict)
    msg_type: str | None = None


def test_resolve_metric_from_utterance_matches_specific_metric() -> None:
    """Resolver should match direct metric phrases."""
    result = resolve_metric_from_utterance(None, "show energy per unit for line one")
    assert result is CanonicalMetric.ENERGY_PER_UNIT


def test_resolve_metric_from_utterance_handles_co2_total_variants() -> None:
    """Resolver should map CO2 total-like language to canonical metric."""
    result = resolve_metric_from_utterance(None, "what is total carbon emissions")
    assert result is CanonicalMetric.CO2_TOTAL


def test_canonicalize_asset_id_normalizes_line_synonyms() -> None:
    """Asset canonicalizer should normalize spoken line aliases."""
    assert canonicalize_asset_id(None, "line too") == "Line-2"
    assert canonicalize_asset_id(None, "Compressor-1") == "Compressor-1"


def test_extract_intent_name_reads_nested_intent_payload() -> None:
    """Intent extractor should normalize skill-prefixed payloads."""
    message = DummyMessage(data={"__intent__": {"intent_name": "skill:kpi.energy.total.intent"}})
    assert extract_intent_name(None, message) == "kpi.energy.total"


def test_extract_intent_name_ignores_non_kpi_intents() -> None:
    """Intent extractor should return empty string for non-kpi intents."""
    message = DummyMessage(data={"intent_name": "skill:help.intent"})
    assert extract_intent_name(None, message) == ""
