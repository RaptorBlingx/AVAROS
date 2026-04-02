"""Platform configuration CRUD APIs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore[assignment]

from dependencies import get_adapter_factory, get_settings_service
from schemas.config import (
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    ResetResponse,
    sanitize_extra_settings,
)
from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.clients.cookie_utils import normalize_cookie_header_value
from skill.services.settings import PlatformConfig, SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["config"])
logger = logging.getLogger(__name__)

_MESSAGEBUS_URL = os.environ.get(
    "OVOS_MESSAGEBUS_URL", "ws://ovos_messagebus:8181/core",
)


def _notify_skill_profile_changed(profile_name: str) -> bool:
    """Send profile activation event so the OVOS skill reloads its adapter.

    Best-effort — returns False on failure, never raises.
    """
    try:
        if websocket is None:
            logger.warning("websocket-client not installed — cannot notify skill")
            return False
        ws = websocket.create_connection(_MESSAGEBUS_URL, timeout=3)
        msg = {
            "type": "avaros.profile.activated",
            "data": {"profile": profile_name},
            "context": {},
        }
        ws.send(json.dumps(msg))
        ws.close()
        logger.info(
            "Sent avaros.profile.activated to messagebus (profile='%s')",
            profile_name,
        )
        return True
    except Exception as exc:
        logger.warning("Could not notify skill via messagebus: %s", exc)
        return False

_ANALYTICS_MACHINES_PATH = "/api/analytics/api/v1/machines"
_ANALYTICS_DISCOVERY_CONFIG: dict[str, Any] = {
    "enabled": True,
    "endpoint": _ANALYTICS_MACHINES_PATH,
    "records_path": "",
    "id_field": "id",
    "name_field": "name",
    "type_field": "type",
    "default_asset_type": "machine",
    "metadata_fields": ["factory_id", "factory_name", "factory_location", "is_active"],
}
_ANALYTICS_AUTO_METRIC_MAPPINGS: dict[str, dict[str, Any]] = {
    "energy_per_unit": {
        "endpoint": "/api/analytics/api/v1/kpi/all?machine_id={asset_id}&start={start_date}&end={end_date}",
        "trend_endpoint": "/api/analytics/api/v1/timeseries/sec?machine_id={asset_id}&start_time={start_date}&end_time={end_date}&interval=1hour",
        "json_path": "$.kpis.sec.value",
        "trend_json_path": "$.data_points",
        "unit": "kWh/unit",
        "transform": None,
    },
    "energy_total": {
        "endpoint": "/api/analytics/api/v1/kpi/all?machine_id={asset_id}&start={start_date}&end={end_date}",
        "trend_endpoint": "/api/analytics/api/v1/timeseries/energy?machine_id={asset_id}&start_time={start_date}&end_time={end_date}&interval=1hour",
        "json_path": "$.totals.total_energy_kwh",
        "trend_json_path": "$.data_points",
        "unit": "kWh",
        "transform": None,
    },
    "peak_demand": {
        "endpoint": "/api/analytics/api/v1/kpi/all?machine_id={asset_id}&start={start_date}&end={end_date}",
        "trend_endpoint": "/api/analytics/api/v1/timeseries/power?machine_id={asset_id}&start_time={start_date}&end_time={end_date}&interval=1hour",
        "json_path": "$.kpis.peak_demand.value",
        "trend_json_path": "$.data_points",
        "unit": "kW",
        "transform": None,
    },
    "co2_total": {
        "endpoint": "/api/analytics/api/v1/kpi/all?machine_id={asset_id}&start={start_date}&end={end_date}",
        "json_path": "$.kpis.carbon_intensity.value",
        "unit": "kg CO2-eq",
        "transform": None,
    },
    "co2_per_unit": {
        "endpoint": "/api/analytics/api/v1/kpi/all?machine_id={asset_id}&start={start_date}&end={end_date}",
        "json_path": "$.kpis.carbon_intensity.co2_per_unit",
        "unit": "kg CO2-eq/unit",
        "transform": None,
    },
}


def _origin_signature(url: str) -> str:
    """Build normalized origin signature for URL comparisons."""
    parsed = urlparse(str(url or "").strip())
    scheme = (parsed.scheme or "").lower()
    netloc = (parsed.netloc or "").lower()
    if not scheme or not netloc:
        return ""
    return f"{scheme}://{netloc}"


def _prune_live_discovery_assets_on_origin_change(
    settings_service: SettingsService,
    *,
    previous_api_url: str,
    next_api_url: str,
) -> None:
    """Remove previously discovered assets when platform origin changes.

    This prevents cross-platform asset mixing (e.g., WASABI machines + RENERYO SEUs
    in the same profile) while keeping manual/generator rows intact.
    """
    previous_origin = _origin_signature(previous_api_url)
    next_origin = _origin_signature(next_api_url)
    if not previous_origin or not next_origin or previous_origin == next_origin:
        return

    current_assets = settings_service.get_asset_mappings()
    if not current_assets:
        return

    pruned_assets: dict[str, dict[str, Any]] = {}
    removed_count = 0
    for asset_id, mapping in current_assets.items():
        row = mapping if isinstance(mapping, dict) else {}
        mapping_source = str(row.get("mapping_source", "")).strip().lower()
        if mapping_source == "live_discovery":
            removed_count += 1
            continue
        pruned_assets[asset_id] = row

    if removed_count > 0:
        settings_service.set_asset_mappings(pruned_assets)
        logger.info(
            "Platform origin changed (%s -> %s): pruned %d live_discovery assets",
            previous_origin,
            next_origin,
            removed_count,
        )


def _resolve_effective_platform_type(
    payload: PlatformConfigRequest,
) -> str:
    """Return requested platform type without profile-specific overrides."""
    return payload.platform_type


def _mask_api_key(api_key: str) -> str:
    """Mask key as ****XXXX; for short keys return ****."""
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"


def _to_response(config: PlatformConfig) -> PlatformConfigResponse:
    """Convert service config into API-safe masked response.

    Public Web UI contract intentionally exposes only ``custom_rest`` and
    ``unconfigured`` platform types. Unknown internal aliases are surfaced
    as ``custom_rest`` at the API boundary.
    """
    raw = str(config.platform_type or "unconfigured").lower()
    platform_type = raw if raw in {"custom_rest", "unconfigured"} else "custom_rest"
    return PlatformConfigResponse(
        platform_type=platform_type,
        api_url=config.api_url,
        api_key=_mask_api_key(config.api_key),
        extra_settings=sanitize_extra_settings(config.extra_settings),
    )


def _build_auth_headers(config: PlatformConfig) -> dict[str, str]:
    """Build upstream auth headers from platform config."""
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "AVAROS/1.0 (+generic-rest-bootstrap)",
    }
    extra = sanitize_extra_settings(config.extra_settings)
    auth_type = str(extra.get("auth_type", "bearer")).strip().lower()
    if auth_type == "none":
        return headers
    if auth_type == "cookie":
        headers.update(
            {
                "Cookie": normalize_cookie_header_value(
                    config.api_key or "",
                    decode=True,
                ),
            },
        )
        return headers
    headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def _fetch_json(base_url: str, path: str, headers: dict[str, str]) -> Any | None:
    """Fetch JSON payload from upstream API. Returns None on errors."""
    if not base_url:
        return None
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=8) as response:  # noqa: S310 - internal trusted config
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _extract_machine_rows(payload: Any) -> list[dict[str, str]]:
    """Extract machine rows from analytics catalog payload."""
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        machine_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        machine_type = str(item.get("type", "")).strip().lower() or "machine"
        if not machine_id or not name:
            continue
        rows.append(
            {
                "id": machine_id,
                "name": name,
                "type": machine_type if machine_type in {"machine", "line", "sensor", "seu"} else "machine",
            },
        )
    return rows


def _maybe_auto_bootstrap_supported_mappings(
    settings_service: SettingsService,
) -> None:
    """Auto-bootstrap discovery + KPI mappings from analytics-style APIs."""
    config = settings_service.get_platform_config()
    if str(config.platform_type or "").strip().lower() != "custom_rest":
        return

    headers = _build_auth_headers(config)
    machines_payload = _fetch_json(config.api_url, _ANALYTICS_MACHINES_PATH, headers)
    machine_rows = _extract_machine_rows(machines_payload)
    if not machine_rows:
        return

    # 1) Ensure discovery config exists (generic contract).
    extra = sanitize_extra_settings(config.extra_settings)
    if not isinstance(extra.get("asset_discovery"), dict):
        extra["asset_discovery"] = dict(_ANALYTICS_DISCOVERY_CONFIG)
        settings_service.update_platform_config(
            PlatformConfig(
                platform_type=config.platform_type,
                api_url=config.api_url,
                api_key=config.api_key,
                extra_settings=extra,
            ),
        )
        logger.info("Auto-bootstrap: enabled generic asset_discovery config")

    # 2) Merge discovered machines into profile asset mappings.
    existing_assets = settings_service.get_asset_mappings()
    merged_assets = dict(existing_assets)
    assets_changed = False
    for row in machine_rows:
        machine_id = row["id"]
        current = merged_assets.get(machine_id, {})
        current_mapping = dict(current) if isinstance(current, dict) else {}
        display_name = str(current_mapping.get("display_name") or row["name"]).strip() or row["name"]
        aliases = current_mapping.get("aliases", [])
        aliases_list = aliases if isinstance(aliases, list) else []
        if not aliases_list:
            alias_candidate = display_name.lower().strip()
            aliases_list = [alias_candidate] if alias_candidate else []
        next_mapping = {
            **current_mapping,
            "display_name": display_name,
            "asset_type": str(current_mapping.get("asset_type") or row["type"] or "machine"),
            "aliases": aliases_list,
            "mapping_source": str(current_mapping.get("mapping_source") or "live_discovery"),
            "capability_mode": str(current_mapping.get("capability_mode") or "full_kpi"),
        }
        # Heal legacy/native-only rows when analytics machine endpoints are available.
        # For analytics platforms, energy_total should resolve through global metric mappings,
        # not RENERYO-style SEU native strategy.
        native_bindings = current_mapping.get("native_metric_bindings")
        if isinstance(native_bindings, dict):
            energy_binding = native_bindings.get("energy_total")
            if isinstance(energy_binding, dict):
                strategy = str(energy_binding.get("strategy", "")).strip().lower()
                if strategy == "asset_consumption_total":
                    next_mapping["capability_mode"] = "full_kpi"
                    next_mapping["native_metric_bindings"] = {}
        if next_mapping != current_mapping:
            merged_assets[machine_id] = next_mapping
            assets_changed = True

    if assets_changed:
        settings_service.set_asset_mappings(merged_assets)
        logger.info(
            "Auto-bootstrap: merged %d analytics assets into profile registry",
            len(machine_rows),
        )

    # 3) Add supported metric mappings if they are missing.
    seeded_metrics = 0
    for metric_name, mapping in _ANALYTICS_AUTO_METRIC_MAPPINGS.items():
        if isinstance(settings_service.get_metric_mapping(metric_name), dict):
            continue
        settings_service.set_metric_mapping(metric_name, dict(mapping))
        seeded_metrics += 1

    if seeded_metrics > 0:
        logger.info(
            "Auto-bootstrap: seeded %d metric mappings from analytics API",
            seeded_metrics,
        )


@router.post("/platform", response_model=PlatformConfigResponse)
async def upsert_platform_config(
    payload: PlatformConfigRequest,
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> PlatformConfigResponse:
    """Create or update platform configuration and hot-reload adapter."""
    previous_config = settings_service.get_platform_config()
    platform_type = _resolve_effective_platform_type(payload)
    config = PlatformConfig(
        platform_type=platform_type,
        api_url=payload.api_url,
        api_key=payload.api_key,
        extra_settings=sanitize_extra_settings(payload.extra_settings),
    )
    _prune_live_discovery_assets_on_origin_change(
        settings_service,
        previous_api_url=str(previous_config.api_url or ""),
        next_api_url=str(config.api_url or ""),
    )
    settings_service.update_platform_config(config)
    _maybe_auto_bootstrap_supported_mappings(settings_service)

    # Keep voice runtime in sync with freshly saved platform settings.
    try:
        await adapter_factory.reload()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Platform config saved but adapter reload failed: %s",
            exc,
        )

    profile_name = settings_service.get_active_profile_name()
    _notify_skill_profile_changed(profile_name)

    return _to_response(settings_service.get_platform_config())


@router.get("/platform", response_model=PlatformConfigResponse)
def get_platform_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> PlatformConfigResponse:
    """Return current platform configuration with masked API key."""
    return _to_response(settings_service.get_platform_config())


@router.delete("/platform", response_model=ResetResponse)
def reset_platform_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> ResetResponse:
    """Reset configuration by switching back to unconfigured profile."""
    active = settings_service.get_active_profile_name()
    if active != settings_service.DEFAULT_PROFILE:
        settings_service.delete_profile(active)
    return ResetResponse(status="reset", platform_type="unconfigured")


@router.post("/platform/test", response_model=ConnectionTestResponse)
async def test_platform_connection(
    payload: PlatformConfigRequest,
) -> ConnectionTestResponse:
    """
    Test connectivity to the configured platform.

    Creates a temporary adapter from the payload config,
    runs test_connection(), and returns detailed results.
    Does NOT save the configuration (non-destructive).
    """
    try:
        adapter = _create_adapter_from_config(payload)
        result = await adapter.test_connection()
        return ConnectionTestResponse(
            success=result.success,
            message=result.message,
            latency_ms=result.latency_ms,
            adapter_name=result.adapter_name,
            resources_discovered=list(result.resources_discovered),
            error_code=result.error_code,
            error_details=result.error_details,
        )
    except Exception as exc:
        return ConnectionTestResponse(
            success=False,
            message=f"Failed to create adapter: {exc}",
            error_code="ADAPTER_CREATION_FAILED",
            error_details=str(exc),
        )


def _create_adapter_from_config(
    payload: PlatformConfigRequest,
) -> ManufacturingAdapter:
    """
    Create a throwaway adapter instance from a request payload.

    Used for connection testing — creates an adapter to test
    connectivity before committing the configuration.

    Args:
        payload: Platform configuration from the request body.

    Returns:
        Configured ManufacturingAdapter instance.

    Raises:
        ValueError: If platform_type is unknown.
    """
    if payload.platform_type == "custom_rest":
        from skill.adapters.generic_rest import GenericRestAdapter

        return GenericRestAdapter(
            api_url=payload.api_url,
            api_key=payload.api_key,
            timeout=payload.extra_settings.get("timeout", 10),
            auth_type=payload.extra_settings.get("auth_type", "bearer"),
            extra_settings=sanitize_extra_settings(payload.extra_settings),
        )

    raise ValueError(f"Unknown platform type: {payload.platform_type}")
