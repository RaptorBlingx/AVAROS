"""
Deterministic data generators for the mock RENERYO server.

Uses seed-based random for reproducible responses. Value ranges
match MockAdapter's baselines so integration tests are consistent.

This module is independent of the skill codebase — it does NOT
import anything from skill/.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any


# =========================================================================
# Metric Configuration (mirrors MockAdapter._METRIC_BASELINES)
# =========================================================================

# Maps canonical metric name → (baseline, variation, unit)
METRIC_CONFIG: dict[str, tuple[float, float, str]] = {
    "energy_per_unit": (2.8, 0.5, "kWh/unit"),
    "energy_total": (15000.0, 2000.0, "kWh"),
    "peak_demand": (850.0, 100.0, "kW"),
    "peak_tariff_exposure": (12.5, 3.0, "%"),
    "scrap_rate": (2.5, 1.0, "%"),
    "rework_rate": (1.8, 0.8, "%"),
    "material_efficiency": (94.5, 2.0, "%"),
    "recycled_content": (35.0, 10.0, "%"),
    "supplier_lead_time": (5.2, 1.5, "days"),
    "supplier_defect_rate": (0.8, 0.3, "%"),
    "supplier_on_time": (92.0, 5.0, "%"),
    "supplier_co2_per_kg": (2.1, 0.4, "kg CO₂/kg"),
    "oee": (82.5, 5.0, "%"),
    "throughput": (120.0, 15.0, "units/hr"),
    "cycle_time": (45.0, 5.0, "sec"),
    "changeover_time": (25.0, 8.0, "min"),
    "co2_per_unit": (0.85, 0.15, "kg CO₂-eq/unit"),
    "co2_total": (4500.0, 800.0, "kg CO₂-eq"),
    "co2_per_batch": (42.0, 8.0, "kg CO₂-eq/batch"),
}

# Default demo assets
DEFAULT_ASSETS = ["Line-1", "Line-2", "Line-3"]

# Reneryo native measurement types per metric
_RENERYO_TYPE_MAP: dict[str, str] = {
    "energy_per_unit": "energy_consumption",
    "energy_total": "energy_total",
    "peak_demand": "power_demand",
    "peak_tariff_exposure": "tariff_exposure",
    "scrap_rate": "scrap_measurement",
    "rework_rate": "rework_measurement",
    "material_efficiency": "material_efficiency",
    "recycled_content": "recycled_content",
    "supplier_lead_time": "lead_time",
    "supplier_defect_rate": "defect_rate",
    "supplier_on_time": "on_time_delivery",
    "supplier_co2_per_kg": "supplier_carbon",
    "oee": "overall_equipment_effectiveness",
    "throughput": "throughput",
    "cycle_time": "cycle_time",
    "changeover_time": "changeover_time",
    "co2_per_unit": "carbon_per_unit",
    "co2_total": "carbon_total",
    "co2_per_batch": "carbon_per_batch",
}


def _make_rng(seed: int = 42, extra: str = "") -> random.Random:
    """Create a seeded Random instance for deterministic output."""
    combined = seed + hash(extra) % (10**6)
    return random.Random(combined)


def generate_single_value(
    metric_name: str,
    asset_id: str = "Line-1",
    period: str = "today",
    seed: int = 42,
) -> dict[str, Any]:
    """
    Generate a single KPI data point in AVAROS canonical format.

    Args:
        metric_name: Canonical metric name (e.g. 'energy_per_unit').
        asset_id: Asset identifier.
        period: Time period label.
        seed: Random seed for reproducibility.

    Returns:
        Dict with metric_name, value, unit, timestamp, asset_id, period, metadata.
    """
    baseline, variation, unit = METRIC_CONFIG.get(
        metric_name, (50.0, 10.0, "units")
    )
    rng = _make_rng(seed, f"{metric_name}:{asset_id}:{period}")

    asset_offset = (hash(asset_id) % 100) / 100.0
    value = baseline + (asset_offset - 0.5) * variation * 2
    value += rng.uniform(-variation * 0.1, variation * 0.1)
    value = round(value, 2)

    return {
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "asset_id": asset_id,
        "period": period,
        "metadata": {
            "source": "reneryo-mock",
            "confidence": 0.95,
        },
    }


def generate_trend_data(
    metric_name: str,
    asset_id: str = "Line-1",
    granularity: str = "daily",
    period: str = "last_7_days",
    datetime_min: str | None = None,
    datetime_max: str | None = None,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Generate an array of time-series data points for trend endpoints.

    Args:
        metric_name: Canonical metric name.
        asset_id: Asset identifier.
        granularity: 'hourly', 'daily', or 'weekly'.
        period: Time period label.
        datetime_min: ISO start (optional).
        datetime_max: ISO end (optional).
        seed: Random seed for reproducibility.

    Returns:
        List of dicts, each with value, unit, timestamp, asset_id.
    """
    baseline, variation, unit = METRIC_CONFIG.get(
        metric_name, (50.0, 10.0, "units")
    )
    rng = _make_rng(seed, f"trend:{metric_name}:{asset_id}:{granularity}")

    hours_per_point = {"hourly": 1, "daily": 24, "weekly": 168}.get(
        granularity, 24
    )
    num_points = _resolve_num_points(
        granularity, datetime_min, datetime_max
    )
    start = _resolve_start(datetime_min, hours_per_point, num_points)

    current = baseline + rng.uniform(-variation * 0.3, variation * 0.3)
    trend_bias = rng.uniform(-0.02, 0.02)
    points: list[dict[str, Any]] = []

    for i in range(num_points):
        ts = start + timedelta(hours=i * hours_per_point)
        change = rng.uniform(-variation * 0.1, variation * 0.1)
        change += trend_bias * baseline * 0.01
        current += change
        current = max(
            baseline - variation,
            min(baseline + variation, current),
        )
        points.append({
            "metric_name": metric_name,
            "value": round(current, 2),
            "unit": unit,
            "timestamp": ts.isoformat(),
            "asset_id": asset_id,
            "period": period,
            "metadata": {
                "source": "reneryo-mock",
                "confidence": 0.95,
            },
        })

    return points


