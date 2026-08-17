"""KPI value extraction helpers for Generic REST metric mappings."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult

MetricMapping = dict[str, Any]


_HIGHER_IS_BETTER: set[CanonicalMetric] = {
    CanonicalMetric.OEE,
    CanonicalMetric.MATERIAL_EFFICIENCY,
    CanonicalMetric.THROUGHPUT,
    CanonicalMetric.SUPPLIER_ON_TIME,
    CanonicalMetric.RECYCLED_CONTENT,
}

_SUM_METRICS = {
    CanonicalMetric.ENERGY_TOTAL,
    CanonicalMetric.CO2_TOTAL,
}
_MAX_METRICS = {CanonicalMetric.PEAK_DEMAND}
_VALID_AGGREGATIONS = {"average", "sum", "max", "latest"}


def canonical_aggregation(metric: CanonicalMetric, period: TimePeriod) -> str:
    """Return the safe default aggregation for a canonical metric query."""
    if period.display_name == "latest available":
        return "latest"
    if metric in _SUM_METRICS:
        return "sum"
    if metric in _MAX_METRICS:
        return "max"
    return "average"


def get_mapping_aggregation(
    mapping: MetricMapping,
    metric: CanonicalMetric,
    period: TimePeriod,
) -> str:
    """Resolve and validate mapping-level aggregation overrides."""
    aggregation = str(mapping.get("aggregation", "") or "").strip().lower()
    if not aggregation:
        return canonical_aggregation(metric, period)
    if aggregation not in _VALID_AGGREGATIONS:
        raise AdapterError(
            message=f"Unsupported metric aggregation '{aggregation}'",
            code="GENERIC_REST_MAPPING_INVALID",
            platform="generic_rest",
            user_message="The configured aggregation for this metric is invalid.",
        )
    return aggregation


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
    """Extract and transform KPI value from payload.

    Args:
        data: Upstream JSON payload.
        json_path: Supported JSONPath subset expression.
        mapping: Metric mapping dict (contains optional transform).

    Returns:
        Numeric KPI value after optional transform.

    Raises:
        AdapterError: If value is missing, invalid or transform is unsupported.
    """
    value = resolve_json_path(data, json_path)
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

    return apply_transform(numeric, mapping.get("transform"))


def parse_mapped_kpi_response(
    data: dict | list,
    mapping: MetricMapping,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
    *,
    source_profile: str = "",
) -> KPIResult:
    """Parse mapped KPI payload into KPIResult."""
    aggregation = get_mapping_aggregation(mapping, metric, period)
    series = _resolve_kpi_series(data, mapping)
    observed_at: datetime | None = None
    source_start: datetime | None = None
    source_end: datetime | None = None
    sample_count = 1
    coverage_status = "complete"
    warnings: list[str] = []

    if series is not None:
        values, timestamps = _parse_series_values(series, mapping)
        value = _aggregate_values(values, timestamps, aggregation)
        sample_count = len(values)
        valid_times = [item for item in timestamps if item is not None]
        if valid_times:
            source_start = min(valid_times)
            source_end = max(valid_times)
            observed_at = source_end
        total = _payload_record_count(data)
        if total is not None and total > sample_count:
            coverage_status = "partial"
            warnings.append(
                f"Only {sample_count} of {total} source observations were retrieved."
            )
        freshness_seconds = _positive_int(mapping.get("freshness_seconds"))
        if freshness_seconds and observed_at is not None:
            age_seconds = (datetime.now(tz=timezone.utc) - observed_at).total_seconds()
            if age_seconds > freshness_seconds:
                coverage_status = "stale" if coverage_status == "complete" else coverage_status
                warnings.append(
                    f"Latest source observation is older than {freshness_seconds} seconds."
                )
    else:
        json_path = get_mapping_json_path(mapping)
        value = extract_mapped_value(data, json_path, mapping)

    return KPIResult(
        metric=metric,
        value=value,
        unit=get_mapping_unit(mapping, metric),
        asset_id=asset_id,
        period=period,
        timestamp=datetime.now(tz=timezone.utc),
        source_observed_at=observed_at,
        source_period_start=source_start,
        source_period_end=source_end,
        sample_count=sample_count,
        aggregation=aggregation,
        source_profile=source_profile,
        coverage_status=coverage_status,
        warnings=tuple(warnings),
    )


def _resolve_kpi_series(
    payload: dict | list,
    mapping: MetricMapping,
) -> list[Any] | None:
    """Resolve an explicitly mapped or conventional KPI observation list."""
    series_path = str(mapping.get("series_path", "") or "").strip()
    if series_path:
        resolved = resolve_json_path(payload, series_path)
        if not isinstance(resolved, list):
            raise AdapterError(
                message="series_path must resolve to a list",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            )
        return resolved
    json_path = str(mapping.get("json_path", "") or "").strip()
    if (
        isinstance(payload, dict)
        and json_path.startswith("$.records[")
        and isinstance(payload.get("records"), list)
    ):
        return payload["records"]
    if isinstance(payload, list) and json_path in {"$.[0]", "$[0]"}:
        return payload
    return None


def _parse_series_values(
    series: list[Any],
    mapping: MetricMapping,
) -> tuple[list[float], list[datetime | None]]:
    """Parse numeric values and source timestamps from observation records."""
    if not series:
        raise AdapterError(
            message="No source observations in selected period",
            code="GENERIC_REST_NO_DATA",
            platform="generic_rest",
            user_message="I couldn't find data for that period.",
        )
    value_key = str(mapping.get("value_path", "value") or "value").split(".")[-1]
    timestamp_key = str(mapping.get("timestamp_path", "datetime") or "datetime").split(".")[-1]
    values: list[float] = []
    timestamps: list[datetime | None] = []
    for item in series:
        raw_value = item.get(value_key) if isinstance(item, dict) else item
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                message=f"Series observation is not numeric: {raw_value}",
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
            ) from exc
        values.append(apply_transform(numeric, mapping.get("transform")))
        raw_timestamp = item.get(timestamp_key) if isinstance(item, dict) else None
        if raw_timestamp is None and isinstance(item, dict):
            raw_timestamp = first_present(item, ("timestamp", "datetime", "date", "time"))
        timestamps.append(_parse_source_timestamp(raw_timestamp))
    return values, timestamps


def _aggregate_values(
    values: list[float],
    timestamps: list[datetime | None],
    aggregation: str,
) -> float:
    """Aggregate complete source observations with deterministic semantics."""
    if aggregation == "sum":
        return sum(values)
    if aggregation == "max":
        return max(values)
    if aggregation == "average":
        return sum(values) / len(values)
    dated = [
        (timestamp, value)
        for value, timestamp in zip(values, timestamps)
        if timestamp is not None
    ]
    if dated:
        return max(dated, key=lambda item: item[0])[1]
    return values[-1]


def _parse_source_timestamp(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _payload_record_count(payload: dict | list) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("recordCount", "record_count", "total", "totalCount"):
        value = payload.get(key)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def _positive_int(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def rank_descending(metric: CanonicalMetric) -> bool:
    """Return True when higher metric values should rank first."""
    return metric in _HIGHER_IS_BETTER


def resolve_json_path(payload: dict | list, json_path: str) -> Any:
    """Resolve a small JSONPath subset.

    Supported syntax:
        - Root-prefixed paths like ``$.a.b``
        - List indexing like ``$.records[0].value``

    Limitations:
        - No wildcards, filters, unions, slices or recursive descent.

    Args:
        payload: JSON payload to traverse.
        json_path: Path expression in supported subset.

    Returns:
        Resolved value at requested path.

    Raises:
        AdapterError: If syntax is unsupported or path cannot be resolved.
    """
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
                code="GENERIC_REST_NO_DATA",
                platform="generic_rest",
                user_message=(
                    "I couldn't find data for that time period. "
                    "Try a different range like last week or last month."
                ),
            )
        current = current[index]

    return current


def apply_transform(value: float, transform: Any) -> float:
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


def first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return first non-None value from dict keys."""
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None
