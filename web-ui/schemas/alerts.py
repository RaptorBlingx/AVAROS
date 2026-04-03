"""Request and response schemas for proactive alert configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MonitoredPairSchema(BaseModel):
    """A metric + asset pair to monitor."""

    metric: str = Field(..., description="Canonical metric name.")
    asset_id: str = Field(..., description="Asset identifier.")


class AlertConfigSchema(BaseModel):
    """Proactive monitoring settings."""

    enabled: bool = Field(True, description="Whether background checks are active.")
    interval_seconds: int = Field(
        14400, ge=60, le=86400,
        description="Seconds between checks (60–86400).",
    )
    severity_threshold: Literal["none", "low", "medium", "high", "critical"] = Field(
        "medium", description="Minimum severity to voice an alert.",
    )
    cooldown_minutes: int = Field(
        60, ge=1, le=1440,
        description="Minutes before re-alerting the same pair.",
    )
    monitored_pairs: list[MonitoredPairSchema] = Field(
        default_factory=list,
        description="Metric-asset pairs to monitor. Empty = auto-discover.",
    )
    z_score_threshold: float = Field(
        2.0, ge=1.0, le=5.0,
        description=(
            "Anomaly detection sensitivity threshold (standard deviations). "
            "Lower = more sensitive (more alerts). "
            "Higher = less sensitive (fewer, higher-confidence alerts). "
            "Industry SPC standard is 3.0; default 2.0 is more conservative."
        ),
    )
