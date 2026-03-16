"""Tests for generic compare/trend handlers added in P5.5-E02."""

from __future__ import annotations

from unittest.mock import Mock

from skill import AVAROSSkill
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod


def _make_skill() -> AVAROSSkill:
    """Create a skill instance with mocked runtime collaborators."""
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.speak = Mock()
    skill.speak_dialog = Mock()
    skill.dispatcher = Mock()
    skill.dispatcher.adapter = Mock()
    skill.dispatcher.adapter.get_supported_metrics = Mock(return_value=list(CanonicalMetric))
    skill.dispatcher.adapter.supports_capability = Mock(return_value=True)
    skill.response_builder = Mock()
    skill._resolve_compare_assets = Mock(return_value=("Line-1", "Line-2"))
    skill._resolve_asset_id = Mock(return_value="Line-1")
    skill._parse_period = Mock(return_value=TimePeriod.from_natural_language("today"))
    skill._safe_dispatch = Mock(side_effect=lambda _handler, action: action())
    return skill


def _message(**data):
    """Create a minimal OVOS-like message object."""
    message = Mock()
    message.data = data
    message.msg_type = None
    return message


def test_compare_metric_resolves_oee_and_dispatches():
    """Compare handler should resolve OEE and dispatch compare()."""
    skill = _make_skill()
    result = Mock()
    skill.dispatcher.compare.return_value = result
    skill.response_builder.format_comparison_result.return_value = "ok"

    skill.handle_compare_metric(_message(metric="oee", period="today"))

    skill.dispatcher.compare.assert_called_once_with(
        metric=CanonicalMetric.OEE,
        asset_ids=["Line-1", "Line-2"],
        period=skill._parse_period.return_value,
    )
    skill.response_builder.format_comparison_result.assert_called_once_with(result)
    skill.speak.assert_called_once_with("ok")


def test_compare_metric_resolves_material_efficiency_and_dispatches():
    """Compare handler should resolve a multi-word canonical metric."""
    skill = _make_skill()
    skill.dispatcher.compare.return_value = Mock()
    skill.response_builder.format_comparison_result.return_value = "ok"

    skill.handle_compare_metric(_message(metric="material efficiency", period="today"))

    called_metric = skill.dispatcher.compare.call_args.kwargs["metric"]
    assert called_metric is CanonicalMetric.MATERIAL_EFFICIENCY


def test_compare_metric_unrecognized_metric_speaks_error():
    """Unknown compare metric should speak guidance and skip dispatch."""
    skill = _make_skill()

    skill.handle_compare_metric(_message(metric="foobar metric", period="today"))

    skill.dispatcher.compare.assert_not_called()
    skill.speak_dialog.assert_called_once_with("metric.not_recognized")


def test_compare_metric_unmapped_metric_speaks_error():
    """Recognized but unmapped compare metric should be blocked gracefully."""
    skill = _make_skill()
    skill.dispatcher.adapter.get_supported_metrics.return_value = [CanonicalMetric.ENERGY_PER_UNIT]

    skill.handle_compare_metric(_message(metric="oee", period="today"))

    skill.dispatcher.compare.assert_not_called()
    skill.speak_dialog.assert_called_once_with(
        "metric.not_configured",
        data={"metric": CanonicalMetric.OEE.display_name},
    )


def test_compare_metric_mapping_guard_fails_closed_on_adapter_errors():
    """Adapter capability lookup errors should fail closed and block dispatch."""
    skill = _make_skill()
    skill.dispatcher.adapter.get_supported_metrics.side_effect = RuntimeError("boom-1")
    skill.dispatcher.adapter.supports_capability.side_effect = RuntimeError("boom-2")

    skill.handle_compare_metric(_message(metric="oee", period="today"))

    skill.dispatcher.compare.assert_not_called()
    skill.speak_dialog.assert_called_once_with(
        "metric.not_configured",
        data={"metric": CanonicalMetric.OEE.display_name},
    )


def test_trend_metric_resolves_throughput_and_dispatches():
    """Trend handler should resolve throughput and dispatch get_trend()."""
    skill = _make_skill()
    result = Mock()
    skill.dispatcher.get_trend.return_value = result
    skill.response_builder.format_trend_result.return_value = "ok"

    skill.handle_trend_metric(_message(metric="throughput", period="today"))

    skill.dispatcher.get_trend.assert_called_once_with(
        metric=CanonicalMetric.THROUGHPUT,
        asset_id="Line-1",
        period=skill._parse_period.return_value,
        granularity="daily",
    )
    skill.response_builder.format_trend_result.assert_called_once_with(result)
    skill.speak.assert_called_once_with("ok")


