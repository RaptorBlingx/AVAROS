"""Request-building helpers for Generic REST metric mappings."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from skill.domain.exceptions import AdapterError
from skill.domain.models import TimePeriod

MetricMapping = dict[str, Any]


def resolve_request(
    mapping: MetricMapping,
    period: TimePeriod,
    asset_id: str,
    extra_settings: dict[str, str],
    *,
    endpoint_key: str = "endpoint",
) -> tuple[str, dict[str, str]]:
    """Build endpoint path and query params from mapping placeholders.

    Args:
        mapping: Metric mapping configuration dict.
        period: Requested time window.
        asset_id: Target asset/site identifier.
        extra_settings: Profile-level scalar settings for placeholders.
        endpoint_key: Mapping key containing endpoint template.

    Returns:
        Tuple of ``(endpoint_path, query_params)`` after placeholder expansion.

    Raises:
        AdapterError: If endpoint is missing or placeholders are unresolved.
    """
    endpoint = str(mapping.get(endpoint_key, "") or "").strip()
    if not endpoint:
        raise AdapterError(
            message=f"Metric mapping {endpoint_key} is empty",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )

    replacements = _build_replacements(asset_id, extra_settings)
    _add_period_replacements(replacements, period)
    filled = _fill_placeholders(endpoint, replacements)

    parsed = urlsplit(filled)
    params = dict(parse_qsl(parsed.query, keep_blank_values=False))

    endpoint_path = _normalize_endpoint_path(parsed, filled)
    return endpoint_path, params


def _fill_placeholders(endpoint: str, replacements: dict[str, str]) -> str:
    """Replace ``{placeholder}`` tokens with runtime values."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        normalized = key.lower()
        if normalized in replacements:
            return replacements[normalized]
        raise AdapterError(
            message=(
                f"Metric mapping placeholder {{{key}}} is unresolved. "
                "Set it in profile extra settings."
            ),
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )

    return re.sub(r"\{([^{}]+)\}", _replace, endpoint)


def _build_replacements(
    asset_id: str,
    extra_settings: dict[str, str],
) -> dict[str, str]:
    """Build normalized replacement table used in endpoint templates."""
    replacements: dict[str, str] = {
        "asset_id": asset_id,
        "assetid": asset_id,
    }
    for key, value in extra_settings.items():
        if value is None:
            continue
        replacements[str(key).strip().lower()] = str(value).strip()
    return replacements


def _add_period_replacements(
    replacements: dict[str, str],
    period: TimePeriod,
) -> None:
    """Add standard period placeholders from ``TimePeriod``."""
    start_iso = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")
    replacements["start_date"] = start_iso
    replacements["start_datetime"] = start_iso
    replacements["datetimemin"] = start_iso
    replacements["end_date"] = end_iso
    replacements["end_datetime"] = end_iso
    replacements["datetimemax"] = end_iso
    replacements["period"] = f"{start_iso}_{end_iso}"

    # APIs commonly express time windows as Unix epoch values rather than
    # ISO-8601 strings.  Keep both forms available in every generic mapping
    # rather than coupling the adapter to one platform's query convention.
    start_epoch_seconds = _to_utc_epoch_seconds(period.start)
    end_epoch_seconds = _to_utc_epoch_seconds(period.end)
    replacements["start_epoch_seconds"] = str(start_epoch_seconds)
    replacements["end_epoch_seconds"] = str(end_epoch_seconds)
    replacements["start_epoch_ms"] = str(start_epoch_seconds * 1000)
    replacements["end_epoch_ms"] = str(end_epoch_seconds * 1000)


def _to_utc_epoch_seconds(value: datetime) -> int:
    """Return a Unix epoch value, treating naive datetimes as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _normalize_endpoint_path(parsed, filled: str) -> str:
    """Normalize endpoint path from relative/absolute URL input."""
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"
    endpoint = parsed.path or filled
    endpoint = endpoint.strip()
    if not endpoint:
        return "/"
    return endpoint
