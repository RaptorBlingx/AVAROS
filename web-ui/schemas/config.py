"""Request and response schemas for platform configuration APIs."""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


PlatformType = Literal["mock", "reneryo", "custom_rest"]

_PROFILE_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9\-]{0,48}[a-z0-9]$",
)


def sanitize_extra_settings(extra_settings: dict[str, Any] | None) -> dict[str, Any]:
    """Drop deprecated platform-level settings before save/response."""
    sanitized = dict(extra_settings or {})
    sanitized.pop("seu_id", None)
    return sanitized


class PlatformConfigRequest(BaseModel):
    """Create/update platform configuration payload."""

    platform_type: PlatformType = Field(
        ...,
        description="Platform adapter type.",
    )
    api_url: str = Field(
        default="",
        description="Platform API base URL. Required for non-mock platforms.",
    )
    api_key: str = Field(
        default="",
        description="Platform API key. Required for non-mock platforms.",
    )
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific extra settings.",
    )

    @model_validator(mode="after")
    def validate_for_platform(self) -> PlatformConfigRequest:
        """Enforce platform-specific required fields."""
        if self.platform_type == "mock":
            return self

        if not self.api_url:
            raise ValueError("api_url is required for non-mock platforms")

        parsed = urlparse(self.api_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("api_url must be a valid URL")

        auth_type = str(self.extra_settings.get("auth_type", "bearer")).strip().lower()
        if auth_type != "none" and not self.api_key:
            raise ValueError("api_key is required for non-mock platforms")

        return self


class PlatformConfigResponse(BaseModel):
    """Masked platform configuration response."""

    platform_type: PlatformType = Field(
        ...,
        description="Configured platform adapter type.",
    )
    api_url: str = Field(
        ...,
        description="Configured platform API base URL.",
    )
    api_key: str = Field(
        ...,
        description="Masked API key value (never plaintext).",
    )
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Configured platform-specific settings.",
    )


class ConnectionTestResponse(BaseModel):
    """Platform connection test result with detailed diagnostics."""

    success: bool = Field(..., description="Whether the connection test succeeded.")
    message: str = Field(..., description="Connection test status message.")
    latency_ms: float = Field(
        default=0.0,
        description="Round-trip latency in milliseconds.",
    )
    adapter_name: str = Field(
        default="",
        description="Name of the adapter that was tested.",
    )
    resources_discovered: list[str] = Field(
        default_factory=list,
        description="List of discovered resources (meters, endpoints, etc.).",
    )
    error_code: str = Field(
        default="",
        description="Machine-readable error code for troubleshooting.",
    )
    error_details: str = Field(
        default="",
        description="Technical error details (not shown to operators by default).",
    )


class ResetResponse(BaseModel):
    """Response for resetting platform configuration to default mock."""

    status: str = Field(..., description="Reset operation status.")
    platform_type: PlatformType = Field(..., description="Current platform after reset.")


# ── Profile Schemas ─────────────────────────────────────


class ProfileMetadataResponse(BaseModel):
    """Summary of a single profile (used in list responses)."""

    name: str = Field(..., description="Profile name.")
    platform_type: str = Field(..., description="Platform adapter type.")
    is_builtin: bool = Field(..., description="True for the mock profile.")
    is_active: bool = Field(..., description="True if this profile is active.")


class ProfileListResponse(BaseModel):
    """List of all profiles with active profile indicated."""

    active_profile: str = Field(..., description="Name of the active profile.")
    profiles: list[ProfileMetadataResponse] = Field(
        ..., description="All profiles (mock first).",
    )


class ProfileDetailResponse(BaseModel):
    """Full profile configuration with masked API key."""

    name: str = Field(..., description="Profile name.")
    platform_type: str = Field(..., description="Platform adapter type.")
    api_url: str = Field(..., description="Platform API base URL.")
    api_key: str = Field(..., description="Masked API key.")
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific settings.",
    )
    is_builtin: bool = Field(..., description="True for the mock profile.")
    is_active: bool = Field(..., description="True if this profile is active.")


class CreateProfileRequest(BaseModel):
    """Request body for creating a new profile."""

    name: str = Field(
        ...,
        description="Profile name (2-50 chars, lowercase alphanumeric + hyphens).",
    )
    platform_type: str = Field(..., description="Platform adapter type.")
    api_url: str = Field(default="", description="Platform API base URL.")
    api_key: str = Field(default="", description="Platform API key.")
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific extra settings.",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Enforce profile naming rules."""
        if not _PROFILE_NAME_PATTERN.match(value):
            raise ValueError(
                f"Invalid profile name: '{value}'. "
                "Must be 2-50 chars, lowercase alphanumeric "
                "+ hyphens, no leading/trailing hyphen.",
            )
        return value


class UpdateProfileRequest(BaseModel):
    """Request body for updating an existing profile."""

    platform_type: str = Field(..., description="Platform adapter type.")
    api_url: str = Field(default="", description="Platform API base URL.")
    api_key: str = Field(default="", description="Platform API key.")
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific extra settings.",
    )


class ActivateProfileResponse(BaseModel):
    """Response after activating a profile."""

    status: str = Field(..., description="Operation status.")
    active_profile: str = Field(..., description="Name of the now-active profile.")
    adapter_type: str = Field(..., description="Platform type of active adapter.")
    message: str = Field(..., description="Human-readable result message.")
    voice_reloaded: bool = Field(
        default=False,
        description="True if the OVOS skill was notified via message bus.",
    )


class DeleteProfileResponse(BaseModel):
    """Response after deleting a profile."""

    status: str = Field(..., description="Operation status.")
    deleted_profile: str = Field(..., description="Name of the deleted profile.")
    active_profile: str = Field(..., description="Name of the active profile after deletion.")
    message: str = Field(..., description="Human-readable result message.")
