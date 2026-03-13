"""
RENERYO Connection Test — Platform connectivity diagnostics.

Provides the ``ReneryoConnectionTestMixin`` that ``ReneryoAdapter``
inherits to gain a ``test_connection()`` override with detailed
error classification, latency measurement, and meter discovery.

Extracted from ``_adapter.py`` to keep file sizes under 300 lines.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional in minimal OVOS images
    aiohttp = None  # type: ignore[assignment]

from skill.domain.results import ConnectionTestResult


class ReneryoConnectionTestMixin:
    """
    Mixin providing ``test_connection()`` for the RENERYO adapter.

    Expects the host class to expose:
        - ``_api_url: str``
        - ``_timeout: int``
        - ``_build_auth_headers() -> dict``
        - ``platform_name: str``
    """

    # --- public entry point -------------------------------------------------

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

    # --- session / request --------------------------------------------------

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
        url = f"{self._api_url}/api/u/measurement/meter/item"
        async with session.get(url, params=self._build_test_query_params()) as response:
            elapsed = (time.monotonic() - start) * 1000
            return await self._parse_test_response(response, elapsed)

    @staticmethod
    def _build_test_query_params() -> dict[str, str]:
        """Build required datetime window params for meter endpoint."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=365)
        return {
            "datetimeMin": start.isoformat().replace("+00:00", "Z"),
            "datetimeMax": end.isoformat().replace("+00:00", "Z"),
        }

    # --- response parsing ---------------------------------------------------

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

    # --- error builders -----------------------------------------------------

    def _build_connection_error(
        self,
        start: float,
        exc: aiohttp.ClientConnectorError,
    ) -> ConnectionTestResult:
        """Build result for connection-refused / DNS errors."""
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
        elapsed = (time.monotonic() - start) * 1000
        return ConnectionTestResult(
            success=False,
            latency_ms=round(elapsed, 1),
            message=f"Unexpected error: {type(exc).__name__}",
            adapter_name=self.platform_name,
            error_code="UNKNOWN",
            error_details=str(exc),
        )
