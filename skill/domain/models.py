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
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Literal


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
            self.SCRAP_RATE: "%",
            self.REWORK_RATE: "%",
            self.MATERIAL_EFFICIENCY: "%",
            self.RECYCLED_CONTENT: "%",
            self.SUPPLIER_LEAD_TIME: "days",
            self.SUPPLIER_DEFECT_RATE: "%",
            self.SUPPLIER_ON_TIME: "%",
            self.OEE: "%",
            self.THROUGHPUT: "units/hr",
            self.CYCLE_TIME: "sec",
            self.CHANGEOVER_TIME: "min",
            self.CO2_PER_UNIT: "kg CO₂-eq/unit",
            self.CO2_TOTAL: "kg CO₂-eq",
            self.CO2_PER_BATCH: "kg CO₂-eq/batch",
        }
        return units.get(self, "")


_VALID_ASSET_TYPES = {"machine", "line", "sensor", "seu"}


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
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, display_name="today")
    
    @classmethod
    def this_week(cls) -> TimePeriod:
        """Create a period for the current week (Monday to now)."""
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, display_name="this week")
    
    @classmethod
    def last_week(cls) -> TimePeriod:
        """Create a period for the previous week."""
        now = datetime.now()
        end = now - timedelta(days=now.weekday())
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        return cls(start=start, end=end, display_name="last week")
    
    @classmethod
    def last_month(cls) -> TimePeriod:
        """Create a period for the last 30 days."""
        now = datetime.now()
        start = now - timedelta(days=30)
        return cls(start=start, end=now, display_name="last month")
    
    @classmethod
    def from_natural_language(cls, text: str) -> TimePeriod:
        """
        Parse natural language period description.
        
        Args:
            text: Natural language like "today", "last week", "past 3 months"
            
        Returns:
            Corresponding TimePeriod
        """
        normalized = text.lower().strip()
        
        mapping = {
            "today": cls.today,
            "this week": cls.this_week,
            "last week": cls.last_week,
            "past week": cls.last_week,
            "last month": cls.last_month,
            "past month": cls.last_month,
        }
        
        factory = mapping.get(normalized, cls.today)
        return factory()
    
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
        description: Human-readable description
    """
    
    timestamp: datetime
    metric: CanonicalMetric
    expected_value: float
    actual_value: float
    deviation: float
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
