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
    """Platform connection test result."""

    success: bool = Field(..., description="Whether the connection test succeeded.")
    message: str = Field(..., description="Connection test status message.")


class ResetResponse(BaseModel):
    """Response for resetting platform configuration to default mock."""

    status: str = Field(..., description="Reset operation status.")
    platform_type: PlatformType = Field(..., description="Current platform after reset.")