def test_trend_metric_resolves_co2_per_unit_and_dispatches():
    """Trend handler should resolve CO₂ phrasing variants."""
    skill = _make_skill()
    skill.dispatcher.get_trend.return_value = Mock()
    skill.response_builder.format_trend_result.return_value = "ok"

    skill.handle_trend_metric(_message(metric="CO₂ per unit", period="today"))

    called_metric = skill.dispatcher.get_trend.call_args.kwargs["metric"]
    assert called_metric is CanonicalMetric.CO2_PER_UNIT


def test_trend_metric_unrecognized_metric_speaks_error():
    """Unknown trend metric should speak guidance and skip dispatch."""
    skill = _make_skill()

    skill.handle_trend_metric(_message(metric="unknown trend metric", period="today"))

    skill.dispatcher.get_trend.assert_not_called()
    skill.speak_dialog.assert_called_once_with("metric.not_recognized")


def test_trend_metric_unmapped_metric_speaks_error():
    """Recognized but unmapped trend metric should be blocked gracefully."""
    skill = _make_skill()
    skill.dispatcher.adapter.get_supported_metrics.return_value = [CanonicalMetric.ENERGY_PER_UNIT]

    skill.handle_trend_metric(_message(metric="oee", period="today"))

    skill.dispatcher.get_trend.assert_not_called()
    skill.speak_dialog.assert_called_once_with(
        "metric.not_configured",
        data={"metric": CanonicalMetric.OEE.display_name},
    )


def test_old_compare_energy_intent_still_works():
    """Legacy compare energy handler should remain behavior-compatible."""
    skill = _make_skill()
    skill.dispatcher.compare.return_value = Mock()
    skill.response_builder.format_comparison_result.return_value = "ok"

    skill.handle_compare_energy(_message(period="today"))

    called_metric = skill.dispatcher.compare.call_args.kwargs["metric"]
    assert called_metric is CanonicalMetric.ENERGY_PER_UNIT


def test_old_trend_energy_intent_still_works():
    """Legacy trend energy handler should remain behavior-compatible."""
    skill = _make_skill()
    skill.dispatcher.get_trend.return_value = Mock()
    skill.response_builder.format_trend_result.return_value = "ok"

    skill.handle_trend_energy(_message(period="today"))

    called_metric = skill.dispatcher.get_trend.call_args.kwargs["metric"]
    assert called_metric is CanonicalMetric.ENERGY_PER_UNIT


def test_trend_energy_falls_back_to_last_week_when_today_is_empty():
    """Empty today trend should retry automatically with last-week period."""
    skill = _make_skill()
    skill._parse_period = Mock(side_effect=lambda value: TimePeriod.from_natural_language(str(value)))
    skill.dispatcher.get_trend.side_effect = [
        AdapterError(
            message="Empty trend response for energy_per_unit",
            code="EMPTY_RESPONSE",
            platform="reneryo",
        ),
        Mock(),
    ]
    skill.response_builder.format_trend_result.return_value = "ok"

    skill.handle_trend_energy(_message(period="today"))

    assert skill.dispatcher.get_trend.call_count == 2
    first_period = skill.dispatcher.get_trend.call_args_list[0].kwargs["period"]
    second_period = skill.dispatcher.get_trend.call_args_list[1].kwargs["period"]
    assert first_period.display_name == "today"
    assert second_period.display_name == "last week"


def test_trend_energy_falls_back_to_kpi_when_trend_unavailable():
    """When trend remains empty, handler should return current KPI instead of generic error."""
    skill = _make_skill()
    skill._parse_period = Mock(side_effect=lambda value: TimePeriod.from_natural_language(str(value)))
    skill.dispatcher.get_trend.side_effect = [
        AdapterError(
            message="Empty trend response for energy_per_unit",
            code="EMPTY_RESPONSE",
            platform="reneryo",
        ),
        AdapterError(
            message="Empty trend response for energy_per_unit",
            code="EMPTY_RESPONSE",
            platform="reneryo",
        ),
    ]
    kpi_result = Mock()
    skill.dispatcher.get_kpi.return_value = kpi_result
    skill.response_builder.format_kpi_result.return_value = "Energy per unit for Line-1 is 2.35 kWh/unit today."

    skill.handle_trend_energy(_message(period="today"))

    skill.dispatcher.get_kpi.assert_called_once()
    skill.response_builder.format_kpi_result.assert_called_once_with(kpi_result)
    spoken = skill.speak.call_args.args[0]
    assert "couldn't find enough trend points" in spoken
    assert "Energy per unit for Line-1 is 2.35 kWh/unit today." in spoken


def test_old_trend_scrap_intent_still_works():
    """Legacy trend scrap handler should remain behavior-compatible."""
    skill = _make_skill()
    skill.dispatcher.get_trend.return_value = Mock()
    skill.response_builder.format_trend_result.return_value = "ok"

    skill.handle_trend_scrap(_message(period="today"))

    called_metric = skill.dispatcher.get_trend.call_args.kwargs["metric"]
    assert called_metric is CanonicalMetric.SCRAP_RATE
