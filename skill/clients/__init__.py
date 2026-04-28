"""
AVAROS External Service Clients

Client interfaces and implementations for WASABI consortium services.
Each client follows the ExternalServiceClient ABC contract.

Available Clients:
    - PreventionClient: Anomaly detection and drift monitoring

Design Principles:
    - Platform-agnostic interfaces (DEC-001)
    - Clean architecture: domain models in skill.domain (DEC-003)
    - Clients fetch data only; intelligence in QueryDispatcher (DEC-007)
    - Connection details via SettingsService (DEC-006)
    - Graceful degradation when services unavailable (DEC-005)
"""

from skill.clients.base import ExternalServiceClient
from skill.clients.prevention import (
    PreventionClient,
)

__all__ = [
    "ExternalServiceClient",
    "PreventionClient",
]
