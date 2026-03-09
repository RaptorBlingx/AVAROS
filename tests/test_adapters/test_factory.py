"""
AdapterFactory Unit Tests

Comprehensive tests for the factory pattern that creates platform adapters.
Tests creation, caching, reload, registry, and zero-config fallback.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from skill.adapters.factory import AdapterFactory
from skill.adapters.mock import MockAdapter
from skill.adapters.base import ManufacturingAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_adapter_registry() -> None:
    """
    Reset the class-level registry before each test.

    AdapterFactory._ADAPTER_REGISTRY is shared state — tests that call
    register_adapter() would pollute other tests without this cleanup.
    """
    original = dict(AdapterFactory._ADAPTER_REGISTRY)
    yield
    AdapterFactory._ADAPTER_REGISTRY = original


@pytest.fixture
def mock_settings_service() -> MagicMock:
    """Create a mock SettingsService returning mock platform config."""
    service = MagicMock()
    config = MagicMock()
    config.platform_type = "mock"
    service.get_active_profile_name.return_value = "mock"
    service.get_profile.return_value = config
    # Keep old API mocked for backward compat tests
    service.get_platform_config.return_value = config
    return service


@pytest.fixture
def factory_no_settings() -> AdapterFactory:
    """Factory with no SettingsService (zero-config mode)."""
    return AdapterFactory(settings_service=None)


@pytest.fixture
def factory_with_settings(mock_settings_service: MagicMock) -> AdapterFactory:
    """Factory with a mocked SettingsService."""
    return AdapterFactory(settings_service=mock_settings_service)


# ---------------------------------------------------------------------------
# Stub adapter for registry tests
# ---------------------------------------------------------------------------

class _StubAdapter(ManufacturingAdapter):
    """Minimal concrete adapter used only in registry tests."""

    async def get_kpi(self, metric, asset_id, period):  # type: ignore[override]
        """Stub — not called in these tests."""
        ...

    async def compare(self, metric, asset_ids, period):  # type: ignore[override]
        """Stub — not called in these tests."""
        ...

    async def get_trend(self, metric, asset_id, period, granularity="daily"):  # type: ignore[override]
        """Stub — not called in these tests."""
        ...

    async def get_raw_data(self, metric, asset_id, period):  # type: ignore[override]
        """Stub — not called in these tests."""
        ...

    async def list_assets(self):  # type: ignore[override]
        """Stub — not called in these tests."""
        return []


# ---------------------------------------------------------------------------
# create() — Adapter Creation
# ---------------------------------------------------------------------------

class TestAdapterFactoryCreate:
    """Tests for create() — the primary adapter creation method."""

    def test_create_no_settings_returns_mock_adapter(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """With no SettingsService, create() must return MockAdapter."""
        adapter = factory_no_settings.create()

        assert isinstance(adapter, MockAdapter)

    def test_create_with_mock_config_returns_mock_adapter(
        self,
        factory_with_settings: AdapterFactory,
    ) -> None:
        """When settings return platform_type='mock', get MockAdapter."""
        adapter = factory_with_settings.create()

        assert isinstance(adapter, MockAdapter)

    def test_create_caches_adapter_instance(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """Calling create() twice must return the same object."""
        first = factory_no_settings.create()
        second = factory_no_settings.create()

        assert first is second

    def test_create_with_demo_config_returns_mock_adapter(self) -> None:
        """'demo' is an alias for MockAdapter in the registry."""
        service = MagicMock()
        config = MagicMock()
        config.platform_type = "demo"
        service.get_active_profile_name.return_value = "demo"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, MockAdapter)

    def test_create_with_unknown_platform_falls_back_to_mock(self) -> None:
        """Unknown platform names should gracefully fall back to MockAdapter."""
        service = MagicMock()
        config = MagicMock()
        config.platform_type = "nonexistent_platform"
        service.get_active_profile_name.return_value = "nope"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, MockAdapter)


# ---------------------------------------------------------------------------
# create_async() — Async Creation with Initialization
# ---------------------------------------------------------------------------

class TestAdapterFactoryCreateAsync:
    """Tests for create_async() — async adapter creation + init."""

    @pytest.mark.asyncio
    async def test_create_async_returns_mock_adapter(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """create_async() should return an initialized MockAdapter."""
        adapter = await factory_no_settings.create_async()

        assert isinstance(adapter, MockAdapter)

    @pytest.mark.asyncio
    async def test_create_async_calls_initialize(self) -> None:
        """create_async() must call adapter.initialize()."""
        factory = AdapterFactory(settings_service=None)

        with patch.object(MockAdapter, "initialize", new_callable=AsyncMock) as mock_init:
            await factory.create_async()
            mock_init.assert_called_once()


# ---------------------------------------------------------------------------
# _get_configured_platform()
# ---------------------------------------------------------------------------

class TestGetConfiguredPlatform:
    """Tests for _get_configured_platform() — platform resolution."""

    def test_none_settings_returns_mock(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """No settings service → 'mock'."""
        result = factory_no_settings._get_configured_platform()

        assert result == "mock"

    def test_settings_returns_configured_platform(
        self,
        factory_with_settings: AdapterFactory,
    ) -> None:
        """SettingsService returning valid config → that platform name."""
        result = factory_with_settings._get_configured_platform()

        assert result == "mock"

    def test_settings_error_falls_back_to_mock(self) -> None:
        """If SettingsService raises, fall back to 'mock'."""
        service = MagicMock()
        service.get_active_profile_name.side_effect = RuntimeError("DB down")

        factory = AdapterFactory(settings_service=service)
        result = factory._get_configured_platform()

        assert result == "mock"

    def test_settings_returns_none_config_falls_back(self) -> None:
        """If get_profile() returns None, use 'mock'."""
        service = MagicMock()
        service.get_active_profile_name.return_value = "deleted"
        service.get_profile.return_value = None

        factory = AdapterFactory(settings_service=service)
        result = factory._get_configured_platform()

        assert result == "mock"

    def test_settings_returns_empty_platform_type_falls_back(self) -> None:
        """If platform_type is 'mock', use 'mock'."""
        service = MagicMock()
        config = MagicMock()
        config.platform_type = "mock"
        service.get_active_profile_name.return_value = "mock"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        result = factory._get_configured_platform()

        assert result == "mock"

    def test_platform_name_is_lowercased(self) -> None:
        """Platform identification must be case-insensitive."""
        service = MagicMock()
        config = MagicMock()
        config.platform_type = "RENERYO"
        service.get_active_profile_name.return_value = "reneryo"
        service.get_profile.return_value = config
        service.get_asset_mappings.return_value = {"Line-1": {"seu_id": "seu-1"}}

        factory = AdapterFactory(settings_service=service)
        result = factory._get_configured_platform()

        assert result == "reneryo"


# ---------------------------------------------------------------------------
# _instantiate_adapter()
# ---------------------------------------------------------------------------

class TestInstantiateAdapter:
    """Tests for _instantiate_adapter() — adapter construction."""

    def test_instantiate_mock_adapter_returns_instance(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """MockAdapter class → MockAdapter instance."""
        adapter = factory_no_settings._instantiate_adapter(MockAdapter, "mock")

        assert isinstance(adapter, MockAdapter)

    def test_instantiate_unknown_class_returns_instance(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """Non-MockAdapter classes should also be instantiated."""
        adapter = factory_no_settings._instantiate_adapter(
            _StubAdapter, "stub",
        )

        assert isinstance(adapter, _StubAdapter)

    def test_create_reneryo_adapter_passes_profile_context(self) -> None:
        """Factory forwards settings/profile metadata to ReneryoAdapter."""
        service = MagicMock()
        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.example"
        config.api_key = "secret"
        config.timeout = 25
        config.extra_settings = {
            "auth_type": "cookie",
            "api_format": "native",
            "SEU_ID": "seu-7",
        }
        service.get_active_profile_name.return_value = "reneryo"
        service.get_profile.return_value = config
        service.get_asset_mappings.return_value = {"Line-1": {"seu_id": "seu-1"}}

        factory = AdapterFactory(settings_service=service)

        with patch("skill.adapters.factory.ReneryoAdapter") as adapter_cls:
            adapter_cls.return_value = MagicMock()
            factory._create_reneryo_adapter()

            kwargs = adapter_cls.call_args.kwargs
            assert kwargs["settings_service"] is service
            assert kwargs["profile_name"] == "reneryo"
            assert kwargs["extra_settings"]["SEU_ID"] == "seu-7"
            assert kwargs["asset_mappings"] == {"Line-1": {"seu_id": "seu-1"}}
            service.get_asset_mappings.assert_called_once_with(profile="reneryo")


# ---------------------------------------------------------------------------
# register_adapter()
# ---------------------------------------------------------------------------

class TestAdapterFactoryRegister:
    """Tests for register_adapter() — dynamic registry extension."""

    def test_register_adapter_adds_to_registry(self) -> None:
        """Registering adds the class to _ADAPTER_REGISTRY."""
        AdapterFactory.register_adapter("custom", _StubAdapter)

        assert "custom" in AdapterFactory._ADAPTER_REGISTRY
        assert AdapterFactory._ADAPTER_REGISTRY["custom"] is _StubAdapter

    def test_register_adapter_lowercase_key(self) -> None:
        """Platform name is normalized to lowercase."""
        AdapterFactory.register_adapter("UPPER", _StubAdapter)

        assert "upper" in AdapterFactory._ADAPTER_REGISTRY

    def test_registered_adapter_is_created_by_factory(self) -> None:
        """After registration, create() should produce the new adapter."""
        AdapterFactory.register_adapter("stub", _StubAdapter)

        service = MagicMock()
        config = MagicMock()
        config.platform_type = "stub"
        service.get_active_profile_name.return_value = "stub"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, _StubAdapter)


# ---------------------------------------------------------------------------
# get_available_platforms()
# ---------------------------------------------------------------------------

class TestGetAvailablePlatforms:
    """Tests for get_available_platforms() — platform listing."""

    def test_includes_mock_and_demo(self) -> None:
        """Default registry must include 'mock' and 'demo'."""
        platforms = AdapterFactory.get_available_platforms()

        assert "mock" in platforms
        assert "demo" in platforms

    def test_includes_registered_platform(self) -> None:
        """Dynamically registered platforms appear in the list."""
        AdapterFactory.register_adapter("custom_plat", _StubAdapter)

        platforms = AdapterFactory.get_available_platforms()

        assert "custom_plat" in platforms

    def test_returns_list_type(self) -> None:
        """Return type must be a list of strings."""
        platforms = AdapterFactory.get_available_platforms()

        assert isinstance(platforms, list)
        for p in platforms:
            assert isinstance(p, str)


# ---------------------------------------------------------------------------
# reload() — Hot-Swap Adapter
# ---------------------------------------------------------------------------

class TestAdapterFactoryReload:
    """Tests for reload() — tear down old adapter and create new one."""

    @pytest.mark.asyncio
    async def test_reload_returns_new_adapter(
        self,
        factory_no_settings: AdapterFactory,
    ) -> None:
        """reload() should return a fresh adapter instance."""
        old = factory_no_settings.create()
        new = await factory_no_settings.reload()

        assert isinstance(new, MockAdapter)
        assert new is not old

    @pytest.mark.asyncio
    async def test_reload_shuts_down_old_adapter(self) -> None:
        """reload() must call shutdown() on the previous adapter."""
        factory = AdapterFactory(settings_service=None)
        old_adapter = factory.create()

        with patch.object(
            type(old_adapter), "shutdown", new_callable=AsyncMock,
        ) as mock_shutdown:
            # Replace cached adapter with one we can spy on
            factory._current_adapter = old_adapter
            await factory.reload()
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_with_no_previous_adapter(self) -> None:
        """reload() on a fresh factory should work without error."""
        factory = AdapterFactory(settings_service=None)

        adapter = await factory.reload()

        assert isinstance(adapter, MockAdapter)

    @pytest.mark.asyncio
    async def test_reload_swallows_shutdown_error(self) -> None:
        """If old adapter.shutdown() raises, reload still succeeds."""
        factory = AdapterFactory(settings_service=None)
        factory.create()

        with patch.object(
            MockAdapter, "shutdown",
            new_callable=AsyncMock,
            side_effect=RuntimeError("cleanup failed"),
        ):
            adapter = await factory.reload()

        assert isinstance(adapter, MockAdapter)

    @pytest.mark.asyncio
    async def test_reload_initializes_new_adapter(self) -> None:
        """reload() uses create_async which calls initialize()."""
        factory = AdapterFactory(settings_service=None)
        factory.create()

        with patch.object(
            MockAdapter, "initialize", new_callable=AsyncMock,
        ) as mock_init:
            await factory.reload()
            mock_init.assert_called_once()


# ---------------------------------------------------------------------------
# Profile-Based Adapter Creation (DEC-028)
# ---------------------------------------------------------------------------


class TestAdapterFactoryProfiles:
    """Tests for profile-based adapter creation and reload."""

    def test_create_with_active_profile_mock(self) -> None:
        """When active profile is 'mock', MockAdapter is created."""
        service = MagicMock()
        service.get_active_profile_name.return_value = "mock"
        service.get_profile.return_value = MagicMock(
            platform_type="mock",
        )

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, MockAdapter)

    def test_create_with_active_profile_reneryo(self) -> None:
        """When active profile is 'reneryo', ReneryoAdapter is created."""
        from skill.adapters.reneryo import ReneryoAdapter

        config = MagicMock()
        config.platform_type = "reneryo"
        config.api_url = "https://api.example.com"
        config.api_key = "test-key"
        config.timeout = 30
        config.extra_settings = {"auth_type": "bearer"}

        service = MagicMock()
        service.get_active_profile_name.return_value = "reneryo"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, ReneryoAdapter)

    def test_custom_rest_profile_creates_generic_rest_adapter(self) -> None:
        """When active profile is custom_rest, GenericRestAdapter is created."""
        from skill.adapters.generic_rest import GenericRestAdapter

        config = MagicMock()
        config.platform_type = "custom_rest"
        config.api_url = "https://api.example.com"
        config.api_key = "test-key"
        config.timeout = 20
        config.extra_settings = {"auth_type": "cookie"}

        service = MagicMock()
        service.get_active_profile_name.return_value = "custom-rest"
        service.get_profile.return_value = config

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, GenericRestAdapter)

    def test_create_with_missing_profile_falls_back_to_mock(self) -> None:
        """When active profile config returns None, fall back to mock."""
        service = MagicMock()
        service.get_active_profile_name.return_value = "deleted"
        service.get_profile.return_value = None

        factory = AdapterFactory(settings_service=service)
        adapter = factory.create()

        assert isinstance(adapter, MockAdapter)

    @pytest.mark.asyncio
    async def test_reload_with_profile_name_switches_active(self) -> None:
        """reload(profile_name=...) calls set_active_profile first."""
        service = MagicMock()
        service.get_active_profile_name.return_value = "mock"
        service.get_profile.return_value = MagicMock(
            platform_type="mock",
        )

        factory = AdapterFactory(settings_service=service)
        factory.create()

        await factory.reload(profile_name="reneryo")

        service.set_active_profile.assert_called_once_with("reneryo")

    @pytest.mark.asyncio
    async def test_reload_without_profile_name_uses_current(self) -> None:
        """reload() without profile_name does not change active."""
        service = MagicMock()
        service.get_active_profile_name.return_value = "mock"
        service.get_profile.return_value = MagicMock(
            platform_type="mock",
        )

        factory = AdapterFactory(settings_service=service)
        factory.create()

        await factory.reload()

        service.set_active_profile.assert_not_called()
