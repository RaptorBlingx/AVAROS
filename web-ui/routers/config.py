"""Platform configuration CRUD APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import get_settings_service
from schemas.config import (
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    ResetResponse,
    sanitize_extra_settings,
)
from skill.adapters.base import ManufacturingAdapter
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
        extra_settings=sanitize_extra_settings(config.extra_settings),
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
        extra_settings=sanitize_extra_settings(payload.extra_settings),
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
    """Reset configuration by switching back to mock profile."""
    active = settings_service.get_active_profile_name()
    if active != settings_service.BUILTIN_MOCK_PROFILE:
        settings_service.delete_profile(active)
    return ResetResponse(status="reset", platform_type="mock")


@router.post("/platform/test", response_model=ConnectionTestResponse)
async def test_platform_connection(
    payload: PlatformConfigRequest,
) -> ConnectionTestResponse:
    """
    Test connectivity to the configured platform.

    Creates a temporary adapter from the payload config,
    runs test_connection(), and returns detailed results.
    Does NOT save the configuration (non-destructive).
    """
    try:
        adapter = _create_adapter_from_config(payload)
        result = await adapter.test_connection()
        return ConnectionTestResponse(
            success=result.success,
            message=result.message,
            latency_ms=result.latency_ms,
            adapter_name=result.adapter_name,
            resources_discovered=list(result.resources_discovered),
            error_code=result.error_code,
            error_details=result.error_details,
        )
    except Exception as exc:
        return ConnectionTestResponse(
            success=False,
            message=f"Failed to create adapter: {exc}",
            error_code="ADAPTER_CREATION_FAILED",
            error_details=str(exc),
        )


def _create_adapter_from_config(
    payload: PlatformConfigRequest,
) -> ManufacturingAdapter:
    """
    Create a throwaway adapter instance from a request payload.

    Used for connection testing — creates an adapter to test
    connectivity before committing the configuration.

    Args:
        payload: Platform configuration from the request body.

    Returns:
        Configured ManufacturingAdapter instance.

    Raises:
        ValueError: If platform_type is unknown.
    """
    if payload.platform_type == "mock":
        from skill.adapters.mock import MockAdapter

        return MockAdapter()

    if payload.platform_type == "reneryo":
        from skill.adapters.reneryo import ReneryoAdapter

        return ReneryoAdapter(
            api_url=payload.api_url,
            api_key=payload.api_key,
            timeout=payload.extra_settings.get("timeout", 10),
            auth_type=payload.extra_settings.get("auth_type", "bearer"),
            api_format=payload.extra_settings.get("api_format", "native"),
            native_seu_id=str(payload.extra_settings.get("seu_id", "")).strip(),
            extra_settings=sanitize_extra_settings(payload.extra_settings),
        )

    raise ValueError(f"Unknown platform type: {payload.platform_type}")
