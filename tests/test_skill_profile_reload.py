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
from skill.domain.exceptions import AVAROSError
from skill.domain.models import CanonicalMetric
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
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "demo"
        profile = Mock()
        profile.platform_type = "mock"
        skill.settings_service.get_profile.return_value = profile

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

    def test_handle_profile_switch_recovers_missing_factory(self):
        """When adapter_factory is missing, runtime recovery recreates it."""
        skill = _initialized_skill()
        skill.adapter_factory = None
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "reneryo"

        skill._handle_profile_switch(_make_message("reneryo"))

        assert skill.adapter_factory is not None


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
        skill._loaded_platform = "mock"

        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "mock"
        profile = Mock()
        profile.platform_type = "mock"
        skill.settings_service.get_profile.return_value = profile

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

    def test_safe_dispatch_recovers_dispatcher_when_missing(self):
        """_safe_dispatch attempts adapter reload and proceeds when recovered."""
        skill = _initialized_skill()
        skill.dispatcher = None
        skill.speak = Mock()

        def _recover(profile_name: str) -> None:
            skill._loaded_profile = profile_name
            skill.dispatcher = QueryDispatcher(adapter=MockAdapter())

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
        profile.platform_type = "mock"
        skill.settings_service.get_profile.return_value = profile
        new_adapter = MockAdapter()
        skill.adapter_factory.reload = AsyncMock(return_value=new_adapter)

        old_dispatcher = skill.dispatcher

        # Act
        skill._reload_adapter("demo")

        # Assert
        assert skill.dispatcher is not old_dispatcher
        assert skill._loaded_profile == "demo"


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
        skill.settings_service.get_active_profile_name.return_value = "reneryo"
        skill.settings_service.get_intent_binding.return_value = None
        skill.speak = Mock()

        result = skill._require_intent_binding("status.system.show")

        assert result is False
        skill.speak.assert_called_once()

    def test_require_intent_binding_allows_non_mock_when_present(self):
        """Non-mock profile proceeds when a binding exists."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "reneryo"
        skill.settings_service.get_intent_binding.return_value = {
            "endpoint": "/status/system",
            "method": "GET",
            "json_path": "$.status",
        }

        result = skill._require_intent_binding("status.system.show")

        assert result is True

    def test_require_intent_binding_allows_mock_without_lookup(self):
        """Mock profile should not require explicit binding."""
        skill = _initialized_skill()
        skill.settings_service = Mock()
        skill.settings_service.get_active_profile_name.return_value = "mock"

        result = skill._require_intent_binding("status.system.show")

        assert result is True
        skill.settings_service.get_intent_binding.assert_not_called()


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

    def test_resolve_metric_from_utterance_co2_total(self):
        """Resolves CO2 total from common phrasing."""
        skill = _make_skill()

        metric = skill._resolve_metric_from_utterance("what is total carbon emissions")

        assert metric == CanonicalMetric.CO2_TOTAL

    def test_metric_query_fallback_handles_peak_demand(self):
        """Fallback should answer KPI query when intent matching misses."""
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
        skill.dispatcher.get_kpi.assert_called_once()
        skill.speak.assert_called_once_with("peak demand response")

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


class TestIntentFailureRecovery:
    """Tests for intent_failure bus recovery path."""

    def test_intent_failure_recovers_co2_total(self):
        """When intent parser fails, CO2 total utterance should still be handled."""
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

        skill.dispatcher.get_kpi.assert_called_once()
        skill.speak.assert_called_once_with("co2 total response")

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
        skill.dispatcher.check_anomaly.side_effect = AVAROSError(
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

        skill.dispatcher.check_anomaly.assert_called_once()
        skill.response_builder.format_anomaly_result.assert_not_called()
        skill.speak.assert_called_once_with(
            "Anomaly detection is not yet available. This feature requires "
            "the PREVENTION service which is pending."
        )


class TestFallbackEligibility:
    """Tests for FallbackSkill can_answer implementation."""

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

    def test_can_answer_true_when_ping_lacks_utterances(self):
        """Fallback ping without utterances should remain eligible."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {}

        assert skill.can_answer(msg) is True

    def test_can_answer_true_for_check_anomalies_utterance(self):
        """Fallback ping should report True for anomaly phrases."""
        skill = _make_skill()
        msg = Mock()
        msg.data = {"utterances": ["check anomalies"]}

        assert skill.can_answer(msg) is True


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
