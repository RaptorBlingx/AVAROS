"""
ReneryoAdapter Unit Tests

Tests the RENERYO adapter skeleton: all methods raise AdapterError,
platform_name is correct, capabilities are limited, and factory
integration works.
"""

import pytest

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.adapters.reneryo import ReneryoAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> ReneryoAdapter:
    """Create a ReneryoAdapter with test credentials."""
    return ReneryoAdapter(
        api_url="https://reneryo.example.com",
        api_key="test-key-123",
    )


@pytest.fixture
def period() -> TimePeriod:
    """Create a default time period for tests."""
    return TimePeriod.today()


@pytest.fixture(autouse=True)
def reset_adapter_registry() -> None:
    """Reset the class-level registry before each test."""
    original = dict(AdapterFactory._ADAPTER_REGISTRY)
    yield
    AdapterFactory._ADAPTER_REGISTRY = original


# ---------------------------------------------------------------------------
# Construction Tests
# ---------------------------------------------------------------------------


class TestReneryoAdapterConstruction:
    """Tests for ReneryoAdapter instantiation."""

    def test_instantiate_with_required_args(self) -> None:
        """ReneryoAdapter('url', 'key') creates without error."""
        adapter = ReneryoAdapter(api_url="https://api.test", api_key="key")
        assert adapter is not None

    def test_stores_api_url(self) -> None:
        """Constructor stores api_url."""
        adapter = ReneryoAdapter(api_url="https://api.test", api_key="key")
        assert adapter._api_url == "https://api.test"

    def test_stores_api_key(self) -> None:
        """Constructor stores api_key."""
        adapter = ReneryoAdapter(api_url="https://api.test", api_key="secret")
        assert adapter._api_key == "secret"

    def test_default_timeout(self) -> None:
        """Default timeout is 30 seconds."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        assert adapter._timeout == 30

    def test_custom_timeout(self) -> None:
        """Custom timeout overrides default."""
        adapter = ReneryoAdapter(api_url="url", api_key="key", timeout=60)
        assert adapter._timeout == 60

    def test_session_starts_none(self) -> None:
        """Session is None before initialize()."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        assert adapter._session is None

    def test_is_manufacturing_adapter(self) -> None:
        """ReneryoAdapter is a ManufacturingAdapter subclass."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        assert isinstance(adapter, ManufacturingAdapter)


# ---------------------------------------------------------------------------
# Query Method Tests — All Must Raise AdapterError
# ---------------------------------------------------------------------------


class TestReneryoAdapterQueryMethods:
    """All query methods raise AdapterError with RENERYO_NOT_CONNECTED."""

    @pytest.mark.asyncio
    async def test_get_kpi_raises_adapter_error(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """get_kpi() raises AdapterError with correct code."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=period,
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    async def test_compare_raises_adapter_error(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """compare() raises AdapterError with correct code."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.compare(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_ids=["Line-1", "Line-2"],
                period=period,
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    async def test_get_trend_raises_adapter_error(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """get_trend() raises AdapterError with correct code."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_trend(
                metric=CanonicalMetric.SCRAP_RATE,
                asset_id="Line-1",
                period=period,
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    async def test_get_raw_data_raises_adapter_error(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """get_raw_data() raises AdapterError with correct code."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_raw_data(
                metric=CanonicalMetric.CO2_PER_UNIT,
                asset_id="Furnace-1",
                period=period,
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", list(CanonicalMetric))
    async def test_get_kpi_raises_for_every_metric(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
        metric: CanonicalMetric,
    ) -> None:
        """Every CanonicalMetric raises AdapterError on get_kpi()."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=metric,
                asset_id="Line-1",
                period=period,
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    async def test_error_message_is_descriptive(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """Error message mentions RENERYO API not connected."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=period,
            )
        assert "not yet connected" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_error_platform_is_reneryo(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """Error platform field is 'reneryo'."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=period,
            )
        assert exc_info.value.platform == "reneryo"

    @pytest.mark.asyncio
    async def test_error_details_include_method_and_metric(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """Error message includes method name and metric value."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Line-1",
                period=period,
            )
        message = exc_info.value.message
        assert "get_kpi" in message
        assert "energy_per_unit" in message
        assert "/api/v1/kpis/energy/per-unit" in message


# ---------------------------------------------------------------------------
# Platform Name & Capability Tests
# ---------------------------------------------------------------------------


class TestReneryoAdapterCapabilities:
    """Tests for platform name and capability discovery."""

    def test_platform_name_is_reneryo(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """platform_name returns 'RENERYO'."""
        assert adapter.platform_name == "RENERYO"

    def test_supports_carbon_capability(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """RENERYO supports carbon tracking."""
        assert adapter.supports_capability("carbon") is True

    def test_supports_realtime_capability(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """RENERYO supports realtime data."""
        assert adapter.supports_capability("realtime") is True

    def test_does_not_support_whatif(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """RENERYO does not support what-if (requires DocuBoT)."""
        assert adapter.supports_capability("whatif") is False

    def test_does_not_support_anomaly_ml(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """RENERYO does not support anomaly_ml (requires PREVENTION)."""
        assert adapter.supports_capability("anomaly_ml") is False

    def test_get_supported_metrics_returns_all_mapped(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """get_supported_metrics() returns all metrics in endpoint map."""
        metrics = adapter.get_supported_metrics()
        assert len(metrics) == len(CanonicalMetric)
        for metric in CanonicalMetric:
            assert metric in metrics

    def test_endpoint_map_covers_all_metrics(self) -> None:
        """_ENDPOINT_MAP has an entry for every CanonicalMetric."""
        for metric in CanonicalMetric:
            assert metric in ReneryoAdapter._ENDPOINT_MAP, (
                f"Missing endpoint mapping for {metric.value}"
            )


# ---------------------------------------------------------------------------
# Lifecycle Tests
# ---------------------------------------------------------------------------


class TestReneryoAdapterLifecycle:
    """Tests for initialize() and shutdown() lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_does_not_raise(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """initialize() completes without error in skeleton mode."""
        await adapter.initialize()

    @pytest.mark.asyncio
    async def test_shutdown_does_not_raise(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """shutdown() completes without error."""
        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_clears_session(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """shutdown() sets session to None."""
        adapter._session = "fake-session"
        await adapter.shutdown()
        assert adapter._session is None


# ---------------------------------------------------------------------------
# Factory Integration Tests
# ---------------------------------------------------------------------------


class TestReneryoAdapterFactoryIntegration:
    """Tests for AdapterFactory + ReneryoAdapter integration."""

    def test_reneryo_in_available_platforms(self) -> None:
        """AdapterFactory.get_available_platforms() includes 'reneryo'."""
        platforms = AdapterFactory.get_available_platforms()
        assert "reneryo" in platforms

    def test_factory_creates_reneryo_adapter(self) -> None:
        """Factory with reneryo config creates ReneryoAdapter instance."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://reneryo.example.com"
        config.api_key = "test-key"
        config.timeout = 30
        settings.get_platform_config.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)

    def test_factory_reneryo_passes_config(self) -> None:
        """Factory passes api_url and api_key from settings to adapter."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-secret-key"
        config.timeout = 45
        settings.get_platform_config.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert adapter._api_url == "https://api.reneryo.test"
        assert adapter._api_key == "my-secret-key"
        assert adapter._timeout == 45

    def test_factory_reneryo_no_settings_uses_defaults(self) -> None:
        """Factory without settings still creates ReneryoAdapter with empty config."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = None
        config.api_key = None
        config.timeout = None
        settings.get_platform_config.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)
        assert adapter._api_url == ""
        assert adapter._api_key == ""
        assert adapter._timeout == 30
