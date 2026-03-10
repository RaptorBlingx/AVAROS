"""
Manufacturing-aware data profile definitions and time-series generators.

Generates realistic manufacturing data for 19 AVAROS canonical metrics
with shift patterns, weekend drops, gradual improvement trends, anomalies,
and cross-metric correlations.

This is a standalone tool — it does NOT import from skill/.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal


# =========================================================================
# Metric Profiles
# =========================================================================


@dataclass(frozen=True)
class MetricProfile:
    """Definition of a single metric's data generation parameters.

    Args:
        name: Canonical metric name.
        display_name: Human-readable name for Reneryo.
        baseline: Center value for normal operations.
        min_val: Minimum possible value.
        max_val: Maximum possible value.
        unit: Display unit string.
        better: Direction of improvement ("lower" or "higher").
        is_production: Metric tied to production activity (drops on weekends).
        is_energy: Energy-related metric (partial drop on weekends).
    """

    name: str
    display_name: str
    baseline: float
    min_val: float
    max_val: float
    unit: str
    better: Literal["lower", "higher"]
    is_production: bool = False
    is_energy: bool = False


METRIC_PROFILES: tuple[MetricProfile, ...] = (
    MetricProfile(
        "energy_per_unit", "AVAROS Energy Per Unit",
        2.5, 1.8, 3.5, "kWh/unit", "lower", is_energy=True,
    ),
    MetricProfile(
        "energy_total", "AVAROS Energy Total",
        15000, 10000, 22000, "kWh", "lower", is_energy=True,
    ),
    MetricProfile(
        "peak_demand", "AVAROS Peak Demand",
        450, 300, 650, "kW", "lower", is_energy=True,
    ),
    MetricProfile(
        "peak_tariff_exposure", "AVAROS Peak Tariff Exposure",
        12, 5, 25, "%", "lower", is_energy=True,
    ),
    MetricProfile(
        "scrap_rate", "AVAROS Scrap Rate",
        4.2, 1.5, 8.0, "%", "lower", is_production=True,
    ),
    MetricProfile(
        "rework_rate", "AVAROS Rework Rate",
        3.0, 1.0, 6.0, "%", "lower", is_production=True,
    ),
    MetricProfile(
        "material_efficiency", "AVAROS Material Efficiency",
        91.5, 85, 97, "%", "higher", is_production=True,
    ),
    MetricProfile(
        "recycled_content", "AVAROS Recycled Content",
        28, 15, 40, "%", "higher",
    ),
    MetricProfile(
        "oee", "AVAROS OEE",
        72, 55, 90, "%", "higher", is_production=True,
    ),
    MetricProfile(
        "throughput", "AVAROS Throughput",
        120, 80, 180, "units/hr", "higher", is_production=True,
    ),
    MetricProfile(
        "cycle_time", "AVAROS Cycle Time",
        30, 20, 50, "s/unit", "lower", is_production=True,
    ),
    MetricProfile(
        "changeover_time", "AVAROS Changeover Time",
        45, 15, 90, "min", "lower", is_production=True,
    ),
    MetricProfile(
        "co2_per_unit", "AVAROS CO2 Per Unit",
        1.8, 1.0, 3.0, "kg CO2-eq/unit", "lower", is_energy=True,
    ),
    MetricProfile(
        "co2_total", "AVAROS CO2 Total",
        12000, 8000, 18000, "kg CO2-eq", "lower", is_energy=True,
    ),
    MetricProfile(
        "co2_per_batch", "AVAROS CO2 Per Batch",
        85, 50, 150, "kg CO2-eq/batch", "lower", is_energy=True,
    ),
    MetricProfile(
        "supplier_lead_time", "AVAROS Supplier Lead Time",
        8, 3, 15, "days", "lower",
    ),
    MetricProfile(
        "supplier_defect_rate", "AVAROS Supplier Defect Rate",
        2.1, 0.5, 5.0, "%", "lower",
    ),
    MetricProfile(
        "supplier_on_time", "AVAROS Supplier On Time",
        88, 70, 98, "%", "higher",
    ),
    MetricProfile(
        "supplier_co2_per_kg", "AVAROS Supplier CO2 Per Kg",
        3.2, 1.5, 6.0, "kg CO2/kg", "lower",
    ),
)

PROFILE_BY_NAME: dict[str, MetricProfile] = {p.name: p for p in METRIC_PROFILES}

DEFAULT_ASSETS: tuple[str, ...] = ("Line-1", "Line-2", "Line-3")


# =========================================================================
# Asset personality offsets — each line is slightly different
# =========================================================================

_ASSET_OFFSETS: dict[str, float] = {
    "Line-1": 0.0,
    "Line-2": 0.05,
    "Line-3": -0.03,
}


# =========================================================================
# Pattern helpers
# =========================================================================


def is_weekend(dt: datetime) -> bool:
    """Check if a datetime falls on Saturday (5) or Sunday (6)."""
    return dt.weekday() >= 5


def shift_factor(dt: datetime) -> float:
    """Return multiplier based on shift.

    Day (06–14): 1.0, Evening (14–22): 0.95, Night (22–06): 0.85.
    """
    hour = dt.hour
    if 6 <= hour < 14:
        return 1.0
    if 14 <= hour < 22:
        return 0.95
    return 0.85


def improvement_factor(
    dt: datetime,
    start: datetime,
    better: Literal["lower", "higher"],
    monthly_rate: float = 0.005,
) -> float:
    """Gradual improvement factor over time (~0.5%/month).

    Args:
        dt: Current timestamp.
        start: Start of the time series.
        better: Improvement direction.
        monthly_rate: Per-month improvement rate.

    Returns:
        Multiplier for baseline value.
    """
    months = (dt - start).total_seconds() / (30.44 * 86400)
    delta = months * monthly_rate
    return (1.0 - delta) if better == "lower" else (1.0 + delta)


# =========================================================================
# Single-value generator
# =========================================================================


def generate_value(
    profile: MetricProfile,
    dt: datetime,
    start: datetime,
    asset: str,
    rng: random.Random,
    *,
    throughput_factor: float = 1.0,
    scrap_factor: float = 1.0,
    energy_per_unit_factor: float = 1.0,
) -> float:
    """Generate a single data point for a metric.

    Applies asset offset, shift pattern, weekend drop, gradual
    improvement, cross-metric correlations, random noise, and
    anomaly injection.

    Args:
        profile: Metric profile.
        dt: Timestamp for the data point.
        start: Start of time series (for improvement trend).
        asset: Asset identifier.
        rng: Seeded random instance.
        throughput_factor: Normalized throughput for correlation.
        scrap_factor: Normalized scrap rate for correlation.
        energy_per_unit_factor: Normalized energy_per_unit for correlation.

    Returns:
        Generated value, clamped to [min_val, max_val].
    """
    base = _apply_asset_offset(profile, asset)
    base = _apply_temporal_patterns(profile, base, dt, start)
    base = _apply_correlations(
        profile,
        base,
        throughput_factor,
        scrap_factor,
        energy_per_unit_factor,
    )
    base = _apply_noise_and_anomalies(profile, base, rng)

    # On weekends, production/energy values can drop below normal min
    weekend = is_weekend(dt)
    lower = 0.0 if weekend and (profile.is_production or profile.is_energy) else profile.min_val
    return max(lower, min(profile.max_val, round(base, 2)))


def _apply_asset_offset(profile: MetricProfile, asset: str) -> float:
    """Shift baseline by asset personality."""
    base = profile.baseline
    offset = _ASSET_OFFSETS.get(asset, 0.0)
    if profile.better == "lower":
        return base * (1.0 + offset)
    return base * (1.0 - offset)


def _apply_temporal_patterns(
    profile: MetricProfile,
    base: float,
    dt: datetime,
    start: datetime,
) -> float:
    """Apply weekend, shift, and improvement patterns."""
    weekend = is_weekend(dt)

    if weekend and profile.is_production:
        base *= 0.2
    elif weekend and profile.is_energy:
        base *= 0.4
    elif not weekend:
        base *= shift_factor(dt)

    return base * improvement_factor(dt, start, profile.better)


def _apply_correlations(
    profile: MetricProfile,
    base: float,
    throughput_factor: float,
    scrap_factor: float,
    energy_per_unit_factor: float,
) -> float:
    """Apply cross-metric correlations."""
    if profile.name == "energy_total":
        base *= throughput_factor
    elif profile.name == "material_efficiency":
        base *= 2.0 - scrap_factor
    elif profile.name == "co2_per_unit":
        base *= energy_per_unit_factor
    return base


def _apply_noise_and_anomalies(
    profile: MetricProfile,
    base: float,
    rng: random.Random,
) -> float:
    """Add gaussian noise and occasional anomaly spikes."""
    span = profile.max_val - profile.min_val
    noise = rng.gauss(0, span * 0.08)
    value = base + noise

    if rng.random() < 0.015:
        spike = span * 0.3 * rng.random() * rng.choice([-1, 1])
        value += spike

    return value


# =========================================================================
# Correlated time-series generator (all 19 metrics for one asset)
# =========================================================================


def generate_all_metrics(
    start: datetime,
    end: datetime,
    asset: str,
    seed: int = 42,
    interval_minutes: int = 15,
) -> dict[str, list[dict[str, float | str]]]:
    """Generate correlated time series for all 19 metrics for one asset.

    Throughput and scrap_rate are generated first to derive correlation
    factors used by dependent metrics (energy_total, material_efficiency,
    co2_per_unit).

    Args:
        start: Start datetime (inclusive, UTC).
        end: End datetime (exclusive, UTC).
        asset: Asset identifier (e.g. "Line-1").
        seed: Random seed for reproducibility.
        interval_minutes: Minutes between data points.

    Returns:
        Dict mapping metric_name → list of {value, datetime} dicts.
    """
    timestamps = _build_timestamps(start, end, interval_minutes)
    throughput_vals, scrap_vals, energy_per_unit_vals = _generate_reference_metrics(
        timestamps, start, asset, seed
    )
    throughput_baseline = PROFILE_BY_NAME["throughput"].baseline
    scrap_baseline = PROFILE_BY_NAME["scrap_rate"].baseline
    energy_per_unit_baseline = PROFILE_BY_NAME["energy_per_unit"].baseline

    result: dict[str, list[dict[str, float | str]]] = {}

    for profile in METRIC_PROFILES:
        if profile.name == "throughput":
            result[profile.name] = _to_points(timestamps, throughput_vals)
            continue
        if profile.name == "scrap_rate":
            result[profile.name] = _to_points(timestamps, scrap_vals)
            continue

        rng = random.Random(f"{profile.name}:{asset}:{seed}")
        values: list[float] = []
        for i, ts in enumerate(timestamps):
            val = generate_value(
                profile, ts, start, asset, rng,
                throughput_factor=throughput_vals[i] / throughput_baseline,
                scrap_factor=scrap_vals[i] / scrap_baseline,
                energy_per_unit_factor=(
                    energy_per_unit_vals[i] / energy_per_unit_baseline
                ),
            )
            values.append(val)
        result[profile.name] = _to_points(timestamps, values)

    return result


def generate_single_metric(
    profile: MetricProfile,
    dt: datetime,
    start: datetime,
    asset: str,
    seed: int = 42,
) -> dict[str, float | str]:
    """Generate one data point for daemon mode (no cross-correlations).

    Args:
        profile: Metric profile.
        dt: Current timestamp.
        start: Reference start for improvement trend.
        asset: Asset identifier.
        seed: Random seed.

    Returns:
        Single {value, datetime} dict.
    """
    rng = random.Random(f"{profile.name}:{asset}:{seed}:{dt.isoformat()}")
    val = generate_value(profile, dt, start, asset, rng)
    return {
        "value": val,
        "datetime": dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }


# =========================================================================
# Internal helpers
# =========================================================================


def _build_timestamps(
    start: datetime,
    end: datetime,
    interval_minutes: int,
) -> list[datetime]:
    """Build a list of evenly spaced timestamps."""
    interval = timedelta(minutes=interval_minutes)
    timestamps: list[datetime] = []
    current = start
    while current < end:
        timestamps.append(current)
        current += interval
    return timestamps


def _generate_reference_metrics(
    timestamps: list[datetime],
    start: datetime,
    asset: str,
    seed: int,
) -> tuple[list[float], list[float], list[float]]:
    """Generate reference metrics used by cross-correlation rules."""
    tp = PROFILE_BY_NAME["throughput"]
    sp = PROFILE_BY_NAME["scrap_rate"]
    eu = PROFILE_BY_NAME["energy_per_unit"]
    rng_tp = random.Random(f"throughput:{asset}:{seed}")
    rng_sp = random.Random(f"scrap_rate:{asset}:{seed}")
    rng_eu = random.Random(f"energy_per_unit:{asset}:{seed}")

    throughput_vals: list[float] = []
    scrap_vals: list[float] = []
    energy_per_unit_vals: list[float] = []
    for ts in timestamps:
        throughput_vals.append(
            generate_value(tp, ts, start, asset, rng_tp)
        )
        scrap_vals.append(
            generate_value(sp, ts, start, asset, rng_sp)
        )
        energy_per_unit_vals.append(
            generate_value(eu, ts, start, asset, rng_eu)
        )
    return throughput_vals, scrap_vals, energy_per_unit_vals


def _to_points(
    timestamps: list[datetime],
    values: list[float],
) -> list[dict[str, float | str]]:
    """Zip timestamps + values into API-compatible dicts."""
    return [
        {
            "value": v,
            "datetime": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        for ts, v in zip(timestamps, values)
    ]
