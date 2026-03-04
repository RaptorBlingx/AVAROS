"""Unit tests for FastAPI dependency providers."""

from __future__ import annotations

import sys
from pathlib import Path


WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if WEB_UI_DIR not in sys.path:
    sys.path.insert(0, WEB_UI_DIR)

import dependencies  # noqa: E402


class FakeSettingsService:
    """Lightweight stand-in to verify caching semantics."""

    created = 0
    initialized = 0

    def __init__(self) -> None:
        type(self).created += 1

    def initialize(self) -> None:
        type(self).initialized += 1


<<<<<<< HEAD
=======
class FakeKPIMeasurementService:
    """Lightweight stand-in for KPI measurement dependency."""


class FakeKPICollector:
    """Track constructor calls for KPI collector singleton test."""

    created = 0

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        type(self).created += 1


class FakeKPIScheduler:
    """Track constructor calls for KPI scheduler singleton test."""

    created = 0

    def __init__(self, collector: FakeKPICollector) -> None:
        type(self).created += 1
        self.collector = collector


>>>>>>> feature/P6-E02-dashboard-scheduler-fixes
def test_get_settings_service_returns_cached_singleton(monkeypatch) -> None:
    """Consecutive calls should reuse one initialized SettingsService."""
    FakeSettingsService.created = 0
    FakeSettingsService.initialized = 0
    dependencies.get_settings_service.cache_clear()
    monkeypatch.setattr(dependencies, "SettingsService", FakeSettingsService)

    first = dependencies.get_settings_service()
    second = dependencies.get_settings_service()

    assert first is second
    assert FakeSettingsService.created == 1
    assert FakeSettingsService.initialized == 1

    dependencies.get_settings_service.cache_clear()


def test_get_adapter_factory_uses_cached_settings_instance(monkeypatch) -> None:
    """AdapterFactory should receive the cached SettingsService instance."""
    FakeSettingsService.created = 0
    FakeSettingsService.initialized = 0
    dependencies.get_settings_service.cache_clear()
    monkeypatch.setattr(dependencies, "SettingsService", FakeSettingsService)

    settings_service = dependencies.get_settings_service()
    factory = dependencies.get_adapter_factory(settings_service=settings_service)

    assert factory._settings_service is settings_service

    dependencies.get_settings_service.cache_clear()
<<<<<<< HEAD
=======


def test_get_kpi_scheduler_returns_cached_singleton(monkeypatch) -> None:
    """KPI scheduler provider should create one shared singleton instance."""
    FakeKPICollector.created = 0
    FakeKPIScheduler.created = 0
    dependencies.get_kpi_scheduler.cache_clear()

    monkeypatch.setattr(dependencies, "KPICollector", FakeKPICollector)
    monkeypatch.setattr(dependencies, "KPIScheduler", FakeKPIScheduler)
    monkeypatch.setattr(
        dependencies,
        "get_kpi_measurement_service",
        lambda: FakeKPIMeasurementService(),
    )

    first = dependencies.get_kpi_scheduler()
    second = dependencies.get_kpi_scheduler()

    assert first is second
    assert FakeKPICollector.created == 1
    assert FakeKPIScheduler.created == 1

    dependencies.get_kpi_scheduler.cache_clear()
>>>>>>> feature/P6-E02-dashboard-scheduler-fixes
