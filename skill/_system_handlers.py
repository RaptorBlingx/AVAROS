"""System and non-KPI intent handlers for AVAROSSkill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill.domain.models import CanonicalMetric, ScenarioParameter, WhatIfScenario
from skill.domain.results import WhatIfResult

if TYPE_CHECKING:
    from ovos_bus_client.message import Message
    from skill import AVAROSSkill


def handle_greeting(skill: "AVAROSSkill", message: Message) -> None:
    """Handle greetings such as 'hello' or 'hey avaros'."""
    skill.speak_dialog("greeting.response")


def handle_help(skill: "AVAROSSkill", message: Message) -> None:
    """Handle generic help requests."""
    skill.speak_dialog("help.response")


def handle_whatif_temperature(skill: "AVAROSSkill", message: Message) -> None:
    """Handle: 'What if we reduce temperature by {amount} degrees?'."""

    def _execute() -> None:
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


def handle_control_turn_on(skill: "AVAROSSkill", message: Message) -> None:
    """Handle generic turn-on command (platform-agnostic mock default)."""

    def _execute() -> None:
        if not skill._require_intent_binding("control.device.turn_on"):
            return
        target = skill._resolve_asset_id(message, default="system")
        skill._set_power_state("on")
        skill.speak(f"Power state is now on for {target}.")

    skill._safe_dispatch("handle_control_turn_on", _execute)


def handle_control_turn_off(skill: "AVAROSSkill", message: Message) -> None:
    """Handle generic turn-off command (platform-agnostic mock default)."""

    def _execute() -> None:
        if not skill._require_intent_binding("control.device.turn_off"):
            return
        target = skill._resolve_asset_id(message, default="system")
        skill._set_power_state("off")
        skill.speak(f"Power state is now off for {target}.")

    skill._safe_dispatch("handle_control_turn_off", _execute)


def handle_status_system_show(skill: "AVAROSSkill", message: Message) -> None:
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


def handle_status_profile_show(skill: "AVAROSSkill", message: Message) -> None:
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


def handle_help_capabilities_list(skill: "AVAROSSkill", message: Message) -> None:
    """Handle capability/help request for generic + KPI intents."""

    def _execute() -> None:
        if not skill._require_intent_binding("help.capabilities.list"):
            return

        skill.speak(
            "I can report KPIs, compare and trend metrics, check anomalies, run what if simulations, "
            "and handle generic commands like turn on, turn off, and show status."
        )

    skill._safe_dispatch("handle_help_capabilities_list", _execute)


def handle_list_assets(skill: "AVAROSSkill", message: Message) -> None:
    """Handle voice request to list configured assets."""

    def _execute() -> None:
        assets = skill._get_asset_registry(force_refresh=True)
        if not assets:
            skill.speak_dialog("list.assets")
            return

        names = [
            str(asset.display_name or asset.asset_id).strip()
            for asset in assets
            if str(asset.display_name or asset.asset_id).strip()
        ]
        response = skill.response_builder.format_asset_list(names)
        skill.speak(response)

    skill._safe_dispatch("handle_list_assets", _execute)
