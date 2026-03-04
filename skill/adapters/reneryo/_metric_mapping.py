"""Helpers for profile-scoped metric mappings in ReneryoAdapter."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult

MetricMapping = dict[str, Any]


def resolve_kpi_request(
    mapping: MetricMapping,
    period: TimePeriod,
    asset_id: str,
    extra_settings: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Build endpoint and params from a stored metric mapping."""
    endpoint = str(mapping.get("endpoint", "") or "").strip()
    if not endpoint:
        raise AdapterError(
            message="Metric mapping endpoint is empty",
            code="RENERYO_MAPPING_INVALID",
            platform="reneryo",
        )

    replacements = _build_replacements(asset_id, extra_settings)
    _add_period_replacements(replacements, period)
    filled = _fill_placeholders(endpoint, replacements)
    parsed = urlsplit(filled)
    query = dict(parse_qsl(parsed.query, keep_blank_values=False))
    if "datetimeMin" not in query:
        query["datetimeMin"] = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "datetimeMax" not in query:
        query["datetimeMax"] = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")

    endpoint_path = _normalize_endpoint_path(parsed.path or filled)
    return endpoint_path, query


def extract_mapped_value(data: dict | list, json_path: str) -> float:
    """Extract numeric KPI value from JSON payload using a basic JSONPath."""
    value = _resolve_json_path(data, json_path)
    if value is None:
        raise AdapterError(
            message=f"No data at {json_path} for selected period",
            code="RENERYO_NO_DATA",
            platform="reneryo",
            user_message=(
                "I couldn't find data for that period. "
                "Please try a wider period like last month."
            ),
        )
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterError(
            message=f"Mapped value at {json_path} is not numeric: {value}",
            code="RENERYO_MAPPING_INVALID",
            platform="reneryo",
        ) from exc


def get_mapping_unit(mapping: MetricMapping, metric: CanonicalMetric) -> str:
    """Return configured mapping unit or canonical default."""
    unit = str(mapping.get("unit", "") or "").strip()
    return unit or metric.default_unit


def get_mapping_json_path(mapping: MetricMapping) -> str:
    """Return configured json_path from mapping."""
    json_path = str(mapping.get("json_path", "") or "").strip()
    if not json_path:
        raise AdapterError(
            message="Metric mapping json_path is empty",
            code="RENERYO_MAPPING_INVALID",
            platform="reneryo",
        )
    return json_path


def parse_mapped_kpi_response(
    data: dict | list,
    mapping: MetricMapping,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> KPIResult:
    """Parse KPI response using configured json_path and unit."""
    json_path = get_mapping_json_path(mapping)
    value = extract_mapped_value(data, json_path)
    unit = get_mapping_unit(mapping, metric)
    return KPIResult(
        metric=metric,
        value=value,
        unit=unit,
        asset_id=asset_id,
        period=period,
        timestamp=datetime.now(tz=timezone.utc),
    )


def _fill_placeholders(endpoint: str, replacements: dict[str, str]) -> str:
    """Replace {PLACEHOLDER} tokens using known runtime values."""
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        lowered = key.lower()
        if lowered in replacements:
            return replacements[lowered]
        raise AdapterError(
            message=(
                f"Metric mapping placeholder {{{key}}} is unresolved. "
                "Set it in profile extra settings."
            ),
            code="RENERYO_MAPPING_INVALID",
            platform="reneryo",
        )

    return re.sub(r"\{([^{}]+)\}", _replace, endpoint)


def _build_replacements(
    asset_id: str,
    extra_settings: dict[str, str],
) -> dict[str, str]:
    """Create normalized placeholder replacement table."""
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
    replacements: dict[str, str], period: TimePeriod,
) -> None:
    """Add standard date placeholders derived from TimePeriod."""
    start_iso = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")
    replacements["start_date"] = start_iso
    replacements["start_datetime"] = start_iso
    replacements["datetimemin"] = start_iso
    replacements["end_date"] = end_iso
    replacements["end_datetime"] = end_iso
    replacements["datetimemax"] = end_iso


def _resolve_json_path(payload: dict | list, json_path: str) -> object:
    """Resolve a small JSONPath subset: $.a.b[0].c"""
    path = json_path.strip()
    if not path.startswith("$."):
        raise AdapterError(
            message=f"Unsupported json_path format: {json_path}",
            code="RENERYO_MAPPING_INVALID",
            platform="reneryo",
        )
    tokens = re.findall(r"([^.\[\]]+)|\[(\d+)\]", path[2:])
    current: object = payload
    for key_token, index_token in tokens:
        if key_token:
            if not isinstance(current, dict) or key_token not in current:
                raise AdapterError(
                    message=f"json_path not found: {json_path}",
                    code="RENERYO_MAPPING_INVALID",
                    platform="reneryo",
                )
            current = current[key_token]
            continue
        if not isinstance(current, list):
            raise AdapterError(
                message=f"json_path expects list before index in {json_path}",
                code="RENERYO_MAPPING_INVALID",
                platform="reneryo",
            )
        index = int(index_token)
        if index >= len(current):
            raise AdapterError(
                message=f"json_path index out of range in {json_path}",
                code="RENERYO_MAPPING_INVALID",
                platform="reneryo",
            )
        current = current[index]
    return current


def _normalize_endpoint_path(endpoint_path: str) -> str:
    """Normalize mapping endpoint path for RENERYO native routes."""
    normalized = endpoint_path.strip()
    if normalized.startswith("/u/"):
        return f"/api{normalized}"
    return normalized
