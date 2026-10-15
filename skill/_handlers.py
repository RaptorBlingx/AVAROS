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
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric, ScenarioParameter, WhatIfScenario
from skill.domain.results import KPIResult
from skill.services.dia_response import clarification_metadata, speak_with_evidence, speak_information
from skill.services.language import is_turkish
from skill.services.period_resolution import remove_period_reference
from skill.services.query_scope import entity_scope, is_comparison_request
from skill.services.dia_dialogue import (
    _is_explicit_capabilities_request,
    is_browser_message,
    remember_kpi_result,
    try_handle_structured_query,
)

if TYPE_CHECKING:
    from ovos_bus_client.message import Message
    from skill import AVAROSSkill


def handle_metric_query_fallback(skill: "AVAROSSkill", message: Message) -> bool:
    """Fallback: resolve metric KPI queries missed by strict intent parsing."""
    from skill._system_handlers import try_handle_read_only_request

    if try_handle_read_only_request(skill, message):
        return True

    utterance = skill._extract_utterance_text(message).lower()

    from skill._reneryo_handlers import (
        handle_reneryo_query,
        has_signed_widget_context,
        try_handle_scoped_query,
    )

    if handle_reneryo_query(skill, message, allow_semantic=False):
        return True

    if has_signed_widget_context(message) and _is_explicit_capabilities_request(
        utterance
    ):
        return try_handle_structured_query(skill, message, include_simple_kpi=True)

    if has_signed_widget_context(message) and (
        is_comparison_request(utterance) or entity_scope(utterance)[0]
    ):
        return try_handle_scoped_query(skill, message)

    # The signed Future Gen widget is a Reneryo surface. Give its constrained
    # local resolver first refusal before generic manufacturing structured
    # parsing, whose broad summary/definition forms otherwise steal natural
    # Reneryo inventory and detail questions.
    if has_signed_widget_context(message) and handle_reneryo_query(skill, message):
        return True

    if skill._is_anomaly_query(utterance):
        return _fallback_anomaly(skill, message, utterance)

    if skill._is_drift_query(utterance):
        return _fallback_drift(skill, message, utterance)

    if skill._is_forecast_query(utterance):
        return _fallback_forecast(skill, message, utterance)

    if skill._is_whatif_query(utterance):
        return _fallback_whatif(skill, message, utterance)

    if try_handle_structured_query(skill, message, include_simple_kpi=True):
        return True

    if handle_reneryo_query(skill, message, clarify_on_ambiguity=False):
        return True

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        if is_browser_message(message):
            handle_intent_failure(skill, message)
            return True
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
        speak_with_evidence(skill, response, result)
        remember_kpi_result(skill, message, result)
        return True

    skill._safe_dispatch("handle_metric_query_fallback", _execute)
    return True


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

    skill._safe_dispatch("fallback_anomaly", _execute)
    return True


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
        speak_with_evidence(skill, response, result)
        return True

    skill._safe_dispatch("fallback_drift", _execute)
    return True


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
        speak_with_evidence(skill, response, result)
        return True

    skill._safe_dispatch("fallback_forecast", _execute)
    return True


