"""Execution layer for structured deterministic manufacturing dialogue."""

from __future__ import annotations

import uuid
from statistics import mean
from typing import Any

from skill._system_handlers import _status_freshness_clause
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.capability_manifest import build_capability_manifest
from skill.services.conversation_state import DialogueState, message_session_id
from skill.services.dia_query import QueryOperation, parse_structured_query
from skill.services.dia_response import (
    clarification_metadata,
    speak_information,
    speak_with_evidence,
)
from skill.services.metric_knowledge import get_metric_knowledge

_HEADLINE_METRICS = (
    CanonicalMetric.OEE,
    CanonicalMetric.THROUGHPUT,
    CanonicalMetric.SCRAP_RATE,
    CanonicalMetric.ENERGY_PER_UNIT,
    CanonicalMetric.CO2_TOTAL,
)


def try_handle_structured_query(skill, message, *, include_simple_kpi: bool = False) -> bool:
    """Parse and execute rich operations before legacy KPI intent fallback."""
    utterance = skill._extract_utterance_text(message).strip()
    if not utterance:
        return False
    store = getattr(skill, "_dialogue_state_store", None)
    session_id = message_session_id(message)
    prior = store.get(session_id) if store is not None else None
    assets = skill._get_asset_registry()
    query = parse_structured_query(
        utterance,
        assets=assets,
        prior=prior,
        timezone_name=_site_timezone(skill),
    )

    should_claim = (
        query.operation is not QueryOperation.UNKNOWN
        and (
            include_simple_kpi
            or query.operation is not QueryOperation.KPI
            or len(query.metrics) > 1
            or query.scope_kind == "all_assets"
            or _is_follow_up(utterance)
            or bool(query.ambiguity)
        )
    )
    if not should_claim:
        return False

    # Keep mature single-KPI period/cumulative-meter safeguards in the legacy
    # handler. The structured layer owns ambiguity, composites and follow-ups.
    if (
        query.operation is QueryOperation.KPI
        and len(query.metrics) == 1
        and (query.asset_ids or len(assets) == 1)
        and query.scope_kind != "all_assets"
        and not _is_follow_up(utterance)
        and not query.ambiguity
    ):
        return False

    # The existing deterministic what-if handler performs physical-range and
    # process-parameter validation; let the caller route through that path.
    if query.operation is QueryOperation.WHAT_IF:
        return False

    if query.ambiguity:
        _speak_clarification(skill, query.ambiguity, _period_suggestions())
        _remember(store, session_id, query, pending=query.ambiguity)
        return True

    if query.operation is QueryOperation.CONTROL:
        speak_information(skill,
            "AVAROS is read-only and cannot control equipment. "
            "Use the approved equipment control system and site safety procedure.",
            response_type="read_only_boundary",
        )
        _remember(store, session_id, query)
        return True

    if query.operation in {
        QueryOperation.ANOMALY,
        QueryOperation.DRIFT,
        QueryOperation.FORECAST,
    }:
        handler = {
            QueryOperation.ANOMALY: skill.handle_anomaly_check,
            QueryOperation.DRIFT: skill.handle_drift_check,
            QueryOperation.FORECAST: skill.handle_forecast_metric,
        }[query.operation]
        handler(message)
        _remember(store, session_id, query)
        return True

    if query.operation is QueryOperation.CAPABILITIES:
        _handle_capabilities(skill)
        _remember(store, session_id, query)
        return True

    if query.operation is QueryOperation.STATUS:
        _handle_status(skill)
        _remember(store, session_id, query)
        return True

    if query.operation is QueryOperation.DEFINE:
        if not query.metrics:
            _speak_clarification(skill, "Which manufacturing metric should I explain?", _metric_suggestions(skill))
            return True
        _handle_definition(skill, query.metrics)
        _remember(store, session_id, query)
        return True

    if query.scope_kind == "suppliers" and not query.asset_ids:
        speak_information(
            skill,
            "No supplier assets are configured in the active profile, so I cannot rank supplier performance.",
            response_type="unavailable_scope",
        )
        _remember(store, session_id, query, pending="supplier assets")
        return True

    metrics = list(query.metrics)
    is_default_summary = not metrics and query.operation is QueryOperation.SUMMARY
    if is_default_summary:
        supported = set(skill.dispatcher.adapter.get_supported_metrics())
        metrics = [metric for metric in _HEADLINE_METRICS if metric in supported]
    if not metrics:
        _speak_clarification(skill, "Which manufacturing metric do you mean?", _metric_suggestions(skill))
        _remember(store, session_id, query, pending="metric")
        return True

    asset_ids = list(query.asset_ids)
    if not asset_ids:
        if len(assets) == 1:
            asset_ids = [assets[0].asset_id]
        else:
            _speak_clarification(
                skill,
                "Which asset should I use?",
                [f"Use {asset.display_name}" for asset in assets[:3]],
            )
            _remember(store, session_id, query, pending="asset")
            return True

    # A factory-wide default headline intentionally uses the three core
    # production KPIs.  This keeps the spoken answer and first evidence card
    # responsive; explicit energy/carbon summary requests remain unrestricted.
    if is_default_summary and len(asset_ids) > 1:
        metrics = metrics[:3]

    period = query.period or TimePeriod.latest()
    if query.operation in {QueryOperation.COMPARE, QueryOperation.RANK, QueryOperation.AVERAGE}:
        if len(asset_ids) < 2:
            _speak_clarification(skill, "Please name at least two assets, or say all lines.", [])
            _remember(store, session_id, query, pending="comparison assets")
            return True
        _handle_composite_operation(skill, query.operation, metrics[0], asset_ids, period)
    elif query.operation is QueryOperation.SUMMARY or len(metrics) > 1:
        _handle_summary(skill, metrics, asset_ids, period)
    elif query.operation is QueryOperation.TARGET:
        _handle_target(skill, metrics[0], asset_ids[0], period)
    elif query.operation is QueryOperation.DIAGNOSE:
        _handle_diagnosis(skill, metrics[0], asset_ids, period)
    elif query.operation is QueryOperation.RECOMMEND:
        _handle_recommendation(skill, metrics[0], asset_ids[0], period)
    elif query.operation is QueryOperation.TREND:
        _handle_trends(skill, metrics[0], asset_ids, period)
    else:
        _handle_kpis(skill, metrics, asset_ids, period)

    remembered = DialogueState(
        metrics=tuple(metrics),
        asset_ids=tuple(asset_ids),
        period=period,
        operation=query.operation.value,
        answer_evidence=_conversation_candidates(prior, asset_ids, utterance),
    )
    if store is not None:
        store.put(session_id, remembered)
    return True


