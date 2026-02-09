"""System status API router."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from config import APP_VERSION
from dependencies import get_settings_service
from schemas.status import SystemStatusResponse
from skill.services.settings import SettingsService


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["status"])


def _intent_count() -> int:
    """Count intent files from mounted skill path or local fallback path."""
    mounted_locale_dir = Path("/opt/avaros/skill/locale/en-us")
    fallback_locale_dir = (
        Path(__file__).resolve().parents[2] / "skill" / "locale" / "en-us"
    )
    locale_dir = mounted_locale_dir if mounted_locale_dir.exists() else fallback_locale_dir
    return sum(1 for _ in locale_dir.glob("*.intent"))


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(
    settings_service: SettingsService = Depends(get_settings_service),
) -> SystemStatusResponse:
    """Return current AVAROS configuration and readiness status."""
    loaded_intents = _intent_count()

    defaults = SystemStatusResponse(
        configured=False,
        active_adapter="mock",
        platform_type="mock",
        loaded_intents=loaded_intents,
        database_connected=False,
        version=APP_VERSION,
    )

    try:
        settings_service.initialize()
        platform_config = settings_service.get_platform_config()
        return SystemStatusResponse(
            configured=settings_service.is_configured(),
            active_adapter=platform_config.platform_type or "mock",
            platform_type=platform_config.platform_type or "mock",
            loaded_intents=loaded_intents,
            database_connected=True,
            version=APP_VERSION,
        )
    except Exception as exc:
        logger.exception("Failed to load system status: %s", exc)
        return defaults

