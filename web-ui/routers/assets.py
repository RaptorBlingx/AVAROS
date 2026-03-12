"""Platform-agnostic asset discovery and mapping APIs."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from dependencies import get_adapter_factory, get_settings_service
from skill.adapters.factory import AdapterFactory
from skill.domain.exceptions import ValidationError
from skill.domain.models import Asset, CanonicalMetric
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1", tags=["assets"])
logger = logging.getLogger(__name__)
_CANONICAL_METRICS = {metric.value for metric in CanonicalMetric}


class AssetItem(BaseModel):
    """Transport model for discovered/configured assets."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetDiscoveryResponse(BaseModel):
    """Unified discovery payload for all platform types."""

    platform_type: str
    supports_discovery: bool
    assets: list[AssetItem] = Field(default_factory=list)
    existing_mappings: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AssetMappingsRequest(BaseModel):
    """Save payload for profile-scoped asset mappings."""

    asset_mappings: dict[str, dict[str, Any]]


class AssetMappingsResponse(BaseModel):
    """Response model for profile-scoped asset mappings."""

    asset_mappings: dict[str, dict[str, Any]]


class GeneratorMappingRequest(BaseModel):
    """Accept mapping_output.json format from Reneryo data generator.

    Generator outputs: ``{metric_name: {asset_id: resource_id}}``.
    This endpoint transforms and merges it into SettingsService
    asset mappings as ``{asset_id: {"metric_resources": {metric: rid}}}``.
    """

    mapping: dict[str, dict[str, str]]


class GeneratorMappingResponse(BaseModel):
    """Result of importing generator mapping into asset mappings."""

    imported_metrics: int
    imported_resources: int
    asset_mappings: dict[str, dict[str, Any]]


