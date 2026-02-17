"""Configuration dataclasses for the AVAROS settings layer.

Pure data containers with no database or framework dependencies.
Imported by ``settings.py``, ``profiles.py``, and external callers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PlatformConfig:
    """Platform connection configuration.

    Attributes:
        platform_type: Adapter type ("mock", "reneryo", etc.)
        api_url: Platform API endpoint
        api_key: Authentication key (encrypted at rest)
        extra_settings: Platform-specific settings
    """

    platform_type: str = "mock"
    api_url: str = ""
    api_key: str = ""
    extra_settings: dict[str, Any] = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        """Check if a real platform is configured (not mock)."""
        return self.platform_type != "mock" and bool(self.api_url)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlatformConfig:
        """Create from dictionary."""
        return cls(
            platform_type=data.get("platform_type", "mock"),
            api_url=data.get("api_url", ""),
            api_key=data.get("api_key", ""),
            extra_settings=data.get("extra_settings", {}),
        )


@dataclass
class VoiceConfig:
    """HiveMind browser client configuration.

    Attributes:
        hivemind_url: WebSocket endpoint for HiveMind-core.
        hivemind_name: Client name for HiveMind authentication token.
        hivemind_key: Client access key.
        hivemind_secret: Client secret/password.
    """

    hivemind_url: str = "ws://localhost:5678"
    hivemind_name: str = "avaros-web-client"
    hivemind_key: str = ""
    hivemind_secret: str = ""
