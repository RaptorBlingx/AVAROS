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
from skill.domain.exceptions import AdapterError, AVAROSError, ValidationError
from skill.services.conversation_state import DialogueState, message_session_id
from skill.services.dia_response import speak_information
from skill.services.factory_questions import (
    answer_factory_question,
    classify_factory_question,
    cost_limitation_headline,
    is_cost_request,
    is_historical_change_question,
)
from skill.services.finding_collection import (
    FindingFilters,
    collection_headline,
    evaluation_headline,
    filters_for,
    is_collection_request,
    is_evaluation_request,
    is_review_question,
    is_finding_evidence_question,
    selection_index,
    selection_requested,
)
from skill.services.finding_explanation import finding_headline
from skill.services.finding_next_review import next_review_headline
from skill.services.futuregen import FutureGenService, default_period, match_metric
from skill.services.futuregen_responses import (
    meter_inventory_headline,
    metric_detail_headline,
    metric_inventory_headline,
    regression_detail_headline,
    regression_inventory_headline,
)
from skill.services.language import is_turkish, normalize_phrase, period_display_name
from skill.services.period_resolution import (
    extract_period_phrase, named_month_reference, remove_period_reference,
    unsupported_period_reference, unsupported_time_precision,
)
from skill.services.request_correction import affirmative_request
from skill.services.query_scope import entity_scope, is_comparison_request, is_negated_comparison
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
        SemanticAction.FINDING_NEXT_REVIEW,
        SemanticAction.FINDING_NEXT_REVIEW_WHY,
        SemanticAction.FINDING_OWNER,
        SemanticAction.FINDING_CAN_ACT,
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

    from skill._system_handlers import try_handle_read_only_request

    if try_handle_read_only_request(skill, message):
        return True

    original_utterance = utterance
    utterance = affirmative_request(utterance)
    if utterance is None:
        speak_information(
            skill,
            ("Hariç tuttuğunuz istek yerine hangi işlemi istediğinizi belirtin."
             if is_turkish(language)
             else "Please specify the operation you want instead of the excluded request."),
            language=language, response_type="clarification",
        )
        return True
    corrected = utterance != original_utterance
    text = normalize_phrase(utterance)

    if unsupported_time_precision(utterance):
        speak_information(
            skill,
            (
                "Saat düzeyindeki sorgular desteklenmiyor. Bir gün, ay veya tarih aralığı belirtin; "
                "istenen saat yerine en güncel ölçümü kullanmadım."
                if is_turkish(language)
                else "Time-of-day queries are not supported. Specify a day, month, or date range; "
                "I have not substituted the latest measurement for the requested time."
            ),
            language=language,
            response_type="clarification",
        )
        _remember(skill, message, state, pending_clarification="time precision")
        return True

    # Bare named-month follow-ups are resolved using the factory dialogue's
    # retained year. All other unsupported explicit periods must stop routing.
    retained_month = (
        named_month_reference(utterance) and not re.search(r"\b\d{4}\b", text)
        and state.operation in {"factory_history", "trend"} and state.period
    )
    if unsupported_period_reference(utterance) and not retained_month:
        _period_clarification(skill, language)
        return True

    if is_cost_request(utterance):
        speak_information(skill, cost_limitation_headline(language),
                          language=language, response_type="unavailable")
        return True

    # "Previous month" after a dated answer may mean the calendar month or
    # the month before the displayed window (including a disclosed fallback).
    # Ask before any source read and leave the grounded period unchanged.
    if state.period and state.operation and re.fullmatch(
        r"(?:(?:and|what about|how about|peki|ya) )?(?:the )?"
        r"(?:previous month|önceki ay|onceki ay)(?: nasıldı| nasildi)?", text
    ):
        speak_information(
            skill,
            ("Önceki ay derken geçen takvim ayını mı, gösterdiğim dönemden önceki ayı mı kastediyorsunuz? Ay ve yılı belirtin."
             if is_turkish(language) else
             "Do you mean the previous calendar month or the month before the period I showed? Please specify the month and year."),
            language=language, response_type="clarification",
        )
        return True

    if _is_meter_metric_question(text):
        _meter_metric_response(skill, message, state, text, language)
        return True

    from skill.services.dia_query import is_comparison_pronoun, is_period_follow_up

    asset_follow_up = bool(
        state.metrics and state.asset_ids
        and re.match(r"^(?:and|what about|how about|peki|ya)\b", text)
        and entity_scope("show " + text)[0]
    )

    if (is_period_follow_up(utterance) and state.metrics and state.asset_ids
            and state.operation in {"kpi", "compare", "rank", "average", "summary"}):
        # The signed Reneryo semantic fallback must not steal a typed asset
        # follow-up. Re-enter the existing structured route only once.
        return try_handle_scoped_query(skill, message) if allow_semantic else False

    comparison = is_comparison_request(utterance)
    # "look at next" is a review verb, not an asset named "next". Remove
    # only that bounded phrase from the scope check; retain all entity cues.
    scope_utterance = (
        re.sub(r"\blook at next\b", "review next", utterance, flags=re.IGNORECASE)
        if is_review_question(utterance) else utterance
    )
    if asset_follow_up:
        scope_utterance = "show " + scope_utterance
    scoped, unresolved = entity_scope(scope_utterance)
    if comparison and not scoped and not (
        is_comparison_pronoun(text)
        and state.metrics
        and (len(state.asset_ids) >= 2 or len(state.answer_evidence) >= 2)
    ):
        # Incomplete comparison shorthand must not select default assets.
        if is_comparison_pronoun(text):
            speak_information(
                skill,
                ("Karşılaştırmak istediğiniz metriği ve en az iki yapılandırılmış ekipmanı belirtin."
                 if is_turkish(language) else
                 "Please name the metric and at least two configured assets you want to compare."),
                language=language, response_type="clarification",
            )
            _remember(skill, message, DialogueState(
                organization_id=state.organization_id, language=language,
                operation="clarification", pending_clarification="equipment scope",
            ))
            return True
        unresolved = True
    if scoped:
        get_assets = getattr(skill, "_get_asset_registry", None)
        try:
            assets = get_assets() if callable(get_assets) else []
        except (AdapterError, ValidationError):
            assets = []
        scoped, unresolved = entity_scope(scope_utterance, assets)
        if not comparison:
            # A full inventory metric name may itself contain an equipment
            # name. Only that exact grounded name is safe to remove from the
            # scope check; a generic alias such as "energy" is insufficient.
            try:
                metrics = skill.dispatcher._run_async(_service(skill).metrics())
            except (AdapterError, ValidationError):
                metrics = []
            scope_text = scope_utterance
            for metric in sorted(metrics, key=lambda row: len(row.name), reverse=True):
                name = metric.name
                if name:
                    scope_text = re.sub(
                        rf"(?<![\w-]){re.escape(name)}(?![\w-])", "measurement", scope_text,
                        flags=re.IGNORECASE,
                    )
            scoped, unresolved = entity_scope(scope_text, assets)
    if comparison or scoped:
        # A factory metric alias is not evidence for an explicitly requested
        # asset. Let the structured/registered asset path handle resolved
        # requests; semantic resolution must never turn them into metric detail.
        if not unresolved and not is_negated_comparison(utterance):
            if not allow_semantic:
                return False
            if asset_follow_up:
                return try_handle_scoped_query(skill, message)
        _scope_clarification(skill, language)
        _remember(skill, message, DialogueState(
            organization_id=state.organization_id, language=language,
            operation="clarification", pending_clarification="equipment scope",
        ))
        return True

    factory_request = classify_factory_question(utterance, state)
    inventory_actions = {
        SemanticAction.METERS_LIST, SemanticAction.METRICS_LIST,
        SemanticAction.REGRESSIONS_LIST, SemanticAction.REGRESSION_DETAIL,
    }
    operation = _deterministic_action(text, state)
    if factory_request is not None and factory_request.kind == "amount":
        # Existing inventory/definition verbs and entity nouns disambiguate the
        # requested view; energy vocabulary alone does not own the operation.
        inventory_cue = bool(re.search(
            r"\b(?:devices?|quantities|measurements?|instruments?|kind|type|unit|"
            r"cihaz\w*|ölçüm\w*|olcum\w*|tür\w*|tur\w*|birim\w*)\b", text
        )) and bool(re.search(
            r"\b(?:which|what|list|available|configured|hangi|hangileri|liste\w*)\b", text
        )) and not bool(re.search(r"\b(?:how much|how many|ne kadar|kaç|kac)\b", text))
        if inventory_cue and not allow_semantic and operation not in inventory_actions:
            # The initial deterministic pass must leave uncertain operation
            # ownership to the existing semantic pass, rather than read a total.
            return False
        if inventory_cue and semantic_resolution is None and allow_semantic:
            resolver = getattr(skill, "_semantic_resolver", None)
            if resolver is not None:
                proposal = resolver.resolve(utterance, state=state, language=language)
                definition = bool(re.search(
                    r"\b(?:kind|type|unit|group|tür\w*|tur\w*|birim\w*)\b", text
                ))
                if proposal.accepted and (
                    proposal.action in inventory_actions
                    or (definition and proposal.action is SemanticAction.METRIC_DETAIL)
                ):
                    semantic_resolution = proposal
        if inventory_cue and (operation in inventory_actions or semantic_resolution is not None):
            factory_request = None
    if corrected and state.metric_name:
        explicit_amount = _has(text, "consum", "tüket", "tuket", "amount", "miktar",
                               "how much", "ne kadar", "produced", "ürett", "urett")
        if (state.operation not in {"factory_history", "trend"}
                and factory_request is not None and factory_request.kind == "amount"
                and not explicit_amount and not extract_period_phrase(utterance)):
            # A detail/finding handoff correction remains a metric detail.
            factory_request = None
        elif factory_request is not None and factory_request.kind == "amount":
            factory_request = replace(
                factory_request, use_period=bool(state.period),
                kind="trend" if state.operation == "trend" and not explicit_amount else "amount",
            )
    if state.operation == "trend" and state.metric_name and is_period_follow_up(utterance):
        factory_request = None
    factory_trend = factory_request is not None and factory_request.kind == "trend"
    if factory_trend:
        utterance = f"{factory_request.utterance} {factory_request.metric_hint} trend"
        text = normalize_phrase(utterance)
    elif factory_request is not None:

        def _factory_execute():
            try:
                period = _query_period(skill, factory_request.utterance, state.period)
            except (ValueError, ValidationError):
                _period_clarification(skill, language)
                return True
            answer = skill.dispatcher._run_async(
                answer_factory_question(
                    _service(skill), factory_request, period, language
                )
            )
            speak_information(
                skill,
                answer.headline,
                language=language,
                response_type=answer.response_type,
                evidence_rows=answer.evidence,
                suggestions=answer.suggestions,
            )
            if answer.metric_name:
                _remember(
                    skill,
                    message,
                    state,
                    operation="factory_history",
                    metric_name=answer.metric_name,
                    period=answer.period or state.period,
                    entity_id="",
                    active_finding_id="",
                    finding_ids=(),
                    selected_finding_from_collection=False,
                )
            elif state.active_finding_id:
                _remember(
                    skill,
                    message,
                    state,
                    operation="factory_selection",
                    metric_name="",
                    entity_id="",
                    active_finding_id="",
                    finding_ids=(),
                    selected_finding_from_collection=False,
                )
            return True

        # A scoped factory request stays claimed even when the safe dispatcher reports an API error.
        skill._safe_dispatch("handle_factory_question", _factory_execute)
        return True

    if (
        state.operation in {"findings", "finding", "evaluation", "clarification"}
        and _finding_selection_scope(text)
        and selection_requested(text, state)
        and selection_index(text, state) is None
    ):
        _finding_selection_clarification(skill, language)
        _remember(skill, message, state, operation="clarification")
        return True
    if is_finding_evidence_question(text) and not state.active_finding_id:
        _finding_selection_clarification(skill, language)
        return True
    if (
        state.finding_ids
        and not state.active_finding_id
        and _finding_selection_scope(text)
        and (is_finding_evidence_question(text) or is_review_question(text)
             or _has(text, "evidence", "kanıt", "kanit", "period", "dönem", "donem"))
        and not is_collection_request(text, state)
    ):
        _finding_selection_clarification(skill, language)
        _remember(skill, message, state, operation="clarification")
        return True

    action = (
        SemanticAction.TREND_SHOW
        if factory_trend or (state.operation == "trend" and state.metric_name
                             and is_period_follow_up(utterance))
        else _deterministic_action(text, state)
    )
    if action is None and corrected and state.metric_name:
        action = (
            SemanticAction.TREND_SHOW if state.operation == "trend"
            else SemanticAction.METRIC_DETAIL
        )
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
        if resolution is not None and resolution.accepted:
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

    if action is SemanticAction.FINDINGS_EVALUATE and not is_evaluation_request(text):
        _semantic_clarification(skill, language)
        _remember(skill, message, state, operation="clarification")
        return True
    if action is SemanticAction.METRICS_LIST and re.match(r"^(?:please )?list\b", text):
        # An explicit list subject still needs to name a supported collection.
        # This is distinct from requiring literal 'metric' in every paraphrase.
        if not re.search(r"\b(?:metrics?|indicators?|kpis?|measurements?|quantities|signals?)\b", text):
            _semantic_clarification(skill, language)
            return True

    def _execute() -> bool:
        service = _service(skill)
        if action is SemanticAction.FINDINGS_EVALUATE:
            return _evaluation_response(skill, message, service, state, language)
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
            try:
                period = _query_period(skill, utterance, state.period, semantic_period)
            except (ValueError, ValidationError):
                _period_clarification(skill, language)
                return True
            # Inherit only subject-free shorthand, before executing. A failed
            # explicit subject is never permission to query the previous one.
            metric_query = (
                state.metric_name if state.metric_name and _is_trend_follow_up(utterance)
                else utterance
            )
            try:
                trend = skill.dispatcher._run_async(service.trend(metric_query, period))
            except (AdapterError, ValidationError) as exc:
                _remember(skill, message, state, operation="trend", metric_name="",
                          pending_clarification="metric unavailable")
                if isinstance(exc, ValidationError) and exc.code == "METRIC_NOT_FOUND":
                    speak_information(
                        skill,
                        ("İstenen ölçüm mevcut Reneryo envanterinde bulunamadı."
                         if is_turkish(language)
                         else "The requested metric is not present in the current Reneryo inventory."),
                        language=language, response_type="unavailable",
                    )
                    return True
                raise
            direction = {
                "increasing": "artıyor",
                "decreasing": "azalıyor",
                "stable": "sabit",
            }.get(trend.direction, trend.direction)
            period_label = _localized_period_label(trend.period_label, language)
            if not trend.points:
                observed_at = trend.metric.last_value_at
                last_seen = observed_at.date().isoformat() if observed_at else None
                if is_turkish(language):
                    headline = f"{trend.metric.name} için {period_label} döneminde gözlem bulunamadı; eğilim hesaplanamıyor."
                    if last_seen:
                        headline += f" Son kayıtlı gözlem {last_seen} tarihinde."
                else:
                    headline = f"No observations were returned for {trend.metric.name} over {period_label}; a trend cannot be calculated."
                    if last_seen:
                        headline += (
                            f" The latest recorded observation is from {last_seen}."
                        )
            elif trend.change_percent is None:
                first_seen = trend.points[0].timestamp.date().isoformat()
                if is_turkish(language):
                    headline = f"{trend.metric.name} için {period_label} döneminde " + (
                        f"yalnızca bir gözlem var ({first_seen}); eğilim hesaplanamıyor."
                        if len(trend.points) == 1
                        else "ilk gözlem sıfır olduğu için yüzde değişim hesaplanamıyor."
                    )
                else:
                    headline = f"For {trend.metric.name} over {period_label}, " + (
                        f"only one observation was returned ({first_seen}); a trend cannot be calculated."
                        if len(trend.points) == 1
                        else "the first observed value is zero, so a percentage change cannot be calculated."
                    )
            elif is_turkish(language):
                headline = f"{trend.metric.name}, {period_label} döneminde %{abs(trend.change_percent):.1f} oranında {direction}."
            else:
                headline = f"{trend.metric.name} is {trend.direction} by {abs(trend.change_percent):.1f}% over {period_label}."
            if trend.requested_period_label:
                missing_period = _localized_period_label(
                    trend.requested_period_label, language
                )
                headline = (
                    f"{missing_period} döneminde gözlem bulunamadı. Bunun yerine tarihsel veriyi gösteriyorum: "
                    if is_turkish(language)
                    else f"No observations were returned for {missing_period}. Showing historical data instead: "
                ) + headline
            actual_period = (
                type(period)(trend.period_start, trend.period_end, trend.period_label)
                if trend.period_start is not None and trend.period_end is not None
                else period
            )
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
                period=actual_period,
                metric_name=trend.metric.name,
                active_finding_id="",
                finding_ids=(),
                selected_finding_from_collection=False,
                entity_id="",
            )
            return True
        if action is SemanticAction.METERS_LIST:
            semantic_period = resolution.slots.get("period", "") if resolution else ""
            period = _query_period(skill, utterance, state.period, semantic_period)
            rows = skill.dispatcher._run_async(service.meters(period))
            if _has(
                text,
                "production",
                "üretim",
                "uretim",
                "electric",
                "elektrik",
                "elektriğ",
            ):
                selected = match_metric(
                    utterance, skill.dispatcher._run_async(service.metrics())
                )
                if selected is not None:
                    rows = [row for row in rows if row.metric_id == selected.metric_id]
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
            _remember(
                skill, message, state, operation="meters", period=period,
                answer_evidence=tuple({"meter_id": r.meter_id, "name": r.name} for r in rows),
                metrics=(), asset_ids=(), metric_name="", entity_id="",
                active_finding_id="", finding_ids=(), selected_finding_from_collection=False,
            )
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
            selected_metric = match_metric(
                utterance if corrected or _is_metric_correction(text) else expected or text,
                rows,
            )
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

    # The selected operation owns this turn even when safe dispatch reports
    # a service failure. Falling through would retry and speak again.
    skill._safe_dispatch("handle_reneryo_query", _execute)
    return True


