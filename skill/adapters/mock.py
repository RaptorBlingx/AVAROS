"""
MockAdapter - Zero-Config Demo Adapter

Returns realistic manufacturing demo data without requiring any external
API configuration. This is the DEFAULT adapter for out-of-box experience.

Features:
    - Realistic manufacturing KPI values
    - Simulated trends with slight variations
    - Demo anomalies for testing
    - Plausible what-if predictions

Usage:
    # Automatically used when no platform is configured
    docker compose up  # MockAdapter is ready immediately
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
import uuid

from skill.adapters.base import ManufacturingAdapter
from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
    WhatIfScenario,
    Anomaly,
)
from skill.domain.results import (
    KPIResult,
    ComparisonResult,
    ComparisonItem,
    TrendResult,
    AnomalyResult,
    WhatIfResult,
)

if TYPE_CHECKING:
    pass


class MockAdapter(ManufacturingAdapter):
    """
    Demo adapter providing realistic manufacturing data without external APIs.
    
    This adapter enables zero-config deployment:
        git clone ... && docker compose up
        # System works immediately with demo data
    
    Data Characteristics:
        - OEE: 75-90% (realistic range)
        - Scrap rate: 1-5%
        - Energy per unit: 2-4 kWh/unit
        - Trends: Slight random variations
        - Anomalies: Occasional simulated spikes
    
    Thread Safety:
        This adapter is stateless and thread-safe.
    """
    
    # =========================================================================
    # Demo Data Configuration
    # =========================================================================
    
    # Baseline values for each metric (realistic manufacturing ranges)
    _METRIC_BASELINES: dict[CanonicalMetric, tuple[float, float, str]] = {
        # (baseline, variation, unit)
        CanonicalMetric.ENERGY_PER_UNIT: (2.8, 0.5, "kWh/unit"),
        CanonicalMetric.ENERGY_TOTAL: (15000, 2000, "kWh"),
        CanonicalMetric.PEAK_DEMAND: (850, 100, "kW"),
        CanonicalMetric.PEAK_TARIFF_EXPOSURE: (12.5, 3, "%"),
        CanonicalMetric.SCRAP_RATE: (2.5, 1.0, "%"),
        CanonicalMetric.REWORK_RATE: (1.8, 0.8, "%"),
        CanonicalMetric.MATERIAL_EFFICIENCY: (94.5, 2.0, "%"),
        CanonicalMetric.RECYCLED_CONTENT: (35, 10, "%"),
        CanonicalMetric.SUPPLIER_LEAD_TIME: (5.2, 1.5, "days"),
        CanonicalMetric.SUPPLIER_DEFECT_RATE: (0.8, 0.3, "%"),
        CanonicalMetric.SUPPLIER_ON_TIME: (92, 5, "%"),
        CanonicalMetric.SUPPLIER_CO2_PER_KG: (2.1, 0.4, "kg CO₂/kg"),
        CanonicalMetric.OEE: (82.5, 5, "%"),
        CanonicalMetric.THROUGHPUT: (120, 15, "units/hr"),
        CanonicalMetric.CYCLE_TIME: (45, 5, "sec"),
        CanonicalMetric.CHANGEOVER_TIME: (25, 8, "min"),
        CanonicalMetric.CO2_PER_UNIT: (0.85, 0.15, "kg CO₂-eq/unit"),
        CanonicalMetric.CO2_TOTAL: (4500, 800, "kg CO₂-eq"),
        CanonicalMetric.CO2_PER_BATCH: (42, 8, "kg CO₂-eq/batch"),
    }
    
    # Demo assets
    _DEMO_ASSETS = [
        "Line-1", "Line-2", "Line-3",
        "Compressor-1", "Compressor-2",
        "Boiler-1", "Furnace-1",
        "CNC-01", "CNC-02", "CNC-03",
    ]
    
    # =========================================================================
    # Query Type 1: KPI Retrieval
    # =========================================================================
    
    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Return realistic demo KPI value."""
        baseline, variation, unit = self._METRIC_BASELINES.get(
            metric, (50.0, 10.0, "units")
        )
        
        # Add deterministic variation based on asset_id for consistency
        asset_seed = hash(asset_id) % 100 / 100  # 0.0 to 0.99
        value = baseline + (asset_seed - 0.5) * variation * 2
        
        # Add small random noise for realism
        value += random.uniform(-variation * 0.1, variation * 0.1)
        
        return KPIResult(
            metric=metric,
            value=round(value, 2),
            unit=unit,
            asset_id=asset_id,
            period=period,
            timestamp=datetime.now(),
            recommendation_id=self._generate_recommendation_id(),
        )
    
    # =========================================================================
    # Query Type 2: Comparison
    # =========================================================================
    
    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """Compare metric across assets with realistic variation."""
        baseline, variation, unit = self._METRIC_BASELINES.get(
            metric, (50.0, 10.0, "units")
        )
        
        # Generate values for each asset
        items: list[ComparisonItem] = []
        for asset_id in asset_ids:
            asset_seed = hash(asset_id) % 100 / 100
            value = baseline + (asset_seed - 0.5) * variation * 2
            value += random.uniform(-variation * 0.1, variation * 0.1)
            items.append(ComparisonItem(
                asset_id=asset_id,
                value=round(value, 2),
                rank=0  # Will be set after sorting
            ))
        
        # Determine if lower or higher is better
        higher_is_better = metric in {
            CanonicalMetric.OEE,
            CanonicalMetric.MATERIAL_EFFICIENCY,
            CanonicalMetric.THROUGHPUT,
            CanonicalMetric.SUPPLIER_ON_TIME,
            CanonicalMetric.RECYCLED_CONTENT,
        }
        
        # Sort and assign ranks
        sorted_items = sorted(
            items,
            key=lambda x: x.value,
            reverse=higher_is_better
        )
        ranked_items = [
            ComparisonItem(item.asset_id, item.value, rank=i + 1)
            for i, item in enumerate(sorted_items)
        ]
        
        winner = ranked_items[0]
        loser = ranked_items[-1]
        
        return ComparisonResult(
            metric=metric,
            items=ranked_items,
            winner_id=winner.asset_id,
            difference=abs(winner.value - loser.value),
            unit=unit,
            period=period,
            recommendation_id=self._generate_recommendation_id(),
        )
    
    # =========================================================================
    # Query Type 3: Trend Analysis
    # =========================================================================
    
    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """Generate realistic trend data with slight variations."""
        baseline, variation, unit = self._METRIC_BASELINES.get(
            metric, (50.0, 10.0, "units")
        )
        
        # Determine number of data points based on granularity
        granularity_hours = {"hourly": 1, "daily": 24, "weekly": 168}
        hours_per_point = granularity_hours.get(granularity, 24)
        
        total_hours = int(period.duration_days * 24)
        num_points = max(3, total_hours // hours_per_point)
        num_points = min(num_points, 30)  # Cap at 30 points
        
        # Generate trend with random walk
        data_points: list[DataPoint] = []
        current_value = baseline + random.uniform(-variation * 0.3, variation * 0.3)
        
        # Add slight overall trend (improving or degrading)
        trend_bias = random.uniform(-0.02, 0.02)  # -2% to +2% per point
        
        for i in range(num_points):
            timestamp = period.start + timedelta(hours=i * hours_per_point)
            
            # Random walk with trend bias
            change = random.uniform(-variation * 0.1, variation * 0.1)
            change += trend_bias * baseline * 0.01
            current_value += change
            
            # Keep within reasonable bounds
            current_value = max(baseline - variation, min(baseline + variation, current_value))
            
            data_points.append(DataPoint(
                timestamp=timestamp,
                value=round(current_value, 2),
                unit=unit,
            ))
        
        # Calculate trend direction and change
        if data_points:
            start_val = data_points[0].value
            end_val = data_points[-1].value
            change_percent = ((end_val - start_val) / start_val) * 100 if start_val != 0 else 0
            
            if abs(change_percent) < 2:
                direction = "stable"
            elif change_percent > 0:
                direction = "up"
            else:
                direction = "down"
        else:
            direction = "stable"
            change_percent = 0
        
        return TrendResult(
            metric=metric,
            asset_id=asset_id,
            data_points=data_points,
            direction=direction,
            change_percent=round(change_percent, 1),
            period=period,
            granularity=granularity,
            recommendation_id=self._generate_recommendation_id(),
        )
    
    # =========================================================================
    # Query Type 4: Anomaly Detection
    # =========================================================================
    
    async def check_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float | None = None,
    ) -> AnomalyResult:
        """Simulate anomaly detection with occasional findings."""
        baseline, variation, _ = self._METRIC_BASELINES.get(
            metric, (50.0, 10.0, "units")
        )
        
        # 30% chance of finding an anomaly for demo purposes
        has_anomaly = random.random() < 0.3
        
        anomalies: list[Anomaly] = []
        if has_anomaly:
            # Generate 1-2 anomalies
            num_anomalies = random.randint(1, 2)
            for _ in range(num_anomalies):
                deviation = random.uniform(2.5, 4.0) * random.choice([-1, 1])
                actual = baseline + deviation * (variation / 2)
                
                anomalies.append(Anomaly(
                    timestamp=datetime.now() - timedelta(hours=random.randint(1, 24)),
                    metric=metric,
                    expected_value=baseline,
                    actual_value=round(actual, 2),
                    deviation=round(deviation, 1),
                    description=f"Unusual {metric.display_name} detected on {asset_id}",
                ))
        
        # Determine overall severity
        if not anomalies:
            severity = "none"
        else:
            max_dev = max(abs(a.deviation) for a in anomalies)
            if max_dev < 2.5:
                severity = "low"
            elif max_dev < 3.0:
                severity = "medium"
            elif max_dev < 4.0:
                severity = "high"
            else:
                severity = "critical"
        
        return AnomalyResult(
            is_anomalous=bool(anomalies),
            anomalies=anomalies,
            severity=severity,
            asset_id=asset_id,
            metric=metric,
            recommendation_id=self._generate_recommendation_id(),
        )
    
    # =========================================================================
    # Query Type 5: What-If Simulation
    # =========================================================================
    
    async def simulate_whatif(
        self,
        scenario: WhatIfScenario,
    ) -> WhatIfResult:
        """Simulate what-if with plausible impact predictions."""
        baseline, variation, unit = self._METRIC_BASELINES.get(
            scenario.target_metric, (50.0, 10.0, "units")
        )
        
        # Calculate cumulative impact from all parameter changes
        total_impact_percent = 0.0
        factors: dict[str, float] = {}
        
        for param in scenario.parameters:
            # Estimate impact: larger parameter changes = larger metric impact
            # This is a simplified heuristic model
            param_change_percent = param.delta_percent
            
            # Impact coefficients (how much 1% param change affects metric)
            impact_coefficient = random.uniform(0.3, 0.8)
            
            param_impact = param_change_percent * impact_coefficient * 0.1
            total_impact_percent += param_impact
            factors[param.name] = round(param.delta, 2)
        
        # Apply impact to baseline
        delta_percent = round(total_impact_percent, 1)
        delta = baseline * (delta_percent / 100)
        projected = baseline + delta
        
        # Confidence decreases with larger changes
        base_confidence = 0.85
        confidence = max(0.5, base_confidence - abs(delta_percent) * 0.01)
        
        return WhatIfResult(
            scenario_name=scenario.name,
            target_metric=scenario.target_metric,
            baseline=round(baseline, 2),
            projected=round(projected, 2),
            delta=round(delta, 2),
            delta_percent=delta_percent,
            confidence=round(confidence, 2),
            factors=factors,
            unit=unit,
            recommendation_id=self._generate_recommendation_id(),
        )
    
    # =========================================================================
    # Capability Discovery
    # =========================================================================
    
    def supports_capability(self, capability: str) -> bool:
        """MockAdapter supports all capabilities for demo purposes."""
        return True
    
    @property
    def platform_name(self) -> str:
        """Return platform name."""
        return "Demo (Mock)"
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _generate_recommendation_id(self) -> str:
        """Generate unique ID for audit trail (GDPR compliance)."""
        return f"mock-{uuid.uuid4().hex[:12]}"
