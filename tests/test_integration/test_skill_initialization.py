"""
Integration Tests for Skill Initialization

Tests that SettingsService is correctly wired into AdapterFactory
during skill initialization. Validates that platform configuration
from the database (Web UI) is respected when creating adapters.

Test scenarios:
    - No database → UnconfiguredAdapter (zero-config)
    - Empty database → UnconfiguredAdapter (no config set)
    - Database with Reneryo config → ReneryoAdapter
    - Database error → UnconfiguredAdapter (graceful fallback)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from ovos_bus_client import MessageBusClient

from skill import AVAROSSkill
from skill.adapters.unconfigured import UnconfiguredAdapter
from skill.adapters.reneryo import ReneryoAdapter


def _make_skill() -> AVAROSSkill:
    """Create an AVAROSSkill with mocked OVOS framework parts."""
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.bus = MagicMock(spec=MessageBusClient)
    return skill


# ══════════════════════════════════════════════════════════
# Test Skill Initialization with SettingsService
# ══════════════════════════════════════════════════════════


class TestSkillInitializationNoDatabase:
    """Test skill initialization when no database is configured."""

    def test_initialize_no_db_env_uses_mock_adapter(self):
        """When AVAROS_DATABASE_URL is not set, skill uses UnconfiguredAdapter."""
        # Arrange: ensure no DB URL in environment
        with patch.dict(os.environ, {}, clear=False):
            if "AVAROS_DATABASE_URL" in os.environ:
                del os.environ["AVAROS_DATABASE_URL"]
            
            skill = _make_skill()
            
            # Act: initialize the skill
            skill.initialize()
            
            # Assert: UnconfiguredAdapter is created
            assert skill.adapter_factory is not None
            adapter = skill.adapter_factory._current_adapter
            assert isinstance(adapter, UnconfiguredAdapter)
            assert skill.dispatcher is not None


class TestSkillInitializationWithDatabase:
    """Test skill initialization when database is configured."""

    def test_initialize_empty_config_uses_mock_adapter(self):
        """When DB is set but no platform configured, skill uses UnconfiguredAdapter."""
        # Arrange: in-memory SQLite DB
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            
            # Act: initialize the skill
            skill.initialize()
            
            # Assert: UnconfiguredAdapter is created (no config in empty DB)
            assert skill.adapter_factory is not None
            adapter = skill.adapter_factory._current_adapter
            assert isinstance(adapter, UnconfiguredAdapter)

    def test_initialize_with_reneryo_config_creates_reneryo_adapter(self):
        """When Reneryo is configured via Web UI, skill uses ReneryoAdapter."""
        # Arrange: in-memory SQLite DB with Reneryo config
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            
            # Initialize first
            skill.initialize()
            
            # Configure RENERYO via SettingsService
            from skill.services.settings import PlatformConfig
            from skill.adapters.factory import AdapterFactory
            
            assert skill.settings_service is not None
            skill.settings_service.update_platform_config(
                PlatformConfig(
                    platform_type="reneryo",
                    api_url="https://api.reneryo.example.com/v1",
                    api_key="test-key-123",
                    extra_settings={"tenant_id": "test-tenant"},
                )
            )
            
            # Act: Create new adapter factory with configured settings
            new_factory = AdapterFactory(settings_service=skill.settings_service)
            new_adapter = new_factory.create()
            
            # Assert: ReneryoAdapter is created
            assert isinstance(new_adapter, ReneryoAdapter)


class TestSkillInitializationErrorHandling:
    """Test graceful fallback when SettingsService fails."""

    def test_initialize_with_bad_db_url_falls_back_to_mock(self):
        """When SettingsService fails to initialize, skill falls back to UnconfiguredAdapter."""
        # Arrange: invalid DB URL that will cause SettingsService to fail
        with patch.dict(
            os.environ,
            {"AVAROS_DATABASE_URL": "postgresql://invalid:5432/nonexistent"},
        ):
            skill = _make_skill()
            
            # Act: initialize the skill (SettingsService will fail)
            skill.initialize()
            
            # Assert: UnconfiguredAdapter is created (graceful fallback)
            assert skill.adapter_factory is not None
            adapter = skill.adapter_factory._current_adapter
            assert isinstance(adapter, UnconfiguredAdapter)
            
            # Warning was logged
            skill.log.warning.assert_called_once()
            assert "SettingsService initialization failed" in skill.log.warning.call_args[0][0]
            
            # Still initialized successfully with UnconfiguredAdapter
            skill.log.info.assert_any_call(
                "AVAROS skill initialized with adapter: %s (profile='%s')",
                "UnconfiguredAdapter",
                "unconfigured",
            )

    def test_settings_service_exists_even_when_db_is_inaccessible(self):
        """
        When SettingsService can't connect to DB, skill still initializes with MockAdapter.
        """
        # Arrange: PostgreSQL URL without psycopg2 installed
        with patch.dict(
            os.environ,
            {"AVAROS_DATABASE_URL": "postgresql://invalid:5432/bad"},
        ):
            skill = _make_skill()
            
            # Act
            skill.initialize()
            
            # Assert: SettingsService exists (created successfully)
            assert skill.settings_service is not None
            
            # Assert: UnconfiguredAdapter is used as fallback
            assert skill.adapter_factory is not None
            adapter = skill.adapter_factory._current_adapter
            assert isinstance(adapter, UnconfiguredAdapter)
            
            # Assert: Skill initialized successfully (using UnconfiguredAdapter)
            skill.log.info.assert_any_call(
                "AVAROS skill initialized with adapter: %s (profile='%s')",
                "UnconfiguredAdapter",
                "unconfigured",
            )


class TestSkillAttributesAfterInitialization:
    """Test that all skill attributes are properly set after initialize()."""

    def test_all_required_attributes_are_set(self):
        """After initialize(), skill has all required components."""
        # Arrange
        skill = _make_skill()
        
        # Act
        skill.initialize()
        
        # Assert: all attributes are set
        assert skill.adapter_factory is not None
        assert skill.dispatcher is not None
        assert skill.response_builder is not None
        # settings_service may be None (no DB) but attribute exists
        assert hasattr(skill, "settings_service")
