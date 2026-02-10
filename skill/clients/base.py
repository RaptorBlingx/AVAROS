"""
ExternalServiceClient — Abstract Base Class

Defines the contract for all WASABI consortium service clients.
Each external service (DocuBoT, PREVENTION, etc.) implements
this interface for lifecycle management and health monitoring.

Design Principles:
    - Async-first for I/O efficiency
    - Health check for graceful degradation
    - Lifecycle hooks for resource management
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExternalServiceClient(ABC):
    """
    Base class for WASABI consortium service clients.

    All external service integrations must implement this interface
    to ensure consistent lifecycle management, health monitoring,
    and graceful degradation.

    Implementing Classes:
        - DocuBotClient: Document-grounded Q&A
        - PreventionClient: Predictive maintenance (P3-L04)

    Lifecycle:
        1. Create instance
        2. Call initialize() to establish connection
        3. Use service-specific methods
        4. Call shutdown() for cleanup

    Example:
        client = MockDocuBotClient()
        await client.initialize()
        if await client.health_check():
            result = await client.search_documents("energy reduction")
        await client.shutdown()
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the client connection.

        Called once during skill startup to establish connections,
        authenticate, and prepare resources.

        Raises:
            ConnectionError: If service is unreachable
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Clean up resources and close connections.

        Called during skill shutdown for graceful cleanup.
        Must be safe to call multiple times.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the external service is available.

        Returns:
            True if the service is reachable and operational

        Note:
            Should be lightweight — no heavy processing.
            Used by Web UI status endpoint and graceful degradation.
        """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """
        Human-readable name for logging and status display.

        Returns:
            Service name (e.g., "Document Q&A", "Predictive Maintenance")
        """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Whether the client currently has an active connection.

        Returns:
            True if connected and ready to accept requests
        """
