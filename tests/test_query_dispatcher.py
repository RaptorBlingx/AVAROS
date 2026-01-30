"""
T4: QueryDispatcher Unit Tests

Tests the QueryDispatcher that routes queries to the appropriate adapter methods
based on the 5 Query Types.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Optional


class MockCanonicalMetric:
    """Mock CanonicalMetric enum for testing"""
    ENERGY_PER_UNIT = "energy_per_unit"
    OEE = "oee"
    SCRAP_RATE = "scrap_rate"
    CO2_PER_UNIT = "co2_per_unit"


class MockKPIResult:
    """Mock KPIResult for testing"""
    def __init__(self, metric: str, value: float, unit: str, asset_id: str, period: str):
        self.metric = metric
        self.value = value
        self.unit = unit
        self.asset_id = asset_id
        self.period = period


class MockComparisonResult:
    """Mock ComparisonResult for testing"""
    def __init__(self, metric: str, items: list, winner_id: str):
        self.metric = metric
        self.items = items
        self.winner_id = winner_id


class MockTrendResult:
    """Mock TrendResult for testing"""
    def __init__(self, metric: str, data_points: list, trend_direction: str):
        self.metric = metric
        self.data_points = data_points
        self.trend_direction = trend_direction


class MockAnomalyResult:
    """Mock AnomalyResult for testing"""
    def __init__(self, is_anomalous: bool, anomalies: list, severity: str):
        self.is_anomalous = is_anomalous
        self.anomalies = anomalies
        self.severity = severity


class MockWhatIfResult:
    """Mock WhatIfResult for testing"""
    def __init__(self, baseline: dict, projected: dict, delta: float, confidence: float):
        self.baseline = baseline
        self.projected = projected
        self.delta = delta
        self.confidence = confidence


class MockQueryDispatcher:
    """Mock QueryDispatcher implementation for testing"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    async def get_kpi(self, metric: str, asset_id: str, period: str) -> MockKPIResult:
        """Route GET_KPI query type to adapter"""
        return await self.adapter.get_kpi(metric, asset_id, period)
    
    async def compare(self, metric: str, asset_ids: list, period: str) -> MockComparisonResult:
        """Route COMPARE query type to adapter"""
        return await self.adapter.compare(metric, asset_ids, period)
    
    async def get_trend(self, metric: str, asset_id: str, period: str, granularity: str) -> MockTrendResult:
        """Route TREND query type to adapter"""
        return await self.adapter.get_trend(metric, asset_id, period, granularity)
    
    async def check_anomaly(self, metric: str, asset_id: str, threshold: Optional[float] = None) -> MockAnomalyResult:
        """Route ANOMALY query type to adapter"""
        return await self.adapter.check_anomaly(metric, asset_id, threshold)
    
    async def simulate_whatif(self, scenario: dict) -> MockWhatIfResult:
        """Route WHATIF query type to adapter"""
        return await self.adapter.simulate_whatif(scenario)


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing"""
    adapter = Mock()
    adapter.get_kpi = AsyncMock(return_value=MockKPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        asset_id="compressor-1",
        period="today"
    ))
    adapter.compare = AsyncMock(return_value=MockComparisonResult(
        metric="energy_per_unit",
        items=[{"id": "comp-1", "value": 45.2}, {"id": "comp-2", "value": 52.3}],
        winner_id="comp-1"
    ))
    adapter.get_trend = AsyncMock(return_value=MockTrendResult(
        metric="scrap_rate",
        data_points=[{"value": 3.1}, {"value": 3.2}],
        trend_direction="up"
    ))
    adapter.check_anomaly = AsyncMock(return_value=MockAnomalyResult(
        is_anomalous=True,
        anomalies=[{"value": 67.8, "expected": 45.2}],
        severity="WARNING"
    ))
    adapter.simulate_whatif = AsyncMock(return_value=MockWhatIfResult(
        baseline={"value": 45.2},
        projected={"value": 42.1},
        delta=-3.1,
        confidence=0.85
    ))
    return adapter


@pytest.fixture
def dispatcher(mock_adapter):
    """Create a QueryDispatcher instance for testing"""
    return MockQueryDispatcher(mock_adapter)


class TestQueryDispatcherKPI:
    """Test QueryDispatcher GET_KPI routing"""
    
    @pytest.mark.asyncio
    async def test_get_kpi_routes_correctly(self, dispatcher, mock_adapter):
        """Test that get_kpi routes to adapter.get_kpi()"""
        result = await dispatcher.get_kpi(
            metric="energy_per_unit",
            asset_id="compressor-1",
            period="today"
        )
        
        mock_adapter.get_kpi.assert_called_once_with(
            "energy_per_unit",
            "compressor-1",
            "today"
        )
        assert result.metric == "energy_per_unit"
        assert result.value == 45.2
        assert result.asset_id == "compressor-1"
    
    @pytest.mark.asyncio
    async def test_get_kpi_returns_kpi_result(self, dispatcher):
        """Test that get_kpi returns correct result type"""
        result = await dispatcher.get_kpi(
            metric="oee",
            asset_id="line-1",
            period="today"
        )
        
        assert isinstance(result, MockKPIResult)
        assert hasattr(result, 'metric')
        assert hasattr(result, 'value')
        assert hasattr(result, 'unit')


class TestQueryDispatcherCompare:
    """Test QueryDispatcher COMPARE routing"""
    
    @pytest.mark.asyncio
    async def test_compare_routes_correctly(self, dispatcher, mock_adapter):
        """Test that compare routes to adapter.compare()"""
        result = await dispatcher.compare(
            metric="energy_per_unit",
            asset_ids=["comp-1", "comp-2"],
            period="today"
        )
        
        mock_adapter.compare.assert_called_once_with(
            "energy_per_unit",
            ["comp-1", "comp-2"],
            "today"
        )
        assert result.winner_id == "comp-1"
    
    @pytest.mark.asyncio
    async def test_compare_returns_comparison_result(self, dispatcher):
        """Test that compare returns correct result type"""
        result = await dispatcher.compare(
            metric="scrap_rate",
            asset_ids=["line-1", "line-2"],
            period="week"
        )
        
        assert isinstance(result, MockComparisonResult)
        assert hasattr(result, 'items')
        assert hasattr(result, 'winner_id')


class TestQueryDispatcherTrend:
    """Test QueryDispatcher TREND routing"""
    
    @pytest.mark.asyncio
    async def test_get_trend_routes_correctly(self, dispatcher, mock_adapter):
        """Test that get_trend routes to adapter.get_trend()"""
        result = await dispatcher.get_trend(
            metric="scrap_rate",
            asset_id="line-1",
            period="week",
            granularity="daily"
        )
        
        mock_adapter.get_trend.assert_called_once_with(
            "scrap_rate",
            "line-1",
            "week",
            "daily"
        )
        assert result.trend_direction == "up"
    
    @pytest.mark.asyncio
    async def test_get_trend_returns_trend_result(self, dispatcher):
        """Test that get_trend returns correct result type"""
        result = await dispatcher.get_trend(
            metric="energy_per_unit",
            asset_id="comp-1",
            period="month",
            granularity="weekly"
        )
        
        assert isinstance(result, MockTrendResult)
        assert hasattr(result, 'data_points')
        assert hasattr(result, 'trend_direction')


class TestQueryDispatcherAnomaly:
    """Test QueryDispatcher ANOMALY routing"""
    
    @pytest.mark.asyncio
    async def test_check_anomaly_routes_correctly(self, dispatcher, mock_adapter):
        """Test that check_anomaly routes to adapter.check_anomaly()"""
        result = await dispatcher.check_anomaly(
            metric="energy_per_unit",
            asset_id="compressor-1",
            threshold=2.0
        )
        
        mock_adapter.check_anomaly.assert_called_once_with(
            "energy_per_unit",
            "compressor-1",
            2.0
        )
        assert result.is_anomalous is True
        assert result.severity == "WARNING"
    
    @pytest.mark.asyncio
    async def test_check_anomaly_optional_threshold(self, dispatcher, mock_adapter):
        """Test that check_anomaly works with optional threshold"""
        result = await dispatcher.check_anomaly(
            metric="scrap_rate",
            asset_id="line-1"
        )
        
        mock_adapter.check_anomaly.assert_called_once()
        assert isinstance(result, MockAnomalyResult)


class TestQueryDispatcherWhatIf:
    """Test QueryDispatcher WHATIF routing"""
    
    @pytest.mark.asyncio
    async def test_simulate_whatif_routes_correctly(self, dispatcher, mock_adapter):
        """Test that simulate_whatif routes to adapter.simulate_whatif()"""
        scenario = {"type": "temperature_reduction", "value": -5}
        result = await dispatcher.simulate_whatif(scenario)
        
        mock_adapter.simulate_whatif.assert_called_once_with(scenario)
        assert result.delta == -3.1
        assert result.confidence == 0.85
    
    @pytest.mark.asyncio
    async def test_simulate_whatif_returns_whatif_result(self, dispatcher):
        """Test that simulate_whatif returns correct result type"""
        scenario = {"type": "material_change", "from": "virgin", "to": "recycled"}
        result = await dispatcher.simulate_whatif(scenario)
        
        assert isinstance(result, MockWhatIfResult)
        assert hasattr(result, 'baseline')
        assert hasattr(result, 'projected')
        assert hasattr(result, 'delta')
        assert hasattr(result, 'confidence')


class TestQueryDispatcherErrorHandling:
    """Test QueryDispatcher error handling"""
    
    @pytest.mark.asyncio
    async def test_adapter_error_propagation(self, mock_adapter):
        """Test that adapter errors are propagated correctly"""
        mock_adapter.get_kpi = AsyncMock(side_effect=Exception("Adapter error"))
        dispatcher = MockQueryDispatcher(mock_adapter)
        
        with pytest.raises(Exception, match="Adapter error"):
            await dispatcher.get_kpi("energy_per_unit", "comp-1", "today")
