"""Response schemas for PREVENTION analytics endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PreventionStatusResponse(BaseModel):
    """PREVENTION integration status."""

    enabled: bool = Field(
        ..., description="Whether PREVENTION integration is enabled.",
    )
    prevention_url: str = Field(
        ..., description="Configured PREVENTION GraphQL base URL.",
    )
    addon_name: str = Field(
        ..., description="PREVENTION addon name for AVAROS.",
    )
