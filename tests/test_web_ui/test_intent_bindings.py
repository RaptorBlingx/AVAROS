"""Tests for non-metric intent binding CRUD endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from skill.services.settings import PlatformConfig, SettingsService


@pytest.fixture()
def binding_payload() -> dict[str, Any]:
    """Valid intent binding payload for control.turn_on."""
    return {
        "intent_name": "control.device.turn_on",
        "endpoint": "/api/control/turn-on",
        "method": "POST",
        "json_path": "$.message",
        "success_path": "$.success",
        "transform": None,
    }


@pytest.fixture(autouse=True)
def active_profile(settings_service: SettingsService) -> None:
    """Use non-mock profile for writable CRUD tests."""
    if settings_service.get_profile("reneryo") is None:
        settings_service.create_profile(
            "reneryo",
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.example.com",
            ),
        )
    settings_service.set_active_profile("reneryo")


def test_create_intent_binding_returns_201(
    client: TestClient,
    binding_payload: dict[str, Any],
) -> None:
    """POST should create binding and return 201."""
    response = client.post("/api/v1/config/intent-bindings", json=binding_payload)

    assert response.status_code == 201
    assert response.json()["intent_name"] == "control.device.turn_on"


def test_list_intent_bindings_returns_created_item(
    client: TestClient,
    binding_payload: dict[str, Any],
) -> None:
    """GET should return created intent binding."""
    client.post("/api/v1/config/intent-bindings", json=binding_payload)

    response = client.get("/api/v1/config/intent-bindings")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["endpoint"] == "/api/control/turn-on"


def test_update_intent_binding_returns_200(
    client: TestClient,
    binding_payload: dict[str, Any],
) -> None:
    """PUT should update existing binding."""
    client.post("/api/v1/config/intent-bindings", json=binding_payload)

    updated = dict(binding_payload)
    updated["endpoint"] = "/api/control/turn-on/v2"
    response = client.put(
        "/api/v1/config/intent-bindings/control.device.turn_on",
        json=updated,
    )

    assert response.status_code == 200
    assert response.json()["endpoint"] == "/api/control/turn-on/v2"


def test_delete_intent_binding_returns_204(
    client: TestClient,
    binding_payload: dict[str, Any],
) -> None:
    """DELETE should remove existing binding."""
    client.post("/api/v1/config/intent-bindings", json=binding_payload)

    response = client.delete(
        "/api/v1/config/intent-bindings/control.device.turn_on",
    )

    assert response.status_code == 204


def test_update_intent_binding_rejects_path_body_mismatch(
    client: TestClient,
    binding_payload: dict[str, Any],
) -> None:
    """PUT should reject mismatched intent_name body/path values."""
    client.post("/api/v1/config/intent-bindings", json=binding_payload)

    updated = dict(binding_payload)
    updated["intent_name"] = "status.system.show"
    response = client.put(
        "/api/v1/config/intent-bindings/control.device.turn_on",
        json=updated,
    )

    assert response.status_code == 422


def test_create_intent_binding_rejects_invalid_intent_name(
    client: TestClient,
) -> None:
    """POST should fail when intent name is outside supported set."""
    response = client.post(
        "/api/v1/config/intent-bindings",
        json={
            "intent_name": "status.unknown.intent",
            "endpoint": "/api/x",
            "method": "GET",
            "json_path": "$.x",
            "success_path": None,
            "transform": None,
        },
    )

    assert response.status_code == 422


def test_get_intent_bindings_mock_returns_defaults(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Mock profile should return built-in default bindings."""
    settings_service.set_active_profile("mock")

    response = client.get("/api/v1/config/intent-bindings")

    assert response.status_code == 200
    items = response.json()
    by_name = {item["intent_name"]: item for item in items}
    assert "help.capabilities.list" in by_name
    assert by_name["status.system.show"]["endpoint"] == "/mock/status/system"
