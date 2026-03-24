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
from skill.services.settings import SettingsService


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["status"])

_LIVE_STATUS_TTL_SECONDS = 20.0
_live_status_cache: dict[str, tuple[float, dict[str, str | bool | None]]] = {}


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

    defaults = SystemStatusResponse(
        configured=False,
        active_adapter="unconfigured",
        platform_type="unconfigured",
        loaded_intents=loaded_intents,
        database_connected=False,
        version=APP_VERSION,
    )

    try:
        settings_service.initialize()
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
        )
    except Exception as exc:
        logger.exception("Failed to load system status: %s", exc)
        return defaults
