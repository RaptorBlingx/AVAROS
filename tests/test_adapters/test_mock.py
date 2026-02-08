"""
MockAdapter Unit Tests

Comprehensive tests for the zero-config demo adapter.
Tests all 4 implemented query methods, lifecycle, capability discovery,
and parametrized coverage across all 19 CanonicalMetrics.
"""

import pytest
from datetime import datetime

from skill.adapters.mock import MockAdapter
from skill.adapters.base import ManufacturingAdapter
from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
)
from skill.domain.results import (
    KPIResult,
    ComparisonResult,
    TrendResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter() -> MockAdapter:
    """Create a fresh MockAdapter instance."""
    return MockAdapter()


@pytest.fixture
def period() -> TimePeriod:
    """Standard test period."""
    return TimePeriod.last_week()


@pytest.fixture
def asset_id() -> str:
    """Standard test asset."""
    return "Line-1"


# ---------------------------------------------------------------------------
# Construction & Inheritance
# ---------------------------------------------------------------------------

class TestMockAdapterConstruction:
    """Tests for MockAdapter construction and type hierarchy."""

    def test_inherits_from_manufacturing_adapter(self, adapter: MockAdapter) -> None:
        """MockAdapter must implement the ManufacturingAdapter ABC."""
        assert isinstance(adapter, ManufacturingAdapter)

    def test_platform_name_returns_demo_mock(self, adapter: MockAdapter) -> None:
        """platform_name property should identify the demo adapter."""
        assert adapter.platform_name == "Demo (Mock)"

    def test_metric_baselines_cover_all_metrics(self) -> None:
        """Every CanonicalMetric must have a baseline entry."""
        for metric in CanonicalMetric:
            assert metric in MockAdapter._METRIC_BASELINES, (
                f"Missing baseline for {metric.value}"
            )

    def test_metric_baselines_have_valid_structure(self) -> None:
        """Each baseline entry is (float, float, str)."""
        for metric, entry in MockAdapter._METRIC_BASELINES.items():
            assert len(entry) == 3
            baseline, variation, unit = entry
            assert isinstance(baseline, (int, float))
            assert isinstance(variation, (int, float))
            assert isinstance(unit, str)
            assert variation > 0, f"{metric.value}: variation must be positive"


# ---------------------------------------------------------------------------
# Query Type 1: get_kpi
# ---------------------------------------------------------------------------

class TestMockAdapterGetKpi:
    """Tests for get_kpi() — single KPI retrieval."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", list(CanonicalMetric))
    async def test_get_kpi_returns_kpi_result_for_all_metrics(
        self,
        adapter: MockAdapter,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """get_kpi must return a KPIResult for every canonical metric."""
        result = await adapter.get_kpi(metric, asset_id, period)

        assert isinstance(result, KPIResult)
        assert result.metric is metric
        assert result.asset_id == asset_id
        assert result.period is period

    @pytest.mark.asyncio
    async def test_get_kpi_value_in_realistic_range(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Value should fall near the baseline ± variation."""
        metric = CanonicalMetric.OEE
        baseline, variation, _ = MockAdapter._METRIC_BASELINES[metric]

        result = await adapter.get_kpi(metric, "Line-1", period)

        # Allow generous 3x variation for seed + noise
        assert baseline - variation * 3 < result.value < baseline + variation * 3

    @pytest.mark.asyncio
    async def test_get_kpi_unit_matches_baseline(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Unit must match the baseline configuration."""
        metric = CanonicalMetric.ENERGY_PER_UNIT
        _, _, expected_unit = MockAdapter._METRIC_BASELINES[metric]

        result = await adapter.get_kpi(metric, "Line-1", period)

        assert result.unit == expected_unit

    @pytest.mark.asyncio
    async def test_get_kpi_timestamp_is_recent(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Timestamp should be approximately now."""
        result = await adapter.get_kpi(CanonicalMetric.OEE, asset_id, period)

        diff = abs((datetime.now() - result.timestamp).total_seconds())
        assert diff < 5, "Timestamp should be within 5 seconds of now"

    @pytest.mark.asyncio
    async def test_get_kpi_recommendation_id_is_non_empty(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """recommendation_id must be a non-empty audit trail token."""
        result = await adapter.get_kpi(CanonicalMetric.SCRAP_RATE, asset_id, period)

        assert result.recommendation_id
        assert result.recommendation_id.startswith("mock-")

    @pytest.mark.asyncio
    async def test_get_kpi_deterministic_for_same_asset(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Same asset should produce similar (not identical due to noise) values."""
        metric = CanonicalMetric.THROUGHPUT
        r1 = await adapter.get_kpi(metric, "CNC-01", period)
        r2 = await adapter.get_kpi(metric, "CNC-01", period)

        baseline, variation, _ = MockAdapter._METRIC_BASELINES[metric]
        # Both should be close to the same deterministic seed value
        assert abs(r1.value - r2.value) < variation * 0.5


# ---------------------------------------------------------------------------
# Query Type 2: compare
# ---------------------------------------------------------------------------

class TestMockAdapterCompare:
    """Tests for compare() — cross-asset comparison."""

    @pytest.mark.asyncio
    async def test_compare_two_assets_returns_comparison_result(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """compare() with 2 assets should return a valid ComparisonResult."""
        result = await adapter.compare(
            CanonicalMetric.ENERGY_PER_UNIT,
            ["Compressor-1", "Compressor-2"],
            period,
        )

        assert isinstance(result, ComparisonResult)
        assert len(result.items) == 2
        assert result.winner_id in {"Compressor-1", "Compressor-2"}

    @pytest.mark.asyncio
    async def test_compare_three_assets_returns_ranked_items(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """compare() with 3+ assets should rank all of them."""
        asset_ids = ["Line-1", "Line-2", "Line-3"]
        result = await adapter.compare(CanonicalMetric.OEE, asset_ids, period)

        assert len(result.items) == 3
        ranks = [item.rank for item in result.items]
        assert sorted(ranks) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_compare_winner_has_rank_one(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Winner should be the item at rank 1."""
        result = await adapter.compare(
            CanonicalMetric.SCRAP_RATE,
            ["CNC-01", "CNC-02", "CNC-03"],
            period,
        )

        winner_item = next(i for i in result.items if i.asset_id == result.winner_id)
        assert winner_item.rank == 1

    @pytest.mark.asyncio
    async def test_compare_difference_is_non_negative(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Difference between winner and loser is always >= 0."""
        result = await adapter.compare(
            CanonicalMetric.MATERIAL_EFFICIENCY,
            ["Line-1", "Line-2"],
            period,
        )

        assert result.difference >= 0

    @pytest.mark.asyncio
    async def test_compare_unit_matches_baseline(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """Unit should match the metric's baseline unit."""
        metric = CanonicalMetric.CO2_PER_UNIT
        _, _, expected_unit = MockAdapter._METRIC_BASELINES[metric]

        result = await adapter.compare(metric, ["Line-1", "Line-2"], period)

        assert result.unit == expected_unit

    @pytest.mark.asyncio
    async def test_compare_recommendation_id_present(
        self,
        adapter: MockAdapter,
        period: TimePeriod,
    ) -> None:
        """recommendation_id must exist for audit trail."""
        result = await adapter.compare(
            CanonicalMetric.OEE,
            ["Line-1", "Line-2"],
            period,
        )

        assert result.recommendation_id
        assert result.recommendation_id.startswith("mock-")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", list(CanonicalMetric))
    async def test_compare_works_for_all_metrics(
        self,
        adapter: MockAdapter,
        metric: CanonicalMetric,
        period: TimePeriod,
    ) -> None:
        """compare() must work for every canonical metric."""
        result = await adapter.compare(metric, ["Line-1", "Line-2"], period)

        assert isinstance(result, ComparisonResult)
        assert result.metric is metric


# ---------------------------------------------------------------------------
# Query Type 3: get_trend
# ---------------------------------------------------------------------------

class TestMockAdapterGetTrend:
    """Tests for get_trend() — time series with direction."""

    @pytest.mark.asyncio
    async def test_get_trend_returns_trend_result(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """get_trend must return a TrendResult."""
        result = await adapter.get_trend(
            CanonicalMetric.SCRAP_RATE, asset_id, period,
        )

        assert isinstance(result, TrendResult)
        assert result.metric is CanonicalMetric.SCRAP_RATE
        assert result.asset_id == asset_id

    @pytest.mark.asyncio
    async def test_get_trend_has_data_points(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Trend must contain data points."""
        result = await adapter.get_trend(
            CanonicalMetric.ENERGY_PER_UNIT, asset_id, period,
        )

        assert len(result.data_points) >= 3

    @pytest.mark.asyncio
    async def test_get_trend_data_points_are_datapoint_objects(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Each data point must be a DataPoint instance."""
        result = await adapter.get_trend(
            CanonicalMetric.OEE, asset_id, period,
        )

        for dp in result.data_points:
            assert isinstance(dp, DataPoint)
            assert isinstance(dp.value, float)
            assert isinstance(dp.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_trend_direction_is_valid(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Direction must be one of up/down/stable."""
        result = await adapter.get_trend(
            CanonicalMetric.THROUGHPUT, asset_id, period,
        )

        assert result.direction in {"up", "down", "stable"}

    @pytest.mark.asyncio
    async def test_get_trend_change_percent_is_numeric(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """change_percent must be a numeric value."""
        result = await adapter.get_trend(
            CanonicalMetric.CYCLE_TIME, asset_id, period,
        )

        assert isinstance(result.change_percent, (int, float))

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "granularity", ["hourly", "daily", "weekly"],
    )
    async def test_get_trend_respects_granularity(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
        granularity: str,
    ) -> None:
        """Trend should accept different granularity values."""
        result = await adapter.get_trend(
            CanonicalMetric.OEE, asset_id, period, granularity=granularity,
        )

        assert result.granularity == granularity
        assert len(result.data_points) >= 3

    @pytest.mark.asyncio
    async def test_get_trend_recommendation_id_present(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """recommendation_id must exist for audit trail."""
        result = await adapter.get_trend(
            CanonicalMetric.SCRAP_RATE, asset_id, period,
        )

        assert result.recommendation_id
        assert result.recommendation_id.startswith("mock-")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", list(CanonicalMetric))
    async def test_get_trend_works_for_all_metrics(
        self,
        adapter: MockAdapter,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """get_trend must work for every canonical metric."""
        result = await adapter.get_trend(metric, asset_id, period)

        assert isinstance(result, TrendResult)
        assert result.metric is metric


# ---------------------------------------------------------------------------
# Query Type 4: get_raw_data
# ---------------------------------------------------------------------------

class TestMockAdapterGetRawData:
    """Tests for get_raw_data() — raw time-series retrieval."""

    @pytest.mark.asyncio
    async def test_get_raw_data_returns_list_of_datapoints(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """get_raw_data must return a list of DataPoint objects."""
        result = await adapter.get_raw_data(
            CanonicalMetric.ENERGY_PER_UNIT, asset_id, period,
        )

        assert isinstance(result, list)
        assert len(result) > 0
        for dp in result:
            assert isinstance(dp, DataPoint)

    @pytest.mark.asyncio
    async def test_get_raw_data_values_are_numeric(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Every data point value should be a float."""
        result = await adapter.get_raw_data(
            CanonicalMetric.SCRAP_RATE, asset_id, period,
        )

        for dp in result:
            assert isinstance(dp.value, float)

    @pytest.mark.asyncio
    async def test_get_raw_data_timestamps_are_within_period(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Data point timestamps should start within the period."""
        result = await adapter.get_raw_data(
            CanonicalMetric.OEE, asset_id, period,
        )

        assert result[0].timestamp >= period.start

    @pytest.mark.asyncio
    async def test_get_raw_data_has_unit_from_baseline(
        self,
        adapter: MockAdapter,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """Data points should carry the correct unit string."""
        metric = CanonicalMetric.CO2_TOTAL
        _, _, expected_unit = MockAdapter._METRIC_BASELINES[metric]

        result = await adapter.get_raw_data(metric, asset_id, period)

        assert result[0].unit == expected_unit

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", list(CanonicalMetric))
    async def test_get_raw_data_works_for_all_metrics(
        self,
        adapter: MockAdapter,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> None:
        """get_raw_data must work for every canonical metric."""
        result = await adapter.get_raw_data(metric, asset_id, period)

        assert isinstance(result, list)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Capability Discovery
# ---------------------------------------------------------------------------

class TestMockAdapterCapabilities:
    """Tests for supports_capability() and get_supported_metrics()."""

    def test_supports_capability_returns_true_for_all(
        self,
        adapter: MockAdapter,
    ) -> None:
        """MockAdapter supports every capability for demo purposes."""
        assert adapter.supports_capability("whatif") is True
        assert adapter.supports_capability("anomaly_ml") is True
        assert adapter.supports_capability("realtime") is True
        assert adapter.supports_capability("carbon") is True
        assert adapter.supports_capability("anything") is True

    def test_get_supported_metrics_returns_all_canonical(
        self,
        adapter: MockAdapter,
    ) -> None:
        """MockAdapter should report support for all 19 metrics."""
        metrics = adapter.get_supported_metrics()

        assert len(metrics) == 19
        for metric in CanonicalMetric:
            assert metric in metrics


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestMockAdapterLifecycle:
    """Tests for initialize() and shutdown()."""

    @pytest.mark.asyncio
    async def test_initialize_does_not_raise(
        self,
        adapter: MockAdapter,
    ) -> None:
        """initialize() should complete without errors."""
        await adapter.initialize()  # no exception = pass

    @pytest.mark.asyncio
    async def test_shutdown_does_not_raise(
        self,
        adapter: MockAdapter,
    ) -> None:
        """shutdown() should complete without errors."""
        await adapter.shutdown()  # no exception = pass

    @pytest.mark.asyncio
    async def test_initialize_then_shutdown_lifecycle(
        self,
        adapter: MockAdapter,
    ) -> None:
        """Full lifecycle: init → query → shutdown."""
        await adapter.initialize()
        result = await adapter.get_kpi(
            CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)
        await adapter.shutdown()


# ---------------------------------------------------------------------------
# Helper: _generate_recommendation_id
# ---------------------------------------------------------------------------

class TestMockAdapterHelpers:
    """Tests for internal helper methods."""

    def test_generate_recommendation_id_format(
        self,
        adapter: MockAdapter,
    ) -> None:
        """IDs should follow 'mock-{hex12}' format."""
        rid = adapter._generate_recommendation_id()

        assert rid.startswith("mock-")
        hex_part = rid[5:]
        assert len(hex_part) == 12
        int(hex_part, 16)  # raises ValueError if not valid hex

    def test_generate_recommendation_id_unique(
        self,
        adapter: MockAdapter,
    ) -> None:
        """Each call should produce a unique ID."""
        ids = {adapter._generate_recommendation_id() for _ in range(100)}

        assert len(ids) == 100