def handle_intent_failure(skill: "AVAROSSkill", message: Message) -> None:
    """Recover KPI queries from global intent-failure events."""
    sync_language = getattr(skill, "_sync_response_language", None)
    if callable(sync_language):
        sync_language(message)
    utterance = skill._extract_utterance_text(message).lower()

    from skill._reneryo_handlers import (
        handle_reneryo_query,
        has_signed_widget_context,
    )

    if handle_reneryo_query(skill, message, allow_semantic=False):
        return

    if has_signed_widget_context(message) and _is_explicit_capabilities_request(
        utterance
    ):
        if try_handle_structured_query(skill, message, include_simple_kpi=True):
            return

    if has_signed_widget_context(message) and handle_reneryo_query(skill, message):
        return

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

    if try_handle_structured_query(skill, message, include_simple_kpi=True):
        return

    if handle_reneryo_query(skill, message):
        return

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        if is_browser_message(message):
            from skill.services.language import is_turkish, normalize_language_tag

            language = normalize_language_tag(getattr(skill, "_response_language", "en-US"))
            if is_turkish(language):
                headline = (
                    "Bu isteği yapılandırılmış bir üretim sorusuyla eşleştiremedim. "
                    "Bir metrik ve ekipman adı belirtin veya neler yapabildiğimi sorun."
                )
                suggestions = ["Neler yapabilirsin?", "Hat 1 OEE değerini göster", "Fabrika özetini göster"]
            else:
                headline = (
                    "I couldn't map that to a configured manufacturing question. "
                    "Name a metric and asset, or ask what I can do."
                )
                suggestions = ["What can you do?", "Show OEE for Line 1", "Give me a factory summary"]
            metadata = clarification_metadata(headline, suggestions)
            metadata["language"] = language
            skill.speak(
                headline,
                meta={"avaros_response": metadata},
            )
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
        speak_with_evidence(skill, response, result)
        remember_kpi_result(skill, message, result)

    skill._safe_dispatch("_handle_intent_failure", _execute)


def can_answer(skill: "AVAROSSkill", message: Message) -> bool:
    """Tell OVOS fallback service when this skill can answer utterance."""
    # HiveMind's fallback ping carries the signed widget context but may not
    # include the utterance itself.  The following fallback request does.
    # Claim the authenticated widget conversation before requiring text so the
    # local semantic resolver can handle that request.
    if is_browser_message(message):
        return True

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
        try:
            scenario = _build_whatif_scenario(skill, message, utterance)
        except ValidationError as exc:
            if exc.code != "SCENARIO_QUANTITY_UNRESOLVED":
                raise
            speak_information(
                skill,
                ("Senaryo için tek bir sayısal hedef veya değişim oranı belirtin; "
                 "örneğin 'OEE yüzde 90 olursa' ya da 'OEE yüzde 10 artarsa'."
                 if is_turkish(getattr(skill, "_response_language", "en-US")) else
                 "Specify one numeric target or percentage change for the scenario; "
                 "for example, 'OEE reaches 90 percent' or 'OEE increases by 10 percent'."),
                response_type="clarification",
            )
            return True
        result = skill.dispatcher.simulate_whatif(scenario)
        response = skill.response_builder.format_whatif_result(result)
        speak_with_evidence(skill, response, result)
        return True

    skill._safe_dispatch("fallback_whatif", _execute)
    return True