def _handle_kpis(skill, metrics, asset_ids, period) -> None:
    results = [
        skill.dispatcher.get_kpi(metric=metric, asset_id=asset_id, period=period)
        for asset_id in asset_ids
        for metric in metrics
    ]
    if len(results) == 1:
        text = skill.response_builder.format_kpi_result(results[0])
        speak_with_evidence(skill, text, results[0])
        return
    _speak_result_collection(skill, "KPI results", results)


def _handle_summary(skill, metrics, asset_ids, period) -> None:
    supported = set(skill.dispatcher.adapter.get_supported_metrics())
    selected = [metric for metric in metrics if metric in supported]
    requests = [
        (metric, asset_id, period)
        for asset_id in asset_ids
        for metric in selected
    ]
    outcomes = skill.dispatcher.get_kpis_batch(requests)
    results = [
        outcome for outcome in outcomes
        if not isinstance(outcome, BaseException)
    ]
    failures = [
        f"{asset_id}/{metric.display_name}: mapped value unavailable"
        for (metric, asset_id, _period), outcome in zip(requests, outcomes)
        if isinstance(outcome, BaseException)
    ]
    if not results:
        _speak_clarification(skill, "No mapped summary data was available for that scope.", [])
        return
    _speak_result_collection(skill, "Factory summary", results, warnings=failures)


def _handle_composite_operation(skill, operation, metric, asset_ids, period) -> None:
    result = skill.dispatcher.compare(metric=metric, asset_ids=asset_ids, period=period)
    if operation is QueryOperation.AVERAGE:
        average_value = mean(item.value for item in result.items)
        values = "; ".join(f"{item.asset_id} {item.value:g} {result.unit}" for item in result.items)
        text = (
            f"The all-asset average {metric.display_name} is {average_value:g} {result.unit} "
            f"for {period.display_name}. Values: {values}."
        )
    else:
        text = skill.response_builder.format_comparison_result(result)
    speak_with_evidence(skill, text, result)


