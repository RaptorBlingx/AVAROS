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
import routers.voice as voice_router  # noqa: E402


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
        """Default HiveMind URL follows the current Web UI origin."""
        settings_service.delete_setting(SettingsService.VOICE_WS_URL_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_NAME)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_SECRET)

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "ws://testserver/hivemind/"

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

    def test_hides_encryption_key_when_browser_encryption_is_disabled(
        self,
        client: TestClient,
        settings_service: SettingsService,
        monkeypatch,
    ) -> None:
        """LAN HTTP mode does not require browser Web Crypto."""
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_CRYPTO_KEY)
        settings_service.delete_setting(SettingsService.VOICE_CLIENT_SECRET)
        monkeypatch.setenv("HIVEMIND_CLIENT_CRYPTO_KEY", "0123456789abcdef")
        monkeypatch.setenv("HIVEMIND_CLIENT_SECRET", "legacy-secret-xyz")
        monkeypatch.setenv("HIVEMIND_BROWSER_ENCRYPTION_ENABLED", "false")

        response = client.get("/api/v1/voice/config")

        assert response.status_code == 200
        assert response.json()["hivemind_secret"] == ""


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

    def test_auto_url_uses_request_origin(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """auto mode returns a public same-origin HiveMind URL."""
        settings_service.update_voice_config(VoiceConfig(hivemind_url="auto"))
        response = client.get(
            "/api/v1/voice/config",
            headers={
                "Host": "avaros.reneryo.com",
                "X-Forwarded-Proto": "https",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "wss://avaros.reneryo.com/hivemind/"

    def test_auto_url_uses_same_origin_for_local_compose(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Local Web UI proxies HiveMind on the current browser origin."""
        settings_service.update_voice_config(VoiceConfig(hivemind_url="auto"))
        response = client.get(
            "/api/v1/voice/config",
            headers={"Host": "localhost:8080"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "ws://localhost:8080/hivemind/"

    def test_auto_url_tracks_custom_web_port(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Changing AVAROS_WEB_PORT requires no HiveMind URL override."""
        settings_service.update_voice_config(VoiceConfig(hivemind_url="auto"))
        response = client.get(
            "/api/v1/voice/config",
            headers={"Host": "localhost:9090"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hivemind_url"] == "ws://localhost:9090/hivemind/"

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


class TestVoiceTTS:
    """Verify server-backed TTS endpoints."""

    def test_tts_endpoint_requires_api_key(
        self, client_no_auth: TestClient
    ) -> None:
        response = client_no_auth.post(
            "/api/v1/voice/tts",
            json={"text": "Hello from AVAROS"},
        )
        assert response.status_code == 401

    def test_tts_endpoint_returns_wav(
        self, client: TestClient, monkeypatch
    ) -> None:
        def fake_run(command, **_kwargs):
            wav_path = Path(command[command.index("-w") + 1])
            wav_path.write_bytes(b"RIFF----WAVEfmt ")

        monkeypatch.setattr(voice_router.shutil, "which", lambda _name: "/usr/bin/espeak-ng")
        monkeypatch.setattr(voice_router.subprocess, "run", fake_run)

        response = client.post(
            "/api/v1/voice/tts",
            json={"text": "Hello from AVAROS", "rate": 1.1},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content.startswith(b"RIFF")

    def test_tts_endpoint_prefers_piper_when_model_available(
        self, client: TestClient, monkeypatch, tmp_path: Path
    ) -> None:
        model_path = tmp_path / "voice.onnx"
        config_path = tmp_path / "voice.onnx.json"
        model_path.write_bytes(b"model")
        config_path.write_text("{}", encoding="utf-8")
        commands: list[list[str]] = []

        def fake_which(name: str) -> str | None:
            if name == "piper":
                return "/usr/bin/piper"
            if name == "espeak-ng":
                return "/usr/bin/espeak-ng"
            return None

        def fake_run(command, **_kwargs):
            commands.append(command)
            wav_path = Path(command[command.index("-f") + 1])
            wav_path.write_bytes(b"RIFF----WAVEfmt ")

        monkeypatch.setattr(voice_router, "PIPER_MODEL_PATH", str(model_path))
        monkeypatch.setattr(voice_router, "PIPER_CONFIG_PATH", str(config_path))
        monkeypatch.setattr(voice_router, "SERVER_TTS_ENGINE", "auto")
        monkeypatch.setattr(voice_router.shutil, "which", fake_which)
        monkeypatch.setattr(voice_router.subprocess, "run", fake_run)

        response = client.post(
            "/api/v1/voice/tts",
            json={"text": "Hello from AVAROS", "rate": 1.1},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content.startswith(b"RIFF")
        assert commands[0][0] == "/usr/bin/piper"

    def test_public_tts_endpoint_accepts_plain_text(
        self, client_no_auth: TestClient, monkeypatch
    ) -> None:
        def fake_run(command, **_kwargs):
            wav_path = Path(command[command.index("-w") + 1])
            wav_path.write_bytes(b"RIFF----WAVEfmt ")

        monkeypatch.setattr(voice_router.shutil, "which", lambda _name: "/usr/bin/espeak-ng")
        monkeypatch.setattr(voice_router.subprocess, "run", fake_run)

        response = client_no_auth.post(
            "/voice/tts",
            content="Hello from the embedded widget",
            headers={"Content-Type": "text/plain;charset=utf-8"},
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert response.headers["content-type"] == "audio/wav"

    def test_public_tts_preflight_allows_widget_origin(
        self, client_no_auth: TestClient
    ) -> None:
        response = client_no_auth.options(
            "/voice/tts",
            headers={
                "Origin": "https://preview.example.test",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == "*"
        assert "POST" in response.headers["access-control-allow-methods"]


class TestVoicePreferences:
    """Verify shared voice mode preferences for UI and embeds."""

    def test_get_preferences_returns_saved_mode(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        settings_service.set_setting("voice_mode", "wake-word")

        response = client.get("/api/v1/voice/preferences")

        assert response.status_code == 200
        assert response.json() == {"voice_mode": "wake-word"}

    def test_put_preferences_persists_mode(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        response = client.put(
            "/api/v1/voice/preferences",
            json={"voice_mode": "push-to-talk"},
        )

        assert response.status_code == 200
        assert response.json() == {"voice_mode": "push-to-talk"}
        assert settings_service.get_setting("voice_mode") == "push-to-talk"

    def test_put_preferences_rejects_unknown_mode(
        self,
        client: TestClient,
    ) -> None:
        response = client.put(
            "/api/v1/voice/preferences",
            json={"voice_mode": "always-on"},
        )

        assert response.status_code == 422

    def test_public_preferences_returns_saved_mode_with_cors(
        self,
        client_no_auth: TestClient,
        settings_service: SettingsService,
    ) -> None:
        settings_service.set_setting("voice_mode", "wake-word")

        response = client_no_auth.get(
            "/voice/preferences",
            headers={"Origin": "https://preview.example.test"},
        )

        assert response.status_code == 200
        assert response.json() == {"voice_mode": "wake-word"}
        assert response.headers["access-control-allow-origin"] == "*"

    def test_public_preferences_preflight_allows_widget_origin(
        self,
        client_no_auth: TestClient,
    ) -> None:
        response = client_no_auth.options(
            "/voice/preferences",
            headers={
                "Origin": "https://preview.example.test",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == "*"
        assert "GET" in response.headers["access-control-allow-methods"]
