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
from unittest.mock import AsyncMock, patch

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
        """Empty DB returns only the built-in mock profile."""
        resp = client.get("/api/v1/config/profiles")

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "mock"
        assert len(body["profiles"]) == 1
        assert body["profiles"][0]["name"] == "mock"
        assert body["profiles"][0]["is_builtin"] is True
        assert body["profiles"][0]["is_active"] is True

    def test_list_profiles_includes_custom(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Custom profiles appear after mock in the list."""
        _seed_profile(settings_service, "reneryo")
        _seed_profile(settings_service, "sap-staging", "custom_rest")

        resp = client.get("/api/v1/config/profiles")

        body = resp.json()
        names = [p["name"] for p in body["profiles"]]
        assert names[0] == "mock"
        assert "reneryo" in names
        assert "sap-staging" in names
        assert len(body["profiles"]) == 3

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
        """Mock profile returns default config."""
        resp = client.get("/api/v1/config/profiles/mock")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "mock"
        assert body["platform_type"] == "mock"
        assert body["is_builtin"] is True
        assert body["api_url"] == ""
        assert body["api_key"] == "****"

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
        """Creating profile named 'mock' returns 400 (built-in guard)."""
        resp = client.post(
            "/api/v1/config/profiles",
            json={
                "name": "mock",
                "platform_type": "mock",
            },
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "Profile 'mock' is built-in and cannot be created"
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
        """Cannot modify the built-in mock profile."""
        resp = client.put(
            "/api/v1/config/profiles/mock",
            json={
                "platform_type": "mock",
            },
        )

        assert resp.status_code == 400
        assert "mock" in resp.json()["detail"].lower()

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
        """Cannot delete the built-in mock profile."""
        resp = client.delete("/api/v1/config/profiles/mock")

        assert resp.status_code == 400
        assert "mock" in resp.json()["detail"].lower()

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
        """Deleting the active profile resets to mock."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        resp = client.delete("/api/v1/config/profiles/reneryo")

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "mock"
        assert "reset to mock" in body["message"].lower()


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
        """Activating an existing profile succeeds."""
        _seed_profile(settings_service, "reneryo")

        resp = client.post(
            "/api/v1/config/profiles/reneryo/activate",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "activated"
        assert body["active_profile"] == "reneryo"
        assert body["adapter_type"] == "reneryo"

    def test_activate_mock_success(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Activating mock profile works (resets to default)."""
        _seed_profile(settings_service, "reneryo")
        settings_service.set_active_profile("reneryo")

        resp = client.post(
            "/api/v1/config/profiles/mock/activate",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["active_profile"] == "mock"
        assert body["adapter_type"] == "mock"

    def test_activate_nonexistent_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """Activating a nonexistent profile returns 404."""
        resp = client.post(
            "/api/v1/config/profiles/nonexistent/activate",
        )

        assert resp.status_code == 404

    def test_activate_profile_reload_failure_returns_500(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Reload errors return 500 and keep active profile switched."""
        _seed_profile(settings_service, "reneryo")

        with patch(
            "skill.adapters.factory.AdapterFactory.reload",
            new=AsyncMock(side_effect=RuntimeError("reload exploded")),
        ):
            resp = client.post(
                "/api/v1/config/profiles/reneryo/activate",
            )

        assert resp.status_code == 500
        assert "Adapter reload failed" in resp.json()["detail"]
        assert settings_service.get_active_profile_name() == "reneryo"


# ══════════════════════════════════════════════════════════
# Legacy /platform endpoint compatibility
# ══════════════════════════════════════════════════════════


class TestLegacyEndpoints:
    """Verify legacy /platform endpoints still work."""

    def test_legacy_get_platform_returns_200(
        self,
        client: TestClient,
    ) -> None:
        """GET /platform returns mock config by default."""
        resp = client.get("/api/v1/config/platform")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "mock"

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
        """DELETE /platform resets to mock."""
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
        assert resp.json()["platform_type"] == "mock"
