"""
SettingsService Alert Config Persistence Tests

Tests get_alert_config / save_alert_config round-trip, defaults,
and partial data handling.
"""

from __future__ import annotations

import pytest

from skill.domain.alert_models import AlertConfig, MonitoredPair
from skill.domain.models import CanonicalMetric
from skill.services.settings import SettingsService


@pytest.fixture
def service() -> SettingsService:
    svc = SettingsService()
    svc.initialize()
    return svc


class TestGetAlertConfigDefaults:
    def test_returns_defaults_when_no_config_saved(
        self, service: SettingsService,
    ) -> None:
        config = service.get_alert_config()
        assert config.enabled is True
        assert config.interval_seconds == 14400
        assert config.severity_threshold == "medium"
        assert config.cooldown_minutes == 60
        assert config.monitored_pairs == ()

    def test_returns_defaults_when_corrupt_value(
        self, service: SettingsService,
    ) -> None:
        service.set_setting(service.ALERT_CONFIG_KEY, "not-a-dict")
        config = service.get_alert_config()
        assert config == AlertConfig()


class TestSaveAlertConfig:
    def test_round_trip_simple(
        self, service: SettingsService,
    ) -> None:
        original = AlertConfig(
            enabled=False,
            interval_seconds=3600,
            severity_threshold="high",
            cooldown_minutes=120,
        )
        service.save_alert_config(original)
        loaded = service.get_alert_config()
        assert loaded.enabled is False
        assert loaded.interval_seconds == 3600
        assert loaded.severity_threshold == "high"
        assert loaded.cooldown_minutes == 120
        assert loaded.monitored_pairs == ()

    def test_round_trip_with_pairs(
        self, service: SettingsService,
    ) -> None:
        pair = MonitoredPair(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Boiler-1",
        )
        original = AlertConfig(
            monitored_pairs=(pair,),
        )
        service.save_alert_config(original)
        loaded = service.get_alert_config()
        assert len(loaded.monitored_pairs) == 1
        assert loaded.monitored_pairs[0].metric == CanonicalMetric.ENERGY_PER_UNIT
        assert loaded.monitored_pairs[0].asset_id == "Boiler-1"

    def test_overwrite_existing(
        self, service: SettingsService,
    ) -> None:
        service.save_alert_config(AlertConfig(enabled=True))
        service.save_alert_config(AlertConfig(enabled=False))
        loaded = service.get_alert_config()
        assert loaded.enabled is False

    def test_invalid_metric_in_pairs_skipped(
        self, service: SettingsService,
    ) -> None:
        service.set_setting(service.ALERT_CONFIG_KEY, {
            "enabled": True,
            "monitored_pairs": [
                {"metric": "energy_per_unit", "asset_id": "A"},
                {"metric": "invalid_metric_xyz", "asset_id": "B"},
            ],
        })
        config = service.get_alert_config()
        assert len(config.monitored_pairs) == 1
        assert config.monitored_pairs[0].asset_id == "A"


class TestQueryAnomalyThreshold:
    def test_defaults_to_alert_threshold_when_unset(
        self,
        service: SettingsService,
    ) -> None:
        """Query threshold falls back to alert z-score threshold by default."""
        service.save_alert_config(AlertConfig(z_score_threshold=3.1))
        service.delete_setting(service.QUERY_ANOMALY_THRESHOLD_KEY)

        threshold = service.get_query_anomaly_threshold()

        assert threshold == pytest.approx(3.1)

    def test_can_persist_query_threshold_independently(
        self,
        service: SettingsService,
    ) -> None:
        """Explicit query threshold stays independent from alert threshold."""
        service.save_alert_config(AlertConfig(z_score_threshold=3.0))
        service.set_query_anomaly_threshold(1.8)

        service.save_alert_config(AlertConfig(z_score_threshold=4.0))

        assert service.get_query_anomaly_threshold() == pytest.approx(1.8)
        assert service.get_alert_config().z_score_threshold == pytest.approx(4.0)
