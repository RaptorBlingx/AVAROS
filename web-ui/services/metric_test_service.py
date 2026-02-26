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
MAX_RESPONSE_BYTES = 1_048_576
_JSON_PATH_TOKEN_PATTERN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


class _JsonPathResolutionError(ValueError):
    """Raised when configured JSON path cannot be resolved on payload."""


class _ResponseTooLargeError(ValueError):
    """Raised when upstream response body exceeds allowed size."""


async def run_metric_mapping_test(
    payload: MetricMappingTestRequest,
) -> MetricMappingTestResponse:
    """Execute one outbound request and validate configured mapping extraction."""
    target_url = _resolve_target_url(payload)
    if isinstance(target_url, MetricMappingTestResponse):
        return target_url
    headers = _build_auth_headers(payload.auth_type, payload.auth_token)
    fetch_result = await _try_fetch(target_url, headers)
    if isinstance(fetch_result, MetricMappingTestResponse):
        return fetch_result
    status_code, raw_text = fetch_result
    return _try_parse_and_extract(status_code, raw_text, payload.json_path)


async def _fetch_response(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, str]:
    """Fetch URL text response with bounded timeout."""
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            body = await _read_limited_body(response)
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

    parsed_endpoint = urlsplit(normalized_endpoint)
    if parsed_endpoint.scheme or parsed_endpoint.netloc or normalized_endpoint.startswith("//"):
        raise ValueError("endpoint must be a relative path")

    if normalized_base.endswith("/") and normalized_endpoint.startswith("/"):
        return f"{normalized_base[:-1]}{normalized_endpoint}"
    if not normalized_base.endswith("/") and not normalized_endpoint.startswith("/"):
        return f"{normalized_base}/{normalized_endpoint}"
    return f"{normalized_base}{normalized_endpoint}"


def _build_auth_headers(auth_type: str, token: str) -> dict[str, str]:
    """Build outbound auth headers for mapping test request."""
    if auth_type == "cookie":
        # RENERYO session cookies are accepted as S=<token> in current deployment.
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


def _response_error(error: str, preview: str = "") -> MetricMappingTestResponse:
    """Build standardized failure response payload."""
    return MetricMappingTestResponse(
        success=False,
        value=None,
        raw_response_preview=preview,
        error=error,
    )


def _resolve_target_url(
    payload: MetricMappingTestRequest,
) -> str | MetricMappingTestResponse:
    """Resolve and validate target URL from request payload."""
    try:
        return _build_request_url(payload.base_url, payload.endpoint)
    except ValueError as exc:
        return _response_error(f"Connection failed: {exc}")


async def _try_fetch(
    target_url: str,
    headers: dict[str, str],
) -> tuple[int, str] | MetricMappingTestResponse:
    """Fetch remote response and normalize network failures."""
    try:
        return await _fetch_response(target_url, headers, REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return _response_error("Connection failed: request timed out")
    except (aiohttp.ClientError, ValueError) as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        return _response_error(f"Connection failed: {detail}")


def _try_parse_and_extract(
    status_code: int,
    raw_text: str,
    json_path: str,
) -> MetricMappingTestResponse:
    """Validate upstream payload and extract numeric metric value."""
    preview = _truncate_preview(raw_text)
    if status_code >= 400:
        return _response_error(
            f"Connection failed: upstream returned HTTP {status_code}",
            preview,
        )
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return _response_error("Response is not valid JSON", preview)
    try:
        extracted = _resolve_json_path(parsed, json_path)
    except _JsonPathResolutionError:
        return _response_error("JSONPath did not resolve to a value", preview)
    try:
        numeric_value = _to_float(extracted)
    except ValueError:
        return _response_error(f"Extracted value is not numeric: {extracted}", preview)
    return MetricMappingTestResponse(
        success=True,
        value=numeric_value,
        raw_response_preview=preview,
        error=None,
    )


async def _read_limited_body(response: aiohttp.ClientResponse) -> str:
    """Read and decode response body with hard byte-size guard."""
    _ensure_content_length_within_limit(response.content_length)
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        total_bytes += len(chunk)
        if total_bytes > MAX_RESPONSE_BYTES:
            raise _ResponseTooLargeError(
                f"response body exceeds {MAX_RESPONSE_BYTES} bytes",
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    return raw.decode(response.charset or "utf-8", errors="replace")


def _ensure_content_length_within_limit(content_length: int | None) -> None:
    """Reject oversized responses before reading body bytes."""
    if content_length is None:
        return
    if content_length > MAX_RESPONSE_BYTES:
        raise _ResponseTooLargeError(
            f"response body exceeds {MAX_RESPONSE_BYTES} bytes",
        )
