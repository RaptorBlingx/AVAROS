"""Platform-agnostic asset discovery and mapping APIs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
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
_UUID_ASSET_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_NATIVE_SEU_ENERGY_BINDING: dict[str, dict[str, Any]] = {
    "energy_total": {
        "strategy": "asset_consumption_total",
        "unit": "kWh",
        "trend_supported": False,
        "compare_supported": False,
        "default_period_mode": "aggregate_total",
        "aggregate_start_iso": "2021-02-01T00:00:00.000Z",
    }
}


def _compat_layer_enabled() -> bool:
    """Return True when optional platform compatibility layer is enabled."""
    raw = str(os.environ.get("AVAROS_ENABLE_PLATFORM_COMPAT_LAYER", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


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
    """Accept mapping_output.json format from the data generator.

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


class GeneratorAssetPreviewItem(BaseModel):
    """Read-only generator mapping preview item for wizard registration UX."""

    asset_id: str
    display_name: str
    asset_type: str
    metric_count: int = 0
    metrics: list[str] = Field(default_factory=list)
    source: Literal["generator"] = "generator"


class GeneratorAssetPreviewResponse(BaseModel):
    """Preview payload for mapping_output.json without mutating profile mappings."""

    available: bool
    source_path: str
    imported_metrics: int = 0
    assets: list[GeneratorAssetPreviewItem] = Field(default_factory=list)
    error: str = ""


def _default_generator_mapping_path() -> Path:
    """Return default mapping_output.json path used for RENERYO quick bootstrap."""
    configured = str(os.environ.get("AVAROS_GENERATOR_MAPPING_FILE", "")).strip()
    if configured:
        return Path(configured)
    # assets.py -> web-ui/routers/assets.py -> project root (parents[2])
    return Path(__file__).resolve().parents[2] / "tools" / "reneryo-data-generator" / "mapping_output.json"


