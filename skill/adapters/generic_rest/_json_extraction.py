"""Facade exports for Generic REST value/trend extraction helpers."""

from __future__ import annotations

from skill.adapters.generic_rest._trend_extraction import (
    compute_trend_change,
    extract_trend_points,
)
from skill.adapters.generic_rest._value_extraction import (
    canonical_aggregation,
    MetricMapping,
    extract_mapped_value,
    get_mapping_json_path,
    get_mapping_aggregation,
    get_mapping_unit,
    parse_mapped_kpi_response,
    rank_descending,
)

__all__ = [
    "MetricMapping",
    "canonical_aggregation",
    "compute_trend_change",
    "extract_mapped_value",
    "extract_trend_points",
    "get_mapping_json_path",
    "get_mapping_aggregation",
    "get_mapping_unit",
    "parse_mapped_kpi_response",
    "rank_descending",
]
