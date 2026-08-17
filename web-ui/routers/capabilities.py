"""Read-only active DIA capability manifest API."""

from __future__ import annotations

from dependencies import get_settings_service
from fastapi import APIRouter, Depends

from skill.services.capability_manifest import build_capability_manifest
from skill.services.settings import SettingsService

router = APIRouter(prefix="/api/v1", tags=["capabilities"])


@router.get("/capabilities")
def get_capabilities(
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    """Return active metrics and only currently available operations."""
    return build_capability_manifest(settings_service)
