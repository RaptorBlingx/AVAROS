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

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import aiohttp

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.reneryo._endpoints import (
    ENDPOINT_MAP,
    REAL_ENERGY_METRICS,
    REAL_METER_ENDPOINT,
    SUPPORTED_CAPABILITIES,
)
from skill.adapters.reneryo._http import ReneryoHttpMixin
from skill.adapters.reneryo._normalizers import (
    is_native_format,
    normalize_meter_to_kpi,
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


class ReneryoAdapter(ReneryoHttpMixin, ManufacturingAdapter):
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
            REAL_METER_ENDPOINT, params,
        )
        if is_native_format(data):
            data = normalize_meters_to_raw(data)
        if not isinstance(data, list):
            data = [data]
        return parse_raw_data_response(data, metric)

    # =========================================================================
    # Connection Testing
    # =========================================================================

    async def test_connection(self) -> ConnectionTestResult:
        """
        Test RENERYO platform connectivity.

        Performs:
            1. HTTP GET to meter endpoint with auth.
            2. Measures round-trip latency.
            3. Discovers available meters/resources.
            4. Validates auth credentials.

        Returns:
            ConnectionTestResult with latency and discovered meter names.
        """
        from skill.domain.results import ConnectionTestResult

        start = time.monotonic()
        session: aiohttp.ClientSession | None = None
        try:
            session = self._create_test_session()
            result = await self._execute_test_request(session, start)
        except aiohttp.ClientConnectorError as exc:
            result = self._build_connection_error(start, exc)
        except asyncio.TimeoutError:
            result = self._build_timeout_error(start)
        except Exception as exc:
            result = self._build_unknown_error(start, exc)
        finally:
            if session is not None:
                await session.close()
        return result

    def _create_test_session(self) -> aiohttp.ClientSession:
        """Create a temporary aiohttp session for connection testing."""
        timeout = aiohttp.ClientTimeout(total=min(self._timeout, 10))
        headers = self._build_auth_headers()
        return aiohttp.ClientSession(timeout=timeout, headers=headers)

    async def _execute_test_request(
        self,
        session: aiohttp.ClientSession,
        start: float,
    ) -> ConnectionTestResult:
        """
        Execute the test HTTP request and parse the response.

        Args:
            session: Temporary aiohttp session.
            start: Monotonic clock start time.

        Returns:
            ConnectionTestResult from the response.
        """
        from skill.domain.results import ConnectionTestResult

        url = f"{self._api_url}/api/u/measurement/meter/item"
        async with session.get(url) as response:
            elapsed = (time.monotonic() - start) * 1000
            return await self._parse_test_response(response, elapsed)

    async def _parse_test_response(
        self,
        response: aiohttp.ClientResponse,
        elapsed: float,
    ) -> ConnectionTestResult:
        """
        Parse HTTP response into a ConnectionTestResult.

        Args:
            response: aiohttp response from the test request.
            elapsed: Measured latency in milliseconds.

        Returns:
            ConnectionTestResult with status and discovered resources.
        """
        from skill.domain.results import ConnectionTestResult

        if response.status == 401:
            return ConnectionTestResult(
                success=False,
                latency_ms=round(elapsed, 1),
                message="Authentication failed — check API key",
                adapter_name=self.platform_name,
                error_code="RENERYO_AUTH_FAILED",
                error_details=f"HTTP 401 from {self._api_url}",
            )
        if response.status != 200:
            return ConnectionTestResult(
                success=False,
                latency_ms=round(elapsed, 1),
                message=f"Unexpected response: HTTP {response.status}",
                adapter_name=self.platform_name,
                error_code=f"HTTP_{response.status}",
                error_details=await response.text(),
            )
        return await self._parse_success_response(response, elapsed)

    async def _parse_success_response(
        self,
        response: aiohttp.ClientResponse,
        elapsed: float,
    ) -> ConnectionTestResult:
        """
        Parse a successful 200 response with meter discovery.

        Handles two response formats:
            - ``{"records": [{"name": "..."}]}`` — real RENERYO API
            - ``[{"meter": "..."}]`` — mock server (list at top level)

        Args:
            response: aiohttp 200 response.
            elapsed: Measured latency in milliseconds.

        Returns:
            ConnectionTestResult with discovered meter names.
        """
        from skill.domain.results import ConnectionTestResult

        data = await response.json()
        meter_names = self._extract_meter_names(data)
        return ConnectionTestResult(
            success=True,
            latency_ms=round(elapsed, 1),
            message=f"Connected — {len(meter_names)} meter(s) discovered",
            adapter_name=self.platform_name,
            resources_discovered=meter_names,
        )

    @staticmethod
    def _extract_meter_names(data: dict | list) -> tuple[str, ...]:
        """
        Extract unique meter names from API response.

        Args:
            data: Parsed JSON — dict with "records" key or raw list.

        Returns:
            Tuple of unique meter name strings.
        """
        if isinstance(data, dict):
            records = data.get("records", [])
        else:
            records = data if isinstance(data, list) else []

        seen: set[str] = set()
        names: list[str] = []
        for r in records:
            if not isinstance(r, dict):
                continue
            name = r.get("name", r.get("meter", r.get("id", "unknown")))
            if name not in seen:
                seen.add(name)
                names.append(name)
        return tuple(names)

    def _build_connection_error(
        self,
        start: float,
        exc: aiohttp.ClientConnectorError,
    ) -> ConnectionTestResult:
        """Build result for connection-refused / DNS errors."""
        from skill.domain.results import ConnectionTestResult

        elapsed = (time.monotonic() - start) * 1000
        return ConnectionTestResult(
            success=False,
            latency_ms=round(elapsed, 1),
            message="Cannot reach server — check URL and network",
            adapter_name=self.platform_name,
            error_code="RENERYO_CONNECTION_FAILED",
            error_details=str(exc),
        )

    def _build_timeout_error(self, start: float) -> ConnectionTestResult:
        """Build result for request timeout."""
        from skill.domain.results import ConnectionTestResult

        elapsed = (time.monotonic() - start) * 1000
        cap = min(self._timeout, 10)
        return ConnectionTestResult(
            success=False,
            latency_ms=round(elapsed, 1),
            message=f"Connection timed out after {cap}s",
            adapter_name=self.platform_name,
            error_code="RENERYO_TIMEOUT",
            error_details=f"Timeout connecting to {self._api_url}",
        )

    def _build_unknown_error(
        self,
        start: float,
        exc: Exception,
    ) -> ConnectionTestResult:
        """Build result for unexpected exceptions."""
        from skill.domain.results import ConnectionTestResult

        elapsed = (time.monotonic() - start) * 1000
        return ConnectionTestResult(
            success=False,
            latency_ms=round(elapsed, 1),
            message=f"Unexpected error: {type(exc).__name__}",
            adapter_name=self.platform_name,
            error_code="UNKNOWN",
            error_details=str(exc),
        )

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

    def _resolve_endpoint(self, metric: CanonicalMetric) -> str:
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
        if self._api_format == "native" and metric in REAL_ENERGY_METRICS:
            return REAL_METER_ENDPOINT
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
        return params

