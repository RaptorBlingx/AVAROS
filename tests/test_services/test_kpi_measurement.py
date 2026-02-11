"""
KPI Measurement Service Test Suite

Covers baseline CRUD, snapshot recording, progress computation,
and dataset export using in-memory SQLite.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from skill.domain.exceptions import ConfigurationError
from skill.domain.kpi_baseline import KPIBaseline, KPIProgress, KPISnapshot
from skill.services.database import Base
from skill.services.kpi_measurement import KPIMeasurementService


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def service() -> KPIMeasurementService:
    """In-memory KPIMeasurementService with thread-safe StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc = KPIMeasurementService(database_url="sqlite:///:memory:")
    svc._engine = engine
    svc._session_factory = sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    Base.metadata.create_all(engine)
    svc._initialized = True
    return svc


def _make_baseline(
    metric: str = "energy_per_unit",
    site_id: str = "artibilim",
    value: float = 2.5,
    unit: str = "kWh/unit",
) -> KPIBaseline:
    """Create a test baseline with sensible defaults."""
    return KPIBaseline(
        metric=metric,
        site_id=site_id,
        baseline_value=value,
        unit=unit,
        recorded_at=datetime(2026, 1, 15, 10, 0),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )


def _make_snapshot(
    metric: str = "energy_per_unit",
    site_id: str = "artibilim",
    value: float = 2.2,
    unit: str = "kWh/unit",
    measured_at: datetime | None = None,
) -> KPISnapshot:
    """Create a test snapshot with sensible defaults."""
    return KPISnapshot(
        metric=metric,
        site_id=site_id,
        value=value,
        unit=unit,
        measured_at=measured_at or datetime(2026, 6, 15, 14, 30),
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
    )


# ══════════════════════════════════════════════════════════
# Baseline CRUD
# ══════════════════════════════════════════════════════════


class TestBaselineCRUD:
    """Baseline record, retrieve, upsert, and delete."""

    def test_record_baseline_and_retrieve(
        self, service: KPIMeasurementService,
    ) -> None:
        """Record a baseline then retrieve it by metric/site."""
        bl = _make_baseline()
        row_id = service.record_baseline(bl)
        assert row_id > 0

        result = service.get_baseline("energy_per_unit", "artibilim")
        assert result is not None
        assert result.baseline_value == 2.5
        assert result.unit == "kWh/unit"

    def test_upsert_baseline_replaces_value(
        self, service: KPIMeasurementService,
    ) -> None:
        """Recording same metric+site overwrites the old baseline."""
        service.record_baseline(_make_baseline(value=2.5))
        service.record_baseline(_make_baseline(value=2.3))

        result = service.get_baseline("energy_per_unit", "artibilim")
        assert result is not None
        assert result.baseline_value == 2.3

    def test_get_baseline_not_found(
        self, service: KPIMeasurementService,
    ) -> None:
        """Missing baseline returns None."""
        result = service.get_baseline("nonexistent", "artibilim")
        assert result is None

    def test_get_all_baselines(
        self, service: KPIMeasurementService,
    ) -> None:
        """Multiple baselines for a site are returned."""
        service.record_baseline(_make_baseline(metric="energy_per_unit"))
        service.record_baseline(
            _make_baseline(metric="co2_per_unit", value=0.8, unit="kg CO2/unit"),
        )

        baselines = service.get_all_baselines("artibilim")
        assert len(baselines) == 2
        metrics = {bl.metric for bl in baselines}
        assert metrics == {"energy_per_unit", "co2_per_unit"}

    def test_delete_baseline_existing(
        self, service: KPIMeasurementService,
    ) -> None:
        """Deleting an existing baseline returns True, then gone."""
        service.record_baseline(_make_baseline())
        assert service.delete_baseline("energy_per_unit", "artibilim") is True
        assert service.get_baseline("energy_per_unit", "artibilim") is None

    def test_delete_baseline_not_found(
        self, service: KPIMeasurementService,
    ) -> None:
        """Deleting non-existent baseline returns False."""
        assert service.delete_baseline("fake", "fake_site") is False


# ══════════════════════════════════════════════════════════
# Snapshot CRUD
# ══════════════════════════════════════════════════════════


class TestSnapshotCRUD:
    """Snapshot recording and retrieval."""

    def test_record_and_get_snapshots(
        self, service: KPIMeasurementService,
    ) -> None:
        """Record snapshots then retrieve in chronological order."""
        s1 = _make_snapshot(
            value=2.4, measured_at=datetime(2026, 3, 15),
        )
        s2 = _make_snapshot(
            value=2.2, measured_at=datetime(2026, 6, 15),
        )
        service.record_snapshot(s1)
        service.record_snapshot(s2)

        results = service.get_snapshots("energy_per_unit", "artibilim")
        assert len(results) == 2
        assert results[0].value == 2.4
        assert results[1].value == 2.2

    def test_get_snapshots_date_filter(
        self, service: KPIMeasurementService,
    ) -> None:
        """Date filters narrow the results."""
        s1 = _make_snapshot(measured_at=datetime(2026, 3, 15))
        s2 = _make_snapshot(measured_at=datetime(2026, 6, 15))
        service.record_snapshot(s1)
        service.record_snapshot(s2)

        results = service.get_snapshots(
            "energy_per_unit", "artibilim",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 7, 1),
        )
        assert len(results) == 1
        assert results[0].value == 2.2

    def test_get_snapshots_empty(
        self, service: KPIMeasurementService,
    ) -> None:
        """No snapshots returns empty list."""
        results = service.get_snapshots("energy_per_unit", "artibilim")
        assert results == []


