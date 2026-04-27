"""
AlertMonitor — Proactive Background Anomaly & Drift Checker

Orchestrates background checks across configured metric–asset pairs.
Applies cooldown suppression to avoid repeating alerts within the
configured window.

DEC-001: Platform-agnostic — no platform names.
DEC-007: Adapters only fetch data; intelligence in services.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from skill.domain.alert_models import (
    AlertConfig,
    AlertEvent,
    AlertType,
    MonitoredPair,
    SeverityLevel,
)

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric
    from skill.use_cases.query_dispatcher import QueryDispatcher

logger = logging.getLogger(__name__)

_SEVERITY_ORDER: dict[SeverityLevel, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _severity_meets_threshold(
    severity: SeverityLevel,
    threshold: SeverityLevel,
) -> bool:
    """Return True if *severity* is at or above *threshold*."""
    return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER.get(
        threshold, 0,
    )


def _cooldown_elapsed(
    last_alert_time: datetime | None,
    cooldown_minutes: int,
    now: datetime,
) -> bool:
    """Return True if enough time has passed since the last alert."""
    if last_alert_time is None:
        return True
    elapsed = (now - last_alert_time).total_seconds()
    return elapsed >= cooldown_minutes * 60


def _pair_key(alert_type: AlertType, pair: MonitoredPair) -> str:
    """Build a unique cache key for suppression tracking."""
    return f"{alert_type}:{pair.metric.value}:{pair.asset_id}"


def _drift_severity(direction: str, rate: float) -> SeverityLevel:
    """Map drift direction and rate to alert severity."""
    if direction != "degrading":
        return "low"

    magnitude = abs(rate)
    if magnitude >= 0.01:
        return "high"
    if magnitude >= 0.003:
        return "medium"
    return "low"


class AlertMonitor:
    """Runs background anomaly/drift checks and builds alert events.

    The monitor does NOT speak — it returns ``AlertEvent`` objects so
    the caller (the skill scheduler) decides how to announce them.

    Attributes:
        _last_alerts: Tracks last alert times for cooldown suppression.
    """

    def __init__(self) -> None:
        self._last_alerts: dict[str, datetime] = {}

    def run_check(
        self,
        dispatcher: QueryDispatcher,
        config: AlertConfig,
        pairs: list[MonitoredPair],
    ) -> list[AlertEvent]:
        """Execute a full background check cycle.

        Iterates every *pair*, runs both anomaly and drift detection,
        applies cooldown/threshold suppression, and returns results.

        Args:
            dispatcher: QueryDispatcher with an active adapter.
            config: Current alert configuration.
            pairs: Metric–asset pairs to check.

        Returns:
            List of AlertEvent (may include suppressed events).
        """
        now = datetime.now(timezone.utc)
        events: list[AlertEvent] = []

        for pair in pairs:
            events.extend(
                self._check_pair(dispatcher, config, pair, now),
            )

        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_pair(
        self,
        dispatcher: QueryDispatcher,
        config: AlertConfig,
        pair: MonitoredPair,
        now: datetime,
    ) -> list[AlertEvent]:
        """Run anomaly + drift checks for a single pair."""
        events: list[AlertEvent] = []

        anomaly_event = self._check_anomaly(
            dispatcher, config, pair, now,
        )
        if anomaly_event is not None:
            events.append(anomaly_event)

        drift_event = self._check_drift(
            dispatcher, config, pair, now,
        )
        if drift_event is not None:
            events.append(drift_event)

        return events

    def _check_anomaly(
        self,
        dispatcher: QueryDispatcher,
        config: AlertConfig,
        pair: MonitoredPair,
        now: datetime,
    ) -> AlertEvent | None:
        """Run anomaly detection for one pair; return event or None."""
        try:
            result = dispatcher.check_anomaly(
                metric=pair.metric,
                asset_id=pair.asset_id,
                threshold=config.z_score_threshold,
            )
        except Exception as exc:
            logger.warning(
                "Background anomaly check failed for %s/%s: %s",
                pair.metric.value, pair.asset_id, exc,
            )
            return None

        if not result.is_anomalous:
            return None

        return self._build_event(
            alert_type="anomaly",
            pair=pair,
            severity=result.severity,
            config=config,
            now=now,
            description=self._anomaly_message(
                pair.metric, pair.asset_id, result,
            ),
        )

    def _check_drift(
        self,
        dispatcher: QueryDispatcher,
        config: AlertConfig,
        pair: MonitoredPair,
        now: datetime,
    ) -> AlertEvent | None:
        """Run drift detection for one pair; return event or None."""
        try:
            result = dispatcher.check_drift(
                metric=pair.metric, asset_id=pair.asset_id,
            )
        except Exception as exc:
            logger.warning(
                "Background drift check failed for %s/%s: %s",
                pair.metric.value, pair.asset_id, exc,
            )
            return None

        if not result.has_drift:
            return None

        return self._build_event(
            alert_type="drift",
            pair=pair,
            severity=_drift_severity(
                result.drift_direction,
                result.drift_rate,
            ),
            config=config,
            now=now,
            description=self._drift_message(
                pair.metric, pair.asset_id, result,
            ),
        )

    def _build_event(
        self,
        *,
        alert_type: AlertType,
        pair: MonitoredPair,
        severity: SeverityLevel,
        config: AlertConfig,
        now: datetime,
        description: str,
    ) -> AlertEvent:
        """Create an AlertEvent with suppression logic applied."""
        key = _pair_key(alert_type, pair)
        suppressed = not self._should_alert(
            severity, config, key, now,
        )
        if not suppressed:
            self._last_alerts[key] = now

        return AlertEvent(
            alert_type=alert_type,
            metric=pair.metric,
            asset_id=pair.asset_id,
            severity=severity,
            message=description,
            detected_at=now,
            suppressed=suppressed,
        )

    def _should_alert(
        self,
        severity: SeverityLevel,
        config: AlertConfig,
        key: str,
        now: datetime,
    ) -> bool:
        """Decide whether to voice an alert.

        Returns False (suppress) if severity is below threshold or
        the same pair was alerted within the cooldown window.
        """
        if not _severity_meets_threshold(severity, config.severity_threshold):
            return False
        last = self._last_alerts.get(key)
        return _cooldown_elapsed(last, config.cooldown_minutes, now)

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    @staticmethod
    def _anomaly_message(
        metric: CanonicalMetric,
        asset_id: str,
        result: object,
    ) -> str:
        """Build a concise voice message for an anomaly alert."""
        severity = getattr(result, "severity", "unknown")
        first = ""
        anomalies = getattr(result, "anomalies", [])
        if anomalies:
            first = getattr(anomalies[0], "description", "")
        base = (
            f"Attention: {metric.display_name} on {asset_id} "
            f"has a {severity} severity anomaly."
        )
        if first:
            return f"{base} {first}"
        return base

    @staticmethod
    def _drift_message(
        metric: CanonicalMetric,
        asset_id: str,
        result: object,
    ) -> str:
        """Build a concise voice message for a drift alert."""
        direction = getattr(result, "drift_direction", "unknown")
        rate = getattr(result, "drift_rate", 0.0)
        return (
            f"Attention: {metric.display_name} on {asset_id} "
            f"is {direction} at {abs(rate):.4f} per day. "
            f"Consider investigating."
        )
