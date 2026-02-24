"""Metric mapping and JSON extraction helpers for GenericRestAdapter."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, DataPoint, TimePeriod
from skill.domain.results import KPIResult

MetricMapping = dict[str, Any]


_HIGHER_IS_BETTER: set[CanonicalMetric] = {
    CanonicalMetric.OEE,
    CanonicalMetric.MATERIAL_EFFICIENCY,
    CanonicalMetric.THROUGHPUT,
    CanonicalMetric.SUPPLIER_ON_TIME,
    CanonicalMetric.RECYCLED_CONTENT,
}


def resolve_request(
    mapping: MetricMapping,
    period: TimePeriod,
    asset_id: str,
    extra_settings: dict[str, str],
    *,
    endpoint_key: str = "endpoint",
) -> tuple[str, dict[str, str]]:
    """Build endpoint and query params from mapping + runtime context."""
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


def get_mapping_json_path(
    mapping: MetricMapping,
    *,
    key: str = "json_path",
) -> str:
    """Return and validate a JSONPath key in mapping."""
    json_path = str(mapping.get(key, "") or "").strip()
    if not json_path:
        raise AdapterError(
            message=f"Metric mapping {key} is empty",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )
    return json_path


def get_mapping_unit(mapping: MetricMapping, metric: CanonicalMetric) -> str:
    """Return configured mapping unit or canonical default unit."""
    unit = str(mapping.get("unit", "") or "").strip()
    return unit or metric.default_unit


def extract_mapped_value(data: dict | list, json_path: str, mapping: MetricMapping) -> float:
    """Extract KPI numeric value using mapping json_path + optional transform."""
    value = _resolve_json_path(data, json_path)
    if value is None:
        raise AdapterError(
            message=f"No data at {json_path} for selected period",
            code="GENERIC_REST_NO_DATA",
            platform="generic_rest",
            user_message=(
                "I couldn't find data for that period. "
                "Please try a wider period like last month."
            ),
        )

    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterError(
            message=f"Mapped value at {json_path} is not numeric: {value}",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        ) from exc

    return _apply_transform(numeric, mapping.get("transform"))


def parse_mapped_kpi_response(
    data: dict | list,
    mapping: MetricMapping,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> KPIResult:
    """Parse mapped KPI payload into KPIResult."""
    json_path = get_mapping_json_path(mapping)
    value = extract_mapped_value(data, json_path, mapping)
    return KPIResult(
        metric=metric,
        value=value,
        unit=get_mapping_unit(mapping, metric),
        asset_id=asset_id,
        period=period,
        timestamp=datetime.now(tz=timezone.utc),
    )


def extract_trend_points(
    payload: dict | list,
    mapping: MetricMapping,
    metric: CanonicalMetric,
    period: TimePeriod,
) -> list[DataPoint]:
    """Extract trend points from generic payload formats."""
    items = _resolve_trend_items(payload, mapping)
    unit = get_mapping_unit(mapping, metric)

    points: list[DataPoint] = []
    total = len(items)
    for idx, item in enumerate(items):
        value, timestamp, point_unit = _parse_trend_item(
            item=item,
            fallback_unit=unit,
            period=period,
            index=idx,
            total=total,
        )
        points.append(DataPoint(timestamp=timestamp, value=value, unit=point_unit))

    return points


def rank_descending(metric: CanonicalMetric) -> bool:
    """Return True when higher metric values should rank first."""
    return metric in _HIGHER_IS_BETTER


def compute_trend_change(
    points: list[DataPoint],
) -> tuple[str, float]:
    """Compute trend direction and percent change from trend points."""
    if len(points) < 2:
        return "stable", 0.0

    first = points[0].value
    last = points[-1].value
    if first == 0:
        return "stable", 0.0

    change_pct = round(((last - first) / abs(first)) * 100, 2)
    if change_pct > 1.0:
        return "up", change_pct
    if change_pct < -1.0:
        return "down", change_pct
    return "stable", change_pct


def _resolve_trend_items(payload: dict | list, mapping: MetricMapping) -> list[Any]:
    """Find an iterable trend series in payload."""
    trend_json_path = str(mapping.get("trend_json_path", "") or "").strip()
    if trend_json_path:
        resolved = _resolve_json_path(payload, trend_json_path)
        if not isinstance(resolved, list):
            raise AdapterError(
                message=(
                    "trend_json_path must resolve to a list of points; "
                    f"got {type(resolved).__name__}"
                ),
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )
        return resolved

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("records", "values", "data", "items", "series"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return candidate

        json_path = str(mapping.get("json_path", "") or "").strip()
        if json_path:
            candidate = _resolve_json_path(payload, json_path)
            if isinstance(candidate, list):
                return candidate

    raise AdapterError(
        message=(
            "Could not infer trend data list from response. "
            "Set trend_json_path in metric mapping."
        ),
        code="GENERIC_REST_MAPPING_INVALID",
        platform="generic_rest",
    )


def _parse_trend_item(
    *,
    item: Any,
    fallback_unit: str,
    period: TimePeriod,
    index: int,
    total: int,
) -> tuple[float, datetime, str]:
    """Parse one trend item into value/timestamp/unit."""
    if isinstance(item, (int, float)):
        return float(item), _interpolate_timestamp(period, index, total), fallback_unit

    if not isinstance(item, dict):
        raise AdapterError(
            message=f"Invalid trend point type: {type(item).__name__}",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )

    raw_value = _first_present(item, ("value", "consumption", "amount", "y"))
    if raw_value is None:
        raise AdapterError(
            message="Trend point does not include a numeric value",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise AdapterError(
            message=f"Trend point value is not numeric: {raw_value}",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        ) from exc

    raw_ts = _first_present(item, ("timestamp", "datetime", "date", "time", "x"))
    timestamp = _parse_timestamp(raw_ts)
    if timestamp is None:
        timestamp = _interpolate_timestamp(period, index, total)

    unit = str(item.get("unit", "") or "").strip() or fallback_unit
    return value, timestamp, unit


def _parse_timestamp(raw: Any) -> datetime | None:
    """Parse timestamp-like value into aware datetime if possible."""
    if raw is None:
        return None

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw

    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (ValueError, OSError):
            return None

    raw_str = str(raw).strip()
    if not raw_str:
        return None

    normalized = raw_str.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _interpolate_timestamp(period: TimePeriod, index: int, total: int) -> datetime:
    """Derive a timestamp if source point does not include one."""
    if total <= 1:
        return period.start.replace(tzinfo=timezone.utc) if period.start.tzinfo is None else period.start

    delta = period.end - period.start
    step_ratio = index / (total - 1)
    ts = period.start + (delta * step_ratio)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _fill_placeholders(endpoint: str, replacements: dict[str, str]) -> str:
    """Replace {PLACEHOLDER} tokens from runtime values."""

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
    """Build normalized placeholder replacement table."""
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
    """Add standard period placeholders from TimePeriod."""
    start_iso = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")
    replacements["start_date"] = start_iso
    replacements["start_datetime"] = start_iso
    replacements["datetimemin"] = start_iso
    replacements["end_date"] = end_iso
    replacements["end_datetime"] = end_iso
    replacements["datetimemax"] = end_iso
    replacements["period"] = f"{start_iso}_{end_iso}"


def _resolve_json_path(payload: dict | list, json_path: str) -> Any:
    """Resolve a small JSONPath subset: $.a.b[0].c"""
    path = json_path.strip()
    if not path.startswith("$."):
        raise AdapterError(
            message=f"Unsupported json_path format: {json_path}",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
        )

    tokens = re.findall(r"([^\.\[\]]+)|\[(\d+)\]", path[2:])
    current: Any = payload
    for key_token, index_token in tokens:
        if key_token:
            if not isinstance(current, dict) or key_token not in current:
                raise AdapterError(
                    message=f"json_path not found: {json_path}",
                    code="GENERIC_REST_MAPPING_INVALID",
                    platform="generic_rest",
                )
            current = current[key_token]
            continue

        if not isinstance(current, list):
            raise AdapterError(
                message=f"json_path expects list before index in {json_path}",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )

        index = int(index_token)
        if index >= len(current):
            raise AdapterError(
                message=f"json_path index out of range in {json_path}",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )
        current = current[index]

    return current


def _normalize_endpoint_path(parsed, filled: str) -> str:
    """Normalize endpoint path from relative/absolute URL input."""
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"
    endpoint = parsed.path or filled
    endpoint = endpoint.strip()
    if not endpoint:
        return "/"
    return endpoint


def _apply_transform(value: float, transform: Any) -> float:
    """Apply optional mapping transform to extracted numeric value."""
    if transform is None:
        return value

    transform_str = str(transform).strip().lower()
    if not transform_str:
        return value

    if transform_str == "percent_to_ratio":
        return value / 100.0
    if transform_str == "ratio_to_percent":
        return value * 100.0

    simple = re.match(r"^x\s*([\+\-\*/])\s*(-?\d+(?:\.\d+)?)$", transform_str)
    if simple:
        op, raw_operand = simple.groups()
        operand = float(raw_operand)
        if op == "+":
            return value + operand
        if op == "-":
            return value - operand
        if op == "*":
            return value * operand
        if op == "/":
            if operand == 0:
                raise AdapterError(
                    message="Metric mapping transform divides by zero",
                    code="GENERIC_REST_MAPPING_INVALID",
                    platform="generic_rest",
                )
            return value / operand

    raise AdapterError(
        message=(
            f"Unsupported mapping transform '{transform}'. "
            "Use one of: percent_to_ratio, ratio_to_percent, x+N, x-N, x*N, x/N"
        ),
        code="GENERIC_REST_MAPPING_INVALID",
        platform="generic_rest",
    )


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return first non-None value from dict keys."""
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None
