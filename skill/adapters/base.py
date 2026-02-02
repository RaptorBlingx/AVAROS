"""
ManufacturingAdapter - Abstract Base Class

Defines the contract that ALL platform adapters must implement.
Every adapter provides exactly 5 query methods that return canonical types.

Usage:
    class ReneryoAdapter(ManufacturingAdapter):
        async def get_kpi(self, metric, asset_id, period) -> KPIResult:
            # Call RENERYO API, transform to canonical type
            ...

    class SAPAdapter(ManufacturingAdapter):
        async def get_kpi(self, metric, asset_id, period) -> KPIResult:
            # Call SAP API, transform to canonical type
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, TimePeriod, WhatIfScenario
    from skill.domain.results import (
        KPIResult,
        ComparisonResult,
        TrendResult,
        AnomalyResult,
        WhatIfResult,
    )


class ManufacturingAdapter(ABC):
    """
    Abstract base class for all manufacturing platform adapters.
    
    This defines the contract between AVAROS skill handlers and
    platform-specific implementations. All 5 query types are represented.
    
    Implementing Classes:
        - MockAdapter: Demo data (default, zero-config)
        - ReneryoAdapter: RENERYO platform (to be implemented)
        - Future: SAPAdapter, SiemensAdapter, etc.
    
    Design Principles:
        - Return ONLY canonical types (never raw API responses)
        - Handle errors gracefully with AdapterError
        - Log all API calls for audit trail
        - Support async operations for I/O efficiency
    
    Example:
        adapter = adapter_factory.create()  # Returns configured adapter
        result = await adapter.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
        # result is always a KPIResult, regardless of platform
    """
    
    # =========================================================================
    # Abstract Methods - The 5 Query Types
    # =========================================================================
    
    @abstractmethod
    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """
        Query Type 1: KPI Retrieval
        
        Retrieve a single KPI value for an asset over a time period.
        This is the most common query type.
        
        Args:
            metric: The canonical metric to retrieve
            asset_id: Target asset/machine identifier
            period: Time period for the measurement
            
        Returns:
            KPIResult with value, unit, and metadata
            
        Raises:
            AdapterError: Platform communication failure
            MetricNotSupportedError: Metric not available
            AssetNotFoundError: Unknown asset
            
        Example:
            result = await adapter.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=TimePeriod.today()
            )
            print(f"OEE: {result.value}%")  # "OEE: 82.5%"
        """
        ...
    
    @abstractmethod
    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """
        Query Type 2: Comparison
        
        Compare a metric across multiple assets to identify best/worst performers.
        
        Args:
            metric: The canonical metric to compare
            asset_ids: List of assets to compare (2 or more)
            period: Time period for comparison
            
        Returns:
            ComparisonResult with ranked items and winner
            
        Raises:
            AdapterError: Platform communication failure
            ValidationError: Fewer than 2 assets provided
            
        Example:
            result = await adapter.compare(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_ids=["Compressor-1", "Compressor-2"],
                period=TimePeriod.this_week()
            )
            print(f"Winner: {result.winner_id}")
        """
        ...
    
    @abstractmethod
    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """
        Query Type 3: Trend Analysis
        
        Get time series data with trend direction and change percentage.
        
        Args:
            metric: The canonical metric to trend
            asset_id: Target asset identifier
            period: Time period to analyze
            granularity: Data point frequency ("hourly", "daily", "weekly")
            
        Returns:
            TrendResult with data points, direction, and change %
            
        Raises:
            AdapterError: Platform communication failure
            ValidationError: Invalid granularity
            
        Example:
            result = await adapter.get_trend(
                metric=CanonicalMetric.SCRAP_RATE,
                asset_id="Line-1",
                period=TimePeriod.last_week(),
                granularity="daily"
            )
            print(f"Trend: {result.direction} ({result.change_percent}%)")
        """
        ...
    
    @abstractmethod
    async def check_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float | None = None,
    ) -> AnomalyResult:
        """
        Query Type 4: Anomaly Detection
        
        Check for unusual patterns in recent data using PREVENTION service
        or built-in statistical methods.
        
        Args:
            metric: The canonical metric to check
            asset_id: Target asset identifier
            threshold: Optional sensitivity threshold (std deviations)
            
        Returns:
            AnomalyResult with detection status and anomaly details
            
        Raises:
            AdapterError: Platform/PREVENTION communication failure
            
        Example:
            result = await adapter.check_anomaly(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1"
            )
            if result.is_anomalous:
                print(f"Found {len(result.anomalies)} anomalies!")
        """
        ...
    
    @abstractmethod
    async def simulate_whatif(
        self,
        scenario: WhatIfScenario,
    ) -> WhatIfResult:
        """
        Query Type 5: What-If Simulation
        
        Predict the impact of parameter changes on a target metric.
        Uses ML models or heuristics depending on platform capabilities.
        
        Args:
            scenario: Definition of parameter changes to simulate
            
        Returns:
            WhatIfResult with baseline, projected values, and confidence
            
        Raises:
            AdapterError: Simulation service failure
            ValidationError: Invalid scenario parameters
            
        Example:
            scenario = WhatIfScenario(
                name="temp_reduction",
                asset_id="Line-1",
                parameters=[
                    ScenarioParameter("temperature", 25.0, 20.0, "°C")
                ],
                target_metric=CanonicalMetric.ENERGY_PER_UNIT
            )
            result = await adapter.simulate_whatif(scenario)
            print(f"Projected savings: {result.delta_percent}%")
        """
        ...
    
    # =========================================================================
    # Capability Discovery
    # =========================================================================
    
    def supports_capability(self, capability: str) -> bool:
        """
        Check if this adapter supports an optional capability.
        
        Some platforms may not support all features (e.g., what-if simulation).
        Use this to gracefully handle unsupported operations.
        
        Args:
            capability: Capability name to check. Standard capabilities:
                - "whatif": What-if simulations
                - "anomaly_ml": ML-based anomaly detection
                - "realtime": Real-time data (vs batch)
                - "carbon": Carbon tracking metrics
                
        Returns:
            True if capability is supported, False otherwise
            
        Example:
            if adapter.supports_capability("whatif"):
                result = await adapter.simulate_whatif(scenario)
            else:
                speak("What-if simulations aren't available with this platform")
        """
        # Default implementation - subclasses override
        return True
    
    def get_supported_metrics(self) -> list[CanonicalMetric]:
        """
        Return list of metrics this adapter can provide.
        
        Returns:
            List of CanonicalMetric values supported by this adapter
        """
        from skill.domain.models import CanonicalMetric
        return list(CanonicalMetric)
    
    # =========================================================================
    # Lifecycle
    # =========================================================================
    
    async def initialize(self) -> None:
        """
        Initialize the adapter (e.g., establish connections, load config).
        
        Called by AdapterFactory after construction.
        Override in subclasses if initialization is needed.
        """
        pass
    
    async def shutdown(self) -> None:
        """
        Clean up resources (e.g., close connections).
        
        Called when adapter is being replaced or system is shutting down.
        Override in subclasses if cleanup is needed.
        """
        pass
    
    @property
    def platform_name(self) -> str:
        """Human-readable name of the platform this adapter connects to."""
        return self.__class__.__name__.replace("Adapter", "")