def _transform_generator_mapping(
    generator_mapping: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Invert generator mapping to per-asset metric_resources dict.

    Args:
        generator_mapping: ``{metric_name: {asset_id: resource_id}}``

    Returns:
        ``{asset_id: {metric_name: resource_id}}`` (inner dict only,
        caller wraps in ``metric_resources`` key).
    """
    per_asset: dict[str, dict[str, str]] = {}
    for metric_name, asset_map in generator_mapping.items():
        if not isinstance(asset_map, dict):
            continue
        for asset_id, resource_id in asset_map.items():
            if not isinstance(resource_id, str) or not resource_id.strip():
                continue
            per_asset.setdefault(asset_id, {})[metric_name] = resource_id.strip()
    return per_asset


def _reject_unknown_metrics(generator_mapping: dict[str, dict[str, str]]) -> None:
    """Reject generator mappings containing non-canonical metric names."""
    unknown = sorted(
        metric_name
        for metric_name in generator_mapping
        if metric_name not in _CANONICAL_METRICS
    )
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unknown metric names: {', '.join(unknown)}. "
                f"Valid metrics: {', '.join(sorted(_CANONICAL_METRICS))}"
            ),
        )


def _merge_generator_mapping(
    existing: dict[str, dict[str, Any]],
    per_asset: dict[str, dict[str, str]],
) -> int:
    """Merge per-asset metric_resources into existing asset mappings."""
    total_resources = 0
    for asset_id, metric_resources in per_asset.items():
        entry = existing.get(asset_id, {})
        old_resources = entry.get("metric_resources", {})
        if not isinstance(old_resources, dict):
            old_resources = {}
        entry["metric_resources"] = {**old_resources, **metric_resources}
        existing[asset_id] = entry
        total_resources += len(metric_resources)
    return total_resources


def _serialize_asset(asset: Asset) -> AssetItem:
    """Convert domain Asset model to API transport model."""
    return AssetItem(
        asset_id=asset.asset_id,
        display_name=asset.display_name,
        asset_type=asset.asset_type,
        aliases=asset.aliases,
        metadata=asset.metadata,
    )


def _get_current_platform(settings_service: SettingsService) -> str:
    """Resolve active profile platform type."""
    profile_name = settings_service.get_active_profile_name()
    profile = settings_service.get_profile(profile_name)
    if profile is None:
        return "mock"
    return str(profile.platform_type or "mock").lower()


def _persist_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService,
) -> AssetMappingsResponse:
    """Save mappings via SettingsService (which handles bus notification)."""
    try:
        _validate_asset_mappings(payload.asset_mappings)
        settings_service.set_asset_mappings(payload.asset_mappings)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


def _validate_asset_mappings(mappings: dict[str, Any]) -> None:
    """Reject empty or structurally invalid asset mappings."""
    for asset_id, mapping in mappings.items():
        if not isinstance(mapping, dict) or not mapping:
            raise ValidationError(
                f"Asset '{asset_id}' has an empty mapping. "
                "At minimum, provide a display_name.",
            )


@router.get("/assets/mappings", response_model=AssetMappingsResponse)
def get_asset_mappings(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Legacy endpoint returning current profile asset mappings."""
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


@router.put("/assets/mappings", response_model=AssetMappingsResponse)
def put_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Legacy endpoint for updating profile-scoped asset mappings."""
    return _persist_asset_mappings(payload, settings_service)


@router.get("/config/assets", response_model=AssetMappingsResponse)
def get_config_assets(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Return profile-scoped asset mappings for settings/wizard UI."""
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


@router.post("/config/assets", response_model=AssetMappingsResponse)
def post_config_assets(
    payload: AssetMappingsRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Persist profile-scoped asset mappings for all platform types."""
    return _persist_asset_mappings(payload, settings_service)


@router.get("/assets/discover", response_model=AssetDiscoveryResponse)
async def discover_assets(
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> AssetDiscoveryResponse:
    """Discover assets through active adapter's list_assets() implementation.

    Creates a fresh adapter per call. For MockAdapter this is cheap; for
    ReneryoAdapter it involves HTTP session setup/teardown.  If discovery
    becomes a hot path, consider caching the adapter across requests.
    """
    platform_type = _get_current_platform(settings_service)
    adapter = adapter_factory.create()
    supports_discovery = adapter.supports_asset_discovery()
    discovered_assets: list[Asset] = []

    if supports_discovery:
        try:
            await adapter.initialize()
            discovered_assets = await adapter.list_assets()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Asset discovery failed for '{platform_type}': {exc}",
            ) from exc
        finally:
            try:
                await adapter.shutdown()
            except Exception as exc:  # pragma: no cover - defensive shutdown path
                logger.warning("Adapter shutdown after asset discovery failed: %s", exc)

    items = [_serialize_asset(asset) for asset in discovered_assets if isinstance(asset, Asset)]
    return AssetDiscoveryResponse(
        platform_type=platform_type,
        supports_discovery=supports_discovery,
        assets=items,
        existing_mappings=settings_service.get_asset_mappings(),
    )


@router.post(
    "/assets/import-generator-mapping",
    response_model=GeneratorMappingResponse,
)
def import_generator_mapping(
    payload: GeneratorMappingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> GeneratorMappingResponse:
    """Import Reneryo data generator mapping_output.json into asset mappings.

    Accepts the generator's ``{metric_name: {asset_id: resource_id}}``
    format, transforms it to per-asset ``metric_resources`` dicts, and
    merges into the existing SettingsService asset mappings.

    Existing asset mapping fields (display_name, aliases, etc.) are
    preserved — only ``metric_resources`` is updated/merged.
    """
    _reject_unknown_metrics(payload.mapping)
    per_asset = _transform_generator_mapping(payload.mapping)
    if not per_asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid metric-resource mappings found in payload",
        )

    existing = settings_service.get_asset_mappings()
    total_resources = _merge_generator_mapping(existing, per_asset)

    try:
        settings_service.set_asset_mappings(existing)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    return GeneratorMappingResponse(
        imported_metrics=len(payload.mapping),
        imported_resources=total_resources,
        asset_mappings=settings_service.get_asset_mappings(),
    )
