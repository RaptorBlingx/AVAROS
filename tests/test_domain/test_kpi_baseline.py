"""
KPI Baseline Domain Model Tests

Covers all 3 frozen dataclasses:
    - KPIBaseline: field access, defaults, frozen enforcement
    - KPISnapshot: field access, frozen enforcement
    - KPIProgress: field access, computed fields, frozen enforcement
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from skill.domain.kpi_baseline import KPIBaseline, KPIProgress, KPISnapshot


# ══════════════════════════════════════════════════════════
# KPIBaseline
# ══════════════════════════════════════════════════════════


class TestKPIBaseline:
    """Tests for KPIBaseline frozen dataclass."""

    def test_fields_accessible(self) -> None:
        """All required fields are readable after creation."""
        bl = KPIBaseline(
            metric="energy_per_unit",
            site_id="artibilim",
            baseline_value=2.5,
            unit="kWh/unit",
            recorded_at=datetime(2026, 1, 15, 10, 0),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        assert bl.metric == "energy_per_unit"
        assert bl.site_id == "artibilim"
        assert bl.baseline_value == 2.5
        assert bl.unit == "kWh/unit"
        assert bl.period_start == date(2026, 1, 1)
        assert bl.period_end == date(2026, 1, 31)

    def test_default_notes_empty(self) -> None:
        """Notes defaults to empty string."""
        bl = KPIBaseline(
            metric="co2_per_unit",
            site_id="mext",
            baseline_value=0.8,
            unit="kg CO2/unit",
            recorded_at=datetime(2026, 2, 1),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        assert bl.notes == ""

    def test_notes_custom_value(self) -> None:
        """Custom notes value preserved."""
        bl = KPIBaseline(
            metric="material_efficiency",
            site_id="artibilim",
            baseline_value=85.0,
            unit="%",
            recorded_at=datetime(2026, 1, 15),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            notes="Initial baseline from January pilot",
        )
        assert bl.notes == "Initial baseline from January pilot"

    def test_frozen_prevents_mutation(self) -> None:
        """Attempting to modify a field raises FrozenInstanceError."""
        bl = KPIBaseline(
            metric="energy_per_unit",
            site_id="artibilim",
            baseline_value=2.5,
            unit="kWh/unit",
            recorded_at=datetime(2026, 1, 15),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        with pytest.raises(FrozenInstanceError):
            bl.baseline_value = 3.0  # type: ignore[misc]

    def test_zero_baseline_value(self) -> None:
        """Zero baseline value is valid."""
        bl = KPIBaseline(
            metric="co2_total",
            site_id="mext",
            baseline_value=0.0,
            unit="tonnes",
            recorded_at=datetime(2026, 1, 1),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        assert bl.baseline_value == 0.0

    def test_equality(self) -> None:
        """Two baselines with same values are equal."""
        kwargs = dict(
            metric="energy_per_unit",
            site_id="artibilim",
            baseline_value=2.5,
            unit="kWh/unit",
            recorded_at=datetime(2026, 1, 15),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        assert KPIBaseline(**kwargs) == KPIBaseline(**kwargs)


# ══════════════════════════════════════════════════════════
# KPISnapshot
# ══════════════════════════════════════════════════════════


class TestKPISnapshot:
    """Tests for KPISnapshot frozen dataclass."""

    def test_fields_accessible(self) -> None:
        """All fields are readable after creation."""
        snap = KPISnapshot(
            metric="energy_per_unit",
            site_id="artibilim",
            value=2.3,
            unit="kWh/unit",
            measured_at=datetime(2026, 6, 15, 14, 30),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )
        assert snap.metric == "energy_per_unit"
        assert snap.value == 2.3
        assert snap.measured_at == datetime(2026, 6, 15, 14, 30)

    def test_frozen_prevents_mutation(self) -> None:
        """Attempting to modify a field raises FrozenInstanceError."""
        snap = KPISnapshot(
            metric="co2_per_unit",
            site_id="mext",
            value=0.7,
            unit="kg CO2/unit",
            measured_at=datetime(2026, 6, 1),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )
        with pytest.raises(FrozenInstanceError):
            snap.value = 0.6  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two snapshots with same values are equal."""
        kwargs = dict(
            metric="material_efficiency",
            site_id="artibilim",
            value=88.5,
            unit="%",
            measured_at=datetime(2026, 6, 15),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )
        assert KPISnapshot(**kwargs) == KPISnapshot(**kwargs)


# ══════════════════════════════════════════════════════════
# KPIProgress
# ══════════════════════════════════════════════════════════


class TestKPIProgress:
    """Tests for KPIProgress frozen dataclass."""

    def test_fields_accessible(self) -> None:
        """All fields are readable."""
        prog = KPIProgress(
            metric="energy_per_unit",
            site_id="artibilim",
            baseline_value=2.5,
            current_value=2.2,
            target_percent=8.0,
            improvement_percent=12.0,
            target_met=True,
            unit="kWh/unit",
            baseline_date=datetime(2026, 1, 15),
            current_date=datetime(2026, 6, 15),
            direction="reduction",
        )
        assert prog.metric == "energy_per_unit"
        assert prog.improvement_percent == 12.0
        assert prog.target_met is True
        assert prog.direction == "reduction"

    def test_frozen_prevents_mutation(self) -> None:
        """Attempting to modify a field raises FrozenInstanceError."""
        prog = KPIProgress(
            metric="material_efficiency",
            site_id="artibilim",
            baseline_value=85.0,
            current_value=90.0,
            target_percent=5.0,
            improvement_percent=5.88,
            target_met=True,
            unit="%",
            baseline_date=datetime(2026, 1, 15),
            current_date=datetime(2026, 6, 15),
            direction="improvement",
        )
        with pytest.raises(FrozenInstanceError):
            prog.target_met = False  # type: ignore[misc]

    def test_target_not_met(self) -> None:
        """Progress with insufficient improvement."""
        prog = KPIProgress(
            metric="co2_per_unit",
            site_id="mext",
            baseline_value=1.0,
            current_value=0.95,
            target_percent=10.0,
            improvement_percent=5.0,
            target_met=False,
            unit="kg CO2/unit",
            baseline_date=datetime(2026, 1, 1),
            current_date=datetime(2026, 6, 1),
            direction="reduction",
        )
        assert prog.target_met is False
        assert prog.improvement_percent == 5.0

    def test_direction_improvement(self) -> None:
        """Improvement direction (higher is better)."""
        prog = KPIProgress(
            metric="material_efficiency",
            site_id="artibilim",
            baseline_value=85.0,
            current_value=90.0,
            target_percent=5.0,
            improvement_percent=5.88,
            target_met=True,
            unit="%",
            baseline_date=datetime(2026, 1, 1),
            current_date=datetime(2026, 7, 1),
            direction="improvement",
        )
        assert prog.direction == "improvement"

    def test_equality(self) -> None:
        """Two progress objects with same values are equal."""
        kwargs = dict(
            metric="energy_per_unit",
            site_id="artibilim",
            baseline_value=2.5,
            current_value=2.2,
            target_percent=8.0,
            improvement_percent=12.0,
            target_met=True,
            unit="kWh/unit",
            baseline_date=datetime(2026, 1, 1),
            current_date=datetime(2026, 6, 1),
            direction="reduction",
        )
        assert KPIProgress(**kwargs) == KPIProgress(**kwargs)
