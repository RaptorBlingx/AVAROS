"""Facade exports for Generic REST mapping helper functions."""

from __future__ import annotations

from skill.adapters.generic_rest._json_extraction import (
    MetricMapping,
    compute_trend_change,
    extract_mapped_value,
    extract_trend_points,
    get_mapping_json_path,
    get_mapping_unit,
    parse_mapped_kpi_response,
    rank_descending,
)
from skill.adapters.generic_rest._request_helpers import resolve_request

__all__ = [
    "MetricMapping",
    "compute_trend_change",
    "extract_mapped_value",
    "extract_trend_points",
    "get_mapping_json_path",
    "get_mapping_unit",
    "parse_mapped_kpi_response",
    "rank_descending",
    "resolve_request",
]
