"""PREVENTION analytics status API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from dependencies import get_settings_service
from schemas.prevention import PreventionStatusResponse
from skill.services.settings import SettingsService

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["prevention"])


@router.get("/prevention/status", response_model=PreventionStatusResponse)
def get_prevention_status(
    settings_service: SettingsService = Depends(get_settings_service),
) -> PreventionStatusResponse:
    """Return PREVENTION integration configuration status."""
    try:
        settings_service.initialize()
        config = settings_service.get_prevention_config()
        return PreventionStatusResponse(
            enabled=config["enabled"],
            prevention_url=config["prevention_url"],
            addon_name=config["addon_name"],
        )
    except Exception as exc:
        logger.exception("Failed to load PREVENTION status: %s", exc)
        return PreventionStatusResponse(
            enabled=False,
            prevention_url="",
            addon_name="avaros",
        )
