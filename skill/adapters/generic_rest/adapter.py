"""Generic REST adapter using profile metric mappings."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import time
from typing import TYPE_CHECKING, Any

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional in minimal OVOS images
    aiohttp = None  # type: ignore[assignment]

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.generic_rest._config_mixin import GenericRestConfigMixin
from skill.adapters.generic_rest._http import GenericRestHttpMixin
from skill.adapters.generic_rest._mapping_helpers import (
    MetricMapping,
    compute_trend_change,
    extract_mapped_value,
    extract_trend_points,
    get_mapping_json_path,
    get_mapping_unit,
    parse_mapped_kpi_response,
    rank_descending,
    resolve_request,
)
from skill.adapters.generic_rest._settings_mixin import GenericRestSettingsMixin
from skill.domain.exceptions import AdapterError
from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.domain.results import (
    ComparisonItem,
    ComparisonResult,
    ConnectionTestResult,
    KPIResult,
    TrendResult,
)

if TYPE_CHECKING:
    from skill.services.settings import SettingsService

logger = logging.getLogger(__name__)


class GenericRestAdapter(
    GenericRestHttpMixin,
    GenericRestConfigMixin,
    GenericRestSettingsMixin,
    ManufacturingAdapter,
):
    """Platform-agnostic adapter driven by metric mappings."""

    _AUTH_PROBE_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/seu/names?count=1",
        "/u/measurement/seu/names?count=1",
        "/api/status",
        "/status",
        "/api/health",
        "/health",
    )
    _AUTO_DISCOVERY_ENDPOINTS: tuple[str, ...] = (
        "/api/analytics/api/v1/machines",
        "/api/analytics/api/v1/assets",
        "/api/analytics/api/v1/devices",
        "/api/v1/assets",
        "/api/assets",
        "/assets",
        "/api/v1/resources",
        "/api/resources",
        "/resources",
        "/api/v1/devices",
        "/api/devices",
        "/devices",
        "/api/v1/machines",
        "/api/machines",
        "/machines",
        "/api/v1/lines",
        "/api/lines",
        "/lines",
    )
    _COMPAT_ASSET_DISCOVERY_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
        "/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
        "/api/u/measurement/seu/names?count=100",
        "/u/measurement/seu/names?count=100",
    )
    _SEU_ITEM_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/seu/item",
        "/u/measurement/seu/item",
    )

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        auth_type: str = "bearer",
        settings_service: SettingsService | None = None,
        profile_name: str = "",
        extra_settings: dict[str, Any] | None = None,
    ) -> None:
        self._api_url = (api_url or "").strip().rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._auth_type = (auth_type or "bearer").strip().lower()
        self._settings_service = settings_service
        self._profile_name = profile_name
        self._extra_settings: dict[str, Any] = dict(extra_settings or {})
        self._session: aiohttp.ClientSession | None = None

        self._max_retries = self._parse_max_retries(self._extra_settings)
        self._backoff_factors = self._parse_backoff_factors(self._extra_settings)

    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Fetch KPI from mapped endpoint and parse mapped value."""
        self._ensure_initialized()
        native_binding = self._resolve_native_metric_binding(metric=metric, asset_id=asset_id)
        if native_binding is not None:
            return await self._query_native_metric_kpi(
                metric=metric,
                asset_id=asset_id,
                period=period,
                binding=native_binding,
            )

        if self._is_energy_only_asset(asset_id):
            self._raise_asset_metric_unavailable(
                metric=metric,
                asset_id=asset_id,
                supported_metrics=(CanonicalMetric.ENERGY_TOTAL,),
            )

        return await self._query_mapped_kpi(metric=metric, asset_id=asset_id, period=period)

    async def _query_mapped_kpi(
        self,
        *,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Resolve KPI through standard metric mappings."""
        mapping = self._require_metric_mapping(metric)
        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._runtime_settings_for(metric.value, asset_id),
        )
        data = await self._retry_fetch(endpoint, params)
        return parse_mapped_kpi_response(data, mapping, metric, asset_id, period)

    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """Fetch mapped KPI for each asset and return ranked comparison."""
        self._ensure_initialized()
        if len(asset_ids) < 2:
            raise AdapterError(
                message="Comparison requires at least two asset IDs",
                code="GENERIC_REST_COMPARE_INVALID",
                platform="generic_rest",
            )

        unsupported = [asset_id for asset_id in asset_ids if self._is_energy_only_asset(asset_id)]
        if unsupported:
            raise AdapterError(
                message=f"Comparison is not available for energy-only assets: {unsupported}",
                code="ASSET_METRIC_UNAVAILABLE",
                platform="generic_rest",
                user_message=(
                    "Comparison is not available for energy-only assets in the current source. "
                    "Use assets with full metric mappings for comparison commands."
                ),
            )

        mapping = self._require_metric_mapping(metric)
        json_path = get_mapping_json_path(mapping)
        unit = get_mapping_unit(mapping, metric)

        values: list[tuple[str, float]] = []
        for asset_id in asset_ids:
            endpoint, params = resolve_request(
                mapping=mapping,
                period=period,
                asset_id=asset_id,
                extra_settings=self._runtime_settings_for(metric.value, asset_id),
            )
            data = await self._retry_fetch(endpoint, params)
            value = extract_mapped_value(data, json_path, mapping)
            values.append((asset_id, value))

        sorted_values = sorted(
            values,
            key=lambda item: item[1],
            reverse=rank_descending(metric),
        )
        items = [
            ComparisonItem(asset_id=asset_id, value=value, rank=index + 1)
            for index, (asset_id, value) in enumerate(sorted_values)
        ]

        winner_id = items[0].asset_id
        difference = round(abs(max(value for _, value in values) - min(value for _, value in values)), 2)

        return ComparisonResult(
            metric=metric,
            items=items,
            winner_id=winner_id,
            difference=difference,
            unit=unit,
            period=period,
        )

    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """Fetch trend endpoint and parse generic time-series payload."""
        self._ensure_initialized()
        if self._is_energy_only_asset(asset_id):
            raise AdapterError(
                message=f"Trend is not available for energy-only asset '{asset_id}'",
                code="ASSET_METRIC_UNAVAILABLE",
                platform="generic_rest",
                user_message=(
                    f"Trend is not available for {asset_id} from the current source. "
                    "This asset currently exposes aggregate energy consumption only."
                ),
            )

        mapping = self._require_metric_mapping(metric)

        endpoint, params = self._resolve_trend_request(
            mapping=mapping,
            metric_name=metric.value,
            period=period,
            asset_id=asset_id,
            granularity=granularity,
        )
        data = await self._retry_fetch(endpoint, params)

        points = extract_trend_points(
            payload=data,
            mapping=mapping,
            metric=metric,
            period=period,
        )
        if not points:
            raise AdapterError(
                message="No trend data points returned",
                code="GENERIC_REST_NO_DATA",
                platform="generic_rest",
                user_message=(
                    "I couldn't find trend data for that period. "
                    "Please try a wider period."
                ),
            )

        direction, change_percent = compute_trend_change(points)
        return TrendResult(
            metric=metric,
            asset_id=asset_id,
            data_points=points,
            direction=direction,
            change_percent=change_percent,
            period=period,
            granularity=granularity,
        )

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> dict | list:
        """Fetch and return mapped endpoint payload without normalization."""
        self._ensure_initialized()
        if self._is_energy_only_asset(asset_id):
            self._raise_asset_metric_unavailable(
                metric=metric,
                asset_id=asset_id,
                supported_metrics=(CanonicalMetric.ENERGY_TOTAL,),
            )

        mapping = self._require_metric_mapping(metric)

        endpoint_key = "raw_endpoint" if str(mapping.get("raw_endpoint", "")).strip() else "endpoint"
        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._runtime_settings_for(metric.value, asset_id),
            endpoint_key=endpoint_key,
        )
        return await self._retry_fetch(endpoint, params)

    async def list_assets(self) -> list[Asset]:
        """Return profile assets, with live discovery fallback when empty."""
        mappings = self._load_asset_mappings()
        assets: list[Asset] = []
        for asset_id, mapping in sorted(mappings.items(), key=lambda item: item[0]):
            if not isinstance(mapping, dict):
                continue
            asset = self._build_asset_from_mapping(asset_id, mapping)
            if asset is not None:
                assets.append(asset)
        if assets:
            return assets

        # For first-run wizard flows, allow live discovery fallback when no
        # profile assets are registered yet.
        discovered_assets = await self._discover_assets_from_api()
        if discovered_assets:
            return discovered_assets
        return assets

    async def discover_assets(self) -> list[Asset]:
        """Return live-discovered upstream assets for wizard discovery views."""
        self._ensure_initialized()
        return await self._discover_assets_from_api()

    def supports_asset_discovery(self) -> bool:
        """Return whether lightweight discovery can be attempted."""
        return bool(self._api_url)

    def supports_capability(self, capability: str) -> bool:
        """Return True only when capability maps to a configured metric."""
        metric_name = self._normalize_metric_name(capability)
        if not metric_name:
            return False
        if self._lookup_metric_mapping_by_name(metric_name) is not None:
            return True
        return metric_name in self._list_native_supported_metric_names()

    def get_supported_metrics(self) -> list[CanonicalMetric]:
        """List canonical metrics that currently have mappings configured."""
        mappings = self._list_metric_mappings()
        supported: list[CanonicalMetric] = []
        seen: set[CanonicalMetric] = set()
        for metric_name in mappings.keys():
            try:
                metric = CanonicalMetric.from_string(metric_name)
                if metric in seen:
                    continue
                supported.append(metric)
                seen.add(metric)
            except ValueError:
                logger.debug("Ignoring unknown mapped metric name: %s", metric_name)
        for metric_name in sorted(self._list_native_supported_metric_names()):
            try:
                metric = CanonicalMetric.from_string(metric_name)
            except ValueError:
                continue
            if metric in seen:
                continue
            supported.append(metric)
            seen.add(metric)
        return supported

    async def initialize(self) -> None:
        """Create HTTP session and validate configured base URL is reachable."""
        if not self._api_url:
            raise AdapterError(
                message="API URL is required for GenericRestAdapter",
                code="GENERIC_REST_INIT_FAILED",
                platform="generic_rest",
            )

        if self._session is not None and not self._session.closed:
            await self._session.close()

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        headers = self._build_auth_headers()
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)

        try:
            await self._probe_base_url()
        except Exception:
            await self.shutdown()
            raise

        logger.info(
            "GenericRestAdapter initialized — API URL: %s, auth: %s, retries: %d",
            self._api_url,
            self._auth_type,
            self._max_retries,
        )

    async def test_connection(self) -> ConnectionTestResult:
        """Probe connectivity and verify auth with known protected endpoints."""
        start = time.monotonic()
        try:
            await self.initialize()
            auth_error = await self._probe_authenticated_endpoint()
            if auth_error:
                elapsed = (time.monotonic() - start) * 1000
                return ConnectionTestResult(
                    success=False,
                    latency_ms=round(elapsed, 1),
                    message=auth_error,
                    adapter_name=self.platform_name,
                    error_code="GENERIC_REST_AUTH_FAILED",
                    error_details=auth_error,
                )

            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=True,
                latency_ms=round(elapsed, 1),
                message="Connection established",
                adapter_name=self.platform_name,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=round(elapsed, 1),
                message=str(exc),
                adapter_name=self.platform_name,
                error_code=getattr(exc, "code", "UNKNOWN"),
                error_details=str(exc),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Close HTTP session gracefully."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info("GenericRestAdapter shut down")

    async def _probe_authenticated_endpoint(self) -> str | None:
        """Return auth error when credentials are rejected, otherwise None."""
        if self._auth_type == "none":
            return None
        if self._session is None:
            return "Adapter session is not initialized"

        custom_probe = str(
            self._extra_settings.get("connection_test_endpoint", ""),
        ).strip()
        candidates = []
        if custom_probe:
            candidates.append(custom_probe)
        candidates.extend(self._AUTH_PROBE_ENDPOINTS)

        visited: set[str] = set()
        for endpoint in candidates:
            cleaned = endpoint.strip()
            if not cleaned or cleaned in visited:
                continue
            visited.add(cleaned)

            url = self._build_request_url(cleaned)
            try:
                async with self._session.get(url) as response:
                    if response.status in {401, 403}:
                        return (
                            "Authentication failed. Check API key/cookie settings and try again."
                        )
                    if 200 <= response.status < 300:
                        return None
                    if response.status in {404, 405}:
                        continue
            except Exception:
                continue

        return None

    async def _discover_assets_from_api(self) -> list[Asset]:
        """Discover assets via config-driven contract with optional compat fallback."""
        config = self._resolve_discovery_config()
        if config is not None:
            assets = await self._discover_assets_from_config(config)
            if assets:
                return assets

        assets = await self._discover_assets_from_auto_probe()
        if assets:
            return assets

        if self._compat_layer_enabled():
            return await self._discover_assets_from_compat_endpoints()

        return []

    async def _discover_assets_from_auto_probe(self) -> list[Asset]:
        """Try generic REST discovery endpoints and infer records heuristically."""
        if self._session is None:
            return []

        endpoints = list(self._AUTO_DISCOVERY_ENDPOINTS)
        extra_endpoints = self._extra_settings.get("asset_discovery_auto_endpoints", [])
        if isinstance(extra_endpoints, list):
            endpoints = [str(item).strip() for item in extra_endpoints if str(item).strip()] + endpoints

        visited: set[str] = set()
        for endpoint in endpoints:
            candidate = endpoint.strip()
            if not candidate or candidate in visited:
                continue
            visited.add(candidate)
            try:
                url = self._build_request_url(candidate)
                async with self._session.get(url) as response:
                    if response.status in {401, 403}:
                        continue
                    if response.status >= 400:
                        continue
                    payload = await response.json()
            except Exception:  # noqa: BLE001 - best-effort probing
                continue

            records = self._infer_records(payload)
            if not records:
                continue

            discovered = self._normalize_discovery_records(
                records=records,
                id_field="",
                name_field="",
                type_field="",
                aliases_field="",
                energy_resource_field="",
                default_asset_type="machine",
                metadata_fields=[],
            )
            if discovered:
                return discovered
        return []

    @staticmethod
    def _compat_layer_enabled() -> bool:
        """Return True when optional platform compatibility layer is enabled."""
        raw = str(os.environ.get("AVAROS_ENABLE_PLATFORM_COMPAT_LAYER", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _resolve_discovery_config(self) -> dict[str, Any] | None:
        """Resolve generic discovery config from profile extra settings."""
        raw = self._extra_settings.get("asset_discovery")
        if not isinstance(raw, dict):
            return None

        enabled_raw = raw.get("enabled", True)
        enabled = bool(enabled_raw)
        if isinstance(enabled_raw, str):
            enabled = enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return None

        endpoint = str(raw.get("endpoint", "")).strip()
        if not endpoint:
            return None

        params_raw = raw.get("params", {})
        params: dict[str, str] = {}
        if isinstance(params_raw, dict):
            params = {
                str(key): str(value)
                for key, value in params_raw.items()
                if str(key).strip()
            }

        metadata_fields_raw = raw.get("metadata_fields", [])
        metadata_fields = (
            [str(item).strip() for item in metadata_fields_raw if str(item).strip()]
            if isinstance(metadata_fields_raw, list)
            else []
        )

        return {
            "endpoint": endpoint,
            "params": params,
            "records_path": str(raw.get("records_path", "records")).strip(),
            "id_field": str(raw.get("id_field", "id")).strip(),
            "name_field": str(raw.get("name_field", "name")).strip(),
            "type_field": str(raw.get("type_field", "asset_type")).strip(),
            "aliases_field": str(raw.get("aliases_field", "")).strip(),
            "energy_resource_field": str(raw.get("energy_resource_field", "")).strip(),
            "default_asset_type": str(raw.get("default_asset_type", "machine")).strip() or "machine",
            "metadata_fields": metadata_fields,
        }

    async def _discover_assets_from_config(
        self,
        config: dict[str, Any],
    ) -> list[Asset]:
        """Execute config-driven discovery endpoint and normalize assets."""
        if self._session is None:
            return []

        try:
            url = self._build_request_url(str(config.get("endpoint", "")))
            params = config.get("params")
            async with self._session.get(url, params=params if isinstance(params, dict) and params else None) as response:
                if response.status in {401, 403}:
                    return []
                if response.status >= 400:
                    return []
                payload = await response.json()
        except Exception:  # noqa: BLE001 - discovery is best-effort
            return []

        records = self._extract_records(payload, str(config.get("records_path", "records")))
        if not records:
            return []
        return self._normalize_discovery_records(
            records=records,
            id_field=str(config.get("id_field", "id")),
            name_field=str(config.get("name_field", "name")),
            type_field=str(config.get("type_field", "asset_type")),
            aliases_field=str(config.get("aliases_field", "")),
            energy_resource_field=str(config.get("energy_resource_field", "")),
            default_asset_type=str(config.get("default_asset_type", "machine")),
            metadata_fields=config.get("metadata_fields", []),
        )

    async def _discover_assets_from_compat_endpoints(self) -> list[Asset]:
        """Legacy compatibility discovery for known RENERYO-style payloads."""
        if self._session is None:
            return []

        seen_ids: set[str] = set()
        for endpoint in self._COMPAT_ASSET_DISCOVERY_ENDPOINTS:
            try:
                url = self._build_request_url(endpoint)
                async with self._session.get(url) as response:
                    if response.status in {401, 403}:
                        return []
                    if response.status >= 400:
                        continue
                    payload = await response.json()
            except Exception:  # noqa: BLE001 - discovery is best-effort
                continue

            records = payload.get("records", []) if isinstance(payload, dict) else []
            if not isinstance(records, list):
                continue

            discovered: list[Asset] = []
            for record in records:
                if not isinstance(record, dict):
                    # Ignore non-object entries to avoid guessing synthetic asset IDs.
                    continue

                asset_id = str(record.get("id", "")).strip()
                display_name = str(record.get("name", "")).strip() or asset_id
                energy_resource = str(record.get("energyResource", "")).strip()

                if not asset_id:
                    continue
                normalized_id = asset_id.lower()
                if normalized_id in seen_ids:
                    continue
                seen_ids.add(normalized_id)

                alias = display_name.lower().strip()
                aliases = []
                if alias and alias != asset_id.lower() and len(alias) <= 32:
                    aliases = [alias]

                metadata: dict[str, Any] = {"source": "api_discovery"}
                if energy_resource:
                    metadata["energy_resource"] = energy_resource

                discovered.append(
                    Asset(
                        asset_id=asset_id,
                        display_name=display_name,
                        asset_type="machine",
                        aliases=aliases,
                        metadata=metadata,
                    ),
                )

            if discovered:
                return discovered

        return []

    def _normalize_discovery_records(
        self,
        *,
        records: list[Any],
        id_field: str,
        name_field: str,
        type_field: str,
        aliases_field: str,
        energy_resource_field: str,
        default_asset_type: str,
        metadata_fields: list[Any],
    ) -> list[Asset]:
        """Normalize discovery records to canonical Asset list."""
        seen_ids: set[str] = set()
        discovered: list[Asset] = []

        for record in records:
            if not isinstance(record, dict):
                continue

            if id_field.strip():
                asset_id = str(self._extract_field(record, id_field)).strip()
            else:
                asset_id = self._infer_asset_id(record)

            if name_field.strip():
                display_name = str(self._extract_field(record, name_field)).strip()
            else:
                display_name = self._infer_display_name(record)

            if not asset_id and display_name:
                asset_id = display_name
            if not display_name and asset_id:
                display_name = asset_id
            if not asset_id:
                continue

            normalized_id = asset_id.lower()
            if normalized_id in seen_ids:
                continue
            seen_ids.add(normalized_id)

            if type_field.strip():
                asset_type = str(self._extract_field(record, type_field)).strip().lower()
            else:
                asset_type = self._infer_asset_type(record)
            if asset_type not in {"machine", "line", "sensor", "seu"}:
                asset_type = str(default_asset_type or "machine").strip().lower() or "machine"

            aliases = self._resolve_aliases(
                record=record,
                aliases_field=aliases_field,
                display_name=display_name,
                asset_id=asset_id,
            )

            metadata: dict[str, Any] = {"source": "api_discovery"}
            if energy_resource_field.strip():
                energy_resource = str(self._extract_field(record, energy_resource_field)).strip()
                if energy_resource:
                    metadata["energy_resource"] = energy_resource
            else:
                inferred_energy = str(record.get("energyResource", "")).strip()
                if inferred_energy:
                    metadata["energy_resource"] = inferred_energy

            for field in metadata_fields:
                value = self._extract_field(record, str(field))
                if value in {"", None}:
                    continue
                metadata[str(field)] = value

            discovered.append(
                Asset(
                    asset_id=asset_id,
                    display_name=display_name,
                    asset_type=asset_type,
                    aliases=aliases,
                    metadata=metadata,
                ),
            )
        return discovered

    @staticmethod
    def _infer_records(payload: Any) -> list[Any]:
        """Infer record collection from common REST response shapes."""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        candidate_keys = (
            "records",
            "items",
            "assets",
            "results",
            "rows",
            "devices",
            "machines",
            "lines",
            "resources",
            "data",
        )
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = GenericRestAdapter._infer_records(value)
                if nested:
                    return nested
        return []

    def _infer_asset_id(self, record: dict[str, Any]) -> str:
        """Infer asset id from common fields."""
        for field in ("id", "asset_id", "assetId", "uuid", "key", "code"):
            value = str(record.get(field, "")).strip()
            if value:
                return value
        return ""

    def _infer_display_name(self, record: dict[str, Any]) -> str:
        """Infer asset display name from common fields."""
        for field in ("name", "display_name", "displayName", "label", "title"):
            value = str(record.get(field, "")).strip()
            if value:
                return value
        return ""

    def _infer_asset_type(self, record: dict[str, Any]) -> str:
        """Infer canonical asset type from common fields."""
        for field in ("asset_type", "assetType", "type", "kind", "category"):
            value = str(record.get(field, "")).strip().lower()
            if value in {"machine", "line", "sensor", "seu"}:
                return value
        return "machine"

    def _resolve_aliases(
        self,
        *,
        record: dict[str, Any],
        aliases_field: str,
        display_name: str,
        asset_id: str,
    ) -> list[str]:
        """Resolve aliases from config field or fallback display-name alias."""
        aliases: list[str] = []
        if aliases_field.strip():
            aliases_value = self._extract_field(record, aliases_field)
            if isinstance(aliases_value, list):
                aliases = [str(item).strip() for item in aliases_value if str(item).strip()]
            elif isinstance(aliases_value, str) and aliases_value.strip():
                aliases = [value.strip() for value in aliases_value.split(",") if value.strip()]
        if aliases:
            return aliases

        fallback_alias = display_name.lower().strip()
        if fallback_alias and fallback_alias != asset_id.lower() and len(fallback_alias) <= 64:
            return [fallback_alias]
        return []

    @staticmethod
    def _extract_records(payload: Any, path: str) -> list[Any]:
        """Extract record list from payload using dotted path (e.g. data.records)."""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        normalized_path = str(path or "").strip()
        if not normalized_path:
            records = payload.get("records", [])
            return records if isinstance(records, list) else []

        current: Any = payload
        for part in normalized_path.split("."):
            token = part.strip()
            if not token:
                continue
            if isinstance(current, dict):
                current = current.get(token)
                continue
            if isinstance(current, list):
                try:
                    index = int(token)
                except ValueError:
                    return []
                if index < 0 or index >= len(current):
                    return []
                current = current[index]
                continue
            return []

        return current if isinstance(current, list) else []

    @staticmethod
    def _extract_field(record: dict[str, Any], path: str) -> Any:
        """Extract a field from record using dotted path."""
        normalized_path = str(path or "").strip()
        if not normalized_path:
            return ""

        current: Any = record
        for part in normalized_path.split("."):
            token = part.strip()
            if not token:
                continue
            if isinstance(current, dict):
                current = current.get(token)
                continue
            if isinstance(current, list):
                try:
                    index = int(token)
                except ValueError:
                    return ""
                if index < 0 or index >= len(current):
                    return ""
                current = current[index]
                continue
            return ""
        return current

    @property
    def platform_name(self) -> str:
        """Return platform name used in logs/UI."""
        return "GENERIC_REST"

    def _list_native_supported_metric_names(self) -> set[str]:
        """Return canonical metric names exposed via native asset bindings."""
        metric_names: set[str] = set()
        for mapping in self._load_asset_mappings().values():
            if not isinstance(mapping, dict):
                continue
            raw_bindings = mapping.get("native_metric_bindings")
            if not isinstance(raw_bindings, dict):
                continue
            for metric_name in raw_bindings.keys():
                normalized = str(metric_name).strip()
                if normalized:
                    metric_names.add(normalized)
        return metric_names

    def _resolve_asset_mapping(self, asset_id: str) -> dict[str, Any] | None:
        """Resolve an asset mapping row by id, display name, or alias."""
        target = self._normalize_asset_lookup(asset_id)
        if not target:
            return None

        mappings = self._load_asset_mappings()
        for key, mapping in mappings.items():
            if not isinstance(mapping, dict):
                continue
            lookup_values = [str(key)]
            display_name = str(mapping.get("display_name", "")).strip()
            if display_name:
                lookup_values.append(display_name)
            raw_aliases = mapping.get("aliases", [])
            if isinstance(raw_aliases, list):
                lookup_values.extend(str(alias).strip() for alias in raw_aliases if str(alias).strip())
            if any(self._normalize_asset_lookup(value) == target for value in lookup_values):
                return mapping
        return None

    def _is_energy_only_asset(self, asset_id: str) -> bool:
        """Return True when asset mapping is marked as energy-only."""
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return False
        capability_mode = str(mapping.get("capability_mode", "")).strip().lower()
        if capability_mode != "energy_only":
            return False

        # If profile-level mappings clearly support asset-id based KPI lookups,
        # do not enforce native energy-only restrictions for this asset.
        if self._supports_asset_id_metric_mappings():
            return False
        return True

    def _supports_asset_id_metric_mappings(self) -> bool:
        """Return True when any non-native metric mapping is asset-id addressable."""
        if not self._settings_service:
            return False
        try:
            mappings = self._settings_service.list_metric_mappings()
        except Exception:  # pragma: no cover - defensive runtime guard
            return False
        if not isinstance(mappings, dict):
            return False

        for metric_name, mapping in mappings.items():
            if metric_name == CanonicalMetric.ENERGY_TOTAL.value:
                continue
            if not isinstance(mapping, dict):
                continue
            endpoint = str(mapping.get("endpoint", "")).strip()
            if "{asset_id}" in endpoint:
                return True
        return False

    def _resolve_native_metric_binding(
        self,
        *,
        metric: CanonicalMetric,
        asset_id: str,
    ) -> dict[str, Any] | None:
        """Resolve native metric binding config for an asset-specific metric."""
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return None
        native_bindings = mapping.get("native_metric_bindings")
        if not isinstance(native_bindings, dict):
            return None
        raw_binding = native_bindings.get(metric.value)
        if not isinstance(raw_binding, dict):
            return None
        return raw_binding

    def _asset_display_name(self, asset_id: str) -> str:
        """Resolve human-friendly asset label for user-facing messages."""
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return asset_id
        display_name = str(mapping.get("display_name", "")).strip()
        return display_name or asset_id

    def _raise_asset_metric_unavailable(
        self,
        *,
        metric: CanonicalMetric,
        asset_id: str,
        supported_metrics: tuple[CanonicalMetric, ...],
    ) -> None:
        """Raise a normalized asset-level unsupported metric error."""
        display_name = self._asset_display_name(asset_id)
        supported_label = ", ".join(m.display_name for m in supported_metrics)
        raise AdapterError(
            message=(
                f"Metric '{metric.value}' is not available for asset '{asset_id}' "
                "under current native bindings"
            ),
            code="ASSET_METRIC_UNAVAILABLE",
            platform="generic_rest",
            user_message=(
                f"{metric.display_name} is not available for {display_name} from the current source. "
                f"Available metric for this asset: {supported_label}."
            ),
        )

    async def _query_native_metric_kpi(
        self,
        *,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        binding: dict[str, Any],
    ) -> KPIResult:
        """Resolve KPI values from asset-native bindings."""
        strategy = str(binding.get("strategy", "")).strip().lower()
        if strategy == "asset_consumption_total":
            try:
                return await self._query_seu_energy_total(asset_id=asset_id, period=period)
            except AdapterError as native_exc:
                if metric == CanonicalMetric.ENERGY_TOTAL:
                    try:
                        logger.info(
                            "Native energy_total strategy failed for '%s'; trying mapped KPI fallback",
                            asset_id,
                        )
                        return await self._query_mapped_kpi(
                            metric=metric,
                            asset_id=asset_id,
                            period=period,
                        )
                    except AdapterError:
                        pass
                raise native_exc
        raise AdapterError(
            message=f"Unsupported native binding strategy '{strategy}' for {metric.value}",
            code="GENERIC_REST_NATIVE_BINDING_INVALID",
            platform="generic_rest",
        )

    async def _query_seu_energy_total(self, *, asset_id: str, period: TimePeriod) -> KPIResult:
        """Fetch aggregate energy consumption from item endpoint."""
        start_iso = self._to_reneryo_iso(period.start)
        end_iso = self._to_reneryo_iso(period.end)
        params = {"datetimeMin": start_iso, "datetimeMax": end_iso}

        payload: dict | list | None = None
        for endpoint in self._SEU_ITEM_ENDPOINTS:
            try:
                payload = await self._retry_fetch(endpoint, params)
            except AdapterError as exc:
                if exc.code in {"GENERIC_REST_ENDPOINT_NOT_FOUND", "GENERIC_REST_UNEXPECTED_STATUS"}:
                    continue
                raise
            else:
                break

        if not isinstance(payload, dict):
            raise AdapterError(
                message="SEU energy endpoint returned invalid payload",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )

        records = payload.get("records", [])
        if not isinstance(records, list):
            records = []

        target = self._normalize_asset_lookup(asset_id)
        selected: dict[str, Any] | None = None
        for record in records:
            if not isinstance(record, dict):
                continue
            candidate_id = str(record.get("id", "")).strip()
            candidate_name = str(record.get("name", "")).strip()
            if not candidate_id and not candidate_name:
                continue
            if self._normalize_asset_lookup(candidate_id) == target:
                selected = record
                break
            if candidate_name and self._normalize_asset_lookup(candidate_name) == target:
                selected = record
                break

        if selected is None:
            raise AdapterError(
                message=f"No SEU record found for '{asset_id}' in requested period",
                code="EMPTY_RESPONSE",
                platform="generic_rest",
                user_message=(
                    f"I couldn't find energy consumption data for {self._asset_display_name(asset_id)} "
                    f"over {period.display_name}."
                ),
            )

        try:
            value = float(selected.get("consumption"))
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                message=f"SEU record has non-numeric consumption for '{asset_id}'",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            ) from exc

        return KPIResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            value=value,
            unit="kWh",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.now(tz=timezone.utc),
        )

    @staticmethod
    def _to_reneryo_iso(value: datetime) -> str:
        """Format datetime for upstream query parameters."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _require_metric_mapping(self, metric: CanonicalMetric) -> MetricMapping:
        """Load mapping for metric or raise clear missing-mapping error."""
        mapping = self._lookup_metric_mapping_by_name(metric.value)
        if mapping is not None:
            return mapping

        raise AdapterError(
            message=f"No mapping configured for {metric.value}",
            code="GENERIC_REST_MAPPING_NOT_FOUND",
            platform="generic_rest",
            user_message=(
                f"This command is not configured for {metric.display_name} yet. "
                "Add a metric mapping in Settings first."
            ),
        )

    def _load_asset_mappings(self) -> dict[str, dict[str, Any]]:
        """Load profile asset mappings from SettingsService or local fallback."""
        if self._settings_service is not None:
            mappings = self._settings_service.get_asset_mappings(
                profile=self._profile_name or None,
            )
            if isinstance(mappings, dict):
                return mappings
        local = self._extra_settings.get("asset_mappings")
        return local if isinstance(local, dict) else {}

    @staticmethod
    def _build_asset_from_mapping(asset_id: str, mapping: dict[str, Any]) -> Asset | None:
        """Convert a mapping row into a canonical Asset instance."""
        normalized_id = str(asset_id).strip()
        if not normalized_id:
            return None

        display_name = str(
            mapping.get("display_name")
            or mapping.get("name")
            or normalized_id,
        ).strip()
        asset_type = str(mapping.get("asset_type") or "machine").strip().lower()
        if asset_type not in {"machine", "line", "sensor", "seu"}:
            asset_type = "machine"

        aliases: list[str] = []
        raw_aliases = mapping.get("aliases", [])
        if isinstance(raw_aliases, list):
            aliases = [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
        metadata = {
            key: value
            for key, value in mapping.items()
            if key not in {"display_name", "name", "asset_type", "aliases"}
        }

        try:
            return Asset(
                asset_id=normalized_id,
                display_name=display_name or normalized_id,
                asset_type=asset_type,
                aliases=aliases,
                metadata=metadata,
            )
        except ValueError:
            return None
