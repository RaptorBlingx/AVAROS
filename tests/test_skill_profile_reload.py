"""Tests for Skill Runtime Adapter Reload (P5-L10 / DEC-029).

Validates the message bus listener, reload logic, mock fallback,
lazy profile mismatch detection, and event registration.

Test scenarios:
    - Profile switch via message bus → adapter reloaded
    - Reload failure → MockAdapter fallback (DEC-005)
    - Lazy reload on profile mismatch → automatic recovery
    - No mismatch → no reload
    - SettingsService None → lazy check skipped safely
    - Bus listener registered on initialize
    - Force mock fallback sets correct state
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from ovos_bus_client import MessageBusClient

from skill import AVAROSSkill
from skill.adapters.mock import MockAdapter
from skill.use_cases.query_dispatcher import QueryDispatcher


# ── Helpers ─────────────────────────────────────────────


def _make_skill() -> AVAROSSkill:
    """Create an AVAROSSkill with mocked OVOS framework parts."""
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.bus = MagicMock(spec=MessageBusClient)
    return skill


def _initialized_skill() -> AVAROSSkill:
    """Return a skill that has been fully initialized."""
    skill = _make_skill()
    skill.initialize()
    return skill


def _make_message(profile: str = "reneryo") -> Mock:
    """Build a fake OVOS message with ``data.profile``."""
    msg = Mock()
    msg.data = {"profile": profile}
    return msg


# ══════════════════════════════════════════════════════════
# Profile Switch Handler
# ══════════════════════════════════════════════════════════


class TestHandleProfileSwitch:
    """Tests for _handle_profile_switch()."""

    def test_handle_profile_switch_reloads_adapter(self):
        """Receiving a profile switch event reloads the adapter."""
        skill = _initialized_skill()
        original_dispatcher = skill.dispatcher

        # Mock the adapter factory reload to return a new MockAdapter
        new_adapter = MockAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        # Act
        skill._handle_profile_switch(_make_message("demo"))

        # Assert
        skill.adapter_factory.reload.assert_awaited_once_with("demo")
        assert skill.dispatcher is not original_dispatcher
        assert skill._loaded_profile == "demo"
        skill.log.info.assert_any_call(
            "Profile switch event received: '%s'", "demo",
        )

    def test_handle_profile_switch_failure_falls_back_to_mock(self):
        """When reload raises, skill falls back to MockAdapter (DEC-005)."""
        skill = _initialized_skill()

        skill.adapter_factory.reload = AsyncMock(
            side_effect=RuntimeError("connection refused"),
        )

        # Act
        skill._handle_profile_switch(_make_message("reneryo"))

        # Assert: MockAdapter fallback
        assert skill._loaded_profile == "mock"
        assert isinstance(
            skill.dispatcher._adapter, MockAdapter,
        )
        skill.log.error.assert_called_once()


# ══════════════════════════════════════════════════════════
# Lazy Reload (Profile Mismatch)
# ══════════════════════════════════════════════════════════


class TestLazyReload:
    """Tests for _check_profile_mismatch() (lazy reload)."""

    def test_lazy_reload_on_profile_mismatch(self):
        """Mismatch between loaded and active profile triggers reload."""
        skill = _initialized_skill()
        skill._loaded_profile = "mock"

        # Pretend DB says active profile is "reneryo"
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "reneryo"

        new_adapter = MockAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        # Act
        skill._check_profile_mismatch()

        # Assert
        skill.adapter_factory.reload.assert_awaited_once_with("reneryo")
        assert skill._loaded_profile == "reneryo"

    def test_lazy_reload_skipped_when_profile_matches(self):
        """No reload when loaded profile matches active profile."""
        skill = _initialized_skill()
        skill._loaded_profile = "mock"

        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "mock"

        skill.adapter_factory.reload = AsyncMock()

        # Act
        skill._check_profile_mismatch()

        # Assert: reload never called
        skill.adapter_factory.reload.assert_not_awaited()

    def test_lazy_reload_handles_settings_service_none(self):
        """No crash when settings_service is None."""
        skill = _initialized_skill()
        skill.settings_service = None

        # Act — should not raise
        skill._check_profile_mismatch()

    def test_lazy_reload_handles_settings_error(self):
        """Settings error is caught and logged, no crash."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.side_effect = RuntimeError(
            "DB gone",
        )

        # Act — should not raise
        skill._check_profile_mismatch()

        skill.log.warning.assert_any_call(
            "Profile mismatch check failed: %s",
            skill.settings_service.get_active_profile_name.side_effect,
        )


# ══════════════════════════════════════════════════════════
# Bus Listener Registration
# ══════════════════════════════════════════════════════════


class TestBusListenerRegistration:
    """Tests for event registration during initialize()."""

    def test_profile_switch_handler_registered_on_initialize(self):
        """initialize() registers the avaros.profile.activated listener."""
        skill = _initialized_skill()

        skill.bus.on.assert_called_once_with(
            "avaros.profile.activated",
            skill._handle_profile_switch,
        )


# ══════════════════════════════════════════════════════════
# Force Mock Fallback
# ══════════════════════════════════════════════════════════


class TestForceMockFallback:
    """Tests for _force_mock_fallback()."""

    def test_force_mock_fallback_sets_mock_adapter(self):
        """_force_mock_fallback() replaces dispatcher with MockAdapter."""
        skill = _initialized_skill()
        skill._loaded_profile = "reneryo"

        # Act
        skill._force_mock_fallback()

        # Assert
        assert skill._loaded_profile == "mock"
        assert isinstance(skill.dispatcher._adapter, MockAdapter)
        skill.log.info.assert_any_call("Forced MockAdapter fallback")


# ══════════════════════════════════════════════════════════
# _safe_dispatch Integration
# ══════════════════════════════════════════════════════════


class TestSafeDispatchProfileCheck:
    """Verify _safe_dispatch calls _check_profile_mismatch."""

    def test_safe_dispatch_calls_profile_mismatch_check(self):
        """_safe_dispatch invokes lazy profile check before action."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()

        result = skill._safe_dispatch("test_handler", lambda: 42)

        assert result == 42
        skill._check_profile_mismatch.assert_called_once()

    def test_safe_dispatch_still_works_when_dispatcher_none(self):
        """_safe_dispatch speaks error when dispatcher is None."""
        skill = _initialized_skill()
        skill.dispatcher = None
        skill.speak = Mock()

        result = skill._safe_dispatch("test", lambda: 1)

        assert result is None
        skill.speak.assert_called_once_with(
            "AVAROS is still initializing. Please try again.",
        )


# ══════════════════════════════════════════════════════════
# _reload_adapter Edge Cases
# ══════════════════════════════════════════════════════════


class TestReloadAdapterEdgeCases:
    """Edge cases for _reload_adapter()."""

    def test_reload_adapter_no_factory_logs_warning(self):
        """When adapter_factory is None, log warning and return."""
        skill = _initialized_skill()
        skill.adapter_factory = None

        # Act — should not raise
        skill._reload_adapter("demo")

        skill.log.warning.assert_any_call(
            "No adapter factory — cannot reload",
        )

    def test_reload_adapter_updates_dispatcher(self):
        """Successful reload creates a new QueryDispatcher."""
        skill = _initialized_skill()
        new_adapter = MockAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        old_dispatcher = skill.dispatcher

        # Act
        skill._reload_adapter("demo")

        # Assert
        assert skill.dispatcher is not old_dispatcher
        assert skill._loaded_profile == "demo"
