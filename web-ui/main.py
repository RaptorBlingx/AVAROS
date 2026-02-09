"""FastAPI entry point for AVAROS Web UI backend."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import APP_VERSION, CORS_ORIGINS, DATABASE_URL
from skill.services.settings import SettingsService


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="AVAROS Web UI", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^http://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_check() -> None:
    """Validate shared skill imports and DB-backed settings init path."""
    settings_service = SettingsService()
    settings_service.initialize()
    logger.info(
        "SettingsService import successful: %s (db_url_set=%s)",
        settings_service.__class__.__name__,
        bool(DATABASE_URL),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint for local and container health checks."""
    return {"status": "ok", "version": APP_VERSION}
