"""
Anomaly Detection and Drift Monitoring Domain Models

Immutable data models for anomaly detection results and drift reports.
Used by external service clients (anomaly detection services) to return
structured analysis of time-series manufacturing data.

These models are platform-agnostic (DEC-001) — no service-specific
terminology in model names or field names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric


@dataclass(frozen=True)
class AnomalyDetectionResult:
    """
    Result from an anomaly detection analysis.

    Indicates whether a metric exhibits anomalous behavior, with
    severity classification and actionable recommendations.

    Attributes:
        metric: The canonical metric that was analyzed
        is_anomalous: Whether an anomaly was detected
        severity: Severity level (none, low, medium, high, critical)
        confidence: Detection confidence score (0.0 to 1.0)
        anomaly_type: Type of anomaly detected, or None
        description: Human-readable explanation of the finding
        detected_at: ISO 8601 timestamp of detection
        recommended_action: Suggested corrective action, or None

    Example:
        AnomalyDetectionResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            is_anomalous=True,
            severity="medium",
            confidence=0.85,
            anomaly_type="spike",
            description="Energy per unit spiked 2.3σ above baseline.",
            detected_at="2026-02-10T14:30:00Z",
            recommended_action="Check compressor maintenance schedule.",
        )
    """

    metric: CanonicalMetric
    is_anomalous: bool
    severity: str
    confidence: float
    anomaly_type: str | None
    description: str
    detected_at: str
    recommended_action: str | None


@dataclass(frozen=True)
class DriftReport:
    """
    Result from a drift monitoring analysis.

    Reports whether a metric shows gradual drift (improving, degrading,
    or stable) over a specified number of periods.

    Attributes:
        metric: The canonical metric that was analyzed
        has_drift: Whether meaningful drift was detected
        drift_direction: Direction of change (improving, degrading, stable)
        drift_rate: Rate of change per period (negative = decreasing)
        periods_analyzed: Number of periods included in the analysis
        description: Human-readable summary of the drift finding

    Example:
        DriftReport(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            has_drift=True,
            drift_direction="improving",
            drift_rate=-0.3,
            periods_analyzed=7,
            description="Energy per unit decreased 0.3 kWh/unit per day ...",
        )
    """

    metric: CanonicalMetric
    has_drift: bool
    drift_direction: str
    drift_rate: float
    periods_analyzed: int
    description: str
