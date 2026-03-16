"""Platform-agnostic asset discovery and mapping APIs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

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
_SORTED_CANONICAL_METRICS = sorted(_CANONICAL_METRICS)


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
    discovery_source: Literal["adapter", "registered", "none"] = "none"
    assets: list[AssetItem] = Field(default_factory=list)
    registered_assets: list[AssetItem] = Field(default_factory=list)
    discovery_error: str = ""
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


class AssetLinkingItem(BaseModel):
    """Asset-level resource-linking status for wizard steps."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = Field(default_factory=list)
    source: Literal["imported", "registered", "discovered"]
    linked_metrics: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    linked_metric_count: int = 0
    total_metrics: int = 0


class MetricCoverageItem(BaseModel):
    """Coverage summary for a canonical metric across imported assets."""

    metric_name: str
    linked_assets: int
    total_assets: int
    missing_assets: list[str] = Field(default_factory=list)


class AssetLinkingSummaryResponse(BaseModel):
    """Aggregated linking truth used by wizard Step 3/4/5."""

    platform_type: str
    supports_discovery: bool
    discovery_source: Literal["adapter", "registered", "none"] = "none"
    discovery_error: str = ""
    canonical_metrics: list[str] = Field(default_factory=list)
    imported_assets: list[AssetLinkingItem] = Field(default_factory=list)
    unlinked_assets: list[AssetLinkingItem] = Field(default_factory=list)
    discovered_assets: list[AssetLinkingItem] = Field(default_factory=list)
    metric_coverage: list[MetricCoverageItem] = Field(default_factory=list)


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


def _normalize_asset_key(value: str) -> str:
    """Normalize asset keys for cross-source dedupe."""
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _normalize_aliases(raw: Any) -> list[str]:
    """Normalize aliases into non-empty trimmed list."""
    if not isinstance(raw, list):
        return []
    aliases: list[str] = []
    for alias in raw:
        normalized = str(alias).strip()
        if normalized:
            aliases.append(normalized)
    return aliases


def _normalize_metric_resources(mapping: dict[str, Any]) -> dict[str, str]:
    """Return canonical metric->resource mapping with non-empty values."""
    raw_resources = mapping.get("metric_resources", {})
    if not isinstance(raw_resources, dict):
        return {}
    normalized: dict[str, str] = {}
    for metric_name, resource_id in raw_resources.items():
        if metric_name not in _CANONICAL_METRICS:
            continue
        resource = str(resource_id).strip()
        if resource:
            normalized[metric_name] = resource
    return normalized


def _build_asset_linking_item(
    *,
    asset_id: str,
    display_name: str,
    asset_type: str,
    aliases: list[str],
    source: Literal["imported", "registered", "discovered"],
    linked_metrics: list[str],
) -> AssetLinkingItem:
    """Build a linking item with derived missing/coverage fields."""
    linked_sorted = sorted(set(linked_metrics))
    missing = [metric for metric in _SORTED_CANONICAL_METRICS if metric not in linked_sorted]
    return AssetLinkingItem(
        asset_id=asset_id,
        display_name=display_name,
        asset_type=asset_type,
        aliases=aliases,
        source=source,
        linked_metrics=linked_sorted,
        missing_metrics=missing,
        linked_metric_count=len(linked_sorted),
        total_metrics=len(_SORTED_CANONICAL_METRICS),
    )


def _build_mapping_linking_groups(
    mappings: dict[str, dict[str, Any]],
) -> tuple[list[AssetLinkingItem], list[AssetLinkingItem]]:
    """Split stored mappings into imported vs unlinked groups."""
    imported: list[AssetLinkingItem] = []
    unlinked: list[AssetLinkingItem] = []
    for asset_id in sorted(mappings.keys()):
        mapping = mappings.get(asset_id, {})
        if not isinstance(mapping, dict):
            continue
        linked_metrics = list(_normalize_metric_resources(mapping).keys())
        item = _build_asset_linking_item(
            asset_id=asset_id,
            display_name=str(mapping.get("display_name") or asset_id),
            asset_type=str(mapping.get("asset_type") or "machine"),
            aliases=_normalize_aliases(mapping.get("aliases")),
            source="imported" if linked_metrics else "registered",
            linked_metrics=linked_metrics,
        )
        if linked_metrics:
            imported.append(item)
        else:
            unlinked.append(item)
    return imported, unlinked


def _build_metric_coverage(
    imported_assets: list[AssetLinkingItem],
) -> list[MetricCoverageItem]:
    """Build per-metric coverage over imported assets."""
    total_assets = len(imported_assets)
    if total_assets == 0:
        return [
            MetricCoverageItem(
                metric_name=metric_name,
                linked_assets=0,
                total_assets=0,
                missing_assets=[],
            )
            for metric_name in _SORTED_CANONICAL_METRICS
        ]

    coverage: list[MetricCoverageItem] = []
    for metric_name in _SORTED_CANONICAL_METRICS:
        linked_assets = [
            asset.asset_id
            for asset in imported_assets
            if metric_name in asset.linked_metrics
        ]
        missing_assets = [
            asset.asset_id
            for asset in imported_assets
            if metric_name not in asset.linked_metrics
        ]
        coverage.append(
            MetricCoverageItem(
                metric_name=metric_name,
                linked_assets=len(linked_assets),
                total_assets=total_assets,
                missing_assets=missing_assets,
            ),
        )
    return coverage