def _build_whatif_scenario(
    skill: "AVAROSSkill",
    message: "Message",
    utterance: str,
) -> WhatIfScenario:
    """Parse an utterance into a bounded KPI-change scenario."""
    unsupported_process_terms = (
        "temperature",
        "pressure",
        "machine speed",
        "line speed",
        "humidity",
        "sıcaklık",
        "sicaklik",
        "basınç",
        "basinc",
        "nem oran",
    )
    if any(term in utterance for term in unsupported_process_terms):
        raise ValidationError(
            message="No configured process-to-KPI sensitivity model",
            field="scenario",
            value=utterance,
            user_message=(
                "I cannot estimate the KPI impact of that process change because no "
                "validated sensitivity model is configured. Ask a direct KPI scenario, "
                "such as 'what if energy per unit drops by 10 percent'."
            ),
        )

    metric = skill._resolve_metric_from_utterance(utterance)
    if metric is None:
        metric = CanonicalMetric.PEAK_DEMAND if "peak" in utterance else CanonicalMetric.ENERGY_PER_UNIT

    asset_id = _resolve_drift_asset(skill, message)
    target_value = _resolve_whatif_target_value(utterance)
    if target_value is not None:
        _validate_whatif_target(metric, target_value, utterance)
        parameter = ScenarioParameter(
            name="target_value",
            baseline_value=0.0,
            proposed_value=target_value,
            unit=metric.default_unit,
        )
        return WhatIfScenario(
            name=f"{metric.value}_target_{target_value:g}",
            asset_id=asset_id,
            parameters=[parameter],
            target_metric=metric,
        )

    # A mentioned quantity is never permission to substitute the default +5%.
    # Equipment numbers alone are not scenario quantities.
    quantity_text = _whatif_quantity_text(utterance)
    without_asset = quantity_text.replace("-", " ")
    names = [asset_id]
    get_assets = getattr(skill, "_get_asset_registry", None)
    assets = get_assets() if callable(get_assets) else []
    if isinstance(assets, (list, tuple)):
        for asset in assets:
            if asset.asset_id == asset_id:
                names.extend([asset.display_name, *asset.aliases])
    for name in sorted(names, key=len, reverse=True):
        normalized_name = _whatif_quantity_text(name).replace("-", " ")
        without_asset = re.sub(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", " ", without_asset)
    # Line/Hat numeric aliases identify equipment, not a scenario quantity.
    without_asset = re.sub(r"\b(?:line|hat)\s+\d+\b", " ", without_asset)
    explicit_quantity = bool(re.search(
        r"%|\b(?:percent|yüzde|yuzde|reach\w*|become\w*|hedef\w*)|(?<!\w)\d",
        remove_period_reference(without_asset),
    ))
    if explicit_quantity and (
        _whatif_change_amount(quantity_text) is None
        or re.search(r"\b(?:reach\w*|become\w*|hedef\w*|olursa|olsa|olduğunda|oldugunda)\b", quantity_text)
        or not re.search(
            r"\b(?:by|shift|increase\w*|rise\w*|rising|higher|reduce\w*|drop\w*|"
            r"decrease\w*|lower|cut|save|savings|improv\w*|worse|worsen\w*|degrad\w*|"
            r"art\w*|azal\w*|yüksel\w*|yuksel\w*|düş\w*|dus\w*|iyileş\w*|iyiles\w*)\b",
            quantity_text,
        )
    ):
        raise ValidationError(
            message="Scenario quantity could not be resolved unambiguously",
            code="SCENARIO_QUANTITY_UNRESOLVED", field="scenario quantity", value=utterance,
        )
    change_percent = _resolve_whatif_change_percent(skill, utterance, metric)
    _validate_whatif_change(metric, change_percent, utterance)
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


_BOUNDED_PERCENT_METRICS = frozenset({
    CanonicalMetric.PEAK_TARIFF_EXPOSURE,
    CanonicalMetric.SCRAP_RATE,
    CanonicalMetric.REWORK_RATE,
    CanonicalMetric.MATERIAL_EFFICIENCY,
    CanonicalMetric.RECYCLED_CONTENT,
    CanonicalMetric.SUPPLIER_DEFECT_RATE,
    CanonicalMetric.SUPPLIER_ON_TIME,
    CanonicalMetric.OEE,
})


def _validate_whatif_target(
    metric: CanonicalMetric,
    target_value: float,
    utterance: str,
) -> None:
    """Reject target values outside the physical domain of the KPI."""
    invalid = target_value < 0 or (
        metric in _BOUNDED_PERCENT_METRICS and target_value > 100
    )
    if invalid:
        upper = " between 0 and 100 percent" if metric in _BOUNDED_PERCENT_METRICS else " non-negative"
        raise ValidationError(
            message=f"Invalid target {target_value} for {metric.value}",
            field="scenario target",
            value=utterance,
            user_message=(
                f"That target is outside the valid range for {metric.display_name}. "
                f"Use a value{upper}."
            ),
        )


def _validate_whatif_change(
    metric: CanonicalMetric,
    change_percent: float,
    utterance: str,
) -> None:
    """Reject impossible reductions and unbounded scenario assumptions."""
    if change_percent <= -100:
        raise ValidationError(
            message=f"Impossible reduction {change_percent}% for {metric.value}",
            field="scenario change",
            value=utterance,
            user_message=(
                "A KPI cannot be reduced by 100 percent or more in this scenario. "
                "Use a reduction between 0 and 99.9 percent."
            ),
        )
    if abs(change_percent) > 300:
        raise ValidationError(
            message=f"Scenario change exceeds supported range: {change_percent}%",
            field="scenario change",
            value=utterance,
            user_message="That scenario change is too large. Use a value between minus 99.9 and 300 percent.",
        )


_WHATIF_NUMBER = r"[-+]?\d+(?:\.\d+)?(?!\d|[.,]\d)"


def _whatif_quantity_text(utterance: str) -> str:
    """Keep Turkish letters, decimal precision and signs in scenario quantities."""
    text = utterance.casefold().replace("i\u0307", "i")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"[^\w.%+,\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _whatif_percentages(text: str) -> list[float]:
    pattern = (rf"(?:\bpercent\b|\byüzde\b|\byuzde\b|%)\s*({_WHATIF_NUMBER})(?!\w)"
               rf"|(?<![\w.,+-])({_WHATIF_NUMBER})\s*(?:%|percent\b)")
    return [float(m.group(1) or m.group(2)) for m in re.finditer(pattern, text)]


def _resolve_whatif_target_value(utterance: str) -> float | None:
    """Resolve one absolute EN/TR target; leave ambiguity for clarification."""
    text = _whatif_quantity_text(utterance)
    percentages = _whatif_percentages(text)
    if len(percentages) > 1 or re.search(r"\b(?:or|and|veya|ve|ya da)\b|\d\s*-\s*\d", text):
        return None
    patterns = [
        rf"\b(?:to|reach|reaches|reaching|become|becomes|at)\s+({_WHATIF_NUMBER})\b(?:\s*(?:%|percent))?",
        rf"(?:\byüzde\b|\byuzde\b|%)\s*({_WHATIF_NUMBER})(?:\s*[ae])?\s+"
        r"(?:olursa|olsa|olduğunda|oldugunda|ulaşırsa|ulasirsa)\b",
        rf"(?<![\w.,+-])({_WHATIF_NUMBER})\s*%\s*(?:olursa|olsa|olduğunda|oldugunda)\b",
        rf"(?:\byüzde\b|\byuzde\b|%)\s*({_WHATIF_NUMBER})\s*[ae]\s+"
        r"(?:çıkarsa|cikarsa|yükselirse|yukselirse|düşerse|duserse|inerse|ulaşırsa|ulasirsa)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            return value if not percentages or percentages == [value] else None
    return None


def _whatif_change_amount(text: str) -> float | None:
    percentages = _whatif_percentages(text)
    if len(percentages) > 1 or re.search(r"\b(?:or|and|veya|ve|ya da)\b|\d\s*-\s*\d", text):
        return None
    if re.search(rf"(?:%|yüzde|yuzde)\s*{_WHATIF_NUMBER}\s*[ae]\b", text):
        return None
    if percentages:
        return percentages[0]
    match = re.search(rf"\bby\s+({_WHATIF_NUMBER})\b", text)
    return float(match.group(1)) if match else None


def _resolve_whatif_change_percent(
    skill: "AVAROSSkill",
    utterance: str,
    metric: CanonicalMetric,
) -> float:
    """Resolve scenario change direction and percentage from text."""
    normalized = _whatif_quantity_text(utterance)
    resolved_amount = _whatif_change_amount(normalized)
    amount = resolved_amount if resolved_amount is not None else 5.0

    if "shift" in normalized and "peak" in normalized:
        return -abs(amount)
    if re.search(r"\b(increase|increases|increased|rise|rises|rising|higher|art\w*|yüksel\w*|yuksel\w*)\b", normalized):
        return abs(amount)
    if re.search(r"\b(reduce|reduces|reduced|drop|drops|decrease|decreases|lower|cut|save|savings|azal\w*|düş\w*|dus\w*)\b", normalized):
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
