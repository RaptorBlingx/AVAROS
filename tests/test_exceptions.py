"""
T6: Exception Hierarchy Tests

Tests for AVAROS domain-specific exception hierarchy with structured error handling.
Validates exception classes, error codes, and error message formatting.
"""
import pytest
from typing import Dict, Optional


class AVAROSError(Exception):
    """
    Base exception for AVAROS
    All custom exceptions inherit from this
    """
    def __init__(self, message: str, code: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def __str__(self):
        return f"[{self.code}] {self.message}"
    
    def to_dict(self) -> Dict:
        """Serialize exception to dictionary for API responses"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details
        }


class AdapterError(AVAROSError):
    """Platform adapter errors (API connection, authentication, etc.)"""
    
    def __init__(self, message: str, code: str = "ADAPTER_ERROR", details: Optional[Dict] = None):
        super().__init__(message, code, details)


class ValidationError(AVAROSError):
    """Input validation errors (invalid metric, asset_id, period, etc.)"""
    
    def __init__(self, message: str, code: str = "VALIDATION_ERROR", details: Optional[Dict] = None):
        super().__init__(message, code, details)


class ConfigurationError(AVAROSError):
    """Configuration errors (missing settings, invalid config values)"""
    
    def __init__(self, message: str, code: str = "CONFIG_ERROR", details: Optional[Dict] = None):
        super().__init__(message, code, details)


class QueryError(AVAROSError):
    """Query execution errors (timeout, invalid query, etc.)"""
    
    def __init__(self, message: str, code: str = "QUERY_ERROR", details: Optional[Dict] = None):
        super().__init__(message, code, details)


class DataError(AVAROSError):
    """Data processing errors (parsing, transformation, etc.)"""
    
    def __init__(self, message: str, code: str = "DATA_ERROR", details: Optional[Dict] = None):
        super().__init__(message, code, details)


class TestAVAROSErrorBase:
    """Test base AVAROSError exception"""
    
    def test_base_error_creation(self):
        """Test creating base AVAROSError"""
        error = AVAROSError(
            message="Something went wrong",
            code="GENERIC_ERROR",
            details={"context": "test"}
        )
        
        assert error.message == "Something went wrong"
        assert error.code == "GENERIC_ERROR"
        assert error.details == {"context": "test"}
    
    def test_base_error_string_representation(self):
        """Test error string formatting"""
        error = AVAROSError(
            message="Test error",
            code="TEST_ERROR"
        )
        
        assert str(error) == "[TEST_ERROR] Test error"
    
    def test_base_error_to_dict(self):
        """Test error serialization to dictionary"""
        error = AVAROSError(
            message="Test error",
            code="TEST_ERROR",
            details={"field": "value"}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "AVAROSError"
        assert error_dict["message"] == "Test error"
        assert error_dict["code"] == "TEST_ERROR"
        assert error_dict["details"] == {"field": "value"}
    
    def test_base_error_without_details(self):
        """Test creating error without details parameter"""
        error = AVAROSError(
            message="Simple error",
            code="SIMPLE_ERROR"
        )
        
        assert error.details == {}
    
    def test_base_error_is_exception(self):
        """Test that AVAROSError is an Exception"""
        error = AVAROSError("test", "TEST")
        
        assert isinstance(error, Exception)
        
        # Test that it can be raised and caught
        with pytest.raises(AVAROSError):
            raise error


class TestAdapterError:
    """Test AdapterError exception"""
    
    def test_adapter_error_creation(self):
        """Test creating AdapterError"""
        error = AdapterError(
            message="Failed to connect to platform",
            code="PLATFORM_UNAVAILABLE",
            details={"api_url": "http://example.com"}
        )
        
        assert error.message == "Failed to connect to platform"
        assert error.code == "PLATFORM_UNAVAILABLE"
        assert isinstance(error, AVAROSError)
    
    def test_adapter_error_default_code(self):
        """Test AdapterError with default error code"""
        error = AdapterError(message="Connection failed")
        
        assert error.code == "ADAPTER_ERROR"
    
    def test_adapter_error_inherits_base(self):
        """Test that AdapterError inherits from AVAROSError"""
        error = AdapterError("test", "TEST")
        
        assert isinstance(error, AVAROSError)
        assert isinstance(error, Exception)
    
    def test_adapter_error_to_dict(self):
        """Test AdapterError serialization"""
        error = AdapterError(
            message="API timeout",
            code="API_TIMEOUT",
            details={"timeout_seconds": 30}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "AdapterError"
        assert error_dict["code"] == "API_TIMEOUT"


class TestValidationError:
    """Test ValidationError exception"""
    
    def test_validation_error_creation(self):
        """Test creating ValidationError"""
        error = ValidationError(
            message="Invalid asset_id format",
            code="INVALID_ASSET_ID",
            details={"asset_id": "invalid@id", "expected": "alphanumeric"}
        )
        
        assert error.message == "Invalid asset_id format"
        assert error.code == "INVALID_ASSET_ID"
        assert isinstance(error, AVAROSError)
    
    def test_validation_error_default_code(self):
        """Test ValidationError with default error code"""
        error = ValidationError(message="Invalid input")
        
        assert error.code == "VALIDATION_ERROR"
    
    def test_validation_error_field_details(self):
        """Test ValidationError with field details"""
        error = ValidationError(
            message="Invalid metric",
            details={"field": "metric", "value": "unknown_metric"}
        )
        
        assert error.details["field"] == "metric"
        assert error.details["value"] == "unknown_metric"


class TestConfigurationError:
    """Test ConfigurationError exception"""
    
    def test_configuration_error_creation(self):
        """Test creating ConfigurationError"""
        error = ConfigurationError(
            message="Missing required configuration",
            code="CONFIG_MISSING",
            details={"missing_keys": ["api_url", "api_key"]}
        )
        
        assert error.message == "Missing required configuration"
        assert error.code == "CONFIG_MISSING"
        assert isinstance(error, AVAROSError)
    
    def test_configuration_error_default_code(self):
        """Test ConfigurationError with default error code"""
        error = ConfigurationError(message="Invalid config")
        
        assert error.code == "CONFIG_ERROR"


class TestQueryError:
    """Test QueryError exception"""
    
    def test_query_error_creation(self):
        """Test creating QueryError"""
        error = QueryError(
            message="Query execution timeout",
            code="QUERY_TIMEOUT",
            details={"query_id": "q-12345", "timeout_seconds": 60}
        )
        
        assert error.message == "Query execution timeout"
        assert error.code == "QUERY_TIMEOUT"
        assert isinstance(error, AVAROSError)
    
    def test_query_error_default_code(self):
        """Test QueryError with default error code"""
        error = QueryError(message="Query failed")
        
        assert error.code == "QUERY_ERROR"


class TestDataError:
    """Test DataError exception"""
    
    def test_data_error_creation(self):
        """Test creating DataError"""
        error = DataError(
            message="Failed to parse response",
            code="PARSE_ERROR",
            details={"format": "json", "raw_data": "invalid"}
        )
        
        assert error.message == "Failed to parse response"
        assert error.code == "PARSE_ERROR"
        assert isinstance(error, AVAROSError)
    
    def test_data_error_default_code(self):
        """Test DataError with default error code"""
        error = DataError(message="Data processing failed")
        
        assert error.code == "DATA_ERROR"


class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance"""
    
    def test_all_exceptions_inherit_base(self):
        """Test that all custom exceptions inherit from AVAROSError"""
        exception_classes = [
            AdapterError,
            ValidationError,
            ConfigurationError,
            QueryError,
            DataError
        ]
        
        for exc_class in exception_classes:
            instance = exc_class("test message")
            assert isinstance(instance, AVAROSError)
            assert isinstance(instance, Exception)
    
    def test_exception_catching_by_base(self):
        """Test that specific exceptions can be caught by base class"""
        specific_errors = [
            AdapterError("adapter error"),
            ValidationError("validation error"),
            ConfigurationError("config error"),
            QueryError("query error"),
            DataError("data error")
        ]
        
        for error in specific_errors:
            with pytest.raises(AVAROSError):
                raise error
    
    def test_exception_catching_specifically(self):
        """Test that specific exceptions can be caught individually"""
        with pytest.raises(AdapterError):
            raise AdapterError("specific error")
        
        with pytest.raises(ValidationError):
            raise ValidationError("validation failed")
    
    def test_all_exceptions_have_to_dict(self):
        """Test that all exceptions support to_dict serialization"""
        exception_classes = [
            AVAROSError,
            AdapterError,
            ValidationError,
            ConfigurationError,
            QueryError,
            DataError
        ]
        
        for exc_class in exception_classes:
            error = exc_class("test", "TEST_CODE")
            error_dict = error.to_dict()
            
            assert "error_type" in error_dict
            assert "message" in error_dict
            assert "code" in error_dict
            assert "details" in error_dict


class TestErrorCodeConventions:
    """Test error code naming conventions"""
    
    def test_error_codes_are_uppercase(self):
        """Test that error codes follow UPPER_SNAKE_CASE convention"""
        error = AVAROSError("test", "TEST_ERROR_CODE")
        
        assert error.code.isupper()
        assert "_" in error.code
    
    def test_specific_error_codes(self):
        """Test specific error code examples"""
        test_cases = [
            (AdapterError("test", "PLATFORM_UNAVAILABLE"), "PLATFORM_UNAVAILABLE"),
            (AdapterError("test", "API_TIMEOUT"), "API_TIMEOUT"),
            (ValidationError("test", "INVALID_ASSET_ID"), "INVALID_ASSET_ID"),
            (ValidationError("test", "INVALID_METRIC"), "INVALID_METRIC"),
            (ConfigurationError("test", "CONFIG_MISSING"), "CONFIG_MISSING"),
            (QueryError("test", "QUERY_TIMEOUT"), "QUERY_TIMEOUT"),
            (DataError("test", "PARSE_ERROR"), "PARSE_ERROR")
        ]
        
        for error, expected_code in test_cases:
            assert error.code == expected_code


class TestErrorContextDetails:
    """Test error context and detail information"""
    
    def test_error_with_rich_context(self):
        """Test error with detailed context information"""
        error = AdapterError(
            message="Failed to retrieve KPI",
            code="KPI_RETRIEVAL_FAILED",
            details={
                "metric": "energy_per_unit",
                "asset_id": "compressor-1",
                "period": "today",
                "api_url": "http://example.com/api",
                "http_status": 500,
                "timestamp": "2026-01-30T10:00:00Z"
            }
        )
        
        assert error.details["metric"] == "energy_per_unit"
        assert error.details["http_status"] == 500
        assert len(error.details) == 6
    
    def test_error_details_in_serialization(self):
        """Test that error details are preserved in serialization"""
        original_details = {
            "field": "asset_id",
            "value": "invalid",
            "constraint": "alphanumeric"
        }
        
        error = ValidationError(
            message="Invalid input",
            code="VALIDATION_FAILED",
            details=original_details
        )
        
        serialized = error.to_dict()
        
        assert serialized["details"] == original_details
