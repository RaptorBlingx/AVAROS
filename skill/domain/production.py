"""
Production Domain Models

Platform-agnostic domain models for supplementary manufacturing data
(production counts, material consumption, quality data).

These models enable the 3 WASABI KPI calculations:
    - energy_per_unit = energy_total / production_count
    - material_efficiency = good_produced / material_consumed × 100
    - co2_per_unit = (energy × emission_factor) / production_count
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProductionRecord:
    """Single production data point — shift, day, or batch.

    Platform-agnostic (DEC-001). Any factory can report this data
    regardless of MES/ERP system.

    Attributes:
        record_date: Day this entry covers.
        asset_id: Machine/line identifier (e.g. "Line-1").
        production_count: Total units produced.
        good_count: Units passing QC (≤ production_count).
        material_consumed_kg: Raw material input in kg.
        shift: Optional shift label ("morning", "afternoon", "night").
        batch_id: Optional batch reference.
        notes: Operator notes.
    """

    record_date: date
    asset_id: str
    production_count: int
    good_count: int
    material_consumed_kg: float
    shift: str = ""
    batch_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate business rules on construction."""
        _validate_non_negative(self.production_count, "production_count")
        _validate_non_negative(self.good_count, "good_count")
        _validate_non_negative_float(
            self.material_consumed_kg, "material_consumed_kg",
        )
        _validate_good_count(self.good_count, self.production_count)
        _validate_date_not_future(self.record_date)


@dataclass(frozen=True)
class ProductionSummary:
    """Aggregated production data for a time period.

    Attributes:
        total_produced: Sum of production_count across records.
        total_good: Sum of good_count across records.
        total_material_kg: Sum of material_consumed_kg.
        record_count: Number of records aggregated.
    """

    total_produced: int
    total_good: int
    total_material_kg: float
    record_count: int

    @property
    def material_efficiency(self) -> float:
        """Material efficiency percentage.

        Returns:
            ``(total_good / total_produced) × 100`` if total_produced > 0,
            else 0.0.
        """
        if self.total_produced <= 0:
            return 0.0
        return round((self.total_good / self.total_produced) * 100, 1)


# ── Validation helpers (module-level, stateless) ───────────


def _validate_non_negative(value: int, field: str) -> None:
    """Raise ValueError if value < 0."""
    if value < 0:
        raise ValueError(f"{field} must be >= 0, got {value}")


def _validate_non_negative_float(value: float, field: str) -> None:
    """Raise ValueError if value < 0."""
    if value < 0:
        raise ValueError(f"{field} must be >= 0, got {value}")


def _validate_good_count(good: int, total: int) -> None:
    """Raise ValueError if good > total."""
    if good > total:
        raise ValueError(
            f"good_count ({good}) cannot exceed "
            f"production_count ({total})",
        )


def _validate_date_not_future(record_date: date) -> None:
    """Raise ValueError if date is in the future."""
    if record_date > date.today():
        raise ValueError(
            f"record_date cannot be in the future: {record_date}",
        )
