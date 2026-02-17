"""Backward-compatibility API tests for DEC-029 profile scoping."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


def _ensure_reneryo_active(service: SettingsService) -> None:
    """Create and activate a reneryo profile for profile-transparent tests."""
    if service.get_profile("reneryo") is None:
        service.create_profile(
            "reneryo",
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.example.com",
                api_key="secret-key",
            ),
        )
    service.set_active_profile("reneryo")


def test_get_metrics_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET metrics stays profile-transparent without URL changes."""
    _ensure_reneryo_active(settings_service)
    settings_service.set_metric_mapping(
        "energy_per_unit",
        {"endpoint": "/energy", "json_path": "$.value", "unit": "kWh/unit", "transform": None},
    )

    reneryo_resp = client.get("/api/v1/config/metrics")
    assert reneryo_resp.status_code == 200
    assert len(reneryo_resp.json()) == 1

    settings_service.set_active_profile("mock")
    mock_resp = client.get("/api/v1/config/metrics")
    assert mock_resp.status_code == 200
    assert mock_resp.json() == []


def test_put_metric_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """PUT metric update writes into scoped active-profile key."""
    _ensure_reneryo_active(settings_service)
    payload = {
        "canonical_metric": "energy_per_unit",
        "endpoint": "/energy/v1",
        "json_path": "$.value",
        "unit": "kWh/unit",
        "transform": None,
    }
    client.post("/api/v1/config/metrics", json=payload)

    updated = dict(payload)
    updated["endpoint"] = "/energy/v2"
    resp = client.put("/api/v1/config/metrics/energy_per_unit", json=updated)

    assert resp.status_code == 200
    stored = settings_service.get_setting("metric_mapping:reneryo:energy_per_unit")
    assert stored["endpoint"] == "/energy/v2"


def test_get_emission_factors_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET emission factors remains profile-transparent."""
    _ensure_reneryo_active(settings_service)
    settings_service.set_emission_factor("electricity", 0.48, country="TR")

    reneryo_resp = client.get("/api/v1/config/emission-factors")
    reneryo_factors = {row["energy_source"]: row["factor"] for row in reneryo_resp.json()["factors"]}
    assert reneryo_factors["electricity"] == 0.48

    settings_service.set_active_profile("mock")
    mock_resp = client.get("/api/v1/config/emission-factors")
    mock_factors = {row["energy_source"]: row["factor"] for row in mock_resp.json()["factors"]}
    assert mock_factors["electricity"] == 0.48


def test_post_emission_factor_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """POST emission factor writes into scoped active-profile key."""
    _ensure_reneryo_active(settings_service)
    resp = client.post(
        "/api/v1/config/emission-factors",
        json={
            "energy_source": "electricity",
            "factor": 0.41,
            "country": "TR",
            "source": "Manual",
            "year": 2026,
        },
    )

    assert resp.status_code == 200
    stored = settings_service.get_setting("emission_factor:reneryo:electricity")
    assert stored["factor"] == 0.41


def test_get_intents_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET intents returns active profile state without endpoint changes."""
    _ensure_reneryo_active(settings_service)
    settings_service.set_intent_active("kpi.oee", False)

    reneryo_resp = client.get("/api/v1/config/intents")
    reneryo_items = {item["intent_name"]: item["active"] for item in reneryo_resp.json()["intents"]}
    assert reneryo_items["kpi.oee"] is False

    settings_service.set_active_profile("mock")
    mock_resp = client.get("/api/v1/config/intents")
    mock_items = {item["intent_name"]: item["active"] for item in mock_resp.json()["intents"]}
    assert all(mock_items.values()) is True


def test_put_intents_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """PUT intent toggle writes into scoped active-profile key."""
    _ensure_reneryo_active(settings_service)

    resp = client.put("/api/v1/config/intents/kpi.oee", json={"active": False})

    assert resp.status_code == 200
    assert settings_service.get_setting("intent_active:reneryo:kpi.oee") is False


def test_get_platform_config_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET platform endpoint remains unchanged and profile-aware."""
    _ensure_reneryo_active(settings_service)
    resp = client.get("/api/v1/config/platform")

    assert resp.status_code == 200
    body = resp.json()
    assert body["platform_type"] == "reneryo"
    assert body["api_url"] == "https://api.reneryo.example.com"


def test_post_platform_config_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """POST platform endpoint still writes active profile config."""
    _ensure_reneryo_active(settings_service)
    resp = client.post(
        "/api/v1/config/platform",
        json={
            "platform_type": "reneryo",
            "api_url": "https://api.updated.example.com",
            "api_key": "updated-key",
            "extra_settings": {"auth_type": "cookie"},
        },
    )

    assert resp.status_code == 200
    config = settings_service.get_platform_config()
    assert config.platform_type == "reneryo"
    assert config.api_url == "https://api.updated.example.com"


def test_profiles_list_endpoint_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Profiles list endpoint still returns mock first."""
    _ensure_reneryo_active(settings_service)
    settings_service.create_profile(
        "sap",
        PlatformConfig(platform_type="custom_rest", api_url="https://sap.example.com"),
    )

    resp = client.get("/api/v1/config/profiles")
    assert resp.status_code == 200
    body = resp.json()
    names = [item["name"] for item in body["profiles"]]
    assert names[0] == "mock"
    assert "reneryo" in names
    assert "sap" in names


def test_profiles_activate_endpoint_includes_voice_reloaded(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Activation response includes voice_reloaded field."""
    _ensure_reneryo_active(settings_service)
    settings_service.set_active_profile("mock")

    with patch("routers.profiles.AdapterFactory.reload", new=AsyncMock(return_value=None)):
        with patch("routers.profiles._notify_skill_via_bus", return_value=True):
            resp = client.post("/api/v1/config/profiles/reneryo/activate")

    assert resp.status_code == 200
    body = resp.json()
    assert "voice_reloaded" in body
    assert body["voice_reloaded"] is True