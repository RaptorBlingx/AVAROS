"""Natural bilingual explanations for structured MDSP findings."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from skill.domain.reneryo_models import MdspFinding
from skill.services.language import is_turkish, normalize_phrase

_CONTINUITY_RULE = "metric-source-recent-continuity"
_FRESHNESS_RULE = "metric-resource-relative-freshness"
_REGRESSION_CADENCE_RULE = "regression-driver-cadence-compatibility"
_REGRESSION_FIT_RULE = "regression-model-fit-quality"
_REGRESSION_PRIMARY_RULE = "regression-primary-model-availability"


def finding_headline(finding: MdspFinding, text: str, language: str) -> str:
    """Return a natural deterministic answer for one finding turn."""
    normalized = normalize_phrase(text)
    if _has(normalized, "period", "window", "donem", "dönem", "zaman"):
        return _period_explanation(finding, language)
    if _has(normalized, "entity", "affect", "varlik", "varlık", "etkiliyor"):
        return _entity_explanation(finding, language)
    if _has(normalized, "evidence", "kanit", "kanıt"):
        return _evidence_explanation(finding, language)
    return _finding_explanation(finding, language)


def _finding_explanation(finding: MdspFinding, language: str) -> str:
    evidence = finding.evidence
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        source = _source_name(evidence.get("source"))
        resources = _integer(evidence.get("affectedResourceCount"))
        gaps = _integer(evidence.get("recentGapCount"))
        hours = _gap_hours(evidence.get("longestGap"))
        if turkish:
            return (
                f"MDSP, son 30 günlük izleme döneminde {resources} {source} "
                f"kaynağını etkileyen {gaps} önemli veri boşluğu buldu. En uzun "
                f"boşluk yaklaşık {hours} saat sürdü."
            )
        return (
            f"MDSP found {gaps} significant data gaps affecting {resources} "
            f"{source} resources during the latest 30-day monitoring window. "
            f"The longest gap lasted about {hours} hours."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        metric = str(evidence.get("metricName") or finding.metric_name or "the metric")
        lag = round(_number(evidence.get("lagHours")))
        sibling_current = bool(evidence.get("currentSiblingResourceId"))
        if turkish:
            detail = (
                " Aynı metriğin başka bir kaynağı güncel olduğu için bulgunun "
                "önem düzeyi düşüktür."
                if sibling_current
                else ""
            )
            return (
                f"MDSP, {metric} için bu kaynağın son gözleminin Reneryo'daki "
                f"en güncel verinin yaklaşık {lag} saat gerisinde olduğunu "
                f"tespit etti.{detail}"
            )
        detail = (
            " Another source for the same metric is current, so this finding is "
            "low severity."
            if sibling_current
            else ""
        )
        return (
            f"MDSP found that this source's latest observation for {metric} is "
            f"about {lag} hours behind the latest data in Reneryo.{detail}"
        )
    if finding.rule_id == _REGRESSION_CADENCE_RULE:
        driver = _first_driver(evidence)
        cadence_days = _cadence_days(driver.get("fastestCadenceSeconds"))
        driver_name = str(driver.get("name") or "a regression driver")
        if turkish:
            period = _period_name(evidence.get("period"), turkish=True)
            return (
                f"MDSP, {period} dönemli regresyonun {driver_name} sürücüsünden "
                f"daha sık çalıştığını tespit etti. Sürücü yaklaşık {cadence_days} "
                "günde bir güncellendiği için model dönemi veri sıklığından daha ayrıntılıdır."
            )
        period = _period_name(evidence.get("period"), turkish=False)
        return (
            f"MDSP found that the {period} regression runs more frequently than "
            f"its {driver_name} driver updates. The driver updates about every "
            f"{cadence_days} days, so the model period is finer than its supporting data."
        )
    if finding.rule_id == _REGRESSION_FIT_RULE:
        r_squared = _number(evidence.get("rSquared"))
        normalized_rmse = _number(evidence.get("normalizedRmsePct"))
        if turkish:
            return (
                "MDSP bu kayıtlı regresyon modelinin uyum kalitesinin gözden "
                f"geçirilmesini öneriyor. R² değeri {r_squared:.3f}, normalize "
                f"hata ise %{normalized_rmse:.1f}."
            )
        return (
            "MDSP recommends reviewing this saved regression model because its "
            f"fit quality is weak: R-squared is {r_squared:.3f} and normalized "
            f"error is {normalized_rmse:.1f}%."
        )
    if finding.rule_id == _REGRESSION_PRIMARY_RULE:
        results = _integer(evidence.get("resultCount"))
        if turkish:
            return (
                f"MDSP {results} kayıtlı gelişmiş regresyon sonucu buldu, ancak "
                "sürekli karar desteği için hiçbiri birincil model olarak seçilmemiş."
            )
        return (
            f"MDSP found {results} saved advanced regression results, but none "
            "is selected as the primary model for ongoing decision support."
        )
    title = _clean_text(finding.title.for_language(language), finding)
    summary = _clean_text(finding.summary.for_language(language), finding)
    return f"{_sentence(title)} {_sentence(summary)}".strip()


def _evidence_explanation(finding: MdspFinding, language: str) -> str:
    evidence = finding.evidence
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        source = _source_name(evidence.get("source"))
        resources = _integer(evidence.get("affectedResourceCount"))
        gaps = _integer(evidence.get("recentGapCount"))
        gap = _mapping(evidence.get("longestGap"))
        hours = _gap_hours(gap)
        start = _time(gap.get("start"))
        end = _time(gap.get("end"))
        if turkish:
            return (
                f"Kanıtlar, {resources} {source} kaynağında {gaps} yakın tarihli "
                f"önemli boşluk olduğunu gösteriyor. En uzun boşluk {start} ile "
                f"{end} arasında yaklaşık {hours} saat sürdü."
            )
        return (
            f"The evidence shows {gaps} recent significant gaps across {resources} "
            f"{source} resources. The longest ran from {start} to {end} and "
            f"lasted about {hours} hours."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        metric = str(evidence.get("metricName") or finding.metric_name or "the metric")
        observed = _time(evidence.get("lastObservationAt"))
        watermark = _time(evidence.get("sourceWatermark") or finding.source_watermark)
        lag = round(_number(evidence.get("lagHours")))
        samples = _integer(evidence.get("observedSampleCount"))
        if turkish:
            return (
                f"{metric} için {samples} örnek incelendi. Bu kaynağın son gözlemi "
                f"{observed}, Reneryo kaynak veri zamanı ise {watermark}; aradaki "
                f"fark yaklaşık {lag} saat."
            )
        return (
            f"For {metric}, MDSP examined {samples} observations. This source's "
            f"latest observation was {observed}, while Reneryo's source watermark "
            f"was {watermark}, a lag of about {lag} hours."
        )
    if finding.rule_id == _REGRESSION_CADENCE_RULE:
        driver = _first_driver(evidence)
        driver_name = str(driver.get("name") or "the driver")
        cadence_days = _cadence_days(driver.get("fastestCadenceSeconds"))
        if turkish:
            period = _period_name(evidence.get("period"), turkish=True)
            return (
                f"Kanıtlar model döneminin {period}, {driver_name} sürücüsünün "
                f"gözlenen güncelleme sıklığının ise yaklaşık {cadence_days} gün "
                "olduğunu gösteriyor."
            )
        period = _period_name(evidence.get("period"), turkish=False)
        return (
            f"The evidence shows a {period} model period, while {driver_name} "
            f"updates only about every {cadence_days} days."
        )
    if finding.rule_id == _REGRESSION_FIT_RULE:
        r_squared = _number(evidence.get("rSquared"))
        min_r_squared = _number(evidence.get("minimumRSquared"))
        normalized_rmse = _number(evidence.get("normalizedRmsePct"))
        max_rmse = _number(evidence.get("maximumNormalizedRmsePct"))
        if turkish:
            return (
                f"Modelin R² değeri {r_squared:.3f}; geçici alt sınır "
                f"{min_r_squared:.2f}. Normalize hata %{normalized_rmse:.1f}; "
                f"geçici üst sınır %{max_rmse:.0f}."
            )
        return (
            f"The model's R-squared is {r_squared:.3f}, below the provisional "
            f"{min_r_squared:.2f} threshold. Its normalized error is "
            f"{normalized_rmse:.1f}%, above the provisional {max_rmse:.0f}% threshold."
        )
    if finding.rule_id == _REGRESSION_PRIMARY_RULE:
        results = _integer(evidence.get("resultCount"))
        primary = _integer(evidence.get("primaryCount"))
        if turkish:
            return (
                f"Kanıtlar {results} kayıtlı gelişmiş regresyon sonucu ve "
                f"{primary} birincil model olduğunu gösteriyor."
            )
        return (
            f"The evidence contains {results} saved advanced regression results "
            f"and {primary} primary models."
        )
    facts = _friendly_scalar_facts(evidence)
    if not facts:
        return (
            "Bu bulgu için yapılandırılmış kanıt mevcut."
            if turkish
            else "Structured evidence is available for this finding."
        )
    detail = "; ".join(facts[:4])
    return (
        f"Bu bulguyu destekleyen değerler: {detail}."
        if turkish
        else f"The values supporting this finding are: {detail}."
    )


def _period_explanation(finding: MdspFinding, language: str) -> str:
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        gap = _mapping(finding.evidence.get("longestGap"))
        start = _time(gap.get("start"))
        end = _time(gap.get("end"))
        hours = _gap_hours(gap)
        if turkish:
            return (
                "Bu bulgu, kuralın son 30 günlük yakın dönem penceresini kapsıyor. "
                f"Bulgu içindeki en uzun veri boşluğu {start} ile {end} arasında "
                f"yaklaşık {hours} saat sürdü."
            )
        return (
            "This finding covers the rule's most recent 30-day lookback window. "
            f"The longest gap in the finding ran from {start} to {end} and "
            f"lasted about {hours} hours."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        observed = _time(finding.evidence.get("lastObservationAt"))
        watermark = _time(
            finding.evidence.get("sourceWatermark") or finding.source_watermark
        )
        if turkish:
            return (
                f"Bu bulgu, kaynağın {observed} tarihli son gözlemini {watermark} "
                "tarihli Reneryo kaynak veri zamanıyla karşılaştırıyor."
            )
        return (
            f"This finding compares the source's latest observation at {observed} "
            f"with Reneryo's source watermark at {watermark}."
        )
    start = finding.evaluation_start.strftime("%Y-%m-%d %H:%M UTC")
    end = finding.evaluation_end.strftime("%Y-%m-%d %H:%M UTC")
    if turkish:
        return (
            f"Bu bulgu {start} ile {end} arasındaki veri kullanılarak değerlendirildi."
        )
    return f"This finding was evaluated using data from {start} to {end}."


def _entity_explanation(finding: MdspFinding, language: str) -> str:
    label = (
        finding.metric_name or _source_name(finding.entity_id) or finding.entity_type
    )
    if is_turkish(language):
        return (
            f"Bu bulgu {label} varlığını etkiliyor. Varlık kimliği {finding.entity_id}."
        )
    return f"This finding affects {label}. Its entity ID is {finding.entity_id}."


def _source_name(value: Any) -> str:
    raw = str(value or "the monitored").strip()
    if raw.upper() == "OPEN_WEATHER" or raw.lower() == "integration:open_weather":
        return "OpenWeather"
    return raw.replace("_", " ").strip().title()


def _clean_text(value: str, finding: MdspFinding) -> str:
    count = _integer(finding.evidence.get("affectedResourceCount"))
    resource_word = "resource" if count == 1 else "resources"
    cleaned = value.replace("resource(s)", resource_word)
    return re.sub(r"\bOPEN_WEATHER\b", "OpenWeather", cleaned)


def _sentence(value: str) -> str:
    stripped = value.strip()
    if not stripped or stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _friendly_scalar_facts(evidence: dict[str, Any]) -> list[str]:
    facts = []
    for key, value in evidence.items():
        if not isinstance(value, (str, int, float, bool)):
            continue
        label = re.sub(r"(?<!^)(?=[A-Z])", " ", key).replace("_", " ").lower()
        facts.append(f"{label}: {value}")
    return facts


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_driver(evidence: dict[str, Any]) -> dict[str, Any]:
    drivers = evidence.get("incompatibleDrivers")
    if isinstance(drivers, list) and drivers and isinstance(drivers[0], dict):
        return drivers[0]
    return {}


def _integer(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _gap_hours(value: Any) -> int:
    return round(_number(_mapping(value).get("durationSeconds")) / 3600)


def _cadence_days(value: Any) -> int:
    return max(1, round(_number(value) / 86400))


def _period_name(value: Any, *, turkish: bool) -> str:
    normalized = str(value or "configured").strip().upper()
    if turkish:
        return {"DAILY": "günlük", "WEEKLY": "haftalık", "MONTHLY": "aylık"}.get(
            normalized, "yapılandırılmış"
        )
    return normalized.lower()


def _time(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return "an unknown time"
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _has(text: str, *words: str) -> bool:
    return any(normalize_phrase(word) in text for word in words)
