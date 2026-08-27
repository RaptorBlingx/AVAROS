"""System and non-KPI intent handlers for AVAROSSkill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.dia_response import speak_information
from skill.services.language import is_turkish, metric_display_name

if TYPE_CHECKING:
    from ovos_bus_client.message import Message
    from skill import AVAROSSkill


def _is_turkish_request(skill: "AVAROSSkill") -> bool:
    """Return the language selected for the current request."""
    return is_turkish(
        getattr(skill, "_response_language", getattr(skill, "lang", "en-US"))
    )


def handle_greeting(skill: "AVAROSSkill", message: Message) -> None:
    """Handle greetings such as 'hello' or 'hey avaros'."""
    speak_information(
        skill,
        (
            "Merhaba. Yapılandırılmış üretim KPI'ları ve kanıtlarla yardımcı olabilirim."
            if _is_turkish_request(skill)
            else "Hello. I can help with configured manufacturing KPIs and evidence."
        ),
        response_type="greeting",
        suggestions=(
            ["Ne yapabilirsin?", "Kullanılabilir varlıkları listele"]
            if _is_turkish_request(skill)
            else ["What can you do?", "List the available assets"]
        ),
    )


def handle_help(skill: "AVAROSSkill", message: Message) -> None:
    """Handle generic help requests."""
    handle_help_capabilities_list(skill, message)


def handle_control_turn_on(skill: "AVAROSSkill", message: Message) -> None:
    """Explain the advisory-only control boundary without changing state."""
    speak_information(skill,
        (
            "AVAROS salt okunurdur ve ekipmanı açamaz. Onaylı ekipman kontrol "
            "sistemini ve tesis güvenlik prosedürünü kullanın."
            if _is_turkish_request(skill)
            else "AVAROS is read-only and cannot turn equipment on. "
            "Use the approved equipment control system and site safety procedure."
        ),
        response_type="read_only_boundary",
    )


def handle_control_turn_off(skill: "AVAROSSkill", message: Message) -> None:
    """Explain the advisory-only control boundary without changing state."""
    speak_information(skill,
        (
            "AVAROS salt okunurdur ve ekipmanı kapatamaz. Onaylı ekipman kontrol "
            "sistemini ve tesis güvenlik prosedürünü kullanın."
            if _is_turkish_request(skill)
            else "AVAROS is read-only and cannot turn equipment off. "
            "Use the approved equipment control system and site safety procedure."
        ),
        response_type="read_only_boundary",
    )


def handle_status_system_show(skill: "AVAROSSkill", message: Message) -> None:
    """Report actual adapter connectivity and active profile scope."""

    def _execute() -> None:
        active_profile = skill._resolve_active_profile()
        adapter = skill.dispatcher.adapter
        connection = skill.dispatcher._run_async(adapter.test_connection())
        assets = skill._get_asset_registry(force_refresh=True)
        metrics = adapter.get_supported_metrics()
        prevention_available = getattr(skill.dispatcher, "_prevention_client", None) is not None
        health = "connected" if connection.success else "not connected"
        freshness = _status_freshness_clause(skill, assets, metrics)
        if _is_turkish_request(skill):
            headline = (
                f"Etkin veri kaynağı {'bağlı' if connection.success else 'bağlı değil'}. "
                f"Profil: {active_profile}. Yapılandırılmış kapsam: {len(assets)} varlık ve "
                f"{len(metrics)} metrik. PREVENTION analitiği "
                f"{'kullanılabilir' if prevention_available else 'kullanılamıyor'}."
            )
        else:
            headline = (
                f"The active data source is {health}. Profile: {active_profile}. "
                f"Configured scope: {len(assets)} assets and {len(metrics)} metrics. "
                f"{freshness} "
                f"PREVENTION analytics is {'available' if prevention_available else 'unavailable'}. "
                f"Connection check: {connection.message}"
            )
        speak_information(
            skill,
            headline,
            response_type="system_status",
            evidence_rows=[{
                "profile": active_profile,
                "connection": health,
                "asset_count": len(assets),
                "metric_count": len(metrics),
                "prevention_available": prevention_available,
            }],
        )

    skill._safe_dispatch("handle_status_system_show", _execute)


def _status_freshness_clause(skill: "AVAROSSkill", assets, metrics) -> str:
    """Return an operator-facing timestamp from one live mapped observation."""
    if not assets or not metrics:
        return "No mapped observation is available for a freshness check."
    for asset in assets:
        asset_id = asset.asset_id
        for metric in metrics:
            try:
                result = skill.dispatcher.get_kpi(
                    metric,
                    asset_id,
                    TimePeriod.latest(),
                )
            except Exception:
                continue
            observed = result.source_observed_at
            if observed is None:
                return "The source did not provide an observation timestamp."
            quality = result.coverage_status or "complete"
            return f"Latest checked observation: {observed.isoformat()} ({quality})."
    return "No mapped observation could be read for a freshness check."


def handle_status_profile_show(skill: "AVAROSSkill", message: Message) -> None:
    """Handle profile/config status request."""

    def _execute() -> None:
        profile = skill._resolve_active_profile()
        platform = "unconfigured"
        if skill.settings_service is not None:
            config = skill.settings_service.get_profile(profile)
            if config is not None:
                platform = config.platform_type

        speak_information(
            skill,
            (
                f"Geçerli profil {profile}; platform {platform}."
                if _is_turkish_request(skill)
                else f"Current profile is {profile} on platform {platform}."
            ),
            response_type="profile_status",
            evidence_rows=[{"profile": profile, "platform": platform}],
        )

    skill._safe_dispatch("handle_status_profile_show", _execute)


def handle_help_capabilities_list(skill: "AVAROSSkill", message: Message) -> None:
    """Handle capability help using mapped metrics and active profile intents."""

    def _execute() -> None:
        from skill.services.capability_manifest import build_capability_manifest

        manifest = build_capability_manifest(
            skill.settings_service,
            getattr(skill.dispatcher, "adapter", None),
        )
        metric_names = [
            metric_display_name(
                CanonicalMetric.from_string(item["id"]),
                getattr(
                    skill,
                    "_response_language",
                    getattr(skill, "lang", "en-US"),
                ),
            )
            for item in manifest["metrics"]
        ]
        if _is_turkish_request(skill):
            metric_part = ", ".join(metric_names[:5]) if metric_names else "yapılandırılmış KPI'lar"
            more = len(metric_names) - 5
            if more > 0:
                metric_part += f" ve {more} metrik daha"
            speak_information(
                skill,
                f"{metric_part} raporlayabilir; enerji karşılaştırabilir, eğilimleri ve "
                "sistem durumunu gösterebilirim. Salt okunurum ve ekipmanı kontrol edemem.",
                response_type="capabilities",
            )
            return
        capabilities: list[str] = []
        if metric_names:
            metric_part = ", ".join(metric_names[:5])
            if len(metric_names) > 5:
                metric_part += f", and {len(metric_names) - 5} more"
            capabilities.append(f"report KPIs like {metric_part}")
        else:
            capabilities.append("report configured KPIs")

        if _intent_is_active(skill, "compare.energy"):
            capabilities.append("compare energy")
        anomaly_active = _intent_is_active(skill, "anomaly.production.check")
        if anomaly_active:
            capabilities.append("check production anomalies")
        if (
            _intent_is_active(skill, "trend.energy")
            or _intent_is_active(skill, "trend.scrap")
        ):
            capabilities.append("show trends")
        if _intent_is_active(skill, "status.system.show"):
            capabilities.append("show system status")
        if _intent_is_active(skill, "status.profile.show"):
            capabilities.append("report the active profile")

        analytics = ""
        if anomaly_active:
            analytics = (
                " PREVENTION anomaly analytics is available."
                if manifest["prevention"]["available"]
                else " PREVENTION anomaly, drift, and forecast analytics are unavailable."
            )
        speak_information(
            skill,
            f"I can {', '.join(capabilities)}.{analytics} "
            "I am read-only and cannot control equipment.",
            response_type="capabilities",
        )

    skill._safe_dispatch("handle_help_capabilities_list", _execute)


def _get_mapped_metric_names(skill: "AVAROSSkill") -> list[str]:
    """Return display names of metrics mapped in the active profile."""
    adapter = getattr(getattr(skill, "dispatcher", None), "adapter", None)
    if adapter is None:
        return []
    try:
        metrics = adapter.get_supported_metrics()
        if not isinstance(metrics, list):
            return []
        return [m.display_name for m in metrics if hasattr(m, "display_name")]
    except Exception:
        return []


def _intent_is_active(skill: "AVAROSSkill", intent_name: str) -> bool:
    """Return profile-scoped activation state, failing open for legacy setup."""
    settings_service = getattr(skill, "settings_service", None)
    if settings_service is None:
        return True
    try:
        return bool(settings_service.is_intent_active(intent_name))
    except Exception:
        return True


def handle_list_assets(skill: "AVAROSSkill", message: Message) -> None:
    """Handle voice request to list configured assets."""
    # Broad analytics wording can overlap Padatious' "all assets" list
    # patterns. Give the deterministic operation parser first refusal.
    from skill.services.dia_dialogue import try_handle_structured_query

    if try_handle_structured_query(skill, message):
        return

    def _execute() -> None:
        assets = skill._get_asset_registry(force_refresh=True)
        if not assets:
            speak_information(
                skill,
                (
                    "Etkin profilde yapılandırılmış varlık yok."
                    if _is_turkish_request(skill)
                    else "No assets are configured in the active profile."
                ),
                response_type="asset_list",
                warnings=[
                    "Etkin profilde yapılandırılmış varlık yok."
                    if _is_turkish_request(skill)
                    else "The active profile has no configured assets."
                ],
            )
            return

        names = [
            str(asset.display_name or asset.asset_id).strip()
            for asset in assets
            if str(asset.display_name or asset.asset_id).strip()
        ]
        response = skill.response_builder.format_asset_list(names)
        speak_information(
            skill,
            response,
            response_type="asset_list",
            evidence_rows=[{"asset": name} for name in names],
        )

    skill._safe_dispatch("handle_list_assets", _execute)
