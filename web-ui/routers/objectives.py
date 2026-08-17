"""Explicit KPI objective configuration API."""

from __future__ import annotations

from dependencies import get_settings_service
from fastapi import APIRouter, Depends, HTTPException, Response, status
from schemas.objectives import KPIObjectiveRequest, KPIObjectiveResponse

from skill.domain.exceptions import ValidationError
from skill.services.settings import SettingsService

router = APIRouter(prefix="/api/v1/config", tags=["objectives"])


@router.get("/objectives", response_model=list[KPIObjectiveResponse])
def list_objectives(
    settings_service: SettingsService = Depends(get_settings_service),
) -> list[KPIObjectiveResponse]:
    return [KPIObjectiveResponse(**row) for row in settings_service.list_kpi_objectives()]


@router.put("/objectives/{metric}/{asset_id}", response_model=KPIObjectiveResponse)
def put_objective(
    metric: str,
    asset_id: str,
    payload: KPIObjectiveRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> KPIObjectiveResponse:
    if payload.metric != metric or payload.asset_id != asset_id:
        raise HTTPException(status_code=422, detail="Path and payload objective scope must match")
    if payload.mode == "threshold" and payload.target_value is None:
        raise HTTPException(status_code=422, detail="threshold objectives require target_value")
    if payload.mode == "improvement_from_baseline" and (
        payload.baseline_value is None or payload.improvement_percent is None
    ):
        raise HTTPException(status_code=422, detail="baseline objectives require baseline_value and improvement_percent")
    try:
        settings_service.set_kpi_objective(metric, asset_id, payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return KPIObjectiveResponse(**payload.model_dump())


@router.delete("/objectives/{metric}/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_objective(
    metric: str,
    asset_id: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> Response:
    if not settings_service.delete_kpi_objective(metric, asset_id):
        raise HTTPException(status_code=404, detail="Objective not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
