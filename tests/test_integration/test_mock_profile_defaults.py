"""Integration tests for built-in mock profile behavior."""

from __future__ import annotations

import pytest

from skill.domain.exceptions import ValidationError
from skill.services.settings import KNOWN_INTENTS, SettingsService


@pytest.fixture
def svc() -> SettingsService:
    """Fresh in-memory SettingsService with mock as active profile."""
    service = SettingsService(database_url="sqlite:///:memory:")
    service.initialize()
    service.set_active_profile("mock")
    return service


def test_mock_metric_mappings_empty(svc: SettingsService) -> None:
    """Mock profile exposes built-in metric mappings for demo API."""
    mappings = svc.list_metric_mappings()
    assert len(mappings) >= 3
    assert "energy_per_unit" in mappings
    assert "oee" in mappings
    assert "scrap_rate" in mappings


def test_mock_get_metric_mapping_returns_none(svc: SettingsService) -> None:
    """Mock profile returns virtual mapping entries."""
    mapping = svc.get_metric_mapping("energy_per_unit")
    assert mapping is not None
    assert mapping["endpoint"] == "/api/v1/kpis/energy/per-unit"
    assert mapping["json_path"] == "$.value"


def test_mock_emission_factors_turkey_defaults(svc: SettingsService) -> None:
    """Mock profile returns Türkiye default emission factors."""
    factors = svc.list_emission_factors()
    assert factors["electricity"].factor == pytest.approx(0.48)
    assert factors["gas"].factor == pytest.approx(0.2)


def test_mock_intent_states_all_true(svc: SettingsService) -> None:
    """Mock profile keeps all known intents enabled."""
    states = svc.list_intent_states()
    assert len(states) == len(KNOWN_INTENTS)
    assert all(states.values()) is True


def test_mock_write_metric_mapping_raises(svc: SettingsService) -> None:
    """Mock profile rejects metric mapping writes."""
    with pytest.raises(ValidationError):
        svc.set_metric_mapping(
            "energy_per_unit",
            {"endpoint": "/x", "json_path": "$.x", "unit": "kWh/unit"},
        )


def test_mock_write_emission_factor_raises(svc: SettingsService) -> None:
    """Mock profile rejects emission factor writes."""
    with pytest.raises(ValidationError):
        svc.set_emission_factor("electricity", 0.48)


def test_mock_write_intent_active_raises(svc: SettingsService) -> None:
    """Mock profile rejects intent state writes."""
    with pytest.raises(ValidationError):
        svc.set_intent_active("kpi.oee", False)


def test_mock_get_effective_emission_factor_returns_turkey(svc: SettingsService) -> None:
    """Effective emission factor falls back to Türkiye default on mock."""
    assert svc.get_effective_emission_factor("electricity") == pytest.approx(0.48)