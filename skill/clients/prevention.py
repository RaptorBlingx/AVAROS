"""PreventionClient — Anomaly Detection and Drift Monitoring Interface.

Abstract base class for anomaly detection and drift monitoring clients.
Platform-agnostic (DEC-001), domain models in skill.domain (DEC-003),
graceful degradation when unavailable (DEC-005).

Implementations:
    - StatisticalPreventionClient: Real z-score / linear-drift analysis
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from skill.clients._prevention_demo_data import (
    ANOMALY_DESCRIPTIONS,
    METRIC_CATEGORY_MAP,
)
from skill.clients.base import ExternalServiceClient
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, DataPoint

logger = logging.getLogger(__name__)


class PreventionClient(ExternalServiceClient):
    """
    Client interface for anomaly detection and drift monitoring.

    Provides two core capabilities:
        1. Anomaly detection — analyze data points for anomalies
        2. Drift monitoring — detect gradual KPI degradation

    Implementing Classes:
        - StatisticalPreventionClient: Real z-score / drift analysis
    """

    @abstractmethod
    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
        asset_id: str | None = None,
    ) -> AnomalyDetectionResult:
        """
        Analyze data points for anomalous behavior.

        Args:
            metric: The canonical metric to analyze
            data_points: Time-series data points to evaluate
            threshold: Deviation threshold in standard deviations
            asset_id: Optional asset identifier for clients that can
                return asset-scoped anomalies.

        Returns:
            AnomalyDetectionResult with detection findings

        Raises:
            ConnectionError: If the detection service is unavailable
        """

    @abstractmethod
    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """
        Check for gradual drift in metric values.

        Args:
            metric: The canonical metric to monitor
            data_points: Time-series data points to evaluate
            periods: Number of periods to analyze

        Returns:
            DriftReport with drift analysis findings

        Raises:
            ConnectionError: If the detection service is unavailable
        """


def _get_category_for_metric(metric: CanonicalMetric) -> str:
    """Map a canonical metric to its anomaly detection category."""
    return METRIC_CATEGORY_MAP.get(metric.value, "production")


def _build_anomaly_description(
    category: str,
    is_anomalous: bool,
    deviation: float,
) -> str:
    """Build a human-readable anomaly description from category and flags."""
    templates = ANOMALY_DESCRIPTIONS.get(
        category,
        ANOMALY_DESCRIPTIONS["production"],
    )
    key = "anomalous" if is_anomalous else "normal"
    template = templates[key]
    return template.format(deviation=f"{deviation:.1f}")


def _get_recommended_action(
    category: str,
    is_anomalous: bool,
) -> str | None:
    """Return a corrective action string if anomalous, else None."""
    if not is_anomalous:
        return None
    templates = ANOMALY_DESCRIPTIONS.get(
        category,
        ANOMALY_DESCRIPTIONS["production"],
    )
    return templates["action"]


def _get_detection_timestamp(data_points: list[DataPoint]) -> str:
    """Return ISO timestamp from last data point, or current UTC time."""
    if data_points:
        return data_points[-1].timestamp.isoformat()
    return datetime.now(tz=timezone.utc).isoformat()
