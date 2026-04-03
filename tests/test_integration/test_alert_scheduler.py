"""
Integration Tests for Proactive Alert Scheduler

Tests that the AVAROSSkill correctly starts/stops the background
alert scheduler on initialization, profile switches, and stop().
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from ovos_bus_client import MessageBusClient

from skill import AVAROSSkill
from skill.domain.alert_models import AlertConfig, AlertEvent, MonitoredPair
from skill.domain.models import CanonicalMetric


def _make_skill() -> AVAROSSkill:
    """Create an AVAROSSkill with mocked OVOS framework parts."""
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.bus = MagicMock(spec=MessageBusClient)
    return skill


# ── Scheduler Lifecycle ──────────────────────────────


class TestAlertSchedulerStart:
    def test_initialize_starts_scheduler(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVAROS_DATABASE_URL", None)
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

        # UnconfiguredAdapter → scheduler NOT started
        assert skill._alert_scheduler_active is False
        skill.schedule_repeating_event.assert_not_called()

    def test_scheduler_starts_with_configured_adapter(self) -> None:
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

            # Unconfigured by default → not started
            assert skill._alert_scheduler_active is False

    def test_scheduler_respects_disabled_config(self) -> None:
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

            # Manually configure adapter as non-unconfigured
            mock_adapter = MagicMock()
            mock_adapter.platform_name = "generic_rest"
            skill.dispatcher._adapter = mock_adapter

            # Save disabled config
            skill.settings_service.save_alert_config(
                AlertConfig(enabled=False),
            )

            # Reset and re-start scheduler
            skill._alert_scheduler_active = False
            skill._start_alert_scheduler()
            assert skill._alert_scheduler_active is False


class TestAlertSchedulerStop:
    def test_stop_cancels_scheduler(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVAROS_DATABASE_URL", None)
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

            # Manually mark as active
            skill._alert_scheduler_active = True
            skill.stop()
            skill.cancel_scheduled_event.assert_called_once_with(
                "avaros_prevention_alert",
            )
            assert skill._alert_scheduler_active is False

    def test_stop_safe_when_not_active(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVAROS_DATABASE_URL", None)
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()
            skill.stop()
            skill.cancel_scheduled_event.assert_not_called()


# ── Background Check Handler ─────────────────────────


class TestRunBackgroundCheck:
    def test_disabled_config_short_circuits(self) -> None:
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.speak = Mock()
            skill.initialize()

            skill.settings_service.save_alert_config(
                AlertConfig(enabled=False),
            )

            msg = MagicMock()
            skill._run_background_check(msg)
            skill.speak.assert_not_called()

    def test_speaks_unsuppressed_events(self) -> None:
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.speak = Mock()
            skill.initialize()

            # Inject mock alert monitor that returns an event
            from datetime import datetime, timezone
            event = AlertEvent(
                alert_type="anomaly",
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Boiler-1",
                severity="high",
                message="Test alert message",
                detected_at=datetime.now(timezone.utc),
                suppressed=False,
            )
            skill._alert_monitor.run_check = Mock(return_value=[event])

            # Set up config and pairs
            skill.settings_service.save_alert_config(AlertConfig(
                enabled=True,
                monitored_pairs=(
                    MonitoredPair(
                        metric=CanonicalMetric.ENERGY_PER_UNIT,
                        asset_id="Boiler-1",
                    ),
                ),
            ))

            msg = MagicMock()
            skill._run_background_check(msg)
            skill.speak.assert_called_once_with("Test alert message")

    def test_suppressed_events_not_spoken(self) -> None:
        with patch.dict(os.environ, {"AVAROS_DATABASE_URL": "sqlite:///:memory:"}):
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.speak = Mock()
            skill.initialize()

            from datetime import datetime, timezone
            event = AlertEvent(
                alert_type="anomaly",
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Boiler-1",
                severity="low",
                message="Suppressed alert",
                detected_at=datetime.now(timezone.utc),
                suppressed=True,
            )
            skill._alert_monitor.run_check = Mock(return_value=[event])

            skill.settings_service.save_alert_config(AlertConfig(
                enabled=True,
                monitored_pairs=(
                    MonitoredPair(
                        metric=CanonicalMetric.ENERGY_PER_UNIT,
                        asset_id="Boiler-1",
                    ),
                ),
            ))

            msg = MagicMock()
            skill._run_background_check(msg)
            skill.speak.assert_not_called()


# ── Monitored Pairs Resolution ───────────────────────


class TestResolveMonitoredPairs:
    def test_uses_config_pairs_when_provided(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVAROS_DATABASE_URL", None)
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

            pair = MonitoredPair(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="Boiler-1",
            )
            config = AlertConfig(monitored_pairs=(pair,))
            result = skill._resolve_monitored_pairs(config)
            assert len(result) == 1
            assert result[0] == pair

    def test_empty_pairs_discovers_from_adapter(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVAROS_DATABASE_URL", None)
            skill = _make_skill()
            skill.schedule_repeating_event = Mock()
            skill.cancel_scheduled_event = Mock()
            skill.initialize()

            # Mock adapter with metrics and assets
            mock_adapter = MagicMock()
            mock_adapter.get_supported_metrics.return_value = [
                CanonicalMetric.ENERGY_PER_UNIT,
            ]
            mock_asset = MagicMock()
            mock_asset.asset_id = "A-1"
            mock_adapter.list_assets = MagicMock(return_value=mock_asset)
            skill.dispatcher._adapter = mock_adapter
            skill.dispatcher._run_async = Mock(return_value=[mock_asset])

            config = AlertConfig(monitored_pairs=())
            result = skill._resolve_monitored_pairs(config)
            assert len(result) >= 1
