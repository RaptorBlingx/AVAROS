"""Request and response schemas for KPI progress API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class BaselineRequest(BaseModel):
    """Create or update a KPI baseline."""

    metric: str = Field(
        ..., min_length=1, max_length=100,
        description="Canonical metric name (e.g. energy_per_unit).",
    )
    site_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Pilot site identifier.",
    )
    value: float = Field(
        ..., description="Baseline measurement value.",
    )
    unit: str = Field(
        ..., min_length=1, max_length=50,
        description="Engineering unit (e.g. kWh/unit).",
    )
    period_start: date = Field(
        ..., description="Measurement period start.",
    )
    period_end: date = Field(
        ..., description="Measurement period end.",
    )
    notes: str = Field(
        default="", max_length=500,
        description="Optional notes about the baseline.",
    )


class BaselineResponse(BaseModel):
    """Recorded KPI baseline."""

    id: int
    metric: str
    site_id: str
    baseline_value: float
    unit: str
    recorded_at: datetime
    period_start: date
    period_end: date
    notes: str = ""


class SnapshotRequest(BaseModel):
    """Record a KPI measurement snapshot."""

    metric: str = Field(
        ..., min_length=1, max_length=100,
        description="Canonical metric name.",
    )
    site_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Pilot site identifier.",
    )
    value: float = Field(
        ..., description="Measured value.",
    )
    unit: str = Field(
        ..., min_length=1, max_length=50,
        description="Engineering unit.",
    )
    period_start: date = Field(
        ..., description="Measurement period start.",
    )
    period_end: date = Field(
        ..., description="Measurement period end.",
    )


class SnapshotResponse(BaseModel):
    """Recorded KPI snapshot."""

    id: int
    metric: str
    site_id: str
    value: float
    unit: str
    measured_at: datetime
    period_start: date
    period_end: date


class KPIProgressResponse(BaseModel):
    """Progress toward a WASABI KPI target."""

    metric: str
    site_id: str
    baseline_value: float
    current_value: float
    target_percent: float
    improvement_percent: float
    target_met: bool
    unit: str
    baseline_date: datetime
    current_date: datetime
    direction: str


class SiteProgressResponse(BaseModel):
    """Aggregated KPI progress for a site."""

    site_id: str
    baselines_count: int
    targets_met: int
    targets_total: int
    progress: list[KPIProgressResponse]
