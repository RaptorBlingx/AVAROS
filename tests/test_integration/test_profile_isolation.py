"""Integration tests for profile data isolation (DEC-029)."""

from __future__ import annotations

import pytest

from skill.services.models import PlatformConfig, VoiceConfig
from skill.services.settings import SettingsService


@pytest.fixture
def svc() -> SettingsService:
    """Fresh in-memory SettingsService."""
    service = SettingsService(database_url="sqlite:///:memory:")
    service.initialize()
    return service


def _create_profiles(service: SettingsService) -> None:
    """Create two custom profiles used by isolation tests."""
    service.create_profile(
        "my-api",
        PlatformConfig(platform_type="custom_rest", api_url="https://api.example.com"),
    )
    service.create_profile(
        "sap",
        PlatformConfig(platform_type="custom_rest", api_url="https://sap.example.com"),
    )


def test_two_profiles_independent_metric_mappings(svc: SettingsService) -> None:
    """Each profile sees only its own metric mappings."""
    _create_profiles(svc)

    svc.set_active_profile("my-api")
    svc.set_metric_mapping("energy_per_unit", {"endpoint": "/e", "json_path": "$.e", "unit": "kWh/unit"})
    svc.set_metric_mapping("oee", {"endpoint": "/o", "json_path": "$.o", "unit": "%"})
    svc.set_metric_mapping("scrap_rate", {"endpoint": "/s", "json_path": "$.s", "unit": "%"})

    svc.set_active_profile("sap")
    svc.set_metric_mapping("co2_per_unit", {"endpoint": "/c", "json_path": "$.c", "unit": "kgCO2/unit"})

    assert set(svc.list_metric_mappings().keys()) == {"co2_per_unit"}

    svc.set_active_profile("my-api")
    assert set(svc.list_metric_mappings().keys()) == {
        "energy_per_unit",
        "oee",
        "scrap_rate",
    }


def test_two_profiles_independent_emission_factors(svc: SettingsService) -> None:
    """Emission factors are isolated by active profile."""
    _create_profiles(svc)

    svc.set_active_profile("my-api")
    svc.set_emission_factor("electricity", 0.48, country="TR")

    svc.set_active_profile("sap")
    svc.set_emission_factor("electricity", 0.35, country="DE")
    assert svc.get_emission_factor("electricity").factor == pytest.approx(0.35)

    svc.set_active_profile("my-api")
    assert svc.get_emission_factor("electricity").factor == pytest.approx(0.48)


def test_two_profiles_independent_intent_states(svc: SettingsService) -> None:
    """Intent activation states remain profile-scoped."""
    _create_profiles(svc)

    svc.set_active_profile("my-api")
    svc.set_intent_active("kpi.oee", False)
    svc.set_intent_active("kpi.scrap_rate", False)
    svc.set_intent_active("trend.energy", False)

    svc.set_active_profile("sap")
    sap_states = svc.list_intent_states()
    assert all(sap_states.values()) is True

    svc.set_active_profile("my-api")
    api_states = svc.list_intent_states()
    assert api_states["kpi.oee"] is False
    assert api_states["kpi.scrap_rate"] is False
    assert api_states["trend.energy"] is False


def test_switch_preserves_and_restores_all_domains(svc: SettingsService) -> None:
    """Round-trip switching restores each profile's full state."""
    _create_profiles(svc)

    svc.set_active_profile("my-api")
    svc.set_metric_mapping("energy_per_unit", {"endpoint": "/api", "json_path": "$.value", "unit": "kWh/unit"})
    svc.set_emission_factor("electricity", 0.48, country="TR")
    svc.set_intent_active("kpi.oee", False)
    api_snapshot = (
        svc.list_metric_mappings(),
        svc.get_effective_emission_factor("electricity"),
        svc.list_intent_states(),
    )

    svc.set_active_profile("sap")
    svc.set_metric_mapping("energy_per_unit", {"endpoint": "/sap", "json_path": "$.data", "unit": "kWh/unit"})
    svc.set_emission_factor("electricity", 0.35, country="DE")
    svc.set_intent_active("kpi.oee", True)

    svc.set_active_profile("my-api")
    assert svc.list_metric_mappings() == api_snapshot[0]
    assert svc.get_effective_emission_factor("electricity") == pytest.approx(api_snapshot[1])
    assert svc.list_intent_states() == api_snapshot[2]


def test_delete_profile_removes_scoped_settings(svc: SettingsService) -> None:
    """Deleting a profile removes all profile-scoped keys."""
    svc.create_profile(
        "temp",
        PlatformConfig(platform_type="custom_rest", api_url="https://temp.example.com"),
    )
    svc.set_active_profile("temp")
    svc.set_metric_mapping("energy_per_unit", {"endpoint": "/temp", "json_path": "$.e", "unit": "kWh/unit"})
    svc.set_emission_factor("electricity", 0.4, country="TR")
    svc.set_intent_active("kpi.oee", False)

    svc.set_active_profile("unconfigured")
    assert svc.delete_profile("temp") is True

    keys = svc.list_settings()
    assert all(not key.startswith("metric_mapping:temp:") for key in keys)
    assert all(not key.startswith("emission_factor:temp:") for key in keys)
    assert all(not key.startswith("intent_active:temp:") for key in keys)


def test_profile_switch_does_not_affect_voice_config(svc: SettingsService) -> None:
    """Voice configuration remains global across profile switches."""
    _create_profiles(svc)
    svc.update_voice_config(
        VoiceConfig(
            hivemind_url="ws://custom:5678",
            hivemind_name="web-client",
            hivemind_key="client-key",
            hivemind_secret="client-secret",
        )
    )

    svc.set_active_profile("my-api")
    svc.set_active_profile("sap")
    svc.set_active_profile("unconfigured")

    voice = svc.get_voice_config()
    assert voice.hivemind_url == "ws://custom:5678"
    assert voice.hivemind_name == "web-client"
    assert voice.hivemind_key == "client-key"