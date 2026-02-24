"""Intent and fallback handler implementations for AVAROSSkill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill.domain.models import CanonicalMetric
from skill.domain.results import AnomalyResult, ComparisonResult, KPIResult, TrendResult, WhatIfResult

if TYPE_CHECKING:
    from skill import AVAROSSkill


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


def handle_greeting(skill: "AVAROSSkill", message) -> None:
    """Handle greetings such as 'hello' or 'hey avaros'."""
    skill.speak_dialog("greeting.response")


def handle_help(skill: "AVAROSSkill", message) -> None:
    """Handle generic help requests."""
    skill.speak_dialog("help.response")


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


def handle_trend_scrap(skill: "AVAROSSkill", message) -> None:
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


def handle_trend_energy(skill: "AVAROSSkill", message) -> None:
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


def handle_control_turn_on(skill: "AVAROSSkill", message) -> None:
    """Handle generic turn-on command (platform-agnostic mock default)."""

    def _execute() -> None:
        if not skill._require_intent_binding("control.device.turn_on"):
            return
        target = skill._resolve_asset_id(message, default="system")
        skill._set_power_state("on")
        skill.speak(f"Power state is now on for {target}.")

    skill._safe_dispatch("handle_control_turn_on", _execute)


def handle_control_turn_off(skill: "AVAROSSkill", message) -> None:
    """Handle generic turn-off command (platform-agnostic mock default)."""

    def _execute() -> None:
        if not skill._require_intent_binding("control.device.turn_off"):
            return
        target = skill._resolve_asset_id(message, default="system")
        skill._set_power_state("off")
        skill.speak(f"Power state is now off for {target}.")

    skill._safe_dispatch("handle_control_turn_off", _execute)


def handle_status_system_show(skill: "AVAROSSkill", message) -> None:
    """Handle generic system status request."""

    def _execute() -> None:
        if not skill._require_intent_binding("status.system.show"):
            return

        active_profile = skill._resolve_active_profile()
        power_state = skill._get_power_state()
        platform = "mock"
        if skill.settings_service is not None:
            config = skill.settings_service.get_profile(active_profile)
            if config is not None:
                platform = config.platform_type

        adapter_name = (
            type(skill.dispatcher._adapter).__name__
            if skill.dispatcher is not None
            else "UnknownAdapter"
        )
        health = "online" if power_state == "on" else "offline"
        skill.speak(
            (
                f"System is {health}. Active profile is {active_profile} on platform "
                f"{platform}, and adapter is {adapter_name}."
            )
        )

    skill._safe_dispatch("handle_status_system_show", _execute)


def handle_status_profile_show(skill: "AVAROSSkill", message) -> None:
    """Handle profile/config status request."""

    def _execute() -> None:
        if not skill._require_intent_binding("status.profile.show"):
            return

        profile = skill._resolve_active_profile()
        platform = "mock"
        if skill.settings_service is not None:
            config = skill.settings_service.get_profile(profile)
            if config is not None:
                platform = config.platform_type

        skill.speak(f"Current profile is {profile} on platform {platform}.")

    skill._safe_dispatch("handle_status_profile_show", _execute)


def handle_help_capabilities_list(skill: "AVAROSSkill", message) -> None:
    """Handle capability/help request for generic + KPI intents."""

    def _execute() -> None:
        if not skill._require_intent_binding("help.capabilities.list"):
            return

        skill.speak(
            "I can report KPIs, compare and trend metrics, check anomalies, run what if simulations, "
            "and handle generic commands like turn on, turn off, and show status."
        )

    skill._safe_dispatch("handle_help_capabilities_list", _execute)


def handle_metric_query_fallback(skill: "AVAROSSkill", message):
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


def handle_intent_failure(skill: "AVAROSSkill", message) -> None:
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


def can_answer(skill: "AVAROSSkill", message) -> bool:
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
