"""
ReneryoAdapter — RENERYO Manufacturing Platform Adapter.

Connects to the RENERYO REST API to fetch real manufacturing KPIs.
Supports bearer token and session-cookie authentication (DEC-022).

Dependencies:
    - aiohttp: Async HTTP client for RENERYO REST API calls.
    - _parsers: Response JSON → domain model parsers.
    - _normalizers: Native → mock format transformers.
"""

from __future__ import annotations

import logging
from urllib.parse import quote
from typing import TYPE_CHECKING

import aiohttp

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.reneryo._endpoints import (
    ENDPOINT_MAP,
    REAL_ENERGY_METRICS,
    REAL_METRIC_RESOURCE_VALUES_ENDPOINT,
    REAL_METER_ENDPOINT,
    REAL_SEU_GRAPH_ENDPOINT,
    REAL_SEU_ITEMS_ENDPOINT,
    REAL_SEU_VALUES_ENDPOINT,
    REAL_SUPPORTED_METRICS,
    SUPPORTED_CAPABILITIES,
)
from skill.adapters.reneryo._connection_test import ReneryoConnectionTestMixin
from skill.adapters.reneryo._http import ReneryoHttpMixin
from skill.adapters.reneryo._metric_mapping import (
    MetricMapping,
    parse_mapped_kpi_response,
    resolve_kpi_request,
)
from skill.adapters.reneryo._normalizers import (
    is_native_format,
    normalize_meter_to_kpi,
    normalize_metric_resource_to_kpi,
    normalize_metric_resource_to_trend,
    normalize_seu_graph_to_trend,
    normalize_seus_to_comparison,
    normalize_seu_values_to_kpi,
    normalize_seu_values_to_trend,
    normalize_meters_to_comparison,
    normalize_meters_to_raw,
    normalize_meters_to_trend,
)
from skill.adapters.reneryo._parsers import (
    parse_comparison_response,
    parse_kpi_response,
    parse_raw_data_response,
    parse_trend_response,
)
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod

if TYPE_CHECKING:
    from skill.domain.models import DataPoint
    from skill.domain.results import ComparisonResult, KPIResult, TrendResult

logger = logging.getLogger(__name__)


