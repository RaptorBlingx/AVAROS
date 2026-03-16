"""System status API router."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from config import APP_VERSION
from dependencies import get_adapter_factory, get_settings_service
from schemas.status import SystemStatusResponse
from skill.adapters.factory import AdapterFactory
from skill.domain.results import ConnectionTestResult
from skill.services.settings import SettingsService


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["status"])
_STATUS_CONNECTION_TIMEOUT_SECONDS = 3.0


def _intent_count() -> int:
    """Count intent files from mounted skill path or local fallback path."""
    mounted_locale_dir = Path("/opt/avaros/skill/locale/en-us")
    fallback_locale_dir = (
        Path(__file__).resolve().parents[2] / "skill" / "locale" / "en-us"
    )
    locale_dir = mounted_locale_dir if mounted_locale_dir.exists() else fallback_locale_dir
    return sum(1 for _ in locale_dir.glob("*.intent"))


def _classify_live_failure(result: ConnectionTestResult) -> str:
    """Map adapter test failure details to UI-friendly status states."""
    error_code = (result.error_code or "").upper()
    message = (result.message or "").lower()

    if "AUTH" in error_code or "cookie" in message or "unauthorized" in message:
        return "auth_failed"
    if (
        "TIMEOUT" in error_code
        or "CONNECTION" in error_code
        or "ECONN" in message
        or "timed out" in message
    ):
        return "unreachable"
    if "CONFIG" in error_code or "CREATION" in error_code:
        return "misconfigured"
    return "unknown"


async def _probe_live_connection(
    platform_type: str,
    configured: bool,
    adapter_factory: AdapterFactory,
) -> tuple[str, bool, str, str, str]:
    """Return normalized live connection state tuple for status response."""
    checked_at = datetime.now(timezone.utc).isoformat()

    if platform_type == "mock":
        return (
            "healthy",
            True,
            "Mock adapter active (development mode).",
            "",
            checked_at,
        )

    if not configured:
        return (
            "unconfigured",
            False,
            "Platform is not configured.",
            "PLATFORM_NOT_CONFIGURED",
            checked_at,
        )

    try:
        adapter = adapter_factory.create()
        result = await asyncio.wait_for(
            adapter.test_connection(),
            timeout=_STATUS_CONNECTION_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return (
            "unreachable",
            False,
            "Live connection check timed out.",
            "STATUS_CHECK_TIMEOUT",
            checked_at,
        )
    except Exception as exc:
        return (
            "misconfigured",
            False,
            f"Live connection check failed: {exc}",
            "STATUS_CHECK_FAILED",
            checked_at,
        )

    if result.success:
        return (
            "healthy",
            True,
            result.message or "Connection verified.",
            "",
            checked_at,
        )

    return (
        _classify_live_failure(result),
        False,
        result.message or "Connection failed.",
        result.error_code or "CONNECTION_TEST_FAILED",
        checked_at,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
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
        live_connection_state="unknown",
        live_connection_verified=False,
        live_connection_message="System status unavailable.",
        live_connection_error_code="STATUS_UNAVAILABLE",
        live_connection_checked_at=None,
    )

    try:
        settings_service.initialize()
        platform_config = settings_service.get_platform_config()
        configured = settings_service.is_configured()
        platform_type = platform_config.platform_type or "mock"
        (
            live_state,
            live_verified,
            live_message,
            live_error_code,
            live_checked_at,
        ) = await _probe_live_connection(
            platform_type=platform_type,
            configured=configured,
            adapter_factory=adapter_factory,
        )
        return SystemStatusResponse(
            configured=configured,
            active_adapter=platform_type,
            platform_type=platform_type,
            loaded_intents=loaded_intents,
            database_connected=True,
            version=APP_VERSION,
            live_connection_state=live_state,
            live_connection_verified=live_verified,
            live_connection_message=live_message,
            live_connection_error_code=live_error_code,
            live_connection_checked_at=live_checked_at,
        )
    except Exception as exc:
        logger.exception("Failed to load system status: %s", exc)
        return defaults
