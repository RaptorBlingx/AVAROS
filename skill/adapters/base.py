"""
ManufacturingAdapter - Abstract Base Class

Defines the contract that ALL platform adapters must implement.
Every adapter provides the core query methods plus asset discovery.

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

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill.domain.models import (
        Asset,
        CanonicalMetric,
        DataPoint,
        TimePeriod,
    )
    from skill.domain.results import (
        ConnectionTestResult,
        KPIResult,
        ComparisonResult,
        TrendResult,
    )


class ManufacturingAdapter(ABC):
    """
    Abstract base class for all manufacturing platform adapters.
    
    This defines the contract between AVAROS skill handlers and
    platform-specific implementations.
    
    Implementing Classes:
        - UnconfiguredAdapter: Default when no platform is configured
        - ReneryoAdapter: RENERYO platform
        - GenericRestAdapter: Custom REST API platforms
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
    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> list[DataPoint]:
        """
        Query Type 4: Raw Data Retrieval
        
        Fetch raw time-series data for intelligence services to analyze.
        This is NOT an intent-level query - it's used internally by QueryDispatcher
        to feed data to PREVENTION (anomaly detection) and DocuBoT (what-if simulation).
        
        DEC-007: Intelligence Services Are Platform-Independent
        Adapters provide DATA, not INTELLIGENCE. This method returns raw data
        that the QueryDispatcher orchestrates through DocuBoT and PREVENTION.
        
        Args:
            metric: The canonical metric to retrieve data for
            asset_id: Target asset identifier
            period: Time period for data retrieval
            
        Returns:
            List of DataPoint objects (timestamp, value, unit)
            
        Raises:
            AdapterError: Platform communication failure
            MetricNotSupportedError: Metric not available
            
        Example:
            # QueryDispatcher uses this internally:
            raw_data = await adapter.get_raw_data(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Line-1",
                period=TimePeriod.last_7_days()
            )
            # Then feeds to PREVENTION for anomaly detection
            anomalies = prevention_client.detect_anomalies(raw_data)
        """
        ...

    @abstractmethod
    async def list_assets(self) -> list[Asset]:
        """Return all assets available on this platform."""
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

    def supports_asset_discovery(self) -> bool:
        """Return whether adapter supports live upstream asset discovery."""
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
    # Connection Testing
    # =========================================================================

    async def test_connection(self) -> ConnectionTestResult:
        """
        Test connectivity to the platform.

        Default implementation: try initialize() + measure latency.
        Subclasses should override with platform-specific health checks.

        Returns:
            ConnectionTestResult with success, latency, and discovered resources.
        """
        from skill.domain.results import ConnectionTestResult

        start = time.monotonic()
        try:
            await self.initialize()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=True,
                latency_ms=round(elapsed, 1),
                message="Connection established",
                adapter_name=self.platform_name,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=round(elapsed, 1),
                message=str(exc),
                adapter_name=self.platform_name,
                error_code=getattr(exc, "code", "UNKNOWN"),
                error_details=str(exc),
            )
        finally:
            await self.shutdown()

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
