"""Request and response schemas for platform configuration APIs."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


PlatformType = Literal["mock", "reneryo", "custom_rest"]


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

        if not self.api_key:
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


class ProfileMetadataResponse(BaseModel):
    """Profile metadata used in profile listing responses."""

    name: str = Field(
        ...,
        description="Unique profile name.",
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    platform_type: PlatformType = Field(..., description="Profile adapter type.")
    is_active: bool = Field(..., description="Whether this profile is currently active.")
    is_builtin: bool = Field(..., description="Whether this profile is built-in and read-only.")


class ProfileListResponse(BaseModel):
    """List of available adapter profiles and current active profile."""

    profiles: list[ProfileMetadataResponse] = Field(
        default_factory=list,
        description="All available profiles (mock + custom).",
    )
    active_profile: str = Field(
        ...,
        description="Name of the currently active profile.",
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )


class ProfileConfigResponse(BaseModel):
    """Profile configuration payload returned by profile endpoints."""

    name: str = Field(
        ...,
        description="Profile name.",
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    platform_type: PlatformType = Field(..., description="Configured platform type.")
    api_url: str = Field(..., description="Configured API URL.")
    api_key: str = Field(..., description="Masked API key.")
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Profile-specific extra settings.",
    )
    is_builtin: bool = Field(..., description="Whether profile is built-in.")
    is_active: bool = Field(..., description="Whether profile is currently active.")


class ProfileCreateRequest(BaseModel):
    """Create a new custom profile."""

    name: str = Field(
        ...,
        description="Custom profile name.",
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    platform_type: PlatformType = Field(..., description="Platform type for this profile.")
    api_url: str = Field(
        default="",
        description="Optional API URL. Can be configured later.",
    )
    api_key: str = Field(
        default="",
        description="Optional API key. Can be configured later.",
    )
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extra settings.",
    )


class ProfileUpdateRequest(BaseModel):
    """Update an existing custom profile."""

    platform_type: PlatformType | None = Field(
        default=None,
        description="Updated platform type.",
    )
    api_url: str | None = Field(
        default=None,
        description="Updated API URL.",
    )
    api_key: str | None = Field(
        default=None,
        description="Updated API key.",
    )
    extra_settings: dict[str, Any] | None = Field(
        default=None,
        description="Updated extra settings.",
    )

