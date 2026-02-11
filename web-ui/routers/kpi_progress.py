"""KPI progress REST API.

Provides baseline management, snapshot recording, progress
computation, and anonymized export for WASABI D3.2.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_kpi_measurement_service
from schemas.kpi_progress import (
    BaselineRequest,
    BaselineResponse,
    KPIProgressResponse,
    SiteProgressResponse,
    SnapshotRequest,
    SnapshotResponse,
)
from skill.domain.exceptions import ConfigurationError
from skill.domain.kpi_baseline import KPIBaseline, KPIProgress, KPISnapshot
from skill.services.kpi_measurement import KPIMeasurementService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi-progress"])


# ── Baseline endpoints ──────────────────────────────────


@router.post("/baseline", response_model=BaselineResponse, status_code=201)
def record_baseline(
    payload: BaselineRequest,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> BaselineResponse:
    """Record or update a KPI baseline (upsert)."""
    baseline = _request_to_baseline(payload)
    row_id = service.record_baseline(baseline)
    return _baseline_response(row_id, baseline)


@router.get("/baseline/{site_id}", response_model=list[BaselineResponse])
def get_baselines(
    site_id: str,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> list[BaselineResponse]:
    """Get all baselines for a site."""
    return [
        _baseline_response(0, bl)
        for bl in service.get_all_baselines(site_id)
    ]


@router.delete("/baseline/{site_id}/{metric}")
def delete_baseline(
    site_id: str, metric: str,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> dict[str, str]:
    """Delete a baseline by site and metric."""
    if not service.delete_baseline(metric, site_id):
        raise HTTPException(status_code=404, detail="Baseline not found")
    return {"status": "deleted", "metric": metric, "site_id": site_id}


# ── Snapshot endpoints ───────────────────────────────────


@router.post("/snapshot", response_model=SnapshotResponse, status_code=201)
def record_snapshot(
    payload: SnapshotRequest,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> SnapshotResponse:
    """Record a KPI measurement snapshot."""
    snapshot = _request_to_snapshot(payload)
    row_id = service.record_snapshot(snapshot)
    return _snapshot_response(row_id, snapshot)


@router.get(
    "/snapshots/{site_id}/{metric}",
    response_model=list[SnapshotResponse],
)
def get_snapshots(
    site_id: str, metric: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> list[SnapshotResponse]:
    """Get snapshots for a metric at a site."""
    return [
        _snapshot_response(0, s)
        for s in service.get_snapshots(metric, site_id, start_date, end_date)
    ]


# ── Progress endpoints ───────────────────────────────────


@router.get("/progress/{site_id}", response_model=SiteProgressResponse)
def get_site_progress(
    site_id: str,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> SiteProgressResponse:
    """Get progress for all baselined metrics using latest snapshots."""
    baselines = service.get_all_baselines(site_id)
    current_values = _latest_snapshot_values(service, site_id, baselines)
    progress_list = service.get_all_progress(site_id, current_values)
    return _site_progress_response(site_id, baselines, progress_list)


@router.get(
    "/progress/{site_id}/{metric}",
    response_model=KPIProgressResponse,
)
def get_metric_progress(
    site_id: str, metric: str,
    current_value: float = Query(...),
    current_unit: str = Query(...),
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> KPIProgressResponse:
    """Get progress for a single metric with explicit current value."""
    try:
        progress = service.compute_progress(
            metric, site_id, current_value, current_unit,
        )
    except ConfigurationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _progress_response(progress)


# ── Export endpoint ──────────────────────────────────────


@router.get("/export/{site_id}")
def export_kpi_dataset(
    site_id: str,
    service: KPIMeasurementService = Depends(get_kpi_measurement_service),
) -> list[dict]:
    """Export anonymized KPI dataset for WASABI D3.2."""
    return service.export_kpi_dataset(site_id)


# ── Helpers ──────────────────────────────────────────────


def _request_to_baseline(payload: BaselineRequest) -> KPIBaseline:
    """Convert API request to domain KPIBaseline."""
    return KPIBaseline(
        metric=payload.metric,
        site_id=payload.site_id,
        baseline_value=payload.value,
        unit=payload.unit,
        recorded_at=datetime.now(timezone.utc),
        period_start=payload.period_start,
        period_end=payload.period_end,
        notes=payload.notes,
    )


def _request_to_snapshot(payload: SnapshotRequest) -> KPISnapshot:
    """Convert API request to domain KPISnapshot."""
    return KPISnapshot(
        metric=payload.metric,
        site_id=payload.site_id,
        value=payload.value,
        unit=payload.unit,
        measured_at=datetime.now(timezone.utc),
        period_start=payload.period_start,
        period_end=payload.period_end,
    )


def _baseline_response(
    row_id: int, bl: KPIBaseline,
) -> BaselineResponse:
    """Build API response from domain baseline."""
    return BaselineResponse(
        id=row_id, metric=bl.metric, site_id=bl.site_id,
        baseline_value=bl.baseline_value, unit=bl.unit,
        recorded_at=bl.recorded_at,
        period_start=bl.period_start, period_end=bl.period_end,
        notes=bl.notes,
    )


def _snapshot_response(
    row_id: int, snap: KPISnapshot,
) -> SnapshotResponse:
    """Build API response from domain snapshot."""
    return SnapshotResponse(
        id=row_id, metric=snap.metric, site_id=snap.site_id,
        value=snap.value, unit=snap.unit,
        measured_at=snap.measured_at,
        period_start=snap.period_start, period_end=snap.period_end,
    )


def _progress_response(p: KPIProgress) -> KPIProgressResponse:
    """Build API response from domain progress."""
    return KPIProgressResponse(
        metric=p.metric, site_id=p.site_id,
        baseline_value=p.baseline_value, current_value=p.current_value,
        target_percent=p.target_percent,
        improvement_percent=p.improvement_percent,
        target_met=p.target_met, unit=p.unit,
        baseline_date=p.baseline_date, current_date=p.current_date,
        direction=p.direction,
    )


def _latest_snapshot_values(
    service: KPIMeasurementService,
    site_id: str,
    baselines: list[KPIBaseline],
) -> dict[str, tuple[float, str]]:
    """Get latest snapshot value for each baselined metric."""
    values: dict[str, tuple[float, str]] = {}
    for bl in baselines:
        snapshots = service.get_snapshots(bl.metric, site_id)
        if snapshots:
            latest = snapshots[-1]
            values[bl.metric] = (latest.value, latest.unit)
    return values


def _site_progress_response(
    site_id: str,
    baselines: list[KPIBaseline],
    progress_list: list[KPIProgress],
) -> SiteProgressResponse:
    """Build aggregated site progress response."""
    met = sum(1 for p in progress_list if p.target_met)
    return SiteProgressResponse(
        site_id=site_id,
        baselines_count=len(baselines),
        targets_met=met,
        targets_total=len(progress_list),
        progress=[_progress_response(p) for p in progress_list],
    )
