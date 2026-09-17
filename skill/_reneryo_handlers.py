"""Deterministic bilingual handlers for the Future Gen Reneryo slice."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from skill.clients.mdsp import MdspClient
from skill.clients.reneryo import ReneryoClient
from skill.domain.exceptions import AdapterError
from skill.services.conversation_state import DialogueState, message_session_id
from skill.services.dia_response import speak_information
from skill.services.futuregen import FutureGenService, default_period
from skill.services.language import is_turkish, normalize_phrase

if TYPE_CHECKING:
    from ovos_bus_client.message import Message

    from skill import AVAROSSkill


_DOMAIN_WORDS = (
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
    "finding",
    "bulgu",
    "decision support",
    "karar destek",
)


def handle_reneryo_query(skill: AVAROSSkill, message: Message) -> bool:
    """Answer a Reneryo domain query and retain only bounded entity context."""
    utterance = skill._extract_utterance_text(message)
    state = _context_state(skill, message)
    text = normalize_phrase(utterance)
    reneryo_active = getattr(skill, "_loaded_profile", "") == "reneryo"
    if not _should_handle(text, state, reneryo_active):
        return False

    def _execute() -> bool:
        service = _service(skill)
        language = _signed_language(message) or skill._response_language
        finding_follow_up = state.active_finding_id and not _has(
            text,
            "trend",
            "egilim",
            "eğilim",
            "regression",
            "regresyon",
            "meter",
            "meters",
            "sayac",
            "sayaç",
            "list metrics",
            "metrikleri listele",
        )
        if finding_follow_up or _has(
            text,
            "finding",
            "findings",
            "bulgu",
            "bulgular",
            "explain",
            "acikla",
            "açıkla",
        ):
            return _finding_response(skill, message, service, state, text, language)
        if _has(text, "regression", "regressions", "regresyon"):
            rows = skill.dispatcher._run_async(service.regressions())
            headline = (
                f"{len(rows)} kayıtlı regresyon modeli var."
                if is_turkish(language)
                else f"There are {len(rows)} saved regression models."
            )
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
                for row in rows
            ]
            speak_information(
                skill, headline, response_type="regression", evidence_rows=evidence
            )
            _remember(skill, message, state, operation="regressions")
            return True
        if _has(text, "trend", "egilim", "eğilim", "change", "degisim", "değişim"):
            period = _query_period(skill, utterance, state.period)
            trend = skill.dispatcher._run_async(
                service.trend(utterance or state.metric_name, period)
            )
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
                skill, headline, response_type="trend", evidence_rows=evidence
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
        if _has(text, "meter", "meters", "sayac", "sayaç"):
            period = _query_period(skill, utterance, state.period)
            rows = skill.dispatcher._run_async(service.meters(period))
            total = sum(row.consumption or 0 for row in rows)
            headline = (
                f"{len(rows)} sayaç var; dönem tüketimi toplamı {total:,.2f}."
                if is_turkish(language)
                else f"There are {len(rows)} meters; period consumption totals {total:,.2f}."
            )
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
                skill, headline, response_type="meters", evidence_rows=evidence
            )
            _remember(skill, message, state, operation="meters", period=period)
            return True
        rows = skill.dispatcher._run_async(service.metrics())
        headline = (
            f"Future Gen için {len(rows)} metrik kullanılabilir."
            if is_turkish(language)
            else f"Future Gen has {len(rows)} available metrics."
        )
        evidence = [
            {
                "id": r.metric_id,
                "name": r.name,
                "type": r.metric_type,
                "last_value": r.last_value,
                "observed_at": _iso(r.last_value_at),
            }
            for r in rows
        ]
        speak_information(
            skill, headline, response_type="metrics", evidence_rows=evidence
        )
        _remember(skill, message, state, operation="metrics")
        return True

    handled = skill._safe_dispatch("handle_reneryo_query", _execute)
    return bool(handled)


def _finding_response(skill, message, service, state, text, language) -> bool:
    organization_id = state.organization_id or os.environ.get(
        "FUTUREGEN_ORGANIZATION_ID", ""
    )
    finding_id = state.active_finding_id
    if finding_id:
        finding = skill.dispatcher._run_async(
            service.finding(organization_id, finding_id)
        )
        headline = _finding_headline(finding, text, language)
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
    headline = (
        f"{result.active_count} etkin bulgu var."
        if is_turkish(language)
        else f"There are {result.active_count} active findings."
    )
    evidence = [
        {
            "id": f.finding_id,
            "severity": f.severity,
            "domain": f.domain,
            "title": f.title.for_language(language),
        }
        for f in result.findings
    ]
    speak_information(skill, headline, response_type="findings", evidence_rows=evidence)
    _remember(skill, message, state, operation="findings")
    return True


def _finding_headline(finding, text: str, language: str) -> str:
    """Return a concise, deterministic answer for finding follow-ups."""
    turkish = is_turkish(language)
    if _has(text, "period", "window", "donem", "dönem", "zaman"):
        start = finding.evaluation_start.strftime("%Y-%m-%d %H:%M UTC")
        end = finding.evaluation_end.strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"Bu bulgu {start} ile {end} arasındaki değerlendirme dönemini kapsıyor."
            if turkish
            else f"This finding covers the evaluation period from {start} to {end}."
        )
    if _has(text, "entity", "affect", "varlik", "varlık", "etkiliyor"):
        label = finding.metric_name or finding.entity_type
        return (
            f"Bu bulgu {label} varlığını etkiliyor. Varlık kimliği {finding.entity_id}."
            if turkish
            else f"This finding affects {label}. Its entity ID is {finding.entity_id}."
        )
    if _has(text, "evidence", "kanit", "kanıt"):
        facts = [
            f"{key}: {value}"
            for key, value in finding.evidence.items()
            if isinstance(value, (str, int, float, bool))
        ][:4]
        detail = "; ".join(facts)
        if not detail:
            return (
                "Bu bulgu için yapılandırılmış kanıt mevcut."
                if turkish
                else "Structured evidence is available for this finding."
            )
        return (
            f"Bu bulgunun kanıtı: {detail}."
            if turkish
            else f"The evidence for this finding is: {detail}."
        )
    return f"{finding.title.for_language(language)} {finding.summary.for_language(language)}"


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


def _should_handle(text: str, state: DialogueState, reneryo_active: bool) -> bool:
    if state.active_finding_id:
        return True
    return reneryo_active and any(
        normalize_phrase(word) in text for word in _DOMAIN_WORDS
    )


_PERIOD_PATTERN = re.compile(
    r"\b(?:"
    r"past 30 days|last 30 days|last two weeks|last 2 weeks|"
    r"last month|past month|this month|last week|past week|this week|"
    r"right now|today|yesterday|latest|current|"
    r"son otuz gün|son 30 gün|son iki hafta|son 2 hafta|"
    r"geçen hafta|son hafta|bu hafta|geçen ay|son ay|bu ay|"
    r"şu anda|en güncel|bugün|dün"
    r")\b"
)


def _query_period(skill, utterance: str, current):
    """Extract a supported period phrase without sending the full query parser input."""
    match = _PERIOD_PATTERN.search(normalize_phrase(utterance))
    if match:
        parsed = skill._parse_period(match.group(0))
        if parsed:
            return parsed
    return current or default_period()


def _signed_language(message) -> str:
    """Return the language asserted by the trusted Reneryo widget session."""
    context = getattr(message, "context", {}) or {}
    session = context.get("session")
    if not isinstance(session, dict):
        return ""
    return str(session.get("lang", "") or "")


def _has(text: str, *words: str) -> bool:
    return any(normalize_phrase(word) in text for word in words)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
