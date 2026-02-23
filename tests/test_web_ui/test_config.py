"""
Tests for platform configuration CRUD endpoints.

Covers:
    - POST /api/v1/config/platform  — create/update
    - GET  /api/v1/config/platform  — read (masked key)
    - DELETE /api/v1/config/platform — reset
    - POST /api/v1/config/platform/test — real connection test
    - Validation: invalid URL, missing required fields
    - API key masking logic
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from routers.config import _create_adapter_from_config
from schemas.config import PlatformConfigRequest
from skill.domain.results import ConnectionTestResult
from skill.services.settings import SettingsService


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture()
def valid_reneryo_payload() -> dict[str, Any]:
    """Valid non-mock platform config payload."""
    return {
        "platform_type": "reneryo",
        "api_url": "https://api.reneryo.example.com/v1",
        "api_key": "reneryo-secret-key-1234",
        "extra_settings": {"tenant_id": "wasabi-01"},
    }


@pytest.fixture()
def valid_mock_payload() -> dict[str, Any]:
    """Valid mock platform config payload (no URL/key required)."""
    return {
        "platform_type": "mock",
        "api_url": "",
        "api_key": "",
        "extra_settings": {},
    }


# ══════════════════════════════════════════════════════════
# POST /api/v1/config/platform
# ══════════════════════════════════════════════════════════


class TestCreatePlatformConfig:
    """Tests for creating/updating platform configuration."""

    def test_create_reneryo_config_returns_201_or_200(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """POST with valid reneryo payload succeeds."""
        response = client.post(
            "/api/v1/config/platform",
            json=valid_reneryo_payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["platform_type"] == "reneryo"

    def test_create_config_masks_api_key(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Returned API key is masked, not plaintext."""
        response = client.post(
            "/api/v1/config/platform",
            json=valid_reneryo_payload,
        )

        body = response.json()
        assert body["api_key"].startswith("****")
        assert "reneryo-secret" not in body["api_key"]

    def test_create_config_preserves_extra_settings(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Extra settings are persisted and returned."""
        response = client.post(
            "/api/v1/config/platform",
            json=valid_reneryo_payload,
        )

        assert response.json()["extra_settings"] == {"tenant_id": "wasabi-01"}

    def test_create_config_drops_legacy_seu_id_setting(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Platform config must not persist deprecated top-level seu_id."""
        payload = {
            **valid_reneryo_payload,
            "extra_settings": {
                "auth_type": "cookie",
                "seu_id": "SEU-123",
                "tenant_id": "wasabi-01",
            },
        }
        response = client.post("/api/v1/config/platform", json=payload)

        assert response.status_code == 200
        assert response.json()["extra_settings"] == {
            "auth_type": "cookie",
            "tenant_id": "wasabi-01",
        }

    def test_create_mock_config_succeeds(
        self,
        client: TestClient,
        valid_mock_payload: dict[str, Any],
    ) -> None:
        """Mock platform type does not require URL or key."""
        response = client.post(
            "/api/v1/config/platform",
            json=valid_mock_payload,
        )

        assert response.status_code == 200
        assert response.json()["platform_type"] == "mock"

    def test_create_config_upsert_overwrites(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Second POST overwrites first (upsert behaviour)."""
        client.post("/api/v1/config/platform", json=valid_reneryo_payload)

        updated = {
            **valid_reneryo_payload,
            "api_url": "https://api.reneryo-v2.example.com",
        }
        response = client.post("/api/v1/config/platform", json=updated)

        assert response.status_code == 200
        assert response.json()["api_url"] == "https://api.reneryo-v2.example.com"


# ══════════════════════════════════════════════════════════
# POST validation errors
# ══════════════════════════════════════════════════════════


class TestCreatePlatformConfigValidation:
    """Validation error tests for platform config creation."""

    def test_reject_non_mock_without_api_url(
        self,
        client: TestClient,
    ) -> None:
        """Non-mock platform without api_url returns 422."""
        response = client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "reneryo",
                "api_url": "",
                "api_key": "some-key",
            },
        )

        assert response.status_code == 422

    def test_reject_non_mock_without_api_key(
        self,
        client: TestClient,
    ) -> None:
        """Non-mock platform without api_key returns 422."""
        response = client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "reneryo",
                "api_url": "https://api.example.com",
                "api_key": "",
            },
        )

        assert response.status_code == 422

    def test_reject_invalid_url_format(
        self,
        client: TestClient,
    ) -> None:
        """Non-mock platform with malformed URL returns 422."""
        response = client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "reneryo",
                "api_url": "not-a-url",
                "api_key": "some-key",
            },
        )

        assert response.status_code == 422

    def test_reject_unknown_platform_type(
        self,
        client: TestClient,
    ) -> None:
        """Unknown platform_type returns 422."""
        response = client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "totally_unknown",
                "api_url": "https://api.example.com",
                "api_key": "key",
            },
        )

        assert response.status_code == 422

    def test_reject_missing_platform_type(
        self,
        client: TestClient,
    ) -> None:
        """Missing required platform_type field returns 422."""
        response = client.post(
            "/api/v1/config/platform",
            json={
                "api_url": "https://api.example.com",
                "api_key": "key",
            },
        )

        assert response.status_code == 422


# ══════════════════════════════════════════════════════════
# GET /api/v1/config/platform
# ══════════════════════════════════════════════════════════


class TestGetPlatformConfig:
    """Tests for reading platform configuration."""

    def test_get_default_config_returns_mock(
        self,
        client: TestClient,
    ) -> None:
        """Fresh DB returns default mock config."""
        response = client.get("/api/v1/config/platform")

        assert response.status_code == 200
        body = response.json()
        assert body["platform_type"] == "mock"

    def test_get_config_after_create(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """GET returns the config saved by POST."""
        client.post("/api/v1/config/platform", json=valid_reneryo_payload)

        response = client.get("/api/v1/config/platform")

        assert response.status_code == 200
        body = response.json()
        assert body["platform_type"] == "reneryo"
        assert body["api_url"] == valid_reneryo_payload["api_url"]

    def test_get_config_api_key_is_masked(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """GET never exposes the raw API key."""
        client.post("/api/v1/config/platform", json=valid_reneryo_payload)

        body = client.get("/api/v1/config/platform").json()

        assert body["api_key"].startswith("****")
        assert valid_reneryo_payload["api_key"] not in body["api_key"]


# ══════════════════════════════════════════════════════════
# DELETE /api/v1/config/platform
# ══════════════════════════════════════════════════════════


class TestResetPlatformConfig:
    """Tests for resetting platform configuration."""

    def test_reset_returns_mock_status(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """DELETE returns reset status with mock platform."""
        client.post("/api/v1/config/platform", json=valid_reneryo_payload)

        response = client.delete("/api/v1/config/platform")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "reset"
        assert body["platform_type"] == "mock"

    def test_reset_reverts_get_to_mock(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """After DELETE, GET returns default mock config."""
        client.post("/api/v1/config/platform", json=valid_reneryo_payload)
        client.delete("/api/v1/config/platform")

        body = client.get("/api/v1/config/platform").json()

        assert body["platform_type"] == "mock"

    def test_reset_on_fresh_db_still_succeeds(
        self,
        client: TestClient,
    ) -> None:
        """DELETE on unconfigured DB does not error."""
        response = client.delete("/api/v1/config/platform")

        assert response.status_code == 200
        assert response.json()["platform_type"] == "mock"


# ══════════════════════════════════════════════════════════
# POST /api/v1/config/platform/test
# ══════════════════════════════════════════════════════════


class TestConnectionTest:
    """Tests for POST /api/v1/config/platform/test (real implementation)."""

    def test_mock_platform_succeeds_with_adapter_name(
        self,
        client: TestClient,
        valid_mock_payload: dict[str, Any],
    ) -> None:
        """Mock platform test returns success with adapter name."""
        response = client.post(
            "/api/v1/config/platform/test",
            json=valid_mock_payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["adapter_name"] == "Demo (Mock)"
        assert "demo" in body["message"].lower()
        assert len(body["resources_discovered"]) == 3

    def test_mock_platform_returns_latency(
        self,
        client: TestClient,
        valid_mock_payload: dict[str, Any],
    ) -> None:
        """Mock platform test includes latency_ms field."""
        response = client.post(
            "/api/v1/config/platform/test",
            json=valid_mock_payload,
        )

        body = response.json()
        assert body["latency_ms"] >= 0

    def test_reneryo_connection_success(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """RENERYO test with mocked adapter returns success + meters."""
        mock_result = ConnectionTestResult(
            success=True,
            latency_ms=55.3,
            message="Connected — 2 meter(s) discovered",
            adapter_name="RENERYO",
            resources_discovered=("Meter-A", "Meter-B"),
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=valid_reneryo_payload,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["latency_ms"] == 55.3
        assert body["adapter_name"] == "RENERYO"
        assert body["resources_discovered"] == ["Meter-A", "Meter-B"]

    def test_reneryo_connection_auth_failure(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """RENERYO test with 401 returns auth error details."""
        mock_result = ConnectionTestResult(
            success=False,
            latency_ms=12.0,
            message="Authentication failed — check API key",
            adapter_name="RENERYO",
            error_code="RENERYO_AUTH_FAILED",
            error_details="HTTP 401",
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=valid_reneryo_payload,
            )

        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "RENERYO_AUTH_FAILED"

    def test_reneryo_connection_unreachable(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """RENERYO test with unreachable server returns connection error."""
        mock_result = ConnectionTestResult(
            success=False,
            latency_ms=3000.0,
            message="Cannot reach server — check URL and network",
            adapter_name="RENERYO",
            error_code="RENERYO_CONNECTION_FAILED",
            error_details="Connection refused",
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=valid_reneryo_payload,
            )

        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "RENERYO_CONNECTION_FAILED"

    def test_response_includes_resources_list(
        self,
        client: TestClient,
        valid_mock_payload: dict[str, Any],
    ) -> None:
        """Response includes resources_discovered as a list."""
        response = client.post(
            "/api/v1/config/platform/test",
            json=valid_mock_payload,
        )

        body = response.json()
        assert isinstance(body["resources_discovered"], list)
        assert len(body["resources_discovered"]) > 0

    def test_unknown_platform_returns_error(
        self,
        client: TestClient,
    ) -> None:
        """Unknown platform_type returns adapter creation error."""
        payload = {
            "platform_type": "custom_rest",
            "api_url": "https://example.com",
            "api_key": "key",
        }
        response = client.post(
            "/api/v1/config/platform/test",
            json=payload,
        )

        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "ADAPTER_CREATION_FAILED"

    def test_connection_test_does_not_save_config(
        self,
        client: TestClient,
        settings_service: SettingsService,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Testing doesn't modify stored platform config."""
        # Get config before test
        config_before = settings_service.get_platform_config()

        mock_result = ConnectionTestResult(
            success=True,
            latency_ms=10.0,
            message="OK",
            adapter_name="RENERYO",
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            client.post(
                "/api/v1/config/platform/test",
                json=valid_reneryo_payload,
            )

        # Config should be unchanged
        config_after = settings_service.get_platform_config()
        assert config_before.platform_type == config_after.platform_type


# ══════════════════════════════════════════════════════════
# API key masking helper
# ══════════════════════════════════════════════════════════


class TestApiKeyMasking:
    """Tests for the _mask_api_key helper via round-trip."""

    def test_long_key_shows_last_four(
        self,
        client: TestClient,
    ) -> None:
        """Keys longer than 4 chars show ****XXXX (last 4)."""
        payload = {
            "platform_type": "reneryo",
            "api_url": "https://api.example.com",
            "api_key": "abcdefgh",
        }
        response = client.post("/api/v1/config/platform", json=payload)

        assert response.json()["api_key"] == "****efgh"

    def test_short_key_fully_masked(
        self,
        client: TestClient,
    ) -> None:
        """Keys with 4 or fewer chars are fully masked as ****."""
        payload = {
            "platform_type": "reneryo",
            "api_url": "https://api.example.com",
            "api_key": "abcd",
        }
        response = client.post("/api/v1/config/platform", json=payload)

        assert response.json()["api_key"] == "****"


# ══════════════════════════════════════════════════════════
# Auth type pass-through in connection test
# ══════════════════════════════════════════════════════════


class TestConnectionTestAuthType:
    """Tests for auth_type pass-through to adapter creation."""

    def test_connection_test_with_cookie_auth_type(
        self,
        client: TestClient,
    ) -> None:
        """POST with auth_type=cookie creates adapter with cookie auth."""
        payload = {
            "platform_type": "reneryo",
            "api_url": "https://api.reneryo.example.com",
            "api_key": "session-cookie-value",
            "extra_settings": {"auth_type": "cookie"},
        }
        mock_result = ConnectionTestResult(
            success=True,
            latency_ms=42.0,
            message="Connected via cookie auth",
            adapter_name="RENERYO",
            resources_discovered=("Meter-1",),
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=payload,
            )

            # Verify auth_type was passed through in the payload
            call_args = mock_factory.call_args[0][0]
            assert call_args.extra_settings.get("auth_type") == "cookie"

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestAdapterFactoryAuthType:
    """Direct unit tests for adapter factory auth_type wiring."""

    def test_create_adapter_with_cookie_auth_passes_cookie_to_reneryo_adapter(
        self,
    ) -> None:
        """Factory forwards auth_type=cookie to ReneryoAdapter constructor."""
        payload = PlatformConfigRequest(
            platform_type="reneryo",
            api_url="https://api.reneryo.example.com",
            api_key="session-cookie-value",
            extra_settings={"auth_type": "cookie"},
        )

        with patch("skill.adapters.reneryo.ReneryoAdapter") as mock_adapter_class:
            _create_adapter_from_config(payload)

        assert mock_adapter_class.call_count == 1
        assert mock_adapter_class.call_args.kwargs["auth_type"] == "cookie"

    def test_connection_test_with_bearer_auth_type(
        self,
        client: TestClient,
    ) -> None:
        """POST with auth_type=bearer creates adapter with bearer auth."""
        payload = {
            "platform_type": "reneryo",
            "api_url": "https://api.reneryo.example.com",
            "api_key": "api-key-value",
            "extra_settings": {"auth_type": "bearer"},
        }
        mock_result = ConnectionTestResult(
            success=True,
            latency_ms=30.0,
            message="Connected via bearer auth",
            adapter_name="RENERYO",
            resources_discovered=("Meter-A",),
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=payload,
            )

            call_args = mock_factory.call_args[0][0]
            assert call_args.extra_settings.get("auth_type") == "bearer"

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_connection_test_without_auth_type_defaults_to_bearer(
        self,
        client: TestClient,
    ) -> None:
        """POST without auth_type in extra_settings defaults to bearer."""
        payload = {
            "platform_type": "reneryo",
            "api_url": "https://api.reneryo.example.com",
            "api_key": "api-key-value",
            "extra_settings": {},
        }
        mock_result = ConnectionTestResult(
            success=True,
            latency_ms=25.0,
            message="Connected",
            adapter_name="RENERYO",
            resources_discovered=(),
        )
        with patch(
            "routers.config._create_adapter_from_config",
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = mock_result
            mock_factory.return_value = mock_adapter

            response = client.post(
                "/api/v1/config/platform/test",
                json=payload,
            )

            # extra_settings should have no auth_type — adapter defaults
            call_args = mock_factory.call_args[0][0]
            assert call_args.extra_settings.get("auth_type", "bearer") == "bearer"

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_create_adapter_supports_legacy_seu_id_fallback(
        self,
    ) -> None:
        """Connection-test adapter keeps legacy seu_id fallback for compatibility."""
        payload = PlatformConfigRequest(
            platform_type="reneryo",
            api_url="https://api.reneryo.example.com",
            api_key="api-key-value",
            extra_settings={"auth_type": "bearer", "seu_id": "SEU-123"},
        )

        with patch("skill.adapters.reneryo.ReneryoAdapter") as mock_adapter_class:
            _create_adapter_from_config(payload)

        assert mock_adapter_class.call_count == 1
        assert mock_adapter_class.call_args.kwargs["native_seu_id"] == "SEU-123"
        assert "seu_id" not in mock_adapter_class.call_args.kwargs["extra_settings"]


# ══════════════════════════════════════════════════════════
# Profile endpoints (P5-L08)
# ══════════════════════════════════════════════════════════


class TestProfileEndpoints:
    """Smoke tests for profile CRUD and activation endpoints."""

    def test_list_profiles_contains_mock_first(self, client: TestClient) -> None:
        """GET /profiles always includes built-in mock profile first."""
        response = client.get("/api/v1/config/profiles")
        assert response.status_code == 200
        body = response.json()
        assert body["active_profile"] == "mock"
        assert len(body["profiles"]) >= 1
        assert body["profiles"][0]["name"] == "mock"
        assert body["profiles"][0]["is_builtin"] is True

    def test_create_get_activate_delete_profile_flow(self, client: TestClient) -> None:
        """Create custom profile, activate it, then delete it."""
        create_resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "site-a",
                "platform_type": "reneryo",
                "api_url": "https://api.reneryo.example.com",
                "api_key": "secret-1234",
                "extra_settings": {"auth_type": "cookie"},
            },
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["name"] == "site-a"

        get_resp = client.get("/api/v1/config/profiles/site-a")
        assert get_resp.status_code == 200
        assert get_resp.json()["platform_type"] == "reneryo"
        assert get_resp.json()["is_builtin"] is False

        activate_resp = client.post("/api/v1/config/profiles/site-a/activate")
        assert activate_resp.status_code == 200
        assert activate_resp.json()["is_active"] is True

        list_resp = client.get("/api/v1/config/profiles")
        assert list_resp.status_code == 200
        assert list_resp.json()["active_profile"] == "site-a"

        platform_resp = client.get("/api/v1/config/platform")
        assert platform_resp.status_code == 200
        assert platform_resp.json()["platform_type"] == "reneryo"

        delete_resp = client.delete("/api/v1/config/profiles/site-a")
        assert delete_resp.status_code == 204

        list_after_delete = client.get("/api/v1/config/profiles").json()
        assert list_after_delete["active_profile"] == "mock"

    def test_delete_mock_profile_rejected(self, client: TestClient) -> None:
        """DELETE mock profile is blocked."""
        response = client.delete("/api/v1/config/profiles/mock")
        assert response.status_code == 400

    def test_activate_missing_profile_returns_404(self, client: TestClient) -> None:
        """Activating unknown profile returns 404."""
        response = client.post("/api/v1/config/profiles/does-not-exist/activate")
        assert response.status_code == 404

    def test_activate_reneryo_overwrites_cookie(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Activating reneryo profile forces default cookie auth key."""
        create_resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "reneryo",
                "platform_type": "reneryo",
                "api_url": "http://10.33.10.110:30896",
                "api_key": "old-cookie",
                "extra_settings": {"auth_type": "bearer"},
            },
        )
        assert create_resp.status_code == 201

        activate_resp = client.post("/api/v1/config/profiles/reneryo/activate")
        assert activate_resp.status_code == 200
        assert activate_resp.json()["is_active"] is True

        platform_cfg = settings_service.get_platform_config()
        assert platform_cfg.platform_type == "reneryo"
        assert (
            platform_cfg.api_key
            == "575e90e9-ac4b-4fa8-a373-1206b67b2ad5."
            "b4DLZUbCyjECM0mb2C%2Fy9ca%2BekfgWv9tCVc8C5Unq2E%3D"
        )
        assert platform_cfg.extra_settings.get("auth_type") == "cookie"

    def test_activate_mock_collects_kpi_data(self, client: TestClient) -> None:
        """Mock activation triggers baseline seed + historical snapshots."""
        fake_collector = AsyncMock()
        fake_collector.seed_baselines = AsyncMock(return_value=3)
        fake_collector.seed_mock_snapshot_history = AsyncMock(return_value=30)

        with patch("routers.config.KPICollector", return_value=fake_collector):
            resp = client.post("/api/v1/config/profiles/mock/activate")

        assert resp.status_code == 200
        fake_collector.seed_baselines.assert_awaited_once_with("pilot-1")
        fake_collector.seed_mock_snapshot_history.assert_awaited_once_with("pilot-1", points=10)
