"""Metric mapping CRUD API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from dependencies import get_settings_service
from schemas.metrics import (
    CANONICAL_METRIC_VALUES,
    MetricMappingListResponse,
    MetricMappingRequest,
    MetricMappingResponse,
    MetricMappingTestRequest,
    MetricMappingTestResponse,
)
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric
from skill.services.settings import SettingsService
from services.metric_test_service import run_metric_mapping_test


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


def _requires_secret_resolution(token: str) -> bool:
    """Return True when frontend token is empty or masked."""
    trimmed = token.strip()
    return not trimmed or trimmed.startswith("****")


def _to_response(
    metric_name: str,
    mapping: dict,
    *,
    source: str = "manual",
) -> MetricMappingResponse:
    """Convert stored mapping dict to API response model."""
    return MetricMappingResponse(
        canonical_metric=metric_name,
        endpoint=str(mapping.get("endpoint", "")),
        json_path=str(mapping.get("json_path", "")),
        unit=str(mapping.get("unit", "")),
        transform=mapping.get("transform"),
        source=source,
    )


_METRIC_RESOURCE_ENDPOINT = "/api/u/measurement/metric/resource/{resource_id}/values"
_METRIC_RESOURCE_JSON_PATH = "$.records[*].value"


def _derive_auto_metrics(
    settings_service: SettingsService,
) -> list[MetricMappingResponse]:
    """Derive metric mappings from asset_mappings metric_resources.

    Scans all configured assets for their metric_resources entries
    and creates read-only (source='auto') mapping rows.
    """
    mappings = settings_service.get_asset_mappings()
    seen_metrics: dict[str, str] = {}  # metric -> first resource_id
    for _asset_id, asset_data in mappings.items():
        if not isinstance(asset_data, dict):
            continue
        resources = asset_data.get("metric_resources", {})
        if not isinstance(resources, dict):
            continue
        for metric_name, resource_id in resources.items():
            if metric_name not in seen_metrics:
                seen_metrics[metric_name] = str(resource_id)
    items: list[MetricMappingResponse] = []
    for metric_name, resource_id in sorted(seen_metrics.items()):
        if metric_name not in CANONICAL_METRIC_VALUES:
            continue
        try:
            cm = CanonicalMetric(metric_name)
            unit = cm.default_unit
        except ValueError:
            unit = ""
        items.append(
            MetricMappingResponse(
                canonical_metric=metric_name,
                endpoint=_METRIC_RESOURCE_ENDPOINT.format(resource_id=resource_id),
                json_path=_METRIC_RESOURCE_JSON_PATH,
                unit=unit,
                source="auto",
            ),
        )
    return items


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
    """Return all configured metric mappings.

    Manual mappings (set by user) take priority. For metrics without a manual
    mapping, auto-derived entries from asset_mappings metric_resources are
    appended so the UI always shows what is configured.
    """
    data = settings_service.list_metric_mappings()
    manual_items = [
        _to_response(metric_name, mapping, source="manual")
        for metric_name, mapping in data.items()
    ]
    manual_names = {item.canonical_metric for item in manual_items}
    auto_items = [
        item
        for item in _derive_auto_metrics(settings_service)
        if item.canonical_metric not in manual_names
    ]
    return MetricMappingListResponse(root=manual_items + auto_items)


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


@router.post("/metrics/test", response_model=MetricMappingTestResponse)
async def test_metric_mapping(
    payload: MetricMappingTestRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> MetricMappingTestResponse:
    """Test metric endpoint + JSON path resolution with one sample request."""
    if _requires_secret_resolution(payload.auth_token):
        active_config = settings_service.get_platform_config()
        payload = payload.model_copy(update={"auth_token": active_config.api_key})
    return await run_metric_mapping_test(payload)
