"""KPI Baseline Domain Models for WASABI validation.

Frozen dataclasses representing baselines, snapshots, and progress
toward WASABI KPI targets (≥8% electricity/unit, ≥5% material
efficiency, ≥10% CO₂-eq reduction).

DEC-004: All domain models use ``frozen=True``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class KPIBaseline:
    """Recorded KPI baseline for a pilot site.

    Attributes:
        metric: CanonicalMetric value (e.g. ``energy_per_unit``).
        site_id: Pilot site identifier (e.g. ``artibilim``, ``mext``).
        baseline_value: Measured baseline value.
        unit: Engineering unit (e.g. ``kWh/unit``).
        recorded_at: Timestamp when the baseline was recorded.
        period_start: Start of the measurement period.
        period_end: End of the measurement period.
        notes: Optional free-text notes.
    """

    metric: str
    site_id: str
    baseline_value: float
    unit: str
    recorded_at: datetime
    period_start: date
    period_end: date
    notes: str = ""


@dataclass(frozen=True)
class KPISnapshot:
    """Point-in-time KPI measurement for comparison.

    Attributes:
        metric: CanonicalMetric value.
        site_id: Pilot site identifier.
        value: Measured value at this point in time.
        unit: Engineering unit.
        measured_at: Timestamp of the measurement.
        period_start: Start of the measurement period.
        period_end: End of the measurement period.
    """

    metric: str
    site_id: str
    value: float
    unit: str
    measured_at: datetime
    period_start: date
    period_end: date


@dataclass(frozen=True)
class KPIProgress:
    """Progress toward a WASABI KPI target.

    Attributes:
        metric: CanonicalMetric value.
        site_id: Pilot site identifier.
        baseline_value: Original baseline measurement.
        current_value: Most recent measurement.
        target_percent: WASABI target improvement percentage.
        improvement_percent: Actual improvement achieved so far.
        target_met: Whether the target has been met.
        unit: Engineering unit.
        baseline_date: When the baseline was recorded.
        current_date: When the current value was measured.
        direction: ``"reduction"`` or ``"improvement"``.
    """

    metric: str
    site_id: str
    baseline_value: float
    current_value: float
    target_percent: float
    improvement_percent: float
    target_met: bool
    unit: str
    baseline_date: datetime
    current_date: datetime
    direction: str
