"""Request and response schemas for voice configuration APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


VoiceModeValue = str


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


class VoicePreferencesRequest(BaseModel):
    """Persisted browser voice preference shared by AVAROS embeds."""

    voice_mode: VoiceModeValue = Field(
        ...,
        description="Preferred AVAROS voice mode.",
    )

    @field_validator("voice_mode")
    @classmethod
    def validate_voice_mode(cls, value: str) -> str:
        if value not in {"wake-word", "push-to-talk", "text"}:
            raise ValueError("voice_mode must be wake-word, push-to-talk, or text")
        return value


class VoicePreferencesResponse(BaseModel):
    """Persisted browser voice preference shared by AVAROS embeds."""

    voice_mode: VoiceModeValue = Field(
        ...,
        description="Preferred AVAROS voice mode.",
    )
