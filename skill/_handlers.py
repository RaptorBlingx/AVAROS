"""KPI and fallback handler implementations for AVAROSSkill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill._metric_handlers import _resolve_default_metric
from skill._metric_handlers import _resolve_kpi_period as _resolve_kpi_period_impl
from skill.domain.models import CanonicalMetric
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
        asset_id = skill._resolve_asset_id(message)
        metric = _resolve_default_metric(skill, utterance)
        result = skill.dispatcher.check_anomaly(metric=metric, asset_id=asset_id)
        response = skill.response_builder.format_anomaly_result(result)
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
        asset_id = skill._resolve_asset_id(message)
        metric = _resolve_default_metric(skill, utterance)
        result = skill.dispatcher.check_drift(metric=metric, asset_id=asset_id)
        response = skill.response_builder.format_drift_result(result)
        skill.speak(response)
        return True

    handled = skill._safe_dispatch("fallback_drift", _execute)
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
        return True

    return (
        skill._resolve_metric_from_utterance(text) is not None
        or skill._is_anomaly_query(text)
        or skill._is_drift_query(text)
    )
