"""
QueryDispatcher - Routes Queries to Adapter Methods

Central orchestrator that routes the 5 query types to the appropriate
adapter method. Provides a synchronous interface for OVOS handlers
while managing async adapter calls internally.

Responsibilities:
    - Route queries to correct adapter method
    - Handle async/sync bridging
    - Apply common pre/post processing
    - Audit logging for compliance

Design Pattern:
    This is a Facade that simplifies adapter interaction for skill handlers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
import uuid

from skill.services.audit import AuditLogger

if TYPE_CHECKING:
    from skill.adapters.base import ManufacturingAdapter
    from skill.domain.models import CanonicalMetric, TimePeriod, WhatIfScenario
    from skill.domain.results import (
        KPIResult,
        ComparisonResult,
        TrendResult,
        AnomalyResult,
        WhatIfResult,
    )


logger = logging.getLogger(__name__)


class QueryDispatcher:
    """
    Routes manufacturing queries to the appropriate adapter method.
    
    This class acts as a facade between OVOS intent handlers and
    platform adapters. It handles:
    
    1. Async/sync bridging (OVOS handlers are sync, adapters are async)
    2. Query routing to the 5 query types
    3. Audit logging for GDPR compliance
    4. Error handling and user-friendly messages
    
    Attributes:
        adapter: The platform adapter to route queries to
        _loop: Event loop for async operations
    
    Example:
        dispatcher = QueryDispatcher(adapter=mock_adapter)
        
        # Sync call from OVOS handler
        result = dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
    """
    
    def __init__(self, adapter: ManufacturingAdapter, audit_logger: AuditLogger | None = None):
        """
        Initialize dispatcher with an adapter.
        
        Args:
            adapter: ManufacturingAdapter instance to route queries to
            audit_logger: Optional AuditLogger for compliance logging
        """
        self._adapter = adapter
        self._audit_logger = audit_logger or AuditLogger()
        self._loop: asyncio.AbstractEventLoop | None = None
    
    @property
    def adapter(self) -> ManufacturingAdapter:
        """Get the current adapter."""
        return self._adapter
    
    def set_adapter(self, adapter: ManufacturingAdapter) -> None:
        """
        Replace the adapter (for hot-reload support).
        
        Args:
            adapter: New adapter instance
        """
        logger.info(
            "Switching adapter from %s to %s",
            type(self._adapter).__name__,
            type(adapter).__name__,
        )
        self._adapter = adapter
    
    # =========================================================================
    # Query Type 1: KPI Retrieval
    # =========================================================================
    
    def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """
        Retrieve a KPI value (synchronous wrapper).
        
        This is the primary interface for OVOS intent handlers.
        
        Args:
            metric: Canonical metric to retrieve
            asset_id: Target asset identifier
            period: Time period for measurement
            
        Returns:
            KPIResult with value and metadata
            
        Example:
            result = dispatcher.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=TimePeriod.today()
            )
            speak(f"OEE is {result.value} percent")
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] get_kpi: metric=%s, asset=%s, period=%s",
            query_id, metric.value, asset_id, period.display_name,
        )
        
        result = self._run_async(
            self._adapter.get_kpi(metric, asset_id, period)
        )
        
        self._log_audit("get_kpi", query_id, metric.value, asset_id, result)
        return result
    
    # =========================================================================
    # Query Type 2: Comparison
    # =========================================================================
    
    def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """
        Compare a metric across multiple assets (synchronous wrapper).
        
        Args:
            metric: Canonical metric to compare
            asset_ids: List of asset identifiers (2+)
            period: Time period for comparison
            
        Returns:
            ComparisonResult with ranked items and winner
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] compare: metric=%s, assets=%s, period=%s",
            query_id, metric.value, asset_ids, period.display_name,
        )
        
        result = self._run_async(
            self._adapter.compare(metric, asset_ids, period)
        )
        
        self._log_audit("compare", query_id, metric.value, str(asset_ids), result)
        return result
    
    # =========================================================================
    # Query Type 3: Trend Analysis
    # =========================================================================
    
    def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """
        Get trend data for a metric (synchronous wrapper).
        
        Args:
            metric: Canonical metric to trend
            asset_id: Target asset identifier
            period: Time period to analyze
            granularity: Data frequency ("hourly", "daily", "weekly")
            
        Returns:
            TrendResult with data points and trend direction
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] get_trend: metric=%s, asset=%s, period=%s, granularity=%s",
            query_id, metric.value, asset_id, period.display_name, granularity,
        )
        
        result = self._run_async(
            self._adapter.get_trend(metric, asset_id, period, granularity)
        )
        
        self._log_audit("get_trend", query_id, metric.value, asset_id, result)
        return result
    
    # =========================================================================
    # Query Type 4: Anomaly Detection (INTELLIGENCE - Phase 3)
    # =========================================================================
    
    def check_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float | None = None,
    ) -> AnomalyResult:
        """
        Check for anomalies (orchestrates PREVENTION service).
        
        TODO PHASE 3: Implement DEC-007 compliant orchestration:
        1. Get raw data: adapter.get_raw_data(metric, asset_id, period)
        2. Call PREVENTION: prevention_client.detect_anomalies(raw_data, threshold)
        3. Call DocuBoT: docubot_client.explain_anomaly(metric, anomalies)
        4. Combine into AnomalyResult
        
        Current Phase 1 behavior: Returns mock result for testing intent handlers.
        
        Args:
            metric: Canonical metric to check
            asset_id: Target asset identifier
            threshold: Optional sensitivity threshold
            
        Returns:
            AnomalyResult with detection status and details
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] check_anomaly: metric=%s, asset=%s, threshold=%s",
            query_id, metric.value, asset_id, threshold,
        )
        
        # TODO PHASE 3: Replace with orchestration logic
        # For now, return mock result for testing
        from skill.domain.results import AnomalyResult
        from datetime import datetime
        result = AnomalyResult(
            is_anomalous=False,
            anomalies=[],
            severity="none",
            asset_id=asset_id,
            metric=metric,
            recommendation_id=self._generate_query_id(),
        )
        
        self._log_audit("check_anomaly", query_id, metric.value, asset_id, result)
        return result
    
    # =========================================================================
    # Query Type 5: What-If Simulation (INTELLIGENCE - Phase 3)
    # =========================================================================
    
    def simulate_whatif(
        self,
        scenario: WhatIfScenario,
    ) -> WhatIfResult:
        """
        Run what-if simulation (orchestrates DocuBoT + ML models).
        
        TODO PHASE 3: Implement DEC-007 compliant orchestration:
        1. Get historical data: adapter.get_raw_data(scenario.target_metric, ...)
        2. Call DocuBoT: docubot_client.get_parameter_correlations(scenario.parameters)
        3. Run simulation model with historical data + correlations
        4. Build WhatIfResult with confidence scores
        
        Current Phase 1 behavior: Returns mock result for testing intent handlers.
        
        Args:
            scenario: Scenario definition with parameter changes
            
        Returns:
            WhatIfResult with baseline, projected, and confidence
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] simulate_whatif: scenario=%s, asset=%s, target=%s",
            query_id, scenario.name, scenario.asset_id, scenario.target_metric.value,
        )
        
        # TODO PHASE 3: Replace with orchestration logic
        # For now, return mock result for testing
        from skill.domain.results import WhatIfResult
        result = WhatIfResult(
            scenario_name=scenario.name,
            target_metric=scenario.target_metric,
            baseline=100.0,
            projected=95.0,
            delta=-5.0,
            delta_percent=-5.0,
            confidence=0.75,
            factors={param.name: param.delta for param in scenario.parameters},
            unit="units",
            recommendation_id=self._generate_query_id(),
        )
        
        self._log_audit(
            "simulate_whatif", query_id, 
            scenario.target_metric.value, scenario.asset_id, result
        )
        return result
    
    # =========================================================================
    # Async/Sync Bridging
    # =========================================================================
    
    def _run_async(self, coro):
        """
        Run an async coroutine synchronously.
        
        Creates a new event loop if needed. This bridges the sync OVOS
        handler world with async adapter calls.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        try:
            # Try to get existing loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, use run_coroutine_threadsafe
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result(timeout=30)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(coro)
    
    # =========================================================================
    # Audit Logging (GDPR Compliance)
    # =========================================================================
    
    def _log_audit(
        self,
        query_type: str,
        query_id: str,
        metric: str,
        asset_id: str,
        result,
        user_role: str = "operator",
    ) -> None:
        """
        Log query for audit trail (GDPR compliance).
        
        Creates immutable audit record with:
        - Query ID for traceability
        - Query type and parameters
        - Result summary (not full data)
        - Timestamp
        
        Args:
            query_type: Type of query (get_kpi, compare, etc.)
            query_id: Unique query identifier
            metric: Canonical metric name
            asset_id: Asset identifier
            result: Query result object
            user_role: User role for access control
        """
        recommendation_id = getattr(result, 'recommendation_id', None)
        
        # Generate response summary based on result type
        response_summary = self._generate_response_summary(result)
        
        # Log to audit service
        try:
            self._audit_logger.log_query(
                query_id=query_id,
                user_role=user_role,
                query_type=query_type,
                metric=metric,
                asset_id=asset_id,
                recommendation_id=recommendation_id,
                response_summary=response_summary,
            )
        except Exception as e:
            # Don't fail query if audit logging fails
            logger.error("Failed to write audit log: %s", e)
    
    def _generate_response_summary(self, result) -> str:
        """Generate brief summary of result for audit log."""
        from skill.domain.results import (
            KPIResult, ComparisonResult, TrendResult,
            AnomalyResult, WhatIfResult
        )
        
        if isinstance(result, KPIResult):
            return f"KPI value: {result.value:.2f} {result.unit}"
        elif isinstance(result, ComparisonResult):
            return f"Winner: {result.winner_id}, diff: {result.difference:.2f}"
        elif isinstance(result, TrendResult):
            return f"Direction: {result.direction}, change: {result.change_percent:.1f}%"
        elif isinstance(result, AnomalyResult):
            return f"Anomalous: {result.is_anomalous}, count: {len(result.anomalies)}"
        elif isinstance(result, WhatIfResult):
            return f"Delta: {result.delta:.2f}, improvement: {result.is_improvement}"
        else:
            return str(type(result).__name__)

    
    def _generate_query_id(self) -> str:
        """Generate unique query ID for tracing."""
        return f"q-{uuid.uuid4().hex[:8]}"
