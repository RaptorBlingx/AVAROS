"""
Tests for voice configuration endpoint.

Covers:
    - GET /api/v1/voice/config — default values (no env vars)
    - GET /api/v1/voice/config — configured values (env vars set)
    - GET /api/v1/voice/config — requires API key authentication
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure web-ui is importable
_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from config import WEB_API_KEY as TEST_API_KEY  # noqa: E402


# ══════════════════════════════════════════════════════════
# GET /api/v1/voice/config
# ══════════════════════════════════════════════════════════


class TestGetVoiceConfigDefaults:
    """Verify defaults when no HiveMind env vars are set."""

    def test_returns_default_url(self, client: TestClient) -> None:
        """Default hivemind_url is ws://localhost:5678."""
        with patch.dict(
            "os.environ",
            {},
            clear=False,
        ):
            # Remove keys if present
            import os

            os.environ.pop("HIVEMIND_WS_URL", None)
            os.environ.pop("HIVEMIND_CLIENT_KEY", None)
            os.environ.pop("HIVEMIND_CLIENT_SECRET", None)

            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "ws://localhost:5678"

    def test_returns_empty_key_when_not_set(
        self, client: TestClient
    ) -> None:
        """hivemind_key is empty when HIVEMIND_CLIENT_KEY is not set."""
        import os

        os.environ.pop("HIVEMIND_CLIENT_KEY", None)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_key"] == ""

    def test_voice_disabled_without_key(
        self, client: TestClient
    ) -> None:
        """voice_enabled is False when HIVEMIND_CLIENT_KEY is absent."""
        import os

        os.environ.pop("HIVEMIND_CLIENT_KEY", None)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["voice_enabled"] is False

    def test_returns_empty_secret_when_not_set(
        self, client: TestClient
    ) -> None:
        """hivemind_secret is empty when HIVEMIND_CLIENT_SECRET is absent."""
        import os

        os.environ.pop("HIVEMIND_CLIENT_SECRET", None)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_secret"] == ""


class TestGetVoiceConfigFromEnv:
    """Verify config is populated from environment variables."""

    def test_returns_configured_url(self, client: TestClient) -> None:
        """hivemind_url reflects HIVEMIND_WS_URL env var."""
        with patch.dict(
            "os.environ",
            {"HIVEMIND_WS_URL": "wss://prod.example.com/hivemind"},
        ):
            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "wss://prod.example.com/hivemind"

    def test_returns_configured_key(self, client: TestClient) -> None:
        """hivemind_key reflects HIVEMIND_CLIENT_KEY env var."""
        with patch.dict(
            "os.environ",
            {"HIVEMIND_CLIENT_KEY": "test-access-key-123"},
        ):
            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_key"] == "test-access-key-123"

    def test_returns_configured_secret(
        self, client: TestClient
    ) -> None:
        """hivemind_secret reflects HIVEMIND_CLIENT_SECRET env var."""
        with patch.dict(
            "os.environ",
            {"HIVEMIND_CLIENT_SECRET": "super-secret-456"},
        ):
            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_secret"] == "super-secret-456"

    def test_voice_enabled_when_key_set(
        self, client: TestClient
    ) -> None:
        """voice_enabled is True when HIVEMIND_CLIENT_KEY has a value."""
        with patch.dict(
            "os.environ",
            {"HIVEMIND_CLIENT_KEY": "any-key"},
        ):
            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["voice_enabled"] is True

    def test_full_config_response_structure(
        self, client: TestClient
    ) -> None:
        """Response contains all expected fields."""
        with patch.dict(
            "os.environ",
            {
                "HIVEMIND_WS_URL": "ws://hivemind:5678",
                "HIVEMIND_CLIENT_KEY": "key-abc",
                "HIVEMIND_CLIENT_SECRET": "secret-xyz",
            },
        ):
            response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {
            "hivemind_url",
            "hivemind_key",
            "hivemind_secret",
            "voice_enabled",
        }
        assert data["hivemind_url"] == "ws://hivemind:5678"
        assert data["hivemind_key"] == "key-abc"
        assert data["hivemind_secret"] == "secret-xyz"
        assert data["voice_enabled"] is True


class TestVoiceConfigAuth:
    """Verify authentication is enforced on voice config endpoint."""

    def test_voice_config_requires_api_key(
        self, client_no_auth: TestClient
    ) -> None:
        """Request without API key returns 401."""
        response = client_no_auth.get("/api/v1/voice/config")
        assert response.status_code == 401

    def test_voice_config_rejects_invalid_key(
        self, client_no_auth: TestClient
    ) -> None:
        """Request with wrong API key returns 401."""
        response = client_no_auth.get(
            "/api/v1/voice/config",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_voice_config_accepts_valid_key(
        self, client_no_auth: TestClient
    ) -> None:
        """Request with correct API key returns 200."""
        response = client_no_auth.get(
            "/api/v1/voice/config",
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.status_code == 200
