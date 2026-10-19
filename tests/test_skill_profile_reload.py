"""Tests for Skill Runtime Adapter Reload (P5-L10 / DEC-029).

Validates the message bus listener, reload logic, unconfigured fallback,
lazy profile mismatch detection, and event registration.

Test scenarios:
    - Profile switch via message bus → adapter reloaded
    - Reload failure → UnconfiguredAdapter fallback (DEC-005)
    - Lazy reload on profile mismatch → automatic recovery
    - No mismatch → no reload
    - SettingsService None → lazy check skipped safely
    - Bus listener registered on initialize
    - Force unconfigured fallback sets correct state
"""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from ovos_bus_client import MessageBusClient

from skill import AVAROSSkill
from skill.adapters.unconfigured import UnconfiguredAdapter
from skill.domain.exceptions import AVAROSError
from skill.domain.models import Asset, CanonicalMetric
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


def _make_message(profile: str = "my-api") -> Mock:
    """Build a fake OVOS message with ``data.profile``."""
    msg = Mock()
    msg.data = {"profile": profile}
    return msg


def _assert_structured_speak(skill: AVAROSSkill, headline: str) -> None:
    """Assert the compatible headline plus browser evidence envelope."""
    skill.speak.assert_called_once()
    assert skill.speak.call_args.args[0] == headline
    assert "avaros_response" in skill.speak.call_args.kwargs["meta"]


# ══════════════════════════════════════════════════════════
# Profile Switch Handler
# ══════════════════════════════════════════════════════════


class TestHandleProfileSwitch:
    """Tests for _handle_profile_switch()."""

    def test_handle_profile_switch_reloads_adapter(self):
        """Receiving a profile switch event reloads the adapter."""
        skill = _initialized_skill()
        original_dispatcher = skill.dispatcher
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type="custom_rest"
        skill.settings_service.get_profile.return_value = profile

        # Mock the adapter factory reload to return a new adapter
        new_adapter = UnconfiguredAdapter()
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
        """When reload raises, skill falls back to UnconfiguredAdapter (DEC-005)."""
        skill = _initialized_skill()

        skill.adapter_factory.reload = AsyncMock(
            side_effect=RuntimeError("connection refused"),
        )

        # Act
        skill._handle_profile_switch(_make_message("my-api"))

        # Assert: UnconfiguredAdapter fallback
        assert skill._loaded_profile == "unconfigured"
        assert isinstance(
            skill.dispatcher._adapter, UnconfiguredAdapter,
        )
        skill.log.error.assert_called_once()

    def test_handle_profile_switch_recovers_missing_factory(self):
        """When adapter_factory is missing, runtime recovery recreates it."""
        skill = _initialized_skill()
        skill.adapter_factory = None
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"

        skill._handle_profile_switch(_make_message("my-api"))

        assert skill.adapter_factory is not None


# ══════════════════════════════════════════════════════════
# Lazy Reload (Profile Mismatch)
# ══════════════════════════════════════════════════════════


