"""Backward-compatibility API tests for DEC-029 profile scoping."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


def _ensure_custom_rest_active(service: SettingsService) -> None:
    """Create and activate a custom_rest profile for profile-transparent tests."""
    if service.get_profile("my-api") is None:
        service.create_profile(
            "my-api",
            PlatformConfig(
                platform_type="custom_rest",
                api_url="https://api.example.com",
                api_key="secret-key",
            ),
        )
    service.set_active_profile("my-api")


def test_get_metrics_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET metrics stays profile-transparent without URL changes."""
    _ensure_custom_rest_active(settings_service)
    settings_service.set_metric_mapping(
        "energy_per_unit",
        {"endpoint": "/energy", "json_path": "$.value", "unit": "kWh/unit", "transform": None},
    )

    api_resp = client.get("/api/v1/config/metrics")
    assert api_resp.status_code == 200
    assert len(api_resp.json()) == 1

    settings_service.set_active_profile("unconfigured")
    mock_resp = client.get("/api/v1/config/metrics")
    assert mock_resp.status_code == 200
    mock_items = mock_resp.json()
    assert len(mock_items) >= 3
    by_metric = {item["canonical_metric"]: item for item in mock_items}
    assert by_metric["energy_per_unit"]["endpoint"] == "/api/v1/kpis/energy/per-unit"


def test_put_metric_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """PUT metric update writes into scoped active-profile key."""
    _ensure_custom_rest_active(settings_service)
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
    stored = settings_service.get_setting("metric_mapping:my-api:energy_per_unit")
    assert stored["endpoint"] == "/energy/v2"


def test_get_emission_factors_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET emission factors remains profile-transparent."""
    _ensure_custom_rest_active(settings_service)
    settings_service.set_emission_factor("electricity", 0.48, country="TR")

    api_resp = client.get("/api/v1/config/emission-factors")
    api_factors = {row["energy_source"]: row["factor"] for row in api_resp.json()["factors"]}
    assert api_factors["electricity"] == 0.48

    settings_service.set_active_profile("unconfigured")
    mock_resp = client.get("/api/v1/config/emission-factors")
    mock_factors = {row["energy_source"]: row["factor"] for row in mock_resp.json()["factors"]}
    assert mock_factors["electricity"] == 0.48


def test_post_emission_factor_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """POST emission factor writes into scoped active-profile key."""
    _ensure_custom_rest_active(settings_service)
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
    stored = settings_service.get_setting("emission_factor:my-api:electricity")
    assert stored["factor"] == 0.41


def test_get_intents_returns_active_profile_data(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET intents returns active profile state without endpoint changes."""
    _ensure_custom_rest_active(settings_service)
    settings_service.set_intent_active("kpi.oee", False)

    api_resp = client.get("/api/v1/config/intents")
    api_items = {item["intent_name"]: item["active"] for item in api_resp.json()["intents"]}
    assert api_items["kpi.oee"] is False

    settings_service.set_active_profile("unconfigured")
    mock_resp = client.get("/api/v1/config/intents")
    mock_items = {item["intent_name"]: item["active"] for item in mock_resp.json()["intents"]}
    assert all(mock_items.values()) is True


def test_put_intents_writes_to_active_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """PUT intent toggle writes into scoped active-profile key."""
    _ensure_custom_rest_active(settings_service)

    resp = client.put("/api/v1/config/intents/kpi.oee", json={"active": False})

    assert resp.status_code == 200
    assert settings_service.get_setting("intent_active:my-api:kpi.oee") is False


def test_get_platform_config_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """GET platform endpoint remains unchanged and profile-aware."""
    _ensure_custom_rest_active(settings_service)
    resp = client.get("/api/v1/config/platform")

    assert resp.status_code == 200
    body = resp.json()
    assert body["platform_type"] == "custom_rest"
    assert body["api_url"] == "https://api.example.com"


def test_post_platform_config_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """POST platform endpoint still writes active profile config."""
    _ensure_custom_rest_active(settings_service)
    resp = client.post(
        "/api/v1/config/platform",
        json={
            "platform_type": "custom_rest",
            "api_url": "https://api.updated.example.com",
            "api_key": "updated-key",
            "extra_settings": {"auth_type": "cookie"},
        },
    )

    assert resp.status_code == 200
    config = settings_service.get_platform_config()
    assert config.platform_type == "custom_rest"
    assert config.api_url == "https://api.updated.example.com"


def test_profiles_list_endpoint_unchanged(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Profiles list endpoint still returns mock first."""
    _ensure_custom_rest_active(settings_service)
    settings_service.create_profile(
        "sap",
        PlatformConfig(platform_type="custom_rest", api_url="https://sap.example.com"),
    )

    resp = client.get("/api/v1/config/profiles")
    assert resp.status_code == 200
    body = resp.json()
    names = [item["name"] for item in body["profiles"]]
    assert "my-api" in names
    assert "sap" in names


def test_profiles_activate_endpoint_includes_voice_reloaded(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Activation response includes voice_reloaded field."""
    _ensure_custom_rest_active(settings_service)
    settings_service.set_active_profile("unconfigured")

    with patch("routers.profiles.AdapterFactory.reload", new=AsyncMock(return_value=None)):
        with patch("routers.profiles._notify_skill_via_bus", return_value=True):
            resp = client.post("/api/v1/config/profiles/my-api/activate")

    assert resp.status_code == 200
    body = resp.json()
    assert "voice_reloaded" in body
    assert body["voice_reloaded"] is True