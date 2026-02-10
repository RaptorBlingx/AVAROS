"""PreventionClient — Anomaly Detection and Drift Monitoring Client.

REST API client for anomaly detection and drift monitoring (DEC-019).
Platform-agnostic (DEC-001), domain models in skill.domain (DEC-003),
graceful degradation when unavailable (DEC-005).
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from skill.clients._prevention_demo_data import (
    ANOMALOUS_METRICS,
    ANOMALY_DESCRIPTIONS,
    DRIFT_PROFILES,
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
        - MockPreventionClient: Demo data (zero-config, DEC-005)
        - Future: HttpPreventionClient (real REST API integration)
    """

    @abstractmethod
    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
    ) -> AnomalyDetectionResult:
        """
        Analyze data points for anomalous behavior.

        Args:
            metric: The canonical metric to analyze
            data_points: Time-series data points to evaluate
            threshold: Deviation threshold in standard deviations

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


def _is_metric_anomalous(metric: CanonicalMetric) -> bool:
    """Return True if this metric produces anomalies in demo mode."""
    return metric.value in ANOMALOUS_METRICS


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


class MockPreventionClient(PreventionClient):
    """
    Demo implementation of anomaly detection client.

    Returns realistic manufacturing anomaly data without an external
    service. Enables zero-config deployment (DEC-005). Deterministic:
    same metric always produces same result for testability.
    """

    def __init__(self) -> None:
        """Initialize the mock client."""
        self._initialized: bool = False

    # =====================================================================
    # Lifecycle Methods (ExternalServiceClient)
    # =====================================================================

    async def initialize(self) -> None:
        """Initialize mock client (no-op, always succeeds)."""
        self._initialized = True
        logger.info("MockPreventionClient initialized (demo mode)")

    async def shutdown(self) -> None:
        """Shut down mock client (safe to call multiple times)."""
        self._initialized = False
        logger.info("MockPreventionClient shut down")

    async def health_check(self) -> bool:
        """
        Check service health.

        Returns:
            Always True for mock implementation
        """
        return True

    @property
    def service_name(self) -> str:
        """
        Human-readable service name.

        Returns:
            Service display name
        """
        return "Anomaly Detection"

    @property
    def is_connected(self) -> bool:
        """
        Whether the client is connected.

        Returns:
            True after initialize() has been called
        """
        return self._initialized

    # =====================================================================
    # PreventionClient Methods
    # =====================================================================

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
    ) -> AnomalyDetectionResult:
        """
        Detect anomalies using deterministic demo data.

        Energy and carbon metrics return anomalous results;
        others return normal results. Same input always produces
        same output for testability.

        Args:
            metric: The canonical metric to analyze
            data_points: Time-series data (used for timestamp)
            threshold: Deviation threshold (used in description)

        Returns:
            AnomalyDetectionResult with demo findings
        """
        category = _get_category_for_metric(metric)
        is_anomalous = _is_metric_anomalous(metric)
        deviation = 2.3 if is_anomalous else 0.8
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
        )

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """
        Check for drift using deterministic demo profiles.

        Each metric category has a fixed drift profile for
        consistent, testable behavior.

        Args:
            metric: The canonical metric to monitor
            data_points: Time-series data (unused in mock)
            periods: Number of periods (used in result)

        Returns:
            DriftReport with demo drift analysis
        """
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


def _get_detection_timestamp(data_points: list[DataPoint]) -> str:
    """Return ISO timestamp from last data point, or current UTC time."""
    if data_points:
        return data_points[-1].timestamp.isoformat()
    return datetime.now(tz=timezone.utc).isoformat()
