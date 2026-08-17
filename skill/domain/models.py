"""
Canonical Manufacturing Domain Models

These models define the universal manufacturing concepts that AVAROS understands.
They are platform-agnostic and immutable (frozen dataclasses).

Usage:
    All adapters must convert platform-specific responses INTO these types.
    Intent handlers work ONLY with these canonical types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import calendar
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class CanonicalMetric(Enum):
    """
    Universal manufacturing metrics that AVAROS understands.
    
    These are the "language" of AVAROS. Platform adapters map their
    specific metric names to these canonical values.
    
    Categories:
        - Energy: Power consumption and efficiency
        - Material: Waste and efficiency tracking
        - Supplier: Supply chain performance
        - Production: Manufacturing performance
        - Carbon: Environmental impact
    """
    
    # Energy Metrics
    ENERGY_PER_UNIT = "energy_per_unit"       # kWh per unit produced
    ENERGY_TOTAL = "energy_total"             # Total kWh consumed
    PEAK_DEMAND = "peak_demand"               # Maximum power draw (kW)
    PEAK_TARIFF_EXPOSURE = "peak_tariff_exposure"  # Cost exposure to peak rates
    CONSUMPTION_POWER = "consumption_power"   # Instantaneous electrical consumption
    PRODUCTION_POWER = "production_power"     # Instantaneous electrical production
    ENERGY_PRODUCTION_TOTAL = "energy_production_total"  # Accumulated generated energy
    GRID_POWER = "grid_power"                 # Instantaneous grid import/export power
    ENERGY_GRID_IMPORT_TOTAL = "energy_grid_import_total"  # Accumulated grid import
    ENERGY_GRID_EXPORT_TOTAL = "energy_grid_export_total"  # Accumulated grid export
    STORAGE_STATE_OF_CHARGE = "storage_state_of_charge"  # Battery state of charge
    STORAGE_POWER = "storage_power"           # Battery charge/discharge power
    
    # Material Metrics
    SCRAP_RATE = "scrap_rate"                 # % of material scrapped
    REWORK_RATE = "rework_rate"               # % requiring rework
    MATERIAL_EFFICIENCY = "material_efficiency"  # % of input that becomes output
    RECYCLED_CONTENT = "recycled_content"     # % of recycled material used
    
    # Supplier Metrics
    SUPPLIER_LEAD_TIME = "supplier_lead_time"     # Days from order to delivery
    SUPPLIER_DEFECT_RATE = "supplier_defect_rate" # % defective from supplier
    SUPPLIER_ON_TIME = "supplier_on_time"         # % of on-time deliveries
    SUPPLIER_CO2_PER_KG = "supplier_co2_per_kg"   # CO2 per kg of material
    
    # Production Metrics
    OEE = "oee"                               # Overall Equipment Effectiveness %
    THROUGHPUT = "throughput"                 # Units per hour
    CYCLE_TIME = "cycle_time"                 # Seconds per unit
    CHANGEOVER_TIME = "changeover_time"       # Minutes for product changeover
    
    # Carbon Metrics
    CO2_PER_UNIT = "co2_per_unit"             # kg CO2-eq per unit
    CO2_TOTAL = "co2_total"                   # Total kg CO2-eq
    CO2_PER_BATCH = "co2_per_batch"           # kg CO2-eq per batch
    
    @classmethod
    def from_string(cls, value: str) -> CanonicalMetric:
        """
        Parse a string into a CanonicalMetric, supporting common aliases.
        
        Args:
            value: Metric name or alias (case-insensitive)
            
        Returns:
            Matching CanonicalMetric
            
        Raises:
            ValueError: If no matching metric found
        """
        # Normalize input
        normalized = value.lower().strip().replace(" ", "_").replace("-", "_")
        
        # Try direct enum match
        for metric in cls:
            if metric.value == normalized:
                return metric
        
        # Common aliases
        aliases = {
            "energy": cls.ENERGY_PER_UNIT,
            "power": cls.ENERGY_PER_UNIT,
            "electricity": cls.ENERGY_PER_UNIT,
            "scrap": cls.SCRAP_RATE,
            "waste": cls.SCRAP_RATE,
            "efficiency": cls.MATERIAL_EFFICIENCY,
            "oee": cls.OEE,
            "overall_equipment_effectiveness": cls.OEE,
            "carbon": cls.CO2_PER_UNIT,
            "co2": cls.CO2_PER_UNIT,
            "emissions": cls.CO2_PER_UNIT,
            "lead_time": cls.SUPPLIER_LEAD_TIME,
        }
        
        if normalized in aliases:
            return aliases[normalized]
        
        raise ValueError(f"Unknown metric: {value}")
    
    @property
    def display_name(self) -> str:
        """Human-readable name for voice responses."""
        names = {
            self.ENERGY_PER_UNIT: "energy per unit",
            self.ENERGY_TOTAL: "total energy",
            self.PEAK_DEMAND: "peak demand",
            self.CONSUMPTION_POWER: "consumption power",
            self.PRODUCTION_POWER: "production power",
            self.ENERGY_PRODUCTION_TOTAL: "total production energy",
            self.GRID_POWER: "grid power",
            self.ENERGY_GRID_IMPORT_TOTAL: "total grid import energy",
            self.ENERGY_GRID_EXPORT_TOTAL: "total grid export energy",
            self.STORAGE_STATE_OF_CHARGE: "battery state of charge",
            self.STORAGE_POWER: "battery power",
            self.SCRAP_RATE: "scrap rate",
            self.REWORK_RATE: "rework rate",
            self.MATERIAL_EFFICIENCY: "material efficiency",
            self.OEE: "overall equipment effectiveness",
            self.THROUGHPUT: "throughput",
            self.CYCLE_TIME: "cycle time",
            self.CO2_PER_UNIT: "carbon per unit",
            self.CO2_TOTAL: "total carbon emissions",
        }
        return names.get(self, self.value.replace("_", " "))
    
    @property
    def default_unit(self) -> str:
        """Default unit of measurement for this metric."""
        units = {
            self.ENERGY_PER_UNIT: "kWh/unit",
            self.ENERGY_TOTAL: "kWh",
            self.PEAK_DEMAND: "kW",
            self.CONSUMPTION_POWER: "W",
            self.PRODUCTION_POWER: "W",
            self.ENERGY_PRODUCTION_TOTAL: "Wh",
            self.GRID_POWER: "W",
            self.ENERGY_GRID_IMPORT_TOTAL: "Wh",
            self.ENERGY_GRID_EXPORT_TOTAL: "Wh",
            self.STORAGE_STATE_OF_CHARGE: "%",
            self.STORAGE_POWER: "W",
            self.PEAK_TARIFF_EXPOSURE: "%",
            self.SCRAP_RATE: "%",
            self.REWORK_RATE: "%",
            self.MATERIAL_EFFICIENCY: "%",
            self.RECYCLED_CONTENT: "%",
            self.SUPPLIER_LEAD_TIME: "days",
            self.SUPPLIER_DEFECT_RATE: "%",
            self.SUPPLIER_ON_TIME: "%",
            self.SUPPLIER_CO2_PER_KG: "kg CO₂/kg",
            self.OEE: "%",
            self.THROUGHPUT: "units/hr",
            self.CYCLE_TIME: "sec",
            self.CHANGEOVER_TIME: "min",
            self.CO2_PER_UNIT: "kg CO₂-eq/unit",
            self.CO2_TOTAL: "kg CO₂-eq",
            self.CO2_PER_BATCH: "kg CO₂-eq/batch",
        }
        return units.get(self, "")


_VALID_ASSET_TYPES = {"machine", "line", "sensor", "seu", "supplier", "group"}


@dataclass(frozen=True)
class Asset:
    """Immutable platform-agnostic asset descriptor."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate asset identity and type."""
        if not self.asset_id.strip():
            raise ValueError("asset_id must be non-empty")
        if self.asset_type not in _VALID_ASSET_TYPES:
            valid_types = ", ".join(sorted(_VALID_ASSET_TYPES))
            raise ValueError(
                f"Invalid asset_type '{self.asset_type}'. Must be one of: {valid_types}",
            )


