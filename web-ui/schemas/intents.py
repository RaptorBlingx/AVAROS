"""Request and response schemas for intent activation APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentStateResponse(BaseModel):
    """Single intent activation state with metric dependency info."""

    intent_name: str = Field(
        ...,
        description="Intent identifier (e.g., kpi.energy.per_unit).",
    )
    active: bool = Field(
        ...,
        description="Whether the intent is currently active.",
    )
    required_metrics: list[str] = Field(
        ...,
        description="Canonical metric names this intent depends on.",
    )
    metrics_mapped: bool = Field(
        ...,
        description="True when all required metrics have stored mappings.",
    )
    category: Literal["kpi", "action", "system"] = Field(
        default="kpi",
        description="Intent category: kpi, action, or system.",
    )


class IntentListResponse(BaseModel):
    """List of all intents with aggregate counts."""

    intents: list[IntentStateResponse] = Field(
        ...,
        description="All known intents with their states.",
    )
    total: int = Field(
        ...,
        description="Total number of known intents.",
    )
    active_count: int = Field(
        ...,
        description="Number of currently active intents.",
    )


class IntentToggleRequest(BaseModel):
    """Payload for toggling an intent's activation state."""

    active: bool = Field(
        ...,
        description="New activation state for the intent.",
    )
