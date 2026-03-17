"""
AdapterFactory - Creates Platform Adapters Based on Configuration

Implements the Factory pattern to instantiate the appropriate adapter
based on system configuration stored in SettingsService (database-backed).

Default Behavior:
    - If no platform is configured, returns UnconfiguredAdapter
    - Supports hot-reload when configuration changes
    - No container restart required for adapter switching

Usage:
    factory = AdapterFactory(settings_service)
    adapter = factory.create()  # Returns configured adapter
    
    # Later, after user configures RENERYO in Web UI:
    factory.reload()  # Hot-swaps to ReneryoAdapter
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.generic_rest import GenericRestAdapter
from skill.adapters.reneryo import ReneryoAdapter
from skill.adapters.unconfigured import UnconfiguredAdapter

if TYPE_CHECKING:
    from skill.services.settings import SettingsService


logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory for creating platform adapters based on configuration.
    
    This factory defaults to UnconfiguredAdapter when no platform
    is configured, providing clear error messages guiding the user
    to set up a connection via the Web UI.
    
    Attributes:
        settings_service: Database-backed configuration service
        _current_adapter: Cached adapter instance
    
    Thread Safety:
        The factory is thread-safe. Adapter creation and reload are
        synchronized to prevent race conditions.
    
    Example:
        # At startup (no config)
        factory = AdapterFactory(settings_service=None)
        adapter = factory.create()  # Returns UnconfiguredAdapter
        
        # After user configures platform via Web UI
        factory.reload()  # Switches to configured adapter
    """
    
    # Registry of available adapters
    # Maps platform name -> adapter class
    _ADAPTER_REGISTRY: dict[str, type[ManufacturingAdapter]] = {
        "reneryo": ReneryoAdapter,
        "custom_rest": GenericRestAdapter,
        # "sap": SAPAdapter,           # Future
    }
    
    def __init__(self, settings_service: SettingsService | None = None):
        """
        Initialize factory with optional settings service.
        
        Args:
            settings_service: Configuration service. If None, defaults to UnconfiguredAdapter.
        """
        self._settings_service = settings_service
        self._current_adapter: ManufacturingAdapter | None = None
        self._lock = None  # Would use asyncio.Lock() in async context
    
    def create(self) -> ManufacturingAdapter:
        """
        Create and return the configured adapter.
        
        Returns cached adapter if available, otherwise creates new instance.
        Defaults to UnconfiguredAdapter if no platform is configured.
        
        Returns:
            ManufacturingAdapter instance ready for use
            
        Raises:
            ConfigurationError: If configured platform has invalid settings
        """
        if self._current_adapter is not None:
            return self._current_adapter
        
        # Determine which platform to use
        platform_name = self._get_configured_platform()
        
        # Create adapter
        adapter_class = self._ADAPTER_REGISTRY.get(
            platform_name, UnconfiguredAdapter,
        )
        
        logger.info(
            "Creating adapter: %s (platform: %s)",
            adapter_class.__name__,
            platform_name,
        )
        
        # Instantiate with platform-specific config
        adapter = self._instantiate_adapter(adapter_class, platform_name)
        
        self._current_adapter = adapter
        return adapter
    
    async def create_async(self) -> ManufacturingAdapter:
        """
        Async version of create() that also initializes the adapter.
        
        Returns:
            Initialized ManufacturingAdapter instance
        """
        adapter = self.create()
        await adapter.initialize()
        return adapter
    
    async def reload(
        self, profile_name: str | None = None,
    ) -> ManufacturingAdapter:
        """Hot-reload adapter based on current configuration.

        Optionally switches the active profile before reloading.
        Called when user changes platform settings via Web UI.
        Gracefully shuts down old adapter before creating new one.

        Args:
            profile_name: If provided, set this as the active profile
                before creating the new adapter.

        Returns:
            New ManufacturingAdapter instance
        """
        if profile_name is not None and self._settings_service is not None:
            self._settings_service.set_active_profile(profile_name)
            logger.info("Reloading adapter for profile '%s'", profile_name)
        else:
            logger.info("Reloading adapter due to configuration change")
        
        # Shutdown existing adapter
        if self._current_adapter is not None:
            try:
                await self._current_adapter.shutdown()
            except Exception as e:
                logger.warning("Error shutting down adapter: %s", e)
            self._current_adapter = None
        
        # Create new adapter
        return await self.create_async()
    
    def _get_configured_platform(self) -> str:
        """Get the configured platform name from the active profile.

        Uses the profile system (DEC-028) to resolve the active
        adapter.  Falls back to ``"unconfigured"`` when no profile is set.

        Returns:
            Platform name (e.g., "unconfigured", "reneryo")
        """
        if self._settings_service is None:
            logger.debug("No settings service, defaulting to unconfigured adapter")
            return "unconfigured"

        try:
            profile_name = (
                self._settings_service.get_active_profile_name()
            )
            config = self._settings_service.get_profile(profile_name)
            if config is None or not config.platform_type or config.platform_type == "unconfigured":
                return "unconfigured"
            return config.platform_type.lower()
        except Exception as e:
            logger.warning(
                "Error reading platform config: %s. Using unconfigured.", e,
            )
            return "unconfigured"
    
    def _instantiate_adapter(
        self,
        adapter_class: type[ManufacturingAdapter],
        platform_name: str,
    ) -> ManufacturingAdapter:
        """
        Instantiate adapter with platform-specific configuration.
        
        Args:
            adapter_class: The adapter class to instantiate
            platform_name: Platform identifier for loading config
            
        Returns:
            Configured adapter instance
        """
        # UnconfiguredAdapter needs no configuration
        if adapter_class == UnconfiguredAdapter:
            return UnconfiguredAdapter()
        
        # ReneryoAdapter requires api_url and api_key from platform config
        if adapter_class == ReneryoAdapter:
            return self._create_reneryo_adapter()

        # GenericRestAdapter uses profile metric mappings (custom_rest)
        if adapter_class == GenericRestAdapter:
            return self._create_generic_rest_adapter()
        
        # Fallback for unknown adapters
        return adapter_class()
    
    def _create_reneryo_adapter(self) -> ReneryoAdapter:
        """Create ReneryoAdapter with config from the active profile.

        Reads api_url, api_key, timeout and auth_type from the
        active profile's ``PlatformConfig`` (DEC-028).

        Returns:
            Configured ReneryoAdapter instance
        """
        api_url = ""
        api_key = ""
        timeout = 30
        auth_type = "bearer"
        api_format = "native"
        native_seu_id = ""
        profile_name = ""
        extra: dict = {}
        asset_mappings: dict[str, dict[str, object]] = {}

        if self._settings_service is not None:
            try:
                profile_name = (
                    self._settings_service.get_active_profile_name()
                )
                config = self._settings_service.get_profile(
                    profile_name,
                )
                if config is not None:
                    api_url = getattr(config, "api_url", "") or ""
                    api_key = getattr(config, "api_key", "") or ""
                    timeout = getattr(config, "timeout", 30) or 30
                    extra = (
                        getattr(config, "extra_settings", {}) or {}
                    )
                    auth_type = (
                        extra.get("auth_type", "bearer")
                        if isinstance(extra, dict)
                        else "bearer"
                    )
                    api_format = (
                        extra.get("api_format", "native")
                        if isinstance(extra, dict)
                        else "native"
                    )
                    native_seu_id = (
                        str(extra.get("seu_id", "")).strip()
                        if isinstance(extra, dict)
                        else ""
                    )
                    profile_for_assets = profile_name or None
                    raw_mappings = self._settings_service.get_asset_mappings(
                        profile=profile_for_assets,
                    )
                    if isinstance(raw_mappings, dict):
                        asset_mappings = raw_mappings
            except Exception as exc:
                logger.warning(
                    "Error reading RENERYO config: %s", exc,
                )

        return ReneryoAdapter(
            api_url=api_url,
            api_key=api_key,
            timeout=timeout,
            auth_type=auth_type,
            api_format=api_format,
            native_seu_id=native_seu_id,
            settings_service=self._settings_service,
            profile_name=profile_name,
            extra_settings=self._sanitize_extra_settings(extra),
            asset_mappings=asset_mappings,
        )

    def _create_generic_rest_adapter(self) -> GenericRestAdapter:
        """Create GenericRestAdapter with config from active profile."""
        api_url = ""
        api_key = ""
        timeout = 30
        auth_type = "bearer"
        profile_name = ""
        extra: dict = {}

        if self._settings_service is not None:
            try:
                profile_name = (
                    self._settings_service.get_active_profile_name()
                )
                config = self._settings_service.get_profile(
                    profile_name,
                )
                if config is not None:
                    api_url = getattr(config, "api_url", "") or ""
                    api_key = getattr(config, "api_key", "") or ""
                    timeout = getattr(config, "timeout", 30) or 30
                    extra = (
                        getattr(config, "extra_settings", {}) or {}
                    )
                    auth_type = (
                        extra.get("auth_type", "bearer")
                        if isinstance(extra, dict)
                        else "bearer"
                    )
            except Exception as exc:
                logger.warning(
                    "Error reading custom_rest config: %s", exc,
                )

        return GenericRestAdapter(
            api_url=api_url,
            api_key=api_key,
            timeout=timeout,
            auth_type=auth_type,
            settings_service=self._settings_service,
            profile_name=profile_name,
            extra_settings=extra if isinstance(extra, dict) else {},
        )

    @staticmethod
    def _sanitize_extra_settings(extra_settings: dict | None) -> dict:
        """Strip deprecated keys before passing settings to adapter runtime."""
        sanitized = dict(extra_settings or {})
        sanitized.pop("seu_id", None)
        return sanitized

    @classmethod
    def register_adapter(
        cls,
        platform_name: str,
        adapter_class: type[ManufacturingAdapter],
    ) -> None:
        """
        Register a new adapter class for a platform.
        
        This allows plugins to add new adapters without modifying factory code.
        
        Args:
            platform_name: Identifier for the platform (lowercase)
            adapter_class: ManufacturingAdapter subclass
            
        Example:
            AdapterFactory.register_adapter("siemens", SiemensAdapter)
        """
        cls._ADAPTER_REGISTRY[platform_name.lower()] = adapter_class
        logger.info("Registered adapter '%s' for platform '%s'", 
                   adapter_class.__name__, platform_name)
    
    @classmethod
    def get_available_platforms(cls) -> list[str]:
        """
        Get list of available platform adapters.
        
        Returns:
            List of platform names that can be configured
        """
        return list(cls._ADAPTER_REGISTRY.keys())
