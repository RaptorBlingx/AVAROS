"""
Exception Hierarchy Unit Tests

Tests for AVAROS domain exception classes with structured error handling.
Validates exception construction, error codes, serialization, and inheritance.
"""

import pytest

from skill.domain.exceptions import (
    AVAROSError,
    ValidationError,
    AdapterError,
    MetricNotSupportedError,
    AssetNotFoundError,
    ConfigurationError,
)


class TestAVAROSError:
    """Tests for base AVAROSError exception."""
    
    def test_creation_with_message_and_code_creates_error(self):
        """Test creating AVAROSError with message and code."""
        # Arrange
        message = "Something went wrong"
        code = "GENERIC_ERROR"
        
        # Act
        error = AVAROSError(message=message, code=code)
        
        # Assert
        assert error.message == message
        assert error.code == code
        assert error.details == {}
        assert error.user_message == "I encountered an error processing your request."
    
    def test_creation_with_details_stores_details(self):
        """Test creating AVAROSError with details dictionary."""
        # Arrange
        details = {"context": "test", "value": 42}
        
        # Act
        error = AVAROSError(
            message="Test error",
            code="TEST_ERROR",
            details=details
        )
        
        # Assert
        assert error.details == details
    
    def test_creation_with_custom_user_message_stores_message(self):
        """Test creating AVAROSError with custom user message."""
        # Arrange
        user_message = "Please try again later"
        
        # Act
        error = AVAROSError(
            message="Internal error",
            code="INTERNAL",
            user_message=user_message
        )
        
        # Assert
        assert error.user_message == user_message
    
    def test_str_with_code_and_message_formats_correctly(self):
        """Test error string representation includes code and message."""
        # Arrange
        error = AVAROSError(message="Test error", code="TEST_CODE")
        
        # Act
        result = str(error)
        
        # Assert
        assert result == "[TEST_CODE] Test error"
    
    def test_to_dict_with_all_fields_serializes_correctly(self):
        """Test error serialization to dictionary."""
        # Arrange
        error = AVAROSError(
            message="Test error",
            code="TEST_ERROR",
            details={"field": "value"},
            user_message="Custom message"
        )
        
        # Act
        error_dict = error.to_dict()
        
        # Assert
        assert error_dict["code"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"
        assert error_dict["details"] == {"field": "value"}
        assert error_dict["user_message"] == "Custom message"
    
    def test_raise_and_catch_raises_exception(self):
        """Test that AVAROSError can be raised and caught."""
        # Arrange
        error = AVAROSError(message="test", code="TEST")
        
        # Act & Assert
        with pytest.raises(AVAROSError):
            raise error
    
    def test_inheritance_from_exception_is_valid(self):
        """Test that AVAROSError inherits from Exception."""
        # Arrange
        error = AVAROSError(message="test", code="TEST")
        
        # Act & Assert
        assert isinstance(error, Exception)


class TestValidationError:
    """Tests for ValidationError exception."""
    
    def test_creation_with_field_and_value_creates_error(self):
        """Test creating ValidationError with field and value."""
        # Arrange
        message = "Invalid input"
        field = "asset_id"
        value = "invalid@id"
        
        # Act
        error = ValidationError(
            message=message,
            field=field,
            value=value
        )
        
        # Assert
        assert error.message == message
        assert error.field == field
        assert error.value == value
        assert error.code == "VALIDATION_ERROR"
    
    def test_creation_with_field_populates_details(self):
        """Test that field and value are added to details."""
        # Arrange & Act
        error = ValidationError(
            message="Invalid format",
            field="period",
            value="yesterday yesterday"
        )
        
        # Assert
        assert error.details["field"] == "period"
        assert error.details["value"] == "yesterday yesterday"
    
    def test_creation_without_field_uses_empty_details(self):
        """Test ValidationError without field uses empty string."""
        # Arrange & Act
        error = ValidationError(message="Invalid input")
        
        # Assert
        assert error.field == ""
        assert error.value is None
    
    def test_default_user_message_includes_field(self):
        """Test default user message includes field name."""
        # Arrange & Act
        error = ValidationError(
            message="Invalid input",
            field="metric"
        )
        
        # Assert
        assert "metric" in error.user_message.lower()
    
    def test_inheritance_from_avaros_error_is_valid(self):
        """Test that ValidationError inherits from AVAROSError."""
        # Arrange
        error = ValidationError(message="test", field="test")
        
        # Act & Assert
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)