def _is_meter_metric_question(text: str) -> bool:
    return bool(re.fullmatch(
        r"which metric is (?:the (?:first|second|third) (?:one|meter)|it|this meter) linked to|"
        r"(?:ilki|ikincisi|üçüncüsü|ucuncusu|bu sayaç|bu sayac|o) hangi metri(?:ğe|ge) ba(?:ğlı|gli)",
        text,
    ))


def _meter_metric_response(skill, message, state, text, language) -> None:
    """Resolve only IDs from the last scoped meter result, then recheck its link."""
    def clarify():
        speak_information(
            skill,
            (("Hangi sayacı kastediyorsunuz? Son listedeki sırasını belirtin."
              if candidates else
              "Hangi sayacı kastediyorsunuz? Önce sayaçları listeleyip listedeki sırasını belirtin.")
             if is_turkish(language) else
             ("Which meter do you mean? Specify its position in the last list."
              if candidates else
              "Which meter do you mean? List the meters first, then specify its position in that list.")),
            language=language, response_type="clarification",
        )

    candidates = state.answer_evidence if state.operation == "meters" else ()
    index = next((i for i, pattern in enumerate((
        r"\b(?:first|ilki)\b", r"\b(?:second|ikincisi)\b", r"\b(?:third|üçüncüsü|ucuncusu)\b"
    )) if re.search(pattern, text)), None)
    if index is None and len(candidates) == 1:
        index = 0
    if index is None or index >= len(candidates) or not state.period:
        clarify()
        return
    meter_id = candidates[index].get("meter_id", "")

    def execute():
        service = _service(skill)
        meters = skill.dispatcher._run_async(service.meters(state.period))
        meter = next((row for row in meters if row.meter_id == meter_id), None)
        metric = None
        if meter is not None and meter.metric_id:
            rows = skill.dispatcher._run_async(service.metrics())
            metric = next((row for row in rows if row.metric_id == meter.metric_id), None)
        if metric is None:
            speak_information(
                skill,
                ("Bu sayacın bağlı olduğu metriği mevcut Reneryo verisinden doğrulayamıyorum. Sayacı ve metrik bağlantısını kontrol edin."
                 if is_turkish(language) else
                 "I cannot verify this meter's linked metric from the current Reneryo data. Please check the meter and its metric link."),
                language=language, response_type="clarification",
            )
            return
        speak_information(
            skill, metric_detail_headline(metric, language), language=language,
            response_type="metrics", evidence_rows=[{
                "id": metric.metric_id, "name": metric.name, "type": metric.metric_type,
                "last_value": metric.last_value, "observed_at": _iso(metric.last_value_at),
            }],
        )
        _remember(skill, message, state, operation="metric_detail", metric_name=metric.name,
                  answer_evidence=(), entity_id="", active_finding_id="", finding_ids=())

    skill._safe_dispatch("handle_meter_metric_reference", execute)


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
    context = getattr(message, "context", {}) or {}
    signed = context.get("reneryo_context")
    if not isinstance(signed, dict) or not signed.get("organization_id"):
        return False
    utterance = skill._extract_utterance_text(message)
    if unsupported_time_precision(utterance):
        # Recognizer slots and exact legacy matches cannot drop clock precision.
        return handle_reneryo_query(skill, message, allow_semantic=False)
    if is_comparison_request(utterance) or entity_scope(utterance)[0]:
        # Validate even exact/slot-based legacy matches before they can use
        # defaults for an unresolved asset or fall back to factory data.
        return try_handle_scoped_query(skill, message)
    if not (
        intent_name in _ARBITRATABLE_LEGACY_INTENTS
        or intent_name.startswith("kpi.")
    ):
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
    if (
        classify_factory_question(utterance, state) is not None
        or _deterministic_action(text, state) is not None
    ):
        if handle_reneryo_query(skill, message, allow_semantic=False):
            return True

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


