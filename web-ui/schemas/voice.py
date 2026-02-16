"""Request and response schemas for voice configuration APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceConfigResponse(BaseModel):
    """HiveMind connection configuration for the browser client."""

    hivemind_url: str = Field(
        ...,
        description="WebSocket URL for HiveMind-core connection.",
    )
    hivemind_name: str = Field(
        ...,
        description="Client name for HiveMind authentication token.",
    )
    hivemind_key: str = Field(
        ...,
        description="Client access key for HiveMind authentication.",
    )
    hivemind_secret: str = Field(
        ...,
        description="Client secret for HiveMind authentication.",
    )
    voice_enabled: bool = Field(
        ...,
        description="Whether voice features are enabled (key configured).",
    )
