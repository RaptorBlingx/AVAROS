"""
RENERYO Response Parsers — Transforms raw JSON into domain models.

Extracted from ReneryoAdapter to keep file sizes under 300 lines.
These parsers convert RENERYO API JSON responses into frozen domain
models (KPIResult, TrendResult, ComparisonResult, DataPoint).

Each parser raises AdapterError on missing or invalid fields.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, DataPoint, TimePeriod
from skill.domain.results import ComparisonItem, ComparisonResult, KPIResult, TrendResult

logger = logging.getLogger(__name__)


def parse_kpi_response(
    data: dict,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> KPIResult:
    """
    Parse single KPI JSON into KPIResult domain model.

    Args:
        data: Raw JSON dict from RENERYO API.
        metric: Canonical metric that was requested.
        asset_id: Asset ID from the request.
        period: Time period from the request.

    Returns:
        KPIResult with parsed value, unit, and metadata.

    Raises:
        AdapterError: On missing or invalid fields.
    """
    try:
        value = float(data["value"])
        unit = str(data.get("unit", metric.default_unit))
        timestamp_str = data.get("timestamp", "")
        timestamp = _parse_timestamp(timestamp_str)
    except (KeyError, TypeError, ValueError) as exc:
        raise AdapterError(
            message=f"Invalid KPI response for {metric.value}: {exc}",
            code="RENERYO_INVALID_RESPONSE",
            platform="reneryo",
        ) from exc

    return KPIResult(
        metric=metric,
        value=value,
        unit=unit,
        asset_id=asset_id,
        period=period,
        timestamp=timestamp,
    )


def parse_trend_response(
    data: list[dict],
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
    granularity: str,
) -> TrendResult:
    """
    Parse trend JSON array into TrendResult with DataPoints.

    Args:
        data: List of JSON dicts from RENERYO trend endpoint.
        metric: Canonical metric that was requested.
        asset_id: Asset ID from the request.
        period: Time period from the request.
        granularity: Data granularity (hourly, daily, weekly).

    Returns:
        TrendResult with data points, direction, and change %.

    Raises:
        AdapterError: On missing or invalid fields.
    """
    if not data:
        raise AdapterError(
            message=f"Empty trend response for {metric.value}",
            code="RENERYO_INVALID_RESPONSE",
            platform="reneryo",
        )

    data_points = _parse_data_points(data, metric)
    direction, change_pct = _compute_trend(data_points)

    return TrendResult(
        metric=metric,
        asset_id=asset_id,
        data_points=data_points,
        direction=direction,
        change_percent=change_pct,
        period=period,
        granularity=granularity,
    )


def parse_comparison_response(
    data: list[dict],
    metric: CanonicalMetric,
    period: TimePeriod,
) -> ComparisonResult:
    """
    Parse comparison JSON array into ComparisonResult.

    Args:
        data: List of per-asset JSON dicts.
        metric: Canonical metric that was compared.
        period: Time period from the request.

    Returns:
        ComparisonResult with ranked items and winner.

    Raises:
        AdapterError: On missing or invalid fields.
    """
    if not data:
        raise AdapterError(
            message=f"Empty comparison response for {metric.value}",
            code="RENERYO_INVALID_RESPONSE",
            platform="reneryo",
        )

    items = _build_comparison_items(data, metric)
    winner = min(items, key=lambda x: x.rank)
    difference = _compute_difference(items)
    unit = str(data[0].get("unit", metric.default_unit))

    return ComparisonResult(
        metric=metric,
        items=items,
        winner_id=winner.asset_id,
        difference=difference,
        unit=unit,
        period=period,
    )


def parse_raw_data_response(
    data: list[dict],
    metric: CanonicalMetric,
) -> list[DataPoint]:
    """
    Parse raw measurement array into DataPoint list.

    Args:
        data: List of measurement dicts from native endpoint.
        metric: Canonical metric for unit fallback.

    Returns:
        List of DataPoint domain objects.

    Raises:
        AdapterError: On missing or invalid fields.
    """
    if not data:
        return []
    return _parse_data_points(data, metric)


# =========================================================================
# Internal Helpers
# =========================================================================


def _parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO timestamp string, falling back to now() on empty input.

    Args:
        timestamp_str: ISO format timestamp string.

    Returns:
        Parsed datetime (UTC-aware).
    """
    if not timestamp_str:
        return datetime.now(tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc)


