"""Request and response schemas for production data API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ProductionRecordRequest(BaseModel):
    """Create a single production data record."""

    record_date: date = Field(
        ..., description="Date this entry covers (YYYY-MM-DD).",
    )
    asset_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Machine/line identifier.",
    )
    production_count: int = Field(
        ..., ge=0, description="Total units produced.",
    )
    good_count: int = Field(
        ..., ge=0, description="Units passing QC.",
    )
    material_consumed_kg: float = Field(
        ..., ge=0.0, description="Raw material input in kg.",
    )
    shift: str = Field(
        default="", max_length=50, description="Shift label.",
    )
    batch_id: str = Field(
        default="", max_length=100, description="Batch reference.",
    )
    notes: str = Field(
        default="", max_length=500, description="Operator notes.",
    )


class ProductionRecordResponse(BaseModel):
    """Single production data record (from DB)."""

    id: int
    record_date: date
    asset_id: str
    production_count: int
    good_count: int
    material_consumed_kg: float
    shift: str = ""
    batch_id: str = ""
    notes: str = ""
    created_at: datetime | None = None


class ProductionRecordListResponse(BaseModel):
    """Paginated list of production records."""

    records: list[ProductionRecordResponse]
    total: int


class CsvUploadResponse(BaseModel):
    """Result of a CSV bulk upload."""

    total_rows: int
    valid_rows: int
    inserted: int
    errors: list[dict]


class ProductionSummaryResponse(BaseModel):
    """Aggregated production data for a date range."""

    asset_id: str
    start_date: date
    end_date: date
    total_produced: int
    total_good: int
    total_material_kg: float
    record_count: int
    material_efficiency_pct: float