def _build_discovered_linking_items(
    discovered_assets: list[Asset],
    existing_asset_ids: set[str],
) -> list[AssetLinkingItem]:
    """Convert adapter-discovered assets into deduplicated diagnostic items."""
    items: list[AssetLinkingItem] = []
    seen: set[str] = set()
    for discovered in discovered_assets:
        if not isinstance(discovered, Asset):
            continue
        normalized = _normalize_asset_key(discovered.asset_id)
        if not normalized:
            continue
        if normalized in existing_asset_ids or normalized in seen:
            continue
        seen.add(normalized)
        items.append(
            _build_asset_linking_item(
                asset_id=discovered.asset_id,
                display_name=discovered.display_name,
                asset_type=discovered.asset_type,
                aliases=discovered.aliases,
                source="discovered",
                linked_metrics=[],
            ),
        )
    return items


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
    """Save mappings via SettingsService (which handles bus notification).

    Preserve previously imported ``metric_resources`` when UI payloads
    update only registration/linking fields (for example ``seu_id``).
    """
    try:
        _validate_asset_mappings(payload.asset_mappings)
        existing = settings_service.get_asset_mappings()
        merged = _merge_with_existing_metric_resources(
            incoming=payload.asset_mappings,
            existing=existing,
        )
        settings_service.set_asset_mappings(merged)
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


def _merge_with_existing_metric_resources(
    *,
    incoming: dict[str, dict[str, Any]],
    existing: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge incoming mappings while preserving existing metric resources.

    Frontend asset editors may submit asset rows without ``metric_resources``.
    Without this merge, imported generator mappings are unintentionally lost.
    """
    merged: dict[str, dict[str, Any]] = {}
    for asset_id, incoming_mapping in incoming.items():
        current = existing.get(asset_id, {})
        next_mapping = dict(incoming_mapping)

        if "metric_resources" not in next_mapping:
            existing_resources = current.get("metric_resources")
            if isinstance(existing_resources, dict) and existing_resources:
                next_mapping["metric_resources"] = dict(existing_resources)

        merged[asset_id] = next_mapping
    return merged


def _serialize_registered_assets(
    mappings: dict[str, dict[str, Any]],
) -> list[AssetItem]:
    """Convert stored asset mapping rows to AssetItem list."""
    items: list[AssetItem] = []
    for asset_id in sorted(mappings.keys()):
        mapping = mappings.get(asset_id, {})
        if not isinstance(mapping, dict):
            continue
        aliases_raw = mapping.get("aliases", [])
        aliases = (
            [str(alias).strip() for alias in aliases_raw if str(alias).strip()]
            if isinstance(aliases_raw, list)
            else []
        )
        metadata_raw = mapping.get("metadata", {})
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        items.append(
            AssetItem(
                asset_id=asset_id,
                display_name=str(mapping.get("display_name") or asset_id),
                asset_type=str(mapping.get("asset_type") or "machine"),
                aliases=aliases,
                metadata=metadata,
            ),
        )
    return items


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
    existing_mappings = settings_service.get_asset_mappings()
    registered_assets = _serialize_registered_assets(existing_mappings)
    adapter = adapter_factory.create()
    supports_discovery = adapter.supports_asset_discovery()
    discovered_assets: list[Asset] = []
    discovery_source: Literal["adapter", "registered", "none"] = (
        "registered" if registered_assets else "none"
    )

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
    if items:
        discovery_source = "adapter"
    return AssetDiscoveryResponse(
        platform_type=platform_type,
        supports_discovery=supports_discovery,
        discovery_source=discovery_source,
        assets=items,
        registered_assets=registered_assets,
        existing_mappings=existing_mappings,
    )


@router.get("/assets/linking-summary", response_model=AssetLinkingSummaryResponse)
async def get_asset_linking_summary(
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> AssetLinkingSummaryResponse:
    """Return a unified RENERYO-friendly linking summary for wizard steps."""
    platform_type = _get_current_platform(settings_service)
    mappings = settings_service.get_asset_mappings()
    imported_assets, unlinked_assets = _build_mapping_linking_groups(mappings)
    metric_coverage = _build_metric_coverage(imported_assets)

    supports_discovery = False
    discovery_source: Literal["adapter", "registered", "none"] = (
        "registered" if imported_assets or unlinked_assets else "none"
    )
    discovery_error = ""
    discovered_items: list[AssetLinkingItem] = []

    adapter = adapter_factory.create()
    supports_discovery = adapter.supports_asset_discovery()
    if supports_discovery:
        try:
            await asyncio.wait_for(adapter.initialize(), timeout=5.0)
            discovered_assets = await asyncio.wait_for(
                adapter.list_assets(),
                timeout=12.0,
            )
            existing_asset_ids = {
                _normalize_asset_key(asset.asset_id)
                for asset in imported_assets + unlinked_assets
            }
            discovered_items = _build_discovered_linking_items(
                discovered_assets if isinstance(discovered_assets, list) else [],
                existing_asset_ids,
            )
            if discovered_items:
                discovery_source = "adapter"
        except Exception as exc:  # noqa: BLE001 - endpoint degrades by design
            discovery_error = str(exc)
            logger.warning("Asset linking summary discovery failed: %s", exc)
        finally:
            try:
                await asyncio.wait_for(adapter.shutdown(), timeout=5.0)
            except Exception as exc:  # pragma: no cover - defensive cleanup
                logger.warning("Adapter shutdown for linking summary failed: %s", exc)

    return AssetLinkingSummaryResponse(
        platform_type=platform_type,
        supports_discovery=supports_discovery,
        discovery_source=discovery_source,
        discovery_error=discovery_error,
        canonical_metrics=_SORTED_CANONICAL_METRICS,
        imported_assets=imported_assets,
        unlinked_assets=unlinked_assets,
        discovered_assets=discovered_items,
        metric_coverage=metric_coverage,
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
