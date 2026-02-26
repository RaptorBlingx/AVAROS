"""Trend extraction helpers for Generic REST metric mappings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from skill.adapters.generic_rest._value_extraction import (
    MetricMapping,
    first_present,
    get_mapping_unit,
    resolve_json_path,
)
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, DataPoint, TimePeriod


def extract_trend_points(
    payload: dict | list,
    mapping: MetricMapping,
    metric: CanonicalMetric,
    period: TimePeriod,
) -> list[DataPoint]:
    """Extract trend data points from response payload.

    Args:
        payload: Upstream JSON payload.
        mapping: Metric mapping dict.
        metric: Target canonical metric.
        period: Requested trend period.

    Returns:
        Ordered list of ``DataPoint`` values.

    Raises:
        AdapterError: If trend structure cannot be inferred or parsed.
    """
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


def compute_trend_change(
    points: list[DataPoint],
) -> tuple[str, float]:
    """Compute trend direction and percent change.

    Args:
        points: Trend points sorted by time.

    Returns:
        Tuple ``(direction, change_percent)``.

    Raises:
        None.
    """
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
        resolved = resolve_json_path(payload, trend_json_path)
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
            candidate = resolve_json_path(payload, json_path)
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

    raw_value = first_present(item, ("value", "consumption", "amount", "y"))
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

    raw_ts = first_present(item, ("timestamp", "datetime", "date", "time", "x"))
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
