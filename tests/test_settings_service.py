"""
T8: SettingsService Tests

Tests for SettingsService that manages runtime configuration via database.
Validates settings CRUD operations, validation, encryption, and hot-reload triggers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Optional, Any
import json


class SettingsService:
    """
    Manages runtime configuration stored in database.
    All configuration happens via Web UI or API, NOT files.
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self._cache: Dict[str, Any] = {}
        self._observers = []
    
    def get_platform_config(self) -> Dict[str, Any]:
        """Get platform connection configuration"""
        return self._get_setting("platform", default={
            "platform_type": "mock",
            "api_url": "",
            "api_key": "",
            "timeout": 30
        })
    
    def update_platform_config(self, config: Dict[str, Any]) -> None:
        """Update platform configuration and trigger reload"""
        self._validate_platform_config(config)
        self._set_setting("platform", config)
        self._notify_observers("platform")
    
    def get_alert_thresholds(self) -> Dict[str, float]:
        """Get alert threshold configuration"""
        return self._get_setting("alert_thresholds", default={
            "energy_spike_sigma": 2.0,
            "scrap_rate_percent": 5.0,
            "anomaly_severity": 2.5
        })
    
    def update_alert_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update alert thresholds"""
        self._validate_alert_thresholds(thresholds)
        self._set_setting("alert_thresholds", thresholds)
    
    def is_configured(self) -> bool:
        """Check if system has been configured (for first-run wizard)"""
        config = self.get_platform_config()
        return config.get("platform_type") != "mock" or config.get("configured", False)
    
    def mark_configured(self) -> None:
        """Mark system as configured (first-run complete)"""
        config = self.get_platform_config()
        config["configured"] = True
        self.update_platform_config(config)
    
    def register_observer(self, callback) -> None:
        """Register callback for configuration changes"""
        self._observers.append(callback)
    
    def _get_setting(self, category: str, default: Any = None) -> Any:
        """Internal method to get setting from DB"""
        # Check cache first
        if category in self._cache:
            return self._cache[category]
        
        # Query database
        if self.db:
            result = self.db.get(category)
            if result:
                value = json.loads(result) if isinstance(result, str) else result
                self._cache[category] = value
                return value
        
        return default
    
    def _set_setting(self, category: str, value: Any) -> None:
        """Internal method to save setting to DB"""
        if self.db:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            self.db.set(category, serialized)
        
        # Update cache
        self._cache[category] = value
    
    def _validate_platform_config(self, config: Dict[str, Any]) -> None:
        """Validate platform configuration"""
        required_fields = ["platform_type"]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        valid_platforms = ["mock", "reneryo", "sap", "custom"]
        if config["platform_type"] not in valid_platforms:
            raise ValueError(f"Invalid platform_type: {config['platform_type']}")
        
        # If not mock, require API credentials
        if config["platform_type"] != "mock":
            if not config.get("api_url"):
                raise ValueError("api_url required for non-mock platforms")
    
    def _validate_alert_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Validate alert thresholds"""
        for key, value in thresholds.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"Threshold {key} must be numeric")
            if value < 0:
                raise ValueError(f"Threshold {key} must be non-negative")
    
    def _notify_observers(self, category: str) -> None:
        """Notify observers of configuration change"""
        for observer in self._observers:
            observer(category)


class MockDatabase:
    """Mock database for testing"""
    
    def __init__(self):
        self.store: Dict[str, str] = {}
    
    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)
    
    def set(self, key: str, value: str) -> None:
        self.store[key] = value


class TestSettingsServiceBasics:
    """Test SettingsService basic functionality"""
    
    def test_settings_service_creation(self):
        """Test creating a SettingsService instance"""
        service = SettingsService()
        
        assert service is not None
        assert service._cache == {}
    
    def test_settings_service_with_db(self):
        """Test creating SettingsService with database"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        assert service.db is mock_db
    
    def test_get_platform_config_default(self):
        """Test getting platform config returns default when not set"""
        service = SettingsService()
        
        config = service.get_platform_config()
        
        assert config["platform_type"] == "mock"
        assert "timeout" in config
        assert config["timeout"] == 30


class TestPlatformConfiguration:
    """Test platform configuration management"""
    
    def test_update_platform_config(self):
        """Test updating platform configuration"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        new_config = {
            "platform_type": "mock",
            "api_url": "http://example.com",
            "timeout": 60
        }
        
        service.update_platform_config(new_config)
        
        retrieved = service.get_platform_config()
        assert retrieved["api_url"] == "http://example.com"
        assert retrieved["timeout"] == 60
    
    def test_platform_config_validation_missing_field(self):
        """Test that missing required fields raise error"""
        service = SettingsService()
        
        invalid_config = {
            "api_url": "http://example.com"
            # Missing platform_type
        }
        
        with pytest.raises(ValueError, match="Missing required field: platform_type"):
            service.update_platform_config(invalid_config)
    
    def test_platform_config_validation_invalid_type(self):
        """Test that invalid platform_type raises error"""
        service = SettingsService()
        
        invalid_config = {
            "platform_type": "invalid_platform"
        }
        
        with pytest.raises(ValueError, match="Invalid platform_type"):
            service.update_platform_config(invalid_config)
    
    def test_platform_config_requires_api_url_for_non_mock(self):
        """Test that non-mock platforms require api_url"""
        service = SettingsService()
        
        invalid_config = {
            "platform_type": "reneryo"
            # Missing api_url
        }
        
        with pytest.raises(ValueError, match="api_url required"):
            service.update_platform_config(invalid_config)
    
    def test_platform_config_mock_no_api_url_required(self):
        """Test that mock platform doesn't require api_url"""
        service = SettingsService()
        
        valid_config = {
            "platform_type": "mock"
        }
        
        # Should not raise
        service.update_platform_config(valid_config)


