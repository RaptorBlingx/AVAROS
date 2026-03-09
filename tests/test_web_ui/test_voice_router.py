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
from fastapi.testclient import TestClient

# Ensure web-ui is importable
_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from config import WEB_API_KEY as TEST_API_KEY  # noqa: E402
from skill.services.settings import SettingsService, VoiceConfig  # noqa: E402


# ══════════════════════════════════════════════════════════
# GET /api/v1/voice/config
# ══════════════════════════════════════════════════════════


class TestGetVoiceConfigDefaults:
    """Verify defaults when no explicit voice settings are saved."""

    def test_returns_default_url(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Default hivemind_url is ws://localhost:5678."""
        settings_service.delete_setting(SettingsService.VOICE_WS_URL_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_NAME)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_SECRET)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "ws://localhost:5678"

    def test_returns_default_name(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Default hivemind_name is avaros-web-client."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_NAME)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_name"] == "avaros-web-client"

    def test_returns_empty_key_when_not_set(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_key is empty when no key is configured."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_KEY)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_key"] == ""

    def test_voice_disabled_without_key(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """voice_enabled is False when no key is configured."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_KEY)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["voice_enabled"] is False

    def test_returns_empty_secret_when_not_set(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_secret is empty when no secret is configured."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_SECRET)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_secret"] == ""

    def test_prefers_crypto_key_over_legacy_secret(
        self,
        client: TestClient,
        settings_service: SettingsService,
        monkeypatch,
    ) -> None:
        """hivemind_secret prefers crypto key when both env values exist."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_CRYPTO_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_SECRET)
        monkeypatch.setenv("HIVEMIND_CLIENT_CRYPTO_KEY", "crypto-key-123")
        monkeypatch.setenv("HIVEMIND_CLIENT_SECRET", "legacy-secret-xyz")

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_secret"] == "crypto-key-123"


class TestGetVoiceConfigFromSettings:
    """Verify config is populated from SettingsService persistence."""

    def test_returns_configured_url(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_url is normalized for HiveMind websocket auth parsing."""
        settings_service.update_voice_config(
            VoiceConfig(hivemind_url="wss://prod.example.com/hivemind")
        )
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "wss://prod.example.com/hivemind/"

    def test_returns_configured_key(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_key reflects stored SettingsService value."""
        settings_service.update_voice_config(
            VoiceConfig(hivemind_key="test-access-key-123")
        )
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_key"] == "test-access-key-123"

    def test_returns_configured_name(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_name reflects stored SettingsService value."""
        settings_service.update_voice_config(
            VoiceConfig(hivemind_name="custom-web-client")
        )
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_name"] == "custom-web-client"

    def test_returns_configured_secret(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """hivemind_secret reflects stored SettingsService value."""
        settings_service.update_voice_config(
            VoiceConfig(hivemind_secret="super-secret-456")
        )
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_secret"] == "super-secret-456"

    def test_voice_enabled_when_key_set(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """voice_enabled is True when key has a value."""
        settings_service.update_voice_config(VoiceConfig(hivemind_key="any-key"))
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["voice_enabled"] is True

    def test_full_config_response_structure(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Response contains all expected fields."""
        settings_service.update_voice_config(
            VoiceConfig(
                hivemind_url="ws://hivemind:5678",
                hivemind_name="voice-client-01",
                hivemind_key="key-abc",
                hivemind_secret="secret-xyz",
            )
        )
        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {
            "hivemind_url",
            "hivemind_name",
            "hivemind_key",
            "hivemind_secret",
            "voice_enabled",
        }
        assert data["hivemind_url"] == "ws://hivemind:5678"
        assert data["hivemind_name"] == "voice-client-01"
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
