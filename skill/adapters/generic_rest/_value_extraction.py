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
                code="GENERIC_REST_MAPPING_INVALID",
                platform="generic_rest",
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