# ══════════════════════════════════════════════════════════
# Progress Computation
# ══════════════════════════════════════════════════════════


class TestProgressComputation:
    """KPI progress calculation against WASABI targets."""

    def test_reduction_metric_energy(
        self, service: KPIMeasurementService,
    ) -> None:
        """Energy reduction: baseline 2.5, current 2.2 → 12% improvement."""
        service.record_baseline(_make_baseline(value=2.5))

        progress = service.compute_progress(
            "energy_per_unit", "artibilim", 2.2, "kWh/unit",
        )
        assert progress.improvement_percent == 12.0
        assert progress.target_percent == 8.0
        assert progress.target_met is True
        assert progress.direction == "reduction"

    def test_improvement_metric_material(
        self, service: KPIMeasurementService,
    ) -> None:
        """Material efficiency: baseline 85, current 90 → ~5.88%."""
        service.record_baseline(
            _make_baseline(
                metric="material_efficiency",
                value=85.0,
                unit="%",
            ),
        )
        progress = service.compute_progress(
            "material_efficiency", "artibilim", 90.0, "%",
        )
        assert progress.improvement_percent == 5.88
        assert progress.target_percent == 5.0
        assert progress.target_met is True
        assert progress.direction == "improvement"

    def test_no_baseline_raises_config_error(
        self, service: KPIMeasurementService,
    ) -> None:
        """Computing progress without baseline raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="No baseline"):
            service.compute_progress(
                "energy_per_unit", "artibilim", 2.2, "kWh/unit",
            )

    def test_reduction_target_not_met(
        self, service: KPIMeasurementService,
    ) -> None:
        """Small reduction that doesn't meet the 8% target."""
        service.record_baseline(_make_baseline(value=2.5))

        progress = service.compute_progress(
            "energy_per_unit", "artibilim", 2.45, "kWh/unit",
        )
        assert progress.improvement_percent == 2.0
        assert progress.target_met is False

    def test_co2_reduction_metric(
        self, service: KPIMeasurementService,
    ) -> None:
        """CO₂ metric uses 10% reduction target."""
        service.record_baseline(
            _make_baseline(
                metric="co2_per_unit", value=1.0, unit="kg CO2/unit",
            ),
        )
        progress = service.compute_progress(
            "co2_per_unit", "artibilim", 0.85, "kg CO2/unit",
        )
        assert progress.improvement_percent == 15.0
        assert progress.target_percent == 10.0
        assert progress.target_met is True

    def test_zero_baseline_returns_zero_improvement(
        self, service: KPIMeasurementService,
    ) -> None:
        """Zero baseline avoids division by zero, returns 0%."""
        service.record_baseline(_make_baseline(value=0.0))

        progress = service.compute_progress(
            "energy_per_unit", "artibilim", 2.0, "kWh/unit",
        )
        assert progress.improvement_percent == 0.0

    def test_non_wasabi_metric_zero_target(
        self, service: KPIMeasurementService,
    ) -> None:
        """Non-WASABI metric gets 0% target, direction=reduction."""
        service.record_baseline(
            _make_baseline(metric="oee", value=80.0, unit="%"),
        )
        progress = service.compute_progress(
            "oee", "artibilim", 85.0, "%",
        )
        assert progress.target_percent == 0.0
        assert progress.direction == "reduction"


# ══════════════════════════════════════════════════════════
# All Progress
# ══════════════════════════════════════════════════════════


class TestAllProgress:
    """Get all progress for a site."""

    def test_get_all_progress_for_site(
        self, service: KPIMeasurementService,
    ) -> None:
        """Progress computed for each metric with current values."""
        service.record_baseline(
            _make_baseline(metric="energy_per_unit", value=2.5),
        )
        service.record_baseline(
            _make_baseline(
                metric="material_efficiency", value=85.0, unit="%",
            ),
        )

        current_values = {
            "energy_per_unit": (2.2, "kWh/unit"),
            "material_efficiency": (90.0, "%"),
        }
        results = service.get_all_progress("artibilim", current_values)
        assert len(results) == 2
        metrics = {r.metric for r in results}
        assert metrics == {"energy_per_unit", "material_efficiency"}

    def test_all_progress_skips_missing_current(
        self, service: KPIMeasurementService,
    ) -> None:
        """Metrics without current values are skipped."""
        service.record_baseline(_make_baseline())
        results = service.get_all_progress("artibilim", {})
        assert len(results) == 0


# ══════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════


class TestExport:
    """Export anonymized KPI dataset."""

    def test_export_format(
        self, service: KPIMeasurementService,
    ) -> None:
        """Export returns list of dicts with required fields."""
        service.record_baseline(_make_baseline())
        dataset = service.export_kpi_dataset("artibilim")

        assert len(dataset) == 1
        row = dataset[0]
        assert row["metric"] == "energy_per_unit"
        assert row["site_id"] == "site_1"
        assert row["baseline_value"] == 2.5
        assert row["unit"] == "kWh/unit"
        assert "period_start" in row
        assert "period_end" in row

    def test_export_empty_site(
        self, service: KPIMeasurementService,
    ) -> None:
        """Export for site with no baselines returns empty list."""
        dataset = service.export_kpi_dataset("nonexistent")
        assert dataset == []
