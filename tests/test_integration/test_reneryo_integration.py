"""
ReneryoAdapter Integration Tests — Full HTTP round-trip against mock server.

These tests require the mock RENERYO server to be running:
    docker compose -f docker-compose.yml up reneryo-mock

Skip by default — run with: pytest -m integration
"""

from __future__ import annotations

import os

import pytest

from skill.adapters.reneryo import ReneryoAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import ComparisonResult, KPIResult, TrendResult

# =========================================================================
# Configuration
# =========================================================================

MOCK_SERVER_URL = os.environ.get("RENERYO_MOCK_URL", "http://localhost:8090")
MOCK_API_KEY = "integration-test-key"

pytestmark = pytest.mark.integration


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
async def adapter():
    """Create and initialize a ReneryoAdapter pointing at mock server."""
    a = ReneryoAdapter(
        api_url=MOCK_SERVER_URL,
        api_key=MOCK_API_KEY,
        timeout=10,
        auth_type="bearer",
    )
    await a.initialize()
    yield a
    await a.shutdown()


@pytest.fixture
async def cookie_adapter():
    """Create a ReneryoAdapter using cookie auth."""
    a = ReneryoAdapter(
        api_url=MOCK_SERVER_URL,
        api_key=MOCK_API_KEY,
        timeout=10,
        auth_type="cookie",
    )
    await a.initialize()
    yield a
    await a.shutdown()


# =========================================================================
# KPI Tests
# =========================================================================


class TestGetKpiFromMockServer:
    """Full round-trip KPI queries against mock RENERYO server."""

    @pytest.mark.asyncio
    async def test_get_kpi_energy_per_unit(self, adapter: ReneryoAdapter) -> None:
        """Fetch energy_per_unit KPI from mock server."""
        result = await adapter.get_kpi(
            CanonicalMetric.ENERGY_PER_UNIT, "Line-1", TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.value > 0
        assert result.unit == "kWh/unit"
        assert result.asset_id == "Line-1"

    @pytest.mark.asyncio
    async def test_get_kpi_oee(self, adapter: ReneryoAdapter) -> None:
        """Fetch OEE KPI from mock server."""
        result = await adapter.get_kpi(
            CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.OEE
        assert 0 < result.value <= 100
        assert result.unit == "%"

    @pytest.mark.asyncio
    async def test_get_kpi_all_metrics(self, adapter: ReneryoAdapter) -> None:
        """Fetch every mapped metric successfully."""
        for metric in CanonicalMetric:
            result = await adapter.get_kpi(
                metric, "Line-1", TimePeriod.today(),
            )
            assert isinstance(result, KPIResult)
            assert result.metric == metric


# =========================================================================
# Trend Tests
# =========================================================================


class TestGetTrendFromMockServer:
    """Full round-trip trend queries against mock RENERYO server."""

    @pytest.mark.asyncio
    async def test_get_trend_daily(self, adapter: ReneryoAdapter) -> None:
        """Fetch daily trend from mock server."""
        result = await adapter.get_trend(
            CanonicalMetric.SCRAP_RATE,
            "Line-1",
            TimePeriod.last_week(),
            granularity="daily",
        )
        assert isinstance(result, TrendResult)
        assert len(result.data_points) > 0
        assert result.direction in ("up", "down", "stable")
        assert result.granularity == "daily"

    @pytest.mark.asyncio
    async def test_get_trend_hourly(self, adapter: ReneryoAdapter) -> None:
        """Fetch hourly trend from mock server."""
        result = await adapter.get_trend(
            CanonicalMetric.ENERGY_PER_UNIT,
            "Line-1",
            TimePeriod.today(),
            granularity="hourly",
        )
        assert isinstance(result, TrendResult)
        assert len(result.data_points) > 0


# =========================================================================
# Comparison Tests
# =========================================================================


class TestCompareFromMockServer:
    """Full round-trip comparison queries against mock RENERYO server."""

    @pytest.mark.asyncio
    async def test_compare_two_assets(self, adapter: ReneryoAdapter) -> None:
        """Compare energy_per_unit across 2 assets."""
        result = await adapter.compare(
            CanonicalMetric.ENERGY_PER_UNIT,
            ["Line-1", "Line-2"],
            TimePeriod.today(),
        )
        assert isinstance(result, ComparisonResult)
        assert len(result.items) == 2
        assert result.winner_id in ("Line-1", "Line-2")
        assert result.difference >= 0

    @pytest.mark.asyncio
    async def test_compare_three_assets(self, adapter: ReneryoAdapter) -> None:
        """Compare OEE across 3 assets."""
        result = await adapter.compare(
            CanonicalMetric.OEE,
            ["Line-1", "Line-2", "Line-3"],
            TimePeriod.today(),
        )
        assert isinstance(result, ComparisonResult)
        assert len(result.items) == 3
        assert result.items[0].rank == 1


# =========================================================================
# Raw Data Tests
# =========================================================================


class TestGetRawDataFromMockServer:
    """Full round-trip raw data queries against mock RENERYO server."""

    @pytest.mark.asyncio
    async def test_get_raw_data(self, adapter: ReneryoAdapter) -> None:
        """Fetch raw measurement data from native endpoint."""
        result = await adapter.get_raw_data(
            CanonicalMetric.ENERGY_PER_UNIT,
            "Line-1",
            TimePeriod.today(),
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0].value > 0


# =========================================================================
# Auth Tests
# =========================================================================


class TestAuthFromMockServer:
    """Authentication integration tests."""

    @pytest.mark.asyncio
    async def test_cookie_auth_works(self, cookie_adapter: ReneryoAdapter) -> None:
        """Cookie-based auth works against mock server."""
        result = await cookie_adapter.get_kpi(
            CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)

    @pytest.mark.asyncio
    async def test_no_auth_fails(self) -> None:
        """Request without auth credentials fails with auth error."""
        adapter = ReneryoAdapter(
            api_url=MOCK_SERVER_URL,
            api_key="",
            timeout=5,
            auth_type="bearer",
        )
        await adapter.initialize()
        try:
            with pytest.raises(AdapterError) as exc_info:
                await adapter.get_kpi(
                    CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
                )
            assert exc_info.value.code in (
                "RENERYO_AUTH_FAILED",
                "RENERYO_SERVER_ERROR",
            )
        finally:
            await adapter.shutdown()
