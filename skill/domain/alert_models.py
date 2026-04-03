"""
Proactive Alert Domain Models

Immutable data models for background anomaly/drift alert events
and user-configurable alert settings.

DEC-001: Platform-agnostic — no platform names.
DEC-004: All models use frozen=True.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from skill.domain.models import CanonicalMetric


AlertType = Literal["anomaly", "drift"]
SeverityLevel = Literal["none", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class MonitoredPair:
    """A metric + asset combination to monitor.

    Attributes:
        metric: Canonical metric to check.
        asset_id: Target asset identifier.
    """

    metric: CanonicalMetric
    asset_id: str


@dataclass(frozen=True)
class AlertEvent:
    """A single alert produced by a background check.

    Attributes:
        alert_type: Whether this is an anomaly or drift alert.
        metric: The canonical metric that triggered.
        asset_id: The asset that triggered.
        severity: Severity level from detection engine.
        message: Human-friendly voice message.
        detected_at: UTC timestamp of the detection.
        suppressed: True if cooldown prevented voicing this alert.
    """

    alert_type: AlertType
    metric: CanonicalMetric
    asset_id: str
    severity: SeverityLevel
    message: str
    detected_at: datetime
    suppressed: bool = False


@dataclass(frozen=True)
class AlertConfig:
    """User-configurable proactive monitoring settings.

    Attributes:
        enabled: Whether background checks are active.
        interval_seconds: Seconds between checks (default 4 h).
        severity_threshold: Minimum severity to voice (default medium).
        cooldown_minutes: Minutes before re-alerting same pair.
        monitored_pairs: Specific pairs to monitor; empty = all supported.
        z_score_threshold: Standard-deviation multiplier for anomaly
            detection sensitivity. Lower = more sensitive (more alerts),
            higher = less sensitive (fewer alerts). Default 2.0 flags the
            top ~4.6 % of readings; 3.0 (industry SPC standard) flags 0.3 %.
    """

    enabled: bool = True
    interval_seconds: int = 14400
    severity_threshold: SeverityLevel = "medium"
    cooldown_minutes: int = 60
    monitored_pairs: tuple[MonitoredPair, ...] = ()
    z_score_threshold: float = 2.0