@dataclass(frozen=True)
class TimePeriod:
    """
    Immutable value object representing a time range for queries.
    
    Attributes:
        start: Beginning of the period
        end: End of the period (inclusive)
        display_name: Human-readable name (e.g., "today", "last week")
    """
    
    start: datetime
    end: datetime
    display_name: str = ""
    
    def __post_init__(self):
        """Validate period."""
        if self.start > self.end:
            raise ValueError(f"Start ({self.start}) must be before end ({self.end})")
    
    @classmethod
    def today(cls) -> TimePeriod:
        """Create a period for today."""
        now = datetime.now(tz=timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, display_name="today")

    @classmethod
    def yesterday(cls) -> TimePeriod:
        """Create a period for the previous calendar day."""
        today_start = datetime.now(tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        start = today_start - timedelta(days=1)
        return cls(start=start, end=today_start, display_name="yesterday")
    
    @classmethod
    def this_week(cls) -> TimePeriod:
        """Create a period for the current week (Monday to now)."""
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, display_name="this week")

    @classmethod
    def this_month(cls) -> TimePeriod:
        """Create a period for the current month."""
        now = datetime.now(tz=timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, display_name="this month")
    
    @classmethod
    def last_week(cls) -> TimePeriod:
        """Create a period for the previous week."""
        now = datetime.now(tz=timezone.utc)
        end = now - timedelta(days=now.weekday())
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        return cls(start=start, end=end, display_name="last week")

    @classmethod
    def last_two_weeks(cls) -> TimePeriod:
        """Create a period for the last 14 days."""
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=14)
        return cls(start=start, end=now, display_name="last 2 weeks")
    
    @classmethod
    def last_month(
        cls,
        *,
        now: datetime | None = None,
        timezone_name: str = "UTC",
    ) -> TimePeriod:
        """Create the previous calendar month in the configured site timezone."""
        tz = cls._resolve_timezone(timezone_name)
        local_now = (now or datetime.now(tz=tz)).astimezone(tz)
        this_month = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_day = this_month - timedelta(days=1)
        start = previous_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls(
            start=start.astimezone(timezone.utc),
            end=this_month.astimezone(timezone.utc),
            display_name="last month",
        )

    @classmethod
    def rolling_days(cls, days: int, *, now: datetime | None = None) -> TimePeriod:
        """Create a rolling period ending now."""
        if days <= 0:
            raise ValueError("Rolling period must contain at least one day")
        end = now or datetime.now(tz=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return cls(
            start=end - timedelta(days=days),
            end=end,
            display_name=f"past {days} days",
        )

    @classmethod
    def latest(cls) -> TimePeriod:
        """Create the bounded lookup window used for latest-observation queries."""
        return cls(
            start=datetime(2021, 2, 1, tzinfo=timezone.utc),
            end=datetime.now(tz=timezone.utc),
            display_name="latest available",
        )

    @classmethod
    def wide_default(cls) -> TimePeriod:
        """Backward-compatible alias for an explicit latest-observation lookup."""
        return cls.latest()
    
    @classmethod
    def from_natural_language(
        cls,
        text: str,
        *,
        timezone_name: str = "UTC",
        now: datetime | None = None,
    ) -> TimePeriod:
        """
        Parse natural language period description.
        
        Args:
            text: Natural language like "today", "last week", "past 3 months"
            
        Returns:
            Corresponding TimePeriod
        """
        normalized = re.sub(r"\s+", " ", text.lower().strip())
        if not normalized:
            raise ValueError("Time period cannot be empty")
        
        mapping = {
            "today": cls.today,
            "yesterday": cls.yesterday,
            "this week": cls.this_week,
            "this month": cls.this_month,
            "last week": cls.last_week,
            "past week": cls.last_week,
            "last 2 weeks": cls.last_two_weeks,
            "last two weeks": cls.last_two_weeks,
            "last month": lambda: cls.last_month(
                now=now,
                timezone_name=timezone_name,
            ),
            "past month": lambda: cls.rolling_days(30, now=now),
            "past 30 days": lambda: cls.rolling_days(30, now=now),
            "last 30 days": lambda: cls.rolling_days(30, now=now),
            "latest": cls.latest,
            "current": cls.latest,
            "right now": cls.latest,
        }

        factory = mapping.get(normalized)
        if factory is not None:
            return factory()

        named_month = re.fullmatch(
            r"(" + "|".join(month.lower() for month in calendar.month_name[1:]) + r")\s+(\d{4})",
            normalized,
        )
        if named_month:
            month_name, year_text = named_month.groups()
            month = list(calendar.month_name).index(month_name.title())
            return cls._calendar_month(
                year=int(year_text),
                month=month,
                timezone_name=timezone_name,
                now=now,
            )

        iso_range = re.fullmatch(
            r"(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(\d{4}-\d{2}-\d{2})",
            normalized,
        )
        if iso_range:
            return cls._explicit_date_range(
                iso_range.group(1),
                iso_range.group(2),
                timezone_name=timezone_name,
                now=now,
            )

        raise ValueError(
            "Unsupported time period. Try today, yesterday, last week, "
            "last month, past 30 days, a named month such as July 2026, "
            "or an ISO range such as 2026-07-01 to 2026-07-31."
        )

    @staticmethod
    def _resolve_timezone(timezone_name: str):
        """Resolve an IANA site timezone with a clear validation error."""
        try:
            return ZoneInfo(timezone_name or "UTC")
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown site timezone: {timezone_name}") from exc

    @classmethod
    def _calendar_month(
        cls,
        *,
        year: int,
        month: int,
        timezone_name: str,
        now: datetime | None,
    ) -> TimePeriod:
        tz = cls._resolve_timezone(timezone_name)
        start = datetime(year, month, 1, tzinfo=tz)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=tz)
        else:
            end = datetime(year, month + 1, 1, tzinfo=tz)
        cls._reject_future(start, now=now, tz=tz)
        return cls(
            start=start.astimezone(timezone.utc),
            end=end.astimezone(timezone.utc),
            display_name=f"{calendar.month_name[month]} {year}",
        )

    @classmethod
    def _explicit_date_range(
        cls,
        start_text: str,
        end_text: str,
        *,
        timezone_name: str,
        now: datetime | None,
    ) -> TimePeriod:
        tz = cls._resolve_timezone(timezone_name)
        start = datetime.fromisoformat(start_text).replace(tzinfo=tz)
        end_day = datetime.fromisoformat(end_text).replace(tzinfo=tz)
        cls._reject_future(start, now=now, tz=tz)
        cls._reject_future(end_day, now=now, tz=tz)
        end = end_day + timedelta(days=1)
        return cls(
            start=start.astimezone(timezone.utc),
            end=end.astimezone(timezone.utc),
            display_name=f"{start_text} to {end_text}",
        )

    @staticmethod
    def _reject_future(value: datetime, *, now: datetime | None, tz) -> None:
        reference = now or datetime.now(tz=tz)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=tz)
        if value.date() > reference.astimezone(tz).date():
            raise ValueError("Future time periods are not available")
    
    @property
    def duration_days(self) -> float:
        """Duration of the period in days."""
        return (self.end - self.start).total_seconds() / 86400


