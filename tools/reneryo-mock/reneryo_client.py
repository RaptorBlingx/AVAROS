"""
Async HTTP client for Reneryo's metric resource write API.

Provides methods to create metrics, write time-series values, list
metrics/resources, and read values back. Auth is via session cookie
(RENERYO_SESSION_COOKIE env var).

This is a standalone tool — it does NOT import from skill/.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0


# =========================================================================
# Exceptions
# =========================================================================


class ReneryoClientError(Exception):
    """Base error for Reneryo API client."""


class ReneryoAuthError(ReneryoClientError):
    """Authentication failure (401/403)."""


class ReneryoApiError(ReneryoClientError):
    """Non-retryable API error (4xx)."""


class ReneryoServerError(ReneryoClientError):
    """Server error after all retries exhausted (5xx)."""


# =========================================================================
# Client
# =========================================================================


class ReneryoClient:
    """Async client for Reneryo metric resource API.

    Args:
        base_url: Reneryo API base URL.
        session_cookie: Session cookie value (S=...).
    """

    def __init__(
        self,
        base_url: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self._base_url = (
            base_url
            or os.environ.get(
                "RENERYO_API_URL", "http://deploys.int.arti.ac:31290/api"
            )
        ).rstrip("/")
        cookie_val = session_cookie or os.environ.get(
            "RENERYO_SESSION_COOKIE", ""
        )
        if not cookie_val:
            raise ReneryoAuthError("RENERYO_SESSION_COOKIE is required")
        self._cookie_header = (
            cookie_val if cookie_val.startswith("S=") else f"S={cookie_val}"
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ReneryoClient:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Cookie": self._cookie_header},
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -----------------------------------------------------------------
    # Low-level request helpers
    # -----------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_on_server_error: bool = True,
    ) -> dict[str, Any] | list[Any]:
        """HTTP request with optional retry on 5xx.

        Args:
            method: HTTP method.
            path: API path relative to base_url.
            json_data: JSON body for POST.
            params: Query parameters.
            retry_on_server_error: Whether to retry on 5xx.

        Returns:
            Parsed JSON response.

        Raises:
            ReneryoAuthError: On 401/403.
            ReneryoApiError: On other 4xx.
            ReneryoServerError: On 5xx after retries.
        """
        if not self._client:
            raise ReneryoClientError(
                "Client not initialized — use 'async with'"
            )

        max_attempts = MAX_RETRIES if retry_on_server_error else 1
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                resp = await self._client.request(
                    method, path, json=json_data, params=params
                )
            except httpx.HTTPError as exc:
                last_error = ReneryoServerError(str(exc))
                if attempt < max_attempts - 1:
                    wait = INITIAL_BACKOFF_S * (2**attempt)
                    logger.warning(
                        "HTTP error, retry %d/%d in %.1fs: %s",
                        attempt + 1, max_attempts, wait, exc,
                    )
                    await asyncio.sleep(wait)
                continue

            if resp.status_code in (401, 403):
                raise ReneryoAuthError(
                    f"{resp.status_code} auth error on {method} {path}"
                )
            if resp.status_code == 400:
                raise ReneryoApiError(
                    f"400 Bad Request on {method} {path}: "
                    f"{resp.text[:500]}"
                )
            if 400 < resp.status_code < 500:
                raise ReneryoApiError(
                    f"{resp.status_code} on {method} {path}: "
                    f"{resp.text[:500]}"
                )
            if resp.status_code >= 500:
                last_error = ReneryoServerError(
                    f"{resp.status_code} on {method} {path}: "
                    f"{resp.text[:200]}"
                )
                if attempt < max_attempts - 1:
                    wait = INITIAL_BACKOFF_S * (2**attempt)
                    logger.warning(
                        "Server error, retry %d/%d in %.1fs: %s",
                        attempt + 1, max_attempts, wait, last_error,
                    )
                    await asyncio.sleep(wait)
                continue

            return resp.json()  # type: ignore[no-any-return]

        raise last_error or ReneryoServerError("Request failed")

    # -----------------------------------------------------------------
    # Metric CRUD
    # -----------------------------------------------------------------

    async def create_metric(
        self,
        name: str,
        metric_type: str = "GAUGE",
        unit_group: str = "SCALAR",
        description: str = "",
    ) -> str:
        """Create a metric in Reneryo.

        Args:
            name: Display name (e.g., "AVAROS Scrap Rate").
            metric_type: GAUGE or COUNTER.
            unit_group: SCALAR, ENERGY, etc.
            description: Optional description.

        Returns:
            Metric ID (UUID string).
        """
        payload: dict[str, str] = {
            "name": name,
            "type": metric_type,
            "unitGroup": unit_group,
        }
        if description:
            payload["description"] = description
        result = await self._request(
            "POST", "/u/measurement/metric/item", json_data=payload
        )
        metric_id: str = result.get("id", "") if isinstance(result, dict) else ""
        logger.info("Created metric '%s' → %s", name, metric_id)
        return metric_id

    async def write_values(
        self,
        metric_id: str,
        unit: str,
        values: list[dict[str, Any]],
        labels: list[dict[str, str]],
    ) -> str:
        """Write time-series values with automatic batch splitting.

        If the API returns 500 (e.g. duplicate timestamps in batch),
        the batch is split in half and each half is retried recursively.

        Args:
            metric_id: The metric UUID.
            unit: Unit string (e.g., "SCALAR").
            values: List of {"value": float, "datetime": str} dicts.
            labels: List of {"key": str, "value": str} label dicts.

        Returns:
            Resource ID (UUID string).
        """
        try:
            return await self._write_single(metric_id, unit, values, labels)
        except ReneryoServerError:
            if len(values) <= 1:
                raise
            mid = len(values) // 2
            logger.warning(
                "Batch write failed for metric %s (%d values), "
                "splitting into %d + %d",
                metric_id, len(values), mid, len(values) - mid,
            )
            await self.write_values(metric_id, unit, values[:mid], labels)
            return await self.write_values(
                metric_id, unit, values[mid:], labels
            )

    async def _write_single(
        self,
        metric_id: str,
        unit: str,
        values: list[dict[str, Any]],
        labels: list[dict[str, str]],
    ) -> str:
        """Write a single batch — no retry on 500 (caller handles split).

        Args:
            metric_id: The metric UUID.
            unit: Unit string.
            values: Value/datetime dicts.
            labels: Label key/value dicts.

        Returns:
            Resource ID.
        """
        payload = {"unit": unit, "values": values, "labels": labels}
        result = await self._request(
            "POST",
            f"/u/measurement/metric/item/{metric_id}/values",
            json_data=payload,
            retry_on_server_error=False,
        )
        return result.get("resourceId", "") if isinstance(result, dict) else ""

    # -----------------------------------------------------------------
    # Listing / reading
    # -----------------------------------------------------------------

    async def list_metrics(self, count: int = 100) -> list[dict[str, Any]]:
        """List metrics in Reneryo.

        Args:
            count: Max number of metrics to return.

        Returns:
            List of metric dicts (id, name, type, unitGroup).
        """
        result = await self._request(
            "GET", "/u/measurement/metric/item", params={"count": count}
        )
        if isinstance(result, list):
            return result
        return result.get("records", [])

    async def list_resources(
        self, metric_id: str
    ) -> list[dict[str, Any]]:
        """List resources under a metric.

        Args:
            metric_id: The metric UUID.

        Returns:
            List of resource dicts.
        """
        result = await self._request(
            "GET",
            "/u/measurement/metric/resources",
            params={"metricId": metric_id},
        )
        if isinstance(result, list):
            return result
        return result.get("records", [])

    async def read_values(
        self,
        resource_id: str,
        datetime_min: str | None = None,
        datetime_max: str | None = None,
        period: str = "RAW",
        count: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Read values from a metric resource.

        Args:
            resource_id: The resource UUID.
            datetime_min: ISO datetime lower bound.
            datetime_max: ISO datetime upper bound.
            period: Aggregation period (RAW, HOURLY, etc.).
            count: Max records per page (max 100).
            page: Page number (1-based).

        Returns:
            Dict with recordCount and records list.
        """
        params: dict[str, Any] = {
            "period": period,
            "count": min(count, 100),
            "page": page,
        }
        if datetime_min:
            params["datetimeMin"] = datetime_min
        if datetime_max:
            params["datetimeMax"] = datetime_max
        result = await self._request(
            "GET",
            f"/u/measurement/metric/resource/{resource_id}/values",
            params=params,
        )
        if isinstance(result, dict):
            return result
        return {"recordCount": len(result), "records": result}