def _handle_definition(skill, metrics) -> None:
    parts = []
    for metric in metrics:
        knowledge = get_metric_knowledge(metric)
        parts.append(
            f"{metric.display_name.capitalize()}: {knowledge.definition} "
            f"{knowledge.formula} {knowledge.direction} Required data: {knowledge.data_requirements}"
        )
    speak_information(skill, " ".join(parts), response_type="definition")


def _handle_target(skill, metric, asset_id, period) -> None:
    result = skill.dispatcher.get_kpi(metric, asset_id, period)
    value = skill.response_builder.format_kpi_result(result)
    objective = None
    if skill.settings_service is not None and hasattr(skill.settings_service, "get_kpi_objective"):
        objective = skill.settings_service.get_kpi_objective(metric.value, asset_id)
    if not objective:
        text = f"{value} No site objective is configured for {metric.display_name}, so I cannot rate it as good or bad."
        speak_with_evidence(skill, text, result)
        return

    target = _objective_target(objective)
    if target is None:
        text = f"{value} The configured objective is incomplete, so I cannot calculate a target gap."
        speak_with_evidence(skill, text, result)
        return
    comparator = str(objective.get("comparator", "at_least"))
    meets = result.value >= target if comparator == "at_least" else result.value <= target
    gap = abs(result.value - target)
    direction = "meets" if meets else "does not meet"
    text = (
        f"{value} It {direction} the configured objective of {target:g} {result.unit}; "
        f"the absolute gap is {gap:g} {result.unit}."
    )
    speak_with_evidence(skill, text, result)


def _objective_target(objective: dict[str, Any]) -> float | None:
    try:
        if objective.get("mode") == "improvement_from_baseline":
            baseline = float(objective["baseline_value"])
            improvement = float(objective["improvement_percent"]) / 100.0
            if objective.get("comparator") == "at_most":
                return baseline * (1 - improvement)
            return baseline * (1 + improvement)
        return float(objective["target_value"])
    except (KeyError, TypeError, ValueError):
        return None


def _handle_diagnosis(skill, metric, asset_ids, period) -> None:
    related = {
        CanonicalMetric.OEE: (CanonicalMetric.THROUGHPUT, CanonicalMetric.SCRAP_RATE, CanonicalMetric.CYCLE_TIME),
        CanonicalMetric.ENERGY_PER_UNIT: (CanonicalMetric.THROUGHPUT, CanonicalMetric.CYCLE_TIME),
        CanonicalMetric.SCRAP_RATE: (CanonicalMetric.REWORK_RATE, CanonicalMetric.OEE),
    }.get(metric, ())
    supported = set(skill.dispatcher.adapter.get_supported_metrics())
    evidence = []
    for asset_id in asset_ids:
        for candidate in (metric, *related):
            if candidate not in supported:
                continue
            try:
                evidence.append(skill.dispatcher.get_kpi(candidate, asset_id, period))
            except Exception:
                continue
    if not evidence:
        _speak_clarification(skill, "I do not have aligned evidence to investigate that question.", [])
        return
    values = "; ".join(
        f"{row.asset_id} {row.metric.display_name} {row.value:g} {row.unit}"
        for row in evidence
    )
    text = (
        f"I cannot establish a root cause from these KPI observations alone. Evidence: {values}. "
        "These may identify contributors to inspect, but correlation is not proven causation."
    )
    _speak_result_collection(skill, text, evidence)


def _handle_recommendation(skill, metric, asset_id, period) -> None:
    result = skill.dispatcher.get_kpi(metric, asset_id, period)
    playbooks = {
        CanonicalMetric.OEE: "Inspect availability losses, speed losses, and quality losses against an aligned baseline.",
        CanonicalMetric.SCRAP_RATE: "Inspect defect categories, material lots, tooling, and process-setting changes for the same period.",
        CanonicalMetric.ENERGY_PER_UNIT: "Inspect production volume, idle running, cycle time, and high-load equipment over the same period.",
        CanonicalMetric.PEAK_DEMAND: "Inspect coincident high-load equipment and shiftable loads around the recorded peak.",
    }
    action = playbooks.get(metric, "Inspect the mapped source, period coverage, and related KPI trends before acting.")
    objective = None
    if skill.settings_service is not None and hasattr(skill.settings_service, "get_kpi_objective"):
        objective = skill.settings_service.get_kpi_objective(metric.value, asset_id)
    target = _objective_target(objective) if objective else None
    if target is None:
        objective_context = (
            "No objective is configured, so this is an inspection checklist, "
            "not a claim that performance is poor"
        )
    else:
        comparator = str(objective.get("comparator", "at_least"))
        meets = result.value >= target if comparator == "at_least" else result.value <= target
        gap = abs(result.value - target)
        objective_context = (
            f"The observation {'meets' if meets else 'misses'} the configured objective "
            f"of {target:g} {result.unit} with an absolute gap of {gap:g} {result.unit}"
        )
    text = (
        f"Advisory only: {action} {objective_context}; this does not establish that any item caused the result."
    )
    speak_with_evidence(skill, text, result)


