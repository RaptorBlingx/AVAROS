"""
RENERYO HTTP Transport Mixin.

Provides low-level HTTP operations for the ReneryoAdapter:
fetch, retry with exponential backoff, response handling,
authentication headers, and session guard.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from skill.domain.exceptions import AdapterError

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BACKOFF_FACTORS = (0.5, 1.0, 2.0)


class ReneryoHttpMixin:
    """
    HTTP transport mixin for ReneryoAdapter.

    Provides ``_fetch``, ``_retry_fetch``, ``_handle_response``,
    ``_parse_json``, ``_build_auth_headers``, and ``_ensure_initialized``.

    Requires the consuming class to define:
        ``_session``, ``_api_url``, ``_timeout``, ``_auth_type``, ``_api_key``.
    """

    _session: aiohttp.ClientSession | None
    _api_url: str
    _timeout: int
    _auth_type: str
    _api_key: str

    async def _fetch(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict | list:
        """
        Execute GET request against RENERYO API.

        Args:
            endpoint: REST path (from endpoint map).
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            AdapterError: On connection, auth, timeout, or parse errors.
        """
        self._ensure_initialized()
        await self._refresh_session_if_needed()
        assert self._session is not None
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

    async def _refresh_session_if_needed(self) -> None:
        """Recreate session when bound loop is closed or mismatched."""
        if self._session is None:
            return

        current_loop = asyncio.get_running_loop()
        session_loop = getattr(self._session, "_loop", None)
        loop_mismatch = session_loop is not None and session_loop is not current_loop
        loop_closed = bool(session_loop and getattr(session_loop, "is_closed", lambda: False)())
        if not (self._session.closed or loop_mismatch or loop_closed):
            return

        try:
            if not self._session.closed and not loop_closed:
                await self._session.close()
        except Exception:
            logger.debug("Ignoring close failure for stale RENERYO session", exc_info=True)

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        headers = self._build_auth_headers()
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)

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
        max_retries: int = MAX_RETRIES,
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
                    delay = BACKOFF_FACTORS[attempt]
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