class TestLazyReload:
    """Tests for _check_profile_mismatch() (lazy reload)."""

    def test_lazy_reload_on_profile_mismatch(self):
        """Mismatch between loaded and active profile triggers reload."""
        skill = _initialized_skill()
        skill._loaded_profile = "unconfigured"

        # Pretend DB says active profile is "my-api"
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"

        new_adapter = UnconfiguredAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        # Act
        skill._check_profile_mismatch()

        # Assert
        skill.adapter_factory.reload.assert_awaited_once_with("my-api")
        assert skill._loaded_profile == "my-api"

    def test_lazy_reload_skipped_when_profile_matches(self):
        """No reload when loaded profile matches active profile."""
        skill = _initialized_skill()
        skill._loaded_profile = "unconfigured"
        skill._loaded_platform = "unconfigured"

        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "unconfigured"
        profile = Mock()
        profile.platform_type = ""
        skill.settings_service.get_profile.return_value = profile

        skill.adapter_factory.reload = AsyncMock()

        # Act
        skill._check_profile_mismatch()

        # Assert: reload never called
        skill.adapter_factory.reload.assert_not_awaited()

    def test_expected_platform_normalizes_rest_profiles_to_generic_rest(self):
        """custom_rest/reneryo/mock profiles should map to GenericRest runtime platform."""
        skill = _initialized_skill()
        skill.settings_service = Mock()

        for platform_type in ("custom_rest", "reneryo", "mock"):
            skill.settings_service.get_profile.return_value = Mock(
                platform_type=platform_type,
            )
            assert skill._expected_platform_for_profile("demo") == "generic_rest"

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

        skill.bus.on.assert_any_call(
            "avaros.profile.activated",
            skill._handle_profile_switch,
        )

    def test_intent_failure_handler_registered_on_initialize(self):
        """initialize() registers the intent_failure listener."""
        skill = _initialized_skill()

        skill.bus.on.assert_any_call(
            "intent_failure",
            skill._handle_intent_failure,
        )

    def test_register_intent_handlers_is_idempotent_without_force(self):
        """Repeated registration calls should not duplicate intent files."""
        skill = _initialized_skill()
        register_intent_file = Mock()
        skill.register_entity_file = Mock()
        skill.register_intent_file = register_intent_file
        skill._registered_intent_files.clear()
        skill._registered_entity_files.clear()

        first_count = skill._register_intent_handlers()
        second_count = skill._register_intent_handlers()

        assert first_count > 0
        assert second_count == 0
        assert register_intent_file.call_count == first_count

    def test_register_intent_handlers_force_replays_registration(self):
        """Force mode replays Core registrations without duplicating handlers."""
        skill = _initialized_skill()
        register_intent_file = Mock()
        skill.register_entity_file = Mock()
        skill.register_intent_file = register_intent_file
        skill._registered_intent_files.clear()
        skill._registered_entity_files.clear()

        first_count = skill._register_intent_handlers()
        second_count = skill._register_intent_handlers(force=True)

        assert first_count > 0
        assert second_count == first_count
        assert register_intent_file.call_count == first_count + second_count
        replay_calls = register_intent_file.call_args_list[first_count:]
        assert replay_calls
        assert all(call.args[1] is None for call in replay_calls)

    def test_disabled_intent_registration_guard_skips_handler(self):
        """Profile intent activation state must be enforced at voice dispatch."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill.settings_service.is_intent_active.return_value = False
        skill.speak = Mock()
        handler = Mock()

        guarded = skill._guard_intent_activation("trend.energy", handler)
        guarded(Mock())

        handler.assert_not_called()
        skill.speak.assert_called_once_with(
            "That capability is disabled for the active profile.",
        )

# ══════════════════════════════════════════════════════════
# Force Unconfigured Fallback
# ══════════════════════════════════════════════════════════


class TestForceUnconfiguredFallback:
    """Tests for _force_unconfigured_fallback()."""

    def test_force_unconfigured_fallback_sets_unconfigured_adapter(self):
        """_force_unconfigured_fallback() replaces dispatcher with UnconfiguredAdapter."""
        skill = _initialized_skill()
        skill._loaded_profile = "my-api"

        # Act
        skill._force_unconfigured_fallback()

        # Assert
        assert skill._loaded_profile == "unconfigured"
        assert isinstance(skill.dispatcher._adapter, UnconfiguredAdapter)
        skill.log.info.assert_any_call("Forced UnconfiguredAdapter fallback")


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
        """_safe_dispatch speaks error when dispatcher recovery fails."""
        skill = _initialized_skill()
        skill.dispatcher = None
        skill.speak = Mock()
        skill._reload_adapter = Mock(side_effect=RuntimeError("boom"))

        result = skill._safe_dispatch("test", lambda: 1)

        assert result is None
        skill.speak.assert_called_once_with(
            "AVAROS is still initializing. Please try again.",
        )

    def test_safe_dispatch_timeout_speaks_platform_timeout_message(self):
        """Future timeout should produce a clear user-facing timeout hint."""
        skill = _initialized_skill()
        skill.speak = Mock()

        result = skill._safe_dispatch(
            "test_timeout",
            lambda: (_ for _ in ()).throw(FutureTimeoutError()),
        )

        assert result is None
        _assert_structured_speak(
            skill,
            "The data platform did not respond in time. "
            "Please check the platform connection and try again.",
        )
        assert skill.speak.call_args.kwargs["meta"]["avaros_response"]["response_type"] == "timeout"

    def test_safe_dispatch_recovers_dispatcher_when_missing(self):
        """_safe_dispatch attempts adapter reload and proceeds when recovered."""
        skill = _initialized_skill()
        skill.dispatcher = None
        skill.speak = Mock()

        def _recover(profile_name: str) -> None:
            skill._loaded_profile = profile_name
            skill.dispatcher = QueryDispatcher(adapter=UnconfiguredAdapter())

        skill._reload_adapter = Mock(side_effect=_recover)

        result = skill._safe_dispatch("test", lambda: 123)

        assert result == 123
        assert skill._reload_adapter.call_count >= 1
        skill.speak.assert_not_called()

    def test_safe_dispatch_recovers_factory_before_dispatch(self):
        """_safe_dispatch rebuilds AdapterFactory when missing."""
        skill = _initialized_skill()
        skill.adapter_factory = None
        skill.settings_service = Mock()

        result = skill._safe_dispatch("test", lambda: 5)

        assert result == 5
        assert skill.adapter_factory is not None

    def test_safe_dispatch_recovers_response_builder_when_missing(self):
        """_safe_dispatch should re-create response_builder when absent."""
        skill = _initialized_skill()
        skill.response_builder = None

        result = skill._safe_dispatch("test", lambda: 7)

        assert result == 7
        assert skill.response_builder is not None


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
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type="custom_rest"
        skill.settings_service.get_profile.return_value = profile
        new_adapter = UnconfiguredAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        old_dispatcher = skill.dispatcher

        # Act
        skill._reload_adapter("demo")

        # Assert
        assert skill.dispatcher is not old_dispatcher
        assert skill._loaded_profile == "demo"

    def test_reload_adapter_reuses_dispatcher_async_runner(self):
        """Reload uses dispatcher async runner instead of creating new loop."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type="custom_rest"
        skill.settings_service.get_profile.return_value = profile

        new_adapter = UnconfiguredAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        def _run_async_stub(coro):
            coro.close()
            return new_adapter

        async_runner = Mock(side_effect=_run_async_stub)
        skill.dispatcher._run_async = async_runner

        with patch.object(skill, "_initialize_prevention_client"), patch(
            "skill.asyncio.new_event_loop",
        ) as new_loop:
            skill._reload_adapter("demo")

        async_runner.assert_called_once()
        new_loop.assert_not_called()

    def test_reload_adapter_creates_fallback_loop_when_missing(self):
        """If no loop exists, reload creates and reuses a fallback loop."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type="custom_rest"
        skill.settings_service.get_profile.return_value = profile
        skill.dispatcher = None
        new_adapter = UnconfiguredAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        fallback_loop = asyncio.new_event_loop()
        try:
            with patch(
                "skill.asyncio.get_event_loop",
                side_effect=RuntimeError("no loop"),
            ), patch("skill.asyncio.new_event_loop", return_value=fallback_loop):
                skill._reload_adapter("demo")
        finally:
            fallback_loop.close()

        skill.log.warning.assert_any_call(
            "No current asyncio event loop; creating a fallback loop for reload",
        )

    def test_reload_adapter_uses_create_prevention_client(self):
        """Reload preserves PREVENTION configuration via _create_prevention_client."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type = "custom_rest"
        skill.settings_service.get_profile.return_value = profile
        new_adapter = UnconfiguredAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        with patch.object(
            type(skill), "_create_prevention_client",
        ) as mock_create:
            mock_create.return_value = Mock()
            skill._reload_adapter("demo")

        mock_create.assert_called_once()


