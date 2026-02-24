"""Service helpers for metric mapping validation endpoint."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from schemas.metrics import MetricMappingTestRequest, MetricMappingTestResponse

REQUEST_TIMEOUT_SECONDS = 10
RESPONSE_PREVIEW_LIMIT = 500
_JSON_PATH_TOKEN_PATTERN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


class _JsonPathResolutionError(ValueError):
    """Raised when configured JSON path cannot be resolved on payload."""


async def run_metric_mapping_test(
    payload: MetricMappingTestRequest,
) -> MetricMappingTestResponse:
    """Execute one outbound request and validate configured mapping extraction."""
    try:
        target_url = _build_request_url(payload.base_url, payload.endpoint)
    except ValueError as exc:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview="",
            error=f"Connection failed: {exc}",
        )

    headers = _build_auth_headers(payload.auth_type, payload.auth_token)

    try:
        status_code, raw_text = await _fetch_response(
            target_url,
            headers,
            REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview="",
            error="Connection failed: request timed out",
        )
    except aiohttp.ClientError as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview="",
            error=f"Connection failed: {detail}",
        )

    preview = _truncate_preview(raw_text)
    if status_code >= 400:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview=preview,
            error=f"Connection failed: upstream returned HTTP {status_code}",
        )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview=preview,
            error="Response is not valid JSON",
        )

    try:
        extracted = _resolve_json_path(parsed, payload.json_path)
    except _JsonPathResolutionError:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview=preview,
            error="JSONPath did not resolve to a value",
        )

    try:
        numeric_value = _to_float(extracted)
    except ValueError:
        return MetricMappingTestResponse(
            success=False,
            value=None,
            raw_response_preview=preview,
            error=f"Extracted value is not numeric: {extracted}",
        )

    return MetricMappingTestResponse(
        success=True,
        value=numeric_value,
        raw_response_preview=preview,
        error=None,
    )


async def _fetch_response(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, str]:
    """Fetch URL text response with bounded timeout."""
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            body = await response.text()
            return response.status, body


def _build_request_url(base_url: str, endpoint: str) -> str:
    """Build absolute request URL from base URL and endpoint path."""
    normalized_base = base_url.strip()
    normalized_endpoint = endpoint.strip()

    if not normalized_base:
        raise ValueError("base_url is required")
    if not normalized_endpoint:
        raise ValueError("endpoint is required")

    parsed_base = urlsplit(normalized_base)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise ValueError("base_url must be a valid http/https URL")

    if normalized_endpoint.startswith(("http://", "https://")):
        return normalized_endpoint

    if normalized_base.endswith("/") and normalized_endpoint.startswith("/"):
        return f"{normalized_base[:-1]}{normalized_endpoint}"
    if not normalized_base.endswith("/") and not normalized_endpoint.startswith("/"):
        return f"{normalized_base}/{normalized_endpoint}"
    return f"{normalized_base}{normalized_endpoint}"


def _build_auth_headers(auth_type: str, token: str) -> dict[str, str]:
    """Build outbound auth headers for mapping test request."""
    if auth_type == "cookie":
        return {"Cookie": f"S={token}"}
    return {"Authorization": f"Bearer {token}"}


def _resolve_json_path(payload: Any, json_path: str) -> Any:
    """Resolve a basic JSONPath subset: $.a.b[0].c."""
    path = json_path.strip()
    if path == "$":
        return payload
    if not path.startswith("$."):
        raise _JsonPathResolutionError(path)

    current: Any = payload
    for key_token, index_token in _JSON_PATH_TOKEN_PATTERN.findall(path[2:]):
        if key_token:
            if not isinstance(current, dict) or key_token not in current:
                raise _JsonPathResolutionError(path)
            current = current[key_token]
            continue

        if not isinstance(current, list):
            raise _JsonPathResolutionError(path)
        index = int(index_token)
        if index >= len(current):
            raise _JsonPathResolutionError(path)
        current = current[index]

    return current


def _to_float(value: Any) -> float:
    """Convert extracted JSONPath value to float if numeric."""
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    return float(value)


def _truncate_preview(raw_response: str) -> str:
    """Return response preview capped to endpoint contract length."""
    return raw_response[:RESPONSE_PREVIEW_LIMIT]
