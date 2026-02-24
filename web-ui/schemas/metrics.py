"""Request and response schemas for metric mapping APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel

from skill.domain.models import CanonicalMetric


CANONICAL_METRIC_VALUES = tuple(metric.value for metric in CanonicalMetric)
CanonicalMetricName = Literal[*CANONICAL_METRIC_VALUES]


class MetricMappingRequest(BaseModel):
    """Payload for creating/updating a metric mapping."""

    canonical_metric: CanonicalMetricName = Field(
        ...,
        description="Canonical metric name to map (e.g., energy_per_unit).",
    )
    endpoint: str = Field(
        ...,
        min_length=1,
        description="Platform API endpoint path for this metric.",
    )
    json_path: str = Field(
        ...,
        min_length=1,
        description="JSONPath expression to extract metric value.",
    )
    unit: str = Field(
        ...,
        min_length=1,
        description="Display/storage unit for this metric mapping.",
    )
    transform: str | None = Field(
        default=None,
        description="Optional transform instruction (future use).",
    )


class MetricMappingResponse(BaseModel):
    """Metric mapping response object."""

    canonical_metric: CanonicalMetricName = Field(
        ...,
        description="Canonical metric name.",
    )
    endpoint: str = Field(
        ...,
        description="Platform API endpoint path.",
    )
    json_path: str = Field(
        ...,
        description="JSONPath expression for value extraction.",
    )
    unit: str = Field(
        ...,
        description="Mapped metric unit.",
    )
    transform: str | None = Field(
        default=None,
        description="Optional transform instruction.",
    )


class MetricMappingListResponse(RootModel[list[MetricMappingResponse]]):
    """Array response wrapper for metric mappings list."""


MetricAuthType = Literal["bearer", "cookie"]


class MetricMappingTestRequest(BaseModel):
    """Payload for validating a single metric mapping against remote API."""

    base_url: str = Field(
        ...,
        min_length=1,
        description="Platform base API URL.",
    )
    endpoint: str = Field(
        ...,
        min_length=1,
        description="Metric endpoint path relative to base_url.",
    )
    json_path: str = Field(
        ...,
        min_length=1,
        description="JSONPath expression used to extract the metric value.",
    )
    auth_type: MetricAuthType = Field(
        ...,
        description="Authentication type to use for outbound request.",
    )
    auth_token: str = Field(
        ...,
        description="Bearer token or session cookie value.",
    )


class MetricMappingTestResponse(BaseModel):
    """Result of metric mapping test execution."""

    success: bool = Field(..., description="Whether mapping test succeeded.")
    value: float | None = Field(
        default=None,
        description="Extracted numeric value when success is true.",
    )
    raw_response_preview: str = Field(
        ...,
        description="First 500 chars of upstream response body.",
    )
    error: str | None = Field(
        default=None,
        description="Human-readable error when success is false.",
    )
