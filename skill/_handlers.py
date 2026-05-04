"""KPI and fallback handler implementations for AVAROSSkill."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from skill._metric_handlers import _format_anomaly_query_response
from skill._metric_handlers import _resolve_anomaly_query_scope
from skill._metric_handlers import _resolve_default_metric
from skill._metric_handlers import _resolve_drift_asset
from skill._metric_handlers import _resolve_forecast_horizon
from skill._metric_handlers import _resolve_kpi_period as _resolve_kpi_period_impl
from skill.domain.models import CanonicalMetric, ScenarioParameter, WhatIfScenario
from skill.domain.results import KPIResult

if TYPE_CHECKING:
    from ovos_bus_client.message import Message
    from skill import AVAROSSkill


def handle_metric_query_fallback(skill: "AVAROSSkill", message: Message) -> bool:
    """Fallback: resolve metric KPI queries missed by strict intent parsing."""
    utterance = skill._extract_utterance_text(message).lower()

    if skill._is_anomaly_query(utterance):
        return _fallback_anomaly(skill, message, utterance)

    if skill._is_drift_query(utterance):
        return _fallback_drift(skill, message, utterance)

    if skill._is_forecast_query(utterance):
        return _fallback_forecast(skill, message, utterance)

    if skill._is_whatif_query(utterance):
        return _fallback_whatif(skill, message, utterance)

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        return False

    def _execute() -> bool:
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_kpi_period_impl(
            skill,
            metric=metric,
            asset_id=asset_id,
            message=message,
        )
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


def _fallback_anomaly(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> bool:
    """Execute anomaly check via fallback path."""

    def _execute() -> bool:
        metric, asset_id = _resolve_anomaly_query_scope(
            skill,
            message,
            utterance,
        )
        response = _format_anomaly_query_response(
            skill,
            metric=metric,
            asset_id=asset_id,
        )
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("fallback_anomaly", _execute)
    return bool(handled)


def _fallback_drift(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> bool:
    """Execute drift check via fallback path."""

    def _execute() -> bool:
        asset_id = _resolve_drift_asset(skill, message)
        metric = _resolve_default_metric(skill, utterance)
        result = skill.dispatcher.check_drift(metric=metric, asset_id=asset_id)
        response = skill.response_builder.format_drift_result(result)
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("fallback_drift", _execute)
    return bool(handled)


def _fallback_forecast(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> bool:
    """Execute forecast requests missed by strict intent parsing."""

    def _execute() -> bool:
        asset_id = _resolve_drift_asset(skill, message)
        metric = _resolve_default_metric(skill, utterance)
        horizon = _resolve_forecast_horizon(message)
        result = skill.dispatcher.forecast_metric(
            metric=metric,
            asset_id=asset_id,
            horizon_periods=horizon,
        )
        response = skill.response_builder.format_forecast_result(result)
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("fallback_forecast", _execute)
    return bool(handled)


def handle_intent_failure(skill: "AVAROSSkill", message: Message) -> None:
    """Recover KPI queries from global intent-failure events."""
    utterance = skill._extract_utterance_text(message).lower()

    if skill._is_anomaly_query(utterance):
        _fallback_anomaly(skill, message, utterance)
        return

    if skill._is_drift_query(utterance):
        _fallback_drift(skill, message, utterance)
        return

    if skill._is_forecast_query(utterance):
        _fallback_forecast(skill, message, utterance)
        return

    if skill._is_whatif_query(utterance):
        _fallback_whatif(skill, message, utterance)
        return

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        return

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_kpi_period_impl(
            skill,
            metric=metric,
            asset_id=asset_id,
            message=message,
        )
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
        return False

    return (
        skill._resolve_metric_from_utterance(text) is not None
        or skill._is_anomaly_query(text)
        or skill._is_drift_query(text)
        or skill._is_forecast_query(text)
        or skill._is_whatif_query(text)
    )


def handle_whatif_scenario(skill: "AVAROSSkill", message: Message) -> None:
    """Handle bounded what-if decision-support scenarios."""
    utterance = skill._extract_utterance_text(message).lower()
    _fallback_whatif(skill, message, utterance)


def _fallback_whatif(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> bool:
    """Execute what-if scenarios missed by strict intent parsing."""

    def _execute() -> bool:
        scenario = _build_whatif_scenario(skill, message, utterance)
        result = skill.dispatcher.simulate_whatif(scenario)
        response = skill.response_builder.format_whatif_result(result)
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("fallback_whatif", _execute)
    return bool(handled)


def _build_whatif_scenario(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> WhatIfScenario:
    """Parse an utterance into a bounded KPI-change scenario."""
    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        metric = CanonicalMetric.PEAK_DEMAND if "peak" in utterance else CanonicalMetric.ENERGY_PER_UNIT

    asset_id = _resolve_drift_asset(skill, message)
    change_percent = _resolve_whatif_change_percent(skill, utterance, metric)
    parameter = ScenarioParameter(
        name="assumed_kpi_change_percent",
        baseline_value=0.0,
        proposed_value=change_percent,
        unit="%",
    )
    return WhatIfScenario(
        name=_scenario_name(metric, change_percent),
        asset_id=asset_id,
        parameters=[parameter],
        target_metric=metric,
    )


def _resolve_whatif_change_percent(
    skill: "AVAROSSkill",
    utterance: str,
    metric: CanonicalMetric,
) -> float:
    """Resolve scenario change direction and percentage from text."""
    normalized = re.sub(r"[^a-z0-9.%\s-]", " ", utterance.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    amount_match = (
        re.search(r"\bby\s+([-+]?\d+(?:\.\d+)?)\s*(?:%|percent)?\b", normalized)
        or re.search(r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent)\b", normalized)
    )
    amount = float(amount_match.group(1)) if amount_match else 5.0

    if "shift" in normalized and "peak" in normalized:
        return -abs(amount)
    if re.search(r"\b(increase|increases|increased|rise|rises|rising|higher)\b", normalized):
        return abs(amount)
    if re.search(r"\b(reduce|reduces|reduced|drop|drops|decrease|decreases|lower|cut|save|savings)\b", normalized):
        return -abs(amount)
    if re.search(r"\b(improve|improves|improved|improvement)\b", normalized):
        return abs(amount) if _higher_is_better(metric) else -abs(amount)
    if re.search(r"\b(worse|worsen|worsens|degrade|degrades)\b", normalized):
        return -abs(amount) if _higher_is_better(metric) else abs(amount)
    return -abs(amount) if not _higher_is_better(metric) else abs(amount)


def _higher_is_better(metric: CanonicalMetric) -> bool:
    """Return True for metrics where increases are beneficial."""
    return metric in {
        CanonicalMetric.OEE,
        CanonicalMetric.MATERIAL_EFFICIENCY,
        CanonicalMetric.THROUGHPUT,
        CanonicalMetric.RECYCLED_CONTENT,
        CanonicalMetric.SUPPLIER_ON_TIME,
    }


def _scenario_name(metric: CanonicalMetric, change_percent: float) -> str:
    """Build a stable scenario identifier for audit/logging."""
    direction = "increase" if change_percent >= 0 else "decrease"
    return f"{metric.value}_{direction}_{abs(change_percent):g}_percent"