@dataclass(frozen=True)
class DataPoint:
    """
    Single data point in a time series.
    
    Attributes:
        timestamp: When this measurement was taken
        value: The measured value
        unit: Unit of measurement
    """
    
    timestamp: datetime
    value: float
    unit: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ScenarioParameter:
    """
    A single parameter change in a what-if scenario.
    
    Attributes:
        name: Parameter name (e.g., "temperature", "speed")
        baseline_value: Current value
        proposed_value: Simulated value
        unit: Unit of measurement
    """
    
    name: str
    baseline_value: float
    proposed_value: float
    unit: str = ""
    
    @property
    def delta(self) -> float:
        """Change from baseline to proposed."""
        return self.proposed_value - self.baseline_value
    
    @property
    def delta_percent(self) -> float:
        """Percentage change from baseline."""
        if self.baseline_value == 0:
            return 0.0
        return (self.delta / self.baseline_value) * 100


@dataclass(frozen=True)
class WhatIfScenario:
    """
    Definition of a what-if simulation scenario.
    
    Attributes:
        name: Scenario identifier
        asset_id: Target asset/machine
        parameters: List of parameter changes to simulate
        target_metric: The metric to predict impact on
    """
    
    name: str
    asset_id: str
    parameters: tuple[ScenarioParameter, ...]
    target_metric: CanonicalMetric
    
    def __init__(
        self,
        name: str,
        asset_id: str,
        parameters: list[ScenarioParameter] | tuple[ScenarioParameter, ...],
        target_metric: CanonicalMetric,
    ):
        """Initialize with parameter list converted to tuple for immutability."""
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "parameters", tuple(parameters))
        object.__setattr__(self, "target_metric", target_metric)


@dataclass(frozen=True)
class Anomaly:
    """
    Detected anomaly in manufacturing data.
    
    Attributes:
        timestamp: When the anomaly occurred
        metric: Which metric showed the anomaly
        expected_value: What was expected
        actual_value: What was observed
        deviation: Standard deviations from expected
        anomaly_type: Direction of anomaly ("spike", "dip", or "")
        description: Human-readable description
    """
    
    timestamp: datetime
    metric: CanonicalMetric
    expected_value: float
    actual_value: float
    deviation: float
    anomaly_type: str = ""
    description: str = ""
    
    @property
    def severity(self) -> Literal["low", "medium", "high", "critical"]:
        """Categorize severity based on deviation magnitude."""
        abs_dev = abs(self.deviation)
        if abs_dev < 2:
            return "low"
        elif abs_dev < 3:
            return "medium"
        elif abs_dev < 4:
            return "high"
        return "critical"


# Emission factor models extracted to emission_factors.py (file-size compliance).
# Re-exported here for backward compatibility.
from skill.domain.emission_factors import (  # noqa: F401, E402
    DEFAULT_EMISSION_FACTORS,
    EmissionFactor,
)
