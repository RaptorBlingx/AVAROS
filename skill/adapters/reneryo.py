"""
ReneryoAdapter — RENERYO Manufacturing Platform Adapter.

Connects to the RENERYO REST API to fetch real manufacturing KPIs.
Supports bearer token and session-cookie authentication (DEC-022).

Dependencies:
    - aiohttp: Async HTTP client for RENERYO REST API calls.
    - skill.adapters._reneryo_parsers: Response JSON → domain model parsers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp

from skill.adapters._reneryo_normalizers import (
    is_native_format,
    normalize_meter_to_kpi,
    normalize_meters_to_comparison,
    normalize_meters_to_raw,
    normalize_meters_to_trend,
)
from skill.adapters._reneryo_parsers import (
    parse_comparison_response,
    parse_kpi_response,
    parse_raw_data_response,
    parse_trend_response,
)
from skill.adapters.base import ManufacturingAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod

if TYPE_CHECKING:
    from skill.domain.models import DataPoint, WhatIfScenario
    from skill.domain.results import (
        AnomalyResult,
        ComparisonResult,
        KPIResult,
        TrendResult,
        WhatIfResult,
    )

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_BACKOFF_FACTORS = (0.5, 1.0, 2.0)


class ReneryoAdapter(ManufacturingAdapter):
    """
    RENERYO manufacturing platform adapter.

    Connects to RENERYO REST API to fetch real manufacturing KPIs
    via aiohttp. Supports bearer and cookie auth (DEC-022).

    DEC-001 Compliance:
        This adapter file and AdapterFactory registration are the ONLY
        places where "RENERYO" appears. Handlers, domain, and use_cases
        remain platform-agnostic.
    """

    # =========================================================================
    # RENERYO API Endpoint Mapping
    # =========================================================================

    # Mock API endpoints (used by reneryo-mock server for per-metric routes)
    _ENDPOINT_MAP: dict[CanonicalMetric, str] = {
        # Energy Metrics
        CanonicalMetric.ENERGY_PER_UNIT: "/api/v1/kpis/energy/per-unit",
        CanonicalMetric.ENERGY_TOTAL: "/api/v1/kpis/energy/total",
        CanonicalMetric.PEAK_DEMAND: "/api/v1/kpis/energy/peak-demand",
        CanonicalMetric.PEAK_TARIFF_EXPOSURE: "/api/v1/kpis/energy/tariff-exposure",
        # Material Metrics
        CanonicalMetric.SCRAP_RATE: "/api/v1/kpis/material/scrap-rate",
        CanonicalMetric.REWORK_RATE: "/api/v1/kpis/material/rework-rate",
        CanonicalMetric.MATERIAL_EFFICIENCY: "/api/v1/kpis/material/efficiency",
        CanonicalMetric.RECYCLED_CONTENT: "/api/v1/kpis/material/recycled-content",
        # Supplier Metrics
        CanonicalMetric.SUPPLIER_LEAD_TIME: "/api/v1/kpis/supplier/lead-time",
        CanonicalMetric.SUPPLIER_DEFECT_RATE: "/api/v1/kpis/supplier/defect-rate",
        CanonicalMetric.SUPPLIER_ON_TIME: "/api/v1/kpis/supplier/on-time",
        CanonicalMetric.SUPPLIER_CO2_PER_KG: "/api/v1/kpis/supplier/co2-per-kg",
        # Production Metrics
        CanonicalMetric.OEE: "/api/v1/kpis/production/oee",
        CanonicalMetric.THROUGHPUT: "/api/v1/kpis/production/throughput",
        CanonicalMetric.CYCLE_TIME: "/api/v1/kpis/production/cycle-time",
        CanonicalMetric.CHANGEOVER_TIME: "/api/v1/kpis/production/changeover-time",
        # Carbon Metrics
        CanonicalMetric.CO2_PER_UNIT: "/api/v1/kpis/carbon/per-unit",
        CanonicalMetric.CO2_TOTAL: "/api/v1/kpis/carbon/total",
        CanonicalMetric.CO2_PER_BATCH: "/api/v1/kpis/carbon/per-batch",
    }

    # Real RENERYO API endpoints — energy metrics share one endpoint
    _REAL_METER_ENDPOINT = "/api/u/measurement/meter/item"
    _REAL_METRIC_ENDPOINT = "/api/u/measurement/metric/item"

    # Metrics available in the real RENERYO API (energy monitoring platform)
    _REAL_ENERGY_METRICS: frozenset[CanonicalMetric] = frozenset({
        CanonicalMetric.ENERGY_PER_UNIT,
        CanonicalMetric.ENERGY_TOTAL,
        CanonicalMetric.PEAK_DEMAND,
        CanonicalMetric.PEAK_TARIFF_EXPOSURE,
    })

    _SUPPORTED_CAPABILITIES: set[str] = {"carbon", "realtime"}

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        auth_type: str = "bearer",
        api_format: str = "mock",
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
        """
        self._api_url = api_url.rstrip("/") if api_url else ""
        self._api_key = api_key
        self._timeout = timeout
        self._auth_type = auth_type
        self._api_format = api_format
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
        endpoint = self._resolve_endpoint(metric)
        params = self._build_query_params(asset_id=asset_id, period=period)
        data = await self._retry_fetch(endpoint, params)
        if is_native_format(data):
            data = normalize_meter_to_kpi(data, asset_id)
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
        endpoint = self._resolve_endpoint(metric)
        params = self._build_query_params(period=period)
        params["asset_ids"] = ",".join(asset_ids)
        data = await self._retry_fetch(endpoint, params)
        if is_native_format(data):
            data = normalize_meters_to_comparison(data, asset_ids)
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
        endpoint = self._resolve_endpoint(metric)
        params = self._build_query_params(
            asset_id=asset_id, period=period, granularity=granularity,
        )
        data = await self._retry_fetch(endpoint, params)
        if is_native_format(data):
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
            self._REAL_METER_ENDPOINT, params,
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
        return capability in self._SUPPORTED_CAPABILITIES

    def get_supported_metrics(self) -> list[CanonicalMetric]:
        """
        Return metrics mapped to RENERYO API endpoints.

        Returns:
            List of CanonicalMetric values with known endpoint mappings.
        """
        return list(self._ENDPOINT_MAP.keys())

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self) -> None:
        """Create aiohttp session with auth headers and timeout."""
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
    # HTTP Layer
    # =========================================================================

    async def _fetch(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict | list:
        """
        Execute GET request against RENERYO API.

        Args:
            endpoint: REST path (from _ENDPOINT_MAP).
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            AdapterError: On connection, auth, timeout, or parse errors.
        """
        self._ensure_initialized()
        assert self._session is not None  # guarded by _ensure_initialized
        url = f"{self._api_url}{endpoint}"

        try:
            async with self._session.get(url, params=params) as resp:
                return await self._handle_response(resp, endpoint)
        except AdapterError:
            raise
        except aiohttp.ClientConnectorError as exc:
            raise AdapterError(
                message=f"Connection failed: {exc}",
                code="RENERYO_CONNECTION_FAILED",
                platform="reneryo",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise AdapterError(
                message=f"Request timed out after {self._timeout}s: {endpoint}",
                code="RENERYO_TIMEOUT",
                platform="reneryo",
            ) from exc

    async def _handle_response(
        self,
        resp: aiohttp.ClientResponse,
        endpoint: str,
    ) -> dict | list:
        """
        Handle HTTP response status and parse JSON body.

        Args:
            resp: aiohttp response object.
            endpoint: Endpoint path for error messages.

        Returns:
            Parsed JSON body.

        Raises:
            AdapterError: On non-200 status or JSON parse failure.
        """
        if resp.status == 200:
            return await self._parse_json(resp, endpoint)
        if resp.status == 401:
            raise AdapterError(
                message=f"Authentication failed for {endpoint}",
                code="RENERYO_AUTH_FAILED",
                platform="reneryo",
                status_code=401,
            )
        if resp.status == 404:
            raise AdapterError(
                message=f"Endpoint not found: {endpoint}",
                code="RENERYO_ENDPOINT_NOT_FOUND",
                platform="reneryo",
                status_code=404,
            )
        if resp.status >= 500:
            raise AdapterError(
                message=f"Server error {resp.status} on {endpoint}",
                code="RENERYO_SERVER_ERROR",
                platform="reneryo",
                status_code=resp.status,
            )
        raise AdapterError(
            message=f"Unexpected status {resp.status} on {endpoint}",
            code="RENERYO_UNEXPECTED_STATUS",
            platform="reneryo",
            status_code=resp.status,
        )

    async def _retry_fetch(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
        max_retries: int = _MAX_RETRIES,
    ) -> dict | list:
        """
        Fetch with retry on 5xx errors using exponential backoff.

        Args:
            endpoint: REST path.
            params: Optional query parameters.
            max_retries: Maximum retry attempts (default 3).

        Returns:
            Parsed JSON response.

        Raises:
            AdapterError: After all retries exhausted or on non-retryable error.
        """
        last_error: AdapterError | None = None
        for attempt in range(max_retries + 1):
            try:
                return await self._fetch(endpoint, params)
            except AdapterError as exc:
                if exc.code != "RENERYO_SERVER_ERROR":
                    raise
                last_error = exc
                if attempt < max_retries:
                    delay = _BACKOFF_FACTORS[attempt]
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs (status=%s)",
                        attempt + 1,
                        max_retries,
                        endpoint,
                        delay,
                        exc.status_code,
                    )
                    await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _build_auth_headers(self) -> dict[str, str]:
        """
        Build authentication headers based on auth_type (DEC-022).

        Returns:
            Dict with the appropriate auth header.
        """
        if self._auth_type == "cookie":
            return {"Cookie": f"S={self._api_key}"}
        return {"Authorization": f"Bearer {self._api_key}"}

    def _ensure_initialized(self) -> None:
        """
        Guard: raise AdapterError if session is not created.

        Raises:
            AdapterError: If initialize() was not called.
        """
        if self._session is None:
            raise AdapterError(
                message="ReneryoAdapter not initialized — call initialize() first",
                code="RENERYO_NOT_CONNECTED",
                platform="reneryo",
            )

    def _resolve_endpoint(self, metric: CanonicalMetric) -> str:
        """
        Look up the REST endpoint for a canonical metric.

        For mock format: returns per-metric paths from ``_ENDPOINT_MAP``.
        For native format: returns the shared meter endpoint for
        energy metrics, falling back to ``_ENDPOINT_MAP`` otherwise.

        Args:
            metric: The canonical metric.

        Returns:
            REST path string.

        Raises:
            AdapterError: If metric has no mapped endpoint.
        """
        if self._api_format == "native" and metric in self._REAL_ENERGY_METRICS:
            return self._REAL_METER_ENDPOINT
        endpoint = self._ENDPOINT_MAP.get(metric)
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
            params["datetimeMin"] = period.start.isoformat() + "Z"
            params["datetimeMax"] = period.end.isoformat() + "Z"
            params["period"] = period.display_name or "today"
        if asset_id:
            params["asset_id"] = asset_id
        if granularity:
            params["granularity"] = granularity
        return params

    @staticmethod
    async def _parse_json(
        resp: aiohttp.ClientResponse,
        endpoint: str,
    ) -> dict | list:
        """
        Parse JSON from response body.

        Args:
            resp: aiohttp response object.
            endpoint: Endpoint path for error context.

        Returns:
            Parsed JSON as dict or list.

        Raises:
            AdapterError: On JSON decode failure.
        """
        try:
            return await resp.json()
        except Exception as exc:
            raise AdapterError(
                message=f"Invalid JSON from {endpoint}: {exc}",
                code="RENERYO_INVALID_RESPONSE",
                platform="reneryo",
            ) from exc

    def _raise_not_connected(
        self,
        method: str,
        metric: CanonicalMetric,
    ) -> None:
        """
        Raise AdapterError indicating RENERYO API is not yet connected.

        Args:
            method: The query method that was called.
            metric: The metric that was requested.

        Raises:
            AdapterError: Always — with code RENERYO_NOT_CONNECTED.
        """
        endpoint = self._ENDPOINT_MAP.get(metric, "unknown")
        raise AdapterError(
            message=(
                f"RENERYO API not yet connected "
                f"(method={method}, metric={metric.value}, "
                f"endpoint={endpoint})"
            ),
            code="RENERYO_NOT_CONNECTED",
            platform="reneryo",
        )