# ══════════════════════════════════════════════════════════
# Asset Resolution from ASR Variants
# ══════════════════════════════════════════════════════════


class TestAssetResolutionFromUtterance:
    """Tests for robust asset extraction from imperfect transcriptions."""

    def test_resolve_asset_from_spaced_oee_line_phrase(self):
        """Extracts Line-1 from utterance even when slot parsing misses."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {
            "utterance": "what is o e e for line one",
            "asset": "",
        }

        assert skill._resolve_asset_id(msg) == "Line-1"

    def test_resolve_asset_from_line_to_phrase(self):
        """Maps ASR 'line to' variant to Line-2."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {
            "utterance": "line to energy per unit",
            "asset": "",
        }

        assert skill._resolve_asset_id(msg) == "Line-2"

    def test_resolve_asset_from_dash_separated_line(self):
        """Dash-separated 'line-1' should resolve to Line-1."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {
            "utterance": "check anomalies for energy per unit on line-1",
            "asset": "",
        }

        assert skill._resolve_asset_id(msg) == "Line-1"

    def test_resolve_asset_from_pluralized_meter_phrase(self):
        """Pluralized meter phrasing should still resolve to the configured asset."""
        skill = _make_skill()
        skill._get_asset_registry = Mock(return_value=[
            Asset(
                asset_id="Gas-Main-Meter",
                display_name="Gas Main Meter",
                asset_type="machine",
                aliases=["gas main meter"],
            ),
        ])
        msg = Mock()
        msg.data = {
            "utterance": "what is the total energy for gas main meters today",
            "asset": "",
        }

        assert skill._resolve_asset_id(msg) == "Gas-Main-Meter"

    def test_resolve_compare_assets_from_utterance_fallback(self):
        """Extracts two line assets from utterance when compare slots missing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {
            "utterance": "compare energy between line 1 and line two",
            "asset_a": "",
            "asset_b": "",
        }

        assert skill._resolve_compare_assets(msg) == ("Line-1", "Line-2")

    def test_resolve_compare_assets_from_configured_multiword_names(self):
        """Extracts arbitrary adapter assets when intent slots split names."""
        skill = _make_skill()
        skill._get_asset_registry = Mock(return_value=[
            Asset(
                asset_id="device-a1",
                display_name="Test Device A1",
                asset_type="machine",
                aliases=["A1 test device"],
            ),
            Asset(
                asset_id="device-a2",
                display_name="Test Device A2",
                asset_type="machine",
            ),
        ])
        msg = Mock()
        msg.data = {
            "utterance": (
                "compare energy per unit between Test Device A1 "
                "and Test Device A2"
            ),
            "asset_a": "unit between Test Device A1",
            "asset_b": "Test Device A2",
        }

        assert skill._resolve_compare_assets(msg) == ("device-a1", "device-a2")

    def test_resolve_compare_assets_uses_explicit_utterance_order(self):
        """Registry extraction preserves the order spoken by the user."""
        skill = _make_skill()
        skill._get_asset_registry = Mock(return_value=[
            Asset(
                asset_id="asset-a",
                display_name="Machine Alpha",
                asset_type="machine",
            ),
            Asset(
                asset_id="asset-b",
                display_name="Machine Beta",
                asset_type="machine",
            ),
        ])
        msg = Mock()
        msg.data = {
            "utterance": "compare Machine Beta versus Machine Alpha",
            "asset_a": "",
            "asset_b": "",
        }

        assert skill._resolve_compare_assets(msg) == ("asset-b", "asset-a")

    def test_resolve_compare_assets_requires_explicit_configured_assets(self):
        """Missing comparison slots must not select configured assets silently."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_asset_mappings.return_value = {
            "Line-2": {},
            "Line-1": {},
            "Line-3": {},
        }
        msg = Mock()
        msg.data = {
            "utterance": "compare energy",
            "asset_a": "",
            "asset_b": "",
        }

        with pytest.raises(AVAROSError, match="Comparison assets were not explicit"):
            skill._resolve_compare_assets(msg)

    def test_resolve_compare_assets_rejects_noisy_slots(self):
        """Noisy compare slots should trigger clarification."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill._get_asset_registry = Mock(return_value=[])
        skill.settings_service.get_asset_mappings.return_value = {
            "Line-1": {},
            "Line-2": {},
        }
        msg = Mock()
        msg.data = {
            "utterance": "compare energy",
            "asset_a": "compare energy",
            "asset_b": "trend",
        }

        with pytest.raises(AVAROSError, match="Comparison assets were not explicit"):
            skill._resolve_compare_assets(msg)

    def test_resolve_asset_ignores_metric_phrase_in_slot(self):
        """Metric phrases like 'energy per unit been trending' are noise."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_asset_mappings.return_value = {
            "Line-1": {"metric_resources": {"energy_per_unit": "r1"}},
        }
        skill.settings_service.get_asset_list.return_value = []
        msg = Mock()
        msg.data = {
            "utterance": "how has energy per unit been trending",
            "asset": "energy per unit been trending",
        }

        assert skill._resolve_asset_id(msg) == "Line-1"

    def test_resolve_asset_id_clarifies_multiple_configured_assets(self):
        """No asset mention must not default to the first configured asset."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill._get_asset_registry = Mock(return_value=[])
        skill.settings_service.get_asset_mappings.return_value = {
            "Line-3": {},
            "Line-1": {},
            "Line-2": {},
        }
        msg = Mock()
        msg.data = {"utterance": "show energy trend today", "asset": ""}

        with pytest.raises(AVAROSError, match="Asset scope is ambiguous"):
            skill._resolve_asset_id(msg)

    def test_resolve_asset_id_does_not_choose_metric_ready_asset(self):
        """Metric readiness does not authorize an implicit asset choice."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill._get_asset_registry = Mock(return_value=[])
        skill.settings_service.get_asset_mappings.return_value = {
            "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4": {
                "display_name": "Seu",
                "asset_type": "machine",
            },
            "Line-2": {
                "metric_resources": {"energy_per_unit": "rid-2"},
            },
            "Line-1": {
                "metric_resources": {"energy_per_unit": "rid-1"},
            },
        }
        msg = Mock()
        msg.data = {"utterance": "show energy trend this week", "asset": ""}

        with pytest.raises(AVAROSError, match="Asset scope is ambiguous"):
            skill._resolve_asset_id(msg)

    def test_resolve_compare_assets_does_not_choose_metric_ready_assets(self):
        """Comparison scope must remain explicit despite metric readiness."""
        skill = _make_skill()
        skill.settings_service = Mock()
        skill._get_asset_registry = Mock(return_value=[])
        skill.settings_service.get_asset_mappings.return_value = {
            "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4": {
                "display_name": "Seu",
                "asset_type": "machine",
            },
            "Line-2": {
                "metric_resources": {"energy_per_unit": "rid-2"},
            },
            "Line-1": {
                "metric_resources": {"energy_per_unit": "rid-1"},
            },
        }
        msg = Mock()
        msg.data = {"utterance": "compare energy", "asset_a": "", "asset_b": ""}

        with pytest.raises(AVAROSError, match="Comparison assets were not explicit"):
            skill._resolve_compare_assets(msg)


class TestWhatIfAmountParsing:
    """Tests for robust amount parsing in what-if temperature intent."""

    def test_parse_amount_with_degree_symbol(self):
        """Parses '5°' as numeric 5.0."""
        skill = _make_skill()
        assert skill._parse_numeric_amount("5°") == 5.0

    def test_parse_amount_with_unit_text(self):
        """Parses '5 degrees' as numeric 5.0."""
        skill = _make_skill()
        assert skill._parse_numeric_amount("5 degrees") == 5.0

    def test_resolve_temperature_amount_from_word(self):
        """Resolves spoken number words like 'five'."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"amount": "five"}
        assert skill._resolve_temperature_amount(msg) == 5.0

    def test_resolve_temperature_amount_from_utterance_fallback(self):
        """Extracts amount from utterance when slot parser misses."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"amount": "", "utterance": "what if we reduce temperature by 7°"}
        assert skill._resolve_temperature_amount(msg) == 7.0


class TestNonMetricIntentBindings:
    """Tests for non-metric handler behavior with intent bindings."""

    def test_require_intent_binding_blocks_non_mock_when_missing(self):
        """Non-mock profile should require configured intent binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"
        skill.settings_service.get_intent_binding.return_value = None
        skill.speak = Mock()

        result = skill._require_intent_binding("status.system.show")

        assert result is False
        skill.speak.assert_called_once()

    def test_require_intent_binding_allows_non_mock_when_present(self):
        """Non-mock profile proceeds when a binding exists."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"
        skill.settings_service.get_intent_binding.return_value = {
            "endpoint": "/status/system",
            "method": "GET",
            "json_path": "$.status",
        }

        result = skill._require_intent_binding("status.system.show")

        assert result is True

    def test_require_intent_binding_allows_unconfigured_without_lookup(self):
        """Unconfigured profile should not require explicit binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "unconfigured"

        result = skill._require_intent_binding("status.system.show")

        assert result is True
        skill.settings_service.get_intent_binding.assert_not_called()

    def test_system_status_handler_is_built_in_without_binding(self):
        """System status intent should respond without requiring a binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"
        skill.settings_service.get_profile.return_value = Mock(platform_type="custom_rest")
        skill._require_intent_binding = Mock(return_value=False)
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "show system status"}
        skill.handle_status_system_show(msg)

        skill._require_intent_binding.assert_not_called()
        skill.speak.assert_called_once()

    def test_system_profile_handler_is_built_in_without_binding(self):
        """Profile status intent should respond without requiring a binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"
        skill.settings_service.get_profile.return_value = Mock(platform_type="custom_rest")
        skill._require_intent_binding = Mock(return_value=False)
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "show profile status"}
        skill.handle_status_profile_show(msg)

        skill._require_intent_binding.assert_not_called()
        skill.speak.assert_called_once()

    def test_help_capabilities_handler_is_built_in_without_binding(self):
        """Capabilities help intent should respond without requiring a binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "my-api"
        skill._require_intent_binding = Mock(return_value=False)
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "what can you do"}
        skill.handle_help_capabilities_list(msg)

        skill._require_intent_binding.assert_not_called()
        skill.speak.assert_called_once()

    def test_help_capabilities_reports_only_active_profile_features(self):
        """Capability help must not advertise profile-disabled features."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.is_intent_active.side_effect = (
            lambda name: name in {"status.system.show", "status.profile.show"}
        )
        skill.dispatcher.adapter.get_supported_metrics = Mock(
            return_value=[CanonicalMetric.ENERGY_TOTAL],
        )
        skill.speak = Mock()

        skill.handle_help_capabilities_list(Mock())

        response = skill.speak.call_args.args[0]
        assert "total energy" in response
        assert "system status" in response
        assert "active profile" in response
        assert "compare" not in response
        assert "anomal" not in response
        assert "trend" not in response


