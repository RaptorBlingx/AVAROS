"""Web UI backend configuration."""

from __future__ import annotations

import os


APP_VERSION = "0.1.0"
APP_HOST = "0.0.0.0"
APP_PORT = int(os.environ.get("AVAROS_WEB_UI_PORT", "8080"))
DATABASE_URL = os.environ.get("AVAROS_DATABASE_URL", "")

# Keep explicit dev origins while also allowing localhost:* via regex in main.py.
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
]

