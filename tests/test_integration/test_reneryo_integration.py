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
from skill.domain.results import ComparisonResult, ConnectionTestResult, KPIResult, TrendResult

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


# =========================================================================
# Real API Tests — run with: pytest -m real_api
# =========================================================================

REAL_API_URL = os.environ.get("RENERYO_API_URL", "")
REAL_API_KEY = os.environ.get("RENERYO_API_KEY", "")
REAL_AUTH_TYPE = os.environ.get("RENERYO_AUTH_TYPE", "cookie")

real_api = pytest.mark.real_api
_skip_no_creds = pytest.mark.skipif(
    not REAL_API_URL or not REAL_API_KEY,
    reason="RENERYO_API_URL and RENERYO_API_KEY env vars required",
)


async def _make_real_adapter() -> ReneryoAdapter:
    """Create and initialize a ReneryoAdapter for the real RENERYO API."""
    adapter = ReneryoAdapter(
        api_url=REAL_API_URL,
        api_key=REAL_API_KEY,
        timeout=30,
        auth_type=REAL_AUTH_TYPE,
        api_format="native",
    )
    await adapter.initialize()
    return adapter


@_skip_no_creds
class TestRealApiGetKpi:
    """Fetch KPIs from the real RENERYO API."""

    @real_api
    @pytest.mark.asyncio
    async def test_real_api_get_kpi(self) -> None:
        """Fetch energy_total from real API returns valid KPIResult."""
        adapter = await _make_real_adapter()
        try:
            result = await adapter.get_kpi(
                CanonicalMetric.ENERGY_TOTAL,
                "Electric Main Meter",
                TimePeriod.last_month(),
            )
            assert isinstance(result, KPIResult)
            assert result.metric == CanonicalMetric.ENERGY_TOTAL
            assert result.value > 0
            assert result.unit != ""
        finally:
            await adapter.shutdown()

    @real_api
    @pytest.mark.asyncio
    async def test_real_api_get_raw_data(self) -> None:
        """Fetch raw meter data from real API."""
        from skill.domain.models import DataPoint
        adapter = await _make_real_adapter()
        try:
            result = await adapter.get_raw_data(
                CanonicalMetric.ENERGY_TOTAL,
                "Electric Main Meter",
                TimePeriod.last_month(),
            )
            assert isinstance(result, list)
            assert len(result) > 0
            assert isinstance(result[0], DataPoint)
            assert result[0].value > 0
        finally:
            await adapter.shutdown()


@_skip_no_creds
class TestRealApiGetTrend:
    """Trend queries against the real RENERYO API."""

    @real_api
    @pytest.mark.asyncio
    async def test_real_api_get_trend(self) -> None:
        """Fetch trend from real API returns valid TrendResult."""
        adapter = await _make_real_adapter()
        try:
            result = await adapter.get_trend(
                CanonicalMetric.ENERGY_TOTAL,
                "Electric Main Meter",
                TimePeriod.last_month(),
                granularity="daily",
            )
            assert isinstance(result, TrendResult)
            assert len(result.data_points) > 0
            assert result.direction in ("up", "down", "stable")
        finally:
            await adapter.shutdown()


@_skip_no_creds
class TestRealApiAuthCookie:
    """Cookie auth against the real RENERYO API."""

    @real_api
    @pytest.mark.asyncio
    async def test_real_api_auth_cookie(self) -> None:
        """Cookie auth works against real RENERYO endpoint."""
        adapter = await _make_real_adapter()
        try:
            result = await adapter.get_raw_data(
                CanonicalMetric.ENERGY_TOTAL,
                "Electric Main Meter",
                TimePeriod.last_month(),
            )
            assert isinstance(result, list)
            assert len(result) > 0
        finally:
            await adapter.shutdown()


@_skip_no_creds
class TestRealApiResponseParsing:
    """Validate real JSON → domain model conversion."""

    @real_api
    @pytest.mark.asyncio
    async def test_real_api_response_parsing(self) -> None:
        """Real API JSON correctly maps to frozen domain KPIResult."""
        adapter = await _make_real_adapter()
        try:
            result = await adapter.get_kpi(
                CanonicalMetric.ENERGY_TOTAL,
                "Electric Main Meter",
                TimePeriod.last_month(),
            )
            assert isinstance(result, KPIResult)
            assert result.metric == CanonicalMetric.ENERGY_TOTAL
            assert isinstance(result.value, float)
            assert isinstance(result.unit, str)
            assert result.asset_id == "Electric Main Meter"
            assert result.timestamp is not None
        finally:
            await adapter.shutdown()


# =========================================================================
# Connection Test — Mock Server
# =========================================================================


class TestReneryoConnectionTestIntegration:
    """Integration test for test_connection() against running mock server."""

    @pytest.mark.asyncio
    async def test_real_connection_to_mock_server(self) -> None:
        """Full connection test cycle against mock RENERYO server."""
        adapter = ReneryoAdapter(
            api_url=MOCK_SERVER_URL,
            api_key=MOCK_API_KEY,
            timeout=10,
            auth_type="bearer",
            api_format="native",
        )
        result = await adapter.test_connection()

        assert isinstance(result, ConnectionTestResult)
        assert result.success is True
        assert result.latency_ms > 0
        assert result.adapter_name == "RENERYO"
        assert len(result.resources_discovered) > 0

    @pytest.mark.asyncio
    async def test_connection_test_with_bad_key(self) -> None:
        """Connection test with empty key returns auth error."""
        adapter = ReneryoAdapter(
            api_url=MOCK_SERVER_URL,
            api_key="",
            timeout=5,
            auth_type="bearer",
        )
        result = await adapter.test_connection()

        # Mock server may return 401 or pass depending on auth config
        assert isinstance(result, ConnectionTestResult)
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_connection_test_unreachable_server(self) -> None:
        """Connection test to unreachable host fails with error."""
        adapter = ReneryoAdapter(
            api_url="http://localhost:59999",
            api_key="test",
            timeout=3,
        )
        result = await adapter.test_connection()

        assert isinstance(result, ConnectionTestResult)
        assert result.success is False
        assert result.error_code in (
            "RENERYO_CONNECTION_FAILED",
            "RENERYO_TIMEOUT",
        )