class TestMetricFallback:
    """Tests for metric fallback handler and utterance metric resolution."""

    def test_resolve_metric_from_utterance_energy_total(self):
        """Resolves energy total from common phrasing."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is the total energy")

        assert metric == CanonicalMetric.ENERGY_TOTAL

    def test_resolve_metric_from_utterance_energy_per_unit(self):
        """Resolves energy per unit from common phrasing."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is the energy per unit")

        assert metric == CanonicalMetric.ENERGY_PER_UNIT

    @pytest.mark.parametrize(
        ("utterance", "expected"),
        [
            ("how much power is OpenEMS Edge consuming", CanonicalMetric.CONSUMPTION_POWER),
            ("what is generated power", CanonicalMetric.PRODUCTION_POWER),
            ("what is produced energy", CanonicalMetric.ENERGY_PRODUCTION_TOTAL),
            ("what is grid power", CanonicalMetric.GRID_POWER),
            ("what is energy imported from grid", CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL),
            ("what is energy exported to grid", CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL),
            ("what is battery state of charge", CanonicalMetric.STORAGE_STATE_OF_CHARGE),
            ("what is battery power", CanonicalMetric.STORAGE_POWER),
        ],
    )
    def test_resolve_metric_from_utterance_generic_energy_metrics(self, utterance, expected):
        """Platform-neutral energy phrases resolve to the matching metric."""
        skill = _make_skill()

        assert skill._resolve_metric_from_utterance(utterance) == expected

    def test_resolve_metric_from_utterance_co2_total(self):
        """Resolves CO2 total from common phrasing."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is total carbon emissions")

        assert metric == CanonicalMetric.CO2_TOTAL

    def test_metric_query_fallback_clarifies_peak_demand_asset(self):
        """A KPI query without an asset must not silently default to Line-1."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.get_kpi.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_kpi_result.return_value = "peak demand response"
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "what is peak demand"}

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        skill.dispatcher.get_kpi.assert_not_called()
        assert "Which asset" in skill.speak.call_args.args[0]
        assert "avaros_response" in skill.speak.call_args.kwargs["meta"]

    def test_metric_query_fallback_routes_forecast_energy(self):
        """Fallback should not answer forecast phrases as current KPI values."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill._resolve_asset_id = Mock(return_value="Line-1")
        skill.dispatcher = Mock()
        skill.dispatcher.forecast_metric.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_forecast_result.return_value = (
            "forecast response"
        )
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "forecast energy for Line 1"}

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        skill.dispatcher.forecast_metric.assert_called_once_with(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            horizon_periods=7,
        )
        skill.dispatcher.get_kpi.assert_not_called()
        _assert_structured_speak(skill, "forecast response")

    def test_metric_query_fallback_routes_whatif_scrap(self):
        """Fallback should route what-if phrases to scenario simulation."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill._resolve_asset_id = Mock(return_value="Line-1")
        skill.dispatcher = Mock()
        skill.dispatcher.simulate_whatif.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_whatif_result.return_value = (
            "what-if response"
        )
        skill.speak = Mock()

        msg = Mock()
        msg.data = {
            "utterance": "what if scrap rate improves by 5 percent",
        }

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        scenario = skill.dispatcher.simulate_whatif.call_args.args[0]
        assert scenario.target_metric == CanonicalMetric.SCRAP_RATE
        assert scenario.asset_id == "Line-1"
        assert scenario.parameters[0].proposed_value == -5.0
        _assert_structured_speak(skill, "what-if response")

    def test_metric_query_fallback_whatif_ignores_line_number_as_amount(self):
        """What-if parser should use the percent value, not Line 1."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill._resolve_asset_id = Mock(return_value="Line-1")
        skill.dispatcher = Mock()
        skill.dispatcher.simulate_whatif.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_whatif_result.return_value = "ok"
        skill.speak = Mock()

        msg = Mock()
        msg.data = {
            "utterance": "what if scrap rate on Line 1 improves by 5 percent",
        }

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        scenario = skill.dispatcher.simulate_whatif.call_args.args[0]
        assert scenario.parameters[0].proposed_value == -5.0

    def test_metric_query_fallback_routes_whatif_absolute_target(self):
        """Absolute target phrasing should not be treated as percent change."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill._resolve_asset_id = Mock(return_value="Line-2")
        skill.dispatcher = Mock()
        skill.dispatcher.simulate_whatif.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_whatif_result.return_value = "ok"
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "what if OEE reaches 90 percent for Line 2"}

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        scenario = skill.dispatcher.simulate_whatif.call_args.args[0]
        assert scenario.target_metric == CanonicalMetric.OEE
        assert scenario.asset_id == "Line-2"
        assert scenario.parameters[0].name == "target_value"
        assert scenario.parameters[0].proposed_value == 90.0

    def test_metric_query_fallback_ignores_non_metric_utterance(self):
        """Fallback returns False for unrelated utterances."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "tell me a joke"}

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is False
        skill.dispatcher.get_kpi.assert_not_called()
        skill.speak.assert_not_called()

    def test_metric_query_fallback_energy_total_uses_aggregate_when_period_not_spoken(self):
        """Fallback should ignore implicit today slot when utterance has no period phrase."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.get_kpi.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_kpi_result.return_value = "energy total response"
        skill.speak = Mock()
        skill._resolve_asset_id = Mock(return_value="620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4")
        skill._get_asset_registry = Mock(return_value=[
            Asset("620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4", "Seu", "seu")
        ])
        skill.settings_service = Mock()
        skill.settings_service.get_asset_mappings.return_value = {
            "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4": {
                "display_name": "Seu",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "asset_consumption_total",
                        "default_period_mode": "aggregate_total",
                        "aggregate_start_iso": "2021-02-01T00:00:00.000Z",
                    },
                },
            },
        }

        msg = Mock()
        msg.data = {
            "utterance": "what is total energy for seu",
            "utterances": ["what is total energy for seu"],
            "period": "today",
        }

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        dispatched_period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
        assert dispatched_period.display_name == "in total"
        _assert_structured_speak(skill, "energy total response")

    def test_metric_query_fallback_energy_total_today_rejects_cumulative_meter(self):
        """Fallback should reject spoken today for cumulative-only meter totals."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.adapter = Mock()
        skill.dispatcher.adapter.platform_name = "generic_rest"
        skill.dispatcher.get_kpi.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_kpi_result.return_value = "energy total response"
        skill.speak = Mock()
        skill._resolve_asset_id = Mock(return_value="620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4")
        skill._get_asset_registry = Mock(return_value=[
            Asset("620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4", "Seu", "seu")
        ])
        skill.settings_service = Mock()
        skill.settings_service.get_profile.return_value = None
        skill.settings_service.get_asset_mappings.return_value = {
            "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4": {
                "display_name": "Seu",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "asset_consumption_total",
                        "default_period_mode": "aggregate_total",
                        "aggregate_start_iso": "2021-02-01T00:00:00.000Z",
                    },
                },
            },
        }

        msg = Mock()
        msg.data = {"utterance": "what is total energy for seu today", "period": "today"}

        handled = skill.handle_metric_query_fallback(msg)

        # A narrated failure owns the turn; falling through would retry it.
        assert handled is True
        skill.dispatcher.get_kpi.assert_not_called()
        _assert_structured_speak(
            skill,
            "Time-based total energy is not available for Seu. "
            "This meter only exposes a cumulative total. Ask for total energy without a period."
        )

    def test_metric_query_fallback_energy_total_last_2_weeks_uses_requested_window(self):
        """Fallback should preserve supported last-2-weeks phrasing."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.get_kpi.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_kpi_result.return_value = "energy total response"
        skill.speak = Mock()
        skill._resolve_asset_id = Mock(return_value="Line-1")
        skill._get_asset_registry = Mock(return_value=[Asset("Line-1", "Line 1", "line")])
        skill.settings_service = Mock()
        skill.settings_service.get_asset_mappings.return_value = {}

        msg = Mock()
        msg.data = {
            "utterance": "what is total energy for line one last 2 weeks",
            "period": "last 2 weeks",
        }

        handled = skill.handle_metric_query_fallback(msg)

        assert handled is True
        dispatched_period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
        assert dispatched_period.display_name == "last 2 weeks"
        _assert_structured_speak(skill, "energy total response")

    def test_metric_query_fallback_energy_total_last_week_rejects_cumulative_meter(self):
        """Fallback should speak a clear rejection for cumulative-only meter periods."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.adapter = Mock()
        skill.dispatcher.adapter.platform_name = "generic_rest"
        skill.response_builder = Mock()
        skill.speak = Mock()
        skill._resolve_asset_id = Mock(return_value="Electric-Main-Meter")
        skill._get_asset_registry = Mock(return_value=[
            Asset("Electric-Main-Meter", "Electric Main Meter", "machine")
        ])
        skill.settings_service = Mock()
        skill.settings_service.get_profile.return_value = None
        skill.settings_service.get_asset_mappings.return_value = {
            "Electric-Main-Meter": {
                "display_name": "Electric Main Meter",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "asset_consumption_total",
                        "default_period_mode": "aggregate_total",
                        "aggregate_start_iso": "2021-02-01T00:00:00.000Z",
                    },
                },
            },
        }

        msg = Mock()
        msg.data = {
            "utterance": "what is total energy for electric main meter last week",
            "period": "last week",
        }

        handled = skill.handle_metric_query_fallback(msg)

        # A narrated failure owns the turn; falling through would retry it.
        assert handled is True
        skill.dispatcher.get_kpi.assert_not_called()
        _assert_structured_speak(
            skill,
            "Time-based total energy is not available for Electric Main Meter. "
            "This meter only exposes a cumulative total. Ask for total energy without a period."
        )

    def test_metric_query_fallback_energy_total_this_month_rejects_metric_resource_only_meter(self):
        """Fallback should reject periods when mapping ignores time filters."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.adapter = Mock()
        skill.dispatcher.adapter.platform_name = "generic_rest"
        skill.response_builder = Mock()
        skill.speak = Mock()
        skill._resolve_asset_id = Mock(return_value="Electric-Main-Meter")
        skill._get_asset_registry = Mock(return_value=[
            Asset("Electric-Main-Meter", "Electric Main Meter", "machine")
        ])
        skill.settings_service = Mock()
        skill.settings_service.get_profile.return_value = None
        skill.settings_service.get_asset_mappings.return_value = {
            "Electric-Main-Meter": {
                "display_name": "Electric Main Meter",
                "capability_mode": "full_kpi",
                "metric_resources": {
                    "energy_total": "resource-1",
                },
            },
        }
        skill.settings_service.get_metric_mapping.return_value = {
            "endpoint": "/api/u/measurement/metric/item/{resource_id}",
            "json_path": "$.lastValue",
            "unit": "kWh",
        }

        msg = Mock()
        msg.data = {
            "utterance": "what is total energy for electric main meter this month",
            "period": "this month",
        }

        handled = skill.handle_metric_query_fallback(msg)

        # A narrated failure owns the turn; falling through would retry it.
        assert handled is True
        skill.dispatcher.get_kpi.assert_not_called()
        _assert_structured_speak(
            skill,
            "Time-based total energy is not available for Electric Main Meter. "
            "This meter only exposes a cumulative total. Ask for total energy without a period."
        )

    def test_metric_query_fallback_pluralized_gas_meter_rejects_period(self):
        """Pluralized meter phrasing should reject on the intended gas meter asset."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.adapter = Mock()
        skill.dispatcher.adapter.platform_name = "generic_rest"
        skill.response_builder = Mock()
        skill.speak = Mock()
        skill._get_asset_registry = Mock(return_value=[
            Asset(
                asset_id="Gas-Main-Meter",
                display_name="Gas Main Meter",
                asset_type="machine",
                aliases=["gas main meter"],
            ),
        ])
        skill.settings_service = Mock()
        skill.settings_service.get_profile.return_value = None
        skill.settings_service.get_asset_mappings.return_value = {
            "Gas-Main-Meter": {
                "display_name": "Gas Main Meter",
                "capability_mode": "full_kpi",
                "metric_resources": {
                    "energy_total": "resource-gas-1",
                },
                "aliases": ["gas main meter"],
            },
            "Line-1": {
                "display_name": "Line 1",
                "metric_resources": {
                    "energy_total": "resource-line-1",
                    "energy_per_unit": "resource-line-2",
                },
            },
        }
        skill.settings_service.get_metric_mapping.return_value = {
            "endpoint": "/api/u/measurement/metric/item/{resource_id}",
            "json_path": "$.lastValue",
            "unit": "kWh",
        }

        msg = Mock()
        msg.data = {
            "utterance": "what is the total energy for gas main meters today",
            "period": "today",
        }

        handled = skill.handle_metric_query_fallback(msg)

        # A narrated failure owns the turn; falling through would retry it.
        assert handled is True
        skill.dispatcher.get_kpi.assert_not_called()
        _assert_structured_speak(
            skill,
            "Time-based total energy is not available for Gas Main Meter. "
            "This meter only exposes a cumulative total. Ask for total energy without a period."
        )


class TestIntentFailureRecovery:
    """Tests for intent_failure bus recovery path."""

    def test_intent_failure_clarifies_co2_total_asset(self):
        """Intent recovery must not silently assign an asset to CO2 total."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.get_kpi.return_value = Mock()
        skill.response_builder = Mock()
        skill.response_builder.format_kpi_result.return_value = "co2 total response"
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "what is co2 total"}

        skill._handle_intent_failure(msg)

        skill.dispatcher.get_kpi.assert_not_called()
        assert "Which asset" in skill.speak.call_args.args[0]

    def test_intent_failure_ignores_unrelated_utterance(self):
        """Unrelated utterance in intent_failure should be ignored."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "tell me a joke"}

        skill._handle_intent_failure(msg)

        skill.dispatcher.get_kpi.assert_not_called()
        skill.speak.assert_not_called()

    def test_intent_failure_speaks_honest_anomaly_message(self):
        """Intent failure should speak the pending-feature anomaly message."""
        skill = _initialized_skill()
        skill._check_profile_mismatch = Mock()
        skill.dispatcher = Mock()
        skill.dispatcher.scan_anomalies.side_effect = AVAROSError(
            message="Anomaly detection is not yet available.",
            code="ANOMALY_NOT_AVAILABLE",
            user_message=(
                "Anomaly detection is not yet available. This feature requires "
                "the PREVENTION service which is pending."
            ),
        )
        skill.response_builder = Mock()
        skill.speak = Mock()

        msg = Mock()
        msg.data = {"utterance": "are there any unusual patterns in production"}

        skill._handle_intent_failure(msg)

        skill.dispatcher.scan_anomalies.assert_called_once()
        skill.response_builder.format_anomaly_scan_result.assert_not_called()
        _assert_structured_speak(
            skill,
            "Anomaly detection is not yet available. This feature requires "
            "the PREVENTION service which is pending."
        )


class TestFallbackEligibility:
    """Tests for FallbackSkill can_answer implementation."""

    @pytest.mark.parametrize(
        "utterance",
        [
            "Help me understand this selected issue.",
            "Bu bulgunun kanıtlarını açıkla.",
            "Tell me something useful.",
            "Book a flight tomorrow.",
        ],
    )
    def test_signed_embedded_widget_claims_unknown_utterances_for_resolution(
        self, utterance
    ):
        """Unknown widget turns reach semantic resolution, then clarification."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": [utterance]}
        msg.context = {
            # HiveMind rewrites fallback pings to a connection-specific source
            # while retaining proxy-injected signed-session markers.
            "source": "avaros-client::1::avaros-client::session-1",
            "platform": "AVAROS-Widget-v1",
            "reneryo_widget_session_validated": True,
            "reneryo_context": {"organization_id": "futuregen"},
        }

        assert skill.can_answer(msg) is True

    def test_signed_hivemind_widget_ping_is_claimed_without_utterance_data(self):
        """The later fallback request supplies the utterance after this ping."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {}
        msg.context = {
            "source": "avaros-client::1::avaros-client::session-1",
            "platform": "AVAROS-Widget-v1",
            "reneryo_widget_session_validated": True,
            "reneryo_context": {"organization_id": "futuregen"},
        }

        assert skill.can_answer(msg) is True

    def test_unvalidated_embedded_widget_does_not_claim_unknown_utterance(self):
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["Help me understand this selected issue."]}
        msg.context = {
            "source": "avaros-widget",
            "platform": "AVAROS-Widget-v1",
            "reneryo_context": {"organization_id": "forged"},
        }

        assert skill.can_answer(msg) is False

    def test_can_answer_true_for_total_energy_utterance(self):
        """Fallback ping should report True for total energy phrasing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["what is the total energy"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_true_for_energy_per_unit_utterance(self):
        """Fallback ping should report True for energy per unit phrasing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["what is the energy per unit"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_true_for_co2_total_utterance(self):
        """Fallback ping should report True for known metric phrasing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["what is co2 total"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_false_for_unrelated_utterance(self):
        """Fallback ping should report False for unrelated phrases."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["tell me a joke"]}

        assert skill.can_answer(msg) is False

    def test_can_answer_false_when_ping_lacks_utterances(self):
        """Fallback ping without utterances should decline (empty = noise)."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {}

        assert skill.can_answer(msg) is False

    def test_can_answer_true_for_check_anomalies_utterance(self):
        """Fallback ping should report True for anomaly phrases."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["check anomalies"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_true_for_forecast_utterance(self):
        """Fallback ping should claim forecast phrases for AVAROS routing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["forecast energy for Line 1"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_true_for_whatif_utterance(self):
        """Fallback ping should claim what-if phrases for AVAROS routing."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["what if energy per unit drops by 8 percent"]}

        assert skill.can_answer(msg) is True

    def test_can_answer_false_for_whitespace_only_utterance(self):
        """Whitespace-only utterance should not claim eligibility."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["   "]}

        assert skill.can_answer(msg) is False

    def test_can_answer_false_for_empty_string_utterance(self):
        """Empty string utterance should not claim eligibility."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": [""]}

        assert skill.can_answer(msg) is False


class TestConverseDecline:
    """Tests that converse() always returns False to preserve wake-word gating."""

    def test_converse_returns_false(self):
        """converse() must return False so OVOS does not bypass wake-word."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["show me energy per unit"]}

        assert skill.converse(msg) is False

    def test_converse_returns_false_with_no_message(self):
        """converse() with no argument still returns False."""
        skill = _make_skill()

        assert skill.converse() is False


class TestMetricResolutionRobustness:
    """Tests for noisy ASR phrase handling."""

    def test_resolve_metric_from_noisy_co2_total_phrase(self):
        """ASR typo like 'co2 toto' still resolves to CO2 total."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is co2 toto")

        assert metric == CanonicalMetric.CO2_TOTAL

    def test_resolve_metric_from_change_over_time_phrase(self):
        """ASR spaced variant should resolve to changeover time metric."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is change over time")

        assert metric == CanonicalMetric.CHANGEOVER_TIME
