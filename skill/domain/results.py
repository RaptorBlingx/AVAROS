"""
Query Result Types - Canonical Response Models

Each of the 5 query types returns a specific result type.
These are immutable dataclasses that adapters must produce.

Result Types:
    - KPIResult: Single metric value (get_kpi)
    - ComparisonResult: Multiple assets compared (compare)
    - TrendResult: Time series with trend analysis (get_trend)
    - AnomalyResult: Anomaly detection output (check_anomaly)
    - WhatIfResult: Simulation prediction (simulate_whatif)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
    Anomaly,
)


@dataclass(frozen=True)
class KPIResult:
    """
    Result from a get_kpi() query.
    
    Represents a single KPI measurement for a specific asset and period.
    This is the most common query result type.
    
    Attributes:
        metric: Which canonical metric this measures
        value: The numeric value
        unit: Unit of measurement (e.g., "kWh/unit", "%")
        asset_id: The asset this measurement is for
        period: The time period of the measurement
        timestamp: When this value was computed/retrieved
        recommendation_id: For audit trail (GDPR compliance)
    
    Example:
        KPIResult(
            metric=CanonicalMetric.OEE,
            value=82.5,
            unit="%",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=datetime.now()
        )
    """
    
    metric: CanonicalMetric
    value: float
    unit: str
    asset_id: str
    period: TimePeriod
    timestamp: datetime
    recommendation_id: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "metric": self.metric.value,
            "value": self.value,
            "unit": self.unit,
            "asset_id": self.asset_id,
            "period_start": self.period.start.isoformat(),
            "period_end": self.period.end.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "recommendation_id": self.recommendation_id,
        }
    
    @property
    def formatted_value(self) -> str:
        """Human-readable formatted value with unit."""
        if self.unit == "%":
            return f"{self.value:.1f}%"
        return f"{self.value:.2f} {self.unit}"


@dataclass(frozen=True)
class ComparisonItem:
    """
    Single item in a comparison result.
    
    Attributes:
        asset_id: Asset identifier
        value: Metric value for this asset
        rank: Position in comparison (1 = best)
    """
    
    asset_id: str
    value: float
    rank: int


@dataclass(frozen=True)
class ComparisonResult:
    """
    Result from a compare() query.
    
    Compares a metric across multiple assets and identifies the best performer.
    
    Attributes:
        metric: Which metric was compared
        items: List of assets with their values and ranks
        winner_id: Asset with the best performance
        difference: Difference between best and worst
        unit: Unit of measurement
        period: Time period of comparison
        recommendation_id: For audit trail
    
    Example:
        ComparisonResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            items=[
                ComparisonItem("Compressor-1", 2.3, 1),
                ComparisonItem("Compressor-2", 2.8, 2)
            ],
            winner_id="Compressor-1",
            difference=0.5,
            unit="kWh/unit"
        )
    """
    
    metric: CanonicalMetric
    items: tuple[ComparisonItem, ...]
    winner_id: str
    difference: float
    unit: str
    period: TimePeriod
    recommendation_id: str = ""
    
    def __init__(
        self,
        metric: CanonicalMetric,
        items: list[ComparisonItem] | tuple[ComparisonItem, ...],
        winner_id: str,
        difference: float,
        unit: str,
        period: TimePeriod,
        recommendation_id: str = "",
    ):
        """Initialize with items converted to tuple for immutability."""
        object.__setattr__(self, "metric", metric)
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "winner_id", winner_id)
        object.__setattr__(self, "difference", difference)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "recommendation_id", recommendation_id)
    
    def get_value_for_asset(self, asset_id: str) -> float | None:
        """Get the metric value for a specific asset."""
        for item in self.items:
            if item.asset_id == asset_id:
                return item.value
        return None


@dataclass(frozen=True)
class TrendResult:
    """
    Result from a get_trend() query.
    
    Time series data with trend analysis (direction and magnitude).
    
    Attributes:
        metric: Which metric this trend is for
        asset_id: Asset identifier
        data_points: Time series of measurements
        direction: Overall trend direction
        change_percent: Percentage change over the period
        period: Time period covered
        granularity: Data granularity (hourly, daily, weekly)
        recommendation_id: For audit trail
    
    Example:
        TrendResult(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id="Line-1",
            data_points=[...],
            direction="down",
            change_percent=-12.5,
            period=TimePeriod.last_week(),
            granularity="daily"
        )
    """
    
    metric: CanonicalMetric
    asset_id: str
    data_points: tuple[DataPoint, ...]
    direction: Literal["up", "down", "stable"]
    change_percent: float
    period: TimePeriod
    granularity: str
    recommendation_id: str = ""
    
    def __init__(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        data_points: list[DataPoint] | tuple[DataPoint, ...],
        direction: Literal["up", "down", "stable"],
        change_percent: float,
        period: TimePeriod,
        granularity: str,
        recommendation_id: str = "",
    ):
        """Initialize with data_points converted to tuple."""
        object.__setattr__(self, "metric", metric)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "data_points", tuple(data_points))
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "change_percent", change_percent)
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "granularity", granularity)
        object.__setattr__(self, "recommendation_id", recommendation_id)
    
    @property
    def start_value(self) -> float | None:
        """First value in the series."""
        return self.data_points[0].value if self.data_points else None
    
    @property
    def end_value(self) -> float | None:
        """Last value in the series."""
        return self.data_points[-1].value if self.data_points else None
    
    @property
    def min_value(self) -> float | None:
        """Minimum value in the series."""
        return min(dp.value for dp in self.data_points) if self.data_points else None
    
    @property
    def max_value(self) -> float | None:
        """Maximum value in the series."""
        return max(dp.value for dp in self.data_points) if self.data_points else None


@dataclass(frozen=True)
class AnomalyResult:
    """
    Result from a check_anomaly() query.
    
    Indicates whether anomalies were detected and provides details.
    
    Attributes:
        is_anomalous: Whether any anomalies were found
        anomalies: List of detected anomalies (may be empty)
        severity: Overall severity level
        asset_id: Asset that was checked
        metric: Metric that was checked
        recommendation_id: For audit trail
    
    Example:
        AnomalyResult(
            is_anomalous=True,
            anomalies=[Anomaly(...)],
            severity="medium",
            asset_id="Line-1",
            metric=CanonicalMetric.OEE
        )
    """
    
    is_anomalous: bool
    anomalies: tuple[Anomaly, ...]
    severity: Literal["none", "low", "medium", "high", "critical"]
    asset_id: str
    metric: CanonicalMetric
    recommendation_id: str = ""
    
    def __init__(
        self,
        is_anomalous: bool,
        anomalies: list[Anomaly] | tuple[Anomaly, ...],
        severity: Literal["none", "low", "medium", "high", "critical"],
        asset_id: str,
        metric: CanonicalMetric,
        recommendation_id: str = "",
    ):
        """Initialize with anomalies converted to tuple."""
        object.__setattr__(self, "is_anomalous", is_anomalous)
        object.__setattr__(self, "anomalies", tuple(anomalies))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "metric", metric)
        object.__setattr__(self, "recommendation_id", recommendation_id)
    
    @property
    def anomaly_count(self) -> int:
        """Number of anomalies detected."""
        return len(self.anomalies)


@dataclass(frozen=True)
class WhatIfResult:
    """
    Result from a simulate_whatif() query.
    
    Predicts the impact of scenario changes on a target metric.
    
    Attributes:
        scenario_name: Name of the scenario simulated
        target_metric: Metric that was predicted
        baseline: Current value before changes
        projected: Predicted value after changes
        delta: Absolute change (projected - baseline)
        delta_percent: Percentage change
        confidence: Confidence level (0.0 to 1.0)
        factors: Contributing factors to the prediction
        recommendation_id: For audit trail
    
    Example:
        WhatIfResult(
            scenario_name="temperature_reduction",
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
            baseline=2.5,
            projected=2.2,
            delta=-0.3,
            delta_percent=-12.0,
            confidence=0.85,
            factors={"temperature": -5}
        )
    """
    
    scenario_name: str
    target_metric: CanonicalMetric
    baseline: float
    projected: float
    delta: float
    delta_percent: float
    confidence: float
    factors: dict[str, float]
    unit: str = ""
    recommendation_id: str = ""
    
    @property
    def is_improvement(self) -> bool:
        """Whether the projection shows improvement."""
        # For most metrics, lower is better (energy, scrap, CO2)
        # For some metrics, higher is better (OEE, efficiency)
        higher_is_better = {
            CanonicalMetric.OEE,
            CanonicalMetric.MATERIAL_EFFICIENCY,
            CanonicalMetric.THROUGHPUT,
            CanonicalMetric.SUPPLIER_ON_TIME,
        }
        
        if self.target_metric in higher_is_better:
            return self.delta > 0
        return self.delta < 0
    
    @property
    def confidence_level(self) -> Literal["low", "medium", "high"]:
        """Categorize confidence level."""
        if self.confidence >= 0.8:
            return "high"
        elif self.confidence >= 0.6:
            return "medium"
        return "low"
