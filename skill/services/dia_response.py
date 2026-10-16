"""Structured browser evidence attached to ordinary OVOS speak messages."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from skill.services.language import normalize_language_tag, is_turkish, metric_display_name, period_display_name, speech_text
from skill.domain.results import ComparisonResult, KPIResult, TrendResult, WhatIfResult


def speak_with_evidence(skill, headline: str, result: Any) -> None:
    """Speak a compatible headline and attach an inspectable evidence payload."""
    response = build_response_metadata(headline, result)
    response["language"] = normalize_language_tag(getattr(skill, "_response_language", "en-US"))
    language = response["language"]
    metric = getattr(result, "metric", None)
    if is_turkish(language):
        for row in response.get("evidence_rows", []):
            if metric is not None and "metric_label" in row:
                row["metric_label"] = metric_display_name(metric, language)
        if "period" in response:
            response["period"]["label"] = period_display_name(response["period"]["label"], language)
        if isinstance(result, KPIResult):
            name = metric_display_name(result.metric, language)
            response["suggested_follow_ups"] = [
                f"{result.asset_id} için {name} eğilimini göster",
                f"Tüm hatlar için {name} değerlerini karşılaştır",
            ]
        elif isinstance(result, ComparisonResult):
            name = metric_display_name(result.metric, language)
            response["suggested_follow_ups"] = [
                f"{name} değerleri neden farklı olabilir?",
                f"{result.winner_id} için {name} eğilimini göster",
            ]
    if isinstance(result, WhatIfResult):
        # Use the same typed assumptions in speech and widget details.
        assumption = skill.response_builder._format_whatif_assumptions(result)
        response["assumptions"] = [assumption] if assumption else []
        if is_turkish(language):
            for row, label in zip(response["evidence_rows"], ("Başlangıç", "Senaryo")):
                row["label"] = label
            response["warnings"] = [
                "Bu aritmetik senaryo karar desteği içindir; nedensel bir model değildir."
            ]
    response["speech_text"] = speech_text(headline, language)
    skill.speak(response["speech_text"], meta={"avaros_response": response})


def speak_information(
    skill,
    headline: str,
    *,
    language: str | None = None,
    response_type: str = "information",
    evidence_rows: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> None:
    """Speak non-result information with the same browser metadata contract."""
    language = normalize_language_tag(language or getattr(skill, "_response_language", "en-US"))
    response = {
        "response_type": response_type,
        "query_id": str(uuid.uuid4()),
        "headline": headline,
        "language": language,
        "evidence_rows": list(evidence_rows or []),
        "warnings": list(warnings or []),
        "assumptions": [],
        "suggested_follow_ups": list(suggestions or []),
    }
    response["speech_text"] = speech_text(headline, language)
    skill.speak(
        response["speech_text"],
        meta={"language": language, "avaros_response": response},
    )


def build_response_metadata(headline: str, result: Any) -> dict[str, Any]:
    """Convert supported canonical results to the browser response contract."""
    if isinstance(result, KPIResult):
        return _kpi_metadata(headline, result)
    if isinstance(result, ComparisonResult):
        return _comparison_metadata(headline, result)
    if isinstance(result, TrendResult):
        return _trend_metadata(headline, result)
    if isinstance(result, WhatIfResult):
        return _whatif_metadata(headline, result)
    return {
        "response_type": "information",
        "query_id": _query_id(result),
        "headline": headline,
        "evidence_rows": [],
        "warnings": [],
        "assumptions": [],
        "suggested_follow_ups": [],
    }


def clarification_metadata(headline: str, suggestions: list[str]) -> dict[str, Any]:
    """Build metadata for a deterministic clarification response."""
    return {
        "response_type": "clarification",
        "query_id": str(uuid.uuid4()),
        "headline": headline,
        "evidence_rows": [],
        "warnings": [],
        "assumptions": [],
        "suggested_follow_ups": suggestions,
    }


def _base(
    headline: str,
    result: Any,
    *,
    response_type: str,
    aggregation: str = "",
    source_profile: str = "",
    coverage_status: str = "complete",
    warnings: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    period = getattr(result, "period", None)
    return {
        "response_type": response_type,
        "query_id": _query_id(result),
        "headline": headline,
        "period": {
            "label": getattr(period, "display_name", ""),
            "start": _iso(getattr(period, "start", None)),
            "end": _iso(getattr(period, "end", None)),
        },
        "aggregation": aggregation,
        "source_profile": source_profile,
        "coverage_status": coverage_status,
        "evidence_rows": [],
        "source_times": {},
        "warnings": list(warnings),
        "assumptions": [],
        "suggested_follow_ups": [],
    }


def _kpi_metadata(headline: str, result: KPIResult) -> dict[str, Any]:
    payload = _base(
        headline,
        result,
        response_type="kpi",
        aggregation=result.aggregation,
        source_profile=result.source_profile,
        coverage_status=result.coverage_status,
        warnings=result.warnings,
    )
    payload["evidence_rows"] = [
        {
            "metric": result.metric.value,
            "metric_label": result.metric.display_name,
            "asset_id": result.asset_id,
            "value": result.value,
            "unit": result.unit,
            "sample_count": result.sample_count,
            "observation_time": _iso(result.source_observed_at),
        }
    ]
    payload["source_times"] = {
        "observed_at": _iso(result.source_observed_at),
        "first_observation": _iso(result.source_period_start),
        "last_observation": _iso(result.source_period_end),
        "retrieved_at": _iso(result.timestamp),
    }
    payload["suggested_follow_ups"] = [
        f"Show the {result.metric.display_name} trend for {result.asset_id}",
        f"Compare {result.metric.display_name} across all lines",
    ]
    return payload


def _comparison_metadata(headline: str, result: ComparisonResult) -> dict[str, Any]:
    payload = _base(
        headline,
        result,
        response_type="comparison",
        aggregation=result.aggregation,
        source_profile=result.source_profile,
        coverage_status=result.coverage_status,
        warnings=result.warnings,
    )
    payload["evidence_rows"] = [
        {
            "metric": result.metric.value,
            "metric_label": result.metric.display_name,
            "asset_id": item.asset_id,
            "value": item.value,
            "unit": result.unit,
            "rank": item.rank,
            "sample_count": item.sample_count,
            "observation_time": _iso(item.source_observed_at),
            "coverage_status": item.coverage_status,
        }
        for item in result.items
    ]
    payload["suggested_follow_ups"] = [
        f"Why might {result.metric.display_name} differ?",
        f"Show the {result.metric.display_name} trend for {result.winner_id}",
    ]
    return payload


def _trend_metadata(headline: str, result: TrendResult) -> dict[str, Any]:
    payload = _base(
        headline,
        result,
        response_type="trend",
        source_profile=result.source_profile,
        coverage_status=result.coverage_status,
        warnings=result.warnings,
    )
    payload["evidence_rows"] = [
        {
            "metric": result.metric.value,
            "metric_label": result.metric.display_name,
            "asset_id": result.asset_id,
            "value": point.value,
            "unit": point.unit,
            "observation_time": _iso(point.timestamp),
        }
        for point in result.data_points
    ]
    payload["source_times"] = {
        "first_observation": _iso(result.data_points[0].timestamp)
        if result.data_points
        else None,
        "last_observation": _iso(result.data_points[-1].timestamp)
        if result.data_points
        else None,
    }
    return payload


def _whatif_metadata(headline: str, result: WhatIfResult) -> dict[str, Any]:
    payload = _base(headline, result, response_type="what_if")
    payload["evidence_rows"] = [
        {"label": "Baseline", "value": result.baseline, "unit": result.unit},
        {"label": "Projected", "value": result.projected, "unit": result.unit},
    ]
    payload["assumptions"] = [
        f"{name}: {value:g}%" for name, value in result.factors.items()
    ]
    payload["warnings"] = [
        "Decision support only; this is a bounded arithmetic scenario, not a causal model."
    ]
    return payload


def _query_id(result: Any) -> str:
    return str(getattr(result, "recommendation_id", "") or uuid.uuid4())


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
