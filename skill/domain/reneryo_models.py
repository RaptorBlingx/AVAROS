"""Reneryo-specific read models used by the Future Gen dialogue layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ReneryoMetric:
    """Metric inventory row returned by Reneryo's read-only API."""

    metric_id: str
    name: str
    metric_type: str
    unit_group: str
    last_value: float | None = None
    last_value_at: datetime | None = None


@dataclass(frozen=True)
class ReneryoMeter:
    """Period-scoped Reneryo meter result."""

    meter_id: str
    name: str
    energy_resource: str
    consumption: float | None
    metric_id: str
    metric_name: str
    slice_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReneryoTrendPoint:
    """One Reneryo-aggregated metric observation."""

    timestamp: datetime
    value: float
    sample_count: int


@dataclass(frozen=True)
class ReneryoTrend:
    """Trend summary over Reneryo-owned aggregate values."""

    metric: ReneryoMetric
    period_label: str
    aggregation: str
    points: tuple[ReneryoTrendPoint, ...]
    direction: str
    change_percent: float | None


@dataclass(frozen=True)
class ReneryoRegression:
    """Saved regression result calculated and owned by Reneryo."""

    regression_id: str
    regression_type: str
    driver_names: tuple[str, ...]
    slice_names: tuple[str, ...]
    period: str
    r_squared: float | None
    rmse: float | None
    primary: bool
    train_start: datetime
    train_end: datetime
    predict_start: datetime | None = None
    predict_end: datetime | None = None


@dataclass(frozen=True)
class LocalizedText:
    """English/Turkish text supplied by MDSP."""

    en: str
    tr: str

    def for_language(self, language: str) -> str:
        """Select Turkish for Turkish locales and English otherwise."""
        return self.tr if language.lower().startswith("tr") else self.en


@dataclass(frozen=True)
class MdspNextReview:
    code: str
    version: int
    instruction: LocalizedText
    rationale: LocalizedText
    evidence_keys: tuple[str, ...]
    policy_status: str
    assessment_run_id: str
    review_link: str | None


@dataclass(frozen=True)
class MdspFinding:
    """Explainable MDSP finding retrieved through the service interface."""

    finding_id: str
    status: str
    severity: str
    domain: str
    entity_type: str
    entity_id: str
    title: LocalizedText
    summary: LocalizedText
    evidence: dict[str, Any]
    assumptions: tuple[LocalizedText, ...]
    evaluation_start: datetime
    evaluation_end: datetime
    source_watermark: datetime | None
    deep_link: str | None
    provisional: bool
    metric_name: str = ""
    rule_id: str = ""
    rule_version: int = 0
    next_review: MdspNextReview | None = None
    next_review_abstention: LocalizedText | None = None
    retired_at: datetime | None = None


@dataclass(frozen=True)
class MdspFindingList:
    """Active/resolved finding inventory with MDSP-owned counts."""

    findings: tuple[MdspFinding, ...]
    active_count: int
    resolved_count: int
    severity_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MdspEvaluation:
    """Completed MDSP evaluation; rules and findings remain MDSP-owned."""

    run_id: str
    source_watermark: datetime | None
    evaluated_resource_count: int
    active_finding_count: int
    resolved_finding_count: int
