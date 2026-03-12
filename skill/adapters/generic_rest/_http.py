"""HTTP transport mixin for GenericRestAdapter."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import unquote

import aiohttp

from skill.domain.exceptions import AdapterError

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTORS = (0.5, 1.0, 2.0)


class GenericRestHttpMixin:
    """Low-level HTTP operations for GenericRestAdapter."""

    _session: aiohttp.ClientSession | None
    _api_url: str
    _timeout: int
    _auth_type: str
    _api_key: str
    _max_retries: int
    _backoff_factors: tuple[float, ...]

    async def _fetch(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict | list:
        """Execute GET request and parse JSON response."""
        self._ensure_initialized()
        await self._refresh_session_if_needed()
        assert self._session is not None

        url = self._build_request_url(endpoint)

        try:
            async with self._session.get(url, params=params) as response:
                return await self._handle_response(response, endpoint)
        except AdapterError:
            raise
        except aiohttp.ClientConnectorError as exc:
            raise AdapterError(
                message=f"Connection failed: {exc}",
                code="GENERIC_REST_CONNECTION_FAILED",
                platform="generic_rest",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise AdapterError(
                message=f"Request timed out after {self._timeout}s: {endpoint}",
                code="GENERIC_REST_TIMEOUT",
                platform="generic_rest",
            ) from exc

    async def _retry_fetch(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
        max_retries: int | None = None,
    ) -> dict | list:
        """Fetch with retry on 5xx errors."""
        retries = self._max_retries if max_retries is None else max_retries
        last_error: AdapterError | None = None

        for attempt in range(retries + 1):
            try:
                return await self._fetch(endpoint, params)
            except AdapterError as exc:
                if exc.code != "GENERIC_REST_SERVER_ERROR":
                    raise
                last_error = exc
                if attempt < retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retry %d/%d for %s after %.2fs (status=%s)",
                        attempt + 1,
                        retries,
                        endpoint,
                        delay,
                        exc.status_code,
                    )
                    await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    async def _probe_base_url(self) -> None:
        """Verify base API URL is reachable with a lightweight request."""
        self._ensure_initialized()
        assert self._session is not None

        try:
            async with self._session.head(self._api_url) as response:
                if response.status < 500:
                    return
                raise AdapterError(
                    message=(
                        f"Base URL probe failed with status {response.status}: "
                        f"{self._api_url}"
                    ),
                    code="GENERIC_REST_INIT_FAILED",
                    platform="generic_rest",
                    status_code=response.status,
                )
        except AdapterError:
            raise
        except Exception:
            # Some APIs reject HEAD; GET is fallback.
            try:
                async with self._session.get(self._api_url) as response:
                    if response.status < 500:
                        return
                    raise AdapterError(
                        message=(
                            f"Base URL probe failed with status {response.status}: "
                            f"{self._api_url}"
                        ),
                        code="GENERIC_REST_INIT_FAILED",
                        platform="generic_rest",
                        status_code=response.status,
                    )
            except AdapterError:
                raise
            except aiohttp.ClientConnectorError as exc:
                raise AdapterError(
                    message=f"Could not reach API URL: {self._api_url}",
                    code="GENERIC_REST_INIT_FAILED",
                    platform="generic_rest",
                ) from exc
            except asyncio.TimeoutError as exc:
                raise AdapterError(
                    message=(
                        f"Timed out probing API URL after {self._timeout}s: "
                        f"{self._api_url}"
                    ),
                    code="GENERIC_REST_INIT_FAILED",
                    platform="generic_rest",
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
            logger.debug("Ignoring close failure for stale GenericRest session", exc_info=True)

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        headers = self._build_auth_headers()
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        endpoint: str,
    ) -> dict | list:
        """Handle status codes and parse JSON response body."""
        if 200 <= response.status < 300:
            return await self._parse_json(response, endpoint)

        if response.status == 401:
            raise AdapterError(
                message=f"Authentication failed for {endpoint}",
                code="GENERIC_REST_AUTH_FAILED",
                platform="generic_rest",
                status_code=401,
                user_message=(
                    "Authentication failed. Check API key/cookie settings and try again."
                ),
            )

        if response.status == 404:
            raise AdapterError(
                message=f"Endpoint not found: {endpoint}",
                code="GENERIC_REST_ENDPOINT_NOT_FOUND",
                platform="generic_rest",
                status_code=404,
                user_message=(
                    "The configured endpoint was not found. "
                    "Please check the metric mapping endpoint."
                ),
            )

        if response.status >= 500:
            raise AdapterError(
                message=f"Server error {response.status} on {endpoint}",
                code="GENERIC_REST_SERVER_ERROR",
                platform="generic_rest",
                status_code=response.status,
            )

        raise AdapterError(
            message=f"Unexpected status {response.status} on {endpoint}",
            code="GENERIC_REST_UNEXPECTED_STATUS",
            platform="generic_rest",
            status_code=response.status,
        )

    def _build_request_url(self, endpoint: str) -> str:
        """Build absolute request URL from base URL + endpoint."""
        endpoint = (endpoint or "").strip()
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint

        if endpoint.startswith("/"):
            return f"{self._api_url}{endpoint}"
        return f"{self._api_url}/{endpoint}"

    def _build_auth_headers(self) -> dict[str, str]:
        """Build auth headers for bearer or cookie auth."""
        if self._auth_type == "none":
            return {}
        if self._auth_type == "cookie":
            raw_cookie = (self._api_key or "").strip()
            if raw_cookie.lower().startswith("cookie:"):
                return {"Cookie": raw_cookie.split(":", 1)[1].strip()}

            decoded_cookie = unquote(raw_cookie)
            if decoded_cookie.startswith("S=") or ";" in decoded_cookie:
                return {"Cookie": decoded_cookie}
            return {"Cookie": f"S={decoded_cookie}"}

        return {"Authorization": f"Bearer {self._api_key}"}

    def _ensure_initialized(self) -> None:
        """Raise when adapter session has not been initialized."""
        if self._session is None:
            raise AdapterError(
                message="GenericRestAdapter not initialized — call initialize() first",
                code="GENERIC_REST_NOT_CONNECTED",
                platform="generic_rest",
            )

    def _backoff_delay(self, attempt: int) -> float:
        """Resolve retry delay for an attempt index."""
        if self._backoff_factors:
            index = min(attempt, len(self._backoff_factors) - 1)
            return float(self._backoff_factors[index])
        return float(2**attempt)

    @staticmethod
    async def _parse_json(
        response: aiohttp.ClientResponse,
        endpoint: str,
    ) -> dict | list:
        """Parse JSON body from HTTP response."""
        try:
            return await response.json()
        except Exception as exc:
            raise AdapterError(
                message=f"Invalid JSON from {endpoint}: {exc}",
                code="GENERIC_REST_INVALID_RESPONSE",
                platform="generic_rest",
            ) from exc
