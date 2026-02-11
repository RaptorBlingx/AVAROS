"""
ProductionRecord and ProductionSummary Domain Model Tests

Covers:
    - ProductionRecord validation (frozen, non-negative, good ≤ production, date)
    - ProductionSummary properties (material_efficiency edge cases)
    - DEC-004 frozen enforcement
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from skill.domain.production import ProductionRecord, ProductionSummary


# ══════════════════════════════════════════════════════════
# ProductionRecord — Valid Construction
# ══════════════════════════════════════════════════════════


class TestProductionRecordConstruction:
    """Happy path construction tests."""

    def test_create_minimal_record(self) -> None:
        """Minimal required fields produce a valid record."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=100,
            good_count=95,
            material_consumed_kg=50.0,
        )
        assert record.record_date == date(2026, 1, 15)
        assert record.asset_id == "Line-1"
        assert record.production_count == 100
        assert record.good_count == 95
        assert record.material_consumed_kg == 50.0

    def test_create_full_record(self) -> None:
        """All optional fields set correctly."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-2",
            production_count=500,
            good_count=490,
            material_consumed_kg=120.5,
            shift="morning",
            batch_id="B-2026-001",
            notes="Normal operation",
        )
        assert record.shift == "morning"
        assert record.batch_id == "B-2026-001"
        assert record.notes == "Normal operation"

    def test_zero_production_count_allowed(self) -> None:
        """Zero production is valid (e.g., maintenance day)."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=0,
            good_count=0,
            material_consumed_kg=0.0,
        )
        assert record.production_count == 0

    def test_defaults_for_optional_fields(self) -> None:
        """Optional fields default to empty strings."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=10,
            good_count=10,
            material_consumed_kg=5.0,
        )
        assert record.shift == ""
        assert record.batch_id == ""
        assert record.notes == ""

    def test_today_date_allowed(self) -> None:
        """Today's date is valid — boundary case."""
        record = ProductionRecord(
            record_date=date.today(),
            asset_id="Line-1",
            production_count=1,
            good_count=1,
            material_consumed_kg=0.5,
        )
        assert record.record_date == date.today()


# ══════════════════════════════════════════════════════════
# ProductionRecord — Validation Failures
# ══════════════════════════════════════════════════════════


class TestProductionRecordValidation:
    """Validation rules on __post_init__."""

    def test_negative_production_count_raises(self) -> None:
        """production_count < 0 raises ValueError."""
        with pytest.raises(ValueError, match="production_count must be >= 0"):
            ProductionRecord(
                record_date=date(2026, 1, 15),
                asset_id="Line-1",
                production_count=-1,
                good_count=0,
                material_consumed_kg=0.0,
            )

    def test_negative_good_count_raises(self) -> None:
        """good_count < 0 raises ValueError."""
        with pytest.raises(ValueError, match="good_count must be >= 0"):
            ProductionRecord(
                record_date=date(2026, 1, 15),
                asset_id="Line-1",
                production_count=10,
                good_count=-1,
                material_consumed_kg=5.0,
            )

    def test_negative_material_raises(self) -> None:
        """material_consumed_kg < 0 raises ValueError."""
        with pytest.raises(ValueError, match="material_consumed_kg must be >= 0"):
            ProductionRecord(
                record_date=date(2026, 1, 15),
                asset_id="Line-1",
                production_count=10,
                good_count=10,
                material_consumed_kg=-1.0,
            )

    def test_good_exceeds_production_raises(self) -> None:
        """good_count > production_count raises ValueError."""
        with pytest.raises(ValueError, match="good_count.*cannot exceed"):
            ProductionRecord(
                record_date=date(2026, 1, 15),
                asset_id="Line-1",
                production_count=10,
                good_count=11,
                material_consumed_kg=5.0,
            )

    def test_future_date_raises(self) -> None:
        """Future date raises ValueError."""
        future = date.today() + timedelta(days=1)
        with pytest.raises(ValueError, match="cannot be in the future"):
            ProductionRecord(
                record_date=future,
                asset_id="Line-1",
                production_count=10,
                good_count=10,
                material_consumed_kg=5.0,
            )


# ══════════════════════════════════════════════════════════
# ProductionRecord — DEC-004 Frozen Enforcement
# ══════════════════════════════════════════════════════════


class TestProductionRecordFrozen:
    """DEC-004: Domain models must be immutable."""

    def test_cannot_modify_production_count(self) -> None:
        """Attempting to set a field raises FrozenInstanceError."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=100,
            good_count=95,
            material_consumed_kg=50.0,
        )
        with pytest.raises(AttributeError):
            record.production_count = 200  # type: ignore[misc]

    def test_cannot_modify_asset_id(self) -> None:
        """Frozen dataclass field assignment raises."""
        record = ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=1,
            good_count=1,
            material_consumed_kg=1.0,
        )
        with pytest.raises(AttributeError):
            record.asset_id = "Line-2"  # type: ignore[misc]


# ══════════════════════════════════════════════════════════
# ProductionSummary — Construction & Properties
# ══════════════════════════════════════════════════════════


class TestProductionSummary:
    """ProductionSummary construction and derived properties."""

    def test_material_efficiency_normal(self) -> None:
        """Standard efficiency calculation."""
        summary = ProductionSummary(
            total_produced=1000,
            total_good=950,
            total_material_kg=500.0,
            record_count=5,
        )
        assert summary.material_efficiency == 95.0

    def test_material_efficiency_perfect(self) -> None:
        """100% efficiency when all units are good."""
        summary = ProductionSummary(
            total_produced=100,
            total_good=100,
            total_material_kg=50.0,
            record_count=1,
        )
        assert summary.material_efficiency == 100.0

    def test_material_efficiency_zero_produced(self) -> None:
        """Zero production returns 0.0 (not division by zero)."""
        summary = ProductionSummary(
            total_produced=0,
            total_good=0,
            total_material_kg=0.0,
            record_count=0,
        )
        assert summary.material_efficiency == 0.0

    def test_material_efficiency_rounding(self) -> None:
        """Efficiency is rounded to 1 decimal place."""
        summary = ProductionSummary(
            total_produced=3,
            total_good=2,
            total_material_kg=10.0,
            record_count=1,
        )
        # 2/3 * 100 = 66.666... → 66.7
        assert summary.material_efficiency == 66.7

    def test_frozen_enforcement(self) -> None:
        """DEC-004: ProductionSummary is immutable."""
        summary = ProductionSummary(
            total_produced=100,
            total_good=90,
            total_material_kg=50.0,
            record_count=1,
        )
        with pytest.raises(AttributeError):
            summary.total_produced = 200  # type: ignore[misc]
