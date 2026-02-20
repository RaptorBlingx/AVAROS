"""SettingsService tests for non-metric intent binding CRUD."""

from __future__ import annotations

import pytest

from skill.domain.exceptions import ValidationError
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


@pytest.fixture
def service() -> SettingsService:
    """Create initialized in-memory settings service."""
    settings = SettingsService(database_url="sqlite:///:memory:")
    settings.initialize()
    return settings


@pytest.fixture
def active_reneryo_profile(service: SettingsService) -> None:
    """Create and activate a non-mock profile for writable binding tests."""
    service.create_profile(
        "reneryo",
        PlatformConfig(
            platform_type="reneryo",
            api_url="https://api.reneryo.example.com",
        ),
    )
    service.set_active_profile("reneryo")


def test_list_intent_bindings_mock_returns_defaults(
    service: SettingsService,
) -> None:
    """Mock profile should expose built-in non-metric intent bindings."""
    service.set_active_profile("mock")

    bindings = service.list_intent_bindings()

    assert "control.device.turn_on" in bindings
    assert bindings["status.system.show"]["endpoint"] == "/mock/status/system"


def test_set_intent_binding_non_mock_persists(
    service: SettingsService,
    active_reneryo_profile: None,
) -> None:
    """set_intent_binding should persist under active profile scope."""
    payload = {
        "endpoint": "/api/control/on",
        "method": "POST",
        "json_path": "$.message",
        "success_path": "$.ok",
        "transform": None,
    }

    service.set_intent_binding("control.device.turn_on", payload)

    stored = service.get_intent_binding("control.device.turn_on")
    assert stored is not None
    assert stored["endpoint"] == "/api/control/on"
    assert stored["method"] == "POST"


def test_delete_intent_binding_non_mock_removes_value(
    service: SettingsService,
    active_reneryo_profile: None,
) -> None:
    """delete_intent_binding should remove persisted non-metric binding."""
    service.set_intent_binding(
        "status.profile.show",
        {
            "endpoint": "/api/status/profile",
            "method": "GET",
            "json_path": "$.profile",
            "success_path": "$.success",
            "transform": None,
        },
    )

    deleted = service.delete_intent_binding("status.profile.show")

    assert deleted is True
    assert service.get_intent_binding("status.profile.show") is None


def test_set_intent_binding_invalid_name_raises(
    service: SettingsService,
    active_reneryo_profile: None,
) -> None:
    """Unknown intent name should fail validation."""
    with pytest.raises(ValidationError):
        service.set_intent_binding(
            "status.unknown.intent",
            {
                "endpoint": "/api/x",
                "method": "GET",
                "json_path": "$.x",
                "success_path": None,
                "transform": None,
            },
        )


def test_delete_intent_binding_mock_returns_false(
    service: SettingsService,
) -> None:
    """Mock profile delete should remain read-only."""
    service.set_active_profile("mock")

    deleted = service.delete_intent_binding("status.system.show")

    assert deleted is False
