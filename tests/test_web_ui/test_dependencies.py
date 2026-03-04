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
