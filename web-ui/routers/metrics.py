"""Metric mapping CRUD API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from dependencies import get_settings_service
from schemas.metrics import (
    CANONICAL_METRIC_VALUES,
    MetricMappingListResponse,
    MetricMappingRequest,
    MetricMappingResponse,
)
from skill.domain.exceptions import ValidationError
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["metrics"])


def _ensure_valid_metric_name(metric_name: str) -> None:
    """Validate metric_name against canonical metric enum values."""
    if metric_name not in CANONICAL_METRIC_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid canonical metric: {metric_name}",
        )


def _mapping_data(payload: MetricMappingRequest) -> dict[str, str | None]:
    """Extract storage payload for SettingsService mapping methods."""
    return {
        "endpoint": payload.endpoint,
        "json_path": payload.json_path,
        "unit": payload.unit,
        "transform": payload.transform,
    }


def _to_response(metric_name: str, mapping: dict) -> MetricMappingResponse:
    """Convert stored mapping dict to API response model."""
    return MetricMappingResponse(
        canonical_metric=metric_name,
        endpoint=str(mapping.get("endpoint", "")),
        json_path=str(mapping.get("json_path", "")),
        unit=str(mapping.get("unit", "")),
        transform=mapping.get("transform"),
    )


@router.post(
    "/metrics",
    response_model=MetricMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_metric_mapping(
    payload: MetricMappingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> MetricMappingResponse:
    """Create a new metric mapping."""
    try:
        settings_service.set_metric_mapping(
            payload.canonical_metric,
            _mapping_data(payload),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    saved = settings_service.get_metric_mapping(payload.canonical_metric) or {}
    return _to_response(payload.canonical_metric, saved)


@router.get("/metrics", response_model=MetricMappingListResponse)
def list_metric_mappings(
    settings_service: SettingsService = Depends(get_settings_service),
) -> MetricMappingListResponse:
    """Return all configured metric mappings as an array."""
    data = settings_service.list_metric_mappings()
    items = [_to_response(metric_name, mapping) for metric_name, mapping in data.items()]
    return MetricMappingListResponse(root=items)


@router.put("/metrics/{metric_name}", response_model=MetricMappingResponse)
def update_metric_mapping(
    metric_name: str,
    payload: MetricMappingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> MetricMappingResponse:
    """Update an existing metric mapping."""
    _ensure_valid_metric_name(metric_name)

    if payload.canonical_metric != metric_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="canonical_metric in body must match metric_name path parameter",
        )

    existing = settings_service.get_metric_mapping(metric_name)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric mapping not found: {metric_name}",
        )

    try:
        settings_service.set_metric_mapping(metric_name, _mapping_data(payload))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    saved = settings_service.get_metric_mapping(metric_name) or {}
    return _to_response(metric_name, saved)


@router.delete("/metrics/{metric_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric_mapping(
    metric_name: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> Response:
    """Delete a metric mapping."""
    _ensure_valid_metric_name(metric_name)

    deleted = settings_service.delete_metric_mapping(metric_name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric mapping not found: {metric_name}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

