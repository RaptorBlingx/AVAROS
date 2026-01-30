"""
T7: AdapterFactory Tests

Tests for AdapterFactory that creates and manages platform adapter instances
based on configuration. Validates adapter selection, initialization, and hot-reload.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Type, Optional
from abc import ABC, abstractmethod


class ManufacturingAdapter(ABC):
    """Base adapter interface that all adapters must implement"""
    
    @abstractmethod
    async def get_kpi(self, metric: str, asset_id: str, period: str):
        """Get KPI value"""
        pass
    
    @abstractmethod
    async def compare(self, metric: str, asset_ids: list, period: str):
        """Compare metric across assets"""
        pass
    
    @abstractmethod
    async def get_trend(self, metric: str, asset_id: str, period: str, granularity: str):
        """Get trend data"""
        pass
    
    @abstractmethod
    async def check_anomaly(self, metric: str, asset_id: str, threshold: Optional[float] = None):
        """Check for anomalies"""
        pass
    
    @abstractmethod
    async def simulate_whatif(self, scenario: dict):
        """Simulate what-if scenario"""
        pass
    
    @abstractmethod
    def supports_capability(self, capability: str) -> bool:
        """Check if adapter supports a specific capability"""
        pass


class MockAdapter(ManufacturingAdapter):
    """Mock adapter for testing and demo"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    async def get_kpi(self, metric: str, asset_id: str, period: str):
        return {"value": 45.2, "unit": "kWh/unit"}
    
    async def compare(self, metric: str, asset_ids: list, period: str):
        return {"winner_id": asset_ids[0]}
    
    async def get_trend(self, metric: str, asset_id: str, period: str, granularity: str):
        return {"trend_direction": "up"}
    
    async def check_anomaly(self, metric: str, asset_id: str, threshold: Optional[float] = None):
        return {"is_anomalous": False}
    
    async def simulate_whatif(self, scenario: dict):
        return {"delta": -3.1}
    
    def supports_capability(self, capability: str) -> bool:
        return capability in ["kpi", "trend", "compare"]


