"""Natural bilingual explanations for structured MDSP findings."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from skill.domain.reneryo_models import MdspFinding
from skill.services.language import is_turkish, normalize_phrase, format_localized_number, format_observation_time

_CONTINUITY_RULE = "metric-source-recent-continuity"
_FRESHNESS_RULE = "metric-resource-relative-freshness"
_REGRESSION_CADENCE_RULE = "regression-driver-cadence-compatibility"
_REGRESSION_FIT_RULE = "regression-model-fit-quality"
_REGRESSION_PRIMARY_RULE = "regression-primary-model-availability"


def finding_headline(
    finding: MdspFinding,
    text: str,
    language: str,
    *,
    action: str = "",
    timezone_name: str | None = None, include_timezone: bool = False,
) -> str:
    """Return a natural deterministic answer for one finding turn."""
    normalized = normalize_phrase(text)
    if action == "finding.period" or _has(
        normalized, "period", "window", "donem", "dönem", "zaman"
    ):
        return _period_explanation(finding, language, timezone_name, include_timezone)
    if action == "finding.entity" or _has(
        normalized, "entity", "affect", "varlik", "varlık", "etkiliyor"
    ):
        return _entity_explanation(finding, language)
    if action == "finding.evidence" or _has(normalized, "evidence", "kanit", "kanıt"):
        return _evidence_explanation(finding, language, timezone_name, include_timezone)
    if action == "finding.trigger" or _has(
        normalized,
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
        return _trigger_explanation(finding, language)
    return _finding_explanation(finding, language)


def _finding_explanation(finding: MdspFinding, language: str) -> str:
    evidence = finding.evidence
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        source = _source_name(evidence.get("source"))
        resources = _integer(evidence.get("affectedResourceCount"))
        duration = _gap_duration(evidence.get("longestGap"), language)
        single = resources == 1 and _integer(evidence.get("recentGapCount")) == 1
        gap_label = "önemli veri boşluğu" if single else "önemli veri boşlukları"
        if turkish:
            return (
                f"MDSP, {resources} {source} kaynağında {gap_label} buldu. "
                f"En uzun boşluk {duration} sürdü. Bu aralıkta veri kapsamı eksik; nedeni henüz belirlenmiş değil."
            )
        noun = "resource" if resources == 1 else "resources"
        return (
            f"MDSP found {'a significant data gap' if single else 'significant data gaps'} in {resources} {source} {noun}. "
            f"The longest lasted {duration}. Observation coverage is incomplete over this interval; the cause is unconfirmed."
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
                f"tespit etti. Bu kaynağın güncel izleme için kullanılabilirliği doğrulanmalı.{detail}"
            )
        detail = (
            " Another source for the same metric is current, so this finding is "
            "low severity."
            if sibling_current
            else ""
        )
        return (
            f"MDSP found that this source's latest observation for {metric} is "
            f"about {lag} hours behind the latest data in Reneryo. Its suitability for current monitoring needs review.{detail}"
        )
    if finding.rule_id == _REGRESSION_CADENCE_RULE:
        driver = _first_driver(evidence)
        cadence_days = _cadence_days(driver.get("fastestCadenceSeconds"))
        driver_name = str(driver.get("name") or "a regression driver")
        if turkish:
            period = _period_name(evidence.get("period"), turkish=True)
            return (
                f"MDSP, {period} model döneminin dayandığı veriden daha ayrıntılı olduğunu tespit etti. "
                f"{driver_name} yaklaşık {cadence_days} günde bir güncelleniyor; uygun model dönemi incelenmeli."
            )
        period = _period_name(evidence.get("period"), turkish=False)
        return (
            f"MDSP found that the {period} model period is finer than its supporting data. "
            f"The {driver_name} driver updates about every {cadence_days} days; the appropriate model period needs review."
        )
    if finding.rule_id == _REGRESSION_FIT_RULE:
        r_squared = _optional_number(evidence.get("rSquared"))
        normalized_rmse = _optional_number(evidence.get("normalizedRmsePct"))
        r_text = format_localized_number(r_squared, language, ".3f") if r_squared is not None else ("yok" if turkish else "missing")
        error_text = (f"%{format_localized_number(normalized_rmse, language, '.1f')}" if turkish else f"{normalized_rmse:.1f}%") if normalized_rmse is not None else ("yok" if turkish else "unavailable")
        if turkish:
            return (
                "Bu kayıtlı regresyon modeli geçici uyum kalitesi inceleme sınırına takıldı. "
                f"R²: {r_text}; normalize hata: {error_text}. Modelin amaçlanan kullanımına uygunluğu incelenmeli; bu bulgu yerine başka bir model seçmez."
            )
        return (
            "This saved regression model crossed a provisional fit-quality review gate. "
            f"R-squared: {r_text}; normalized error: {error_text}. Its suitability for the intended use needs review; this finding does not select a replacement model."
        )
    if finding.rule_id == _REGRESSION_PRIMARY_RULE:
        results = _integer(evidence.get("resultCount"))
        seu_name = str(evidence.get("seuName") or ("bu SEU" if turkish else "this SEU"))
        if turkish:
            return (
                f"{seu_name} için {results} kayıtlı uygun regresyon sonucu var ancak "
                "hiçbiri birincil değil. Birincil sonuç gerekip gerekmediği iş politikasıyla doğrulanmalıdır."
            )
        return (
            f"{seu_name} has {results} eligible saved regression {'result' if results == 1 else 'results'}, but none "
            "is primary. Whether one is required needs business confirmation."
        )
    title = _clean_text(finding.title.for_language(language), finding)
    summary = _clean_text(finding.summary.for_language(language), finding)
    return f"{_sentence(title)} {_sentence(summary)}".strip()


def _evidence_explanation(finding: MdspFinding, language: str, timezone_name: str | None = None, include_timezone: bool = False) -> str:
    evidence = finding.evidence
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        source = _source_name(evidence.get("source"))
        resources = _integer(evidence.get("affectedResourceCount"))
        gaps = _integer(evidence.get("recentGapCount"))
        gap = _mapping(evidence.get("longestGap"))
        duration = _gap_duration(gap, language)
        start = _time(gap.get("start"), language, timezone_name, include_timezone)
        end = _time(gap.get("end"), language, timezone_name, include_timezone)
        if turkish:
            return (
                f"Kanıtlar, {resources} {source} kaynağında kaynak başına en fazla {gaps} "
                f"yakın tarihli önemli boşluk olduğunu gösteriyor. En uzun boşluk {start} ile "
                f"{end} arasında {duration} sürdü."
            )
        return (
            f"The evidence shows up to {gaps} recent significant "
            f"{'gap' if gaps == 1 else 'gaps'} per resource across {resources} "
            f"{source} {'resource' if resources == 1 else 'resources'}. The longest ran from {start} to {end} and "
            f"lasted {duration}."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        metric = str(evidence.get("metricName") or finding.metric_name or "the metric")
        observed = _time(evidence.get("lastObservationAt"), language, timezone_name, include_timezone)
        watermark = _time(evidence.get("sourceWatermark") or finding.source_watermark, language, timezone_name, include_timezone)
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
                f"Kanıtlar model döneminin {period}, {driver_name} açıklayıcı değişkeninin "
                f"gözlenen güncelleme sıklığının ise yaklaşık {cadence_days} gün "
                "olduğunu gösteriyor."
            )
        period = _period_name(evidence.get("period"), turkish=False)
        return (
            f"The evidence shows a {period} model period, while {driver_name} "
            f"updates only about every {cadence_days} days."
        )
    if finding.rule_id == _REGRESSION_FIT_RULE:
        r_squared = _optional_number(evidence.get("rSquared"))
        min_r_squared = _number(evidence.get("minimumRSquared"))
        normalized_rmse = _optional_number(evidence.get("normalizedRmsePct"))
        max_rmse = _number(evidence.get("maximumNormalizedRmsePct"))
        r_text = format_localized_number(r_squared, language, ".3f") if r_squared is not None else ("yok" if turkish else "missing")
        error_text = f"%{format_localized_number(normalized_rmse, language, '.1f')}" if normalized_rmse is not None else ("yok" if turkish else "unavailable")
        if turkish:
            return (
                f"Modelin R² değeri {r_text}; geçici alt sınır "
                f"{format_localized_number(min_r_squared, language, '.2f')}. Normalize hata {error_text}; "
                f"geçici üst sınır %{max_rmse:.0f}."
            )
        return (
            f"The model's R-squared is {r_text} (provisional minimum {min_r_squared:.2f}); "
            f"normalized error is {error_text} (provisional maximum {max_rmse:.0f}%)."
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


def _trigger_explanation(finding: MdspFinding, language: str) -> str:
    """Explain the deterministic rule condition separately from its meaning."""
    evidence = finding.evidence
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        gaps = _integer(evidence.get("recentGapCount"))
        duration = _gap_duration(evidence.get("longestGap"), language)
        if turkish:
            return (
                "Bu kural, son 30 günde bir boşluk hem gözlenen veri sıklığının "
                "altı katını hem de altı saati aştığında tetiklenir. Bu kaynakta "
                f"kaynak başına en fazla {gaps} boşluk eşiği aştı; en uzunu {duration} sürdü."
            )
        return (
            "This rule triggers when a gap in the latest 30 days exceeds both "
            "six observed cadences and six hours. Here, "
            f"up to {gaps} {'gap' if gaps == 1 else 'gaps'} per resource crossed that threshold, and the longest lasted "
            f"{duration}."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        lag = round(_number(evidence.get("lagHours")))
        allowed = round(_number(evidence.get("allowedLagHours")))
        cadence_hours = _number(evidence.get("inferredCadenceSeconds")) / 3600
        sibling_current = bool(evidence.get("currentSiblingResourceId"))
        cadence_text = _duration_hours(cadence_hours, turkish=turkish)
        if turkish:
            severity = (
                "Aynı metrik için başka bir kaynak güncel olduğundan önem düzeyi düşüktür."
                if sibling_current
                else ""
            )
            return (
                "Kural, kaynak gecikmesi 48 saat ile gözlenen veri sıklığının üç "
                f"katından büyük olan sınırı aştığında tetiklenir. Gözlenen sıklık "
                f"yaklaşık {cadence_text}, izin verilen gecikme {allowed} saat ve "
                f"gerçek gecikme {lag} saatti. {severity}"
            ).strip()
        severity = (
            " Another source for the same metric is current, so the severity is low."
            if sibling_current
            else ""
        )
        return (
            "The rule triggers when source lag exceeds the larger of 48 hours "
            "or three observed cadences. The observed cadence was about "
            f"{cadence_text}, the allowed lag was {allowed} hours, and the actual "
            f"lag was {lag} hours.{severity}"
        )
    if finding.rule_id == _REGRESSION_CADENCE_RULE:
        driver = _first_driver(evidence)
        driver_name = str(driver.get("name") or "the driver")
        driver_days = _number(driver.get("fastestCadenceSeconds")) / 86400
        model_days = _number(driver.get("regressionPeriodSeconds")) / 86400
        limit_days = model_days * 1.5
        if turkish:
            return (
                "Kural, bir açıklayıcı değişkenin gözlenen veri sıklığı model döneminin 1,5 "
                f"katından yavaş olduğunda tetiklenir. {driver_name} yaklaşık "
                f"{_number_text(driver_days)} günde bir güncellenirken bu model için "
                f"izin verilen sınır {_number_text(limit_days).replace('.', ',')} gündür."
            )
        return (
            "The rule triggers when an observed driver cadence is slower than "
            f"1.5 times the model period. {driver_name} updates about every "
            f"{_number_text(driver_days)} days, while this model's limit is "
            f"{_number_text(limit_days)} days."
        )
    if finding.rule_id == _REGRESSION_FIT_RULE:
        r_squared = _optional_number(evidence.get("rSquared"))
        min_r_squared = _number(evidence.get("minimumRSquared"))
        normalized_rmse = _optional_number(evidence.get("normalizedRmsePct"))
        max_rmse = _number(evidence.get("maximumNormalizedRmsePct"))
        conditions: list[str] = []
        if r_squared is None:
            conditions.append("R² değeri yok" if turkish else "R-squared is missing")
        elif r_squared < min_r_squared:
            conditions.append(
                f"R² {format_localized_number(r_squared, language, '.3f')}, {format_localized_number(min_r_squared, language, '.2f')} alt sınırının altında"
                if turkish
                else f"R-squared is {r_squared:.3f}, below {min_r_squared:.2f}"
            )
        if normalized_rmse is not None and normalized_rmse > max_rmse:
            conditions.append(
                f"normalize hata %{format_localized_number(normalized_rmse, language, '.1f')}, %{max_rmse:.0f} üst sınırının üzerinde"
                if turkish
                else f"normalized error is {normalized_rmse:.1f}%, above {max_rmse:.0f}%"
            )
        joined = _join_conditions(conditions, turkish=turkish)
        if turkish:
            return (
                "Bu geçici kural, R² 0,30'un altında olduğunda, R² olmadığında veya "
                f"normalize hata %25'i aştığında tetiklenir. Bu modelde {joined}."
            )
        return (
            "This provisional rule triggers when R-squared is below 0.30 or "
            "missing, or normalized error exceeds 25%. For this model, "
            f"{joined}."
        )
    if finding.rule_id == _REGRESSION_PRIMARY_RULE:
        results = _integer(evidence.get("resultCount"))
        primary = _integer(evidence.get("primaryCount"))
        if turkish:
            return (
                "Kural, kayıtlı regresyon sonuçları bulunduğu halde hiçbiri "
                f"birincil olmadığında tetiklenir. Burada {results} sonuç ve "
                f"{primary} birincil model var."
            )
        return (
            "The rule triggers when saved regression results exist but none is "
            f"marked primary. Here, there are {results} results and {primary} "
            "primary models."
        )
    return _finding_explanation(finding, language)


def _period_explanation(finding: MdspFinding, language: str, timezone_name: str | None = None, include_timezone: bool = False) -> str:
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        gap = _mapping(finding.evidence.get("longestGap"))
        start = _time(gap.get("start"), language, timezone_name, include_timezone)
        end = _time(gap.get("end"), language, timezone_name, include_timezone)
        window_start = _time(finding.evaluation_start, language, timezone_name, include_timezone)
        window_end = _time(finding.evaluation_end, language, timezone_name, include_timezone)
        duration = _gap_duration(gap, language)
        if turkish:
            return (
                f"Değerlendirme aralığı {window_start} ile {window_end}. "
                f"En uzun boşluk {start} ile {end} arasında {duration} sürdü. "
                "Kural, bitişi değerlendirme aralığına giren boşlukları seçer; süre boşluğun tamamına aittir ve başlangıcı bu aralıktan önce olabilir."
            )
        return (
            f"The evaluation window is {window_start} to {window_end}. "
            f"The longest gap ran from {start} to {end}, lasting {duration}. "
            "The rule selects gaps whose end falls in the lookback window; the duration covers the whole gap, which may start before that window."
        )
    if finding.rule_id == _FRESHNESS_RULE:
        observed = _time(finding.evidence.get("lastObservationAt"), language, timezone_name, include_timezone)
        watermark = _time(
            finding.evidence.get("sourceWatermark") or finding.source_watermark,
            language, timezone_name, include_timezone,
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
    start = _time(finding.evaluation_start, language, timezone_name, include_timezone)
    end = _time(finding.evaluation_end, language, timezone_name, include_timezone)
    if turkish:
        return (
            f"Bu bulgu {start} ile {end} arasındaki veri kullanılarak değerlendirildi."
        )
    return f"This finding was evaluated using data from {start} to {end}."


def _entity_explanation(finding: MdspFinding, language: str) -> str:
    turkish = is_turkish(language)
    if finding.rule_id == _CONTINUITY_RULE:
        source = _source_name(finding.evidence.get("source"))
        affected = finding.evidence.get("affectedMetrics")
        names = []
        if isinstance(affected, list):
            names = [
                str(item.get("name", "")).strip()
                for item in affected
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ]
        metrics = ", ".join(names)
        if turkish:
            return (
                f"Bu bulgu {source} entegrasyon kaynağını ve {len(names)} metriği "
                f"etkiliyor: {metrics}."
            )
        return (
            f"This finding affects the {source} integration source and "
            f"{len(names)} {'metric' if len(names) == 1 else 'metrics'}: {metrics}."
        )
    if finding.rule_id in {_REGRESSION_CADENCE_RULE, _REGRESSION_FIT_RULE}:
        period = _period_name(finding.evidence.get("period"), turkish=turkish)
        drivers = _driver_names(finding.evidence)
        driver_text = ", ".join(drivers) or (
            "açıklayıcı değişken bilgisi yok" if turkish else "no named driver"
        )
        if turkish:
            return (
                f"Bu bulgu {finding.entity_id} kimlikli {period} gelişmiş regresyon "
                f"sonucunu etkiliyor. Sürücü: {driver_text}."
            )
        return (
            f"This finding affects the {period} advanced-regression result "
            f"{finding.entity_id}. Its driver is {driver_text}."
        )
    label = (
        finding.metric_name or _source_name(finding.entity_id) or finding.entity_type
    )
    if turkish:
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


def _driver_names(evidence: dict[str, Any]) -> list[str]:
    values = evidence.get("drivers") or evidence.get("incompatibleDrivers")
    if not isinstance(values, list):
        return []
    return [
        str(item.get("name", "")).strip()
        for item in values
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]


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


def _optional_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _number_text(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _duration_hours(value: float, *, turkish: bool) -> str:
    if value >= 24:
        days = value / 24
        return f"{_number_text(days)} gün" if turkish else f"{_number_text(days)} days"
    return f"{_number_text(value)} saat" if turkish else f"{_number_text(value)} hours"


def _join_conditions(values: list[str], *, turkish: bool) -> str:
    if not values:
        return "eşik koşulu sağlandı" if turkish else "a review threshold was met"
    if len(values) == 1:
        return values[0]
    conjunction = " ve " if turkish else " and "
    return conjunction.join(values)


def _gap_duration(value: Any, language: str) -> str:
    seconds = _optional_number(_mapping(value).get("durationSeconds"))
    if seconds is None or seconds < 0:
        return "bilinmeyen bir süre" if is_turkish(language) else "an unknown duration"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if is_turkish(language):
        return (f"{hours} saat" + (f" {minutes} dakika" if minutes else "")) if hours else f"{minutes} dakika"
    parts = []
    if hours:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes or not parts:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    return " ".join(parts)


def _cadence_days(value: Any) -> int:
    return max(1, round(_number(value) / 86400))


def _period_name(value: Any, *, turkish: bool) -> str:
    normalized = str(value or "configured").strip().upper()
    if turkish:
        return {"DAILY": "günlük", "WEEKLY": "haftalık", "MONTHLY": "aylık"}.get(
            normalized, "yapılandırılmış"
        )
    return normalized.lower()


def _time(value: Any, language: str, timezone_name: str | None, include_timezone: bool = False) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return "bilinmeyen bir zaman" if is_turkish(language) else "an unknown time"
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    return format_observation_time(parsed, language, timezone_name, include_timezone=include_timezone)


def _has(text: str, *words: str) -> bool:
    return any(normalize_phrase(word) in text for word in words)
