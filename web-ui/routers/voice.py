"""Voice configuration endpoints for HiveMind WebSocket bridge."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import get_settings_service
from schemas.voice import VoiceConfigResponse
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.get("/config", response_model=VoiceConfigResponse)
def get_voice_config(
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
        hivemind_url=config.hivemind_url,
        hivemind_name=config.hivemind_name,
        hivemind_key=config.hivemind_key,
        hivemind_secret=config.hivemind_secret,
        voice_enabled=bool(config.hivemind_key),
    )
