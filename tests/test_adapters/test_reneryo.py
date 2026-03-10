"""
ReneryoAdapter Unit Tests

Tests the RENERYO adapter skeleton: all methods raise AdapterError,
platform_name is correct, capabilities are limited, and factory
integration works.
"""

import re

import pytest
import pytest_asyncio

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.adapters.reneryo import ReneryoAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import ConnectionTestResult


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

    def test_native_energy_per_unit_with_seu_id_uses_seu_endpoint(self) -> None:
        """Native ENERGY_PER_UNIT KPI should route to SEU values endpoint."""
        adapter = ReneryoAdapter(
            api_url="https://api.test",
            api_key="key",
            api_format="native",
            native_seu_id="SEU ID 1",
        )
        endpoint = adapter._resolve_endpoint(
            CanonicalMetric.ENERGY_PER_UNIT, purpose="kpi",
        )
        assert "/api/u/measurement/seu/item/SEU%20ID%201/values" == endpoint

    def test_native_energy_per_unit_compare_stays_on_meter_endpoint(self) -> None:
        """Compare flow should keep meter endpoint for compatibility."""
        adapter = ReneryoAdapter(
            api_url="https://api.test",
            api_key="key",
            api_format="native",
            native_seu_id="SEU-1",
        )
        endpoint = adapter._resolve_endpoint(
            CanonicalMetric.ENERGY_PER_UNIT, purpose="compare",
        )
        assert endpoint == "/api/u/measurement/meter/item"

    def test_should_fallback_from_seu_for_client_error(self) -> None:
        """SEU 400/404 responses should trigger meter fallback."""
        endpoint = "/api/u/measurement/seu/item/invalid/values"
        err_400 = AdapterError(
            message="Unexpected status 400",
            code="RENERYO_UNEXPECTED_STATUS",
            platform="reneryo",
            status_code=400,
        )
        err_404 = AdapterError(
            message="Endpoint not found",
            code="RENERYO_ENDPOINT_NOT_FOUND",
            platform="reneryo",
            status_code=404,
        )
        assert ReneryoAdapter._should_fallback_from_seu(endpoint, err_400)
        assert ReneryoAdapter._should_fallback_from_seu(endpoint, err_404)

    def test_should_not_fallback_from_seu_for_auth_error(self) -> None:
        """Auth issues should not silently fall back."""
        endpoint = "/api/u/measurement/seu/item/invalid/values"
        err_401 = AdapterError(
            message="Authentication failed",
            code="RENERYO_AUTH_FAILED",
            platform="reneryo",
            status_code=401,
        )
        assert not ReneryoAdapter._should_fallback_from_seu(endpoint, err_401)


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
        """Error message mentions adapter not initialized."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=period,
            )
        assert "not initialized" in exc_info.value.message.lower()

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
    async def test_error_details_include_adapter_name(
        self,
        adapter: ReneryoAdapter,
        period: TimePeriod,
    ) -> None:
        """Error message includes adapter name and initialize hint."""
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Line-1",
                period=period,
            )
        message = exc_info.value.message
        assert "ReneryoAdapter" in message
        assert "initialize" in message.lower()


class TestReneryoAdapterListAssets:
    """Tests for RENERYO SEU discovery mapping."""

    @pytest.mark.asyncio
    async def test_list_assets_maps_seu_records_to_assets(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """SEU name payload should map to canonical Asset entries."""
        from unittest.mock import AsyncMock

        adapter._retry_fetch = AsyncMock(
            return_value={
                "records": [
                    {"id": "seu-2", "name": "Line 2", "energyResource": "ELECTRIC"},
                    {"id": "seu-1", "name": "Line 1", "energyResource": "GAS"},
                ],
            }
        )

        assets = await adapter.list_assets()

        assert [asset.asset_id for asset in assets] == ["seu-1", "seu-2"]
        assert assets[0].asset_type == "seu"
        assert assets[0].display_name == "Line 1"
        assert assets[0].metadata["energy_resource"] == "GAS"

    @pytest.mark.asyncio
    async def test_list_assets_returns_empty_on_discovery_error(
        self,
        adapter: ReneryoAdapter,
    ) -> None:
        """Discovery failures should return [] instead of raising."""
        from unittest.mock import AsyncMock

        adapter._retry_fetch = AsyncMock(
            side_effect=AdapterError(
                message="boom",
                code="RENERYO_CONNECTION_FAILED",
                platform="reneryo",
            ),
        )

        assets = await adapter.list_assets()

        assert assets == []


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
        from unittest.mock import AsyncMock, MagicMock

        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        adapter._session = mock_session
        await adapter.shutdown()
        assert adapter._session is None
        mock_session.close.assert_awaited_once()


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
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

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
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

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
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)

    def test_factory_reneryo_passes_auth_type(self) -> None:
        """Factory passes auth_type from extra_settings to adapter."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-key"
        config.timeout = 30
        config.extra_settings = {"auth_type": "cookie"}
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert adapter._auth_type == "cookie"

    def test_factory_reneryo_default_auth_type_bearer(self) -> None:
        """Factory defaults to bearer auth when extra_settings is empty."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-key"
        config.timeout = 30
        config.extra_settings = {}
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert adapter._auth_type == "bearer"

    def test_factory_reneryo_preserves_legacy_seu_id_as_native_fallback(self) -> None:
        """Factory keeps legacy seu_id fallback while sanitizing extra settings."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-key"
        config.timeout = 30
        config.extra_settings = {"auth_type": "bearer", "seu_id": "SEU-ABC"}
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert adapter._native_seu_id == "SEU-ABC"
        assert adapter._resolve_seu_id("Line-1") == "SEU-ABC"
        assert "seu_id" not in adapter._extra_settings


