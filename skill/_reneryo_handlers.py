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
from skill._helpers import request_time_format
from skill.services.language import format_observation_time
from skill.services.response_localization import source_metric_label
from skill.services.dia_response import speak_information
from skill.services.factory_questions import (
    answer_factory_question,
    classify_factory_question,
    cost_limitation_headline,
    is_cost_request,
    is_historical_change_question,
    is_freshness_question,
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
from skill.services.futuregen import (
    FutureGenService, default_period, has_metric_alias, match_metric, metric_reference_remainder,
    metric_references,
)
from skill.services.futuregen_responses import (
    meter_inventory_headline,
    metric_detail_headline,
    metric_inventory_headline,
    regression_detail_headline,
    regression_inventory_headline,
)
from skill.services.language import is_turkish, normalize_phrase, period_display_name, format_localized_number, sentence_start
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

    # A clarification is answered by the next turn only. Clear it in the
    # store before routing, so no later route can resume a stale question.
    pending = state.pending_operation if state.pending_clarification == "metric" else ""
    pending_period, pending_window = state.pending_period, state.pending_window
    if (state.pending_clarification or state.pending_operation or state.pending_period
            or state.pending_window is not None):
        store, session_id = skill._dialogue_state_store, message_session_id(message)
        cleared = {"pending_clarification": "", "pending_operation": "", "pending_period": "",
                   "pending_window": None}
        stored = store.get(session_id)
        if stored is not None:
            store.put(session_id, replace(stored, **cleared))
        state = replace(state, **cleared)
    if pending:
        kind, subject = _subject_reply(skill, utterance, allow_period=True)
        if kind == "excluded":
            # "Sıcaklık değil, nem." names a replacement; a bare exclusion
            # still leaves the clarified request waiting for its subject.
            replacement = affirmative_request(utterance)
            kind, subject = (_subject_reply(skill, replacement, allow_period=True)
                             if replacement and replacement != utterance else ("excluded", None))
        if kind in {"unknown", "several", "excluded"}:
            _ask_for_metric(skill, message, state, _safe_metrics(skill), language, pending,
                            period_phrase=pending_period, window=pending_window, reason=kind)
            return True
        if kind == "subject":
            # Execute the clarified operation for this metric directly; the
            # request is never rebuilt as text and classified again. A period
            # named in the answer ("Geçen ay nemin.") is the newer constraint.
            reply_period = extract_period_phrase(utterance)
            reply_period = "" if reply_period in {"latest", "en güncel"} else reply_period
            # Without a new period the window resolved when asking is kept.
            return _resume_metric_request(skill, message, state, subject, pending,
                                          reply_period or pending_period, language,
                                          period=None if reply_period else pending_window)
    elif (state.operation == "trend" and state.metric_name
          and _DISCOURSE.match(text) and not _period_only_follow_up(utterance)):
        # "Peki sıcaklık?" after a trend asks the same view of another subject.
        kind, subject = _subject_reply(skill, utterance)
        if kind == "subject" and subject.name != state.metric_name:
            return _resume_metric_request(skill, message, state, subject, "trend",
                                          state.period_phrase, language, period=state.period)

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

    if extract_period_phrase(utterance) and getattr(skill, "settings_service", None) is not None:
        try:
            from skill._helpers import parse_period
            parse_period(skill, extract_period_phrase(utterance), message)
        except (ValueError, ValidationError):
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
            return try_handle_scoped_query(skill, message)
        _scope_clarification(skill, language)
        _remember(skill, message, DialogueState(
            organization_id=state.organization_id, language=language,
            operation="clarification", pending_clarification="equipment scope",
        ))
        return True

    grounded_read_metric = None
    timestamp_request = is_freshness_question(text) or (
        state.operation == "metric_detail" and bool(state.metric_name)
        and bool(re.fullmatch(r"(?:in )?utc(?: olarak)?(?: (?:please|söyle|soyle))?", text))
    )
    factory_request = classify_factory_question(utterance, state)
    inventory_actions = {
        SemanticAction.METERS_LIST, SemanticAction.METRICS_LIST,
        SemanticAction.REGRESSIONS_LIST, SemanticAction.REGRESSION_DETAIL,
    }
    operation = _deterministic_action(text, state)
    if ((operation is None or operation in {SemanticAction.METRIC_DETAIL, SemanticAction.METRICS_LIST} or operation in _FINDING_ACTIONS)
            and not _has(text, "finding", "bulgu", "alert", "uyarı", "uyari", "regression", "regresyon", "model")
            and not _meter_reference(text) and not _looks_like_trend(text)
            and not _metric_collection_request(text)
            and not is_review_question(text)
            and (_metric_value_request(text, specific=True) or _metric_attribute_request(text) or timestamp_request)
            and (factory_request is None or factory_request.kind in {"reading", "freshness"})):
        rows = skill._safe_dispatch(
            "resolve_metric_read", lambda: skill.dispatcher._run_async(_service(skill).metrics())
        )
        if rows is None:
            _remember(skill, message, DialogueState(organization_id=state.organization_id, language=language),
                      operation="metric_clarification", pending_clarification="metric unavailable")
            return True
        references = metric_references(utterance, rows)
        shorthand = _metric_detail_shorthand(text)
        if not references and shorthand and state.operation in {"metric_detail", "trend", "factory_history"}:
            references = metric_references(state.metric_name, rows)
        if len(references) == 1:
            # Keep the existing counter/factory read path when its subject agrees.
            factory_subjects = metric_references(factory_request.metric_hint, rows) if factory_request else []
            if not factory_subjects or factory_subjects != references:
                factory_request = None
                grounded_read_metric = references[0]
                semantic_resolution = _metric_read_resolution(grounded_read_metric, utterance, language)
                operation = semantic_resolution.action
        elif (references or not shorthand or has_metric_alias(utterance)
              or (timestamp_request and not state.active_finding_id)
              or not (state.metric_name or state.active_finding_id)):
            # Nothing in the dialogue supplies the subject: ask for it and keep
            # the requested read waiting for the answer.
            _ask_for_metric(skill, message, state, references or rows, language,
                            *_pending_read(text, utterance, timestamp_request),
                            window=_requested_window(skill, utterance, message))
            return True
    detail_request = (
        (_metric_attribute_request(text) or (
            _singular_metric_request(text) and not extract_period_phrase(utterance)
            and not _quantity_request(text)
        )) and not _meter_reference(text)
        and operation in {None, SemanticAction.METRICS_LIST, SemanticAction.METRIC_DETAIL}
    )
    if detail_request:
        # An attribute of a metric is a detail request, not a collection.
        operation = SemanticAction.METRIC_DETAIL
        factory_request = None
    elif (operation in {None, SemanticAction.METRICS_LIST}
          and _metric_collection_request(text) and not _meter_reference(text)
          and not _quantity_request(text) and not extract_period_phrase(utterance)):
        # The same catalogue contract owns inventory-shaped factory history
        # proposals as well as amounts, without stealing dated quantity reads.
        operation = SemanticAction.METRICS_LIST
        factory_request = None
    if factory_request is not None and factory_request.kind == "amount":
        # Existing inventory/definition verbs and entity nouns disambiguate the
        # requested view; energy vocabulary alone does not own the operation.
        inventory_cue = bool(re.search(
            r"\b(?:devices?|quantities|measurements?|instruments?|kind|type|unit|"
            r"cihaz\w*|ölçüm\w*|olcum\w*|tür\w*|tur\w*|birim\w*)\b", text
        )) and bool(re.search(
            r"\b(?:which|what|list|available|configured|hangi|hangileri|liste\w*)\b", text
        )) and not bool(re.search(r"\b(?:how much|how many|ne kadar|kaç|kac)\b", text))
        # Selecting which meters measured consumption is an inventory request,
        # distinct from asking how much a meter consumed.
        meter_inventory = bool(re.search(r"\b(?:meters?|sayaç\w*|sayac\w*)\b", text)) and bool(
            re.search(r"\b(?:which|hangi|list|liste\w*)\b", text)
        )
        inventory_cue = inventory_cue or meter_inventory
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
    if _period_follow_up_trend(state, utterance):
        factory_request = None
    factory_trend = factory_request is not None and factory_request.kind == "trend"
    if factory_trend:
        utterance = f"{factory_request.utterance} {factory_request.metric_hint} trend"
        text = normalize_phrase(utterance)
    elif factory_request is not None:

        def _factory_execute():
            try:
                period = _query_period(skill, factory_request.utterance, state.period, message=message)
            except (ValueError, ValidationError):
                _period_clarification(skill, language)
                return True
            answer = skill.dispatcher._run_async(
                answer_factory_question(
                    _service(skill), factory_request, period, language,
                    **request_time_format(skill, message),
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
        if factory_trend or _period_follow_up_trend(state, utterance)
        else operation
    )
    if action is None and corrected and state.metric_name:
        action = (
            SemanticAction.TREND_SHOW if state.operation == "trend"
            else SemanticAction.METRIC_DETAIL
        )
    resolution: SemanticResolution | None = semantic_resolution
    if (action is None and not _metric_collection_request(text)
            and (_metric_value_request(text, specific=True)
                 or (_metric_value_request(text) and extract_period_phrase(utterance)))):
        # A concrete read subject/field outranks an unconstrained action proposal.
        # Explicit operations and factory amount requests have already taken ownership.
        metric = _ground_metric_reference(skill, utterance)
        if metric is not None:
            resolution = _metric_read_resolution(metric, utterance, language)
            action = resolution.action
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

    if (action in {SemanticAction.METERS_LIST, SemanticAction.METRICS_LIST}
            and _metric_value_request(text)
            and not _meter_reference(text) and not _metric_collection_request(text)):
        # An inventory proposal cannot replace an explicit metric value.
        # Keep generic catalogue paraphrases when no metric subject is named.
        metric = _ground_metric_reference(skill, utterance)
        if metric is None and (
            action is SemanticAction.METERS_LIST or has_metric_alias(utterance)
            or _metric_value_request(text, specific=True) or extract_period_phrase(utterance)
        ):
            _metric_clarification(skill, [], language)
            return True
        if metric is not None:
            resolution = _metric_read_resolution(metric, utterance, language)
            action = resolution.action

    if (action is SemanticAction.METRIC_DETAIL and not detail_request and not timestamp_request
            and extract_period_phrase(utterance) not in {"", "latest", "en güncel"}):
        # "Dün hava sıcaklığı kaçtı?": a dated value is that period's trend, as
        # _metric_read_resolution routes it; the latest observation would
        # silently answer a different period. Attributes and timestamps keep
        # their own handling (a dated timestamp abstains below).
        action = SemanticAction.TREND_SHOW
        if resolution is not None:
            resolution = replace(resolution, action=action)

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
                entity_id=selected.regression_id if selected is not None else "",
            )
            return True
        if action is SemanticAction.TREND_SHOW:
            semantic_period = resolution.slots.get("period", "") if resolution else ""
            try:
                period = _query_period(skill, utterance, state.period, semantic_period, message=message)
            except (ValueError, ValidationError):
                _period_clarification(skill, language)
                return True
            # A window inherited from context keeps the phrase that selected it.
            selection = extract_period_phrase(utterance) or (
                state.period_phrase if state.period is not None and period is state.period else ""
            )
            # Inherit only subject-free shorthand, before executing. A failed
            # explicit subject is never permission to query the previous one.
            metric_query = (
                state.metric_name if state.metric_name and _is_trend_follow_up(utterance)
                else utterance
            )
            try:
                inventory = skill.dispatcher._run_async(service.metrics())
                references = metric_references(metric_query, inventory)
                if not references and metric_query == utterance and _names_no_subject(utterance):
                    # "Eylül 2026 eğilimini göster" names no metric: ask for
                    # one rather than reporting the inventory as missing it.
                    _ask_for_metric(skill, message, state, inventory, language, "trend",
                                    period_phrase=selection, window=period if selection else None)
                    return True
                if not references:
                    raise ValidationError(message="Metric not found", code="METRIC_NOT_FOUND")
                if len(references) > 1:
                    _ask_for_metric(skill, message, state, references, language, "trend",
                                    period_phrase=selection, window=period if selection else None)
                    return True
                trend = skill.dispatcher._run_async(service.trend(
                    utterance, period, metric=references[0],
                    allow_history_fallback=not bool(state.period or extract_period_phrase(utterance)),
                    period_phrase=selection,
                ))
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
            return _speak_trend(skill, message, state, trend, period, language, selection)
        if action is SemanticAction.METERS_LIST:
            semantic_period = resolution.slots.get("period", "") if resolution else ""
            period = _query_period(skill, utterance, state.period, semantic_period, message=message)
            references = metric_references(utterance, skill.dispatcher._run_async(service.metrics()))
            if len(references) > 1:
                _metric_clarification(skill, references, language)
                return True
            rows = skill.dispatcher._run_async(service.meters(period))
            if references:
                rows = [row for row in rows if row.metric_id == references[0].metric_id]
            from skill.services.reneryo_periods import meter_window_exact
            exact_window = meter_window_exact(period.start, period.end)
            headline = meter_inventory_headline(rows, period, language, exact_window=exact_window)
            evidence = [
                {
                    "id": r.meter_id,
                    "name": r.name,
                    "resource": r.energy_resource,
                    "consumption": r.consumption,
                    "unit_group": r.unit_group,
                    "metric_id": r.metric_id,
                    "period_exact": exact_window,
                }
                for r in rows
            ]
            speak_information(
                skill,
                headline,
                language=language,
                response_type="meters",
                evidence_rows=evidence,
                warnings=[] if exact_window else [
                    "Reneryo bucket boundaries do not establish exact consumption for this window."
                ],
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
        rows = (
            [grounded_read_metric]
            if action is SemanticAction.METRIC_DETAIL and grounded_read_metric is not None
            else skill.dispatcher._run_async(service.metrics())
        )
        selected_metric = None
        if action is SemanticAction.METRIC_DETAIL:
            expected = (
                resolution.slots.get("metric_name", "")
                if resolution is not None
                else ""
            ) or state.metric_name
            references = metric_references(utterance, rows)
            if len(references) > 1:
                _ask_for_metric(skill, message, state, references, language,
                                *_pending_read(text, utterance, timestamp_request),
                                window=_requested_window(skill, utterance, message))
                return True
            selected_metric = references[0] if references else None
            # Explicit subjects outrank semantic/context slots. For an attribute
            # or value request, inherit only subject-free dialogue shorthand.
            if selected_metric is None and (
                not (detail_request or _metric_value_request(text))
                or _metric_detail_shorthand(text)
            ):
                selected_metric = match_metric(expected or text, rows)
        if action is SemanticAction.METRIC_DETAIL and selected_metric is None:
            _ask_for_metric(skill, message, state, rows, language,
                            *_pending_read(text, utterance, timestamp_request),
                            window=_requested_window(skill, utterance, message))
            return True
        if action is SemanticAction.METRICS_LIST:
            references = metric_references(utterance, rows)
            if _has_inventory_modifier(utterance, rows) or (has_metric_alias(utterance) and not references):
                # An unresolved explicit filter must not widen to all metrics
                # or silently discard an unrecognized part of the subject.
                _metric_clarification(skill, rows, language)
                return True
            if references:
                # A collection may contain several members of a metric family.
                rows = references
        timestamp_only = selected_metric is not None and timestamp_request
        if timestamp_only and extract_period_phrase(utterance) not in {"", "latest", "en güncel"}:
            _timestamp_period_unavailable(skill, message, state, language)
            return True
        if selected_metric is not None:
            return _speak_metric_read(
                skill, message, state, selected_metric, language,
                value_only=not detail_request and _metric_value_request(text),
                timestamp_only=timestamp_only,
            )
        headline = metric_inventory_headline(rows, language, **request_time_format(skill, message))
        speak_information(
            skill,
            headline,
            language=language,
            response_type="metrics",
            evidence_rows=[_metric_evidence(r) for r in rows],
        )
        _remember(skill, message, state, operation="metrics", metric_name="", period=None)
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
            skill, metric_detail_headline(metric, language, **request_time_format(skill, message)), language=language,
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
    if extract_period_phrase(utterance) or unsupported_period_reference(utterance):
        if handle_reneryo_query(skill, message, allow_semantic=False):
            return True
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
            else finding_headline(finding, text, language, action=action.value,
                                   **request_time_format(skill, message))
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
        spoken_headline=collection_headline(result, filters, language, spoken=True),
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
            "açıklayıcı değişken",
            "aciklayici degisken",
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
    if not _has(text, "finding", "bulgu", "alert", "uyarı", "uyari"):
        explicit = _explicit_domain_action(text)
        if explicit is not None:
            if (explicit is SemanticAction.METRICS_LIST and state.metric_name
                    and _metric_detail_shorthand(text)):
                return SemanticAction.METRIC_DETAIL
            return explicit
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
        if _has(text, "what should we do", "what should i do", "recommended next step", "next step", "what do you recommend",
                "sonraki adım", "ne öneriyorsun", "ne tavsiye") or re.search(
                # First and plural persons: yapmalıyım/yapmalıyız, yapmam(ız) gerek, yapalım.
                r"\bne yapmal[ıi]y[ıi][mz]\b|\bne yapmam(?:[ıi]z)? gerek\w*|\bne yapal[ıi]m\b", text):
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
    return _explicit_domain_action(text)


def _explicit_domain_action(text: str) -> SemanticAction | None:
    """Existing subject/operation cues, evaluated before contextual keywords."""
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
    if _has(text, "metric", "metrics", "metrik") or (
        _METRIC_NOUN.search(text) and _metric_collection_request(text)
    ):
        return SemanticAction.METRICS_LIST
    if _has(text, "findings", "bulgular", "decision support", "karar destek"):
        return SemanticAction.FINDINGS_LIST
    return None


def _semantic_clarification(skill, language: str) -> None:
    if is_turkish(language):
        headline = (
            "Hangi veriyi veya işlemi kastediyorsunuz? Ölçümün ya da bulgunun adını belirtir misiniz?"
        )
        suggestions = [
            "Bu bulgunun nedenini açıkla",
            "Kanıtları göster",
            "Metrikleri listele",
        ]
    else:
        headline = (
            "Which data or operation do you mean? Please name the measurement or finding."
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


def _metric_clarification(skill, rows, language: str, *, reason: str = "") -> None:
    names = [row.name for row in rows[:3]]
    if is_turkish(language):
        headline = "Hangi Reneryo metriğini kastediyorsunuz? Metrik adını belirtin."
        prefix = {"unknown": "Bu adla yapılandırılmış bir metrik bulamadım. ",
                  "several": "Bu istek için tek bir metrik seçin. ",
                  "excluded": "Hariç tuttuğunuz metrik yerine kullanılacak olanı söyleyin. "}.get(reason, "")
        headline = prefix + headline
        suggestions = [f"{name} metriğini açıkla" for name in names]
    else:
        headline = "Which Reneryo metric do you mean? Please name the metric."
        prefix = {"unknown": "I could not find a configured metric with that name. ",
                  "several": "Please choose one metric for this request. ",
                  "excluded": "Please name the metric to use instead of the excluded one. "}.get(reason, "")
        headline = prefix + headline
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
    candidates = [row for row in rows if not period or row.period.upper() == period]
    normalized = normalize_phrase(text)
    named = [row for row in rows if any(
        normalize_phrase(name) in normalized for name in row.driver_names if name
    )]
    if named:
        candidates = [row for row in candidates if row in named]
    if period or named:
        return candidates[0] if len(candidates) == 1 else None
    if state.operation == "regression_detail" and state.entity_id:
        contextual = [row for row in rows if row.regression_id == state.entity_id]
        if len(contextual) == 1:
            return contextual[0]
    return None


def _regression_period_hint(text: str) -> str:
    if _has(text, "daily", "gunluk", "günlük"):
        return "DAILY"
    if _has(text, "monthly", "aylik", "aylık"):
        return "MONTHLY"
    return ""


def _regression_clarification(skill, rows, language: str) -> None:
    periods = sorted({row.period.lower() for row in rows})
    if is_turkish(language):
        headline = "Hangi regresyon modelini kastediyorsunuz? Dönemini veya açıklayıcı değişkenini belirtin."
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
    def owner(operation):
        if operation in {"finding", "findings", "evaluation"}:
            return "finding"
        if operation in {"metric_detail", "metrics", "trend", "factory_history", "factory_selection", "metric_clarification"}:
            return "metric"
        if operation in {"regressions", "regression_detail", "regression_clarification"}:
            return "regression"
        return operation

    if "period" in changes and "period_phrase" not in changes:
        changes["period_phrase"] = ""
    operation = changes.get("operation", state.operation)
    previous_owner = owner(state.operation)
    if state.operation in {"clarification", "metric_clarification"}:
        if state.active_finding_id or state.finding_ids:
            previous_owner = "finding"
        elif state.metric_name:
            previous_owner = "metric"
    if operation != "clarification" and owner(operation) != previous_owner:
        state = DialogueState(organization_id=state.organization_id, language=state.language)
    skill._dialogue_state_store.put(
        message_session_id(message), replace(state, **changes)
    )


def _metric_evidence(row) -> dict:
    return {
        "id": row.metric_id,
        "name": row.name,
        "type": row.metric_type,
        "last_value": row.last_value,
        "observed_at": _iso(row.last_value_at),
    }


def _speak_metric_read(skill, message, state, metric, language, *, value_only: bool, timestamp_only: bool) -> bool:
    """Answer one inventory-grounded metric read (value, timestamp or detail)."""
    headline = metric_detail_headline(metric, language, value_only=value_only,
                                      timestamp_only=timestamp_only,
                                      **request_time_format(skill, message))
    speak_information(skill, headline, language=language, response_type="metrics",
                      evidence_rows=[_metric_evidence(metric)])
    _remember(skill, message, state, operation="metric_detail", metric_name=metric.name, period=None)
    return True


def _timestamp_period_unavailable(skill, message, state, language) -> None:
    speak_information(skill,
        ("Metrik envanteri yalnızca en son gözlem zamanını sağlıyor; istenen dönemi bu kayıtla değiştirmedim."
         if is_turkish(language) else
         "The metric inventory provides only the latest observation timestamp; I have not substituted it for the requested period."),
        language=language, response_type="unavailable")
    _remember(skill, message, DialogueState(organization_id=state.organization_id, language=language),
              operation="metric_clarification", pending_clarification="timestamp period")


def _speak_trend(skill, message, state, trend, period, language, period_phrase: str = "") -> bool:
    """Narrate a Reneryo trend and keep its subject and actual period in context."""
    period_label = _localized_period_label(trend.period_label, language)
    if not trend.points:
        observed_at = trend.metric.last_value_at
        last_seen = format_observation_time(observed_at, language, **request_time_format(skill, message)) if observed_at else None
        if is_turkish(language):
            headline = f"{sentence_start(source_metric_label(trend.metric.name, language), language)} için {period_label} döneminde gözlem bulunamadı; eğilim hesaplanamıyor."
            if last_seen:
                headline += f" Son kayıtlı gözlem {last_seen} tarihinde."
        else:
            headline = f"No observations were returned for {trend.metric.name} over {period_label}; a trend cannot be calculated."
            if last_seen:
                headline += (
                    f" The latest recorded observation is from {last_seen}."
                )
    elif trend.metric.unit_group == "TEMPERATURE" and len(trend.points) > 1:
        from skill.services.futuregen_responses import temperature_trend_headline

        headline = temperature_trend_headline(trend, language)
    elif trend.change_percent is None:
        first_seen = format_observation_time(trend.points[0].timestamp, language, **request_time_format(skill, message))
        if is_turkish(language):
            headline = f"{sentence_start(source_metric_label(trend.metric.name, language), language)} için {period_label} döneminde " + (
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
        headline = (f"{period_label[:1].upper() + period_label[1:]} döneminde {source_metric_label(trend.metric.name, language)}, "
                    f"ilk ölçüme göre %{format_localized_number(abs(trend.change_percent), language, '.1f')} "
                    + ("arttı." if trend.change_percent > 0 else "azaldı." if trend.change_percent < 0 else "değişmedi."))
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
        source_metric={"id": trend.metric.metric_id, "name": trend.metric.name, "unit_group": trend.metric.unit_group},
    )
    _remember(
        skill,
        message,
        state,
        operation="trend",
        period=actual_period,
        # A history fallback replaced the requested window; no phrase selected it.
        period_phrase="" if trend.requested_period_label else period_phrase,
        metric_name=trend.metric.name,
        active_finding_id="",
        finding_ids=(),
        selected_finding_from_collection=False,
        entity_id="",
    )
    return True


def _safe_metrics(skill) -> list:
    try:
        return skill.dispatcher._run_async(_service(skill).metrics())
    except (AdapterError, ValidationError):
        return []


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


def _query_period(skill, utterance: str, current, semantic_period: str = "", *, message=None):
    """Extract a supported period phrase without sending the full query parser input."""
    if unsupported_period_reference(utterance):
        raise ValueError("Unsupported requested period")
    phrase = extract_period_phrase(utterance)
    if phrase:
        if message is not None and getattr(skill, "settings_service", None) is not None:
            from skill._helpers import parse_period
            return parse_period(skill, phrase, message)
        parsed = skill._parse_period(phrase)
        if parsed:
            return parsed
    if semantic_period:
        # A proposed slot cannot introduce a period absent from source text.
        raise ValueError("Proposed period is not grounded in the original request")
    from skill._helpers import request_clock
    return current or default_period(now=request_clock(message))


def _is_trend_follow_up(utterance: str) -> bool:
    """Allow context only for a bounded command that names no new subject."""
    if _period_only_follow_up(utterance):
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
            "İstenen dönem desteklenmiyor, geçersiz, gelecekte veya kuruluşun saat dilimi doğrulanmamış. Geçmiş bir tarih, ay ve yıl veya açık tarih aralığı belirtin; dönemi değiştirmedim."
            if is_turkish(language)
            else "The requested period is unsupported, invalid, in the future, or the organization timezone is not verified. Specify a past date, month and year, or an explicit date range; I have not changed the period."
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


_METRIC_ATTRIBUTE = re.compile(
    r"\b(?:types?|kind|units?|resource group|t[üu]r(?:[üu]\w*|de\w*|ler\w*)?|tip(?:i\w*|te\w*|ler\w*)?|birim\w*)\b"
)
_METRIC_VALUE = re.compile(
    r"\b(?:values?|measurements?|readings?|latest|current|recent|"
    r"değer\w*|deger\w*|ölçüm\w*|olcum\w*|güncel\w*|guncel\w*|son|"
    # Ordinary Turkish value questions; bare "kaç"/"ne kadar" stay with amounts.
    r"kaç derece|kac derece|yüzde kaç|yuzde kac)\b"
)


def _meter_reference(text: str) -> bool:
    return bool(re.search(
        r"\b(?:meters?|devices?|instruments?|sayaç\w*|sayac\w*|cihaz\w*|"
        r"donanım\w*|donanim\w*)\b", text
    ))


def _metric_collection_request(text: str) -> bool:
    if re.search(r"\b(?:metrics|indicators|metrikler\w*|göstergeler\w*|gostergeler\w*)\b", text):
        return True
    return bool(_METRIC_NOUN.search(text)) and bool(re.search(
        r"\b(?:list|liste\w*|available|configured|inventory|mevcut|envanter)\b", text
    ))


_METRIC_NOUN = re.compile(r"\b(?:metrics?|indicators?|metri[kğg]\w*|gösterge\w*|gosterge\w*)\b")


def _singular_metric_request(text: str) -> bool:
    return bool(_METRIC_NOUN.search(text)) and not _metric_collection_request(text)


def _quantity_request(text: str) -> bool:
    return bool(re.search(r"\b(?:how much|how many|ne kadar|kaç|kac)\b", text))


def _has_inventory_modifier(utterance: str, metrics) -> bool:
    """Recognize explicit collection modifiers without interpreting new domains.

    Ground known names/families first. These bounded noun-phrase positions
    reject unknown filters rather than silently returning the whole catalogue.
    """
    # Mask opaque names before splitting clauses, including names containing
    # punctuation. A word in a preceding clause is not a collection modifier.
    for metric in sorted(metrics, key=lambda row: len(row.name), reverse=True):
        if metric.name:
            utterance = re.sub(rf"(?<!\w){re.escape(metric.name)}(?!\w)",
                               "configured", utterance, flags=re.IGNORECASE)
    modifiers = []
    for clause in re.split(r"[;.!?]", utterance):
        text = normalize_phrase(clause)
        for metric in metrics:
            name = normalize_phrase(metric.name)
            if name:
                text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "configured", text)
        modifiers += re.findall(r"\b(\w+)\s+(?:metrics|indicators|metrik\w*|gösterge\w*|gosterge\w*)\b", text)
        modifiers += re.findall(r"\b(?:metrics?|indicators?)\s+(?:for|of|about)\s+(?:the\s+)?(\w+)\b", text)
    generic = {
        "the", "all", "which", "what", "available", "configured", "current", "our",
        "these", "those", "reneryo", "futuregen", "factory", "site", "plant",
        "hangi", "mevcut", "tüm", "tum", "bütün", "butun", "bu", "kayıtlı", "kayitli",
        "tanımlı", "tanimli", "ölçülen", "olculen", "ilgili",
        "list", "show", "listele", "göster", "goster",
        "saved", "known", "registered", "named", "measured", "operational",
        "consumption", "usage", "tüketim", "tuketim", "sarfiyat",
    }
    return any(word not in generic and not metric_references(word, metrics) for word in modifiers)


def _metric_attribute_request(text: str) -> bool:
    return (bool(_METRIC_ATTRIBUTE.search(text)) and not _metric_collection_request(text)
            and not _quantity_request(text))


def _metric_value_request(text: str, *, specific: bool = False) -> bool:
    # A measurement noun alone can mean the catalogue; a value/reading or
    # latest/current qualifier requests an observation, not an unnamed catalogue.
    return any(not specific or not re.fullmatch(r"measurements?|ölçüm\w*|olcum\w*", match.group())
               for match in _METRIC_VALUE.finditer(text))


def _metric_read_resolution(metric, utterance: str, language: str) -> SemanticResolution:
    period = extract_period_phrase(utterance)
    action = (SemanticAction.TREND_SHOW if period and period not in {"latest", "en güncel"} and not is_freshness_question(utterance)
              else SemanticAction.METRIC_DETAIL)
    slots = {"metric_name": metric.name}
    if period:
        slots["period"] = period
    return SemanticResolution(action, language, slots=slots, reason="grounded_metric_subject")


def _metric_detail_shorthand(text: str) -> bool:
    remainder = _METRIC_ATTRIBUTE.sub("", _METRIC_VALUE.sub("", text))
    remainder = re.sub(
        r"\b(?:what|which|is|are|was|the|a|an|its|it|this|that|metric|indicator|"
        r"show|tell|me|please|and|of|about|ne|nedir|kaç|kac|hangi|bu|bunun|onun|"
        r"when|does|have|recorded|updated|refreshed|received|timestamp|observations?|time|date|last|in|utc|"
        r"how|that|our|up|to|old|data|veri\w*|en|gözlem\w*|gozlem\w*|related|indicator|ilgili|gösterge|gosterge|zaman|zamanı|zamani|kaydedildi|güncellendi|guncellendi|kayıt|kayit|tarihi|olarak|dahil|"
        r"alındı|alindi|ölçüldü|olculdu|taken|measured|"
        r"metri\w*|göster\w*|goster\w*|söyle\w*|soyle\w*|peki|birim\w*)\b", "", remainder
    )
    return not remainder.strip()


_TREND_WORDS = re.compile(
    r"\b(?:trend\w*|history|eğilim\w*|egilim\w*|geçmiş\w*|gecmis\w*|for|during|over|"
    r"için|icin|döneminde|donemi\w*|dönemi\w*|nasıl\w*|nasil\w*|seyr\w*|"
    r"değiş\w*|degis\w*|how|did|it|change\w*|go|went)\b"
)
_DISCOURSE = re.compile(r"^(?:and|what about|how about|peki|ya)\b\s*")
# Thanks, acknowledgement or cancelling: the pending question is dropped.
_CLOSING_REPLY = re.compile(
    r"(?:thanks?(?: you)?|thank you|ok(?:ay)?|no|yes|never mind|cancel|forget it|"
    r"teşekkür\w*|tesekkur\w*|sağ ?ol\w*|sag ?ol\w*|tamam|peki|evet|hayır|hayir|"
    r"vazgeç\w*|vazgec\w*|iptal|boş ?ver|bos ?ver|önemli değil|onemli degil)"
)
_SUBJECT_FILLER = re.compile(
    r"\b(?:the|of|please|lütfen|lutfen|one|metric|metriği|metrigi|metrik|olan|for|için|icin|"
    r"hava|dış|dis|outdoor|outside|weather)\b"
)
# "Sıcaklık değil", "not temperature": the existing negation guard owns these.
_NEGATED_REPLY = re.compile(
    r"\b(?:değil\w*|degil\w*|olmasın|olmasin|hariç|haric|yerine|not|except|without|instead)\b"
)
_JOINED_REPLY = re.compile(r"\b(?:ve|veya|ya da|ile|and|or)\b")


def _names_no_subject(utterance: str) -> bool:
    """Whether a read/trend request names no metric, only an operation or period."""
    text = _TREND_WORDS.sub(" ", normalize_phrase(remove_period_reference(utterance)))
    return _metric_detail_shorthand(" ".join(text.split()))


def _period_follow_up_trend(state, utterance: str) -> bool:
    """A period alone continues the current metric as that period's trend.

    After a trend it replaces the window. After a latest-value read a past
    period ("Peki dün?", "And yesterday?") asks for the same metric then, and
    a dated value is that period's trend, as _metric_read_resolution routes
    it; it is never answered with the latest observation.
    """
    if not (state.metric_name and _period_only_follow_up(utterance)):
        return False
    if state.operation == "trend":
        return True
    return (state.operation == "metric_detail"
            and extract_period_phrase(utterance) not in {"", "latest", "en güncel"})


def _period_only_follow_up(utterance: str) -> bool:
    """A period alone, optionally with "peki"/"for"/"için", changes only the period.

    This is also the answer to "please specify the month and year", so it
    must continue the current topic instead of starting a new request.
    """
    from skill.services.dia_query import is_period_follow_up

    if is_period_follow_up(utterance):
        return True
    if not extract_period_phrase(utterance) or unsupported_period_reference(utterance):
        return False
    rest = _DISCOURSE.sub("", remove_period_reference(utterance))
    # "Dün nasıldı?" / "How was it yesterday?" ask about the same subject.
    return not re.sub(r"\b(?:for|in|during|için|icin|döneminde|olarak|"
                      r"nasıldı|nasildi|nasıl|nasil|how|was|it)\b", " ", rest).strip()


def _subject_reply(skill, utterance: str, *, allow_period: bool = False):
    """Classify a reply to "which metric?" as ("subject", metric) or otherwise.

    Only a reply that is exactly one inventory-grounded subject ("Nem.",
    "Yağışın.", "Humidity.") may resume the clarified request. A negation
    returns "excluded"; two subjects or an unresolved extra word return
    "several"; an unknown name "unknown"; anything carrying its own
    operation, period or topic is a new "request".
    """
    dated = bool(extract_period_phrase(utterance))
    text = remove_period_reference(utterance) if dated and allow_period else utterance
    text = _DISCOURSE.sub("", normalize_phrase(text))
    text = " ".join(_SUBJECT_FILLER.sub(" ", text).split())
    if (not text or len(text.split()) > 6 or (dated and not allow_period)
            or _CLOSING_REPLY.fullmatch(text)
            or _metric_value_request(text) or _metric_attribute_request(text)
            or _looks_like_trend(text) or is_freshness_question(text)
            or _metric_collection_request(text) or _meter_reference(text)
            or _has(text, "finding", "bulgu", "alert", "uyarı", "uyari", "regression",
                    "regresyon", "model", "list", "liste", "göster", "goster", "show",
                    "evaluate", "değerlendir", "degerlendir", "help", "yardım", "yardim")
            or _deterministic_action(text, DialogueState()) is not None):
        return "request", None
    if _NEGATED_REPLY.search(text):
        return "excluded", None
    try:
        rows = skill.dispatcher._run_async(_service(skill).metrics())
    except (AdapterError, ValidationError):
        return "request", None
    references = metric_references(text, rows)
    if len(references) > 1:
        return "several", None
    if not references:
        return ("several" if _JOINED_REPLY.search(text) else "unknown"), None
    if _JOINED_REPLY.sub(" ", metric_reference_remainder(text, references[0])).strip():
        return "several", None
    return "subject", references[0]


def _pending_read(text: str, utterance: str, timestamp_request: bool) -> tuple[str, str]:
    """The read operation and explicit period a metric clarification keeps."""
    phrase = extract_period_phrase(utterance)
    phrase = "" if phrase in {"latest", "en güncel"} else phrase
    if timestamp_request or is_freshness_question(utterance):
        return "timestamp", phrase
    operation = "value" if _metric_value_request(text) and not _metric_attribute_request(text) else "detail"
    return operation, phrase


def _ask_for_metric(skill, message, state, rows, language, operation, period_phrase="", *,
                    window=None, reason="") -> None:
    """Ask which metric is meant and keep the structured request waiting."""
    _metric_clarification(skill, rows, language, reason=reason)
    _remember(skill, message, DialogueState(
        organization_id=state.organization_id, language=language,
    ), operation="metric_clarification", pending_clarification="metric",
        pending_operation=operation, pending_period=period_phrase,
        pending_window=window if period_phrase else None)


def _requested_window(skill, utterance: str, message):
    """The window an explicit period resolves to now, or None."""
    if extract_period_phrase(utterance) in {"", "latest", "en güncel"}:
        return None
    try:
        return _query_period(skill, utterance, None, message=message)
    except (ValueError, ValidationError):
        return None


def _resume_metric_request(skill, message, state, metric, operation, period_phrase, language, *, period=None) -> bool:
    """Run a clarified or subject-switched request with its kept structure.

    The same response builders as the direct route are used, with the
    operation, selected metric and explicit period passed as data.
    """
    def execute() -> bool:
        requested = period
        if requested is None and (operation == "trend" or period_phrase):
            try:
                requested = _query_period(skill, period_phrase, None, message=message)
            except (ValueError, ValidationError):
                _period_clarification(skill, language)
                return True
        if period_phrase and operation != "trend" and metric.metric_type == "COUNTER":
            # As the direct factory route answers a dated cumulative reading.
            from skill.services.factory_questions import historical_reading_unavailable

            speak_information(skill, historical_reading_unavailable(requested, language),
                              language=language, response_type="unavailable")
            _remember(skill, message, state, operation="factory_history",
                      metric_name=metric.name, period=requested, entity_id="",
                      active_finding_id="", finding_ids=(), selected_finding_from_collection=False)
            return True
        if operation == "timestamp" and period_phrase:
            _timestamp_period_unavailable(skill, message, state, language)
            return True
        if operation == "trend" or period_phrase:
            # A dated value is a trend, as _metric_read_resolution routes it.
            trend = skill.dispatcher._run_async(_service(skill).trend(
                period_phrase, requested, metric=metric,
                allow_history_fallback=not (period_phrase or period is not None),
                period_phrase=period_phrase,
            ))
            return _speak_trend(skill, message, state, trend, requested, language, period_phrase)
        return _speak_metric_read(skill, message, state, metric, language,
                                  value_only=operation == "value",
                                  timestamp_only=operation == "timestamp")

    skill._safe_dispatch("handle_reneryo_query", execute)
    return True


def _ground_metric_reference(skill, utterance: str):
    """Resolve named/aliased metrics only from the live Reneryo inventory."""
    text = normalize_phrase(utterance)
    if _meter_reference(text):
        return None
    try:
        rows = skill.dispatcher._run_async(_service(skill).metrics())
    except (AdapterError, ValidationError):
        return None
    references = metric_references(utterance, rows)
    return references[0] if len(references) == 1 else None


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