def generate_comparison_data(
    metric_name: str,
    asset_ids: list[str],
    period: str = "today",
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Generate per-asset comparison values.

    Args:
        metric_name: Canonical metric name.
        asset_ids: List of asset identifiers.
        period: Time period label.
        seed: Random seed.

    Returns:
        List of dicts, one per asset.
    """
    return [
        generate_single_value(metric_name, aid, period, seed)
        for aid in asset_ids
    ]


def generate_native_measurement(
    metric_name: str,
    asset_id: str = "Line-1",
    datetime_min: str | None = None,
    datetime_max: str | None = None,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Generate data in Reneryo's native measurement format.

    This simulates the real Reneryo /api/u/measurement/meter/item endpoint
    so the response-parsing layer can be tested independently.

    Args:
        metric_name: Canonical metric name.
        asset_id: Asset / meter identifier.
        datetime_min: ISO start (optional).
        datetime_max: ISO end (optional).
        seed: Random seed.

    Returns:
        List of native-format measurement dicts.
    """
    baseline, variation, unit = METRIC_CONFIG.get(
        metric_name, (50.0, 10.0, "units")
    )
    # Strip compound unit to base (e.g. 'kWh/unit' → 'kWh')
    base_unit = unit.split("/")[0].strip()
    rng = _make_rng(seed, f"native:{metric_name}:{asset_id}")

    num_points = 24  # Hourly for one day
    start = _resolve_start(datetime_min, 1, num_points)
    measurement_type = _RENERYO_TYPE_MAP.get(metric_name, "unknown")

    measurements: list[dict[str, Any]] = []
    current = baseline + rng.uniform(-variation * 0.3, variation * 0.3)

    for i in range(num_points):
        ts = start + timedelta(hours=i)
        change = rng.uniform(-variation * 0.1, variation * 0.1)
        current += change
        current = max(
            baseline - variation,
            min(baseline + variation, current),
        )
        measurements.append({
            "id": f"{rng.randint(100000, 999999):06x}",
            "meter": asset_id,
            "value": round(current, 2),
            "unit": base_unit,
            "datetime": ts.isoformat(),
            "type": measurement_type,
        })

    return measurements


# =========================================================================
# Helpers
# =========================================================================

def _resolve_num_points(
    granularity: str,
    datetime_min: str | None,
    datetime_max: str | None,
) -> int:
    """Determine how many data points to generate."""
    if datetime_min and datetime_max:
        try:
            dt_min = datetime.fromisoformat(datetime_min)
            dt_max = datetime.fromisoformat(datetime_max)
            hours = max(1, int((dt_max - dt_min).total_seconds() / 3600))
            divisor = {"hourly": 1, "daily": 24, "weekly": 168}.get(
                granularity, 24
            )
            return max(3, min(60, hours // divisor))
        except (ValueError, TypeError):
            pass
    defaults = {"hourly": 24, "daily": 7, "weekly": 4}
    return defaults.get(granularity, 7)


def _resolve_start(
    datetime_min: str | None,
    hours_per_point: int,
    num_points: int,
) -> datetime:
    """Resolve the start timestamp for generated data."""
    if datetime_min:
        try:
            return datetime.fromisoformat(datetime_min)
        except (ValueError, TypeError):
            pass
    return datetime.now(tz=timezone.utc) - timedelta(
        hours=hours_per_point * num_points
    )