def try_handle_scoped_query(skill, message) -> bool:
    """Resolve a scoped request without single-metric semantic substitution."""
    from skill.services.dia_dialogue import try_handle_structured_query

    if handle_reneryo_query(skill, message, allow_semantic=False):
        return True
    try:
        if try_handle_structured_query(skill, message, include_simple_kpi=True):
            return True
        # Structured parsing deliberately hands scenarios back to the legacy
        # simulator. Scope has already been validated above; keep that handoff.
        if skill._is_whatif_query(skill._extract_utterance_text(message)):
            skill.handle_whatif_scenario(message)
            return True
    except AVAROSError:
        # Missing bindings/unsupported adapter operations remain unavailable;
        # do not retry with a factory metric or inherited subject.
        pass
    state = _context_state(skill, message)
    language = _conversation_language(
        skill._extract_utterance_text(message), state, message, skill._response_language
    )
    _scope_clarification(skill, language)
    _remember(skill, message, DialogueState(
        organization_id=state.organization_id, language=language,
        operation="clarification", pending_clarification="equipment scope",
    ))
    return True


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
    selected_index = selection_index(text, state)
    finding_id = (
        state.finding_ids[selected_index]
        if selected_index is not None
        else (
            ""
            if action is SemanticAction.FINDINGS_LIST or _is_finding_list(text)
            else state.active_finding_id
        )
    )
    if finding_id:
        finding = skill.dispatcher._run_async(
            service.finding(organization_id, finding_id)
        )
        headline = (
            next_review_headline(finding, action.value, language)
            if action in {
                SemanticAction.FINDING_NEXT_REVIEW,
                SemanticAction.FINDING_NEXT_REVIEW_WHY,
                SemanticAction.FINDING_OWNER,
                SemanticAction.FINDING_CAN_ACT,
            }
            else finding_headline(finding, text, language, action=action.value)
        )
        evidence = [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "domain": finding.domain,
                "period_start": finding.evaluation_start.isoformat(),
                "period_end": finding.evaluation_end.isoformat(),
                "next_review_code": finding.next_review.code if finding.next_review else None,
                "next_review_version": finding.next_review.version if finding.next_review else None,
                "assessment_run_id": finding.next_review.assessment_run_id if finding.next_review else None,
                "review_link": finding.next_review.review_link if finding.next_review else None,
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
            selected_finding_from_collection=(
                state.selected_finding_from_collection or selected_index is not None
            ),
        )
        return True
    filters = filters_for(text, state)
    result = skill.dispatcher._run_async(
        service.filtered_findings(
            organization_id,
            status=filters.status,
            severity=filters.severity,
            domain=filters.domain,
        )
    )
    headline = collection_headline(result, filters, language)
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
    _remember(
        skill,
        message,
        state,
        operation="findings",
        active_finding_id="",
        finding_status=filters.status,
        finding_severity=filters.severity,
        finding_domain=filters.domain,
        finding_ids=tuple(f.finding_id for f in result.findings),
        selected_finding_from_collection=False,
    )
    return True


