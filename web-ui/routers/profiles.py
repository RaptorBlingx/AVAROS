"""Profile CRUD and activation API endpoints (DEC-028).

Exposes profile management over REST:
list, get, create, update, delete, and activate.
When activated, the adapter configuration is switched
so the next query uses the new platform — no restart needed.

DEC-029: on activation the voice skill is also notified
via the OVOS message bus so it can hot-reload its adapter.
"""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore[assignment]

from dependencies import get_adapter_factory, get_settings_service
from schemas.config import (
    ActivateProfileResponse,
    CreateProfileRequest,
    DeleteProfileResponse,
    ProfileDetailResponse,
    ProfileListResponse,
    ProfileMetadataResponse,
    UpdateProfileRequest,
    sanitize_extra_settings,
)
from skill.adapters.factory import AdapterFactory
from skill.domain.exceptions import ValidationError
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["profiles"])

MESSAGEBUS_URL = os.environ.get(
    "OVOS_MESSAGEBUS_URL", "ws://ovos_messagebus:8181/core",
)


# ── Helpers ─────────────────────────────────────────────


def _notify_skill_via_bus(profile_name: str) -> bool:
    """Emit profile activation event to OVOS message bus.

    Best-effort — returns False on failure, never raises.

    Args:
        profile_name: The newly activated profile name.

    Returns:
        True if event sent successfully, False otherwise.
    """
    try:
        if websocket is None:
            logger.warning("websocket-client not installed")
            return False
        ws = websocket.create_connection(
            MESSAGEBUS_URL, timeout=3,
        )
        msg = {
            "type": "avaros.profile.activated",
            "data": {"profile": profile_name},
            "context": {},
        }
        ws.send(json.dumps(msg))
        ws.close()
        logger.info(
            "Sent avaros.profile.activated to messagebus (profile='%s')",
            profile_name,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not notify skill via messagebus: %s", exc,
        )
        return False


def _validate_activation(
    name: str,
    svc: SettingsService,
) -> None:
    """Pre-check that a profile can be activated.

    Verifies the profile exists, uses a supported platform, and has
    required configuration fields.  Raises early *before* any state
    change so the caller can abort cleanly.

    Args:
        name: Profile to validate.
        svc: Settings service.

    Raises:
        HTTPException: 404 if profile not found, 422 if config invalid.
    """
    if name == svc.BUILTIN_MOCK_PROFILE:
        return  # mock always valid

    config = svc.get_profile(name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{name}' not found",
        )

    platform = config.platform_type.lower()
    available = AdapterFactory.get_available_platforms()
    if platform not in available:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Platform '{config.platform_type}' is not supported. "
                f"Available: {', '.join(available)}"
            ),
        )

    if platform == "reneryo" and not config.api_url:
        raise HTTPException(
            status_code=422,
            detail="RENERYO profile requires api_url to be configured",
        )


def _mask_api_key(api_key: str) -> str:
    """Mask key as ****XXXX; short keys return ****."""
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"


def _profile_detail(
    name: str,
    config: PlatformConfig,
    active: str,
) -> ProfileDetailResponse:
    """Build a detail response from a profile name and config.

    Args:
        name: Profile name.
        config: Platform configuration for the profile.
        active: Currently active profile name.

    Returns:
        ProfileDetailResponse with masked API key.
    """
    return ProfileDetailResponse(
        name=name,
        platform_type=config.platform_type,
        api_url=config.api_url,
        api_key=_mask_api_key(config.api_key),
        extra_settings=sanitize_extra_settings(config.extra_settings),
        is_builtin=name == "mock",
        is_active=name == active,
    )


# ── Endpoints ───────────────────────────────────────────


@router.get(
    "/profiles",
    response_model=ProfileListResponse,
)
def list_profiles(
    svc: SettingsService = Depends(get_settings_service),
) -> ProfileListResponse:
    """List all profiles with active profile indicated."""
    active = svc.get_active_profile_name()
    raw = svc.list_profiles()
    profiles = [ProfileMetadataResponse(**p) for p in raw]
    return ProfileListResponse(
        active_profile=active,
        profiles=profiles,
    )


@router.get(
    "/profiles/{name}",
    response_model=ProfileDetailResponse,
)
def get_profile(
    name: str,
    svc: SettingsService = Depends(get_settings_service),
) -> ProfileDetailResponse:
    """Get a single profile with masked API key."""
    config = svc.get_profile(name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{name}' not found",
        )
    active = svc.get_active_profile_name()
    return _profile_detail(name, config, active)


