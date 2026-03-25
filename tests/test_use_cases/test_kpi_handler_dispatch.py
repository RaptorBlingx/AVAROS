"""Tests for generic KPI intent dispatch in AVAROSSkill."""

from __future__ import annotations

from datetime import timezone
from unittest.mock import Mock

from skill import AVAROSSkill
from skill._metric_handlers import dispatch_kpi_for_metric
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


def _message_for_intent(
    intent_name: str,
    period: str | None = "today",
    utterance: str | None = None,
    utterances: list[str] | None = None,
):
    """Build a minimal OVOS-like message payload for tests."""
    message = Mock()
    payload: dict[str, str] = {"intent_name": intent_name}
    if period is not None:
        payload["period"] = period
    if utterance is not None:
        payload["utterance"] = utterance
    if utterances is not None:
        payload["utterances"] = utterances
    message.data = payload
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


def test_energy_total_without_period_uses_aggregate_window_for_energy_only_seu():
    """ENERGY_TOTAL without explicit period should use aggregate window on energy-only assets."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent("kpi.energy.total", period=None)

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    dispatched_period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
    assert dispatched_period.display_name == "in total"
    assert dispatched_period.start.year == 2021
    assert dispatched_period.start.month == 2
    assert dispatched_period.start.day == 1
    assert dispatched_period.start.tzinfo == timezone.utc
    skill._parse_period.assert_called_once_with("today")


def test_energy_total_with_explicit_period_keeps_requested_window():
    """Explicit period should always override aggregate default behavior."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "kpi.energy.total",
        period="today",
        utterance="what is total energy for seu today",
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    skill._parse_period.assert_called_once_with("today")
    assert skill.dispatcher.get_kpi.call_args.kwargs["period"] is skill._parse_period.return_value


def test_energy_total_with_implicit_today_slot_uses_aggregate_window():
    """Implicit today should fall back to aggregate when this is not a KPI intent path."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "intent.failure",
        period="today",
        utterance="what is total energy for seu",
        utterances=["what is total energy for seu"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    dispatched_period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
    assert dispatched_period.display_name == "in total"
    assert dispatched_period.start.year == 2021
    assert dispatched_period.start.month == 2
    assert dispatched_period.start.day == 1
    assert dispatched_period.start.tzinfo == timezone.utc


def test_energy_total_prefers_utterance_over_utterances_for_period_detection():
    """When both fields exist, period detection should trust utterance first."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "kpi.energy.total",
        period="today",
        utterance="what is total energy for seu",
        utterances=["what is total energy for seu today"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    assert skill.dispatcher.get_kpi.call_args.kwargs["period"].display_name == "in total"


def test_energy_total_uses_today_when_utterance_has_period_phrase():
    """If utterance contains today and slot is today, explicit today should be respected."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "kpi.energy.total",
        period="today",
        utterance="what is total energy for seu today",
        utterances=["what is total energy for seu"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    assert skill.dispatcher.get_kpi.call_args.kwargs["period"].display_name == "today"


def test_energy_total_without_period_phrase_uses_aggregate_even_for_metric_intent():
    """Metric intent should still use aggregate mode when period phrase is absent."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "kpi.energy.total",
        period="today",
        utterance="what is total energy for seu",
        utterances=["what is total energy for seu"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    assert skill.dispatcher.get_kpi.call_args.kwargs["period"].display_name == "in total"


def test_energy_total_aggregate_defaults_work_without_binding_period_metadata():
    """Energy-only native strategy should default to aggregate even when metadata is absent."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "8ce88962-956e-4773-912e-42230d1d0a9b"
    skill.settings_service = Mock()
    skill.settings_service.get_asset_mappings.return_value = {
        "8ce88962-956e-4773-912e-42230d1d0a9b": {
            "display_name": "Seu With Manually Selected Slice",
            "capability_mode": "energy_only",
            "native_metric_bindings": {
                "energy_total": {
                    "strategy": "asset_consumption_total",
                    "unit": "kWh",
                },
            },
        },
    }
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "kpi.energy.total",
        period="today",
        utterance="what is total energy for seu with manually selected slice",
        utterances=["what is total energy for seu with manually selected slice"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
    assert period.display_name == "in total"
    assert period.start.year == 2021
    assert period.start.month == 2
    assert period.start.day == 1


def test_energy_total_ignores_non_period_slot_text_for_energy_only_assets():
    """Corrupted period slots like 'selected slice' should not override aggregate default."""
    skill = _make_skill()
    skill._resolve_asset_id.return_value = "8ce88962-956e-4773-912e-42230d1d0a9b"
    skill.settings_service = Mock()
    skill.settings_service.get_asset_mappings.return_value = {
        "8ce88962-956e-4773-912e-42230d1d0a9b": {
            "display_name": "Seu With Manually Selected Slice",
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
    skill.dispatcher.get_kpi.return_value = Mock()
    skill.response_builder.format_kpi_result.return_value = "ok"
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    message = _message_for_intent(
        "intent.failure",
        period="selected slice",
        utterance="what is total energy for seu with manually selected slice",
        utterances=["what is total energy for seu with manually selected slice"],
    )

    dispatch_kpi_for_metric(
        skill,
        metric=CanonicalMetric.ENERGY_TOTAL,
        message=message,
        handler_name="handle_kpi_energy_total",
    )

    period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
    assert period.display_name == "in total"