def _handle_trends(skill, metric, asset_ids, period) -> None:
    results = [skill.dispatcher.get_trend(metric, asset_id, period) for asset_id in asset_ids]
    if len(results) == 1:
        text = skill.response_builder.format_trend_result(results[0])
        speak_with_evidence(skill, text, results[0])
        return
    directions = "; ".join(
        f"{result.asset_id} {result.direction} {abs(result.change_percent):g} percent"
        for result in results
    )
    text = f"{metric.display_name.capitalize()} trends for {period.display_name}: {directions}."
    _speak_meta(skill, text, results, response_type="trend_comparison")


def _handle_capabilities(skill) -> None:
    manifest = build_capability_manifest(skill.settings_service, skill.dispatcher.adapter)
    names = ", ".join(item["label"] for item in manifest["metrics"])
    analytics = manifest["prevention"]["available"]
    analytics_text = (
        "PREVENTION anomaly analytics is available."
        if analytics
        else "PREVENTION anomaly, drift, forecast, and proactive-alert analytics are unavailable."
    )
    speak_information(skill,
        f"For the active profile I can report, compare, rank, average, summarize, and trend: {names}. "
        f"I can explain metrics and provide read-only inspection guidance. {analytics_text} I cannot control equipment.",
        response_type="capabilities",
    )


def _handle_status(skill) -> None:
    adapter = skill.dispatcher.adapter
    connection = skill.dispatcher._run_async(adapter.test_connection())
    assets = skill._get_asset_registry(force_refresh=True)
    metrics = adapter.get_supported_metrics()
    state = "connected" if connection.success else "not connected"
    prevention = "available" if getattr(skill.dispatcher, "_prevention_client", None) else "unavailable"
    freshness = _status_freshness_clause(skill, assets, metrics)
    profile = skill._resolve_active_profile()
    headline = (
        f"The active data source is {state}. Active profile: {profile}. "
        f"Configured scope: {len(assets)} assets and {len(metrics)} metrics. "
        f"{freshness} "
        f"PREVENTION analytics is {prevention}. Connection check: {connection.message}"
    )
    speak_information(
        skill,
        headline,
        response_type="system_status",
        evidence_rows=[{
            "profile": profile,
            "connection": state,
            "asset_count": len(assets),
            "metric_count": len(metrics),
            "prevention_available": prevention == "available",
        }],
    )


def _speak_result_collection(skill, title, results, warnings=None) -> None:
    rows = [
        {
            "metric": result.metric.value,
            "metric_label": result.metric.display_name,
            "asset_id": result.asset_id,
            "value": result.value,
            "unit": result.unit,
            "sample_count": result.sample_count,
            "observation_time": result.source_observed_at.isoformat() if result.source_observed_at else None,
        }
        for result in results
    ]
    headline = title if title.endswith(".") else f"{title}: " + "; ".join(
        f"{row['asset_id']} {row['metric_label']} {row['value']:g} {row['unit']}"
        for row in rows[:3]
    ) + (f"; and {len(rows) - 3} more in the evidence card" if len(rows) > 3 else "") + "."
    _speak_meta(skill, headline, results, response_type="summary", warnings=warnings or [])


