"""
MockAdapter Unit Tests

Tests that MockAdapter correctly implements the ManufacturingAdapter contract.
"""

import pytest
from datetime import datetime

from skill.adapters.mock import MockAdapter
from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    WhatIfScenario,
    ScenarioParameter,
)
from skill.domain.results import (
    KPIResult,
    ComparisonResult,
    TrendResult,
    AnomalyResult,
    WhatIfResult,
)


class TestMockAdapterContract:
    """Contract tests - verify MockAdapter implements the interface correctly."""
    
    @pytest.fixture
    def adapter(self) -> MockAdapter:
        return MockAdapter()
    
    @pytest.fixture
    def period(self) -> TimePeriod:
        return TimePeriod.today()
    
    # =========================================================================
    # Query Type 1: get_kpi
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_get_kpi_returns_kpi_result(self, adapter, period):
        """get_kpi must return KPIResult."""
        result = await adapter.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
    
    @pytest.mark.asyncio
    async def test_get_kpi_contains_required_fields(self, adapter, period):
        """KPIResult must have all required fields populated."""
        result = await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            period=period,
        )
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.asset_id == "Line-1"
        assert result.value is not None
        assert result.unit is not None
        assert result.timestamp is not None
        assert result.recommendation_id  # Non-empty for audit
    
    @pytest.mark.asyncio
    async def test_get_kpi_all_metrics(self, adapter, period):
        """Should support all canonical metrics."""
        for metric in CanonicalMetric:
            result = await adapter.get_kpi(metric, "Line-1", period)
            assert result.metric == metric
    
    # =========================================================================
    # Query Type 2: compare
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_compare_returns_comparison_result(self, adapter, period):
        """compare must return ComparisonResult."""
        result = await adapter.compare(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_ids=["Compressor-1", "Compressor-2"],
            period=period,
        )
        assert isinstance(result, ComparisonResult)
    
    @pytest.mark.asyncio
    async def test_compare_has_winner(self, adapter, period):
        """ComparisonResult must identify a winner."""
        result = await adapter.compare(
            metric=CanonicalMetric.OEE,
            asset_ids=["Line-1", "Line-2"],
            period=period,
        )
        assert result.winner_id in ["Line-1", "Line-2"]
        assert len(result.items) == 2
    
    @pytest.mark.asyncio
    async def test_compare_items_have_ranks(self, adapter, period):
        """Each comparison item must have a rank."""
        result = await adapter.compare(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_ids=["Line-1", "Line-2", "Line-3"],
            period=period,
        )
        ranks = [item.rank for item in result.items]
        assert sorted(ranks) == [1, 2, 3]
    
    # =========================================================================
    # Query Type 3: get_trend
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_get_trend_returns_trend_result(self, adapter, period):
        """get_trend must return TrendResult."""
        result = await adapter.get_trend(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id="Line-1",
            period=period,
            granularity="daily",
        )
        assert isinstance(result, TrendResult)
    
    @pytest.mark.asyncio
    async def test_get_trend_has_data_points(self, adapter):
        """TrendResult must have data points."""
        period = TimePeriod.last_week()
        result = await adapter.get_trend(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            period=period,
            granularity="daily",
        )
        assert len(result.data_points) > 0
    
    @pytest.mark.asyncio
    async def test_get_trend_direction_valid(self, adapter, period):
        """Trend direction must be up, down, or stable."""
        result = await adapter.get_trend(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=period,
            granularity="hourly",
        )
        assert result.direction in ["up", "down", "stable"]
    
    # =========================================================================
    # Query Type 4: check_anomaly
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_check_anomaly_returns_anomaly_result(self, adapter):
        """check_anomaly must return AnomalyResult."""
        result = await adapter.check_anomaly(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
        )
        assert isinstance(result, AnomalyResult)
    
    @pytest.mark.asyncio
    async def test_check_anomaly_severity_valid(self, adapter):
        """Anomaly severity must be valid level."""
        result = await adapter.check_anomaly(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id="Line-1",
        )
        assert result.severity in ["none", "low", "medium", "high", "critical"]
    
    # =========================================================================
    # Query Type 5: simulate_whatif
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_simulate_whatif_returns_whatif_result(self, adapter):
        """simulate_whatif must return WhatIfResult."""
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=[ScenarioParameter("temperature", 25.0, 20.0, "°C")],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        result = await adapter.simulate_whatif(scenario)
        assert isinstance(result, WhatIfResult)
    
    @pytest.mark.asyncio
    async def test_simulate_whatif_has_confidence(self, adapter):
        """WhatIfResult must have confidence score."""
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=[ScenarioParameter("speed", 100.0, 110.0, "rpm")],
            target_metric=CanonicalMetric.THROUGHPUT,
        )
        result = await adapter.simulate_whatif(scenario)
        assert 0.0 <= result.confidence <= 1.0
    
    # =========================================================================
    # Capability Discovery
    # =========================================================================
    
    def test_supports_all_capabilities(self, adapter):
        """MockAdapter should support all capabilities for demo."""
        assert adapter.supports_capability("whatif") is True
        assert adapter.supports_capability("anomaly_ml") is True
    
    def test_platform_name(self, adapter):
        """Should return descriptive platform name."""
        assert "Mock" in adapter.platform_name or "Demo" in adapter.platform_name
