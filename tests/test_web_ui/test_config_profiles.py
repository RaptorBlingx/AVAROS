"""
Tests for profile CRUD and activation endpoints.

Covers:
    - GET    /api/v1/config/profiles           — list all
    - GET    /api/v1/config/profiles/{name}     — single profile
    - POST   /api/v1/config/profiles            — create
    - PUT    /api/v1/config/profiles/{name}     — update
    - DELETE /api/v1/config/profiles/{name}     — delete
    - POST   /api/v1/config/profiles/{name}/activate — switch
    - Legacy /platform endpoints still work
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture()
def reneryo_profile_payload() -> dict[str, Any]:
    """Valid create-profile payload for a reneryo profile."""
    return {
        "name": "reneryo",
        "platform_type": "reneryo",
        "api_url": "https://api.reneryo.example.com/v1",
        "api_key": "reneryo-secret-key-1234",
        "extra_settings": {"auth_type": "cookie"},
    }


@pytest.fixture()
def sap_profile_payload() -> dict[str, Any]:
    """Valid create-profile payload for a custom_rest profile."""
    return {
        "name": "sap-staging",
        "platform_type": "custom_rest",
        "api_url": "https://sap.example.com/api",
        "api_key": "secret123",
        "extra_settings": {"auth_type": "bearer"},
    }


def _seed_profile(
    svc: SettingsService,
    name: str,
    platform_type: str = "reneryo",
    api_url: str = "https://api.example.com",
    api_key: str = "test-key-1234",
) -> None:
    """Create a profile directly via SettingsService."""
    svc.create_profile(
        name,
        PlatformConfig(
            platform_type=platform_type,
            api_url=api_url,
            api_key=api_key,
        ),
    )


# ══════════════════════════════════════════════════════════
# GET /api/v1/config/profiles
# ══════════════════════════════════════════════════════════


class TestListProfiles:
    """Tests for listing all profiles."""

    def test_list_profiles_empty_returns_mock(
        self, client: TestClient,
    ) -> None:
        """Empty DB returns empty profiles with unconfigured active."""
        resp = client.get("/api/v1/config/profiles")

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "unconfigured"
        assert len(body["profiles"]) == 0

    def test_list_profiles_includes_custom(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Custom profiles appear in the list."""
        _seed_profile(settings_service, "reneryo")
        _seed_profile(settings_service, "sap-staging", "custom_rest")

        resp = client.get("/api/v1/config/profiles")

        body = resp.json()
        names = [p["name"] for p in body["profiles"]]
        assert "reneryo" in names
        assert "sap-staging" in names
        assert len(body["profiles"]) == 2

    def test_list_profiles_marks_active(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Active profile is marked correctly."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        resp = client.get("/api/v1/config/profiles")

        body = resp.json()
        assert body["active_profile"] == "reneryo"
        for p in body["profiles"]:
            expected = p["name"] == "reneryo"
            assert p["is_active"] is expected


# ══════════════════════════════════════════════════════════
# GET /api/v1/config/profiles/{name}
# ══════════════════════════════════════════════════════════


class TestGetProfile:
    """Tests for getting a single profile."""

    def test_get_mock_profile(self, client: TestClient) -> None:
        """Unconfigured profile returns 404 since it has no stored config."""
        resp = client.get("/api/v1/config/profiles/unconfigured")

        assert resp.status_code == 404

    def test_get_custom_profile_masked_key(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Custom profile returns masked API key."""
        _seed_profile(settings_service, "reneryo", api_key="super-secret-key")

        resp = client.get("/api/v1/config/profiles/reneryo")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "reneryo"
        assert body["api_key"].startswith("****")
        assert "super-secret" not in body["api_key"]
        assert body["is_builtin"] is False

    def test_get_profile_not_found(self, client: TestClient) -> None:
        """Nonexistent profile returns 404."""
        resp = client.get("/api/v1/config/profiles/nonexistent")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ══════════════════════════════════════════════════════════
# POST /api/v1/config/profiles
# ══════════════════════════════════════════════════════════


class TestCreateProfile:
    """Tests for creating profiles."""

    def test_create_profile_success(
        self,
        client: TestClient,
        reneryo_profile_payload: dict[str, Any],
    ) -> None:
        """Valid payload creates profile with 201."""
        resp = client.post(
            "/api/v1/config/profiles",
            json=reneryo_profile_payload,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "reneryo"
        assert body["platform_type"] == "reneryo"
        assert body["api_key"].startswith("****")
        assert body["is_builtin"] is False

    def test_create_profile_mock_name_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Creating profile named 'unconfigured' returns 400 (built-in guard)."""
        resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "unconfigured",
                "platform_type": "reneryo",
            },
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "Profile 'unconfigured' is built-in and cannot be created"
        )

    def test_create_profile_duplicate_returns_409(
        self,
        client: TestClient,
        settings_service: SettingsService,
        reneryo_profile_payload: dict[str, Any],
    ) -> None:
        """Duplicate profile name returns 409."""
        _seed_profile(settings_service, "reneryo")

        resp = client.post(
            "/api/v1/config/profiles",
            json=reneryo_profile_payload,
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_profile_invalid_name_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """Invalid profile name (uppercase, special chars) returns 422."""
        resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "BAD_NAME!!",
                "platform_type": "reneryo",
            },
        )

        assert resp.status_code == 422

    def test_create_profile_short_name_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """Single-character name violates 2-char minimum."""
        resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "x",
                "platform_type": "reneryo",
            },
        )

        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# PUT /api/v1/config/profiles/{name}
