"""Tests for generic KPI intent dispatch in AVAROSSkill."""

from __future__ import annotations

from unittest.mock import Mock

from skill import AVAROSSkill
from skill.domain.models import CanonicalMetric, TimePeriod


def _make_skill() -> AVAROSSkill:
    """Create a skill with mocked runtime collaborators for handler tests."""
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.speak = Mock()
    skill.dispatcher = Mock()
    skill.response_builder = Mock()
    skill._resolve_asset_id = Mock(return_value="Line-1")
    skill._parse_period = Mock(return_value=TimePeriod.from_natural_language("today"))
    return skill


def _message_for_intent(intent_name: str):
    """Build a minimal OVOS-like message payload for tests."""
    message = Mock()
    message.data = {"intent_name": intent_name, "period": "today"}
    message.msg_type = None
    return message


def test_generic_kpi_handler_dispatches_energy_per_unit():
    """Intent kpi.energy.per_unit dispatches ENERGY_PER_UNIT query."""
    skill = _make_skill()
    result = Mock()
    skill.dispatcher.get_kpi.return_value = result
    skill.response_builder.format_kpi_result.return_value = "ok"

    captured = {}

    def _safe_dispatch(handler_name, action):
        captured["handler_name"] = handler_name
        return action()

    skill._safe_dispatch = Mock(side_effect=_safe_dispatch)

    skill._handle_generic_kpi(_message_for_intent("kpi.energy.per_unit"))

    skill.dispatcher.get_kpi.assert_called_once_with(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="Line-1",
        period=skill._parse_period.return_value,
    )
    skill.response_builder.format_kpi_result.assert_called_once_with(result)
    skill.speak.assert_called_once_with("ok")
    assert captured["handler_name"] == "handle_kpi_energy_per_unit"


def test_generic_kpi_handler_dispatches_multiple_metrics():
    """Several mapped intents dispatch to their expected canonical metrics."""
    skill = _make_skill()
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())

    cases = [
        ("kpi.oee", CanonicalMetric.OEE),
        ("kpi.co2.total", CanonicalMetric.CO2_TOTAL),
        ("kpi.scrap_rate", CanonicalMetric.SCRAP_RATE),
        ("kpi.throughput", CanonicalMetric.THROUGHPUT),
        ("kpi.energy.total", CanonicalMetric.ENERGY_TOTAL),
    ]

    for intent_name, metric in cases:
        skill.dispatcher.get_kpi.reset_mock()
        skill._handle_generic_kpi(_message_for_intent(intent_name))
        called_metric = skill.dispatcher.get_kpi.call_args.kwargs["metric"]
        assert called_metric is metric


def test_generic_kpi_handler_unknown_intent_speaks_error():
    """Unknown KPI intent does not dispatch and speaks user guidance."""
    skill = _make_skill()
    skill._safe_dispatch = Mock()

    skill._handle_generic_kpi(_message_for_intent("kpi.unknown_metric"))

    skill.dispatcher.get_kpi.assert_not_called()
    skill._safe_dispatch.assert_not_called()
    skill.speak.assert_called_once_with("I don't recognize that metric.")


def test_generic_kpi_handler_calls_safe_dispatch():
    """Generic handler always executes via _safe_dispatch wrapper."""
    skill = _make_skill()
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())

    skill._handle_generic_kpi(_message_for_intent("kpi.oee"))

    skill._safe_dispatch.assert_called_once()
    handler_name = skill._safe_dispatch.call_args.args[0]
    assert handler_name == "handle_kpi_oee"
