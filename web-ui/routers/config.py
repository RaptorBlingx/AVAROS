"""Platform configuration CRUD APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import get_settings_service
from schemas.config import (
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    ResetResponse,
)
from skill.services.settings import PlatformConfig, SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _mask_api_key(api_key: str) -> str:
    """Mask key as ****XXXX; for short keys return ****."""
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"


def _to_response(config: PlatformConfig) -> PlatformConfigResponse:
    """Convert service config into API-safe masked response."""
    return PlatformConfigResponse(
        platform_type=config.platform_type,
        api_url=config.api_url,
        api_key=_mask_api_key(config.api_key),
        extra_settings=config.extra_settings,
    )


@router.post("/platform", response_model=PlatformConfigResponse)
def upsert_platform_config(
    payload: PlatformConfigRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> PlatformConfigResponse:
    """Create or update platform configuration."""
    config = PlatformConfig(
        platform_type=payload.platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=payload.extra_settings,
    )
    settings_service.update_platform_config(config)
    return _to_response(settings_service.get_platform_config())


@router.get("/platform", response_model=PlatformConfigResponse)
def get_platform_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> PlatformConfigResponse:
    """Return current platform configuration with masked API key."""
    return _to_response(settings_service.get_platform_config())


@router.delete("/platform", response_model=ResetResponse)
def reset_platform_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> ResetResponse:
    """Reset configuration by deleting saved platform config."""
    settings_service.delete_setting("platform_config")
    return ResetResponse(status="reset", platform_type="mock")


@router.post("/platform/test", response_model=ConnectionTestResponse)
def test_platform_connection(
    payload: PlatformConfigRequest,
) -> ConnectionTestResponse:
    """Stub platform connection test endpoint."""
    if payload.platform_type == "mock":
        return ConnectionTestResponse(success=True, message="Mock test passed")
    return ConnectionTestResponse(
        success=False,
        message="Not implemented for this platform",
    )