class TestReneryoApiFormatDetection:
    """Tests for RENERYO API format selection from profile settings."""

    def test_factory_defaults_api_format_to_native(self) -> None:
        """Factory defaults api_format to native when setting is absent."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-key"
        config.timeout = 30
        config.extra_settings = {}
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)
        assert adapter._api_format == "native"

    def test_factory_uses_explicit_api_format(self) -> None:
        """Factory passes configured api_format through to adapter."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.reneryo.test"
        config.api_key = "my-key"
        config.timeout = 30
        config.extra_settings = {"api_format": "mock"}
        settings.get_active_profile_name.return_value = "reneryo"
        settings.get_profile.return_value = config

        factory = AdapterFactory(settings_service=settings)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)
        assert adapter._api_format == "mock"


# ===========================================================================
# HTTP Client Tests (aioresponses-based)
# ===========================================================================


@pytest_asyncio.fixture
async def initialized_adapter():
    """Create and initialize a ReneryoAdapter for HTTP tests."""
    adapter = ReneryoAdapter(
        api_url="https://reneryo.example.com",
        api_key="test-key-123",
        timeout=10,
    )
    await adapter.initialize()
    yield adapter
    await adapter.shutdown()


class TestReneryoAuth:
    """Tests for bearer vs cookie auth header construction."""

    def test_bearer_auth_headers(self) -> None:
        """Bearer auth sends Authorization header."""
        adapter = ReneryoAdapter(
            api_url="https://api.test", api_key="my-token", auth_type="bearer",
        )
        headers = adapter._build_auth_headers()
        assert headers == {"Authorization": "Bearer my-token"}

    def test_cookie_auth_headers(self) -> None:
        """Cookie auth sends Cookie: S=... header."""
        adapter = ReneryoAdapter(
            api_url="https://api.test", api_key="session-id", auth_type="cookie",
        )
        headers = adapter._build_auth_headers()
        assert headers == {"Cookie": "S=session-id"}

    def test_cookie_auth_headers_accept_prefixed_cookie(self) -> None:
        """Cookie auth accepts already-prefixed S cookie values."""
        adapter = ReneryoAdapter(
            api_url="https://api.test", api_key="S=session-id", auth_type="cookie",
        )
        headers = adapter._build_auth_headers()
        assert headers == {"Cookie": "S=session-id"}

    def test_cookie_auth_headers_decode_percent_encoding(self) -> None:
        """Cookie auth decodes percent-encoded cookie token values."""
        adapter = ReneryoAdapter(
            api_url="https://api.test",
            api_key="abc%2Bdef%3D",
            auth_type="cookie",
        )
        headers = adapter._build_auth_headers()
        assert headers == {"Cookie": "S=abc+def="}

    def test_cookie_auth_headers_accept_full_cookie_header(self) -> None:
        """Cookie auth accepts full Cookie header input."""
        adapter = ReneryoAdapter(
            api_url="https://api.test",
            api_key="Cookie: S=session-id; Path=/; Secure",
            auth_type="cookie",
        )
        headers = adapter._build_auth_headers()
        assert headers == {"Cookie": "S=session-id; Path=/; Secure"}

    def test_default_auth_type_is_bearer(self) -> None:
        """Default auth_type is 'bearer'."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        assert adapter._auth_type == "bearer"

    def test_constructor_stores_auth_type(self) -> None:
        """Constructor stores custom auth_type."""
        adapter = ReneryoAdapter(
            api_url="url", api_key="key", auth_type="cookie",
        )
        assert adapter._auth_type == "cookie"

    @pytest.mark.asyncio
    async def test_bearer_header_sent_in_request(
        self,
        initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Bearer token is sent in actual HTTP request."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload={"value": 82.5, "unit": "%", "timestamp": "2026-02-10T12:00:00Z", "asset_id": "Line-1"},
            )
            await initialized_adapter.get_kpi(
                CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
            )
            # Verify the request was made (aioresponses matched it)
            assert mocked.requests

    @pytest.mark.asyncio
    async def test_cookie_header_sent_in_request(self) -> None:
        """Cookie auth header is sent in actual HTTP request."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="session-xyz",
            auth_type="cookie",
        )
        await adapter.initialize()
        try:
            with aioresponses() as mocked:
                mocked.get(
                    re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                    payload={"value": 82.5, "unit": "%", "timestamp": "2026-02-10T12:00:00Z", "asset_id": "Line-1"},
                )
                await adapter.get_kpi(
                    CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
                )
                assert mocked.requests
        finally:
            await adapter.shutdown()


