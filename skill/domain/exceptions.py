"""
AVAROS Domain Exceptions

Hierarchical exception classes for structured error handling.
All exceptions include codes for logging and user-friendly messages.

Hierarchy:
    AVAROSError (base)
    ├── ValidationError - Invalid input
    ├── AdapterError - Platform communication issues
    ├── MetricNotSupportedError - Metric unavailable
    └── AssetNotFoundError - Unknown asset
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AVAROSError(Exception):
    """
    Base exception for all AVAROS errors.
    
    Provides structured error information for logging, audit trails,
    and user-friendly voice responses.
    
    Attributes:
        message: Human-readable error description
        code: Machine-readable error code for logging
        details: Additional context for debugging
        user_message: Simplified message for voice response
    """
    
    message: str
    code: str = "AVAROS_ERROR"
    details: dict[str, Any] = field(default_factory=dict)
    user_message: str = ""
    
    def __post_init__(self):
        """Set default user message if not provided."""
        if not self.user_message:
            self.user_message = "I encountered an error processing your request."
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Return formatted error message."""
        return f"[{self.code}] {self.message}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "user_message": self.user_message,
        }


@dataclass
class ValidationError(AVAROSError):
    """
    Invalid input parameters.
    
    Raised when user input or API parameters fail validation.
    
    Example:
        ValidationError(
            message="Invalid period format",
            field="period",
            value="yesterday yesterday"
        )
    """
    
    field: str = ""
    value: Any = None
    code: str = "VALIDATION_ERROR"
    
    def __post_init__(self):
        """Build detailed message including field info."""
        if self.field and not self.details:
            self.details = {"field": self.field, "value": str(self.value)}
        if not self.user_message:
            self.user_message = f"I didn't understand the {self.field}. Could you rephrase?"
        super().__post_init__()


@dataclass
class AdapterError(AVAROSError):
    """
    Platform adapter communication error.
    
    Raised when an adapter fails to communicate with its platform API.
    Contains both technical details (for logs) and user message (for voice).
    
    Example:
        AdapterError(
            message="RENERYO API timeout after 30s",
            platform="reneryo",
            status_code=504
        )
    """
    
    platform: str = "unknown"
    status_code: int | None = None
    code: str = "ADAPTER_ERROR"
    
    def __post_init__(self):
        """Build details from platform info."""
        self.details = {
            "platform": self.platform,
            "status_code": self.status_code,
        }
        if not self.user_message:
            self.user_message = "I'm having trouble connecting to the data source. Please try again."
        super().__post_init__()


@dataclass
class MetricNotSupportedError(AVAROSError):
    """
    Requested metric is not available.
    
    Raised when a metric is not supported by the current adapter
    or not available for the specified asset.
    
    Example:
        MetricNotSupportedError(
            metric="supplier_co2_per_kg",
            platform="mock",
            available_metrics=["oee", "energy_per_unit"]
        )
    """
    
    metric: str = ""
    platform: str = ""
    available_metrics: list[str] = field(default_factory=list)
    code: str = "METRIC_NOT_SUPPORTED"
    
    def __post_init__(self):
        """Build message and details."""
        if not self.message:
            self.message = f"Metric '{self.metric}' not supported by {self.platform}"
        self.details = {
            "metric": self.metric,
            "platform": self.platform,
            "available_metrics": self.available_metrics,
        }
        if not self.user_message:
            self.user_message = f"Sorry, {self.metric.replace('_', ' ')} data isn't available right now."
        super().__post_init__()


@dataclass
class AssetNotFoundError(AVAROSError):
    """
    Requested asset does not exist.
    
    Raised when an asset ID is not found in the system.
    
    Example:
        AssetNotFoundError(
            asset_id="Line-99",
            available_assets=["Line-1", "Line-2", "Compressor-1"]
        )
    """
    
    asset_id: str = ""
    available_assets: list[str] = field(default_factory=list)
    code: str = "ASSET_NOT_FOUND"
    
    def __post_init__(self):
        """Build message and details."""
        if not self.message:
            self.message = f"Asset '{self.asset_id}' not found"
        self.details = {
            "asset_id": self.asset_id,
            "available_assets": self.available_assets[:10],  # Limit to avoid huge logs
        }
        if not self.user_message:
            self.user_message = f"I couldn't find an asset called {self.asset_id}."
        super().__post_init__()


@dataclass  
class ConfigurationError(AVAROSError):
    """
    System configuration error.
    
    Raised when required configuration is missing or invalid.
    
    Example:
        ConfigurationError(
            message="API key not configured",
            setting="platform.api_key"
        )
    """
    
    setting: str = ""
    code: str = "CONFIG_ERROR"
    
    def __post_init__(self):
        """Build details."""
        self.details = {"setting": self.setting}
        if not self.user_message:
            self.user_message = "The system needs to be configured. Please contact your administrator."
        super().__post_init__()