def _extract_mapping_payload(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Normalize mapping payload supporting both wrapped and raw formats."""
    candidate = raw.get("mapping", raw)
    if not isinstance(candidate, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for metric_name, asset_map in candidate.items():
        if not isinstance(asset_map, dict):
            continue
        normalized[str(metric_name)] = {
            str(asset_id): str(resource_id)
            for asset_id, resource_id in asset_map.items()
        }
    return normalized


def _to_display_name(asset_id: str) -> str:
    """Convert an asset id into a human-friendly display name."""
    return (
        asset_id.replace("_", " ")
        .replace("-", " ")
        .strip()
        .title()
    ) or asset_id


def _infer_asset_type(asset_id: str) -> str:
    """Infer a pragmatic asset type from common AVAROS ids."""
    normalized = asset_id.lower().replace("_", "-")
    if normalized.startswith("line-"):
        return "line"
    return "machine"


def _build_generator_asset_preview(
    mapping: dict[str, dict[str, str]],
) -> list[GeneratorAssetPreviewItem]:
    """Create per-asset preview rows from generator mapping payload."""
    per_asset = _transform_generator_mapping(mapping)
    rows: list[GeneratorAssetPreviewItem] = []
    for asset_id in sorted(per_asset.keys()):
        metric_names = sorted(set(per_asset.get(asset_id, {}).keys()))
        rows.append(
            GeneratorAssetPreviewItem(
                asset_id=asset_id,
                display_name=_to_display_name(asset_id),
                asset_type=_infer_asset_type(asset_id),
                metric_count=len(metric_names),
                metrics=metric_names,
            ),
        )
    return rows


class AssetLinkingItem(BaseModel):
    """Asset-level resource-linking status for wizard steps."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = Field(default_factory=list)
    source: Literal["imported", "registered", "discovered"]
    mapping_mode: Literal["full_kpi", "energy_only", "registration_only"] = "registration_only"
    mapping_source: Literal["manual", "generator", "live_discovery"] = "manual"
    linked_metrics: list[str] = Field(default_factory=list)
    native_metrics: list[str] = Field(default_factory=list)
    supported_metrics: list[str] = Field(default_factory=list)
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
        if str(entry.get("mapping_source", "")).strip() not in {"manual", "generator", "live_discovery"}:
            entry["mapping_source"] = "generator"
        if str(entry.get("capability_mode", "")).strip() not in {"full_kpi", "energy_only"}:
            entry["capability_mode"] = "full_kpi"
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


def _normalize_native_metric_bindings(
    mapping: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return canonical native metric bindings with dict payloads."""
    raw_bindings = mapping.get("native_metric_bindings", {})
    if not isinstance(raw_bindings, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for metric_name, binding in raw_bindings.items():
        if metric_name not in _CANONICAL_METRICS:
            continue
        if not isinstance(binding, dict):
            continue
        normalized[metric_name] = dict(binding)
    return normalized


def _resolve_mapping_mode(
    mapping: dict[str, Any],
    *,
    linked_metrics: list[str],
    native_metrics: list[str],
) -> Literal["full_kpi", "energy_only", "registration_only"]:
    """Resolve how this mapping should be interpreted by wizard readiness."""
    capability_mode = str(mapping.get("capability_mode", "")).strip().lower()
    if capability_mode == "energy_only":
        return "energy_only"
    if native_metrics and not linked_metrics:
        return "energy_only"
    if linked_metrics:
        return "full_kpi"
    return "registration_only"


def _build_asset_linking_item(
    *,
    asset_id: str,
    display_name: str,
    asset_type: str,
    aliases: list[str],
    source: Literal["imported", "registered", "discovered"],
    mapping_mode: Literal["full_kpi", "energy_only", "registration_only"],
    mapping_source: Literal["manual", "generator", "live_discovery"],
    linked_metrics: list[str],
    native_metrics: list[str],
) -> AssetLinkingItem:
    """Build a linking item with derived missing/coverage fields."""
    linked_sorted = sorted(set(linked_metrics))
    native_sorted = sorted(set(native_metrics))
    supported_metrics = sorted(set(linked_sorted + native_sorted))
    missing = [metric for metric in _SORTED_CANONICAL_METRICS if metric not in linked_sorted]
    return AssetLinkingItem(
        asset_id=asset_id,
        display_name=display_name,
        asset_type=asset_type,
        aliases=aliases,
        source=source,
        mapping_mode=mapping_mode,
        mapping_source=mapping_source,
        linked_metrics=linked_sorted,
        native_metrics=native_sorted,
        supported_metrics=supported_metrics,
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
        native_metrics = list(_normalize_native_metric_bindings(mapping).keys())
        combined_linked = sorted(set(linked_metrics + native_metrics))
        mapping_mode = _resolve_mapping_mode(
            mapping,
            linked_metrics=linked_metrics,
            native_metrics=native_metrics,
        )
        raw_mapping_source = str(mapping.get("mapping_source", "")).strip().lower()
        if raw_mapping_source in {"manual", "generator", "live_discovery"}:
            mapping_source: Literal["manual", "generator", "live_discovery"] = raw_mapping_source  # type: ignore[assignment]
        elif mapping_mode == "energy_only":
            mapping_source = "live_discovery"
        else:
            mapping_source = "manual"
        item = _build_asset_linking_item(
            asset_id=asset_id,
            display_name=str(mapping.get("display_name") or asset_id),
            asset_type=str(mapping.get("asset_type") or "machine"),
            aliases=_normalize_aliases(mapping.get("aliases")),
            source="imported" if combined_linked else "registered",
            mapping_mode=mapping_mode,
            mapping_source=mapping_source,
            linked_metrics=combined_linked,
            native_metrics=native_metrics,
        )
        if combined_linked:
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
                mapping_mode="registration_only",
                mapping_source="live_discovery",
                linked_metrics=[],
                native_metrics=[],
            ),
        )
    return items


def _is_uuid_asset_id(value: str) -> bool:
    """Return True when asset id looks like a RENERYO UUID key."""
    return bool(_UUID_ASSET_ID_PATTERN.match((value or "").strip()))


def _has_linked_metric_resources(mapping: dict[str, Any]) -> bool:
    """Return True when mapping includes any non-empty metric resource id."""
    return bool(_normalize_metric_resources(mapping))


def _promote_discovered_seu_assets_to_energy_only(
    *,
    mappings: dict[str, dict[str, Any]],
    discovered_assets: list[Asset],
) -> tuple[dict[str, dict[str, Any]], bool]:
    """Auto-promote registered RENERYO SEU rows to energy-only mode.

    This heals legacy rows that were saved before ``capability_mode`` /
    ``native_metric_bindings`` existed.
    """
    if not mappings or not discovered_assets:
        return mappings, False

    discovered_ids = {
        str(asset.asset_id).strip()
        for asset in discovered_assets
        if isinstance(asset, Asset) and _is_uuid_asset_id(str(asset.asset_id))
    }
    if not discovered_ids:
        return mappings, False

    promoted = False
    updated: dict[str, dict[str, Any]] = {}
    for asset_id, raw_mapping in mappings.items():
        mapping = dict(raw_mapping) if isinstance(raw_mapping, dict) else {}
        row_promoted = False
        if asset_id in discovered_ids and mapping:
            if not _has_linked_metric_resources(mapping):
                native_bindings = _normalize_native_metric_bindings(mapping)
                if not native_bindings:
                    mapping["native_metric_bindings"] = {
                        metric_name: dict(config)
                        for metric_name, config in _NATIVE_SEU_ENERGY_BINDING.items()
                    }
                    row_promoted = True
                else:
                    merged_native = dict(native_bindings)
                    default_energy = dict(_NATIVE_SEU_ENERGY_BINDING["energy_total"])
                    current_energy = native_bindings.get("energy_total")
                    if isinstance(current_energy, dict):
                        current_strategy = str(
                            current_energy.get("strategy", ""),
                        ).strip().lower()
                        if current_strategy == "asset_consumption_total":
                            merged_energy = dict(default_energy)
                            merged_energy.update(current_energy)
                            if merged_energy != current_energy:
                                merged_native["energy_total"] = merged_energy
                                row_promoted = True
                    else:
                        merged_native["energy_total"] = default_energy
                        row_promoted = True

                    if row_promoted:
                        mapping["native_metric_bindings"] = merged_native

                if str(mapping.get("capability_mode", "")).strip().lower() != "energy_only":
                    mapping["capability_mode"] = "energy_only"
                    row_promoted = True

                if str(mapping.get("mapping_source", "")).strip().lower() != "live_discovery":
                    mapping["mapping_source"] = "live_discovery"
                    row_promoted = True

        if row_promoted:
            promoted = True

        updated[asset_id] = mapping

    return updated, promoted


def _get_current_platform(settings_service: SettingsService) -> str:
    """Resolve active profile platform type."""
    profile_name = settings_service.get_active_profile_name()
    profile = settings_service.get_profile(profile_name)
    if profile is None:
        return "unconfigured"
    return str(profile.platform_type or "unconfigured").lower()


def _persist_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService,
) -> AssetMappingsResponse:
    """Save mappings via SettingsService (which handles bus notification).

    Preserve previously imported ``metric_resources`` when UI payloads
    update only registration/linking fields.
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
    """Merge incoming mappings while preserving existing linkage metadata.

    Frontend asset editors may submit asset rows without ``metric_resources``.
    Without this merge, imported/native mappings are unintentionally lost.
    """
    merged: dict[str, dict[str, Any]] = {}
    for asset_id, incoming_mapping in incoming.items():
        current = existing.get(asset_id, {})
        next_mapping = dict(incoming_mapping)

        if "metric_resources" not in next_mapping:
            existing_resources = current.get("metric_resources")
            if isinstance(existing_resources, dict) and existing_resources:
                next_mapping["metric_resources"] = dict(existing_resources)

        if "native_metric_bindings" not in next_mapping:
            native_bindings = current.get("native_metric_bindings")
            if isinstance(native_bindings, dict) and native_bindings:
                next_mapping["native_metric_bindings"] = dict(native_bindings)

        if "capability_mode" not in next_mapping:
            capability_mode = str(current.get("capability_mode", "")).strip()
            if capability_mode in {"full_kpi", "energy_only"}:
                next_mapping["capability_mode"] = capability_mode

        if "mapping_source" not in next_mapping:
            mapping_source = str(current.get("mapping_source", "")).strip()
            if mapping_source in {"manual", "generator", "live_discovery"}:
                next_mapping["mapping_source"] = mapping_source

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

    Creates a fresh adapter per call. For UnconfiguredAdapter this is cheap.
    If discovery becomes a hot path, consider caching the adapter across requests.
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
            discovered_assets = await adapter.discover_assets()
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
    """Return linking summary for wizard readiness and diagnostics."""
    platform_type = _get_current_platform(settings_service)
    mappings = settings_service.get_asset_mappings()

    supports_discovery = False
    discovery_source: Literal["adapter", "registered", "none"] = "none"
    discovery_error = ""
    discovered_items: list[AssetLinkingItem] = []
    discovered_assets: list[Asset] = []

    adapter = adapter_factory.create()
    supports_discovery = adapter.supports_asset_discovery()
    if supports_discovery:
        try:
            await asyncio.wait_for(adapter.initialize(), timeout=5.0)
            discovered = await asyncio.wait_for(adapter.discover_assets(), timeout=12.0)
            if isinstance(discovered, list):
                discovered_assets = [asset for asset in discovered if isinstance(asset, Asset)]
                if discovered_assets:
                    discovery_source = "adapter"
        except Exception as exc:  # noqa: BLE001 - endpoint degrades by design
            discovery_error = str(exc)
            logger.warning("Asset linking summary discovery failed: %s", exc)
        finally:
            try:
                await asyncio.wait_for(adapter.shutdown(), timeout=5.0)
            except Exception as exc:  # pragma: no cover - defensive cleanup
                logger.warning("Adapter shutdown for linking summary failed: %s", exc)

    if _compat_layer_enabled():
        mappings, promoted = _promote_discovered_seu_assets_to_energy_only(
            mappings=mappings,
            discovered_assets=discovered_assets,
        )
        if promoted:
            settings_service.set_asset_mappings(mappings)

    imported_assets, unlinked_assets = _build_mapping_linking_groups(mappings)
    full_kpi_assets = [
        asset
        for asset in imported_assets
        if asset.mapping_mode == "full_kpi"
    ]
    metric_coverage = _build_metric_coverage(full_kpi_assets)

    if discovery_source == "none" and (imported_assets or unlinked_assets):
        discovery_source = "registered"

    existing_asset_ids = {
        _normalize_asset_key(asset_id)
        for asset_id in mappings.keys()
    }
    discovered_items = _build_discovered_linking_items(
        discovered_assets,
        existing_asset_ids,
    )

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


@router.get(
    "/assets/generator-mapping-preview",
    response_model=GeneratorAssetPreviewResponse,
)
def get_generator_mapping_preview() -> GeneratorAssetPreviewResponse:
    """Preview bundled generator mapping assets without persisting anything."""
    path = _default_generator_mapping_path()
    if not path.exists():
        return GeneratorAssetPreviewResponse(
            available=False,
            source_path=str(path),
            error=f"Generator mapping file not found: {path}",
        )

    try:
        payload_json = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - return graceful preview state
        return GeneratorAssetPreviewResponse(
            available=False,
            source_path=str(path),
            error=f"Could not parse generator mapping JSON: {exc}",
        )

    mapping = _extract_mapping_payload(payload_json)
    try:
        _reject_unknown_metrics(mapping)
    except HTTPException as exc:
        return GeneratorAssetPreviewResponse(
            available=False,
            source_path=str(path),
            error=str(exc.detail),
        )

    return GeneratorAssetPreviewResponse(
        available=True,
        source_path=str(path),
        imported_metrics=len(mapping),
        assets=_build_generator_asset_preview(mapping),
    )


@router.post(
    "/assets/import-generator-mapping",
    response_model=GeneratorMappingResponse,
)
def import_generator_mapping(
    payload: GeneratorMappingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> GeneratorMappingResponse:
    """Import data generator mapping_output.json into asset mappings.

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


@router.post(
    "/assets/import-generator-mapping/default",
    response_model=GeneratorMappingResponse,
)
def import_default_generator_mapping(
    settings_service: SettingsService = Depends(get_settings_service),
) -> GeneratorMappingResponse:
    """Import bundled mapping_output.json for RENERYO first-run bootstrap."""
    path = _default_generator_mapping_path()
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Default generator mapping file not found: {path}",
        )

    try:
        payload_json = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse default generator mapping JSON: {exc}",
        ) from exc

    mapping = _extract_mapping_payload(payload_json)
    _reject_unknown_metrics(mapping)
    per_asset = _transform_generator_mapping(mapping)
    if not per_asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid metric-resource mappings found in default file",
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
        imported_metrics=len(mapping),
        imported_resources=total_resources,
        asset_mappings=settings_service.get_asset_mappings(),
    )
