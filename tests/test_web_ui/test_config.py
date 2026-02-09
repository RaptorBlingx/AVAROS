"""
Tests for platform configuration CRUD endpoints.

Covers:
    - POST /api/v1/config/platform  — create/update
    - GET  /api/v1/config/platform  — read (masked key)
    - DELETE /api/v1/config/platform — reset
    - POST /api/v1/config/platform/test — connection test stub
    - Validation: invalid URL, missing required fields
    - API key masking logic
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

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
    """Tests for the stub platform connection test endpoint."""

    def test_mock_platform_test_succeeds(
        self,
        client: TestClient,
        valid_mock_payload: dict[str, Any],
    ) -> None:
        """Mock platform connection test returns success=True."""
        response = client.post(
            "/api/v1/config/platform/test",
            json=valid_mock_payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "mock" in body["message"].lower()

    def test_non_mock_platform_test_not_implemented(
        self,
        client: TestClient,
        valid_reneryo_payload: dict[str, Any],
    ) -> None:
        """Non-mock platform connection test returns success=False."""
        response = client.post(
            "/api/v1/config/platform/test",
            json=valid_reneryo_payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "not implemented" in body["message"].lower()


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
