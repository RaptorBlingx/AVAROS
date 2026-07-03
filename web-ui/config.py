"""Web UI backend configuration."""

from __future__ import annotations

import logging
import os
import secrets

logger = logging.getLogger("uvicorn.error")

APP_VERSION = "0.1.1"
APP_HOST = "0.0.0.0"
APP_PORT = int(os.environ.get("AVAROS_WEB_UI_PORT", "8080"))
DATABASE_URL = os.environ.get("AVAROS_DATABASE_URL", "")

# Keep explicit dev origins while also allowing localhost:* via regex in main.py.
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8081",  # Production port (changed from 8080 due to Keycloak conflict)
    "http://localhost:5173",  # Vite dev server
]


def _resolve_api_key() -> str:
    """Return API key from env or generate a secure default.

    When no ``AVAROS_WEB_API_KEY`` is set, a 32-byte hex token is
    generated and only a masked preview is logged.
    """
    key = os.environ.get("AVAROS_WEB_API_KEY", "")
    if key:
        return key
    generated = secrets.token_hex(32)
    logger.warning(
        "AVAROS_WEB_API_KEY not set — generated default key: %s...%s",
        generated[:4],
        generated[-4:],
    )
    return generated


WEB_API_KEY: str = _resolve_api_key()

SERVER_TTS_ENABLED = os.environ.get("AVAROS_SERVER_TTS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SERVER_TTS_MAX_CHARS = int(os.environ.get("AVAROS_SERVER_TTS_MAX_CHARS", "500"))
SERVER_TTS_TIMEOUT_SECONDS = float(
    os.environ.get("AVAROS_SERVER_TTS_TIMEOUT_SECONDS", "10")
)
SERVER_TTS_ENGINE = os.environ.get("AVAROS_SERVER_TTS_ENGINE", "auto").strip().lower()
PIPER_MODEL_PATH = os.environ.get(
    "AVAROS_PIPER_MODEL_PATH",
    "/opt/avaros/tts/piper/en_US-lessac-medium.onnx",
)
PIPER_CONFIG_PATH = os.environ.get(
    "AVAROS_PIPER_CONFIG_PATH",
    "/opt/avaros/tts/piper/en_US-lessac-medium.onnx.json",
)
PIPER_LENGTH_SCALE = float(os.environ.get("AVAROS_PIPER_LENGTH_SCALE", "1.0"))
PIPER_NOISE_SCALE = float(os.environ.get("AVAROS_PIPER_NOISE_SCALE", "0.667"))
PIPER_NOISE_W_SCALE = float(os.environ.get("AVAROS_PIPER_NOISE_W_SCALE", "0.8"))