class TestAdapterError:
    """Tests for AdapterError exception."""
    
    def test_creation_with_platform_creates_error(self):
        """Test creating AdapterError with platform name."""
        # Arrange
        message = "Connection failed"
        platform = "reneryo"
        
        # Act
        error = AdapterError(
            message=message,
            platform=platform
        )
        
        # Assert
        assert error.message == message
        assert error.platform == platform
        assert error.code == "ADAPTER_ERROR"
    
    def test_creation_with_status_code_stores_code(self):
        """Test creating AdapterError with HTTP status code."""
        # Arrange & Act
        error = AdapterError(
            message="API error",
            platform="reneryo",
            status_code=504
        )
        
        # Assert
        assert error.status_code == 504
        assert error.details["status_code"] == 504
    
    def test_creation_without_platform_uses_default(self):
        """Test AdapterError without platform uses 'unknown'."""
        # Arrange & Act
        error = AdapterError(message="Error")
        
        # Assert
        assert error.platform == "unknown"
    
    def test_details_include_platform_info(self):
        """Test that details dictionary includes platform information."""
        # Arrange & Act
        error = AdapterError(
            message="Timeout",
            platform="reneryo",
            status_code=408
        )
        
        # Assert
        assert error.details["platform"] == "reneryo"
        assert error.details["status_code"] == 408
    
    def test_default_user_message_mentions_connection(self):
        """Test default user message mentions connection issue."""
        # Arrange & Act
        error = AdapterError(message="Error", platform="test")
        
        # Assert
        assert "connecting" in error.user_message.lower() or "connection" in error.user_message.lower()
    
    def test_inheritance_from_avaros_error_is_valid(self):
        """Test that AdapterError inherits from AVAROSError."""
        # Arrange
        error = AdapterError(message="test", platform="test")
        
        # Act & Assert
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)


class TestMetricNotSupportedError:
    """Tests for MetricNotSupportedError exception."""
    
    def test_creation_with_metric_and_platform_creates_error(self):
        """Test creating MetricNotSupportedError with metric and platform."""
        # Arrange
        metric = "supplier_co2_per_kg"
        platform = "mock"
        
        # Act
        error = MetricNotSupportedError(
            metric=metric,
            platform=platform
        )
        
        # Assert
        assert error.metric == metric
        assert error.platform == platform
        assert error.code == "METRIC_NOT_SUPPORTED"
    
    def test_creation_with_available_metrics_stores_list(self):
        """Test creating error with list of available metrics."""
        # Arrange
        available = ["oee", "energy_per_unit", "scrap_rate"]
        
        # Act
        error = MetricNotSupportedError(
            metric="unknown",
            platform="mock",
            available_metrics=available
        )
        
        # Assert
        assert error.available_metrics == available
        assert error.details["available_metrics"] == available
    
    def test_creation_without_message_generates_message(self):
        """Test that message is auto-generated if not provided."""
        # Arrange & Act
        error = MetricNotSupportedError(
            metric="test_metric",
            platform="test_platform"
        )
        
        # Assert
        assert "test_metric" in error.message
        assert "test_platform" in error.message
    
    def test_details_include_metric_info(self):
        """Test that details include metric and platform."""
        # Arrange & Act
        error = MetricNotSupportedError(
            metric="co2_total",
            platform="mock"
        )
        
        # Assert
        assert error.details["metric"] == "co2_total"
        assert error.details["platform"] == "mock"
    
    def test_inheritance_from_avaros_error_is_valid(self):
        """Test that MetricNotSupportedError inherits from AVAROSError."""
        # Arrange
        error = MetricNotSupportedError(metric="test", platform="test")
        
        # Act & Assert
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)


class TestAssetNotFoundError:
    """Tests for AssetNotFoundError exception."""
    
    def test_creation_with_asset_id_creates_error(self):
        """Test creating AssetNotFoundError with asset ID."""
        # Arrange
        asset_id = "Line-99"
        
        # Act
        error = AssetNotFoundError(asset_id=asset_id)
        
        # Assert
        assert error.asset_id == asset_id
        assert error.code == "ASSET_NOT_FOUND"
    
    def test_creation_with_available_assets_stores_list(self):
        """Test creating error with available assets list."""
        # Arrange
        available = ["Line-1", "Line-2", "Compressor-1"]
        
        # Act
        error = AssetNotFoundError(
            asset_id="Line-99",
            available_assets=available
        )
        
        # Assert
        assert error.available_assets == available
    
    def test_creation_without_message_generates_message(self):
        """Test that message is auto-generated if not provided."""
        # Arrange & Act
        error = AssetNotFoundError(asset_id="Test-Asset")
        
        # Assert
        assert "Test-Asset" in error.message
    
    def test_details_limit_available_assets_to_ten(self):
        """Test that details limit available assets to first 10."""
        # Arrange
        many_assets = [f"Asset-{i}" for i in range(20)]
        
        # Act
        error = AssetNotFoundError(
            asset_id="Missing",
            available_assets=many_assets
        )
        
        # Assert
        assert len(error.details["available_assets"]) == 10
    
    def test_user_message_includes_asset_id(self):
        """Test default user message includes asset ID."""
        # Arrange & Act
        error = AssetNotFoundError(asset_id="Test-123")
        
        # Assert
        assert "Test-123" in error.user_message
    
    def test_inheritance_from_avaros_error_is_valid(self):
        """Test that AssetNotFoundError inherits from AVAROSError."""
        # Arrange
        error = AssetNotFoundError(asset_id="test")
        
        # Act & Assert
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)


