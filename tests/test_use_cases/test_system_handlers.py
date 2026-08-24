"""Tests for platform-agnostic system-status observations."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

from skill._system_handlers import _status_freshness_clause
from skill.domain.models import Asset, CanonicalMetric


def test_status_freshness_skips_unreadable_assets() -> None:
    """Freshness probes later assets when the first asset has no KPI data."""
    skill = Mock()
    observed = datetime(2026, 8, 21, 19, 30, tzinfo=timezone.utc)
    skill.dispatcher.get_kpi.side_effect = [
        RuntimeError("asset is not linked to this metric"),
        Mock(source_observed_at=observed, coverage_status="complete"),
    ]
    assets = [
        Asset(asset_id="unbound-meter", display_name="Meter", asset_type="sensor"),
        Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
    ]

    result = _status_freshness_clause(
        skill,
        assets,
        [CanonicalMetric.ENERGY_PER_UNIT],
    )

    assert observed.isoformat() in result
    assert "complete" in result
    assert skill.dispatcher.get_kpi.call_count == 2
