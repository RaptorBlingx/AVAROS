"""Tests for KPICollector — baseline seeding and snapshot collection.

All adapter calls are mocked; only the collector ↔ KPIMeasurementService
interaction is exercised against an in-memory SQLite database.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from services.kpi_collector import KPICollector, _KPI_METRICS  # noqa: E402
from skill.domain.models import CanonicalMetric, TimePeriod  # noqa: E402
from skill.domain.results import KPIResult  # noqa: E402
from skill.services.kpi_measurement import KPIMeasurementService  # noqa: E402
from skill.services.database import Base  # noqa: E402
from skill.services.settings import (  # noqa: E402
    Base as SettingsBase,
    PlatformConfig,
    SettingsService,
)


# ── Fixtures ────────────────────────────────────────────


def _make_settings(platform_type: str = "reneryo") -> SettingsService:
    svc = SettingsService()
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc._engine = engine
    svc._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    SettingsBase.metadata.create_all(engine)
    svc._initialized = True
    if platform_type != "mock":
        svc.update_platform_config(
            PlatformConfig(
                platform_type=platform_type,
                api_url="http://10.33.10.110:30896",
                api_key="test-key",
                extra_settings={"auth_type": "cookie"},
            )
        )
    return svc


def _make_kpi_service() -> KPIMeasurementService:
    svc = KPIMeasurementService(database_url="sqlite:///:memory:")
    svc._engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc._session_factory = sessionmaker(bind=svc._engine, expire_on_commit=False)
    Base.metadata.create_all(svc._engine)
    svc._initialized = True
    return svc


def _kpi_result(metric: CanonicalMetric, value: float, unit: str) -> KPIResult:
    return KPIResult(
        metric=metric,
        value=value,
        unit=unit,
        asset_id="Electric Main Meter",
        period=TimePeriod.last_month(),
        timestamp=datetime.utcnow(),
    )


def _mock_adapter() -> AsyncMock:
    adapter = AsyncMock()
    adapter.get_kpi = AsyncMock(
        side_effect=lambda m, *_a, **_k: _kpi_result(
            m,
            {
                CanonicalMetric.ENERGY_PER_UNIT: 2.35,
                CanonicalMetric.MATERIAL_EFFICIENCY: 87.5,
                CanonicalMetric.CO2_TOTAL: 1250.0,
            }[m],
            {
                CanonicalMetric.ENERGY_PER_UNIT: "kWh/unit",
                CanonicalMetric.MATERIAL_EFFICIENCY: "%",
                CanonicalMetric.CO2_TOTAL: "kg CO₂-eq",
            }[m],
        ),
    )
    adapter.initialize = AsyncMock()
    adapter.shutdown = AsyncMock()
    return adapter


# ── Tests ───────────────────────────────────────────────


class TestSeedBaselines:
    """Baseline seeding via KPICollector.seed_baselines()."""

    @pytest.mark.asyncio
    async def test_seeds_all_three_metrics(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        with patch.object(collector, "_create_adapter", return_value=_mock_adapter()):
            count = await collector.seed_baselines("pilot-1")

        assert count == 3
        baselines = kpi.get_all_baselines("pilot-1")
        metrics = {bl.metric for bl in baselines}
        assert metrics == {"energy_per_unit", "material_efficiency", "co2_total"}

    @pytest.mark.asyncio
    async def test_skips_existing_baselines(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        adapter = _mock_adapter()
        with patch.object(collector, "_create_adapter", return_value=adapter):
            await collector.seed_baselines("pilot-1")
            adapter.reset_mock()
            count = await collector.seed_baselines("pilot-1")

        assert count == 0

    @pytest.mark.asyncio
    async def test_skips_when_mock_platform(self) -> None:
        settings = _make_settings("mock")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        count = await collector.seed_baselines("pilot-1")

        assert count == 0
        assert kpi.get_all_baselines("pilot-1") == []

    @pytest.mark.asyncio
    async def test_records_correct_values(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        with patch.object(collector, "_create_adapter", return_value=_mock_adapter()):
            await collector.seed_baselines("pilot-1")

        bl = kpi.get_baseline("energy_per_unit", "pilot-1")
        assert bl is not None
        assert bl.baseline_value == pytest.approx(2.35)
        assert bl.unit == "kWh/unit"
        assert bl.notes == "auto-seeded by KPICollector"


class TestCollectSnapshots:
    """Snapshot collection via KPICollector.collect_snapshots()."""

    @pytest.mark.asyncio
    async def test_records_three_snapshots(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        with patch.object(collector, "_create_adapter", return_value=_mock_adapter()):
            count = await collector.collect_snapshots("pilot-1")

        assert count == 3
        for metric in ("energy_per_unit", "material_efficiency", "co2_total"):
            snaps = kpi.get_snapshots(metric, "pilot-1")
            assert len(snaps) == 1

    @pytest.mark.asyncio
    async def test_skips_when_mock_platform(self) -> None:
        settings = _make_settings("mock")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        count = await collector.collect_snapshots("pilot-1")

        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_collections_append(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        with patch.object(collector, "_create_adapter", return_value=_mock_adapter()):
            await collector.collect_snapshots("pilot-1")
            await collector.collect_snapshots("pilot-1")

        snaps = kpi.get_snapshots("energy_per_unit", "pilot-1")
        assert len(snaps) == 2


class TestErrorHandling:
    """Collector handles adapter errors gracefully."""

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        adapter = _mock_adapter()
        call_count = 0

        async def flaky_get_kpi(metric, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
                raise ConnectionError("timeout")
            return _kpi_result(
                metric,
                2.35 if metric == CanonicalMetric.ENERGY_PER_UNIT else 1250.0,
                "kWh/unit" if metric == CanonicalMetric.ENERGY_PER_UNIT else "kg CO₂-eq",
            )

        adapter.get_kpi = AsyncMock(side_effect=flaky_get_kpi)

        with patch.object(collector, "_create_adapter", return_value=adapter):
            count = await collector.seed_baselines("pilot-1")

        assert count == 2
        baselines = kpi.get_all_baselines("pilot-1")
        metrics = {bl.metric for bl in baselines}
        assert "material_efficiency" not in metrics
        assert "energy_per_unit" in metrics
        assert "co2_total" in metrics

    @pytest.mark.asyncio
    async def test_adapter_shutdown_called_on_error(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        adapter = _mock_adapter()
        adapter.get_kpi = AsyncMock(side_effect=RuntimeError("boom"))

        with patch.object(collector, "_create_adapter", return_value=adapter):
            await collector.collect_snapshots("pilot-1")

        adapter.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_derives_co2_total_from_energy_total_when_direct_metric_fails(self) -> None:
        settings = _make_settings("reneryo")
        kpi = _make_kpi_service()
        collector = KPICollector(settings, kpi)

        async def selective_get_kpi(metric, *args, **kwargs):
            if metric == CanonicalMetric.CO2_TOTAL:
                raise RuntimeError("co2 endpoint unavailable")
            if metric == CanonicalMetric.ENERGY_TOTAL:
                return _kpi_result(metric, 1000.0, "kWh")
            if metric == CanonicalMetric.ENERGY_PER_UNIT:
                return _kpi_result(metric, 2.35, "kWh/unit")
            raise RuntimeError("unsupported in this test")

        adapter = _mock_adapter()
        adapter.get_kpi = AsyncMock(side_effect=selective_get_kpi)

        with patch.object(collector, "_create_adapter", return_value=adapter):
            count = await collector.seed_baselines("pilot-1")

        # energy_per_unit direct + co2_total derived
        assert count >= 2
        co2 = kpi.get_baseline("co2_total", "pilot-1")
        assert co2 is not None
        # 1000 kWh * 0.48 (TR default electricity factor)
        assert co2.baseline_value == pytest.approx(480.0)