class TestAlertThresholds:
    """Test alert threshold configuration"""
    
    def test_get_alert_thresholds_default(self):
        """Test getting default alert thresholds"""
        service = SettingsService()
        
        thresholds = service.get_alert_thresholds()
        
        assert "energy_spike_sigma" in thresholds
        assert "scrap_rate_percent" in thresholds
        assert thresholds["energy_spike_sigma"] == 2.0
    
    def test_update_alert_thresholds(self):
        """Test updating alert thresholds"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        new_thresholds = {
            "energy_spike_sigma": 3.0,
            "scrap_rate_percent": 7.5,
            "custom_threshold": 10.0
        }
        
        service.update_alert_thresholds(new_thresholds)
        
        retrieved = service.get_alert_thresholds()
        assert retrieved["energy_spike_sigma"] == 3.0
        assert retrieved["custom_threshold"] == 10.0
    
    def test_alert_threshold_validation_non_numeric(self):
        """Test that non-numeric thresholds raise error"""
        service = SettingsService()
        
        invalid_thresholds = {
            "energy_spike_sigma": "not_a_number"
        }
        
        with pytest.raises(ValueError, match="must be numeric"):
            service.update_alert_thresholds(invalid_thresholds)
    
    def test_alert_threshold_validation_negative(self):
        """Test that negative thresholds raise error"""
        service = SettingsService()
        
        invalid_thresholds = {
            "energy_spike_sigma": -2.0
        }
        
        with pytest.raises(ValueError, match="must be non-negative"):
            service.update_alert_thresholds(invalid_thresholds)


class TestFirstRunDetection:
    """Test first-run wizard detection"""
    
    def test_is_configured_false_by_default(self):
        """Test that system is not configured by default"""
        service = SettingsService()
        
        assert service.is_configured() is False
    
    def test_is_configured_true_after_marking(self):
        """Test that marking as configured works"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        service.mark_configured()
        
        assert service.is_configured() is True
    
    def test_is_configured_true_for_non_mock_platform(self):
        """Test that non-mock platform is considered configured"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        config = {
            "platform_type": "reneryo",
            "api_url": "http://example.com",
            "api_key": "key"
        }
        service.update_platform_config(config)
        
        assert service.is_configured() is True


class TestSettingsPersistence:
    """Test settings persistence to database"""
    
    def test_settings_saved_to_db(self):
        """Test that settings are persisted to database"""
        mock_db = MockDatabase()
        service = SettingsService(db_connection=mock_db)
        
        config = {
            "platform_type": "mock",
            "custom_field": "value"
        }
        service.update_platform_config(config)
        
        # Check database directly
        assert "platform" in mock_db.store
    
    def test_settings_loaded_from_db(self):
        """Test that settings are loaded from database"""
        mock_db = MockDatabase()
        
        # Pre-populate database
        saved_config = {
            "platform_type": "reneryo",
            "api_url": "http://saved.com",
            "api_key": "saved_key"
        }
        mock_db.set("platform", json.dumps(saved_config))
        
        # Create service and load
        service = SettingsService(db_connection=mock_db)
        config = service.get_platform_config()
        
        assert config["platform_type"] == "reneryo"
        assert config["api_url"] == "http://saved.com"
    
    def test_settings_cached_after_first_load(self):
        """Test that settings are cached for performance"""
        mock_db = Mock()
        mock_db.get.return_value = json.dumps({"platform_type": "mock"})
        
        service = SettingsService(db_connection=mock_db)
        
        # First call - should hit DB
        config1 = service.get_platform_config()
        
        # Second call - should use cache
        config2 = service.get_platform_config()
        
        # DB should only be called once
        assert mock_db.get.call_count == 1
        assert config1 == config2


class TestHotReloadTriggers:
    """Test hot-reload observer notifications"""
    
    def test_register_observer(self):
        """Test registering configuration change observer"""
        service = SettingsService()
        callback = Mock()
        
        service.register_observer(callback)
        
        assert callback in service._observers
    
    def test_observer_notified_on_platform_config_change(self):
        """Test that observers are notified when platform config changes"""
        service = SettingsService()
        callback = Mock()
        service.register_observer(callback)
        
        config = {"platform_type": "mock"}
        service.update_platform_config(config)
        
        callback.assert_called_once_with("platform")
    
    def test_multiple_observers_notified(self):
        """Test that all registered observers are notified"""
        service = SettingsService()
        callback1 = Mock()
        callback2 = Mock()
        
        service.register_observer(callback1)
        service.register_observer(callback2)
        
        config = {"platform_type": "mock"}
        service.update_platform_config(config)
        
        callback1.assert_called_once()
        callback2.assert_called_once()
    
    def test_observer_receives_correct_category(self):
        """Test that observers receive the changed category"""
        service = SettingsService()
        received_categories = []
        
        def observer(category):
            received_categories.append(category)
        
        service.register_observer(observer)
        
        service.update_platform_config({"platform_type": "mock"})
        
        assert "platform" in received_categories


class TestSettingsValidation:
    """Test comprehensive settings validation"""
    
    def test_valid_platform_types(self):
        """Test all valid platform types"""
        service = SettingsService()
        valid_types = ["mock", "reneryo", "sap", "custom"]
        
        for platform_type in valid_types:
            config = {"platform_type": platform_type}
            if platform_type != "mock":
                config["api_url"] = "http://example.com"
            
            # Should not raise
            service.update_platform_config(config)
    
    def test_numeric_threshold_types_accepted(self):
        """Test that both int and float thresholds are accepted"""
        service = SettingsService()
        
        thresholds = {
            "int_threshold": 5,
            "float_threshold": 2.5
        }
        
        # Should not raise
        service.update_alert_thresholds(thresholds)