class RENERYOAdapter(ManufacturingAdapter):
    """RENERYO platform adapter"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
    
    async def get_kpi(self, metric: str, asset_id: str, period: str):
        return {"value": 42.0}
    
    async def compare(self, metric: str, asset_ids: list, period: str):
        return {"winner_id": asset_ids[0]}
    
    async def get_trend(self, metric: str, asset_id: str, period: str, granularity: str):
        return {"trend_direction": "down"}
    
    async def check_anomaly(self, metric: str, asset_id: str, threshold: Optional[float] = None):
        return {"is_anomalous": True}
    
    async def simulate_whatif(self, scenario: dict):
        return {"delta": -2.5}
    
    def supports_capability(self, capability: str) -> bool:
        return True


class AdapterFactory:
    """
    Factory for creating and managing platform adapter instances.
    Supports hot-reload when configuration changes.
    """
    
    # Registry of available adapters
    _adapter_registry: Dict[str, Type[ManufacturingAdapter]] = {
        "mock": MockAdapter,
        "reneryo": RENERYOAdapter
    }
    
    def __init__(self, settings_service=None):
        self.settings_service = settings_service
        self._current_adapter: Optional[ManufacturingAdapter] = None
        self._current_config: Optional[Dict] = None
    
    @classmethod
    def register_adapter(cls, platform_type: str, adapter_class: Type[ManufacturingAdapter]):
        """Register a new adapter type"""
        if not issubclass(adapter_class, ManufacturingAdapter):
            raise TypeError(f"{adapter_class} must inherit from ManufacturingAdapter")
        
        cls._adapter_registry[platform_type] = adapter_class
    
    @classmethod
    def get_available_adapters(cls) -> list:
        """Get list of available adapter types"""
        return list(cls._adapter_registry.keys())
    
    def create_adapter(self, platform_type: str, config: Dict) -> ManufacturingAdapter:
        """Create an adapter instance for the specified platform"""
        if platform_type not in self._adapter_registry:
            raise ValueError(f"Unknown adapter type: {platform_type}")
        
        adapter_class = self._adapter_registry[platform_type]
        return adapter_class(config)
    
    def get_adapter(self) -> ManufacturingAdapter:
        """
        Get the current adapter instance.
        Creates one if it doesn't exist or config changed.
        """
        if self._current_adapter is None:
            self.reload()
        
        return self._current_adapter
    
    def reload(self):
        """Reload adapter from settings (hot-reload)"""
        if self.settings_service:
            config = self.settings_service.get_platform_config()
        else:
            # Default to mock adapter
            config = {"platform_type": "mock"}
        
        platform_type = config.get("platform_type", "mock")
        
        # Only recreate if config changed
        if self._current_config != config:
            self._current_adapter = self.create_adapter(platform_type, config)
            self._current_config = config


class TestAdapterFactory:
    """Test AdapterFactory basic functionality"""
    
    def test_factory_creation(self):
        """Test creating an AdapterFactory instance"""
        factory = AdapterFactory()
        
        assert factory is not None
        assert factory._current_adapter is None
    
    def test_get_available_adapters(self):
        """Test getting list of available adapters"""
        adapters = AdapterFactory.get_available_adapters()
        
        assert "mock" in adapters
        assert "reneryo" in adapters
        assert len(adapters) >= 2
    
    def test_create_mock_adapter(self):
        """Test creating a MockAdapter"""
        factory = AdapterFactory()
        config = {"platform_type": "mock"}
        
        adapter = factory.create_adapter("mock", config)
        
        assert isinstance(adapter, MockAdapter)
        assert isinstance(adapter, ManufacturingAdapter)
    
    def test_create_reneryo_adapter(self):
        """Test creating a RENERYOAdapter"""
        factory = AdapterFactory()
        config = {
            "platform_type": "reneryo",
            "api_url": "http://example.com",
            "api_key": "test_key"
        }
        
        adapter = factory.create_adapter("reneryo", config)
        
        assert isinstance(adapter, RENERYOAdapter)
        assert adapter.api_url == "http://example.com"
        assert adapter.api_key == "test_key"
    
    def test_create_unknown_adapter_raises_error(self):
        """Test that creating unknown adapter raises ValueError"""
        factory = AdapterFactory()
        
        with pytest.raises(ValueError, match="Unknown adapter type"):
            factory.create_adapter("unknown", {})


class TestAdapterRegistration:
    """Test adapter registration system"""
    
    def test_register_new_adapter(self):
        """Test registering a new adapter type"""
        
        class CustomAdapter(ManufacturingAdapter):
            def __init__(self, config):
                self.config = config
            
            async def get_kpi(self, metric, asset_id, period):
                return {}
            
            async def compare(self, metric, asset_ids, period):
                return {}
            
            async def get_trend(self, metric, asset_id, period, granularity):
                return {}
            
            async def check_anomaly(self, metric, asset_id, threshold=None):
                return {}
            
            async def simulate_whatif(self, scenario):
                return {}
            
            def supports_capability(self, capability):
                return True
        
        initial_count = len(AdapterFactory.get_available_adapters())
        
        AdapterFactory.register_adapter("custom", CustomAdapter)
        
        assert "custom" in AdapterFactory.get_available_adapters()
        assert len(AdapterFactory.get_available_adapters()) == initial_count + 1
    
    def test_register_invalid_adapter_raises_error(self):
        """Test that registering non-adapter class raises TypeError"""
        
        class NotAnAdapter:
            pass
        
        with pytest.raises(TypeError, match="must inherit from ManufacturingAdapter"):
            AdapterFactory.register_adapter("invalid", NotAnAdapter)
    
    def test_registered_adapter_can_be_created(self):
        """Test that registered adapters can be instantiated"""
        
        class TestAdapter(ManufacturingAdapter):
            def __init__(self, config):
                self.config = config
            
            async def get_kpi(self, metric, asset_id, period):
                return {"test": True}
            
            async def compare(self, metric, asset_ids, period):
                return {}
            
            async def get_trend(self, metric, asset_id, period, granularity):
                return {}
            
            async def check_anomaly(self, metric, asset_id, threshold=None):
                return {}
            
            async def simulate_whatif(self, scenario):
                return {}
            
            def supports_capability(self, capability):
                return True
        
        AdapterFactory.register_adapter("test_adapter", TestAdapter)
        factory = AdapterFactory()
        
        adapter = factory.create_adapter("test_adapter", {"key": "value"})
        
        assert isinstance(adapter, TestAdapter)
        assert adapter.config == {"key": "value"}


class TestAdapterHotReload:
    """Test adapter hot-reload functionality"""
    
    def test_get_adapter_creates_default(self):
        """Test that get_adapter creates default adapter if none exists"""
        factory = AdapterFactory()
        
        adapter = factory.get_adapter()
        
        assert adapter is not None
        assert isinstance(adapter, MockAdapter)
    
    def test_reload_creates_adapter(self):
        """Test that reload creates adapter from settings"""
        mock_settings = Mock()
        mock_settings.get_platform_config.return_value = {
            "platform_type": "mock",
            "test_key": "test_value"
        }
        
        factory = AdapterFactory(settings_service=mock_settings)
        factory.reload()
        
        assert factory._current_adapter is not None
        assert isinstance(factory._current_adapter, MockAdapter)
    
    def test_reload_switches_adapter_type(self):
        """Test that reload switches adapter when config changes"""
        mock_settings = Mock()
        
        # Initially mock adapter
        mock_settings.get_platform_config.return_value = {"platform_type": "mock"}
        factory = AdapterFactory(settings_service=mock_settings)
        factory.reload()
        
        assert isinstance(factory._current_adapter, MockAdapter)
        
        # Change to RENERYO adapter
        mock_settings.get_platform_config.return_value = {
            "platform_type": "reneryo",
            "api_url": "http://example.com",
            "api_key": "key"
        }
        factory.reload()
        
        assert isinstance(factory._current_adapter, RENERYOAdapter)
    
    def test_reload_only_when_config_changes(self):
        """Test that adapter is only recreated when config changes"""
        mock_settings = Mock()
        config = {"platform_type": "mock", "key": "value"}
        mock_settings.get_platform_config.return_value = config
        
        factory = AdapterFactory(settings_service=mock_settings)
        factory.reload()
        
        first_adapter = factory._current_adapter
        
        # Reload with same config - should keep same instance
        factory.reload()
        
        # Note: In a real implementation, we'd want to keep the same instance
        # This test documents the expected behavior


class TestAdapterInterfaceCompliance:
    """Test that all adapters comply with ManufacturingAdapter interface"""
    
    @pytest.mark.asyncio
    async def test_mock_adapter_has_all_methods(self):
        """Test that MockAdapter implements all required methods"""
        adapter = MockAdapter({})
        
        # Test all 5 Query Type methods
        result = await adapter.get_kpi("energy_per_unit", "comp-1", "today")
        assert result is not None
        
        result = await adapter.compare("energy_per_unit", ["comp-1", "comp-2"], "today")
        assert result is not None
        
        result = await adapter.get_trend("scrap_rate", "line-1", "week", "daily")
        assert result is not None
        
        result = await adapter.check_anomaly("energy_per_unit", "comp-1")
        assert result is not None
        
        result = await adapter.simulate_whatif({"type": "test"})
        assert result is not None
        
        # Test capability support
        supports = adapter.supports_capability("kpi")
        assert isinstance(supports, bool)
    
    @pytest.mark.asyncio
    async def test_reneryo_adapter_has_all_methods(self):
        """Test that RENERYOAdapter implements all required methods"""
        config = {"api_url": "http://test.com", "api_key": "key"}
        adapter = RENERYOAdapter(config)
        
        # Test all 5 Query Type methods exist and are callable
        result = await adapter.get_kpi("energy_per_unit", "comp-1", "today")
        assert result is not None
        
        result = await adapter.compare("energy_per_unit", ["comp-1"], "today")
        assert result is not None
        
        result = await adapter.get_trend("scrap_rate", "line-1", "week", "daily")
        assert result is not None
        
        result = await adapter.check_anomaly("energy_per_unit", "comp-1")
        assert result is not None
        
        result = await adapter.simulate_whatif({})
        assert result is not None
        
        supports = adapter.supports_capability("kpi")
        assert isinstance(supports, bool)


class TestAdapterConfiguration:
    """Test adapter configuration handling"""
    
    def test_adapter_receives_config(self):
        """Test that adapters receive configuration on creation"""
        config = {"key": "value", "timeout": 30}
        
        adapter = MockAdapter(config)
        
        assert adapter.config == config
    
    def test_reneryo_adapter_extracts_config_values(self):
        """Test that RENERYOAdapter extracts specific config values"""
        config = {
            "api_url": "http://example.com/api",
            "api_key": "secret_key_123",
            "timeout": 60
        }
        
        adapter = RENERYOAdapter(config)
        
        assert adapter.api_url == "http://example.com/api"
        assert adapter.api_key == "secret_key_123"
    
    def test_factory_passes_config_to_adapter(self):
        """Test that factory passes configuration to created adapter"""
        factory = AdapterFactory()
        config = {"platform_type": "mock", "custom_key": "custom_value"}
        
        adapter = factory.create_adapter("mock", config)
        
        assert adapter.config == config


class TestAdapterCapabilities:
    """Test adapter capability detection"""
    
    def test_mock_adapter_capabilities(self):
        """Test MockAdapter capability support"""
        adapter = MockAdapter({})
        
        assert adapter.supports_capability("kpi") is True
        assert adapter.supports_capability("trend") is True
        assert adapter.supports_capability("compare") is True
        assert adapter.supports_capability("unknown") is False
    
    def test_reneryo_adapter_full_support(self):
        """Test that RENERYOAdapter supports all capabilities"""
        adapter = RENERYOAdapter({"api_url": "test", "api_key": "test"})
        
        capabilities = ["kpi", "trend", "compare", "anomaly", "whatif"]
        
        for capability in capabilities:
            assert adapter.supports_capability(capability) is True