def _evaluation_response(skill, message, service, state, language) -> bool:
    """Run the existing MDSP evaluation, then narrate its returned findings."""
    organization_id = state.organization_id or os.environ.get(
        "FUTUREGEN_ORGANIZATION_ID", ""
    )
    evaluation = skill.dispatcher._run_async(service.evaluate(organization_id))
    filters = FindingFilters(status="ACTIVE")
    result = skill.dispatcher._run_async(
        service.filtered_findings(organization_id, status=filters.status)
    )
    headline = evaluation_headline(evaluation, result, filters, language)
    speak_information(
        skill,
        headline,
        language=language,
        response_type="evaluation",
        evidence_rows=[
            {
                "run_id": evaluation.run_id,
                "evaluated_resource_count": evaluation.evaluated_resource_count,
                "active_finding_count": evaluation.active_finding_count,
                "resolved_finding_count": evaluation.resolved_finding_count,
            },
            *[
                {
                    "id": finding.finding_id,
                    "severity": finding.severity,
                    "domain": finding.domain,
                    "title": finding.title.for_language(language),
                }
                for finding in result.findings
            ],
        ],
    )
    _remember(
        skill,
        message,
        state,
        operation="evaluation",
        active_finding_id="",
        finding_status=filters.status,
        finding_severity="",
        finding_domain="",
        finding_ids=tuple(finding.finding_id for finding in result.findings),
        selected_finding_from_collection=False,
    )
    return True