@router.post(
    "/profiles",
    response_model=ProfileDetailResponse,
    status_code=201,
)
def create_profile(
    payload: CreateProfileRequest,
    svc: SettingsService = Depends(get_settings_service),
) -> ProfileDetailResponse:
    """Create a new named profile."""
    if payload.name == svc.BUILTIN_MOCK_PROFILE:
        raise HTTPException(
            status_code=400,
            detail="Profile 'mock' is built-in and cannot be created",
        )

    config = PlatformConfig(
        platform_type=payload.platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=sanitize_extra_settings(payload.extra_settings),
    )
    try:
        svc.create_profile(payload.name, config)
    except ValidationError as exc:
        code = _validation_status_code(exc)
        raise HTTPException(status_code=code, detail=exc.message)
    active = svc.get_active_profile_name()
    return _profile_detail(payload.name, config, active)


@router.put(
    "/profiles/{name}",
    response_model=ProfileDetailResponse,
)
def update_profile(
    name: str,
    payload: UpdateProfileRequest,
    svc: SettingsService = Depends(get_settings_service),
) -> ProfileDetailResponse:
    """Update an existing profile's configuration."""
    config = PlatformConfig(
        platform_type=payload.platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=sanitize_extra_settings(payload.extra_settings),
    )
    try:
        svc.update_profile(name, config)
    except ValidationError as exc:
        code = _validation_status_code(exc)
        raise HTTPException(status_code=code, detail=exc.message)
    active = svc.get_active_profile_name()
    return _profile_detail(name, config, active)


@router.delete(
    "/profiles/{name}",
    response_model=DeleteProfileResponse,
)
def delete_profile(
    name: str,
    svc: SettingsService = Depends(get_settings_service),
) -> DeleteProfileResponse:
    """Delete a custom profile. Falls back to mock if active."""
    try:
        was_active = svc.get_active_profile_name() == name
        deleted = svc.delete_profile(name)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{name}' not found",
        )
    active = svc.get_active_profile_name()
    message = "Profile deleted"
    if was_active:
        message = (
            "Active profile reset to mock "
            "because deleted profile was active"
        )
    return DeleteProfileResponse(
        status="deleted",
        deleted_profile=name,
        active_profile=active,
        message=message,
    )


@router.post(
    "/profiles/{name}/activate",
    response_model=ActivateProfileResponse,
)
async def activate_profile(
    name: str,
    svc: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> ActivateProfileResponse:
    """Activate a profile with pre-validation and rollback.

    Pre-checks profile validity before any state change.  On adapter
    creation failure, rolls back to the previous working profile.
    """
    # Phase 1: Pre-validation (no state change)
    _validate_activation(name, svc)

    old_profile = svc.get_active_profile_name()

    # Phase 2: Attempt activation with rollback
    try:
        svc.set_active_profile(name)
    except ValidationError as exc:
        raise HTTPException(status_code=404, detail=exc.message)

    try:
        await adapter_factory.reload()
    except Exception as exc:
        logger.error(
            "Activation failed for '%s': %s. Rolling back to '%s'.",
            name, exc, old_profile,
        )
        try:
            svc.set_active_profile(old_profile)
            await adapter_factory.reload()
        except Exception as rollback_exc:
            logger.error(
                "Rollback to '%s' also failed: %s. "
                "System may be in bad state.",
                old_profile, rollback_exc,
            )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot activate profile '{name}': {exc}. "
                f"Rolled back to '{old_profile}'."
            ),
        )

    # Phase 3: Notify skill (best-effort, no rollback on failure)
    voice_reloaded = _notify_skill_via_bus(name)

    config = svc.get_profile(name)
    adapter_type = config.platform_type if config else "mock"
    return ActivateProfileResponse(
        status="activated",
        active_profile=name,
        adapter_type=adapter_type,
        message="Adapter reloaded successfully",
        voice_reloaded=voice_reloaded,
    )


# ── Private helpers ─────────────────────────────────────


def _validation_status_code(exc: ValidationError) -> int:
    """Map a ValidationError to the appropriate HTTP status.

    Args:
        exc: The validation error from SettingsService.

    Returns:
        400 for mock-related, 409 for duplicates, 404 not found.
    """
    msg = exc.message.lower()
    if "already exists" in msg:
        return 409
    if "not found" in msg:
        return 404
    return 400