def _parse_data_points(
    data: list[dict],
    metric: CanonicalMetric,
) -> list[DataPoint]:
    """
    Parse list of JSON dicts into DataPoint domain objects.

    Args:
        data: List of measurement dicts with value/timestamp/unit.
        metric: Fallback metric for default unit.

    Returns:
        List of DataPoint objects.

    Raises:
        AdapterError: If value field is missing or not numeric.
    """
    points: list[DataPoint] = []
    for item in data:
        try:
            value = float(item["value"])
            unit = str(item.get("unit", metric.default_unit))
            ts_str = item.get("timestamp", item.get("datetime", ""))
            timestamp = _parse_timestamp(str(ts_str))
            points.append(DataPoint(
                timestamp=timestamp,
                value=value,
                unit=unit,
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                message=f"Invalid data point in {metric.value}: {exc}",
                code="RENERYO_INVALID_RESPONSE",
                platform="reneryo",
            ) from exc
    return points


def _compute_trend(
    data_points: list[DataPoint],
) -> tuple[str, float]:
    """
    Compute trend direction and change percent from data points.

    Args:
        data_points: Ordered list of DataPoint objects.

    Returns:
        Tuple of (direction, change_percent).
    """
    if len(data_points) < 2:
        return ("stable", 0.0)

    first = data_points[0].value
    last = data_points[-1].value
    if first == 0:
        return ("stable", 0.0)

    change_pct = round(((last - first) / abs(first)) * 100, 2)
    if change_pct > 1.0:
        return ("up", change_pct)
    if change_pct < -1.0:
        return ("down", change_pct)
    return ("stable", change_pct)


def _build_comparison_items(
    data: list[dict],
    metric: CanonicalMetric,
) -> list[ComparisonItem]:
    """
    Build ranked ComparisonItem list from raw JSON data.

    Lower-is-better metrics rank ascending; higher-is-better rank descending.

    Args:
        data: List of per-asset dicts with value/asset_id.
        metric: Canonical metric for ranking direction.

    Returns:
        Ranked list of ComparisonItem objects.

    Raises:
        AdapterError: On missing or invalid fields.
    """
    _HIGHER_IS_BETTER = {
        CanonicalMetric.OEE,
        CanonicalMetric.MATERIAL_EFFICIENCY,
        CanonicalMetric.THROUGHPUT,
        CanonicalMetric.SUPPLIER_ON_TIME,
        CanonicalMetric.RECYCLED_CONTENT,
    }

    parsed: list[tuple[str, float]] = []
    for item in data:
        try:
            asset_id = str(item["asset_id"])
            value = float(item["value"])
            parsed.append((asset_id, value))
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                message=f"Invalid comparison item for {metric.value}: {exc}",
                code="RENERYO_INVALID_RESPONSE",
                platform="reneryo",
            ) from exc

    reverse = metric in _HIGHER_IS_BETTER
    sorted_items = sorted(parsed, key=lambda x: x[1], reverse=reverse)

    return [
        ComparisonItem(asset_id=aid, value=val, rank=rank + 1)
        for rank, (aid, val) in enumerate(sorted_items)
    ]


def _compute_difference(items: list[ComparisonItem]) -> float:
    """
    Compute absolute difference between best and worst values.

    Args:
        items: Ranked comparison items.

    Returns:
        Absolute difference between first and last values.
    """
    if len(items) < 2:
        return 0.0
    values = [item.value for item in items]
    return round(abs(max(values) - min(values)), 2)
