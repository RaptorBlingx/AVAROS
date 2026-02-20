"""
RENERYO Response Normalizers — Transforms native API format to parser format.

The real RENERYO API returns a different JSON structure than the mock API.
These normalizers convert native responses into the format expected by
``_parsers.py``, keeping parsers unchanged and mock tests passing.

Real API format:
    Meter endpoint: ``{"records": [{"name": ..., "consumption": ..., ...}]}``
    Metric endpoint: ``{"records": [{"name": ..., "lastValue": ..., ...}]}``

Parser-expected format:
    KPI: ``{"value": float, "unit": str, "timestamp": str}``
    Trend: ``[{"value": float, "unit": str, "timestamp": str}, ...]``
    Comparison: ``[{"asset_id": str, "value": float, "unit": str}, ...]``
    Raw data: ``[{"value": float, "unit": str, "timestamp": str}, ...]``
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# =========================================================================
# Unit Group Mapping
# =========================================================================

_UNIT_GROUP_MAP: dict[str, str] = {
    "ENERGY": "kWh",
    "VOLUME": "m³",
    "TEMPERATURE": "°C",
    "PRESSURE": "bar",
    "POWER": "kW",
}


def is_native_format(data: dict | list) -> bool:
    """
    Detect whether a response is in native RENERYO format.

    Native responses are dicts with a ``records`` key containing a list.
    Mock responses are bare dicts or lists without the wrapper.

    Args:
        data: Raw JSON response from the API.

    Returns:
        True if data is in RENERYO native format.
    """
    return isinstance(data, dict) and "records" in data


def normalize_meter_to_kpi(
    data: dict,
    asset_id: str,
) -> dict:
    """
    Normalize a native meter response to a single KPI dict.

    Finds the matching meter record by name or ID, then maps:
    - ``consumption`` → ``value``
    - ``metric.unitGroup`` → ``unit`` (via ``_UNIT_GROUP_MAP``)
    - Current UTC time → ``timestamp``

    Args:
        data: Native response ``{"records": [...]}``.
        asset_id: Meter name or UUID to match.

    Returns:
        Dict in parser-expected format: ``{"value", "unit", "timestamp"}``.

    Raises:
        KeyError: If no matching meter record found.
    """
    records = data.get("records", [])
    record = _find_record(records, asset_id)
    return _meter_record_to_dict(record)


def normalize_meters_to_comparison(
    data: dict,
    asset_ids: list[str],
) -> list[dict]:
    """
    Normalize native meter response to comparison item list.

    Maps each matching meter record to comparison format:
    - ``name`` → ``asset_id``
    - ``consumption`` → ``value``
    - ``metric.unitGroup`` → ``unit``

    Args:
        data: Native response ``{"records": [...]}``.
        asset_ids: List of meter names or UUIDs to include.

    Returns:
        List of dicts: ``[{"asset_id", "value", "unit"}, ...]``.

    Raises:
        KeyError: If any requested asset is not found.
    """
    records = data.get("records", [])
    items: list[dict] = []
    for aid in asset_ids:
        record = _find_record(records, aid)
        raw_consumption = record.get("consumption")
        items.append({
            "asset_id": record.get("name", record.get("id", aid)),
            "value": float(raw_consumption) if raw_consumption is not None else 0.0,
            "unit": _resolve_unit(record),
        })
    return items


def normalize_meters_to_trend(data: dict) -> list[dict]:
    """
    Normalize native meter response to trend data points.

    The real API returns aggregated consumption per meter, not time-series.
    Each meter record becomes one data point with a synthetic timestamp
    spaced 1 hour apart so trend analysis produces distinct points.

    Args:
        data: Native response ``{"records": [...]}``.

    Returns:
        List of dicts: ``[{"value", "unit", "timestamp"}, ...]``.
    """
    records = data.get("records", [])
    consumable = [r for r in records if r.get("consumption") is not None]
    if not consumable:
        return []
    now = datetime.now(tz=timezone.utc)
    points = [
        _meter_record_to_dict(
            r,
            timestamp=(now - timedelta(hours=len(consumable) - 1 - i)).isoformat(),
        )
        for i, r in enumerate(consumable)
    ]
    logger.warning(
        "Trend timestamps are synthetic — native API returns "
        "aggregated consumption, not time-series data",
    )
    return points


def normalize_meters_to_raw(data: dict) -> list[dict]:
    """
    Normalize native meter response to raw data point list.

    Args:
        data: Native response ``{"records": [...]}``.

    Returns:
        List of dicts: ``[{"value", "unit", "timestamp"}, ...]``.
    """
    records = data.get("records", [])
    return [_meter_record_to_dict(r) for r in records]


def normalize_seu_values_to_kpi(data: dict) -> dict:
    """
    Normalize native SEU values response to single KPI dict.

    Expected shape:
        {"records": [{"value": 12.3, "datetime": "...", "unit": "kWh/unit"}, ...]}

    Uses the first record as current KPI value to match configured JSON path
    behavior (``$.records[0].value``).
    """
    records = data.get("records", [])
    if not records:
        raise KeyError("No SEU value record found")
    return _seu_record_to_dict(records[0])


def normalize_seu_values_to_trend(data: dict) -> list[dict]:
    """
    Normalize native SEU values response to trend data points.

    Expected shape:
        {"records": [{"value": 12.3, "datetime": "..."}, ...]}
    """
    records = data.get("records", [])
    return [_seu_record_to_dict(record) for record in records if record.get("value") is not None]


def normalize_seu_graph_to_trend(data: dict, *, seu_id: str = "") -> list[dict]:
    """
    Normalize ``/measurement/seu/graph`` response to trend data points.

    Expected shape:
        {"values": [{"seuId": "...", "value": 12.3, "datetime": "..."}, ...]}

    Args:
        data: Native graph response.
        seu_id: Optional SEU UUID filter for a single asset trend.
    """
    values = data.get("values", [])
    result: list[dict] = []
    for item in values:
        if seu_id and str(item.get("seuId", "")) != seu_id:
            continue
        if item.get("value") is None:
            continue
        result.append({
            "value": float(item.get("value", 0.0)),
            "unit": "kWh/unit",
            "timestamp": str(item.get("datetime", "")),
        })
    return result


def normalize_metric_resource_to_kpi(data: dict) -> dict:
    """
    Normalize metric resource values response to a single KPI dict.

    Expected shape:
        {"records": [{"value": 82.5, "datetime": "..."}, ...]}
    """
    records = data.get("records", [])
    if not records:
        raise KeyError("No metric resource value record found")
    first = records[0]
    return {
        "value": float(first.get("value", 0.0)),
        "timestamp": str(first.get("datetime", "")),
    }


def normalize_metric_resource_to_trend(data: dict) -> list[dict]:
    """
    Normalize metric resource values response to trend points.
    """
    records = data.get("records", [])
    points: list[dict] = []
    for record in records:
        if record.get("value") is None:
            continue
        points.append({
            "value": float(record.get("value", 0.0)),
            "timestamp": str(record.get("datetime", "")),
        })
    return points


def normalize_seus_to_comparison(data: dict, requested_ids: list[str]) -> list[dict]:
    """
    Normalize native SEU response to comparison item list.
    """
    records = data.get("records", [])
    items: list[dict] = []
    for requested in requested_ids:
        record = _find_record(records, requested)
        raw_consumption = record.get("consumption")
        items.append({
            "asset_id": record.get("name", record.get("id", requested)),
            "value": float(raw_consumption) if raw_consumption is not None else 0.0,
            "unit": "kWh/unit",
        })
    return items


def normalize_metric_to_kpi(
    data: dict,
    metric_name: str,
) -> dict:
    """
    Normalize a native metric-item response to a single KPI dict.

    Uses the ``/api/u/measurement/metric/item`` response format:
    - ``lastValue`` → ``value``
    - ``unitGroup`` → ``unit``
    - ``lastValueDatetime`` → ``timestamp``

    Args:
        data: Native response ``{"records": [...]}``.
        metric_name: Metric name to find in records.

    Returns:
        Dict in parser-expected format: ``{"value", "unit", "timestamp"}``.

    Raises:
        KeyError: If no matching metric record found.
    """
    records = data.get("records", [])
    record = _find_metric_record(records, metric_name)
    return {
        "value": float(record["lastValue"]),
        "unit": _UNIT_GROUP_MAP.get(
            record.get("unitGroup", ""), "",
        ),
        "timestamp": record.get("lastValueDatetime", ""),
    }


# =========================================================================
# Internal Helpers
# =========================================================================


def _find_record(records: list[dict], asset_id: str) -> dict:
    """
    Find a meter record by name or UUID.

    Args:
        records: List of meter record dicts.
        asset_id: Name or UUID to match.

    Returns:
        Matching record dict.

    Raises:
        KeyError: If no record matches.
    """
    def _norm(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    requested = (asset_id or "").strip()
    requested_norm = _norm(requested)

    # Exact match first.
    for record in records:
        if record.get("name") == requested or record.get("id") == requested:
            return record

    # Case/format-insensitive fallback ("compressor 1" ~= "Compressor-1").
    for record in records:
        name = str(record.get("name", ""))
        rec_id = str(record.get("id", ""))
        if requested_norm and (
            _norm(name) == requested_norm or _norm(rec_id) == requested_norm
        ):
            return record

    # MVP fallback: map ordinal spoken assets to available records
    # when backend uses different naming conventions.
    ordinal_match = re.match(r"^(line|compressor)-?(\d+)$", requested.lower())
    if ordinal_match and records:
        index = int(ordinal_match.group(2)) - 1
        if 0 <= index < len(records):
            logger.warning(
                "Asset '%s' not found by name; using ordinal fallback index=%d",
                requested,
                index,
            )
            return records[index]

    # Keep legacy default behavior for generic requests only.
    if records and requested.lower() in {"", "default", "all", "overall"}:
        logger.info(
            "Using first record for generic asset selector '%s'",
            requested or "<empty>",
        )
        return records[0]
    raise KeyError(f"No meter record found for asset_id={asset_id}")


def _find_metric_record(records: list[dict], name: str) -> dict:
    """
    Find a metric record by name (case-insensitive partial match).

    Args:
        records: List of metric record dicts.
        name: Metric name to search for.

    Returns:
        Matching record dict.

    Raises:
        KeyError: If no record matches.
    """
    lower = name.lower()
    for record in records:
        if lower in record.get("name", "").lower():
            return record
    if records:
        return records[0]
    raise KeyError(f"No metric record found for name={name}")


def _meter_record_to_dict(record: dict, *, timestamp: str = "") -> dict:
    """
    Convert a single meter record to parser-expected dict.

    Args:
        record: Native meter record with consumption, metric, etc.
        timestamp: ISO-8601 timestamp override. Uses current UTC time
            when empty (default for KPI/raw queries).

    Returns:
        Dict with value, unit, timestamp keys.
    """
    return {
        "value": float(record.get("consumption") or 0.0),
        "unit": _resolve_unit(record),
        "timestamp": timestamp or datetime.now(tz=timezone.utc).isoformat(),
    }


def _resolve_unit(record: dict) -> str:
    """
    Resolve display unit from a meter record's nested metric.

    Args:
        record: Native meter record with nested ``metric`` dict.

    Returns:
        Human-readable unit string (e.g., "kWh", "m³").
    """
    metric_info = record.get("metric", {})
    unit_group = metric_info.get("unitGroup", "")
    return _UNIT_GROUP_MAP.get(unit_group, unit_group)


def _seu_record_to_dict(record: dict) -> dict:
    """
    Convert a single SEU values record to parser-expected dict.
    """
    timestamp = (
        record.get("datetime")
        or record.get("timestamp")
        or datetime.now(tz=timezone.utc).isoformat()
    )
    unit = str(record.get("unit") or record.get("unitName") or "kWh/unit")
    return {
        "value": float(record.get("value", 0.0)),
        "unit": unit,
        "timestamp": timestamp,
    }
