"""System status API router."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from config import APP_VERSION
from dependencies import get_adapter_factory, get_settings_service
from schemas.status import SystemStatusResponse
from skill.adapters.factory import AdapterFactory
from skill.services.prevention_runtime import (
    probe_prevention_status,
    resolve_prevention_config,
    resolve_prevention_data_status,
)
from skill.services.settings import SettingsService


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["status"])

_LIVE_STATUS_TTL_SECONDS = 20.0
_live_status_cache: dict[str, tuple[float, dict[str, str | bool | None]]] = {}
_PREVENTION_STATUS_TTL_SECONDS = 20.0
_prevention_status_cache: dict[
    str,
    tuple[float, dict[str, str | bool | int | list[str] | None]],
] = {}


def _intent_count() -> int:
    """Count intent files from mounted skill path or local fallback path."""
    mounted_locale_dir = Path("/opt/avaros/skill/locale/en-us")
    fallback_locale_dir = (
        Path(__file__).resolve().parents[2] / "skill" / "locale" / "en-us"
    )
    locale_dir = mounted_locale_dir if mounted_locale_dir.exists() else fallback_locale_dir
    return sum(1 for _ in locale_dir.glob("*.intent"))


def _live_state_from_error_code(
    *,
    success: bool,
    error_code: str,
) -> str:
    """Map adapter connection test result to UI-safe live state."""
    if success:
        return "healthy"
    normalized = (error_code or "").strip().upper()
    if "AUTH" in normalized:
        return "auth_failed"
    if any(token in normalized for token in ("TIMEOUT", "CONNECTION", "INIT_FAILED", "ENDPOINT_NOT_FOUND")):
        return "unreachable"
    if any(token in normalized for token in ("MAPPING", "CONFIG", "CREATION", "UNEXPECTED")):
        return "misconfigured"
    if "UNCONFIGURED" in normalized:
        return "unconfigured"
    return "unknown"


async def _resolve_prevention_status(
    settings_service: SettingsService,
) -> dict[str, str | bool | int | list[str] | None]:
    """Resolve PREVENTION runtime and data freshness state."""
    config = resolve_prevention_config(settings_service)
    data_status = resolve_prevention_data_status(settings_service)

    base_value: dict[str, str | bool | int | None] = {
        "prevention_mode": config.mode,
        "prevention_mode_reason": config.mode_reason,
        "prevention_state": "disabled" if config.mode != "http" else "unknown",
        "prevention_verified": False,
        "prevention_message": (
            "PREVENTION is disabled until a URL is configured."
            if config.mode != "http"
            else ""
        ),
        "prevention_checked_at": None,
        "prevention_endpoint": config.url or None,
        "prevention_data_state": data_status.state,
        "prevention_data_message": data_status.message,
        "prevention_data_updated_at": data_status.updated_at,
        "prevention_data_record_count": data_status.record_count,
        "prevention_analytics_goals": [],
        "prevention_analytics_types": [],
        "prevention_descriptive_state": (
            "disabled" if config.mode != "http" else "unknown"
        ),
        "prevention_predictive_state": (
            "disabled" if config.mode != "http" else "unknown"
        ),
        "prevention_prescriptive_state": "not_available",
    }

    if config.mode != "http" or not config.url:
        return base_value

    cache_key = "|".join([
        config.url,
        config.auth_token[-16:],
        data_status.updated_at or "",
        str(data_status.record_count or 0),
    ])
    now = time.monotonic()
    cached = _prevention_status_cache.get(cache_key)
    if cached is not None and cached[0] > now:
        return cached[1]

    probe = await probe_prevention_status(config)
    value = {
        **base_value,
        "prevention_state": probe.state,
        "prevention_verified": probe.verified,
        "prevention_message": probe.message,
        "prevention_checked_at": probe.checked_at,
        "prevention_analytics_goals": list(probe.analytics_goals),
        "prevention_analytics_types": list(probe.analytics_types),
        "prevention_descriptive_state": probe.descriptive_state,
        "prevention_predictive_state": probe.predictive_state,
        "prevention_prescriptive_state": probe.prescriptive_state,
    }
    _prevention_status_cache[cache_key] = (
        now + _PREVENTION_STATUS_TTL_SECONDS,
        value,
    )
    return value


async def _resolve_live_connection_status(
    *,
    adapter_factory: AdapterFactory,
    cache_key: str,
) -> dict[str, str | bool | None]:
    """Run (or reuse) live connection verification for status endpoint."""
    now = time.monotonic()
    cached = _live_status_cache.get(cache_key)
    if cached is not None and cached[0] > now:
        return cached[1]

    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        adapter = adapter_factory.create()
        result = await adapter.test_connection()
        live_state = _live_state_from_error_code(
            success=result.success,
            error_code=result.error_code or "",
        )
        value: dict[str, str | bool | None] = {
            "live_connection_state": live_state,
            "live_connection_verified": bool(result.success),
            "live_connection_message": result.message or "",
            "live_connection_error_code": result.error_code or "",
            "live_connection_checked_at": checked_at,
        }
    except Exception as exc:  # noqa: BLE001
        value = {
            "live_connection_state": "unknown",
            "live_connection_verified": False,
            "live_connection_message": str(exc),
            "live_connection_error_code": "STATUS_LIVE_CHECK_FAILED",
            "live_connection_checked_at": checked_at,
        }

    _live_status_cache[cache_key] = (now + _LIVE_STATUS_TTL_SECONDS, value)
    return value


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> SystemStatusResponse:
    """Return current AVAROS configuration and readiness status."""
    loaded_intents = _intent_count()
    prevention_status: dict[str, str | bool | int | list[str] | None] = {
        "prevention_mode": "unknown",
        "prevention_mode_reason": "",
        "prevention_state": "unknown",
        "prevention_verified": False,
        "prevention_message": "",
        "prevention_checked_at": None,
        "prevention_endpoint": None,
        "prevention_data_state": "unknown",
        "prevention_data_message": "",
        "prevention_data_updated_at": None,
        "prevention_data_record_count": None,
        "prevention_analytics_goals": [],
        "prevention_analytics_types": [],
        "prevention_descriptive_state": "unknown",
        "prevention_predictive_state": "unknown",
        "prevention_prescriptive_state": "not_available",
    }

    defaults = SystemStatusResponse(
        configured=False,
        active_adapter="unconfigured",
        platform_type="unconfigured",
        loaded_intents=loaded_intents,
        database_connected=False,
        version=APP_VERSION,
        prevention_mode=str(prevention_status["prevention_mode"]),
        prevention_mode_reason=str(prevention_status["prevention_mode_reason"]),
        prevention_state=str(prevention_status["prevention_state"]),
        prevention_verified=bool(prevention_status["prevention_verified"]),
        prevention_message=str(prevention_status["prevention_message"]),
        prevention_checked_at=None,
        prevention_endpoint=None,
        prevention_data_state=str(prevention_status["prevention_data_state"]),
        prevention_data_message=str(prevention_status["prevention_data_message"]),
        prevention_data_updated_at=None,
        prevention_data_record_count=None,
        prevention_analytics_goals=[],
        prevention_analytics_types=[],
        prevention_descriptive_state=str(
            prevention_status["prevention_descriptive_state"],
        ),
        prevention_predictive_state=str(
            prevention_status["prevention_predictive_state"],
        ),
        prevention_prescriptive_state=str(
            prevention_status["prevention_prescriptive_state"],
        ),
    )

    try:
        settings_service.initialize()
        prevention_status = await _resolve_prevention_status(
            settings_service,
        )
        platform_config = settings_service.get_platform_config()
        configured = settings_service.is_configured()
        platform_type = platform_config.platform_type or "unconfigured"

        live_status: dict[str, str | bool | None]
        if not configured:
            live_status = {
                "live_connection_state": "unconfigured",
                "live_connection_verified": False,
                "live_connection_message": "Run the wizard to configure a platform connection.",
                "live_connection_error_code": "UNCONFIGURED",
                "live_connection_checked_at": None,
            }
        else:
            cache_key = "|".join(
                [
                    str(platform_type).strip().lower(),
                    str(platform_config.api_url or "").strip(),
                    str(platform_config.extra_settings.get("auth_type", "")).strip().lower(),
                    str(platform_config.api_key or "")[-16:],
                ],
            )
            live_status = await _resolve_live_connection_status(
                adapter_factory=adapter_factory,
                cache_key=cache_key,
            )

        return SystemStatusResponse(
            configured=configured,
            active_adapter=platform_type,
            platform_type=platform_type,
            loaded_intents=loaded_intents,
            database_connected=True,
            version=APP_VERSION,
            live_connection_state=str(live_status["live_connection_state"] or "unknown"),
            live_connection_verified=bool(live_status["live_connection_verified"]),
            live_connection_message=str(live_status["live_connection_message"] or ""),
            live_connection_error_code=str(live_status["live_connection_error_code"] or ""),
            live_connection_checked_at=(
                str(live_status["live_connection_checked_at"])
                if live_status["live_connection_checked_at"] is not None
                else None
            ),
            prevention_mode=str(prevention_status["prevention_mode"] or "unknown"),
            prevention_mode_reason=str(prevention_status["prevention_mode_reason"] or ""),
            prevention_state=str(prevention_status["prevention_state"] or "unknown"),
            prevention_verified=bool(prevention_status["prevention_verified"]),
            prevention_message=str(prevention_status["prevention_message"] or ""),
            prevention_checked_at=(
                str(prevention_status["prevention_checked_at"])
                if prevention_status["prevention_checked_at"] is not None
                else None
            ),
            prevention_endpoint=(
                str(prevention_status["prevention_endpoint"])
                if prevention_status["prevention_endpoint"] is not None
                else None
            ),
            prevention_data_state=str(
                prevention_status["prevention_data_state"] or "unknown"
            ),
            prevention_data_message=str(
                prevention_status["prevention_data_message"] or ""
            ),
            prevention_data_updated_at=(
                str(prevention_status["prevention_data_updated_at"])
                if prevention_status["prevention_data_updated_at"] is not None
                else None
            ),
            prevention_data_record_count=(
                int(prevention_status["prevention_data_record_count"])
                if prevention_status["prevention_data_record_count"] is not None
                else None
            ),
            prevention_analytics_goals=list(
                prevention_status["prevention_analytics_goals"] or [],
            ),
            prevention_analytics_types=list(
                prevention_status["prevention_analytics_types"] or [],
            ),
            prevention_descriptive_state=str(
                prevention_status["prevention_descriptive_state"] or "unknown",
            ),
            prevention_predictive_state=str(
                prevention_status["prevention_predictive_state"] or "unknown",
            ),
            prevention_prescriptive_state=str(
                prevention_status["prevention_prescriptive_state"]
                or "not_available",
            ),
        )
    except Exception as exc:
        logger.exception("Failed to load system status: %s", exc)
        return defaults
