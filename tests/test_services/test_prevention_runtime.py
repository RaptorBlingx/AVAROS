"""Tests for PREVENTION runtime manifest and data freshness helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from skill.services.prevention_runtime import (
    PreventionConfig,
    _summarize_prevention_capabilities,
    probe_prevention_status,
    resolve_prevention_config,
    resolve_prevention_data_status,
)


class _Settings:
    """Tiny SettingsService stand-in for runtime resolver tests."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._values = values or {}

    def get_setting(self, key: str, default=None):
        return self._values.get(key, default)


def test_resolve_prevention_data_status_uses_env_manifest_path(
    monkeypatch,
    tmp_path,
) -> None:
    """Manifest path can be injected for container-safe runtime checks."""
    manifest_path = tmp_path / "export_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                "platform": "mock",
                "days": 7,
                "total_records": 42,
                "files": {},
            },
        ),
    )
    monkeypatch.setenv("PREVENTION_EXPORT_MANIFEST_PATH", str(manifest_path))

    status = resolve_prevention_data_status(settings_service=None)

    assert status.state == "fresh"
    assert status.record_count == 42
    assert "42 records" in status.message


def test_resolve_prevention_config_detects_keycloak_mode(
    monkeypatch,
) -> None:
    """Keycloak/OIDC credentials enable client-credentials auth mode."""
    monkeypatch.delenv("PREVENTION_AUTH_MODE", raising=False)
    monkeypatch.delenv("PREVENTION_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("PREVENTION_URL", "http://prevention:8081")
    monkeypatch.setenv("PREVENTION_KEYCLOAK_TOKEN_URL", "http://keycloak/token")
    monkeypatch.setenv("PREVENTION_KEYCLOAK_CLIENT_ID", "avaros")
    monkeypatch.setenv("PREVENTION_KEYCLOAK_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PREVENTION_KEYCLOAK_SCOPE", "openid")

    config = resolve_prevention_config(settings_service=None)

    assert config.auth_mode == "keycloak_client_credentials"
    assert config.keycloak_token_url == "http://keycloak/token"
    assert config.keycloak_client_id == "avaros"
    assert config.keycloak_client_secret == "secret"
    assert config.keycloak_scope == "openid"


def test_resolve_prevention_config_supports_saved_keycloak_mode(
    monkeypatch,
) -> None:
    """Saved Wizard settings can provide Keycloak/OIDC auth values."""
    monkeypatch.delenv("PREVENTION_URL", raising=False)
    monkeypatch.delenv("PREVENTION_AUTH_MODE", raising=False)
    settings = _Settings(
        {
            "prevention_url": "http://prevention:8081",
            "prevention_auth_mode": "keycloak_client_credentials",
            "prevention_keycloak_token_url": "http://keycloak/token",
            "prevention_keycloak_client_id": "avaros",
            "prevention_keycloak_client_secret": "secret",
        },
    )

    config = resolve_prevention_config(settings)

    assert config.auth_mode == "keycloak_client_credentials"
    assert config.endpoint_source == "settings"


@pytest.mark.asyncio
async def test_probe_prevention_status_rejects_incomplete_keycloak_config() -> None:
    """Keycloak mode should fail fast before unauthenticated GraphQL probing."""
    status = await probe_prevention_status(
        PreventionConfig(
            url="http://prevention:8081",
            auth_token="",
            auth_mode="keycloak_client_credentials",
            keycloak_token_url="http://keycloak/token",
            keycloak_client_id="avaros",
            keycloak_client_secret="",
            keycloak_scope="",
            mode="http",
            mode_reason="test",
            endpoint_source="test",
        ),
    )

    assert status.state == "misconfigured"
    assert "client secret" in status.message


def test_summarize_prevention_capabilities_reports_predictive_active() -> None:
    """Capability summary separates descriptive, predictive, and prescriptive."""
    capability = _summarize_prevention_capabilities([
        {
            "analytics_goal": "ENERGY_ANOMALY_CHECK",
            "analytics_type": "DESCRIPTIVE",
        },
        {
            "analytics_goal": "ENERGY_FORECAST",
            "analytics_type": "PREDICTIVE",
        },
    ])

    assert capability["descriptive_state"] == "active"
    assert capability["predictive_state"] == "active"
    assert capability["goals"] == ("ENERGY_ANOMALY_CHECK", "ENERGY_FORECAST")
    assert capability["types"] == ("DESCRIPTIVE", "PREDICTIVE")


def test_summarize_prevention_capabilities_reports_predictive_missing() -> None:
    """Predictive is not configured until forecast goals exist."""
    capability = _summarize_prevention_capabilities([
        {
            "analytics_goal": "ENERGY_ANOMALY_CHECK",
            "analytics_type": "DESCRIPTIVE",
        },
    ])

    assert capability["descriptive_state"] == "active"
    assert capability["predictive_state"] == "not_configured"
