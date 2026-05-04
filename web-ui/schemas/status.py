"""Response schema for system status endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    """System status details for configuration and readiness checks."""

    configured: bool = Field(
        ..., description="Whether AVAROS is configured with a platform."
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
    prevention_mode: str = Field(
        default="unknown",
        description=(
            "Active prevention runtime mode: http, disabled, or unknown."
        ),
    )
    prevention_mode_reason: str = Field(
        default="",
        description="Reason/source for selected prevention mode.",
    )
    prevention_state: str = Field(
        default="unknown",
        description=(
            "Live PREVENTION state: healthy, unreachable, misconfigured, "
            "disabled, or unknown."
        ),
    )
    prevention_verified: bool = Field(
        default=False,
        description="True when the PREVENTION endpoint was verified live.",
    )
    prevention_message: str = Field(
        default="",
        description="Human-readable PREVENTION health message.",
    )
    prevention_checked_at: str | None = Field(
        default=None,
        description="ISO timestamp of the latest PREVENTION health verification.",
    )
    prevention_endpoint: str | None = Field(
        default=None,
        description="Resolved PREVENTION base URL, when configured.",
    )
    prevention_data_state: str = Field(
        default="unknown",
        description="PREVENTION input data freshness: fresh, stale, missing, invalid, or unknown.",
    )
    prevention_data_message: str = Field(
        default="",
        description="Human-readable PREVENTION input data freshness message.",
    )
    prevention_data_updated_at: str | None = Field(
        default=None,
        description="ISO timestamp from the latest PREVENTION export manifest.",
    )
    prevention_data_record_count: int | None = Field(
        default=None,
        description="Record count from the latest PREVENTION export manifest.",
    )
    prevention_analytics_goals: list[str] = Field(
        default_factory=list,
        description="Configured PREVENTION analytics goal identifiers.",
    )
    prevention_analytics_types: list[str] = Field(
        default_factory=list,
        description="Configured PREVENTION analytics types.",
    )
    prevention_descriptive_state: str = Field(
        default="unknown",
        description="Capability state for descriptive anomaly/drift analytics.",
    )
    prevention_predictive_state: str = Field(
        default="unknown",
        description="Capability state for predictive forecasting analytics.",
    )
    prevention_prescriptive_state: str = Field(
        default="not_available",
        description="Capability state for full prescriptive optimization.",
    )
