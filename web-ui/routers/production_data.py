"""Production data REST API.

Provides CRUD and CSV upload for supplementary manufacturing data
(production counts, material consumed, quality data).
"""

from __future__ import annotations

import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from dependencies import get_production_data_service
from schemas.production_data import (
    CsvUploadResponse,
    ProductionRecordListResponse,
    ProductionRecordRequest,
    ProductionRecordResponse,
    ProductionSummaryResponse,
)
from skill.domain.production import ProductionRecord
from skill.services.csv_parser import parse_production_csv
from skill.services.production_data import ProductionDataService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/production-data",
    tags=["production-data"],
)


# ── Template ─────────────────────────────────────────────

CSV_TEMPLATE = (
    "date,asset_id,production_count,good_count,"
    "material_consumed_kg,shift,batch_id,notes\n"
    "2026-01-15,Line-1,500,485,120.5,morning,B-2026-001,"
    "Normal operation\n"
    "2026-01-15,Line-1,480,470,115.0,afternoon,B-2026-002,"
    "Minor tool wear\n"
    "2026-01-16,Line-2,600,590,140.0,morning,B-2026-003,\n"
)


@router.get("/template")
def download_csv_template() -> StreamingResponse:
    """Return a CSV template with headers and sample rows."""
    return StreamingResponse(
        io.BytesIO(CSV_TEMPLATE.encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=production_data_template.csv"
            ),
        },
    )


# ── Single record CRUD ──────────────────────────────────


@router.post("", response_model=ProductionRecordResponse, status_code=201)
def add_production_record(
    payload: ProductionRecordRequest,
    service: ProductionDataService = Depends(get_production_data_service),
) -> ProductionRecordResponse:
    """Add a single production data record."""
    try:
        record = _request_to_domain(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    record_id = service.add_record(record)
    return _build_response(record_id, record)


@router.delete("/{record_id}")
def delete_production_record(
    record_id: int,
    service: ProductionDataService = Depends(get_production_data_service),
) -> dict[str, str]:
    """Delete a single production record by ID."""
    deleted = service.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted", "id": str(record_id)}


# ── CSV bulk upload ──────────────────────────────────────


@router.post("/bulk", response_model=CsvUploadResponse)
async def upload_production_csv(
    file: UploadFile = File(...),
    service: ProductionDataService = Depends(get_production_data_service),
) -> CsvUploadResponse:
    """Upload a CSV file with production data."""
    content = await file.read()
    result = parse_production_csv(content)

    inserted = 0
    if result.records:
        inserted = service.add_records_bulk(list(result.records))

    return CsvUploadResponse(
        total_rows=result.total_rows,
        valid_rows=result.valid_rows,
        inserted=inserted,
        errors=[
            {"row": e.row_num, "column": e.column, "message": e.message}
            for e in result.errors
        ],
    )


# ── Query / List ─────────────────────────────────────────


@router.get("", response_model=ProductionRecordListResponse)
def list_production_records(
    asset_id: str | None = Query(None, description="Filter by asset"),
    start_date: date | None = Query(None, description="Start date"),
    end_date: date | None = Query(None, description="End date"),
    service: ProductionDataService = Depends(get_production_data_service),
) -> ProductionRecordListResponse:
    """List production records with optional filters."""
    rows = service.get_records_with_ids(
        asset_id=asset_id,
        start_date=start_date,
        end_date=end_date,
    )
    response_records = [
        _build_response(row_id, record)
        for row_id, record in rows
    ]
    return ProductionRecordListResponse(
        records=response_records, total=len(response_records),
    )


# ── Summary / Aggregation ───────────────────────────────


@router.get("/summary", response_model=ProductionSummaryResponse)
def get_production_summary(
    asset_id: str = Query(..., description="Asset identifier"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    service: ProductionDataService = Depends(get_production_data_service),
) -> ProductionSummaryResponse:
    """Get aggregated production summary for a period."""
    summary = service.get_production_summary(
        asset_id=asset_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ProductionSummaryResponse(
        asset_id=asset_id,
        start_date=start_date,
        end_date=end_date,
        total_produced=summary.total_produced,
        total_good=summary.total_good,
        total_material_kg=summary.total_material_kg,
        record_count=summary.record_count,
        material_efficiency_pct=summary.material_efficiency,
    )


# ── Helpers ──────────────────────────────────────────────


def _request_to_domain(
    payload: ProductionRecordRequest,
) -> ProductionRecord:
    """Convert API request to domain model.

    Args:
        payload: Pydantic request model.

    Returns:
        Validated ProductionRecord domain object.

    Raises:
        ValueError: If domain validation fails.
    """
    return ProductionRecord(
        record_date=payload.record_date,
        asset_id=payload.asset_id,
        production_count=payload.production_count,
        good_count=payload.good_count,
        material_consumed_kg=payload.material_consumed_kg,
        shift=payload.shift,
        batch_id=payload.batch_id,
        notes=payload.notes,
    )


def _build_response(
    record_id: int, record: ProductionRecord,
) -> ProductionRecordResponse:
    """Build API response from domain model.

    Args:
        record_id: Database row ID.
        record: Domain production record.

    Returns:
        Pydantic response model.
    """
    return ProductionRecordResponse(
        id=record_id,
        record_date=record.record_date,
        asset_id=record.asset_id,
        production_count=record.production_count,
        good_count=record.good_count,
        material_consumed_kg=record.material_consumed_kg,
        shift=record.shift,
        batch_id=record.batch_id,
        notes=record.notes,
    )
