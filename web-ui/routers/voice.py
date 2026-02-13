"""Voice configuration endpoints for HiveMind WebSocket bridge."""

from __future__ import annotations

import os

from fastapi import APIRouter

from schemas.voice import VoiceConfigResponse


router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.get("/config", response_model=VoiceConfigResponse)
def get_voice_config() -> VoiceConfigResponse:
    """Return HiveMind connection config for the browser client.

    The frontend uses these values to establish a WebSocket
    connection to HiveMind-core.  When ``HIVEMIND_CLIENT_KEY``
    is not set, ``voice_enabled`` is ``False`` and the UI hides
    voice features.
    """
    client_key = os.environ.get("HIVEMIND_CLIENT_KEY", "")
    return VoiceConfigResponse(
        hivemind_url=os.environ.get(
            "HIVEMIND_WS_URL", "ws://localhost:5678"
        ),
        hivemind_key=client_key,
        hivemind_secret=os.environ.get("HIVEMIND_CLIENT_SECRET", ""),
        voice_enabled=bool(client_key),
    )