class ReneryoAdapter(ReneryoConnectionTestMixin, ReneryoHttpMixin, ManufacturingAdapter):
    """
    RENERYO manufacturing platform adapter.

    Connects to RENERYO REST API to fetch real manufacturing KPIs
    via aiohttp. Supports bearer and cookie auth (DEC-022).

    DEC-001 Compliance:
        This adapter package and AdapterFactory registration are the ONLY
        places where "RENERYO" appears. Handlers, domain, and use_cases
        remain platform-agnostic.
    """

    # Exposed for test introspection (see test_endpoint_map_covers_all_metrics)
    _ENDPOINT_MAP = ENDPOINT_MAP

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        auth_type: str = "bearer",
        api_format: str = "mock",
        native_seu_id: str = "",
        settings_service=None,
        profile_name: str = "",
        extra_settings: dict | None = None,
        asset_mappings: dict[str, dict[str, object]] | None = None,
    ) -> None:
        """
        Initialize RENERYO adapter with connection parameters.

        Args:
            api_url: Base URL for the RENERYO REST API.
            api_key: Authentication key for RENERYO API.
            timeout: Request timeout in seconds (default 30).
            auth_type: Auth mode — "bearer" or "cookie" (DEC-022).
            api_format: Response format — "mock" (per-metric endpoints)
                or "native" (real RENERYO API with /api/u/ paths).
            native_seu_id: Legacy fallback SEU UUID for direct per-unit endpoint.
            asset_mappings: Asset-to-resource mapping configuration.
        """
        self._api_url = api_url.rstrip("/") if api_url else ""
        self._api_key = api_key
        self._timeout = timeout
        self._auth_type = auth_type
        self._api_format = api_format
        self._native_seu_id = native_seu_id.strip()
        self._settings_service = settings_service
        self._profile_name = profile_name
        self._extra_settings = extra_settings or {}
        self._asset_mappings = asset_mappings or {}
        self._session: aiohttp.ClientSession | None = None

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """
        Retrieve a single KPI value from the RENERYO API.

        Args:
            metric: The canonical metric to retrieve.
            asset_id: Target asset/machine identifier.
            period: Time period for the measurement.

        Returns:
            KPIResult with value, unit, and metadata.

        Raises:
            AdapterError: On connection, auth, or parse errors.
        """
        self._ensure_initialized()
        mapped_result = await self._get_kpi_from_mapping(metric, asset_id, period)
        if mapped_result is not None:
            return mapped_result

        endpoint = self._resolve_endpoint(metric, purpose="kpi", asset_id=asset_id)
        params = self._build_query_params(
            asset_id=asset_id,
            period=period,
            include_native_period=self._requires_native_period(endpoint),
        )
        try:
            data = await self._retry_fetch(endpoint, params)
        except AdapterError as exc:
            if self._should_fallback_from_seu(endpoint, exc):
                logger.warning(
                    "SEU endpoint failed (%s). Falling back to meter endpoint.",
                    exc.status_code,
                )
                endpoint = REAL_METER_ENDPOINT
                params = self._build_query_params(
                    asset_id=asset_id,
                    period=period,
                    include_native_period=False,
                )
                data = await self._retry_fetch(endpoint, params)
            else:
                raise
        if is_native_format(data):
            try:
                if self._is_seu_endpoint(endpoint):
                    data = normalize_seu_values_to_kpi(data)
                elif self._is_metric_resource_endpoint(endpoint):
                    data = normalize_metric_resource_to_kpi(data)
                else:
                    data = normalize_meter_to_kpi(data, asset_id)
            except KeyError as exc:
                raise AdapterError(
                    message=f"Requested asset not found for KPI query: {asset_id}",
                    code="RENERYO_ASSET_NOT_FOUND",
                    platform="reneryo",
                    user_message=(
                        f"I couldn't find data for {asset_id}. "
                        "Please try another asset name."
                    ),
                ) from exc
        return parse_kpi_response(data, metric, asset_id, period)

    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """
        Compare a metric across multiple assets via the RENERYO API.

        Args:
            metric: The canonical metric to compare.
            asset_ids: List of assets to compare (2 or more).
            period: Time period for comparison.

        Returns:
            ComparisonResult with ranked items and winner.

        Raises:
            AdapterError: On connection, auth, or parse errors.
        """
        self._ensure_initialized()
        endpoint = self._resolve_endpoint(
            metric, purpose="compare", asset_ids=asset_ids,
        )
        params = self._build_compare_query_params(
            endpoint=endpoint,
            asset_ids=asset_ids,
            period=period,
        )
        data = await self._retry_fetch(endpoint, params)
        if is_native_format(data):
            try:
                if self._is_seu_collection_endpoint(endpoint):
                    resolved_ids = [
                        self._resolve_seu_id(asset) or asset
                        for asset in asset_ids
                    ]
                    data = normalize_seus_to_comparison(data, resolved_ids)
                else:
                    data = normalize_meters_to_comparison(data, asset_ids)
            except KeyError as exc:
                requested = ", ".join(asset_ids)
                raise AdapterError(
                    message=f"Requested comparison assets not found: {requested}",
                    code="RENERYO_ASSET_NOT_FOUND",
                    platform="reneryo",
                    user_message=(
                        "I couldn't find one of those assets. "
                        "Please use exact asset names, for example: Compressor-1 and Compressor-2."
                    ),
                ) from exc
        if not isinstance(data, list):
            data = [data]
        return parse_comparison_response(data, metric, period)

    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """
        Get time-series data with trend direction from the RENERYO API.

        Args:
            metric: The canonical metric to trend.
            asset_id: Target asset identifier.
            period: Time period to analyze.
            granularity: Data point frequency.

        Returns:
            TrendResult with data points, direction, and change %.

        Raises:
            AdapterError: On connection, auth, or parse errors.
        """
        self._ensure_initialized()
        endpoint = self._resolve_endpoint(metric, purpose="trend", asset_id=asset_id)
        params = self._build_query_params(
            asset_id=asset_id,
            period=period,
            granularity=granularity,
            include_native_period=self._requires_native_period(endpoint),
        )
        try:
            data = await self._retry_fetch(endpoint, params)
        except AdapterError as exc:
            if self._should_fallback_from_seu(endpoint, exc):
                logger.warning(
                    "SEU trend endpoint failed (%s). Falling back to meter endpoint.",
                    exc.status_code,
                )
                endpoint = REAL_METER_ENDPOINT
                params = self._build_query_params(
                    asset_id=asset_id,
                    period=period,
                    granularity=granularity,
                    include_native_period=False,
                )
                data = await self._retry_fetch(endpoint, params)
            else:
                raise
        if is_native_format(data):
            if self._is_seu_endpoint(endpoint):
                data = normalize_seu_values_to_trend(data)
            elif self._is_seu_graph_endpoint(endpoint):
                data = normalize_seu_graph_to_trend(
                    data,
                    seu_id=self._resolve_seu_id(asset_id),
                )
            elif self._is_metric_resource_endpoint(endpoint):
                data = normalize_metric_resource_to_trend(data)
            else:
                data = normalize_meters_to_trend(data)
        if not isinstance(data, list):
            data = [data]
        return parse_trend_response(data, metric, asset_id, period, granularity)

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> list[DataPoint]:
        """
        Fetch raw time-series data from the RENERYO native endpoint.

        Args:
            metric: The canonical metric to retrieve data for.
            asset_id: Target asset identifier.
            period: Time period for data retrieval.

        Returns:
            List of DataPoint objects.

        Raises:
            AdapterError: On connection, auth, or parse errors.
        """
        self._ensure_initialized()
        params = self._build_query_params(
            asset_id=asset_id, period=period,
        )
        data = await self._retry_fetch(
            REAL_METER_ENDPOINT, params,
        )
        if is_native_format(data):
            data = normalize_meters_to_raw(data)
        if not isinstance(data, list):
            data = [data]
        return parse_raw_data_response(data, metric)

    # =========================================================================
    # Capability Discovery
    # =========================================================================

    def supports_capability(self, capability: str) -> bool:
        """
        Check if the RENERYO adapter supports a capability.

        Args:
            capability: Capability name.

        Returns:
            True if capability is supported, False otherwise.
        """
        return capability in SUPPORTED_CAPABILITIES

    def get_supported_metrics(self) -> list[CanonicalMetric]:
        """
        Return metrics mapped to RENERYO API endpoints.

        Returns:
            List of CanonicalMetric values with known endpoint mappings.
        """
        return list(ENDPOINT_MAP.keys())

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self) -> None:
        """Create aiohttp session with auth headers and timeout."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        headers = self._build_auth_headers()
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
        )
        logger.info(
            "ReneryoAdapter initialized — API URL: %s, auth: %s, format: %s",
            self._api_url,
            self._auth_type,
            self._api_format,
        )

    async def shutdown(self) -> None:
        """Close aiohttp session gracefully."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info("ReneryoAdapter shut down")

    @property
    def platform_name(self) -> str:
        """Return platform name for display and logging."""
        return "RENERYO"

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _resolve_endpoint(
        self,
        metric: CanonicalMetric,
        *,
        purpose: str,
        asset_id: str = "",
        asset_ids: list[str] | None = None,
    ) -> str:
        """
        Look up the REST endpoint for a canonical metric.

        For mock format: returns per-metric paths from endpoint map.
        For native format: returns the shared meter endpoint for
        energy metrics, falling back to the endpoint map otherwise.

        Args:
            metric: The canonical metric.

        Returns:
            REST path string.

        Raises:
            AdapterError: If metric has no mapped endpoint.
        """
        if self._api_format == "native":
            if metric == CanonicalMetric.ENERGY_PER_UNIT:
                if purpose in {"kpi", "trend"}:
                    seu_id = self._resolve_seu_id(asset_id)
                    if seu_id:
                        encoded_seu_id = quote(seu_id, safe="")
                        return REAL_SEU_VALUES_ENDPOINT.format(seu_id=encoded_seu_id)
                    if purpose == "trend":
                        return REAL_SEU_GRAPH_ENDPOINT
                    return REAL_METER_ENDPOINT
                if purpose == "compare":
                    if asset_ids and all(self._resolve_seu_id(aid) for aid in asset_ids):
                        return REAL_SEU_ITEMS_ENDPOINT
                    return REAL_METER_ENDPOINT

            if metric in REAL_ENERGY_METRICS:
                return REAL_METER_ENDPOINT

            if metric in REAL_SUPPORTED_METRICS and purpose in {"kpi", "trend"}:
                resource_id = self._resolve_metric_resource_id(metric, asset_id)
                if resource_id:
                    encoded_resource_id = quote(resource_id, safe="")
                    return REAL_METRIC_RESOURCE_VALUES_ENDPOINT.format(
                        resource_id=encoded_resource_id,
                    )
        endpoint = ENDPOINT_MAP.get(metric)
        if endpoint is None:
            raise AdapterError(
                message=f"No endpoint mapped for metric {metric.value}",
                code="RENERYO_ENDPOINT_NOT_FOUND",
                platform="reneryo",
            )
        return endpoint

    def _build_query_params(
        self,
        asset_id: str = "",
        period: TimePeriod | None = None,
        granularity: str = "",
        include_native_period: bool = False,
    ) -> dict[str, str]:
        """
        Build query parameters for both mock and real API formats.

        For mock API: uses ``asset_id``, ``period``, ``granularity``.
        For real API: uses ``datetimeMin``/``datetimeMax`` ISO params.

        Args:
            asset_id: Target asset identifier.
            period: Time period for the query.
            granularity: Data point frequency (for trend queries).

        Returns:
            Dict of query parameter key-value pairs.
        """
        params: dict[str, str] = {}
        if period is not None:
            params["datetimeMin"] = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["datetimeMax"] = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")
        if self._api_format == "mock":
            if period is not None:
                params["period"] = period.display_name or "today"
            if asset_id:
                params["asset_id"] = asset_id
            if granularity:
                params["granularity"] = granularity
        elif include_native_period:
            params["period"] = self._native_period_bucket(granularity)
        return params

    def _build_compare_query_params(
        self,
        *,
        endpoint: str,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> dict[str, str]:
        """Build compare-query params based on endpoint type."""
        params = self._build_query_params(period=period)
        if self._api_format != "native":
            params["asset_ids"] = ",".join(asset_ids)
            return params

        if self._is_seu_collection_endpoint(endpoint):
            seu_ids = [
                self._resolve_seu_id(asset_id)
                for asset_id in asset_ids
            ]
            params["seuIds"] = ",".join(seu_id for seu_id in seu_ids if seu_id)
            return params

        params["asset_ids"] = ",".join(asset_ids)
        return params

    def _requires_native_period(self, endpoint: str) -> bool:
        """Return whether endpoint requires ``period`` query parameter."""
        return self._is_seu_endpoint(endpoint) or self._is_metric_resource_endpoint(endpoint)

    @staticmethod
    def _native_period_bucket(granularity: str) -> str:
        """
        Map internal granularity naming to RENERYO SEU period values.
        """
        granularity_key = (granularity or "daily").strip().lower()
        mapping = {
            "hourly": "HOURLY",
            "daily": "DAILY",
            "weekly": "WEEKLY",
            "monthly": "MONTHLY",
        }
        return mapping.get(granularity_key, "DAILY")

    @staticmethod
    def _is_seu_endpoint(endpoint: str) -> bool:
        return "/measurement/seu/item/" in endpoint

    @staticmethod
    def _is_seu_graph_endpoint(endpoint: str) -> bool:
        return endpoint.endswith("/measurement/seu/graph")

    @staticmethod
    def _is_seu_collection_endpoint(endpoint: str) -> bool:
        return endpoint.endswith("/measurement/seu/item")

    @staticmethod
    def _is_metric_resource_endpoint(endpoint: str) -> bool:
        return "/measurement/metric/resource/" in endpoint and endpoint.endswith("/values")

    @staticmethod
    def _should_fallback_from_seu(endpoint: str, exc: AdapterError) -> bool:
        """
        Fallback trigger for SEU endpoint misconfiguration.

        Invalid/unauthorized SEU IDs often return 400/404 in native API.
        In that case we gracefully switch to meter endpoint so voice UX
        still returns a value instead of a hard failure.
        """
        return (
            "/measurement/seu/item/" in endpoint
            and exc.status_code in {400, 404}
        )

    async def _get_kpi_from_mapping(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult | None:
        """Fetch KPI using profile-scoped metric mapping when present."""
        mapping = self._lookup_metric_mapping(metric)
        if mapping is None:
            return None

        endpoint, params = resolve_kpi_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._string_settings(),
        )
        data = await self._retry_fetch(endpoint, params)
        return parse_mapped_kpi_response(data, mapping, metric, asset_id, period)

    def _lookup_metric_mapping(self, metric: CanonicalMetric) -> MetricMapping | None:
        if not self._settings_service or not self._profile_name:
            return None
        return self._settings_service.get_metric_mapping(self._profile_name, metric)

    def _string_settings(self) -> dict[str, str]:
        return {k: str(v) for k, v in self._extra_settings.items()}

    def _resolve_seu_id(self, asset_id: str) -> str:
        """
        Resolve SEU UUID for a requested asset using mapping config.
        """
        if self._asset_mappings:
            mapping = self._resolve_asset_mapping(asset_id)
            if mapping is not None:
                seu_id = str(mapping.get("seu_id", "")).strip()
                if seu_id:
                    return seu_id
        return self._native_seu_id

    def _resolve_metric_resource_id(
        self,
        metric: CanonicalMetric,
        asset_id: str,
    ) -> str:
        """Resolve metric-resource UUID for an asset + metric pair."""
        if not self._asset_mappings:
            return ""
        mapping = self._resolve_asset_mapping(asset_id)
        if mapping is None:
            return ""
        resource_map = mapping.get("metric_resources")
        if not isinstance(resource_map, dict):
            return ""
        resource_id = resource_map.get(metric.value)
        if not resource_id and metric == CanonicalMetric.SCRAP_RATE:
            resource_id = resource_map.get("scrap_rate")
        if not resource_id and metric == CanonicalMetric.OEE:
            resource_id = resource_map.get("oee")
        return str(resource_id or "").strip()

    def _resolve_asset_mapping(self, asset_id: str) -> dict[str, object] | None:
        """Resolve mapping entry by exact key, normalized key, or generic fallback."""
        if not self._asset_mappings:
            return None
        requested = (asset_id or "").strip()
        if requested in self._asset_mappings:
            entry = self._asset_mappings[requested]
            return entry if isinstance(entry, dict) else None

        requested_norm = self._normalize_asset_key(requested)
        for key, value in self._asset_mappings.items():
            if self._normalize_asset_key(key) == requested_norm and isinstance(value, dict):
                return value

        if requested.lower() in {"", "default", "all", "overall"}:
            first_value = next(iter(self._asset_mappings.values()), None)
            if isinstance(first_value, dict):
                return first_value
        return None

    @staticmethod
    def _normalize_asset_key(value: str) -> str:
        return "".join(ch for ch in (value or "").lower() if ch.isalnum())
