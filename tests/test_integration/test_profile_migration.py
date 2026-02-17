"""Integration tests for DEC-029 global-to-profile migration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from skill.services.settings import PlatformConfig, SettingsService


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """Return a file-based SQLite URL for reopen migration tests."""
    db_path = tmp_path / "settings.db"
    return f"sqlite:///{db_path}"


def _init_service(database_url: str) -> SettingsService:
    """Create and initialize a service instance."""
    service = SettingsService(database_url=database_url)
    service.initialize()
    return service


def _seed_active_profile(service: SettingsService, name: str = "reneryo") -> None:
    """Create and activate a custom profile."""
    service.create_profile(
        name,
        PlatformConfig(
            platform_type=name,
            api_url=f"https://api.{name}.example.com",
        ),
    )
    service.set_active_profile(name)


def _sample_mapping() -> dict[str, Any]:
    """Return a simple metric mapping payload."""
    return {
        "endpoint": "/api/v1/kpis/energy",
        "json_path": "$.data.value",
        "unit": "kWh/unit",
        "transform": None,
    }


def test_migration_global_metric_mappings_to_active_profile(database_url: str) -> None:
    """Global metric mapping migrates to active profile key."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting("metric_mapping:energy_per_unit", _sample_mapping())
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("metric_mapping:energy_per_unit") is None
    assert migrated.get_setting("metric_mapping:reneryo:energy_per_unit") == _sample_mapping()
    migrated.close()


def test_migration_global_emission_factors_to_active_profile(database_url: str) -> None:
    """Global emission factor migrates to active profile key."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting(
        "emission_factor:electricity",
        {
            "energy_source": "electricity",
            "factor": 0.48,
            "country": "TR",
            "source": "IEA 2024",
            "year": 2024,
        },
    )
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("emission_factor:electricity") is None
    assert migrated.get_setting("emission_factor:reneryo:electricity")["factor"] == 0.48
    migrated.close()


def test_migration_global_intent_states_to_active_profile(database_url: str) -> None:
    """Global intent activation migrates to active profile key."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting("intent_active:kpi.energy.per_unit", "false")
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("intent_active:kpi.energy.per_unit") is None
    assert migrated.get_setting("intent_active:reneryo:kpi.energy.per_unit") is False
    migrated.close()


def test_migration_combined_all_domains(database_url: str) -> None:
    """All legacy domains migrate in one initialization run."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting("metric_mapping:energy_per_unit", _sample_mapping())
    service.set_setting(
        "emission_factor:electricity",
        {
            "energy_source": "electricity",
            "factor": 0.48,
            "country": "TR",
            "source": "IEA 2024",
            "year": 2024,
        },
    )
    service.set_setting("intent_active:kpi.oee", "false")
    service.close()

    migrated = _init_service(database_url)
    keys = set(migrated.list_settings())
    assert "metric_mapping:reneryo:energy_per_unit" in keys
    assert "emission_factor:reneryo:electricity" in keys
    assert "intent_active:reneryo:kpi.oee" in keys
    assert "metric_mapping:energy_per_unit" not in keys
    assert "emission_factor:electricity" not in keys
    assert "intent_active:kpi.oee" not in keys
    migrated.close()


def test_migration_idempotent_run_twice(database_url: str) -> None:
    """Running migration twice does not create duplicates."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting("metric_mapping:energy_per_unit", _sample_mapping())
    service.close()

    first = _init_service(database_url)
    first_keys = sorted(first.list_settings())
    first.close()

    second = _init_service(database_url)
    second_keys = sorted(second.list_settings())
    assert second_keys == first_keys
    second.close()


def test_migration_skips_when_active_is_mock(database_url: str) -> None:
    """No migration occurs while active profile is mock."""
    service = _init_service(database_url)
    service.set_setting("metric_mapping:energy_per_unit", _sample_mapping())
    service.set_setting("emission_factor:electricity", {"factor": 0.48})
    service.set_setting("intent_active:kpi.oee", "false")
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("metric_mapping:energy_per_unit") is not None
    assert migrated.get_setting("emission_factor:electricity") is not None
    assert migrated.get_setting("intent_active:kpi.oee") is False
    assert migrated.get_setting("metric_mapping:mock:energy_per_unit") is None
    migrated.close()


def test_migration_skips_already_scoped_keys(database_url: str) -> None:
    """Legacy key is removed while existing scoped key value is preserved."""
    service = _init_service(database_url)
    _seed_active_profile(service)
    service.set_setting("metric_mapping:energy_per_unit", {"unit": "legacy"})
    service.set_setting("metric_mapping:reneryo:energy_per_unit", {"unit": "new"})
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("metric_mapping:energy_per_unit") is None
    assert migrated.get_setting("metric_mapping:reneryo:energy_per_unit") == {"unit": "new"}
    migrated.close()


def test_migration_chained_with_legacy_platform_config(database_url: str) -> None:
    """Legacy platform config migration chains with global settings migration."""
    service = _init_service(database_url)
    service.set_setting(
        "platform_config",
        {
            "platform_type": "reneryo",
            "api_url": "https://api.reneryo.example.com",
            "api_key": "",
            "extra_settings": {},
        },
    )
    service.set_setting("metric_mapping:energy_per_unit", _sample_mapping())
    service.close()

    migrated = _init_service(database_url)
    assert migrated.get_setting("platform_config") is None
    assert migrated.get_active_profile_name() == "reneryo"
    assert migrated.get_setting("platform_config:reneryo") is not None
    assert migrated.get_setting("metric_mapping:reneryo:energy_per_unit") == _sample_mapping()
    assert migrated.get_setting("metric_mapping:energy_per_unit") is None
    migrated.close()