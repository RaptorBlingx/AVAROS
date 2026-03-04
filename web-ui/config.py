"""Web UI backend configuration."""

from __future__ import annotations

import logging
import os
import secrets

logger = logging.getLogger("uvicorn.error")

APP_VERSION = "0.1.0"
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

