"""Request and response schemas for platform configuration APIs."""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


PlatformType = Literal["custom_rest"]
ResponsePlatformType = Literal["custom_rest", "unconfigured"]
PreventionState = Literal[
    "healthy",
    "unreachable",
    "misconfigured",
    "disabled",
    "unknown",
]

_PROFILE_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9\-]{0,48}[a-z0-9]$",
)


def sanitize_extra_settings(extra_settings: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize platform-level settings before save/response."""
    return dict(extra_settings or {})


class PlatformConfigRequest(BaseModel):
    """Create/update platform configuration payload."""

    platform_type: PlatformType = Field(
        ...,
        description="Platform adapter type.",
    )
    api_url: str = Field(
        default="",
        description="Platform API base URL. Required for all platforms.",
    )
    api_key: str = Field(
        default="",
        description="Platform API key. Required for all platforms.",
    )
    extra_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific extra settings.",
    )

    @model_validator(mode="after")
    def validate_for_platform(self) -> PlatformConfigRequest:
        """Enforce platform-specific required fields."""
        if not self.api_url:
            raise ValueError("api_url is required")

        parsed = urlparse(self.api_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("api_url must be a valid URL")

        auth_type = str(self.extra_settings.get("auth_type", "bearer")).strip().lower()
        if auth_type != "none" and not self.api_key:
            raise ValueError("api_key is required when auth_type is not 'none'")

        return self


class PlatformConfigResponse(BaseModel):
    """Masked platform configuration response."""

    platform_type: ResponsePlatformType = Field(
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


class PreventionConfigRequest(BaseModel):
    """Create/update PREVENTION analytics configuration payload."""

    enabled: bool = Field(
        default=False,
        description="Whether PREVENTION analytics should be enabled.",
    )
    endpoint_url: str = Field(
        default="",
        description="PREVENTION base URL. Required when enabled.",
    )
    auth_token: str | None = Field(
        default=None,
        description="Optional bearer token. Omit to keep the existing token.",
    )
    clear_auth_token: bool = Field(
        default=False,
        description="Clear any stored PREVENTION auth token.",
    )
    auth_mode: Literal["none", "bearer", "keycloak_client_credentials"] = Field(
        default="none",
        description="PREVENTION authentication mode.",
    )
    keycloak_token_url: str = Field(
        default="",
        description="Keycloak/OIDC token endpoint for client credentials.",
    )
    keycloak_client_id: str = Field(
        default="",
        description="Keycloak/OIDC client ID.",
    )
    keycloak_client_secret: str | None = Field(
        default=None,
        description="Keycloak/OIDC client secret. Omit to keep existing secret.",
    )
    clear_keycloak_client_secret: bool = Field(
        default=False,
        description="Clear any stored Keycloak/OIDC client secret.",
    )
    keycloak_scope: str = Field(
        default="",
        description="Optional Keycloak/OIDC token scope.",
    )
    data_max_age_minutes: int = Field(
        default=1440,
        ge=1,
        description="Freshness limit for exported PREVENTION input data.",
    )

    @model_validator(mode="after")
    def validate_for_enabled_state(self) -> PreventionConfigRequest:
        """Enforce endpoint requirements only when analytics are enabled."""
        self.endpoint_url = self.endpoint_url.strip()
        if self.auth_mode == "none" and (self.auth_token or self.clear_auth_token):
            self.auth_mode = "bearer"
        if self.enabled:
            if not self.endpoint_url:
                raise ValueError("endpoint_url is required when PREVENTION is enabled")
            parsed = urlparse(self.endpoint_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("endpoint_url must be a valid http:// or https:// URL")
            if self.auth_mode == "keycloak_client_credentials":
                self.keycloak_token_url = self.keycloak_token_url.strip()
                parsed_token_url = urlparse(self.keycloak_token_url)
                if (
                    parsed_token_url.scheme not in {"http", "https"}
                    or not parsed_token_url.netloc
                ):
                    raise ValueError(
                        "keycloak_token_url must be a valid http:// or https:// URL",
                    )
                self.keycloak_client_id = self.keycloak_client_id.strip()
                if not self.keycloak_client_id:
                    raise ValueError(
                        "keycloak_client_id is required for Keycloak auth",
                    )
        return self


class PreventionTestRequest(BaseModel):
    """Non-persistent PREVENTION connection test payload."""

    endpoint_url: str = Field(..., description="PREVENTION base URL to test.")
    auth_token: str = Field(default="", description="Optional auth token.")
    auth_mode: Literal["none", "bearer", "keycloak_client_credentials"] = Field(
        default="none",
        description="PREVENTION authentication mode for this probe.",
    )
    keycloak_token_url: str = Field(
        default="",
        description="Keycloak/OIDC token endpoint for client credentials.",
    )
    keycloak_client_id: str = Field(
        default="",
        description="Keycloak/OIDC client ID.",
    )
    keycloak_client_secret: str = Field(
        default="",
        description="Keycloak/OIDC client secret.",
    )
    keycloak_scope: str = Field(
        default="",
        description="Optional Keycloak/OIDC token scope.",
    )

    @model_validator(mode="after")
    def validate_endpoint(self) -> PreventionTestRequest:
        """Require a valid HTTP(S) endpoint."""
        self.endpoint_url = self.endpoint_url.strip()
        if self.auth_mode == "none" and self.auth_token:
            self.auth_mode = "bearer"
        parsed = urlparse(self.endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint_url must be a valid http:// or https:// URL")
        if self.auth_mode == "keycloak_client_credentials":
            self.keycloak_token_url = self.keycloak_token_url.strip()
            parsed_token_url = urlparse(self.keycloak_token_url)
            if (
                parsed_token_url.scheme not in {"http", "https"}
                or not parsed_token_url.netloc
            ):
                raise ValueError(
                    "keycloak_token_url must be a valid http:// or https:// URL",
                )
            self.keycloak_client_id = self.keycloak_client_id.strip()
            self.keycloak_client_secret = self.keycloak_client_secret.strip()
            if not self.keycloak_client_id or not self.keycloak_client_secret:
                raise ValueError(
                    "keycloak_client_id and keycloak_client_secret are required "
                    "for Keycloak auth tests",
                )
        return self


class PreventionConfigResponse(BaseModel):
    """Masked PREVENTION analytics configuration and current status."""

    enabled: bool = Field(..., description="Whether PREVENTION is active.")
    endpoint_url: str = Field(default="", description="Resolved PREVENTION URL.")
    endpoint_source: str = Field(
        default="none",
        description="Source for the active endpoint: env, settings, or none.",
    )
    env_override: bool = Field(
        default=False,
        description="True when PREVENTION_URL overrides saved settings.",
    )
    auth_token_configured: bool = Field(
        default=False,
        description="True when an auth token is configured.",
    )
    auth_token_masked: str = Field(
        default="",
        description="Masked auth token, never plaintext.",
    )
    auth_mode: str = Field(default="none", description="PREVENTION auth mode.")
    keycloak_token_url: str = Field(
        default="",
        description="Configured Keycloak/OIDC token endpoint.",
    )
    keycloak_client_id: str = Field(
        default="",
        description="Configured Keycloak/OIDC client ID.",
    )
    keycloak_client_secret_configured: bool = Field(
        default=False,
        description="True when a Keycloak/OIDC client secret is configured.",
    )
    keycloak_client_secret_masked: str = Field(
        default="",
        description="Masked Keycloak/OIDC client secret, never plaintext.",
    )
    keycloak_scope: str = Field(
        default="",
        description="Configured Keycloak/OIDC token scope.",
    )
    data_max_age_minutes: int = Field(
        default=1440,
        description="Configured freshness limit for exported PREVENTION data.",
    )
    state: PreventionState = Field(default="unknown", description="Live health state.")
    verified: bool = Field(default=False, description="True when health probe passed.")
    message: str = Field(default="", description="Human-readable health message.")
    checked_at: str | None = Field(
        default=None,
        description="ISO timestamp of the latest health probe.",
    )
    data_state: str = Field(default="unknown", description="Data freshness state.")
    data_message: str = Field(default="", description="Data freshness message.")
    data_updated_at: str | None = Field(default=None, description="Latest export time.")
    data_record_count: int | None = Field(default=None, description="Latest export rows.")


class PreventionTestResponse(BaseModel):
    """PREVENTION connection test result."""

    success: bool = Field(..., description="Whether the probe succeeded.")
    state: PreventionState = Field(..., description="Probe health state.")
    message: str = Field(..., description="Probe result message.")
    checked_at: str | None = Field(default=None, description="Probe timestamp.")


class ResetResponse(BaseModel):
    """Response for resetting platform configuration."""

    status: str = Field(..., description="Reset operation status.")
    platform_type: str = Field(..., description="Current platform after reset.")


# ── Profile Schemas ─────────────────────────────────────


class ProfileMetadataResponse(BaseModel):
    """Summary of a single profile (used in list responses)."""

    name: str = Field(..., description="Profile name.")
    platform_type: str = Field(..., description="Platform adapter type.")
    is_builtin: bool = Field(..., description="True for the unconfigured profile.")
    is_active: bool = Field(..., description="True if this profile is active.")


class ProfileListResponse(BaseModel):
    """List of all profiles with active profile indicated."""

    active_profile: str = Field(..., description="Name of the active profile.")
    profiles: list[ProfileMetadataResponse] = Field(
        ..., description="All profiles.",
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
    is_builtin: bool = Field(..., description="True for the unconfigured profile.")
    is_active: bool = Field(..., description="True if this profile is active.")


class CreateProfileRequest(BaseModel):
    """Request body for creating a new profile."""

    name: str = Field(
        ...,
        description="Profile name (2-50 chars, lowercase alphanumeric + hyphens).",
    )
    platform_type: PlatformType = Field(..., description="Platform adapter type.")
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

    platform_type: PlatformType = Field(..., description="Platform adapter type.")
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
