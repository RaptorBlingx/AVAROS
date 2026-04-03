"""
AlertMonitor Test Suite

Tests background check orchestration, cooldown suppression,
severity filtering, and message building.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from skill.domain.alert_models import (
    AlertConfig,
    AlertEvent,
    MonitoredPair,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport
from skill.domain.models import Anomaly, CanonicalMetric
from skill.domain.results import AnomalyResult
from skill.services.alert_monitor import (
    AlertMonitor,
    _cooldown_elapsed,
    _severity_meets_threshold,
)


# ── Fixtures ─────────────────────────────────────────


@pytest.fixture
def monitor() -> AlertMonitor:
    return AlertMonitor()


@pytest.fixture
def default_config() -> AlertConfig:
    return AlertConfig()


@pytest.fixture
def pair_energy_boiler() -> MonitoredPair:
    return MonitoredPair(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="Boiler-1",
    )


@pytest.fixture
def pair_co2_hvac() -> MonitoredPair:
    return MonitoredPair(
        metric=CanonicalMetric.CO2_PER_UNIT,
        asset_id="HVAC-Main",
    )


def _make_anomaly_result(
    *,
    is_anomalous: bool = True,
    severity: str = "high",
) -> AnomalyResult:
    anomalies = []
    if is_anomalous:
        anomalies.append(Anomaly(
            timestamp=datetime(2026, 4, 1, tzinfo=timezone.utc),
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            expected_value=0.0,
            actual_value=0.0,
            deviation=3.2,
            description="Spike of 3.2σ detected.",
        ))
    return AnomalyResult(
        is_anomalous=is_anomalous,
        anomalies=anomalies,
        severity=severity,
        asset_id="Boiler-1",
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        recommendation_id="q-1",
    )


def _make_drift_report(
    *,
    has_drift: bool = True,
    direction: str = "degrading",
) -> DriftReport:
    return DriftReport(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        has_drift=has_drift,
        drift_direction=direction,
        drift_rate=0.005,
        periods_analyzed=14,
        description="Significant upward trend.",
    )


def _mock_dispatcher(
    *,
    anomaly_result: AnomalyResult | None = None,
    drift_report: DriftReport | None = None,
) -> MagicMock:
    d = MagicMock()
    if anomaly_result is not None:
        d.check_anomaly.return_value = anomaly_result
    else:
        d.check_anomaly.return_value = _make_anomaly_result(
            is_anomalous=False, severity="none",
        )
    if drift_report is not None:
        d.check_drift.return_value = drift_report
    else:
        d.check_drift.return_value = _make_drift_report(has_drift=False)
    return d


# ── Helper Tests ─────────────────────────────────────


class TestSeverityMeetsThreshold:
    def test_high_meets_medium(self) -> None:
        assert _severity_meets_threshold("high", "medium") is True

    def test_low_does_not_meet_medium(self) -> None:
        assert _severity_meets_threshold("low", "medium") is False

    def test_medium_meets_medium(self) -> None:
        assert _severity_meets_threshold("medium", "medium") is True

    def test_none_does_not_meet_low(self) -> None:
        assert _severity_meets_threshold("none", "low") is False

    def test_critical_meets_critical(self) -> None:
        assert _severity_meets_threshold("critical", "critical") is True


class TestCooldownElapsed:
    def test_no_previous_alert_returns_true(self) -> None:
        now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
        assert _cooldown_elapsed(None, 60, now) is True

    def test_within_cooldown_returns_false(self) -> None:
        now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
        last = now - timedelta(minutes=30)
        assert _cooldown_elapsed(last, 60, now) is False

    def test_after_cooldown_returns_true(self) -> None:
        now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
        last = now - timedelta(minutes=61)
        assert _cooldown_elapsed(last, 60, now) is True


# ── run_check Tests ──────────────────────────────────


class TestRunCheck:
    def test_no_anomaly_no_drift_returns_empty(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher()
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        assert events == []

    def test_anomaly_detected_returns_event(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="high"),
        )
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        anomaly_events = [e for e in events if e.alert_type == "anomaly"]
        assert len(anomaly_events) == 1
        assert anomaly_events[0].severity == "high"
        assert not anomaly_events[0].suppressed

    def test_drift_detected_returns_event(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher(
            drift_report=_make_drift_report(direction="degrading"),
        )
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        drift_events = [e for e in events if e.alert_type == "drift"]
        assert len(drift_events) == 1
        assert drift_events[0].severity == "medium"

    def test_both_detected_returns_two_events(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="high"),
            drift_report=_make_drift_report(direction="degrading"),
        )
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        assert len(events) == 2

    def test_multiple_pairs_checked(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
        pair_co2_hvac: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="high"),
        )
        events = monitor.run_check(
            dispatcher, default_config,
            [pair_energy_boiler, pair_co2_hvac],
        )
        assert len(events) >= 2


# ── Suppression Tests ────────────────────────────────


class TestSuppression:
    def test_below_threshold_suppressed(
        self, monitor: AlertMonitor, pair_energy_boiler: MonitoredPair,
    ) -> None:
        config = AlertConfig(severity_threshold="high")
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="low"),
        )
        events = monitor.run_check(
            dispatcher, config, [pair_energy_boiler],
        )
        anomaly_events = [e for e in events if e.alert_type == "anomaly"]
        assert len(anomaly_events) == 1
        assert anomaly_events[0].suppressed is True

    def test_cooldown_suppresses_repeat(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="high"),
        )
        # First check — should not suppress
        events1 = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        anomaly1 = [e for e in events1 if e.alert_type == "anomaly"]
        assert anomaly1[0].suppressed is False

        # Second check within cooldown — should suppress
        events2 = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        anomaly2 = [e for e in events2 if e.alert_type == "anomaly"]
        assert anomaly2[0].suppressed is True


# ── Error Handling Tests ─────────────────────────────


class TestErrorHandling:
    def test_anomaly_check_exception_skipped(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = MagicMock()
        dispatcher.check_anomaly.side_effect = RuntimeError("API down")
        dispatcher.check_drift.return_value = _make_drift_report(
            has_drift=False,
        )
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        assert events == []

    def test_drift_check_exception_skipped(
        self, monitor: AlertMonitor, default_config: AlertConfig,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        dispatcher = MagicMock()
        dispatcher.check_anomaly.return_value = _make_anomaly_result(
            is_anomalous=False,
        )
        dispatcher.check_drift.side_effect = RuntimeError("Timeout")
        events = monitor.run_check(
            dispatcher, default_config, [pair_energy_boiler],
        )
        assert events == []


# ── Message Building Tests ───────────────────────────


class TestMessageBuilding:
    def test_anomaly_message_includes_asset(
        self, monitor: AlertMonitor,
    ) -> None:
        result = _make_anomaly_result(severity="high")
        msg = monitor._anomaly_message(
            CanonicalMetric.ENERGY_PER_UNIT, "Boiler-1", result,
        )
        assert "Boiler-1" in msg
        assert "energy per unit" in msg.lower()

    def test_drift_message_includes_direction(
        self, monitor: AlertMonitor,
    ) -> None:
        report = _make_drift_report(direction="degrading")
        msg = monitor._drift_message(
            CanonicalMetric.ENERGY_PER_UNIT, "Boiler-1", report,
        )
        assert "degrading" in msg
        assert "Boiler-1" in msg


# ── Threshold Pass-Through Tests ─────────────────────


class TestThresholdPassThrough:
    """Verify AlertMonitor passes config.z_score_threshold to dispatcher."""

    def test_anomaly_passes_config_threshold(
        self, monitor: AlertMonitor,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        config = AlertConfig(z_score_threshold=3.5)
        dispatcher = _mock_dispatcher(
            anomaly_result=_make_anomaly_result(severity="high"),
        )
        monitor.run_check(dispatcher, config, [pair_energy_boiler])

        dispatcher.check_anomaly.assert_called_once_with(
            metric=pair_energy_boiler.metric,
            asset_id=pair_energy_boiler.asset_id,
            threshold=3.5,
        )

    def test_anomaly_passes_default_threshold(
        self, monitor: AlertMonitor,
        pair_energy_boiler: MonitoredPair,
    ) -> None:
        config = AlertConfig()  # default z_score_threshold=2.0
        dispatcher = _mock_dispatcher()
        monitor.run_check(dispatcher, config, [pair_energy_boiler])

        dispatcher.check_anomaly.assert_called_once_with(
            metric=pair_energy_boiler.metric,
            asset_id=pair_energy_boiler.asset_id,
            threshold=2.0,
        )