def _speak_meta(skill, headline, results, *, response_type, warnings=None) -> None:
    rows = []
    for result in results:
        if hasattr(result, "metric") and hasattr(result, "value"):
            rows.append({
                "metric": result.metric.value,
                "metric_label": result.metric.display_name,
                "asset_id": result.asset_id,
                "value": result.value,
                "unit": result.unit,
                "sample_count": getattr(result, "sample_count", 0),
                "observation_time": (
                    result.source_observed_at.isoformat()
                    if getattr(result, "source_observed_at", None)
                    else None
                ),
            })
    first = results[0] if results else None
    period = getattr(first, "period", None)
    skill.speak(headline, meta={"avaros_response": {
        "response_type": response_type,
        "query_id": getattr(first, "recommendation_id", "") or str(uuid.uuid4()),
        "headline": headline,
        "period": {
            "label": getattr(period, "display_name", ""),
            "start": getattr(period, "start", None).isoformat() if period else None,
            "end": getattr(period, "end", None).isoformat() if period else None,
        },
        "aggregation": getattr(first, "aggregation", ""),
        "source_profile": getattr(first, "source_profile", ""),
        "coverage_status": "partial" if warnings else "complete",
        "evidence_rows": rows,
        "warnings": list(warnings or []),
        "assumptions": [],
        "suggested_follow_ups": [],
    }})


def _speak_clarification(skill, headline: str, suggestions: list[str]) -> None:
    skill.speak(headline, meta={"avaros_response": clarification_metadata(headline, suggestions)})


def _remember(store, session_id, query, *, pending="") -> None:
    if store is None:
        return
    store.put(session_id, DialogueState(
        metrics=query.metrics,
        asset_ids=query.asset_ids,
        period=query.period,
        operation=query.operation.value,
        pending_clarification=pending,
    ))


def remember_kpi_result(skill, message, result) -> None:
    """Refresh dialogue context after a legacy single-KPI intent succeeds."""
    store = getattr(skill, "_dialogue_state_store", None)
    if store is None:
        return
    asset_id = str(getattr(result, "asset_id", "") or "").strip()
    evidence = ({"asset_id": asset_id},) if asset_id else ()
    store.put(message_session_id(message), DialogueState(
        metrics=(result.metric,),
        asset_ids=(asset_id,) if asset_id else (),
        period=result.period,
        operation=QueryOperation.KPI.value,
        answer_evidence=evidence,
    ))


def _metric_suggestions(skill) -> list[str]:
    try:
        metrics = skill.dispatcher.adapter.get_supported_metrics()
    except Exception:
        return []
    if not isinstance(metrics, list):
        return []
    return [f"Show {metric.display_name}" for metric in metrics[:3]]


def _period_suggestions() -> list[str]:
    return ["Use last month", "Use past 30 days", "Use 2026-07-01 to 2026-07-31"]


def _site_timezone(skill) -> str:
    try:
        config = skill.settings_service.get_profile(skill._resolve_active_profile())
        return str(config.extra_settings.get("site_timezone", "UTC") or "UTC") if config else "UTC"
    except Exception:
        return "UTC"


def _is_follow_up(utterance: str) -> bool:
    return utterance.lower().startswith(("and ", "what about", "how about", "why", "compare them", "use the same"))


def _conversation_candidates(prior, asset_ids: list[str], utterance: str) -> tuple[dict[str, Any], ...]:
    """Keep only asset identifiers needed by pronoun-based comparisons."""
    candidates: list[str] = []
    if prior is not None and _is_follow_up(utterance):
        candidates.extend(
            str(row.get("asset_id", ""))
            for row in prior.answer_evidence
            if str(row.get("asset_id", ""))
        )
        candidates.extend(prior.asset_ids)
    candidates.extend(asset_ids)
    return tuple({"asset_id": asset_id} for asset_id in dict.fromkeys(candidates[-6:]))


def is_browser_message(message) -> bool:
    """Return whether a message may use browser conversational fallback.

    The legacy Web UI keeps its existing eligibility behavior.  The embedded
    Reneryo widget is eligible only after the HiveMind proxy has validated its
    signed session and injected an organization claim; ``source`` and
    ``platform`` are routing hints, never an authority boundary.
    """
    context = getattr(message, "context", {}) or {}
    source = context.get("source")
    platform = str(context.get("platform", ""))
    if source == "avaros-web-ui" or platform.startswith("AVAROS-WebUI"):
        return True

    signed = context.get("reneryo_context")
    return (
        source == "avaros-widget"
        and platform.startswith("AVAROS-Widget")
        and isinstance(signed, dict)
        and bool(signed.get("organization_id"))
        and context.get("reneryo_widget_session_validated") is True
    )
