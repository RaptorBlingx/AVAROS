"""Generic REST adapter using profile metric mappings."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
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
    extract_trend_points,
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
    _ASSET_DISCOVERY_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
        "/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
        "/api/u/measurement/seu/names?count=100",
        "/u/measurement/seu/names?count=100",
    )
    _SEU_ITEM_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/seu/item",
        "/u/measurement/seu/item",
    )
    _METRIC_ITEM_ENDPOINTS: tuple[str, ...] = (
        "/api/u/measurement/metric/item/{resource_id}",
        "/u/measurement/metric/item/{resource_id}",
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

        if (
            self._is_energy_only_asset(asset_id)
            and metric != CanonicalMetric.ENERGY_TOTAL
        ):
            self._raise_asset_metric_unavailable(
                metric=metric,
                asset_id=asset_id,
                supported_metrics=(CanonicalMetric.ENERGY_TOTAL,),
            )

        natively_bound = self._get_natively_bound_metrics(asset_id)
        if natively_bound:
            self._raise_asset_metric_unavailable(
                metric=metric,
                asset_id=asset_id,
                supported_metrics=tuple(natively_bound),
            )

        mapping = self._require_metric_mapping(metric)

        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._runtime_settings_for(metric.value, asset_id),
        )
        data = await self._fetch_complete_mapped_payload(
            endpoint=endpoint,
            params=params,
            mapping=mapping,
            period=period,
        )
        return parse_mapped_kpi_response(
            data,
            mapping,
            metric,
            asset_id,
            period,
            source_profile=self._profile_name,
        )

    async def _fetch_complete_mapped_payload(
        self,
        *,
        endpoint: str,
        params: dict[str, str],
        mapping: MetricMapping,
        period: TimePeriod,
    ) -> dict | list:
        """Fetch every page for mapped observation-series endpoints."""
        if not self._mapping_uses_observation_series(mapping, endpoint):
            return await self._retry_fetch(endpoint, params)

        request_params = dict(params)
        if period.display_name == "latest available":
            request_params.update({"count": "1", "page": "1", "descending": "true"})
            return await self._retry_fetch(endpoint, request_params)

        page_size = self._bounded_positive_int(mapping.get("page_size"), default=100, maximum=100)
        max_pages = self._bounded_positive_int(mapping.get("max_pages"), default=1000, maximum=10000)
        request_params.update({"count": str(page_size), "page": "1"})
        first_payload = await self._retry_fetch(endpoint, request_params)
        if not isinstance(first_payload, dict):
            return first_payload
        first_records = first_payload.get("records")
        if not isinstance(first_records, list):
            return first_payload

        all_records = list(first_records)
        total = self._payload_total_count(first_payload)
        page = 1
        current_count = len(first_records)
        while page < max_pages:
            if total is not None and len(all_records) >= total:
                break
            if total is None and current_count < page_size:
                break
            page += 1
            page_params = dict(request_params)
            page_params["page"] = str(page)
            payload = await self._retry_fetch(endpoint, page_params)
            if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                break
            records = payload["records"]
            current_count = len(records)
            if not records:
                break
            all_records.extend(records)
            if total is None:
                total = self._payload_total_count(payload)

        merged = dict(first_payload)
        merged["records"] = all_records
        if total is not None:
            merged["recordCount"] = total
        return merged

    @staticmethod
    def _mapping_uses_observation_series(mapping: MetricMapping, endpoint: str) -> bool:
        json_path = str(mapping.get("json_path", "") or "")
        return bool(
            mapping.get("series_path")
            or mapping.get("pagination")
            or mapping.get("aggregation")
            or ("/values" in endpoint and "records[" in json_path)
        )

    @staticmethod
    def _payload_total_count(payload: dict[str, Any]) -> int | None:
        for key in ("recordCount", "record_count", "total", "totalCount"):
            try:
                value = payload.get(key)
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _bounded_positive_int(raw: Any, *, default: int, maximum: int) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return min(max(value, 1), maximum)

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

        values: list[KPIResult] = []
        for asset_id in asset_ids:
            values.append(await self.get_kpi(metric, asset_id, period))

        sorted_values = sorted(
            values,
            key=lambda item: item.value,
            reverse=rank_descending(metric),
        )
        items = [
            ComparisonItem(
                asset_id=result.asset_id,
                value=result.value,
                rank=index + 1,
                source_observed_at=result.source_observed_at,
                sample_count=result.sample_count,
                coverage_status=result.coverage_status,
            )
            for index, result in enumerate(sorted_values)
        ]

        winner_id = items[0].asset_id
        difference = round(
            abs(max(result.value for result in values) - min(result.value for result in values)),
            2,
        )
        coverage_status = (
            "complete"
            if all(result.coverage_status == "complete" for result in values)
            else "partial"
        )
        warnings = [warning for result in values for warning in result.warnings]

        return ComparisonResult(
            metric=metric,
            items=items,
            winner_id=winner_id,
            difference=difference,
            unit=values[0].unit,
            period=period,
            aggregation=values[0].aggregation,
            source_profile=self._profile_name,
            coverage_status=coverage_status,
            warnings=warnings,
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
        data = await self._fetch_complete_mapped_payload(
            endpoint=endpoint,
            params=params,
            mapping=mapping,
            period=period,
        )

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
        total = self._payload_total_count(data) if isinstance(data, dict) else None
        coverage_status = "complete"
        warnings: list[str] = []
        if total is not None and total > len(points):
            coverage_status = "partial"
            warnings.append(f"Only {len(points)} of {total} trend observations were retrieved.")
        return TrendResult(
            metric=metric,
            asset_id=asset_id,
            data_points=points,
            direction=direction,
            change_percent=change_percent,
            period=period,
            granularity=granularity,
            source_profile=self._profile_name,
            coverage_status=coverage_status,
            warnings=warnings,
        )

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> dict | list:
        """Fetch and return mapped endpoint payload without normalization."""
        self._ensure_initialized()
        if (
            self._is_energy_only_asset(asset_id)
            and metric != CanonicalMetric.ENERGY_TOTAL
        ):
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

    def get_scannable_pairs(
        self,
    ) -> list[tuple[CanonicalMetric, str]]:
        """Return only (metric, asset_id) tuples backed by a metric_resource."""
        mappings = self._load_asset_mappings()
        pairs: list[tuple[CanonicalMetric, str]] = []
        for asset_id, mapping in mappings.items():
            if not isinstance(mapping, dict):
                continue
            resources = mapping.get("metric_resources", {})
            if not isinstance(resources, dict):
                continue
            for metric_name, resource_id in resources.items():
                if not str(resource_id).strip():
                    continue
                try:
                    pairs.append(
                        (CanonicalMetric.from_string(metric_name), str(asset_id)),
                    )
                except ValueError:
                    continue
        return pairs

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
        already_initialized = self._session is not None and not self._session.closed
        try:
            if not already_initialized:
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
            # A status probe may run against the skill's long-lived adapter.
            # Preserve that shared session; only clean up a session created
            # specifically for this standalone connection test.
            if not already_initialized:
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
        """Try common discovery endpoints and convert records to Assets."""
        if self._session is None:
            return []

        seen_ids: set[str] = set()
        for endpoint in self._ASSET_DISCOVERY_ENDPOINTS:
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
        return capability_mode == "energy_only"

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

    def _get_natively_bound_metrics(
        self, asset_id: str,
    ) -> list[CanonicalMetric]:
        """Return canonical metrics with native bindings for an asset.

        Returns an empty list when the asset has no native bindings
        configured, signalling that the generic metric mapping path
        should be attempted instead.
        """
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return []
        native_bindings = mapping.get("native_metric_bindings")
        if not isinstance(native_bindings, dict) or not native_bindings:
            return []
        bound: list[CanonicalMetric] = []
        for key in native_bindings:
            try:
                bound.append(CanonicalMetric(key))
            except ValueError:
                continue
        return bound

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
            return await self._query_seu_energy_total(asset_id=asset_id, period=period)
        if strategy == "metric_item_last_value":
            return await self._query_metric_item_last_value(
                metric=metric,
                asset_id=asset_id,
                period=period,
                binding=binding,
            )
        raise AdapterError(
            message=f"Unsupported native binding strategy '{strategy}' for {metric.value}",
            code="GENERIC_REST_NATIVE_BINDING_INVALID",
            platform="generic_rest",
        )

    async def _query_metric_item_last_value(
        self,
        *,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        binding: dict[str, Any],
    ) -> KPIResult:
        """Fetch a Reneryo metric item counter and read its latest value."""
        if period.display_name != "latest available":
            raise AdapterError(
                message="Native metric item lastValue does not represent a requested historical period",
                code="GENERIC_REST_PERIOD_UNSUPPORTED",
                platform="generic_rest",
                user_message=(
                    "That source exposes only the latest counter value for this asset. "
                    "Ask for the current value or configure a time-series mapping for period totals."
                ),
            )
        resource_id = str(
            binding.get("resource_id")
            or binding.get("resource_uuid")
            or binding.get("metric_id")
            or binding.get("item_id")
            or self._resolve_metric_resource_id(metric.value, asset_id)
            or "",
        ).strip()
        if not resource_id:
            raise AdapterError(
                message=f"Native metric item binding for {asset_id}/{metric.value} has no resource_id",
                code="GENERIC_REST_NATIVE_BINDING_INVALID",
                platform="generic_rest",
            )

        endpoint_templates: tuple[str, ...]
        configured_endpoint = str(binding.get("endpoint", "") or "").strip()
        if configured_endpoint:
            endpoint_templates = (configured_endpoint,)
        else:
            endpoint_templates = self._METRIC_ITEM_ENDPOINTS

        payload: dict | list | None = None
        for template in endpoint_templates:
            endpoint = template.format(
                resource_id=resource_id,
                resource_uuid=resource_id,
                metric_id=resource_id,
                item_id=resource_id,
            )
            try:
                payload = await self._retry_fetch(endpoint, None)
            except AdapterError as exc:
                if exc.code in {"GENERIC_REST_ENDPOINT_NOT_FOUND", "GENERIC_REST_UNEXPECTED_STATUS"}:
                    continue
                raise
            else:
                break

        if not isinstance(payload, dict):
            raise AdapterError(
                message=f"Metric item endpoint returned invalid payload for '{asset_id}'",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )

        value_key = str(binding.get("value_key", "lastValue") or "lastValue").strip()
        try:
            value = float(payload.get(value_key))
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                message=f"Metric item '{resource_id}' has non-numeric {value_key}",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            ) from exc

        observed_at = self._native_observation_time(payload)
        warnings = () if observed_at else (
            "The latest-value source did not provide an observation timestamp.",
        )
        return KPIResult(
            metric=metric,
            value=value,
            unit=str(binding.get("unit") or metric.default_unit),
            asset_id=asset_id,
            period=period,
            timestamp=datetime.now(tz=timezone.utc),
            source_observed_at=observed_at,
            source_period_start=observed_at,
            source_period_end=observed_at,
            sample_count=1,
            aggregation="latest",
            source_profile=self._profile_name,
            coverage_status="complete" if observed_at else "unknown",
            warnings=warnings,
        )

    async def _query_seu_energy_total(self, *, asset_id: str, period: TimePeriod) -> KPIResult:
        """Fetch aggregate energy consumption from item endpoint."""
        start_iso = self._to_iso8601(period.start)
        end_iso = self._to_iso8601(period.end)
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

        observed_at = self._native_observation_time(selected)
        warnings = () if observed_at else (
            "The aggregate source did not provide an observation timestamp.",
        )
        return KPIResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            value=value,
            unit="kWh",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.now(tz=timezone.utc),
            source_observed_at=observed_at,
            source_period_start=period.start,
            source_period_end=period.end,
            sample_count=1,
            aggregation="sum",
            source_profile=self._profile_name,
            coverage_status="complete" if observed_at else "unknown",
            warnings=warnings,
        )

    @staticmethod
    def _native_observation_time(payload: dict[str, Any]) -> datetime | None:
        """Read a source timestamp without substituting retrieval time."""
        for key in (
            "timestamp",
            "datetime",
            "dateTime",
            "lastValueTimestamp",
            "lastValueDatetime",
            "lastUpdate",
            "updatedAt",
        ):
            raw = payload.get(key)
            if isinstance(raw, datetime):
                return raw.replace(tzinfo=raw.tzinfo or timezone.utc).astimezone(timezone.utc)
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
        return None

    @staticmethod
    def _to_iso8601(value: datetime) -> str:
        """Format datetime as ISO 8601 for upstream query parameters."""
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
