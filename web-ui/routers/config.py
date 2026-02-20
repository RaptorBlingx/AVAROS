"""Platform configuration CRUD APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from dependencies import get_kpi_measurement_service, get_settings_service
from schemas.config import (
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    ProfileConfigResponse,
    ProfileCreateRequest,
    ProfileListResponse,
    ProfileMetadataResponse,
    ProfileUpdateRequest,
    ResetResponse,
)
from skill.adapters.base import ManufacturingAdapter
from skill.services.kpi_measurement import KPIMeasurementService
from skill.services.settings import PlatformConfig, SettingsService
from services.kpi_collector import KPICollector


router = APIRouter(prefix="/api/v1/config", tags=["config"])
logger = logging.getLogger(__name__)
MOCK_PROFILE_NAME = "mock"
PROFILE_KEY_PREFIX = "platform_profile:"
ACTIVE_PROFILE_KEY = "platform_profile_active"
KPI_DEFAULT_SITE_ID = "pilot-1"
RENERYO_PROFILE_NAME = "reneryo"


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


def _profile_key(name: str) -> str:
    return f"{PROFILE_KEY_PREFIX}{name}"


def _get_active_profile_name(settings_service: SettingsService) -> str:
    raw = settings_service.get_setting(ACTIVE_PROFILE_KEY, default=MOCK_PROFILE_NAME)
    if not isinstance(raw, str) or not raw:
        return MOCK_PROFILE_NAME
    return raw


def _get_custom_profile(
    settings_service: SettingsService,
    name: str,
) -> PlatformConfig | None:
    raw = settings_service.get_setting(_profile_key(name), default=None)
    if not isinstance(raw, dict):
        return None
    return PlatformConfig.from_dict(raw)


def _list_custom_profile_names(settings_service: SettingsService) -> list[str]:
    keys = settings_service.list_settings()
    names = [
        key[len(PROFILE_KEY_PREFIX) :]
        for key in keys
        if key.startswith(PROFILE_KEY_PREFIX)
    ]
    names = [name for name in names if name]
    names.sort()
    return names


def _to_profile_response(
    name: str,
    config: PlatformConfig,
    is_active: bool,
    is_builtin: bool,
) -> ProfileConfigResponse:
    return ProfileConfigResponse(
        name=name,
        platform_type=config.platform_type,  # type: ignore[arg-type]
        api_url=config.api_url,
        api_key=_mask_api_key(config.api_key),
        extra_settings=config.extra_settings,
        is_builtin=is_builtin,
        is_active=is_active,
    )


def _to_profile_metadata(
    name: str,
    config: PlatformConfig,
    is_active: bool,
    is_builtin: bool,
) -> ProfileMetadataResponse:
    return ProfileMetadataResponse(
        name=name,
        platform_type=config.platform_type,  # type: ignore[arg-type]
        is_active=is_active,
        is_builtin=is_builtin,
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
    active_profile = _get_active_profile_name(settings_service)
    if active_profile != MOCK_PROFILE_NAME:
        settings_service.set_setting(_profile_key(active_profile), config.to_dict())
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
    settings_service.set_setting(ACTIVE_PROFILE_KEY, MOCK_PROFILE_NAME)
    return ResetResponse(status="reset", platform_type="mock")


@router.get("/profiles", response_model=ProfileListResponse)
def list_profiles(
    settings_service: SettingsService = Depends(get_settings_service),
) -> ProfileListResponse:
    """List built-in and custom profiles with active status."""
    active_profile = _get_active_profile_name(settings_service)
    custom_names = _list_custom_profile_names(settings_service)
    custom_profiles: list[tuple[str, PlatformConfig]] = []
    for name in custom_names:
        profile = _get_custom_profile(settings_service, name)
        if profile is not None:
            custom_profiles.append((name, profile))

    if active_profile != MOCK_PROFILE_NAME and not any(
        name == active_profile for name, _ in custom_profiles
    ):
        active_profile = MOCK_PROFILE_NAME
        settings_service.set_setting(ACTIVE_PROFILE_KEY, MOCK_PROFILE_NAME)

    profiles: list[ProfileMetadataResponse] = [
        _to_profile_metadata(
            name=MOCK_PROFILE_NAME,
            config=PlatformConfig(),
            is_active=active_profile == MOCK_PROFILE_NAME,
            is_builtin=True,
        )
    ]
    for name, cfg in custom_profiles:
        profiles.append(
            _to_profile_metadata(
                name=name,
                config=cfg,
                is_active=active_profile == name,
                is_builtin=False,
            )
        )

    return ProfileListResponse(profiles=profiles, active_profile=active_profile)


@router.get("/profiles/{name}", response_model=ProfileConfigResponse)
def get_profile(
    name: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> ProfileConfigResponse:
    """Return one profile config with masked key."""
    active_profile = _get_active_profile_name(settings_service)
    if name == MOCK_PROFILE_NAME:
        return _to_profile_response(
            name=MOCK_PROFILE_NAME,
            config=PlatformConfig(),
            is_active=active_profile == MOCK_PROFILE_NAME,
            is_builtin=True,
        )

    config = _get_custom_profile(settings_service, name)
    if config is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _to_profile_response(
        name=name,
        config=config,
        is_active=active_profile == name,
        is_builtin=False,
    )


@router.post("/profiles", response_model=ProfileConfigResponse, status_code=201)
def create_profile(
    payload: ProfileCreateRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> ProfileConfigResponse:
    """Create a new custom profile."""
    if payload.name == MOCK_PROFILE_NAME:
        raise HTTPException(
            status_code=400,
            detail="mock is a built-in profile and cannot be created",
        )
    if payload.platform_type == "mock":
        raise HTTPException(
            status_code=400,
            detail="Custom profiles cannot use platform_type=mock",
        )
    if _get_custom_profile(settings_service, payload.name) is not None:
        raise HTTPException(status_code=409, detail="Profile already exists")

    config = PlatformConfig(
        platform_type=payload.platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=payload.extra_settings,
    )
    settings_service.set_setting(_profile_key(payload.name), config.to_dict())
    return _to_profile_response(
        name=payload.name,
        config=config,
        is_active=False,
        is_builtin=False,
    )


@router.put("/profiles/{name}", response_model=ProfileConfigResponse)
def update_profile(
    name: str,
    payload: ProfileUpdateRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> ProfileConfigResponse:
    """Update an existing custom profile."""
    if name == MOCK_PROFILE_NAME:
        raise HTTPException(
            status_code=400,
            detail="Built-in mock profile cannot be modified",
        )
    existing = _get_custom_profile(settings_service, name)
    if existing is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    platform_type = payload.platform_type or existing.platform_type
    if platform_type == "mock":
        raise HTTPException(
            status_code=400,
            detail="Custom profiles cannot use platform_type=mock",
        )

    updated = PlatformConfig(
        platform_type=platform_type,
        api_url=payload.api_url if payload.api_url is not None else existing.api_url,
        api_key=payload.api_key if payload.api_key is not None else existing.api_key,
        extra_settings=(
            payload.extra_settings
            if payload.extra_settings is not None
            else existing.extra_settings
        ),
    )
    settings_service.set_setting(_profile_key(name), updated.to_dict())

    active = _get_active_profile_name(settings_service)
    if active == name:
        settings_service.update_platform_config(updated)

    return _to_profile_response(
        name=name,
        config=updated,
        is_active=active == name,
        is_builtin=False,
    )


@router.delete("/profiles/{name}", status_code=204)
def delete_profile(
    name: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> Response:
    """Delete a custom profile. Built-in mock cannot be deleted."""
    if name == MOCK_PROFILE_NAME:
        raise HTTPException(
            status_code=400,
            detail="Built-in mock profile cannot be deleted",
        )
    if _get_custom_profile(settings_service, name) is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    settings_service.delete_setting(_profile_key(name))
    active = _get_active_profile_name(settings_service)
    if active == name:
        settings_service.set_setting(ACTIVE_PROFILE_KEY, MOCK_PROFILE_NAME)
        settings_service.update_platform_config(PlatformConfig())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/profiles/{name}/activate", response_model=ProfileConfigResponse)
async def activate_profile(
    name: str,
    settings_service: SettingsService = Depends(get_settings_service),
    kpi_service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> ProfileConfigResponse:
    """Activate profile and hot-swap active adapter configuration."""
    collector = KPICollector(settings_service=settings_service, kpi_service=kpi_service)

    if name == MOCK_PROFILE_NAME:
        config = PlatformConfig()
        settings_service.update_platform_config(config)
        settings_service.set_setting(ACTIVE_PROFILE_KEY, MOCK_PROFILE_NAME)
        try:
            kpi_service.clear_site_data(KPI_DEFAULT_SITE_ID)
            await collector.seed_baselines(KPI_DEFAULT_SITE_ID)
            await collector.seed_mock_snapshot_history(KPI_DEFAULT_SITE_ID, points=10)
        except Exception:
            logger.warning(
                "KPI seed failed after mock profile activation; data may be stale",
                exc_info=True,
            )
        return _to_profile_response(
            name=MOCK_PROFILE_NAME,
            config=config,
            is_active=True,
            is_builtin=True,
        )

    config = _get_custom_profile(settings_service, name)
    if config is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    settings_service.update_platform_config(config)
    settings_service.set_setting(ACTIVE_PROFILE_KEY, name)

    if name == RENERYO_PROFILE_NAME:
        try:
            # Ensure dashboard has fresh data immediately after switching back from mock.
            await collector.seed_baselines(KPI_DEFAULT_SITE_ID)
            await collector.collect_snapshots(KPI_DEFAULT_SITE_ID)
        except Exception:
            logger.warning(
                "KPI refresh failed after reneryo profile activation; data may be stale",
                exc_info=True,
            )

    return _to_profile_response(
        name=name,
        config=config,
        is_active=True,
        is_builtin=False,
    )


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
            asset_mappings=payload.extra_settings.get("asset_mappings", {}),
        )

    raise ValueError(f"Unknown platform type: {payload.platform_type}")
