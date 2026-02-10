"""
Tests for API-key authentication middleware.

Covers:
    - Requests without API key to /api/v1/ endpoints return 401
    - Requests with invalid API key return 401
    - Requests with valid API key return 200
    - GET /health bypasses auth (liveness check)
    - SPA / root path bypasses auth
    - Default API key generation (config module)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure web-ui is importable.
_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from config import WEB_API_KEY as TEST_API_KEY  # noqa: E402


# ══════════════════════════════════════════════════════════
# Auth bypass — /health stays public
# ══════════════════════════════════════════════════════════


class TestHealthBypassesAuth:
    """GET /health must be accessible without any API key."""

    def test_health_no_key_returns_200(
        self, client_no_auth: TestClient
    ) -> None:
        """GET /health without X-API-Key header returns 200."""
        response = client_no_auth.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_with_key_still_works(self, client: TestClient) -> None:
        """GET /health with API key header also returns 200."""
        response = client.get("/health")

        assert response.status_code == 200


# ══════════════════════════════════════════════════════════
# Auth rejection — missing / invalid key
# ══════════════════════════════════════════════════════════


class TestAuthRejection:
    """Requests to /api/v1/ without a valid key are rejected with 401."""

    def test_status_no_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """GET /api/v1/status without key returns 401."""
        response = client_no_auth.get("/api/v1/status")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or missing API key"

    def test_config_no_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """GET /api/v1/config/platform without key returns 401."""
        response = client_no_auth.get("/api/v1/config/platform")

        assert response.status_code == 401

    def test_intents_no_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """GET /api/v1/config/intents without key returns 401."""
        response = client_no_auth.get("/api/v1/config/intents")

        assert response.status_code == 401

    def test_metrics_no_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """GET /api/v1/config/metrics without key returns 401."""
        response = client_no_auth.get("/api/v1/config/metrics")

        assert response.status_code == 401

    def test_invalid_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """Request with wrong key value returns 401."""
        response = client_no_auth.get(
            "/api/v1/status",
            headers={"X-API-Key": "wrong-key-value"},
        )

        assert response.status_code == 401

    def test_post_config_no_key_returns_401(
        self, client_no_auth: TestClient
    ) -> None:
        """POST /api/v1/config/platform without key returns 401."""
        response = client_no_auth.post(
            "/api/v1/config/platform",
            json={
                "platform_type": "mock",
                "api_url": "",
                "api_key": "",
                "extra_settings": {},
            },
        )

        assert response.status_code == 401


# ══════════════════════════════════════════════════════════
# Auth success — valid key grants access
# ══════════════════════════════════════════════════════════


class TestAuthSuccess:
    """Requests to /api/v1/ with the correct key succeed."""

    def test_status_with_key_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/status with valid key returns 200."""
        response = client.get("/api/v1/status")

        assert response.status_code == 200

    def test_config_get_with_key_returns_200(
        self, client: TestClient
    ) -> None:
        """GET /api/v1/config/platform with valid key returns 200."""
        response = client.get("/api/v1/config/platform")

        assert response.status_code == 200

    def test_intents_with_key_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/config/intents with valid key returns 200."""
        response = client.get("/api/v1/config/intents")

        assert response.status_code == 200

    def test_metrics_with_key_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/config/metrics with valid key returns 200."""
        response = client.get("/api/v1/config/metrics")

        assert response.status_code == 200

    def test_explicit_header_also_works(
        self, client_no_auth: TestClient
    ) -> None:
        """Passing key via explicit header (not default) also works."""
        response = client_no_auth.get(
            "/api/v1/status",
            headers={"X-API-Key": TEST_API_KEY},
        )

        assert response.status_code == 200


# ══════════════════════════════════════════════════════════
# SPA bypass — static paths skip auth
# ══════════════════════════════════════════════════════════


class TestSpaBypassesAuth:
    """Non-API paths (SPA, docs) are not gated by the middleware."""

    def test_root_no_key_not_401(self, client_no_auth: TestClient) -> None:
        """GET / without key does NOT return 401.

        It may return 404 (no frontend build) or 200, but not 401.
        """
        response = client_no_auth.get("/")

        assert response.status_code != 401

    def test_docs_no_key_not_401(self, client_no_auth: TestClient) -> None:
        """GET /docs without key does NOT return 401."""
        response = client_no_auth.get("/docs")

        assert response.status_code != 401


# ══════════════════════════════════════════════════════════
# Default key generation
# ══════════════════════════════════════════════════════════


class TestDefaultKeyGeneration:
    """Config module generates a key when env var is not set."""

    def test_api_key_is_nonempty_string(self) -> None:
        """The resolved API key is always a non-empty string."""
        assert isinstance(TEST_API_KEY, str)
        assert len(TEST_API_KEY) > 0

    def test_api_key_has_sufficient_length(self) -> None:
        """Generated key has at least 32 hex characters (16 bytes)."""
        assert len(TEST_API_KEY) >= 32
