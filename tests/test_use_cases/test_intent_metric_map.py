"""Tests for INTENT_METRIC_MAP completeness and consistency."""

from __future__ import annotations

from pathlib import Path

from skill import INTENT_METRIC_MAP
from skill.domain.models import CanonicalMetric


def test_intent_metric_map_has_19_entries():
    """KPI map must include exactly one entry per KPI intent file."""
    assert len(INTENT_METRIC_MAP) == 19


def test_all_canonical_kpi_metrics_have_intent_mapping():
    """Each canonical metric must be reachable from one intent mapping."""
    mapped_metrics = set(INTENT_METRIC_MAP.values())
    assert mapped_metrics == set(CanonicalMetric)


def test_all_intent_files_exist_for_mapped_intents():
    """Every map key must correspond to an on-disk .intent file."""
    locale_dir = Path(__file__).resolve().parents[2] / "skill" / "locale" / "en-us"
    missing = [
        intent_name
        for intent_name in INTENT_METRIC_MAP
        if not (locale_dir / f"{intent_name}.intent").exists()
    ]
    assert missing == []


def test_no_duplicate_metrics_in_map():
    """No two intent names should point to the same canonical metric."""
    values = list(INTENT_METRIC_MAP.values())
    assert len(values) == len(set(values))
