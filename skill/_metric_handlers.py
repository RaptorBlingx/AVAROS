"""Metric and KPI-related handler implementations for AVAROSSkill."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric
from skill.domain.results import AnomalyResult, ComparisonResult, KPIResult, TrendResult, WhatIfResult

if TYPE_CHECKING:
    from skill import AVAROSSkill


logger = logging.getLogger(__name__)


def _is_metric_mapped_for_active_adapter(
    skill: "AVAROSSkill",
    metric: CanonicalMetric,
) -> bool:
    """Return True when current adapter reports support for the metric."""
    dispatcher = getattr(skill, "dispatcher", None)
    if dispatcher is None:
        return False

    adapter = getattr(dispatcher, "adapter", None)
    if adapter is None:
        return False

    supported_metrics = None
    try:
        supported_metrics = adapter.get_supported_metrics()
    except Exception as exc:
        logger.warning(
            "Could not read supported metrics for '%s': %s",
            metric.value,
            exc,
        )

    if isinstance(supported_metrics, (list, tuple, set, frozenset)):
        return metric in supported_metrics or metric.value in supported_metrics

    try:
        return bool(adapter.supports_capability(metric.value))
    except Exception as exc:
        logger.warning(
            "Capability check failed for '%s'; treating as unmapped: %s",
            metric.value,
            exc,
        )
        return False


def _resolve_and_validate_metric(skill: "AVAROSSkill", message) -> CanonicalMetric | None:
    """Resolve metric from utterance and ensure it is mapped."""
    data = getattr(message, "data", {}) or {}
    metric_text = str(data.get("metric", "")).strip()
    source_text = metric_text or skill._extract_utterance_text(message)
    metric = skill._resolve_metric_from_utterance(source_text)

    if metric is None:
        skill.speak_dialog("metric.not_recognized")
        return None

    if not _is_metric_mapped_for_active_adapter(skill, metric):
        skill.speak_dialog("metric.not_configured", data={"metric": metric.display_name})
        return None

    return metric


def _query_trend_with_period_fallback(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    asset_id: str,
    period,
    granularity: str,
):
    """Query trend and widen period once when narrow-range response is empty."""
    try:
        return skill.dispatcher.get_trend(
            metric=metric,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )
    except AdapterError as exc:
        if exc.code != "EMPTY_RESPONSE":
            raise
        if period.duration_days >= 2:
            raise

        fallback_period = skill._parse_period("last week")
        fallback_granularity = "daily" if granularity == "hourly" else granularity
        logger.info(
            "Trend fallback: metric=%s asset=%s period=%s -> %s",
            metric.value,
            asset_id,
            period.display_name,
            fallback_period.display_name,
        )
        return skill.dispatcher.get_trend(
            metric=metric,
            asset_id=asset_id,
            period=fallback_period,
            granularity=fallback_granularity,
        )


def dispatch_kpi_for_metric(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    message,
    handler_name: str,
) -> None:
    """Execute KPI dispatch for a resolved canonical metric."""

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


def handle_compare_energy(skill: "AVAROSSkill", message) -> None:
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


def handle_compare_metric(skill: "AVAROSSkill", message) -> None:
    """Handle generic compare requests for any canonical metric."""
    metric = _resolve_and_validate_metric(skill, message)
    if metric is None:
        return

    def _execute() -> None:
        data = getattr(message, "data", {}) or {}
        asset_a, asset_b = skill._resolve_compare_assets(message)
        period = skill._parse_period(data.get("period", "today"))
        result: ComparisonResult = skill.dispatcher.compare(
            metric=metric,
            asset_ids=[asset_a, asset_b],
            period=period,
        )
        response = skill.response_builder.format_comparison_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_compare_metric", _execute)


def handle_trend_scrap(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Show scrap rate trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")

        result: TrendResult = _query_trend_with_period_fallback(
            skill,
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_scrap", _execute)


def handle_trend_metric(skill: "AVAROSSkill", message) -> None:
    """Handle generic trend requests for any canonical metric."""
    metric = _resolve_and_validate_metric(skill, message)
    if metric is None:
        return

    def _execute() -> None:
        data = getattr(message, "data", {}) or {}
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(data.get("period", "last week"))
        granularity = data.get("granularity", "daily")

        result: TrendResult = _query_trend_with_period_fallback(
            skill,
            metric=metric,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_metric", _execute)


def handle_trend_energy(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Show energy trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = skill._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")
        if period.duration_days < 2 and granularity == "daily":
            granularity = "hourly"
        try:
            result: TrendResult = _query_trend_with_period_fallback(
                skill,
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id=asset_id,
                period=period,
                granularity=granularity,
            )
            response = skill.response_builder.format_trend_result(result)
            skill.speak(response)
            return
        except AdapterError as exc:
            if exc.code != "EMPTY_RESPONSE":
                raise

        # Last-resort UX fallback: if trend points are unavailable, still return
        # the current energy KPI so the command stays useful.
        kpi_result: KPIResult = skill.dispatcher.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id=asset_id,
            period=skill._parse_period("today"),
        )
        kpi_response = skill.response_builder.format_kpi_result(kpi_result)
        skill.speak(
            f"I couldn't find enough trend points for {period.display_name}. {kpi_response}",
        )

    skill._safe_dispatch("handle_trend_energy", _execute)


def handle_anomaly_check(skill: "AVAROSSkill", message) -> None:
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


def handle_whatif_temperature(skill: "AVAROSSkill", message) -> None:
    """Handle: 'What if we reduce temperature by {amount} degrees?'."""

    def _execute() -> None:
        from skill.domain.models import ScenarioParameter, WhatIfScenario

        amount = skill._resolve_temperature_amount(message)
        asset_id = skill._resolve_asset_id(message)

        scenario = WhatIfScenario(
            name="temperature_change",
            asset_id=asset_id,
            parameters=[
                ScenarioParameter(
                    name="temperature",
                    baseline_value=25.0,
                    proposed_value=25.0 - amount,
                    unit="°C",
                )
            ],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )

        result: WhatIfResult = skill.dispatcher.simulate_whatif(scenario)

        response = skill.response_builder.format_whatif_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_whatif_temperature", _execute)