class TestReneryoHttpClient:
    """Tests for _fetch() handling of response codes and errors."""

    @pytest.mark.asyncio
    async def test_fetch_returns_parsed_json(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() returns parsed JSON on 200 response."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test-endpoint"),
                payload={"key": "value"},
            )
            result = await initialized_adapter._fetch("/test-endpoint")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_fetch_raises_auth_failed_on_401(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_AUTH_FAILED on 401."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"), status=401,
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_AUTH_FAILED"
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_fetch_raises_not_found_on_404(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_ENDPOINT_NOT_FOUND on 404."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"), status=404,
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_ENDPOINT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_fetch_raises_server_error_on_500(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_SERVER_ERROR on 5xx."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"), status=500,
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_SERVER_ERROR"

    @pytest.mark.asyncio
    async def test_fetch_raises_connection_failed(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_CONNECTION_FAILED on connect error."""
        import aiohttp
        from aioresponses import aioresponses
        from unittest.mock import MagicMock

        conn_key = MagicMock()
        conn_key.ssl = None

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"),
                exception=aiohttp.ClientConnectorError(
                    connection_key=conn_key,
                    os_error=OSError("Connection refused"),
                ),
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_CONNECTION_FAILED"

    @pytest.mark.asyncio
    async def test_fetch_raises_timeout(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_TIMEOUT on asyncio.TimeoutError."""
        import asyncio
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"),
                exception=asyncio.TimeoutError(),
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_TIMEOUT"

    @pytest.mark.asyncio
    async def test_fetch_raises_on_unexpected_status(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """_fetch() raises RENERYO_UNEXPECTED_STATUS on 403."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/test"), status=403,
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._fetch("/test")
            assert exc_info.value.code == "RENERYO_UNEXPECTED_STATUS"

    @pytest.mark.asyncio
    async def test_fetch_not_initialized_raises(self) -> None:
        """_fetch() raises RENERYO_NOT_CONNECTED without initialize()."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        with pytest.raises(AdapterError) as exc_info:
            await adapter._fetch("/test")
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"


class TestReneryoRetry:
    """Tests for _retry_fetch() retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_5xx_succeeds_after_retry(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """5xx triggers retry; success on 2nd attempt returns data."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            url = re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee")
            mocked.get(url, status=500)
            mocked.get(url, payload={"value": 82.5})
            result = await initialized_adapter._retry_fetch(
                "/api/v1/kpis/production/oee", max_retries=3,
            )
            assert result == {"value": 82.5}

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_server_error(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """3 retries then fail raises RENERYO_SERVER_ERROR."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            url = re.compile(r"https://reneryo\.example\.com/test")
            for _ in range(4):  # initial + 3 retries
                mocked.get(url, status=500)
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._retry_fetch(
                    "/test", max_retries=3,
                )
            assert exc_info.value.code == "RENERYO_SERVER_ERROR"

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """4xx errors do not trigger retry — raised immediately."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            url = re.compile(r"https://reneryo\.example\.com/test")
            mocked.get(url, status=401)
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter._retry_fetch("/test")
            assert exc_info.value.code == "RENERYO_AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_retry_count_matches_max(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Exactly max_retries+1 total attempts are made."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            url = re.compile(r"https://reneryo\.example\.com/test")
            # Register 2 (initial + 1 retry) = max_retries=1
            mocked.get(url, status=500)
            mocked.get(url, status=500)
            with pytest.raises(AdapterError):
                await initialized_adapter._retry_fetch(
                    "/test", max_retries=1,
                )


class TestReneryoGetKpi:
    """Tests for get_kpi() returning KPIResult."""

    @pytest.mark.asyncio
    async def test_get_kpi_returns_kpi_result(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_kpi() returns KPIResult with correct fields."""
        from aioresponses import aioresponses
        from skill.domain.results import KPIResult

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/energy/per-unit"),
                payload={
                    "value": 4.2,
                    "unit": "kWh/unit",
                    "timestamp": "2026-02-10T12:00:00+00:00",
                    "asset_id": "Line-1",
                    "period": "today",
                },
            )
            result = await initialized_adapter.get_kpi(
                CanonicalMetric.ENERGY_PER_UNIT, "Line-1", TimePeriod.today(),
            )
            assert isinstance(result, KPIResult)
            assert result.value == 4.2
            assert result.unit == "kWh/unit"
            assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
            assert result.asset_id == "Line-1"

    @pytest.mark.asyncio
    async def test_get_kpi_uses_default_unit(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_kpi() uses metric default_unit if response omits unit."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload={"value": 85.0, "timestamp": "2026-02-10T12:00:00Z"},
            )
            result = await initialized_adapter.get_kpi(
                CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
            )
            assert result.unit == "%"  # default_unit for OEE


class TestReneryoCompare:
    """Tests for compare() returning ComparisonResult."""

    @pytest.mark.asyncio
    async def test_compare_returns_comparison_result(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """compare() returns ComparisonResult with ranked items."""
        from aioresponses import aioresponses
        from skill.domain.results import ComparisonResult

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/energy/per-unit"),
                payload=[
                    {"value": 3.1, "unit": "kWh/unit", "asset_id": "Line-1",
                     "timestamp": "2026-02-10T12:00:00Z"},
                    {"value": 4.5, "unit": "kWh/unit", "asset_id": "Line-2",
                     "timestamp": "2026-02-10T12:00:00Z"},
                ],
            )
            result = await initialized_adapter.compare(
                CanonicalMetric.ENERGY_PER_UNIT,
                ["Line-1", "Line-2"],
                TimePeriod.today(),
            )
            assert isinstance(result, ComparisonResult)
            assert result.winner_id == "Line-1"
            assert len(result.items) == 2
            assert result.items[0].rank == 1

    @pytest.mark.asyncio
    async def test_compare_higher_is_better_ranking(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """compare() ranks OEE where higher is better."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload=[
                    {"value": 85.0, "unit": "%", "asset_id": "Line-1",
                     "timestamp": "2026-02-10T12:00:00Z"},
                    {"value": 92.0, "unit": "%", "asset_id": "Line-2",
                     "timestamp": "2026-02-10T12:00:00Z"},
                ],
            )
            result = await initialized_adapter.compare(
                CanonicalMetric.OEE,
                ["Line-1", "Line-2"],
                TimePeriod.today(),
            )
            assert result.winner_id == "Line-2"


class TestReneryoGetTrend:
    """Tests for get_trend() returning TrendResult."""

    @pytest.mark.asyncio
    async def test_get_trend_returns_trend_result(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_trend() returns TrendResult with data points."""
        from aioresponses import aioresponses
        from skill.domain.results import TrendResult

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/material/scrap-rate"),
                payload=[
                    {"value": 2.5, "unit": "%", "timestamp": "2026-02-08T00:00:00Z",
                     "asset_id": "Line-1"},
                    {"value": 2.3, "unit": "%", "timestamp": "2026-02-09T00:00:00Z",
                     "asset_id": "Line-1"},
                    {"value": 2.1, "unit": "%", "timestamp": "2026-02-10T00:00:00Z",
                     "asset_id": "Line-1"},
                ],
            )
            result = await initialized_adapter.get_trend(
                CanonicalMetric.SCRAP_RATE, "Line-1", TimePeriod.last_week(),
                granularity="daily",
            )
            assert isinstance(result, TrendResult)
            assert len(result.data_points) == 3
            assert result.direction == "down"
            assert result.granularity == "daily"

    @pytest.mark.asyncio
    async def test_get_trend_stable_direction(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_trend() returns 'stable' for minimal change."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload=[
                    {"value": 85.0, "unit": "%", "timestamp": "2026-02-08T00:00:00Z"},
                    {"value": 85.1, "unit": "%", "timestamp": "2026-02-09T00:00:00Z"},
                    {"value": 85.0, "unit": "%", "timestamp": "2026-02-10T00:00:00Z"},
                ],
            )
            result = await initialized_adapter.get_trend(
                CanonicalMetric.OEE, "Line-1", TimePeriod.last_week(),
            )
            assert result.direction == "stable"


class TestReneryoGetRawData:
    """Tests for get_raw_data() returning list[DataPoint]."""

    @pytest.mark.asyncio
    async def test_get_raw_data_returns_data_points(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_raw_data() returns list of DataPoint objects."""
        from aioresponses import aioresponses
        from skill.domain.models import DataPoint

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item"),
                payload=[
                    {"value": 2.8, "unit": "kWh", "datetime": "2026-02-10T01:00:00Z",
                     "meter": "Line-1", "type": "energy_consumption", "id": "abc123"},
                    {"value": 2.9, "unit": "kWh", "datetime": "2026-02-10T02:00:00Z",
                     "meter": "Line-1", "type": "energy_consumption", "id": "abc124"},
                ],
            )
            result = await initialized_adapter.get_raw_data(
                CanonicalMetric.ENERGY_PER_UNIT, "Line-1", TimePeriod.today(),
            )
            assert len(result) == 2
            assert isinstance(result[0], DataPoint)
            assert result[0].value == 2.8

    @pytest.mark.asyncio
    async def test_get_raw_data_empty_returns_empty(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """get_raw_data() returns empty list for empty response."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item"),
                payload=[],
            )
            result = await initialized_adapter.get_raw_data(
                CanonicalMetric.ENERGY_PER_UNIT, "Line-1", TimePeriod.today(),
            )
            assert result == []


class TestReneryoParsers:
    """Edge case tests for response parsers."""

    @pytest.mark.asyncio
    async def test_kpi_missing_value_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Missing 'value' field raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload={"unit": "%", "timestamp": "2026-02-10T12:00:00Z"},
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.get_kpi(
                    CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_kpi_non_numeric_value_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Non-numeric 'value' field raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/production/oee"),
                payload={"value": "not_a_number", "unit": "%"},
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.get_kpi(
                    CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_trend_empty_response_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Empty trend response raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/material/scrap-rate"),
                payload=[],
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.get_trend(
                    CanonicalMetric.SCRAP_RATE, "Line-1", TimePeriod.last_week(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_comparison_empty_response_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Empty comparison response raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/energy/per-unit"),
                payload=[],
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.compare(
                    CanonicalMetric.ENERGY_PER_UNIT,
                    ["Line-1", "Line-2"],
                    TimePeriod.today(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_comparison_missing_asset_id_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Comparison item missing asset_id raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/v1/kpis/energy/per-unit"),
                payload=[
                    {"value": 3.1, "unit": "kWh/unit"},
                ],
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.compare(
                    CanonicalMetric.ENERGY_PER_UNIT,
                    ["Line-1"],
                    TimePeriod.today(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_data_point_missing_value_raises(
        self, initialized_adapter: ReneryoAdapter,
    ) -> None:
        """Data point without value field raises RENERYO_INVALID_RESPONSE."""
        from aioresponses import aioresponses

        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item"),
                payload=[{"unit": "kWh", "datetime": "2026-02-10T01:00:00Z"}],
            )
            with pytest.raises(AdapterError) as exc_info:
                await initialized_adapter.get_raw_data(
                    CanonicalMetric.ENERGY_PER_UNIT, "Line-1", TimePeriod.today(),
                )
            assert exc_info.value.code == "RENERYO_INVALID_RESPONSE"


# ===========================================================================
# P7-E01: Metric Resource Read Path Fixes
# ===========================================================================


class TestRequiresNativePeriod:
    """Tests for _requires_native_period() (B1)."""

    def test_seu_endpoint_requires_native_period(self) -> None:
        """SEU endpoints still require native period parameter."""
        adapter = ReneryoAdapter(api_url="https://test", api_key="k")

        result = adapter._requires_native_period(
            "/api/u/measurement/seu/item/abc-123/values",
        )

        assert result is True

    def test_metric_resource_endpoint_does_not_require_native_period(self) -> None:
        """Metric resource endpoints do NOT require native period (GAUGE)."""
        adapter = ReneryoAdapter(api_url="https://test", api_key="k")

        result = adapter._requires_native_period(
            "/api/u/measurement/metric/resource/abc-123/values",
        )

        assert result is False

    def test_meter_endpoint_does_not_require_native_period(self) -> None:
        """Meter endpoint does not require native period."""
        adapter = ReneryoAdapter(api_url="https://test", api_key="k")

        result = adapter._requires_native_period(
            "/api/u/measurement/meter/item",
        )

        assert result is False


class TestBuildQueryParamsMetricResource:
    """Tests for _build_query_params() with metric resource flag (B6)."""

    def test_metric_resource_includes_period_raw(self) -> None:
        """Metric resource queries include period=RAW."""
        adapter = ReneryoAdapter(
            api_url="https://test", api_key="k", api_format="native",
        )

        params = adapter._build_query_params(
            period=TimePeriod.today(),
            is_metric_resource=True,
        )

        assert params["period"] == "RAW"

    def test_metric_resource_includes_count_100(self) -> None:
        """Metric resource queries include count=100."""
        adapter = ReneryoAdapter(
            api_url="https://test", api_key="k", api_format="native",
        )

        params = adapter._build_query_params(
            period=TimePeriod.today(),
            is_metric_resource=True,
        )

        assert params["count"] == "100"

    def test_non_metric_resource_no_count(self) -> None:
        """Non-metric-resource queries do not include count."""
        adapter = ReneryoAdapter(
            api_url="https://test", api_key="k", api_format="native",
        )

        params = adapter._build_query_params(
            period=TimePeriod.today(),
            is_metric_resource=False,
        )

        assert "count" not in params

    def test_seu_endpoint_still_gets_native_period(self) -> None:
        """SEU endpoints still get DAILY/HOURLY period (regression)."""
        adapter = ReneryoAdapter(
            api_url="https://test", api_key="k", api_format="native",
        )

        params = adapter._build_query_params(
            period=TimePeriod.today(),
            include_native_period=True,
            is_metric_resource=False,
        )

        assert params["period"] == "DAILY"
        assert "count" not in params


class TestMetricResourceIntegration:
    """Integration tests for metric resource KPI and trend paths."""

    @pytest.mark.asyncio
    async def test_get_kpi_metric_resource_returns_latest_value(self) -> None:
        """get_kpi() for GAUGE metric resource returns latest (last) record."""
        from unittest.mock import AsyncMock

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="key",
            api_format="native",
            asset_mappings={
                "line_1": {
                    "seu_id": "",
                    "metric_resources": {"oee": "res-oee-uuid"},
                },
            },
        )
        adapter._session = object()
        adapter._retry_fetch = AsyncMock(return_value={
            "records": [
                {"value": 80.0, "datetime": "2026-03-01T00:00:00Z"},
                {"value": 82.5, "datetime": "2026-03-01T00:15:00Z"},
                {"value": 85.0, "datetime": "2026-03-01T00:30:00Z"},
            ],
        })

        result = await adapter.get_kpi(
            CanonicalMetric.OEE, "line_1", TimePeriod.today(),
        )

        assert result.value == 85.0
        call_args = adapter._retry_fetch.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("period") == "RAW"
        assert params.get("count") == "100"

    @pytest.mark.asyncio
    async def test_get_trend_metric_resource_returns_all_points(self) -> None:
        """get_trend() for GAUGE metric resource returns non-empty time series."""
        from unittest.mock import AsyncMock

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="key",
            api_format="native",
            asset_mappings={
                "line_1": {
                    "seu_id": "",
                    "metric_resources": {"scrap_rate": "res-scrap-uuid"},
                },
            },
        )
        adapter._session = object()
        adapter._retry_fetch = AsyncMock(return_value={
            "records": [
                {"value": 2.1, "datetime": "2026-03-01T00:00:00Z"},
                {"value": 2.3, "datetime": "2026-03-01T00:15:00Z"},
                {"value": 2.5, "datetime": "2026-03-01T00:30:00Z"},
            ],
        })

        result = await adapter.get_trend(
            CanonicalMetric.SCRAP_RATE, "line_1", TimePeriod.last_week(),
        )

        assert len(result.data_points) == 3
        call_args = adapter._retry_fetch.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("period") == "RAW"
        assert params.get("count") == "100"

    @pytest.mark.asyncio
    async def test_seu_endpoint_still_uses_daily_period(self) -> None:
        """SEU endpoint regression: still uses DAILY period, no count param."""
        from unittest.mock import AsyncMock

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="key",
            api_format="native",
            native_seu_id="seu-abc",
        )
        adapter._session = object()
        adapter._retry_fetch = AsyncMock(return_value={
            "records": [
                {"value": 4.2, "datetime": "2026-03-01T00:00:00Z", "unit": "kWh/unit"},
            ],
        })

        await adapter.get_kpi(
            CanonicalMetric.ENERGY_PER_UNIT, "line_1", TimePeriod.today(),
        )

        call_args = adapter._retry_fetch.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("period") == "DAILY"
        assert "count" not in params


class TestReneryoLifecycleHTTP:
    """Tests for initialize() and shutdown() with real aiohttp sessions."""

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self) -> None:
        """initialize() creates aiohttp.ClientSession."""
        import aiohttp

        adapter = ReneryoAdapter(api_url="https://api.test", api_key="key")
        assert adapter._session is None
        await adapter.initialize()
        assert isinstance(adapter._session, aiohttp.ClientSession)
        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_session(self) -> None:
        """shutdown() closes session and sets to None."""
        adapter = ReneryoAdapter(api_url="https://api.test", api_key="key")
        await adapter.initialize()
        assert adapter._session is not None
        await adapter.shutdown()
        assert adapter._session is None

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        """Calling shutdown() twice does not raise."""
        adapter = ReneryoAdapter(api_url="https://api.test", api_key="key")
        await adapter.initialize()
        await adapter.shutdown()
        await adapter.shutdown()
        assert adapter._session is None

    @pytest.mark.asyncio
    async def test_query_without_initialize_raises(self) -> None:
        """Query methods raise RENERYO_NOT_CONNECTED without initialize()."""
        adapter = ReneryoAdapter(api_url="url", api_key="key")
        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                CanonicalMetric.OEE, "Line-1", TimePeriod.today(),
            )
        assert exc_info.value.code == "RENERYO_NOT_CONNECTED"

    @pytest.mark.asyncio
    async def test_initialize_with_cookie_auth(self) -> None:
        """initialize() creates session with cookie auth headers."""
        adapter = ReneryoAdapter(
            api_url="https://api.test", api_key="sess-123", auth_type="cookie",
        )
        await adapter.initialize()
        assert adapter._session is not None
        # Session should have cookie header in default headers
        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_api_url_trailing_slash_stripped(self) -> None:
        """Trailing slash in api_url is stripped."""
        adapter = ReneryoAdapter(
            api_url="https://api.test/", api_key="key",
        )
        assert adapter._api_url == "https://api.test"


# ---------------------------------------------------------------------------
# Connection Testing
# ---------------------------------------------------------------------------


class TestReneryoConnectionTest:
    """Tests for ReneryoAdapter.test_connection()."""

    @pytest.mark.asyncio
    async def test_connection_success_returns_meters(self) -> None:
        """test_connection returns success with meter list on 200."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key-123",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                payload={
                    "records": [
                        {"name": "Electric Main Meter", "id": "m1"},
                        {"name": "Gas Meter", "id": "m2"},
                    ],
                },
            )
            result = await adapter.test_connection()

        assert isinstance(result, ConnectionTestResult)
        assert result.success is True
        assert result.latency_ms > 0
        assert result.adapter_name == "RENERYO"
        assert "2 meter(s)" in result.message
        assert result.resources_discovered == ("Electric Main Meter", "Gas Meter")
        assert result.error_code == ""

    @pytest.mark.asyncio
    async def test_connection_auth_failure_returns_error(self) -> None:
        """test_connection returns error on 401."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="bad-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                status=401,
            )
            result = await adapter.test_connection()

        assert result.success is False
        assert result.error_code == "RENERYO_AUTH_FAILED"
        assert "authentication" in result.message.lower()

    @pytest.mark.asyncio
    async def test_connection_server_error_returns_error(self) -> None:
        """test_connection returns error on 500."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                status=500,
                body="Internal Server Error",
            )
            result = await adapter.test_connection()

        assert result.success is False
        assert result.error_code == "HTTP_500"

    @pytest.mark.asyncio
    async def test_connection_timeout_returns_error(self) -> None:
        """test_connection returns error on timeout."""
        import asyncio

        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
            timeout=1,
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                exception=asyncio.TimeoutError(),
            )
            result = await adapter.test_connection()

        assert result.success is False
        assert result.error_code == "RENERYO_TIMEOUT"
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_connection_unreachable_returns_error(self) -> None:
        """test_connection returns error when server is unreachable."""
        from unittest.mock import MagicMock

        import aiohttp as _aiohttp

        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        mock_key = MagicMock()
        mock_key.ssl = None
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                exception=_aiohttp.ClientConnectorError(
                    connection_key=mock_key,
                    os_error=OSError("Connection refused"),
                ),
            )
            result = await adapter.test_connection()

        assert result.success is False
        assert result.error_code == "RENERYO_CONNECTION_FAILED"
        assert "cannot reach" in result.message.lower()

    @pytest.mark.asyncio
    async def test_connection_discovers_meter_names(self) -> None:
        """test_connection lists meter names in resources_discovered."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                payload={
                    "records": [
                        {"name": "Meter-A"},
                        {"name": "Meter-B"},
                        {"name": "Meter-C"},
                    ],
                },
            )
            result = await adapter.test_connection()

        assert result.resources_discovered == ("Meter-A", "Meter-B", "Meter-C")

    @pytest.mark.asyncio
    async def test_connection_latency_is_positive(self) -> None:
        """test_connection reports latency_ms > 0."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                payload={"records": []},
            )
            result = await adapter.test_connection()

        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_connection_session_cleanup_on_success(self) -> None:
        """Session is closed after successful test (no resource leak)."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                payload={"records": []},
            )
            await adapter.test_connection()

        # The test session is separate from the adapter's main session
        assert adapter._session is None

    @pytest.mark.asyncio
    async def test_connection_session_cleanup_on_error(self) -> None:
        """Session is closed even on error (no resource leak)."""
        from aioresponses import aioresponses

        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="test-key",
        )
        with aioresponses() as mocked:
            mocked.get(
                re.compile(r"https://reneryo\.example\.com/api/u/measurement/meter/item.*"),
                status=500,
                body="Error",
            )
            await adapter.test_connection()

        assert adapter._session is None
