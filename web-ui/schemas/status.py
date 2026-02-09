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

