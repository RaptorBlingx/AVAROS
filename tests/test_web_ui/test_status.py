"""
Tests for GET /api/v1/status system status endpoint.

Covers:
    - Unconfigured system returns mock defaults
    - Configured system returns correct adapter/platform
    - Database failure → graceful degradation
    - Response fields match SystemStatusResponse schema
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from skill.services.settings import PlatformConfig, SettingsService


class TestStatusUnconfigured:
    """Status endpoint with default (unconfigured) SettingsService."""

    def test_status_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/status returns 200 on fresh DB."""
        response = client.get("/api/v1/status")

        assert response.status_code == 200

    def test_status_unconfigured_defaults(self, client: TestClient) -> None:
        """Fresh DB reports configured=false, adapter=unconfigured."""
        body = client.get("/api/v1/status").json()

        assert body["configured"] is False
        assert body["active_adapter"] == "unconfigured"
        assert body["platform_type"] == "unconfigured"

    def test_status_database_connected_true(self, client: TestClient) -> None:
        """In-memory SQLite counts as connected database."""
        body = client.get("/api/v1/status").json()

        assert body["database_connected"] is True

    def test_status_includes_version(self, client: TestClient) -> None:
        """Response includes a non-empty version string."""
        body = client.get("/api/v1/status").json()

        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    def test_status_loaded_intents_is_int(self, client: TestClient) -> None:
        """loaded_intents is a non-negative integer."""
        body = client.get("/api/v1/status").json()

        assert isinstance(body["loaded_intents"], int)
        assert body["loaded_intents"] >= 0


class TestStatusConfigured:
    """Status endpoint after platform configuration is saved."""

    def test_status_configured_after_platform_set(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """After saving a reneryo config, configured=true."""
        settings_service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.example.com",
                api_key="secret-key-1234",
            )
        )

        body = client.get("/api/v1/status").json()

        assert body["configured"] is True
        assert body["active_adapter"] == "reneryo"
        assert body["platform_type"] == "reneryo"

    def test_status_returns_unconfigured_after_config_deleted(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Deleting platform config reverts to unconfigured."""
        settings_service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.example.com",
                api_key="secret-key-1234",
            )
        )
        settings_service.delete_profile("reneryo")

        body = client.get("/api/v1/status").json()

        assert body["configured"] is False
        assert body["active_adapter"] == "unconfigured"


class TestStatusDatabaseFailure:
    """Status endpoint when SettingsService raises an exception."""

    def test_status_graceful_degradation(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """When get_platform_config raises, endpoint returns safe defaults."""
        with patch.object(
            settings_service,
            "get_platform_config",
            side_effect=RuntimeError("DB gone"),
        ):
            body = client.get("/api/v1/status").json()

        assert body["configured"] is False
        assert body["active_adapter"] == "unconfigured"
        assert body["database_connected"] is False


class TestStatusResponseShape:
    """Validate the response shape matches schema expectations."""

    EXPECTED_KEYS = {
        "configured",
        "active_adapter",
        "platform_type",
        "loaded_intents",
        "database_connected",
        "version",
    }

    def test_status_response_keys(self, client: TestClient) -> None:
        """Response contains exactly the expected keys."""
        body = client.get("/api/v1/status").json()

        assert set(body.keys()) == self.EXPECTED_KEYS
