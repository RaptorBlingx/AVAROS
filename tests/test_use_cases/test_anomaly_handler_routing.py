"""Tests for anomaly handler routing between pair check and aggregate scan."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from skill._handlers import _fallback_anomaly, _fallback_drift
from skill._metric_handlers import handle_anomaly_check, handle_drift_check
from skill.domain.exceptions import AssetNotFoundError
from skill.domain.models import CanonicalMetric


def _build_skill_for_anomaly() -> SimpleNamespace:
    """Build a minimal skill double for anomaly handler tests."""
    skill = SimpleNamespace()
    skill.dispatcher = Mock()
    skill.response_builder = Mock()
    skill.speak = Mock()
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    skill._extract_utterance_text = Mock(return_value="")
    skill._resolve_metric_from_utterance = Mock(return_value=None)
    skill._extract_line_assets_from_text = Mock(return_value=[])
    skill._canonicalize_asset_id = Mock(side_effect=lambda text, **_: text)
    return skill


def test_handle_anomaly_check_routes_broad_query_to_scan() -> None:
    """Broad anomaly utterances run aggregate scan with no explicit filters."""
    skill = _build_skill_for_anomaly()
    message = SimpleNamespace(data={"utterance": "any unusual patterns today"})

    skill._extract_utterance_text.return_value = "any unusual patterns today"
    skill.dispatcher.scan_anomalies.return_value = "scan-result"
    skill.response_builder.format_anomaly_scan_result.return_value = "scan response"

    handle_anomaly_check(skill, message)

    skill.dispatcher.scan_anomalies.assert_called_once_with(metric=None, asset_id=None)
    skill.dispatcher.check_anomaly.assert_not_called()
    skill.response_builder.format_anomaly_scan_result.assert_called_once_with("scan-result")
    skill.speak.assert_called_once_with("scan response")


def test_handle_anomaly_check_routes_targeted_query_to_pair_check() -> None:
    """Explicit metric + asset utterances use single-pair anomaly checks."""
    skill = _build_skill_for_anomaly()
    message = SimpleNamespace(data={"utterance": "check oee anomalies on line two"})

    skill._extract_utterance_text.return_value = "check oee anomalies on line two"
    skill._resolve_metric_from_utterance.return_value = CanonicalMetric.OEE
    skill._extract_line_assets_from_text.return_value = ["Line-2"]
    skill.dispatcher.check_anomaly.return_value = "pair-result"
    skill.response_builder.format_anomaly_result.return_value = "pair response"

    handle_anomaly_check(skill, message)

    skill.dispatcher.check_anomaly.assert_called_once_with(
        metric=CanonicalMetric.OEE,
        asset_id="Line-2",
    )
    skill.dispatcher.scan_anomalies.assert_not_called()
    skill.response_builder.format_anomaly_result.assert_called_once_with("pair-result")
    skill.speak.assert_called_once_with("pair response")


def test_fallback_anomaly_routes_broad_query_to_scan() -> None:
    """Fallback anomaly path also uses aggregate scan for broad utterances."""
    skill = _build_skill_for_anomaly()
    message = SimpleNamespace(data={"utterance": "any anomalies"})

    skill.dispatcher.scan_anomalies.return_value = "scan-result"
    skill.response_builder.format_anomaly_scan_result.return_value = "scan response"

    handled = _fallback_anomaly(skill, message, "any anomalies")

    assert handled is True
    skill.dispatcher.scan_anomalies.assert_called_once_with(metric=None, asset_id=None)
    skill.dispatcher.check_anomaly.assert_not_called()


def _build_skill_for_drift() -> SimpleNamespace:
    """Build a minimal skill double for drift handler tests."""
    skill = SimpleNamespace()
    skill.dispatcher = Mock()
    skill.response_builder = Mock()
    skill.speak = Mock()
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    skill._extract_utterance_text = Mock(return_value="")
    skill._resolve_metric_from_utterance = Mock(return_value=None)
    skill._resolve_asset_id = Mock(return_value="Line-1")
    skill._get_asset_registry = Mock(return_value=[])
    return skill


def test_handle_drift_falls_back_on_asset_not_found() -> None:
    """Drift handler uses default asset when slot resolution fails."""
    skill = _build_skill_for_drift()
    skill._resolve_asset_id = Mock(side_effect=AssetNotFoundError("bad"))
    skill.settings_service = Mock()
    skill.settings_service.get_asset_mappings.return_value = {
        "Line-1": {"metric_resources": {"energy_per_unit": "r1"}},
    }
    message = SimpleNamespace(data={"utterance": "how has energy been trending"})
    skill._extract_utterance_text.return_value = "how has energy been trending"
    skill._resolve_metric_from_utterance.return_value = CanonicalMetric.ENERGY_PER_UNIT
    skill.dispatcher.check_drift.return_value = "drift-result"
    skill.response_builder.format_drift_result.return_value = "drift response"

    handle_drift_check(skill, message)

    skill.dispatcher.check_drift.assert_called_once()
    skill.speak.assert_called_once_with("drift response")


def test_fallback_drift_falls_back_on_asset_not_found() -> None:
    """Fallback drift path uses default asset when slot resolution fails."""
    skill = _build_skill_for_drift()
    skill._resolve_asset_id = Mock(side_effect=AssetNotFoundError("bad"))
    skill.settings_service = Mock()
    skill.settings_service.get_asset_mappings.return_value = {
        "Line-1": {"metric_resources": {"energy_per_unit": "r1"}},
    }
    message = SimpleNamespace(data={"utterance": "how has energy been trending"})
    skill._resolve_metric_from_utterance.return_value = CanonicalMetric.ENERGY_PER_UNIT
    skill.dispatcher.check_drift.return_value = "drift-result"
    skill.response_builder.format_drift_result.return_value = "drift response"

    handled = _fallback_drift(skill, message, "how has energy been trending")

    assert handled is True
    skill.dispatcher.check_drift.assert_called_once()
    skill.speak.assert_called_once_with("drift response")