# ══════════════════════════════════════════════════════════


class TestUpdateProfile:
    """Tests for updating profiles."""

    def test_update_profile_success(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Updating an existing profile returns 200."""
        _seed_profile(settings_service, "reneryo")

        resp = client.put(
            "/api/v1/config/profiles/reneryo",
            json={
                "platform_type": "reneryo",
                "api_url": "https://new-api.example.com",
                "api_key": "new-key-5678",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["api_url"] == "https://new-api.example.com"
        assert body["api_key"].startswith("****")

    def test_update_mock_profile_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Cannot modify the built-in unconfigured profile (returns 404 since not stored)."""
        resp = client.put(
            "/api/v1/config/profiles/unconfigured",
            json={
                "platform_type": "reneryo",
            },
        )

        assert resp.status_code == 404

    def test_update_nonexistent_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """Updating a profile that doesn't exist returns 404."""
        resp = client.put(
            "/api/v1/config/profiles/nonexistent",
            json={
                "platform_type": "reneryo",
                "api_url": "https://api.example.com",
                "api_key": "key",
            },
        )

        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# DELETE /api/v1/config/profiles/{name}
# ══════════════════════════════════════════════════════════


class TestDeleteProfile:
    """Tests for deleting profiles."""

    def test_delete_profile_success(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Deleting an existing profile returns 200."""
        _seed_profile(settings_service, "reneryo")

        resp = client.delete("/api/v1/config/profiles/reneryo")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"
        assert body["deleted_profile"] == "reneryo"

    def test_delete_mock_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Cannot delete the unconfigured profile (returns 404 since not stored)."""
        resp = client.delete("/api/v1/config/profiles/unconfigured")

        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """Deleting a nonexistent profile returns 404."""
        resp = client.delete("/api/v1/config/profiles/nonexistent")

        assert resp.status_code == 404

    def test_delete_active_profile_resets_to_mock(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Deleting the active profile resets to unconfigured."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        resp = client.delete("/api/v1/config/profiles/reneryo")

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "unconfigured"
        assert "reset to unconfigured" in body["message"].lower()


# ══════════════════════════════════════════════════════════
# POST /api/v1/config/profiles/{name}/activate
# ══════════════════════════════════════════════════════════


class TestActivateProfile:
    """Tests for profile activation."""

    def test_activate_profile_success(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Activating an existing profile succeeds with voice_reloaded."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=True,
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "activated"
        assert body["active_profile"] == "reneryo"
        assert body["adapter_type"] == "reneryo"
        assert body["voice_reloaded"] is True

    def test_activate_mock_success(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Activating unconfigured profile works (resets to default)."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=True,
        ):
            resp = client.post(
                "/api/v1/config/profiles/unconfigured/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "unconfigured"
        assert body["adapter_type"] == "unconfigured"

    def test_activate_nonexistent_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """Activating a nonexistent profile returns 404."""
        resp = client.post(
            "/api/v1/config/profiles/nonexistent/activate",
        )

        assert resp.status_code == 404

    def test_activate_reload_failure_rolls_back_returns_422(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Reload failure rolls back to previous profile and returns 422."""
        _seed_profile(settings_service, "reneryo")
        assert settings_service.get_active_profile_name() == "unconfigured"

        with patch(
            "skill.adapters.factory.AdapterFactory.reload",
            new=AsyncMock(side_effect=RuntimeError("reload exploded")),
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 422
        assert "reload exploded" in resp.json()["detail"]
        assert "Rolled back" in resp.json()["detail"]
        assert settings_service.get_active_profile_name() == "unconfigured"


# ══════════════════════════════════════════════════════════
# Legacy /platform endpoint compatibility
# ══════════════════════════════════════════════════════════


class TestLegacyEndpoints:
    """Verify legacy /platform endpoints still work."""

    def test_legacy_get_platform_returns_200(
        self,
        client: TestClient,
    ) -> None:
        """GET /platform returns unconfigured config by default."""
        resp = client.get("/api/v1/config/platform")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "unconfigured"

    def test_legacy_post_platform_creates_config(
        self,
        client: TestClient,
    ) -> None:
        """POST /platform still creates/updates config."""
        resp = client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "reneryo",
                "api_url": "https://api.example.com/v1",
                "api_key": "key-1234",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "reneryo"

    def test_legacy_delete_platform_resets(
        self,
        client: TestClient,
    ) -> None:
        """DELETE /platform resets to unconfigured."""
        # First create a config
        client.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "reneryo",
                "api_url": "https://api.example.com/v1",
                "api_key": "key-1234",
            },
        )

        resp = client.delete("/api/v1/config/platform")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "unconfigured"


# ══════════════════════════════════════════════════════════
# _notify_skill_via_bus unit tests (DEC-029)
# ══════════════════════════════════════════════════════════


class TestNotifySkillViaBus:
    """Tests for the _notify_skill_via_bus helper."""

    def test_notify_skill_via_bus_success(self) -> None:
        """Successful send returns True with correct message format."""
        mock_ws = MagicMock()
        mock_websocket = MagicMock()
        mock_websocket.create_connection.return_value = mock_ws

        with patch(
            "routers.profiles.websocket",
            mock_websocket,
        ):
            from routers.profiles import _notify_skill_via_bus

            result = _notify_skill_via_bus("reneryo")

        assert result is True
        mock_websocket.create_connection.assert_called_once()

        # Verify sent message format
        import json

        sent = mock_ws.send.call_args[0][0]
        msg = json.loads(sent)
        assert msg["type"] == "avaros.profile.activated"
        assert msg["data"]["profile"] == "reneryo"
        assert "context" in msg
        mock_ws.close.assert_called_once()

    def test_notify_skill_via_bus_timeout_returns_false(self) -> None:
        """Connection failure returns False, never raises."""
        mock_websocket = MagicMock()
        mock_websocket.create_connection.side_effect = ConnectionRefusedError(
            "refused",
        )

        with patch(
            "routers.profiles.websocket",
            mock_websocket,
        ):
            from routers.profiles import _notify_skill_via_bus

            result = _notify_skill_via_bus("reneryo")

        assert result is False

    def test_activate_profile_response_includes_voice_reloaded(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Activation response always includes voice_reloaded field."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=False,
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "voice_reloaded" in body
        assert body["voice_reloaded"] is False


# ══════════════════════════════════════════════════════════
# Pre-Validation Tests (DEC-029 P5-L11)
# ══════════════════════════════════════════════════════════


class TestActivatePreValidation:
    """Pre-validation rejects bad profiles *before* state change."""

    def test_activate_nonexistent_profile_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """Profile that doesn't exist → 404 (pre-validation)."""
        resp = client.post(
            "/api/v1/config/profiles/does-not-exist/activate",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_activate_unsupported_platform_returns_422(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Profile with unknown platform_type → 422."""
        _seed_profile(
            settings_service, "bad-plat",
            platform_type="quantum_computer",
        )

        resp = client.post(
            "/api/v1/config/profiles/bad-plat/activate",
        )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "not supported" in detail.lower()
        assert "quantum_computer" in detail
        # Active profile unchanged
        assert settings_service.get_active_profile_name() == "unconfigured"

    def test_activate_reneryo_missing_url_returns_422(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """RENERYO profile without api_url → 422."""
        _seed_profile(
            settings_service, "ren-broken",
            platform_type="reneryo",
            api_url="",
        )

        resp = client.post(
            "/api/v1/config/profiles/ren-broken/activate",
        )

        assert resp.status_code == 422
        assert "api_url" in resp.json()["detail"].lower()
        assert settings_service.get_active_profile_name() == "unconfigured"

    def test_activate_unconfigured_always_succeeds(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Unconfigured profile requires no validation — always activates."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=True,
        ):
            resp = client.post(
                "/api/v1/config/profiles/unconfigured/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "unconfigured"
        assert body["status"] == "activated"


# ══════════════════════════════════════════════════════════
# Rollback Tests (DEC-029 P5-L11)
# ══════════════════════════════════════════════════════════


class TestActivateRollback:
    """On adapter failure the system rolls back to previous profile."""

    def test_rollback_on_adapter_failure(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """factory.reload() raises → old profile restored, 422 returned."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "skill.adapters.factory.AdapterFactory.reload",
            new=AsyncMock(
                side_effect=ConnectionError("cannot connect"),
            ),
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "cannot connect" in detail.lower()
        assert "Rolled back" in detail
        assert settings_service.get_active_profile_name() == "unconfigured"

    def test_rollback_on_initialize_failure(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Initialize failure via reload() path restores old profile."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "skill.adapters.factory.AdapterFactory.reload",
            new=AsyncMock(side_effect=RuntimeError("init boom")),
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "init boom" in detail
        assert "Rolled back" in detail
        assert settings_service.get_active_profile_name() == "unconfigured"

    def test_rollback_failure_logged_still_returns_422(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Both activation and rollback fail → 422 returned, error logged."""
        _seed_profile(settings_service, "reneryo")
        call_count = 0

        async def _reload_side_effects() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("primary failure")
            raise RuntimeError("rollback failure")

        with patch(
            "skill.adapters.factory.AdapterFactory.reload",
            new=AsyncMock(side_effect=_reload_side_effects),
        ), patch(
            "routers.profiles.logger",
        ) as mock_logger:
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 422
        assert "primary failure" in resp.json()["detail"]
        # Verify rollback failure was logged
        error_calls = [
            str(c) for c in mock_logger.error.call_args_list
        ]
        assert any("rollback" in c.lower() for c in error_calls)

    def test_success_returns_voice_reloaded_field(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Successful activation includes voice_reloaded in response."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=True,
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["voice_reloaded"] is True
        assert body["status"] == "activated"
        assert body["active_profile"] == "reneryo"

    def test_full_activation_unconfigured_to_unconfigured(
        self,
        client: TestClient,
    ) -> None:
        """Trivial switch from unconfigured to unconfigured always works."""
        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=True,
        ):
            resp = client.post(
                "/api/v1/config/profiles/unconfigured/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "unconfigured"
        assert body["adapter_type"] == "unconfigured"

    def test_notification_failure_does_not_rollback(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Message bus failure → voice_reloaded=false, activation succeeds."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "routers.profiles._notify_skill_via_bus",
            return_value=False,
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["voice_reloaded"] is False
        assert body["active_profile"] == "reneryo"
        assert settings_service.get_active_profile_name() == "reneryo"