def _deterministic_action(text: str, state: DialogueState) -> SemanticAction | None:
    """Map established lexical forms without invoking the semantic model."""
    if _finding_selection_scope(text) and selection_index(text, state) is not None:
        return SemanticAction.FINDING_EXPLAIN
    if state.active_finding_id and _has(text, "when this finding was evaluated", "when was this finding evaluated"):
        return SemanticAction.FINDING_PERIOD
    if state.active_finding_id and is_finding_evidence_question(text):
        return SemanticAction.FINDING_EVIDENCE
    if is_evaluation_request(text):
        return SemanticAction.FINDINGS_EVALUATE
    if is_review_question(text):
        return (
            SemanticAction.FINDING_NEXT_REVIEW
            if state.active_finding_id
            else SemanticAction.FINDINGS_LIST
        )
    if is_collection_request(text, state):
        return SemanticAction.FINDINGS_LIST
    if _is_finding_list(text):
        return SemanticAction.FINDINGS_LIST
    # An explicit regression question changes topic even when a finding remains
    # selected. A finding-related regression question was handled above.
    if _has(text, "regression", "regresyon") and not _has(
        text, "finding", "bulgu", "alert", "uyarı", "uyari"
    ):
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
            "quality",
            "weak",
            "training",
            "period",
            "uyum",
            "hata",
            "kalite",
            "zayıf",
            "egitim",
            "eğitim",
            "dönem",
        ):
            return SemanticAction.REGRESSION_DETAIL
        return SemanticAction.REGRESSIONS_LIST
    if state.metric_name and _is_metric_correction(text):
        return (
            SemanticAction.TREND_SHOW
            if state.operation == "trend"
            else SemanticAction.METRIC_DETAIL
        )
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
    if state.metric_name and state.operation in {
        "metric_detail",
        "trend",
        "factory_history",
    }:
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
        if _has(text, "can you take action", "can you act", "take action on it", "işlem yapabilir misin", "eyleme geçebilir misin"):
            return SemanticAction.FINDING_CAN_ACT
        if _has(text, "who should handle", "who is responsible", "who should review",
                "who owns this finding", "who owns it", "who is in charge of it",
                "who should look into this", "who should look at this finding",
                "kim ilgilenmeli", "kim sorumlu", "kim incelemeli",
                "sorumlusu kim", "kimin sorumluluğunda", "kimin sorumlulugunda",
                "bunu kim incelemeli", "buna kim bakmalı", "buna kim bakmali"):
            return SemanticAction.FINDING_OWNER
        if _has(text, "why are you recommending", "why this step", "why recommend", "bu adımı neden", "neden öneriyorsun", "neden tavsiye"):
            return SemanticAction.FINDING_NEXT_REVIEW_WHY
        if _has(text, "what should we do", "recommended next step", "next step", "what do you recommend", "ne yapmalıyız", "sonraki adım", "ne öneriyorsun", "ne tavsiye"):
            return SemanticAction.FINDING_NEXT_REVIEW
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
            "destekleyen gercek",
            "destekleyen gerçek",
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


