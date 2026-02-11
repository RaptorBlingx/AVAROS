"""
KPI Progress Computation Helpers

Stateless functions for computing KPI improvement percentages
and building domain objects. Extracted from ``kpi_measurement.py``
to keep files under 300 lines.
"""

from __future__ import annotations

from datetime import datetime, timezone

from skill.domain.kpi_baseline import KPIBaseline, KPIProgress


# WASABI target percentages (from OC2 agreement, constant)
_WASABI_TARGETS: dict[str, tuple[float, str]] = {
    "energy_per_unit": (8.0, "reduction"),
    "material_efficiency": (5.0, "improvement"),
    "co2_per_unit": (10.0, "reduction"),
    "co2_total": (10.0, "reduction"),
}


def compute_improvement(
    baseline_value: float,
    current_value: float,
    direction: str,
) -> float:
    """Calculate improvement percentage.

    Args:
        baseline_value: Original baseline measurement.
        current_value: Latest measurement.
        direction: ``"reduction"`` or ``"improvement"``.

    Returns:
        Improvement percentage (positive = better).
    """
    if baseline_value == 0:
        return 0.0
    if direction == "reduction":
        return (baseline_value - current_value) / baseline_value * 100
    return (current_value - baseline_value) / baseline_value * 100


def resolve_target(metric: str) -> tuple[float, str]:
    """Look up WASABI target for a metric.

    Args:
        metric: Canonical metric name.

    Returns:
        ``(target_percent, direction)``. Falls back to
        ``(0.0, "reduction")`` for non-WASABI metrics.
    """
    return _WASABI_TARGETS.get(metric, (0.0, "reduction"))


def build_progress(
    baseline: KPIBaseline,
    current_value: float,
    current_unit: str,
) -> KPIProgress:
    """Build a KPIProgress from a baseline and current value.

    Args:
        baseline: Recorded KPI baseline.
        current_value: Latest measured value.
        current_unit: Unit of the current value.

    Returns:
        KPIProgress domain object.
    """
    target_pct, direction = resolve_target(baseline.metric)
    improvement = compute_improvement(
        baseline.baseline_value, current_value, direction,
    )
    return KPIProgress(
        metric=baseline.metric,
        site_id=baseline.site_id,
        baseline_value=baseline.baseline_value,
        current_value=current_value,
        target_percent=target_pct,
        improvement_percent=round(improvement, 2),
        target_met=improvement >= target_pct,
        unit=current_unit,
        baseline_date=baseline.recorded_at,
        current_date=datetime.now(timezone.utc),
        direction=direction,
    )


def baseline_to_export_row(
    baseline: KPIBaseline, *, site_label: str = "site_1",
) -> dict:
    """Convert a baseline to an anonymized export dict.

    Args:
        baseline: Domain KPI baseline.
        site_label: Anonymous site identifier for this export.

    Returns:
        Dict with site_id replaced by the anonymous label for D3.2.
    """
    return {
        "metric": baseline.metric,
        "site_id": site_label,
        "baseline_value": baseline.baseline_value,
        "unit": baseline.unit,
        "period_start": baseline.period_start.isoformat(),
        "period_end": baseline.period_end.isoformat(),
    }
