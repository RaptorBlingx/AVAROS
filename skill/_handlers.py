"""KPI and fallback handler implementations for AVAROSSkill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill.domain.models import CanonicalMetric
from skill.domain.results import AnomalyResult, ComparisonResult, KPIResult, TrendResult

if TYPE_CHECKING:
    from ovos_bus_client.message import Message
    from skill import AVAROSSkill


def dispatch_kpi_for_metric(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    message: Message,
    handler_name: str,
) -> None:
    """Dispatch KPI request for a canonical metric and speak formatted output.

    Args:
        skill: Bound AVAROS skill instance.
        metric: Canonical metric to query.
        message: Incoming bus message with slots and context.
        handler_name: Handler name for structured error logging.

    Returns:
        ``None``. Side effect is speaking the formatted response.
    """

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(message.data.get("period", "today"))

        result: KPIResult = skill.dispatcher.get_kpi(
            metric=metric,
            asset_id=asset_id,
            period=period,
        )

        response = skill.response_builder.format_kpi_result(result)
        skill.speak(response)

    skill._safe_dispatch(handler_name, _execute)


def handle_compare_energy(skill: "AVAROSSkill", message: Message) -> None:
    """Handle: 'Compare energy between {asset_a} and {asset_b}'."""

    def _execute() -> None:
        asset_a, asset_b = skill._resolve_compare_assets(message)
        period = skill._parse_period(message.data.get("period", "today"))

        result: ComparisonResult = skill.dispatcher.compare(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_ids=[asset_a, asset_b],
            period=period,
        )

        response = skill.response_builder.format_comparison_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_compare_energy", _execute)


def handle_trend_scrap(skill: "AVAROSSkill", message: Message) -> None:
    """Handle: 'Show scrap rate trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")

        result: TrendResult = skill.dispatcher.get_trend(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_scrap", _execute)


def handle_trend_energy(skill: "AVAROSSkill", message: Message) -> None:
    """Handle: 'Show energy trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")
        if period.duration_days < 2 and granularity == "daily":
            granularity = "hourly"

        result: TrendResult = skill.dispatcher.get_trend(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_energy", _execute)


def handle_anomaly_check(skill: "AVAROSSkill", message: Message) -> None:
    """Handle: 'Any unusual patterns in production?'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)

        result: AnomalyResult = skill.dispatcher.check_anomaly(
            metric=CanonicalMetric.OEE,
            asset_id=asset_id,
        )

        response = skill.response_builder.format_anomaly_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_anomaly_check", _execute)


def handle_metric_query_fallback(skill: "AVAROSSkill", message: Message) -> bool:
    """Fallback: resolve metric KPI queries missed by strict intent parsing."""
    utterance = skill._extract_utterance_text(message).lower()
    if skill._is_anomaly_query(utterance):

        def _execute_anomaly() -> bool:
            asset_id = skill._resolve_asset_id(message)
            result: AnomalyResult = skill.dispatcher.check_anomaly(
                metric=CanonicalMetric.OEE,
                asset_id=asset_id,
            )
            response = skill.response_builder.format_anomaly_result(result)
            skill.speak(response)
            return True

        handled = skill._safe_dispatch(
            "handle_metric_query_fallback_anomaly",
            _execute_anomaly,
        )
        return bool(handled)

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        return False

    def _execute() -> bool:
        data = getattr(message, "data", {}) or {}
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(data.get("period", "today"))
        result: KPIResult = skill.dispatcher.get_kpi(
            metric=metric,
            asset_id=asset_id,
            period=period,
        )
        response = skill.response_builder.format_kpi_result(result)
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("handle_metric_query_fallback", _execute)
    return bool(handled)


def handle_intent_failure(skill: "AVAROSSkill", message: Message) -> None:
    """Recover KPI queries from global intent-failure events."""
    utterance = skill._extract_utterance_text(message).lower()
    if skill._is_anomaly_query(utterance):

        def _execute_anomaly() -> None:
            asset_id = skill._resolve_asset_id(message)
            result: AnomalyResult = skill.dispatcher.check_anomaly(
                metric=CanonicalMetric.OEE,
                asset_id=asset_id,
            )
            response = skill.response_builder.format_anomaly_result(result)
            skill.speak(response)

        skill._safe_dispatch("_handle_intent_failure_anomaly", _execute_anomaly)
        return

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        return

    def _execute() -> None:
        data = getattr(message, "data", {}) or {}
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(data.get("period", "today"))
        result: KPIResult = skill.dispatcher.get_kpi(
            metric=metric,
            asset_id=asset_id,
            period=period,
        )
        response = skill.response_builder.format_kpi_result(result)
        skill.speak(response)

    skill._safe_dispatch("_handle_intent_failure", _execute)


def can_answer(skill: "AVAROSSkill", message: Message) -> bool:
    """Tell OVOS fallback service when this skill can answer utterance."""
    data = getattr(message, "data", {}) or {}
    utterances = data.get("utterances")
    if isinstance(utterances, list) and utterances:
        text = str(utterances[0]).lower()
    else:
        text = skill._extract_utterance_text(message).lower()

    if not text.strip():
        return True

    return (
        skill._resolve_metric_from_utterance(text) is not None
        or skill._is_anomaly_query(text)
    )
