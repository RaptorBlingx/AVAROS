"""Voice configuration endpoints for HiveMind WebSocket bridge."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request

from dependencies import get_settings_service
from schemas.voice import VoiceConfigResponse
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


def _first_header_value(value: str | None) -> str:
    """Return the first value from a potentially comma-separated proxy header."""
    return (value or "").split(",", maxsplit=1)[0].strip()


def _request_hivemind_url(request: Request) -> str:
    """Build a same-origin HiveMind WebSocket URL from the incoming request."""
    forwarded_proto = _first_header_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _first_header_value(request.headers.get("x-forwarded-host"))
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    proto = forwarded_proto or request.url.scheme
    ws_scheme = "wss" if proto in {"https", "wss"} else "ws"
    return f"{ws_scheme}://{host}/hivemind/"


def _resolve_hivemind_url(configured_url: str, request: Request) -> str:
    """Return the browser-facing HiveMind URL.

    ``HIVEMIND_WS_URL=auto`` lets one Docker image work behind any public
    hostname because the browser receives a WebSocket URL on the same origin
    it used to open AVAROS.
    """
    normalized = configured_url.strip()
    if normalized.lower() in {"", "auto", "same-origin", "same_origin"}:
        return _request_hivemind_url(request)

    parsed = urlparse(normalized)
    if parsed.path.endswith("/hivemind") and not normalized.endswith("/"):
        return f"{normalized}/"
    return normalized


@router.get("/config", response_model=VoiceConfigResponse)
def get_voice_config(
    request: Request,
    settings_service: SettingsService = Depends(get_settings_service),
) -> VoiceConfigResponse:
    """Return HiveMind connection config for the browser client.

    The frontend uses these values to establish a WebSocket
    connection to HiveMind-core.  When no client key is configured,
    ``voice_enabled`` is ``False`` and the UI hides
    voice features.
    """
    config = settings_service.get_voice_config()
    return VoiceConfigResponse(
        hivemind_url=_resolve_hivemind_url(config.hivemind_url, request),
        hivemind_name=config.hivemind_name,
        hivemind_key=config.hivemind_key,
        hivemind_secret=config.hivemind_secret,
        voice_enabled=bool(config.hivemind_key),
    )
