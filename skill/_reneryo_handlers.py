"""Deterministic bilingual handlers for the Future Gen Reneryo slice."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from skill.clients.mdsp import MdspClient
from skill.clients.reneryo import ReneryoClient
from skill.domain.exceptions import AdapterError, ValidationError
from skill.services.conversation_state import DialogueState, message_session_id
from skill.services.dia_response import speak_information
from skill.services.finding_explanation import finding_headline
from skill.services.futuregen import FutureGenService, default_period, match_metric
from skill.services.futuregen_responses import (
    finding_inventory_headline,
    meter_inventory_headline,
    metric_detail_headline,
    metric_inventory_headline,
    regression_detail_headline,
    regression_inventory_headline,
)
from skill.services.language import is_turkish, normalize_phrase
from skill.services.period_resolution import extract_period_phrase
from skill.services.semantic_resolver import SemanticAction, SemanticResolution

if TYPE_CHECKING:
    from ovos_bus_client.message import Message

    from skill import AVAROSSkill


_FINDING_ACTIONS = frozenset(
    {
        SemanticAction.FINDING_EXPLAIN,
        SemanticAction.FINDING_TRIGGER,
        SemanticAction.FINDING_EVIDENCE,
        SemanticAction.FINDING_PERIOD,
        SemanticAction.FINDING_ENTITY,
    }
)


def handle_reneryo_query(
    skill: AVAROSSkill,
    message: Message,
    *,
    allow_semantic: bool = True,
    clarify_on_ambiguity: bool = True,
    semantic_resolution: SemanticResolution | None = None,
) -> bool:
    """Route deterministic intents first, then use local semantic fallback."""
    utterance = skill._extract_utterance_text(message)
    state = _context_state(skill, message)
    text = normalize_phrase(utterance)
    reneryo_active = getattr(skill, "_loaded_profile", "") == "reneryo"
    if not text or not reneryo_active:
        return False
    language = _conversation_language(
        utterance, state, message, skill._response_language
    )
    state = replace(state, language=language)
    _update_message_language(message, language)

    action = _deterministic_action(text, state)
    resolution: SemanticResolution | None = semantic_resolution
    if action is None:
        if not allow_semantic:
            return False
        resolver = getattr(skill, "_semantic_resolver", None)
        if resolution is None and resolver is not None:
            resolution = resolver.resolve(
                utterance,
                state=state,
                language=language,
            )
            action = resolution.action
        if action is None:
            grounded_metric = _ground_metric_reference(skill, utterance)
            if grounded_metric is not None:
                action = (
                    SemanticAction.TREND_SHOW
                    if _looks_like_trend(text)
                    else SemanticAction.METRIC_DETAIL
                )
                slots = {"metric_name": grounded_metric.name}
                period = extract_period_phrase(utterance)
                if period:
                    slots["period"] = period
                resolution = SemanticResolution(
                    action=action,
                    language=language,
                    confidence=1.0,
                    margin=1.0,
                    slots=slots,
                    reason="grounded_metric",
                )
        if action is None:
            if not clarify_on_ambiguity:
                return False
            _semantic_clarification(skill, language)
            _remember(skill, message, state, operation="clarification")
            return True

    def _execute() -> bool:
        service = _service(skill)
        if action in _FINDING_ACTIONS or action is SemanticAction.FINDINGS_LIST:
            return _finding_response(
                skill,
                message,
                service,
                state,
                text,
                language,
                action,
            )
        if action in {
            SemanticAction.REGRESSIONS_LIST,
            SemanticAction.REGRESSION_DETAIL,
        }:
            rows = skill.dispatcher._run_async(service.regressions())
            selected = _select_regression(rows, text, resolution, state)
            if action is SemanticAction.REGRESSION_DETAIL and selected is None:
                _regression_clarification(skill, rows, language)
                _remember(skill, message, state, operation="regression_clarification")
                return True
            headline = (
                regression_detail_headline(selected, language)
                if selected is not None
                else regression_inventory_headline(rows, language)
            )
            response_rows = [selected] if selected is not None else rows
            evidence = [
                {
                    "id": row.regression_id,
                    "type": row.regression_type,
                    "drivers": list(row.driver_names),
                    "period": row.period,
                    "r_squared": row.r_squared,
                    "rmse": row.rmse,
                    "training_period": f"{row.train_start.date()} – {row.train_end.date()}",
                }
                for row in response_rows
            ]
            speak_information(
                skill,
                headline,
                language=language,
                response_type="regression",
                evidence_rows=evidence,
            )
            _remember(
                skill,
                message,
                state,
                operation="regression_detail" if selected is not None else "regressions",
                entity_id=selected.regression_id if selected is not None else state.entity_id,
            )
            return True
        if action is SemanticAction.TREND_SHOW:
            semantic_period = resolution.slots.get("period", "") if resolution else ""
            period = _query_period(skill, utterance, state.period, semantic_period)
            metric_query = utterance
            context_metric = (
                resolution.slots.get("context_metric", "") if resolution else ""
            ) or state.metric_name
            try:
                trend = skill.dispatcher._run_async(service.trend(metric_query, period))
            except (AdapterError, ValidationError):
                if not context_metric:
                    raise
                trend = skill.dispatcher._run_async(service.trend(context_metric, period))
            direction = {
                "increasing": "artıyor",
                "decreasing": "azalıyor",
                "stable": "sabit",
            }.get(trend.direction, trend.direction)
            if is_turkish(language):
                headline = f"{trend.metric.name}, {trend.period_label} döneminde %{abs(trend.change_percent):.1f} oranında {direction}."
            else:
                headline = f"{trend.metric.name} is {trend.direction} by {abs(trend.change_percent):.1f}% over {trend.period_label}."
            evidence = [
                {
                    "time": p.timestamp.isoformat(),
                    "value": p.value,
                    "samples": p.sample_count,
                }
                for p in trend.points
            ]
            speak_information(
                skill,
                headline,
                language=language,
                response_type="trend",
                evidence_rows=evidence,
            )
            _remember(
                skill,
                message,
                state,
                operation="trend",
                period=period,
                metric_name=trend.metric.name,
            )
            return True
        if action is SemanticAction.METERS_LIST:
            semantic_period = resolution.slots.get("period", "") if resolution else ""
            period = _query_period(skill, utterance, state.period, semantic_period)
            rows = skill.dispatcher._run_async(service.meters(period))
            headline = meter_inventory_headline(rows, period, language)
            evidence = [
                {
                    "id": r.meter_id,
                    "name": r.name,
                    "resource": r.energy_resource,
                    "consumption": r.consumption,
                }
                for r in rows
            ]
            speak_information(
                skill,
                headline,
                language=language,
                response_type="meters",
                evidence_rows=evidence,
            )
            _remember(skill, message, state, operation="meters", period=period)
            return True
        if action not in {SemanticAction.METRICS_LIST, SemanticAction.METRIC_DETAIL}:
            _semantic_clarification(skill, language)
            return True
        rows = skill.dispatcher._run_async(service.metrics())
        selected_metric = None
        if action is SemanticAction.METRIC_DETAIL:
            expected = (
                resolution.slots.get("metric_name", "")
                if resolution is not None
                else ""
            ) or state.metric_name
            selected_metric = match_metric(expected or text, rows)
        if action is SemanticAction.METRIC_DETAIL and selected_metric is None:
            _metric_clarification(skill, rows, language)
            _remember(skill, message, state, operation="metric_clarification")
            return True
        response_rows = [selected_metric] if selected_metric is not None else rows
        headline = (
            metric_detail_headline(selected_metric, language)
            if selected_metric is not None
            else metric_inventory_headline(rows, language)
        )
        evidence = [
            {
                "id": r.metric_id,
                "name": r.name,
                "type": r.metric_type,
                "last_value": r.last_value,
                "observed_at": _iso(r.last_value_at),
            }
            for r in response_rows
        ]
        speak_information(
            skill,
            headline,
            language=language,
            response_type="metrics",
            evidence_rows=evidence,
        )
        _remember(
            skill,
            message,
            state,
            operation="metric_detail" if selected_metric is not None else "metrics",
            metric_name=(
                selected_metric.name if selected_metric is not None else state.metric_name
            ),
        )
        return True

    handled = skill._safe_dispatch("handle_reneryo_query", _execute)
    return bool(handled)


_ARBITRATABLE_LEGACY_INTENTS = frozenset(
    {"help", "help.capabilities.list", "list.assets"}
)
_SEMANTIC_OVERRIDE_MARGIN = 0.008


def try_arbitrate_legacy_intent(
    skill: AVAROSSkill,
    message: Message,
    intent_name: str,
) -> bool:
    """Let constrained Reneryo semantics arbitrate broad legacy matches.

    Exact registered phrases stay on their deterministic handler. Arbitration
    is limited to signed Reneryo sessions and the semantic action allow-list;
    execution still goes through the existing scoped Reneryo/MDSP clients.
    """
    if getattr(skill, "_loaded_profile", "") != "reneryo":
        return False
    if not (
        intent_name in _ARBITRATABLE_LEGACY_INTENTS
        or intent_name.startswith("kpi.")
    ):
        return False
    context = getattr(message, "context", {}) or {}
    signed = context.get("reneryo_context")
    if not isinstance(signed, dict) or not signed.get("organization_id"):
        return False

    utterance = skill._extract_utterance_text(message)
    text = normalize_phrase(utterance)
    if not text or _matches_registered_utterance(intent_name, text):
        return False

    state = _context_state(skill, message)
    language = _conversation_language(
        utterance, state, message, skill._response_language
    )
    state = replace(state, language=language)
    if _deterministic_action(text, state) is not None:
        return handle_reneryo_query(skill, message, allow_semantic=False)

    resolver = getattr(skill, "_semantic_resolver", None)
    if resolver is None:
        return False
    resolution = resolver.resolve(utterance, state=state, language=language)
    if not resolution.accepted:
        _update_message_language(message, language)
        _semantic_clarification(skill, language)
        _remember(skill, message, state, operation="clarification")
        return True

    legacy_confidence = _legacy_intent_confidence(message)
    required_margin = (
        _SEMANTIC_OVERRIDE_MARGIN if legacy_confidence >= 0.85 else 0.004
    )
    if resolution.margin < required_margin:
        _update_message_language(message, language)
        _semantic_clarification(skill, language)
        _remember(skill, message, state, operation="clarification")
        return True
    return handle_reneryo_query(
        skill,
        message,
        semantic_resolution=resolution,
    )


def _legacy_intent_confidence(message) -> float:
    data = getattr(message, "data", {}) or {}
    intent = data.get("__intent__")
    raw = intent.get("confidence", 0.0) if isinstance(intent, dict) else 0.0
    try:
        return min(max(float(raw), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


@cache
def _registered_utterance_patterns(intent_name: str) -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    locale_root = Path(__file__).resolve().parent / "locale"
    for locale in ("en-us", "tr-tr"):
        path = locale_root / locale / f"{intent_name}.intent"
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"(\{[^}]+\})", line)
            expression = "".join(
                r".+?" if part.startswith("{") else re.escape(normalize_phrase(part))
                for part in parts
                if part
            )
            patterns.append(re.compile(rf"^{expression}$"))
    return tuple(patterns)


def _matches_registered_utterance(intent_name: str, normalized: str) -> bool:
    return any(
        pattern.fullmatch(normalized)
        for pattern in _registered_utterance_patterns(intent_name)
    )


def _finding_response(skill, message, service, state, text, language, action) -> bool:
    organization_id = state.organization_id or os.environ.get(
        "FUTUREGEN_ORGANIZATION_ID", ""
    )
    finding_id = (
        ""
        if action is SemanticAction.FINDINGS_LIST or _is_finding_list(text)
        else state.active_finding_id
    )
    if finding_id:
        finding = skill.dispatcher._run_async(
            service.finding(organization_id, finding_id)
        )
        headline = finding_headline(finding, text, language, action=action.value)
        evidence = [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "domain": finding.domain,
                "period_start": finding.evaluation_start.isoformat(),
                "period_end": finding.evaluation_end.isoformat(),
                **finding.evidence,
            }
        ]
        assumptions = [item.for_language(language) for item in finding.assumptions]
        speak_information(
            skill,
            headline,
            language=language,
            response_type="finding",
            evidence_rows=evidence,
            warnings=assumptions,
        )
        _remember(
            skill,
            message,
            state,
            operation="finding",
            active_finding_id=finding.finding_id,
            entity_id=finding.entity_id,
            metric_name=finding.metric_name,
        )
        return True
    result = skill.dispatcher._run_async(service.findings(organization_id))
    headline = finding_inventory_headline(result, language)
    evidence = [
        {
            "id": f.finding_id,
            "severity": f.severity,
            "domain": f.domain,
            "title": f.title.for_language(language),
        }
        for f in result.findings
    ]
    speak_information(
        skill,
        headline,
        language=language,
        response_type="findings",
        evidence_rows=evidence,
    )
    _remember(skill, message, state, operation="findings")
    return True


def _deterministic_action(text: str, state: DialogueState) -> SemanticAction | None:
    """Map established lexical forms without invoking the semantic model."""
    if _is_finding_list(text):
        return SemanticAction.FINDINGS_LIST
    if (
        state.operation == "regression_detail"
        and not _has(
            text,
            "finding",
            "bulgu",
            "metric",
            "metrik",
            "meter",
            "sayac",
            "sayaç",
        )
        and _has(
            text,
            "model",
            "fit",
            "quality",
            "error",
            "driver",
            "training",
            "its",
            "regresyon",
            "uyum",
            "kalite",
            "hata",
            "surucu",
            "sürücü",
            "egitim",
            "eğitim",
            "bunun",
        )
    ):
        return SemanticAction.REGRESSION_DETAIL
    if state.metric_name and state.operation in {"metric_detail", "trend"}:
        if _looks_like_trend(text):
            return SemanticAction.TREND_SHOW
        if _has(
            text,
            "this metric",
            "this indicator",
            "related metric",
            "related indicator",
            "bu metrik",
            "bu gosterge",
            "bu gösterge",
            "ilgili metrik",
            "ilgili gosterge",
            "ilgili gösterge",
        ):
            return SemanticAction.METRIC_DETAIL
    if state.active_finding_id:
        if state.metric_name and _looks_like_trend(text):
            return SemanticAction.TREND_SHOW
        if state.metric_name and _has(
            text,
            "related metric",
            "related indicator",
            "this metric",
            "this indicator",
            "ilgili metrik",
            "bu metrik",
            "ilgili gösterge",
            "bu gösterge",
        ):
            return SemanticAction.METRIC_DETAIL
        if _has(
            text,
            "evidence",
            "supporting fact",
            "facts support",
            "data justify",
            "kanit",
            "kanıt",
            "dayanak",
            "destekleyen veri",
        ):
            return SemanticAction.FINDING_EVIDENCE
        if _has(
            text,
            "period",
            "window",
            "when",
            "date",
            "donem",
            "dönem",
            "zaman",
            "tarih",
        ):
            return SemanticAction.FINDING_PERIOD
        if _has(text, "entity", "affect", "varlik", "varlık", "etkiliyor"):
            return SemanticAction.FINDING_ENTITY
        if _has(
            text,
            "why",
            "trigger",
            "condition",
            "neden",
            "tetik",
            "kosul",
            "koşul",
            "olustu",
            "oluştu",
        ):
            return SemanticAction.FINDING_TRIGGER
        explicit_domain_switch = _has(
            text,
            "meter",
            "sayac",
            "sayaç",
            "metric",
            "metrik",
            "trend",
            "egilim",
            "eğilim",
            "regression",
            "regresyon",
        )
        if _has(text, "finding", "bulgu"):
            return SemanticAction.FINDING_EXPLAIN
        if _has(
            text, "alert", "issue", "warning", "uyari", "uyarı", "sorun"
        ) and _has(
            text,
            "understand",
            "interpret",
            "summarize",
            "anlam",
            "yorumla",
            "ozet",
            "özet",
        ):
            return SemanticAction.FINDING_EXPLAIN
        if not explicit_domain_switch and _has(text, "explain", "acikla", "açıkla"):
            return SemanticAction.FINDING_EXPLAIN
    if _has(
        text,
        "meter",
        "meters",
        "measuring device",
        "measurement device",
        "measuring instrument",
        "sayac",
        "sayaç",
        "olcum cihaz",
        "ölçüm cihaz",
        "olcum donanim",
        "ölçüm donanım",
    ):
        return SemanticAction.METERS_LIST
    if _has(text, "model", "models", "modeller") and _has(
        text,
        "saved",
        "available",
        "predictive",
        "statistical",
        "inventory",
        "list",
        "kayitli",
        "kayıtlı",
        "mevcut",
        "tahmin",
        "istatistik",
        "liste",
        "envanter",
    ):
        return SemanticAction.REGRESSIONS_LIST
    if _has(text, "regression", "regressions", "regresyon"):
        if _has(
            text,
            "daily",
            "monthly",
            "gunluk",
            "günlük",
            "aylik",
            "aylık",
            "driver",
            "surucu",
            "sürücü",
            "fit",
            "error",
            "uyum",
            "hata",
            "training",
            "egitim",
            "eğitim",
        ):
            return SemanticAction.REGRESSION_DETAIL
        return SemanticAction.REGRESSIONS_LIST
    if _looks_like_trend(text):
        return SemanticAction.TREND_SHOW
    if _has(text, "metric", "metrics", "metrik"):
        return SemanticAction.METRICS_LIST
    if _has(text, "findings", "bulgular", "decision support", "karar destek"):
        return SemanticAction.FINDINGS_LIST
    return None


def _semantic_clarification(skill, language: str) -> None:
    if is_turkish(language):
        headline = (
            "Bu isteği güvenle eşleştiremedim. Bulguyu açıklamamı, kanıtı veya "
            "dönemi göstermemi ya da metrik, sayaç, eğilim veya regresyonları "
            "listelememi ister misiniz?"
        )
        suggestions = [
            "Bu bulgunun nedenini açıkla",
            "Kanıtları göster",
            "Metrikleri listele",
        ]
    else:
        headline = (
            "I could not map that request confidently. Would you like the finding "
            "explained, its evidence or period shown, or metrics, meters, trends, "
            "or regressions listed?"
        )
        suggestions = [
            "Explain this finding",
            "Show its evidence",
            "List the metrics",
        ]
    speak_information(
        skill,
        headline,
        language=language,
        response_type="clarification",
        suggestions=suggestions,
    )


def _metric_clarification(skill, rows, language: str) -> None:
    names = [row.name for row in rows[:3]]
    if is_turkish(language):
        headline = "Hangi Reneryo metriğini kastediyorsunuz? Metrik adını belirtin."
        suggestions = [f"{name} metriğini açıkla" for name in names]
    else:
        headline = "Which Reneryo metric do you mean? Please name the metric."
        suggestions = [f"Explain the {name} metric" for name in names]
    speak_information(
        skill,
        headline,
        language=language,
        response_type="clarification",
        suggestions=suggestions,
    )


def _select_regression(
    rows, text: str, resolution: SemanticResolution | None, state: DialogueState
):
    period = resolution.slots.get("regression_period", "") if resolution else ""
    period = period or _regression_period_hint(text)
    if period:
        matches = [row for row in rows if row.period.upper() == period]
        if len(matches) == 1:
            return matches[0]
    if state.operation == "regression_detail" and state.entity_id:
        contextual = [row for row in rows if row.regression_id == state.entity_id]
        if len(contextual) == 1:
            return contextual[0]
    normalized = normalize_phrase(text)
    matches = [
        row
        for row in rows
        if any(normalize_phrase(name) in normalized for name in row.driver_names if name)
    ]
    return matches[0] if len(matches) == 1 else None


def _regression_period_hint(text: str) -> str:
    if _has(text, "daily", "gunluk", "günlük"):
        return "DAILY"
    if _has(text, "monthly", "aylik", "aylık"):
        return "MONTHLY"
    return ""


def _regression_clarification(skill, rows, language: str) -> None:
    periods = sorted({row.period.lower() for row in rows})
    if is_turkish(language):
        headline = "Hangi regresyon modelini kastediyorsunuz? Dönemini veya sürücüsünü belirtin."
        suggestions = [f"{period} regresyonunu açıkla" for period in periods]
    else:
        headline = "Which regression model do you mean? Name its period or driver."
        suggestions = [f"Explain the {period} regression" for period in periods]
    speak_information(
        skill,
        headline,
        language=language,
        response_type="clarification",
        suggestions=suggestions,
    )


def _context_state(skill, message) -> DialogueState:
    session_id = message_session_id(message)
    current = skill._dialogue_state_store.get(session_id) or DialogueState()
    context = getattr(message, "context", {}) or {}
    signed = context.get("reneryo_context")
    if not isinstance(signed, dict):
        return current
    return replace(
        current,
        organization_id=str(
            signed.get("organization_id", "") or current.organization_id
        ),
        active_finding_id=str(
            signed.get("finding_id", "") or current.active_finding_id
        ),
        entity_id=str(signed.get("entity_id", "") or current.entity_id),
        metric_name=str(signed.get("metric_name", "") or current.metric_name),
    )


def _remember(skill, message, state, **changes) -> None:
    skill._dialogue_state_store.put(
        message_session_id(message), replace(state, **changes)
    )


def _service(skill) -> FutureGenService:
    service = getattr(skill, "_futuregen_service", None)
    if service is not None:
        return service
    reneryo = ReneryoClient.from_runtime(skill.settings_service)
    try:
        mdsp = MdspClient.from_environment()
    except AdapterError:
        mdsp = None
    service = FutureGenService(reneryo, mdsp)
    skill._futuregen_service = service
    return service


def _is_finding_list(text: str) -> bool:
    return _has(
        text,
        "list findings",
        "list decision support findings",
        "findings list",
        "bulgulari listele",
        "bulguları listele",
        "bulgular",
    )


def _query_period(skill, utterance: str, current, semantic_period: str = ""):
    """Extract a supported period phrase without sending the full query parser input."""
    phrase = extract_period_phrase(utterance)
    if phrase:
        parsed = skill._parse_period(phrase)
        if parsed:
            return parsed
    if semantic_period:
        parsed = skill._parse_period(semantic_period)
        if parsed:
            return parsed
    return current or default_period()


def has_signed_widget_context(message) -> bool:
    """Return whether the trusted proxy injected a scoped Reneryo session."""
    context = getattr(message, "context", {}) or {}
    signed = context.get("reneryo_context")
    return (
        context.get("reneryo_widget_session_validated") is True
        and isinstance(signed, dict)
        and bool(signed.get("organization_id"))
    )


def _ground_metric_reference(skill, utterance: str):
    """Resolve named/aliased metrics only from the live Reneryo inventory."""
    text = normalize_phrase(utterance)
    if _has(
        text,
        "meter",
        "measuring device",
        "measurement device",
        "measuring instrument",
        "sayac",
        "sayaç",
        "olcum cihaz",
        "ölçüm cihaz",
        "olcum donanim",
        "ölçüm donanım",
    ):
        return None
    try:
        rows = skill.dispatcher._run_async(_service(skill).metrics())
    except (AdapterError, ValidationError):
        return None
    return match_metric(utterance, rows)


def _looks_like_trend(text: str) -> bool:
    return _has(
        text,
        "trend",
        "evolve",
        "move over",
        "changed",
        "change over",
        "egilim",
        "eğilim",
        "seyir",
        "degis",
        "değiş",
    )


def _signed_language(message) -> str:
    """Return the language asserted by the trusted Reneryo widget session."""
    context = getattr(message, "context", {}) or {}
    reneryo = context.get("reneryo_context")
    if isinstance(reneryo, dict) and reneryo.get("language"):
        return str(reneryo["language"])
    session = context.get("session")
    if not isinstance(session, dict):
        return ""
    return str(session.get("lang", "") or "")


_TURKISH_LANGUAGE_WORDS = {
    "bu",
    "bulgu",
    "bulguyu",
    "bulgular",
    "hangi",
    "neden",
    "oluştu",
    "kanıt",
    "destekliyor",
    "dönem",
    "kapsıyor",
    "varlığı",
    "etkiliyor",
    "göster",
    "listele",
    "metriklerini",
    "regresyon",
}
_ENGLISH_LANGUAGE_WORDS = {
    "this",
    "finding",
    "findings",
    "what",
    "why",
    "which",
    "explain",
    "evidence",
    "period",
    "entity",
    "show",
    "list",
    "trend",
    "regression",
}


def _conversation_language(utterance, state, message, fallback: str) -> str:
    """Prefer lexical detection, then the trusted current-turn locale and memory."""
    detected = _utterance_language(utterance)
    return (
        detected or _signed_language(message) or state.language or fallback or "en-US"
    )


def _utterance_language(utterance: str) -> str:
    text = normalize_phrase(utterance)
    words = set(text.split())
    turkish_score = len(words & _TURKISH_LANGUAGE_WORDS)
    english_score = len(words & _ENGLISH_LANGUAGE_WORDS)
    if any(character in text for character in "çğıöşü"):
        turkish_score += 2
    if turkish_score > english_score:
        return "tr-TR"
    if english_score > turkish_score:
        return "en-US"
    return ""


def _update_message_language(message, language: str) -> None:
    """Expose the active turn language to later handlers and response metadata."""
    context = getattr(message, "context", None)
    if not isinstance(context, dict):
        return
    reneryo = context.get("reneryo_context")
    if isinstance(reneryo, dict):
        reneryo["language"] = language
    session = context.get("session")
    if isinstance(session, dict):
        session["lang"] = language


def _has(text: str, *words: str) -> bool:
    return any(normalize_phrase(word) in text for word in words)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
