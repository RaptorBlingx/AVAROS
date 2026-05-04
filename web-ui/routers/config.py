"""Platform configuration CRUD APIs."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore[assignment]

from dependencies import get_adapter_factory, get_settings_service
from schemas.config import (
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    PreventionConfigRequest,
    PreventionConfigResponse,
    PreventionTestRequest,
    PreventionTestResponse,
    ResetResponse,
    sanitize_extra_settings,
)
from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.services.prevention_runtime import (
    PreventionConfig,
    probe_prevention_status,
    resolve_prevention_config,
    resolve_prevention_data_max_age_minutes,
    resolve_prevention_data_status,
)
from skill.services.settings import PlatformConfig, SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["config"])
logger = logging.getLogger(__name__)

_MESSAGEBUS_URL = os.environ.get(
    "OVOS_MESSAGEBUS_URL", "ws://ovos_messagebus:8181/core",
)


def _notify_skill_profile_changed(profile_name: str) -> bool:
    """Send profile activation event so the OVOS skill reloads its adapter.

    Best-effort — returns False on failure, never raises.
    """
    try:
        if websocket is None:
            logger.warning("websocket-client not installed — cannot notify skill")
            return False
        ws = websocket.create_connection(_MESSAGEBUS_URL, timeout=3)
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
        logger.warning("Could not notify skill via messagebus: %s", exc)
        return False


def _resolve_effective_platform_type(
    payload: PlatformConfigRequest,
) -> str:
    """Return requested platform type without profile-specific overrides."""
    return payload.platform_type


def _mask_api_key(api_key: str) -> str:
    """Mask key as ****XXXX; for short keys return ****."""
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"


def _mask_secret(value: str) -> str:
    """Mask sensitive tokens while preserving enough suffix for recognition."""
    normalized = value.strip()
    if not normalized:
        return ""
    if len(normalized) <= 4:
        return "****"
    return f"****{normalized[-4:]}"


def _token_is_configured(settings_service: SettingsService) -> tuple[bool, str]:
    """Return whether PREVENTION auth is configured and the masked value."""
    env_token = os.environ.get("PREVENTION_AUTH_TOKEN", "").strip()
    if env_token:
        return True, _mask_secret(env_token)
    saved_token = str(
        settings_service.get_setting("prevention_auth_token", ""),
    ).strip()
    if saved_token:
        return True, _mask_secret(saved_token)
    return False, ""


def _keycloak_secret_is_configured(
    settings_service: SettingsService,
) -> tuple[bool, str]:
    """Return whether a PREVENTION Keycloak secret is configured."""
    env_secret = os.environ.get("PREVENTION_KEYCLOAK_CLIENT_SECRET", "").strip()
    if env_secret:
        return True, _mask_secret(env_secret)
    saved_secret = str(
        settings_service.get_setting("prevention_keycloak_client_secret", ""),
    ).strip()
    if saved_secret:
        return True, _mask_secret(saved_secret)
    return False, ""


async def _build_prevention_response(
    settings_service: SettingsService,
) -> PreventionConfigResponse:
    """Resolve saved/effective PREVENTION configuration for the Web UI."""
    config = resolve_prevention_config(settings_service)
    data_status = resolve_prevention_data_status(settings_service)
    token_configured, token_masked = _token_is_configured(settings_service)
    keycloak_secret_configured, keycloak_secret_masked = (
        _keycloak_secret_is_configured(settings_service)
    )

    if config.mode == "http" and config.url:
        probe = await probe_prevention_status(config)
        state = probe.state
        verified = probe.verified
        message = probe.message
        checked_at = probe.checked_at
    else:
        state = "disabled"
        verified = False
        message = "PREVENTION is disabled until a URL is configured."
        checked_at = None

    return PreventionConfigResponse(
        enabled=config.mode == "http",
        endpoint_url=config.url,
        endpoint_source=config.endpoint_source,
        env_override=config.endpoint_source == "env",
        auth_token_configured=token_configured,
        auth_token_masked=token_masked,
        auth_mode=config.auth_mode,
        keycloak_token_url=config.keycloak_token_url,
        keycloak_client_id=config.keycloak_client_id,
        keycloak_client_secret_configured=keycloak_secret_configured,
        keycloak_client_secret_masked=keycloak_secret_masked,
        keycloak_scope=config.keycloak_scope,
        data_max_age_minutes=resolve_prevention_data_max_age_minutes(
            settings_service,
        ),
        state=state,
        verified=verified,
        message=message,
        checked_at=checked_at,
        data_state=data_status.state,
        data_message=data_status.message,
        data_updated_at=data_status.updated_at,
        data_record_count=data_status.record_count,
    )


def _to_response(config: PlatformConfig) -> PlatformConfigResponse:
    """Convert service config into API-safe masked response.

    Public Web UI contract intentionally exposes only ``custom_rest`` and
    ``unconfigured`` platform types. Unknown internal aliases are surfaced
    as ``custom_rest`` at the API boundary.
    """
    raw = str(config.platform_type or "unconfigured").lower()
    platform_type = raw if raw in {"custom_rest", "unconfigured"} else "custom_rest"
    return PlatformConfigResponse(
        platform_type=platform_type,
        api_url=config.api_url,
        api_key=_mask_api_key(config.api_key),
        extra_settings=sanitize_extra_settings(config.extra_settings),
    )


@router.post("/platform", response_model=PlatformConfigResponse)
async def upsert_platform_config(
    payload: PlatformConfigRequest,
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> PlatformConfigResponse:
    """Create or update platform configuration and hot-reload adapter."""
    platform_type = _resolve_effective_platform_type(payload)
    config = PlatformConfig(
        platform_type=platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=sanitize_extra_settings(payload.extra_settings),
    )
    settings_service.update_platform_config(config)

    # Keep voice runtime in sync with freshly saved platform settings.
    try:
        await adapter_factory.reload()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Platform config saved but adapter reload failed: %s",
            exc,
        )

    profile_name = settings_service.get_active_profile_name()
    _notify_skill_profile_changed(profile_name)

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
    """Reset configuration by switching back to unconfigured profile."""
    active = settings_service.get_active_profile_name()
    if active != settings_service.DEFAULT_PROFILE:
        settings_service.delete_profile(active)
    return ResetResponse(status="reset", platform_type="unconfigured")


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
    if payload.platform_type == "custom_rest":
        from skill.adapters.generic_rest import GenericRestAdapter

        return GenericRestAdapter(
            api_url=payload.api_url,
            api_key=payload.api_key,
            timeout=payload.extra_settings.get("timeout", 10),
            auth_type=payload.extra_settings.get("auth_type", "bearer"),
            extra_settings=sanitize_extra_settings(payload.extra_settings),
        )

    raise ValueError(f"Unknown platform type: {payload.platform_type}")


@router.get("/prevention", response_model=PreventionConfigResponse)
async def get_prevention_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> PreventionConfigResponse:
    """Return PREVENTION analytics configuration and live status."""
    return await _build_prevention_response(settings_service)


@router.post("/prevention", response_model=PreventionConfigResponse)
async def upsert_prevention_config(
    payload: PreventionConfigRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> PreventionConfigResponse:
    """Create or update PREVENTION analytics configuration."""
    endpoint_url = payload.endpoint_url.strip() if payload.enabled else ""
    settings_service.set_setting("prevention_url", endpoint_url)
    settings_service.set_setting(
        "prevention_data_max_age_minutes",
        payload.data_max_age_minutes,
    )
    settings_service.set_setting("prevention_auth_mode", payload.auth_mode)

    if payload.auth_mode != "bearer":
        settings_service.delete_setting("prevention_auth_token")
    elif payload.clear_auth_token:
        settings_service.delete_setting("prevention_auth_token")
    elif "auth_token" in payload.model_fields_set:
        token = (payload.auth_token or "").strip()
        if token:
            settings_service.set_setting(
                "prevention_auth_token",
                token,
                encrypt=True,
            )
        else:
            settings_service.delete_setting("prevention_auth_token")

    if payload.auth_mode != "keycloak_client_credentials":
        settings_service.delete_setting("prevention_keycloak_token_url")
        settings_service.delete_setting("prevention_keycloak_client_id")
        settings_service.delete_setting("prevention_keycloak_client_secret")
        settings_service.delete_setting("prevention_keycloak_scope")
    else:
        settings_service.set_setting(
            "prevention_keycloak_token_url",
            payload.keycloak_token_url.strip(),
        )
        settings_service.set_setting(
            "prevention_keycloak_client_id",
            payload.keycloak_client_id.strip(),
        )
        settings_service.set_setting(
            "prevention_keycloak_scope",
            payload.keycloak_scope.strip(),
        )
        if payload.clear_keycloak_client_secret:
            settings_service.delete_setting("prevention_keycloak_client_secret")
        elif "keycloak_client_secret" in payload.model_fields_set:
            secret = (payload.keycloak_client_secret or "").strip()
            if secret:
                settings_service.set_setting(
                    "prevention_keycloak_client_secret",
                    secret,
                    encrypt=True,
                )
            else:
                settings_service.delete_setting(
                    "prevention_keycloak_client_secret",
                )

    return await _build_prevention_response(settings_service)


@router.post("/prevention/test", response_model=PreventionTestResponse)
async def test_prevention_connection(
    payload: PreventionTestRequest,
) -> PreventionTestResponse:
    """Probe a PREVENTION endpoint without saving it."""
    probe = await probe_prevention_status(
        PreventionConfig(
            url=payload.endpoint_url,
            auth_token=(
                payload.auth_token.strip()
                if payload.auth_mode == "bearer"
                else ""
            ),
            auth_mode=payload.auth_mode,
            keycloak_token_url=payload.keycloak_token_url.strip(),
            keycloak_client_id=payload.keycloak_client_id.strip(),
            keycloak_client_secret=payload.keycloak_client_secret.strip(),
            keycloak_scope=payload.keycloak_scope.strip(),
            mode="http",
            mode_reason="request_payload",
            endpoint_source="request",
        ),
    )
    return PreventionTestResponse(
        success=probe.verified,
        state=probe.state,
        message=probe.message,
        checked_at=probe.checked_at,
    )