def _finding_selection_clarification(skill, language: str) -> None:
    if is_turkish(language):
        headline = "Hangi bulguyu kastediyorsunuz? Listedeki numarasını söyleyin."
        suggestions = ["1 numaralı bulguyu açıkla", "2 numaralı bulguyu açıkla"]
    else:
        headline = "Which finding do you mean? Please say its number from the list."
        suggestions = ["Explain finding number 1", "Explain finding number 2"]
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
    organization = str(signed.get("organization_id", "") or "")
    if organization and current.organization_id and organization != current.organization_id:
        skill._dialogue_state_store.clear(session_id)
        current = DialogueState()
    explicit_finding = _has(
        normalize_phrase(skill._extract_utterance_text(message)), "finding", "bulgu"
    )
    seeded_finding = (
        str(signed.get("finding_id", ""))
        if not current.operation or explicit_finding
        else ""
    )
    return replace(
        current,
        organization_id=str(
            signed.get("organization_id", "") or current.organization_id
        ),
        active_finding_id=(
            # A selected item can only originate from the org-scoped MDSP result
            # IDs retained in this bounded session state.
            current.active_finding_id
            if current.selected_finding_from_collection
            else str(seeded_finding or current.active_finding_id)
        ),
        entity_id=current.entity_id
        or (
            str(signed.get("entity_id", ""))
            if not current.operation or explicit_finding
            else ""
        ),
        metric_name=current.metric_name
        or (
            str(signed.get("metric_name", ""))
            if not current.operation or explicit_finding
            else ""
        ),
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
    if unsupported_period_reference(utterance):
        raise ValueError("Unsupported requested period")
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


def _is_trend_follow_up(utterance: str) -> bool:
    """Allow context only for a bounded command that names no new subject."""
    from skill.services.dia_query import is_period_follow_up

    if is_period_follow_up(utterance):
        return True
    text = remove_period_reference(utterance)
    text = re.sub(r"\b(?:over|for|during|in|the|döneminde|için)\b", "", text)
    text = " ".join(text.split())
    return bool(re.fullmatch(
        r"(?:show|display)?\s*(?:its|this metric s|this indicator s|the metric s)?\s*(?:trend|history)|"
        r"(?:bu metriğin |bu metrik |bunun )?(?:eğilimini|egilimini|eğilim|egilim|geçmişini|gecmisini)"
        r"(?: göster| goster)?", text,
    ))


def _period_clarification(skill, language):
    speak_information(
        skill,
        (
            "İstenen dönem desteklenmiyor, geçersiz veya gelecekte. Geçmiş bir tarih, ay ve yıl veya açık tarih aralığı belirtin; dönemi değiştirmedim."
            if is_turkish(language)
            else "The requested period is unsupported, invalid or in the future. Specify a past date, month and year, or an explicit date range; I have not changed the period."
        ),
        language=language,
        response_type="clarification",
    )


def has_signed_widget_context(message) -> bool:
    """Return whether the trusted proxy injected a scoped Reneryo session."""
    context = getattr(message, "context", {}) or {}
    signed = context.get("reneryo_context")
    return (
        context.get("reneryo_widget_session_validated") is True
        and isinstance(signed, dict)
        and bool(signed.get("organization_id"))
    )


def _scope_clarification(skill, language) -> None:
    speak_information(
        skill,
        (
            "İstenen ekipman kapsamını bu istek için doğrulayamıyorum. "
            "Lütfen yapılandırılmış varlık ve metrik adlarını belirtin; "
            "tesis toplamını ekipman verisi yerine kullanamam."
            if is_turkish(language)
            else "I cannot verify the requested equipment scope for this query. "
            "Please name configured assets and metrics; "
            "I cannot substitute whole-factory data for equipment data."
        ),
        language=language,
        response_type="clarification",
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
    return is_historical_change_question(text) or _has(
        text,
        "trend",
        "history",
        "historical",
        "geçmiş",
        "gecmis",
        "evolve",
        "move over",
        "changed",
        "change over",
        "egilim",
        "eğilim",
        "eglim",
        "eğlim",
        "seyr",
        "degis",
        "değiş",
    )


def _is_metric_correction(text: str) -> bool:
    return bool(
        re.match(r"^(?:no|not)\b", text) or re.search(r"\b(?:değil|degil)\b", text)
    )


def _finding_selection_scope(text: str) -> bool:
    return not (
        _has(text, "trend", "egilim", "eğilim", "meter", "sayac", "sayaç", "metric", "metrik", "regression", "regresyon")
        and not _has(text, "finding", "bulgu", "alert", "uyarı", "uyari")
    )


def _localized_period_label(value: str, language: str) -> str:
    return period_display_name(value, language)


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
    "peki", "haziran", "dun", "bugun",
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
    "and", "june", "yesterday", "today", "i", "need", "should", "review",
}


def _conversation_language(utterance, state, message, fallback: str) -> str:
    """Honor the validated current-turn locale before lexical fallback."""
    context = getattr(message, "context", {}) or {}
    if context.get("reneryo_widget_session_validated") is True:
        signed = context.get("reneryo_context", {})
        if isinstance(signed, dict) and signed.get("language"):
            from skill.services.language import normalize_language_tag
            return normalize_language_tag(signed["language"])
    detected = _utterance_language(utterance)
    return (
        detected or _signed_language(message) or state.language or fallback or "en-US"
    )


def _utterance_language(utterance: str) -> str:
    text = normalize_phrase(utterance)
    words = set(text.split())
    turkish_score = len(words & _TURKISH_LANGUAGE_WORDS)
    english_score = len(words & _ENGLISH_LANGUAGE_WORDS)
    if turkish_score > english_score:
        return "tr-TR"
    if english_score > turkish_score:
        return "en-US"
    if any(character in text for character in "çğıöşü"):
        return "tr-TR"
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
