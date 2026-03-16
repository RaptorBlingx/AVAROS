"""Response schema for system status endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    """System status details for configuration and readiness checks."""

    configured: bool = Field(
        ..., description="Whether AVAROS is configured with a non-mock platform."
    )
    active_adapter: str = Field(
        ..., description="Currently active adapter identifier."
    )
    platform_type: str = Field(
        ..., description="Configured platform type from persistent settings."
    )
    loaded_intents: int = Field(
        ..., description="Number of .intent files detected in English locale."
    )
    database_connected: bool = Field(
        ..., description="True when SettingsService can initialize database access."
    )
    version: str = Field(
        ..., description="Web UI backend application version."
    )
    live_connection_state: str = Field(
        default="unknown",
        description=(
            "Live platform connection state: healthy, auth_failed, "
            "unreachable, misconfigured, unconfigured, or unknown."
        ),
    )
    live_connection_verified: bool = Field(
        default=False,
        description="True when the active platform connection is verified live.",
    )
    live_connection_message: str = Field(
        default="",
        description="Human-readable message for live connection status.",
    )
    live_connection_error_code: str = Field(
        default="",
        description="Machine-readable error code when live verification fails.",
    )
    live_connection_checked_at: str | None = Field(
        default=None,
        description="ISO timestamp of the latest live connection verification.",
    )
