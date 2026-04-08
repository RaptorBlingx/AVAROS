"""MockPreventionClient for deterministic test use.

Used when tests need deterministic, predictable anomaly results
independent of actual data values. Production uses HttpPreventionClient.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from skill.clients._prevention_demo_data import (
    ANOMALOUS_METRICS,
    DRIFT_PROFILES,
)
from skill.clients.prevention import (
    PreventionClient,
    _build_anomaly_description,
    _get_category_for_metric,
    _get_recommended_action,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, DataPoint

logger = logging.getLogger(__name__)


def _is_metric_anomalous(metric: CanonicalMetric) -> bool:
    """Return True if this metric produces anomalies in demo mode."""
    return metric.value in ANOMALOUS_METRICS


def _get_detection_timestamp(data_points: list[DataPoint]) -> str:
    """Return ISO timestamp from last data point, or current UTC time."""
    if data_points:
        return data_points[-1].timestamp.isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


class MockPreventionClient(PreventionClient):
    """Deterministic demo implementation for testing.

    Returns predictable anomaly data without analyzing real values.
    Energy and carbon metrics always anomalous; others always normal.
    Same metric always produces the same result for testability.
    """

    def __init__(self) -> None:
        """Initialize the mock client."""
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize mock client (no-op, always succeeds)."""
        self._initialized = True
        logger.info("MockPreventionClient initialized (demo mode)")

    async def shutdown(self) -> None:
        """Shut down mock client (safe to call multiple times)."""
        self._initialized = False
        logger.info("MockPreventionClient shut down")

    async def health_check(self) -> bool:
        """Return True — mock is always healthy."""
        return True

    @property
    def service_name(self) -> str:
        """Human-readable service name."""
        return "Anomaly Detection"

    @property
    def is_connected(self) -> bool:
        """Whether the client has been initialized."""
        return self._initialized

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
        asset_id: str | None = None,
    ) -> AnomalyDetectionResult:
        """Detect anomalies using deterministic demo data."""
        category = _get_category_for_metric(metric)
        is_anomalous = _is_metric_anomalous(metric)
        deviation = (
            threshold + 0.3 if is_anomalous else max(threshold - 1.2, 0.8)
        )
        description = _build_anomaly_description(
            category, is_anomalous, deviation,
        )
        action = _get_recommended_action(category, is_anomalous)
        detected_at = _get_detection_timestamp(data_points)

        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=is_anomalous,
            severity="medium" if is_anomalous else "none",
            confidence=0.85,
            anomaly_type="spike" if is_anomalous else None,
            description=description,
            detected_at=detected_at,
            recommended_action=action,
            expected_value=100.0 if is_anomalous else None,
            actual_value=120.0 if is_anomalous else None,
            deviation=deviation,
        )

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """Check for drift using deterministic demo profiles."""
        category = _get_category_for_metric(metric)
        profile = DRIFT_PROFILES.get(
            category,
            DRIFT_PROFILES["production"],
        )

        return DriftReport(
            metric=metric,
            has_drift=profile["has_drift"],
            drift_direction=profile["direction"],
            drift_rate=profile["rate"],
            periods_analyzed=periods,
            description=profile["description"],
        )
