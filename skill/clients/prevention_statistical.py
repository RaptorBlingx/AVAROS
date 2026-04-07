"""StatisticalPreventionClient — Real Anomaly Detection and Drift Monitoring.

Implements z-score anomaly detection and linear regression drift analysis
using pure Python math (no numpy/pandas dependencies).

Platform-agnostic (DEC-001), domain models in skill.domain (DEC-003),
zero-config — works with any configured adapter (DEC-005).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from skill.clients._prevention_demo_data import METRIC_CATEGORY_MAP
from skill.clients.prevention import (
    PreventionClient,
    _build_anomaly_description,
    _get_category_for_metric,
    _get_detection_timestamp,
    _get_recommended_action,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, DataPoint

logger = logging.getLogger(__name__)

_MIN_ANOMALY_POINTS = 3
_MIN_DRIFT_POINTS = 10
_DRIFT_SLOPE_THRESHOLD = 0.001
_DRIFT_R2_THRESHOLD = 0.1


def _classify_severity(z_score: float, threshold: float = 2.0) -> str:
    """Classify anomaly severity from z-score magnitude.

    Severity contract:
        - ``"none"`` only when z_score < threshold (not anomalous).
        - ``"low"`` / ``"medium"`` / ``"high"`` / ``"critical"`` when
          z_score >= threshold (anomalous), so callers never see
          ``is_anomalous=True`` paired with ``severity="none"``.

    Args:
        z_score: Absolute z-score magnitude.
        threshold: Anomaly detection threshold (default 2.0).

    Returns:
        Severity string.
    """
    if z_score < threshold:
        return "none"
    if z_score < 2.5:
        return "low"
    if z_score < 3.0:
        return "medium"
    if z_score < 4.0:
        return "high"
    return "critical"


def _mean(values: list[float]) -> float:
    """Compute arithmetic mean."""
    return sum(values) / len(values)


def _std(values: list[float], mean_val: float) -> float:
    """Compute population standard deviation."""
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _linear_regression(
    values: list[float],
) -> tuple[float, float, float]:
    """Compute slope, intercept, and R² via least-squares.

    Args:
        values: Ordered numeric values (y-axis; x = 0, 1, 2, ...).

    Returns:
        Tuple of (slope, intercept, r_squared).
    """
    n = len(values)
    sum_x = n * (n - 1) / 2.0
    sum_x2 = n * (n - 1) * (2 * n - 1) / 6.0
    sum_y = sum(values)
    sum_xy = sum(i * v for i, v in enumerate(values))

    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return 0.0, _mean(values), 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    mean_y = sum_y / n
    ss_tot = sum((v - mean_y) ** 2 for v in values)
    ss_res = sum(
        (v - (slope * i + intercept)) ** 2
        for i, v in enumerate(values)
    )
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, r_squared


class StatisticalPreventionClient(PreventionClient):
    """Real anomaly detection and drift monitoring using statistical methods.

    Implements z-score anomaly detection and linear regression drift
    analysis on actual time-series data from the adapter. No external
    service required — runs locally with pure Python math.

    Algorithms:
        - Z-score anomaly: deviation from mean in standard deviations
        - Linear drift: least-squares slope + R² significance test
    """

    def __init__(self) -> None:
        """Initialize the statistical client."""
        self._initialized: bool = False

    # =====================================================================
    # Lifecycle Methods (ExternalServiceClient)
    # =====================================================================

    async def initialize(self) -> None:
        """Initialize client (no external connection needed)."""
        self._initialized = True
        logger.info("StatisticalPreventionClient initialized")

    async def shutdown(self) -> None:
        """Shut down client (safe to call multiple times)."""
        self._initialized = False
        logger.info("StatisticalPreventionClient shut down")

    async def health_check(self) -> bool:
        """Return True — no external dependency to check."""
        return True

    @property
    def service_name(self) -> str:
        """Human-readable service name (DEC-001: no platform names)."""
        return "Anomaly Detection"

    @property
    def is_connected(self) -> bool:
        """Whether the client has been initialized."""
        return self._initialized

    # =====================================================================
    # Anomaly Detection — Z-Score
    # =====================================================================

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
        asset_id: str | None = None,
    ) -> AnomalyDetectionResult:
        """Detect anomalies using z-score analysis on real data.

        Computes the z-score for each data point and flags the most
        extreme deviation if it exceeds the threshold.

        Args:
            metric: The canonical metric to analyze.
            data_points: Time-series data points to evaluate.
            threshold: Z-score threshold for anomaly detection.

        Returns:
            AnomalyDetectionResult with real detection findings.
        """
        category = _get_category_for_metric(metric)
        values = [dp.value for dp in data_points]

        if len(values) < _MIN_ANOMALY_POINTS:
            return self._insufficient_data_result(
                metric, category, data_points,
                reason="anomaly detection",
                min_required=_MIN_ANOMALY_POINTS,
            )

        mean_val = _mean(values)
        std_val = _std(values, mean_val)

        if std_val == 0:
            return AnomalyDetectionResult(
                metric=metric,
                is_anomalous=False,
                severity="none",
                confidence=1.0,
                anomaly_type=None,
                description=(
                    f"{metric.display_name} values are completely stable "
                    f"(zero variance across {len(values)} data points)."
                ),
                detected_at=_get_detection_timestamp(data_points),
                recommended_action=None,
            )

        max_z = 0.0
        max_idx = 0
        for i, v in enumerate(values):
            z = abs(v - mean_val) / std_val
            if z > max_z:
                max_z = z
                max_idx = i

        is_anomalous = max_z >= threshold
        severity = _classify_severity(max_z, threshold)
        anomaly_type: str | None = None

        if is_anomalous:
            anomaly_type = (
                "spike" if values[max_idx] > mean_val else "dip"
            )

        description = _build_anomaly_description(
            category, is_anomalous, max_z,
        )
        action = _get_recommended_action(category, is_anomalous)
        detected_at = (
            data_points[max_idx].timestamp.isoformat()
            if is_anomalous
            else _get_detection_timestamp(data_points)
        )

        confidence = min(0.99, 0.5 + (len(values) / 200.0))

        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=is_anomalous,
            severity=severity,
            confidence=round(confidence, 2),
            anomaly_type=anomaly_type,
            description=description,
            detected_at=detected_at,
            recommended_action=action,
            expected_value=mean_val,
            actual_value=values[max_idx],
            deviation=round(max_z, 2),
        )

    # =====================================================================
    # Drift Detection — Linear Regression
    # =====================================================================

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """Detect gradual drift using linear regression on real data.

        Fits a least-squares line to the data and reports drift when
        the slope is significant (|slope| > 0.001) and the fit is
        meaningful (R² > 0.1).

        Args:
            metric: The canonical metric to monitor.
            data_points: Time-series data points to evaluate.
            periods: Number of periods for context in the report.

        Returns:
            DriftReport with real drift analysis findings.
        """
        values = [dp.value for dp in data_points]

        if len(values) < _MIN_DRIFT_POINTS:
            return DriftReport(
                metric=metric,
                has_drift=False,
                drift_direction="stable",
                drift_rate=0.0,
                periods_analyzed=0,
                description=(
                    f"Insufficient data for drift analysis "
                    f"({len(values)} points, minimum {_MIN_DRIFT_POINTS} "
                    f"required)."
                ),
            )

        slope, _intercept, r_squared = _linear_regression(values)

        has_drift = (
            abs(slope) > _DRIFT_SLOPE_THRESHOLD
            and r_squared > _DRIFT_R2_THRESHOLD
        )

        if has_drift:
            direction = "degrading" if self._is_increase_bad(metric, slope) else "improving"
        else:
            direction = "stable"

        description = (
            f"{metric.display_name} shows a "
            f"{'significant' if has_drift else 'no significant'} "
            f"trend (slope={slope:.6f}/point, R²={r_squared:.4f}) "
            f"over {len(values)} data points."
        )

        return DriftReport(
            metric=metric,
            has_drift=has_drift,
            drift_direction=direction,
            drift_rate=round(slope, 6),
            periods_analyzed=periods,
            description=description,
        )

    # =====================================================================
    # Internal Helpers
    # =====================================================================

    @staticmethod
    def _is_increase_bad(metric: CanonicalMetric, slope: float) -> bool:
        """Return True when an increasing trend is undesirable.

        For metrics where *lower is better* (energy, scrap, CO₂,
        lead time, cycle time), an upward slope is degrading.
        For metrics where *higher is better* (OEE, throughput,
        material efficiency, on-time delivery), a downward slope
        is degrading.
        """
        category = METRIC_CATEGORY_MAP.get(metric.value, "production")
        higher_is_better = category == "production" or metric.value in {
            "material_efficiency",
            "recycled_content",
            "supplier_on_time",
        }
        if higher_is_better:
            return slope < 0
        return slope > 0

    @staticmethod
    def _insufficient_data_result(
        metric: CanonicalMetric,
        category: str,
        data_points: list[DataPoint],
        *,
        reason: str,
        min_required: int,
    ) -> AnomalyDetectionResult:
        """Build a 'not enough data' result."""
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=False,
            severity="none",
            confidence=0.0,
            anomaly_type=None,
            description=(
                f"Insufficient data for {reason} "
                f"({len(data_points)} points, minimum {min_required} "
                f"required)."
            ),
            detected_at=_get_detection_timestamp(data_points),
            recommended_action=None,
        )