class TestConfigurationError:
    """Tests for ConfigurationError exception."""
    
    def test_creation_with_message_and_setting_creates_error(self):
        """Test creating ConfigurationError with message and setting."""
        # Arrange
        message = "Missing API key"
        setting = "platform.api_key"
        
        # Act
        error = ConfigurationError(
            message=message,
            setting=setting
        )
        
        # Assert
        assert error.message == message
        assert error.setting == setting
        assert error.code == "CONFIG_ERROR"
    
    def test_creation_without_setting_uses_empty_string(self):
        """Test ConfigurationError without setting uses empty string."""
        # Arrange & Act
        error = ConfigurationError(message="Config error")
        
        # Assert
        assert error.setting == ""
    
    def test_details_include_setting(self):
        """Test that details include setting name."""
        # Arrange & Act
        error = ConfigurationError(
            message="Invalid config",
            setting="timeout_seconds"
        )
        
        # Assert
        assert error.details["setting"] == "timeout_seconds"
    
    def test_default_user_message_mentions_configuration(self):
        """Test default user message mentions configuration."""
        # Arrange & Act
        error = ConfigurationError(message="Error", setting="test")
        
        # Assert
        assert "configur" in error.user_message.lower()
    
    def test_inheritance_from_avaros_error_is_valid(self):
        """Test that ConfigurationError inherits from AVAROSError."""
        # Arrange
        error = ConfigurationError(message="test", setting="test")
        
        # Act & Assert
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and polymorphism."""
    
    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from AVAROSError."""
        # Arrange
        exceptions = [
            ValidationError(message="test", field="test"),
            AdapterError(message="test", platform="test"),
            MetricNotSupportedError(metric="test", platform="test"),
            AssetNotFoundError(asset_id="test"),
            ConfigurationError(message="test", setting="test"),
        ]
        
        # Act & Assert
        for error in exceptions:
            assert isinstance(error, AVAROSError)
            assert isinstance(error, Exception)
    
    def test_specific_exceptions_caught_by_base_class(self):
        """Test that specific exceptions can be caught by base class."""
        # Arrange
        error = ValidationError(message="test", field="test")
        
        # Act & Assert
        with pytest.raises(AVAROSError):
            raise error
    
    def test_specific_exceptions_caught_individually(self):
        """Test that specific exceptions can be caught individually."""
        # Arrange
        error = AdapterError(message="test", platform="test")
        
        # Act & Assert
        with pytest.raises(AdapterError):
            raise error
    
    def test_all_exceptions_support_to_dict(self):
        """Test that all exceptions support to_dict serialization."""
        # Arrange
        exceptions = [
            AVAROSError(message="test", code="TEST"),
            ValidationError(message="test", field="test"),
            AdapterError(message="test", platform="test"),
            MetricNotSupportedError(metric="test", platform="test"),
            AssetNotFoundError(asset_id="test"),
            ConfigurationError(message="test", setting="test"),
        ]
        
        # Act & Assert
        for error in exceptions:
            error_dict = error.to_dict()
            assert "code" in error_dict
            assert "message" in error_dict
            assert "details" in error_dict
            assert "user_message" in error_dict


class TestErrorCodes:
    """Tests for error code conventions."""
    
    def test_default_error_codes_are_uppercase_snake_case(self):
        """Test that default error codes follow UPPER_SNAKE_CASE."""
        # Arrange
        errors = [
            AVAROSError(message="test", code="AVAROS_ERROR"),
            ValidationError(message="test", field="test"),
            AdapterError(message="test", platform="test"),
            MetricNotSupportedError(metric="test", platform="test"),
            AssetNotFoundError(asset_id="test"),
            ConfigurationError(message="test", setting="test"),
        ]
        
        # Act & Assert
        for error in errors:
            assert error.code.isupper()
            assert "_" in error.code


class TestErrorContext:
    """Tests for error context and detail information."""
    
    def test_error_with_rich_context_stores_all_details(self):
        """Test error with multiple context fields."""
        # Arrange
        details = {
            "metric": "energy_per_unit",
            "asset_id": "compressor-1",
            "period": "today",
            "api_url": "http://example.com/api",
            "http_status": 500,
            "timestamp": "2026-01-30T10:00:00Z"
        }
        
        # Act
        error = AdapterError(
            message="Failed to retrieve KPI",
            platform="reneryo",
            status_code=500
        )
        # Add custom details after creation through base class
        error.details.update({
            "metric": "energy_per_unit",
            "asset_id": "compressor-1",
            "period": "today",
            "api_url": "http://example.com/api",
            "timestamp": "2026-01-30T10:00:00Z"
        })
        
        # Assert
        assert error.details["metric"] == "energy_per_unit"
        assert error.details["http_status"] == 500
        assert len(error.details) >= 6
    
    def test_error_details_preserved_in_to_dict(self):
        """Test that error details are preserved in serialization."""
        # Arrange
        error = ValidationError(
            message="Invalid input",
            field="asset_id",
            value="invalid"
        )
        
        # Act
        serialized = error.to_dict()
        
        # Assert
        assert serialized["details"]["field"] == "asset_id"
        assert serialized["details"]["value"] == "invalid"
