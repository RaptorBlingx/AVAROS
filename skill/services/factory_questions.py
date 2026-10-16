"""Read-only factory questions grounded in Reneryo's own dated aggregates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from skill.domain.models import TimePeriod
from skill.services.futuregen import match_metric, next_month
from skill.services.language import (
    is_turkish, normalize_phrase, period_display_name, format_localized_number, source_enum_label,
)
from skill.services.period_resolution import (
    extract_period_phrase,
    named_month_reference,
    remove_period_reference,
    unsupported_period_reference,
)


@dataclass(frozen=True)
class FactoryRequest:
    kind: str
    metric_hint: str
    utterance: str
    use_period: bool = False


@dataclass
class FactoryAnswer:
    headline: str
    response_type: str = "information"
    evidence: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    metric_name: str = ""
    period: TimePeriod | None = None


def _has(text, *terms):
    return any(re.search(rf"(?<!\w){re.escape(term)}", text) for term in terms)


def is_cost_request(utterance: str) -> bool:
    text = normalize_phrase(utterance)
    if _has(text, "finding", "bulgu", "rule", "kural", "regression", "regresyon"):
        return False
    return bool(re.search(r"\bTRY\b", utterance)) or bool(re.search(
        r"\b(?:cost\w*|paid|pay|payment\w*|bill\w*|spend|spent)\b|"
        r"\b(?:maliyet|öde|ode|fatura|ücret|ucret)\w*|"
        r"\b(?:para|lira(?:ya|yı|yi|lık|lik|dan|da)?|tl|eur|usd|euros?|dollars?)\b", text,
    ))


def cost_limitation_headline(language: str) -> str:
    return (
        "İstenen maliyet veya ödeme tutarı için doğrulanmış Reneryo verisi mevcut değil."
        if is_turkish(language)
        else "Verified Reneryo cost or payment data is not available for the requested amount."
    )


def is_freshness_question(text: str) -> bool:
    """Recognize last-observation questions, not a freshness policy judgment."""
    text = normalize_phrase(text)
    return (_has(text, "last") and _has(text, "observation")) or _has(
        text, "updated", "update", "fresh", "last data", "last observation",
        "son veri", "ne zaman", "how old", "recorded", "is current",
        "consumption current", "ne kadar eski", "ne kadar güncel",
        "ne kadar guncel", "güncel mi", "guncel mi", "up to date",
        "how recent", "last received", "last refreshed",
    )


def is_historical_change_question(text: str) -> bool:
    """Bounded past-change questions reuse the existing historical trend path."""
    text = normalize_phrase(text)
    if _has(text, "settings", "configuration", "ayar", "price", "cost", "maliyet"):
        return False
    return bool(re.search(
        r"\b(?:how (?:did|has|have)|did|has|have)\b.*"
        r"\b(?:change(?:d)?|increase(?:d)?|decrease(?:d)?)\b|"
        r"\bnasıl değiş(?:ti|miş)\b|\bnasil degis(?:ti|mis)\b|"
        r"\b(?:arttı|artti|azaldı|azaldi|yükseldi|yukseldi|düştü|dustu) m[ıi]\b|"
        r"\b(?:direction|go up|go down|rise|fall|gidişat\w*|gidisat\w*)\b|"
        r"\b(?:art|azal|yüksel|yuksel|düş|dus)(?:mış|mis|miş|mus|müş|muş)\b",
        text,
    ))


def classify_factory_question(utterance, state) -> FactoryRequest | None:
    text = normalize_phrase(utterance)
    # Findings, policy, regressions and weather keep their established dialogue.
    if _has(
        text,
        "finding",
        "bulgu",
        "rule",
        "kural",
        "regression",
        "regresyon",
        "why",
        "neden",
        "not",
        "değil",
        "degil",
        "weather",
        "temperature",
        "humidity",
        "sıcakl",
        "sicakl",
        "nem",
        "turn off",
        "turn on",
        "shut",
        "stop",
        "start machine",
        "switch off",
        "switch on",
        "kapat",
        "durdur",
        "başlat",
    ):
        return None
    resource = _has(
        text,
        "gas",
        "water",
        "steam",
        "fuel",
        "diesel",
        "coal",
        "oil",
        "compressed air",
        "doğalgaz",
        "dogalgaz",
        "gaz",
        "buhar",
        "yakıt",
        "yakit",
        "basınçlı hava",
        "basincli hava",
    ) or bool(re.search(r"\bsu(?:yun|yu|ya)?\b", text))
    if resource and _has(
        text,
        "consum",
        "tüket",
        "tuket",
        "reading",
        "counter",
        "history",
        "data",
        "geçmiş",
        "veri",
        "değer",
        "meter",
        "sayaç",
        "sayac",
    ):
        return FactoryRequest("scope_unavailable", "", utterance)
    if _has(text, "hava"):
        return None
    energy = _has(
        text, "electric", "elektrik", "elektriğ", "elektrig", "energy", "enerji"
    )
    consumption = _has(text, "consum", "tüket", "tuket", "kullan", "harca")
    production = _has(
        text, "production", "produce", "manufactur", "output", "üret", "uret"
    ) or bool(
        re.search(r"\b(?:how many|kaç|kac) (?:units|pieces|adet|parça|parca)\b", text)
    )
    context = (
        state.operation in {"factory_history", "trend"}
        and bool(state.metric_name)
        and _has(
            normalize_phrase(state.metric_name),
            "elektrik",
            "electric",
            "production",
            "üretim",
            "uretim",
        )
    )
    follow_up = context and (
        is_freshness_question(text)
        or is_historical_change_question(text)
        or
        _has(
            text,
            "and",
            "what about",
            "how about",
            "peki",
            "when",
            "ne zaman",
            "history",
            "geçmiş",
            "show",
            "göster",
            "latest",
            "son",
            "how much",
            "ne kadar",
            "trend",
            "eğilim",
            "data",
            "veri",
            "reading",
            "counter",
            "period",
            "dönem",
            "donem",
            "same",
            "aynı",
        )
        or named_month_reference(text)
        or text.rstrip("?")
        in {"production", "electricity", "üretim", "uretim", "elektrik", "elektriği"}
    )
    if not energy and not production and not consumption and not follow_up:
        return None
    hint = (
        "electricity"
        if energy or (consumption and not production)
        else "production" if production else state.metric_name
    )
    if energy and production:
        return FactoryRequest("clarify", "", utterance)
    if is_cost_request(utterance):
        return FactoryRequest("unsupported", hint, utterance)
    # Resource/entity qualifiers must never be discarded by the generic consumption alias.
    if _has(
        text,
        "gas",
        "water",
        "steam",
        "fuel",
        "diesel",
        "coal",
        "doğalgaz",
        "dogalgaz",
        "gaz",
        "buhar",
        "yakıt",
        "yakit",
    ) or re.search(r"\bsu(?:yun|yu|ya)?\b", text):
        return FactoryRequest("scope_unavailable", hint, utterance)
    # A calendar month without a year is usable only with an unambiguous retained year.
    if named_month_reference(text) and not re.search(r"\b\d{4}\b", text):
        if (
            not context
            or state.period is None
            or state.period.start.year
            != (state.period.end - timedelta(microseconds=1)).year
        ):
            return FactoryRequest("period_clarify", hint, utterance)
        utterance = f"{utterance} {state.period.start.year}"
    if unsupported_period_reference(utterance):
        return FactoryRequest("period_clarify", hint, utterance)
    if state.operation in {
        "finding",
        "regression_detail",
        "regression_clarification",
        "regressions",
    } and _has(text, "its", "this", "bunun", "onun"):
        return FactoryRequest("scope_unavailable", hint, utterance)
    phrase = extract_period_phrase(utterance)
    remainder = remove_period_reference(text)
    remainder = re.sub(r"\b(?:19|20)\d{2}\b", "", remainder)
    remainder = re.sub(
        r"\b(?:same period|that period|this period|aynı dönem|ayni donem|bu dönem|bu donem)\b",
        "",
        remainder,
    )
    remainder = re.sub(r"\b(?:the|a|an)\b", "", remainder)
    if phrase:
        from skill.services.period_resolution import _MONTH_NAMES

        remainder = re.sub(rf"\b(?:{_MONTH_NAMES})\b", "", remainder)
        remainder = re.sub(r"\b\d{1,2}\b", "", remainder)
    if _has(
        text,
        "line",
        "oven",
        "machine",
        "equipment",
        "department",
        "workshop",
        "fırın",
        "firin",
        "makine",
        "hatt",
        "hat ",
        "bölüm",
        "bolum",
    ):
        return FactoryRequest("scope_unavailable", hint, utterance)
    reading = _has(
        text,
        "reading",
        "counter",
        "cumulative",
        "sayaç değer",
        "sayac deger",
        "birikimli",
    ) or (_has(text, "değer", "deger") and not consumption and not production)
    if _has(text, "metric", "metrik", "metriğ", "metrig") or (
        _has(text, "meter", "sayaç", "sayac") and not reading and not consumption
    ):
        return None
    latest = _has(
        text, "latest", "current", "right now", "en güncel", "en guncel", "son"
    )
    use_period = bool(
        context
        and state.period
        and not latest
        and (
            follow_up
            or _has(text, "same period", "that period", "aynı dönem", "ayni donem")
        )
    )
    if _has(
        text,
        "forecast",
        "predict",
        "tahmin",
        "per unit",
        "birim başına",
        "oee",
        "carbon",
        "karbon",
        "peak",
        "power",
        "demand",
        "efficiency",
        "intensity",
        "savings",
        "save",
        "reduce",
        "tasarruf",
        "azalt",
        "maximum",
        "maksimum",
        "minimum",
        "average",
        "ortalama",
    ) or any(word.startswith("verim") and not word.startswith("verimiz")
             for word in text.split()):
        # veri+miz (our data) is not verim (efficiency). Keep the existing
        # efficiency boundary, including verimi/verimlilik/verimimiz forms.
        return FactoryRequest("unsupported", hint, utterance)
    if is_historical_change_question(text) or re.search(r"\bseyr(?:i|ini)\b", text):
        return FactoryRequest("trend", hint, utterance, use_period)
    if _has(
        text,
        "trend",
        "eğilim",
        "egilim",
        "increas",
        "decreas",
        "artıyor",
        "azalıyor",
        "compare",
        "karşılaştır",
        "karsilastir",
    ):
        return None
    if (
        state.operation == "trend"
        and follow_up
        and named_month_reference(text)
        and not energy
        and not production
    ):
        return FactoryRequest("trend", hint, utterance, True)
    if is_freshness_question(text):
        return FactoryRequest("freshness", hint, utterance)
    if context and _has(
        text,
        "what period",
        "which period",
        "period does",
        "hangi dönem",
        "hangi donem",
        "hangi tarih",
    ):
        return FactoryRequest("period", hint, utterance, True)
    if reading:
        return FactoryRequest("reading", hint, utterance, use_period)
    if _has(
        text,
        "history",
        "historical",
        "available",
        "data",
        "records",
        "geçmiş",
        "gecmis",
        "veri",
        "kayıt",
        "kayit",
    ):
        return FactoryRequest(
            "history",
            hint,
            utterance,
            use_period
            and _has(text, "same period", "that period", "aynı dönem", "ayni donem"),
        )
    return FactoryRequest("amount", hint, utterance, use_period)


async def answer_factory_question(service, request, period, language) -> FactoryAnswer:
    tr = is_turkish(language)
    if request.kind == "unsupported" and is_cost_request(request.utterance):
        return FactoryAnswer(cost_limitation_headline(language), "unavailable")
    suggestions = (
        [
            "En son elektrik tüketimini göster",
            "Üretim geçmişini göster",
            "Son elektrik değeri ne zaman kaydedildi?",
        ]
        if tr
        else [
            "Show latest electricity consumption",
            "Show production history",
            "When was the last electricity reading recorded?",
        ]
    )
    if request.kind in {"scope_unavailable", "period_clarify"}:
        message = (
            (
                "İstenen kaynak veya ekipman için doğrulanmış veri yok. Tesis toplam elektriğini bunun yerine göstermiyorum."
                if tr
                else "No verified data is available for the requested resource or equipment. I am not substituting whole-factory electricity."
            )
            if request.kind == "scope_unavailable"
            else (
                "İstenen dönemi kesinleştirin: ay ile yılı veya açık bir tarih aralığını belirtin. Dönemi değiştirmedim."
                if tr
                else "Please specify the requested month and year or an explicit date range. I have not changed the period."
            )
        )
        return FactoryAnswer(message, "clarification", suggestions=suggestions)
    if request.kind == "clarify":
        return FactoryAnswer(
            (
                "Elektrik veya üretim seçin; her biri için ayrı dönemli veri gösterebilirim."
                if tr
                else "Choose electricity or production so I can show its dated data separately."
            ),
            "clarification",
            suggestions=suggestions,
        )
    metrics = await service.metrics()
    metric = match_metric(request.metric_hint, metrics)
    group = (
        "ENERGY"
        if request.metric_hint == "electricity"
        else "PIECE" if request.metric_hint == "production" else ""
    )
    candidates = [
        m
        for m in metrics
        if group and m.unit_group == group and m.metric_type == "COUNTER"
    ]
    named = [
        m
        for m in metrics
        if m.name and normalize_phrase(m.name) in normalize_phrase(request.utterance)
    ]
    if len(named) == 1:
        metric = named[0]
    if len(candidates) > 1 and len(named) != 1:
        return FactoryAnswer(
            (
                "Birden fazla ölçüm var; lütfen adını seçin."
                if tr
                else "Multiple metrics match; please choose one by name."
            ),
            "clarification",
            evidence=[{"metric": m.name} for m in candidates],
            suggestions=[m.name for m in candidates],
        )
    if metric is None:
        return FactoryAnswer(
            (
                "Bu ölçüm mevcut Reneryo envanterinde bulunamadı."
                if tr
                else "That metric is not present in the current Reneryo inventory."
            ),
            suggestions=suggestions,
        )
    common = {"metric_name": metric.name, "suggestions": suggestions}
    if request.kind == "unsupported":
        return FactoryAnswer(
            (
                "Bu istek için doğrulanmış Reneryo hesaplaması mevcut değil. Tarihli tüketim, üretim veya geçmiş verisini gösterebilirim."
                if tr
                else "No verified Reneryo calculation is available for that request. I can show dated consumption, production or history instead."
            ),
            **common,
        )
    phrase = extract_period_phrase(request.utterance)
    explicit_window = request.use_period or bool(
        phrase and phrase not in {"latest", "en güncel"}
    )
    if request.kind == "period":
        return FactoryAnswer(
            f"{metric.name}: {period_display_name(period.display_name, language)}; {period.start.isoformat()} – {period.end.isoformat()}.",
            period=period,
            **common,
        )
    if request.kind in {"reading", "freshness"} and explicit_window:
        return FactoryAnswer(
            (
                f"{period_display_name(period.display_name, language)}: Bu erişim arayüzü tarihsel birikimli sayaç değerlerini veya tarihsel güncellik kayıtlarını sunmuyor; yalnızca son değer ve dönem toplamları mevcut. İstenen okumayı son değerle değiştirmedim."
                if tr
                else f"{period_display_name(period.display_name, language)}: This access interface does not expose historical cumulative readings or historical freshness snapshots; it provides the latest reading and period aggregates. I have not substituted the latest reading for the requested one."
            ),
            "unavailable",
            period=period,
            **common,
        )
    if request.kind in {"reading", "freshness"}:
        date = (
            metric.last_value_at.isoformat()
            if metric.last_value_at
            else ("bilinmiyor" if tr else "unknown")
        )
        headline = f"{metric.name}: "
        if request.kind == "freshness":
            headline += (
                f"son kayıt zamanı {date}."
                if tr
                else f"latest recorded timestamp {date}."
            )
        elif metric.last_value is None:
            headline += (
                "kayıtlı değer yok." if tr else "no recorded value is available."
            )
        else:
            headline += f"{format_localized_number(metric.last_value, language)}; {date}; {source_enum_label(metric.unit_group, language)}. "
            if metric.metric_type == "COUNTER":
                headline += (
                    "Bu birikimli sayaç değeridir, dönem tüketimi veya üretimi değildir."
                    if tr
                    else "This is a cumulative counter reading, not period consumption or production."
                )
        return FactoryAnswer(
            headline,
            evidence=[
                {
                    "metric": metric.name,
                    "recorded_at": date,
                    "value": metric.last_value,
                    "type": metric.metric_type,
                    "unit_group": metric.unit_group,
                }
            ],
            **common,
        )

    month_aligned = (
        period.start.day == period.end.day == 1
        and period.start.hour == period.end.hour == 0
        and period.start.minute == period.end.minute == 0
        and period.start.second == period.end.second == 0
    )
    aggregation = "MONTHLY" if month_aligned else "DAILY"
    if request.kind == "amount" and metric.unit_group == "ENERGY":
        aggregation = "DAILY" if (period.end - period.start).days > 7 else "HOURLY"
    points = (
        await service.reneryo.metric_values(
            metric.metric_id, period.start, period.end, aggregation
        )
        if explicit_window
        else []
    )
    fallback = explicit_window and not points
    total_count = None
    if (
        request.kind == "history"
        and _has(normalize_phrase(request.utterance), "all", "entire", "tüm", "tum")
        and not explicit_window
    ):
        points = await service.reneryo.metric_values(
            metric.metric_id,
            datetime(1900, 1, 1, tzinfo=timezone.utc),
            (
                metric.last_value_at + timedelta(days=1)
                if metric.last_value_at
                else datetime.now(timezone.utc)
            ),
            "MONTHLY",
        )
        total_count = len(points)
        aggregation = "MONTHLY"
    if not points:
        points, total_count = await service.reneryo.recent_metric_values(metric)
        aggregation = "MONTHLY"
    if not points:
        return FactoryAnswer(
            (
                "Reneryo dönem değerleri döndürmedi. "
                if tr
                else "Reneryo returned no period values. "
            )
            + (
                (f"Son kayıt zamanı: {metric.last_value_at.isoformat()}." if tr else f"Latest recorded timestamp: {metric.last_value_at.isoformat()}.")
                if metric.last_value_at
                else ""
            ),
            **common,
        )
    actual = (
        period
        if explicit_window and not fallback
        else TimePeriod(
            points[0].timestamp,
            next_month(points[-1].timestamp),
            f"{points[0].timestamp:%Y-%m} – {points[-1].timestamp:%Y-%m}",
        )
    )
    prefix = _fallback(period.display_name, tr) if fallback else ""
    if request.kind == "amount" and metric.unit_group == "ENERGY":
        # An unspecified or empty window gets the latest available monthly bucket.
        if not explicit_window or fallback:
            actual = TimePeriod(
                points[-1].timestamp,
                next_month(points[-1].timestamp),
                f"{points[-1].timestamp:%Y-%m}",
            )
        meters = [
            m for m in await service.meters(actual) if m.metric_id == metric.metric_id
        ]
        if (
            explicit_window
            and not fallback
            and (not meters or any(m.consumption is None for m in meters))
        ):
            historical, _ = await service.reneryo.recent_metric_values(metric)
            if historical:
                actual = TimePeriod(
                    historical[-1].timestamp,
                    next_month(historical[-1].timestamp),
                    f"{historical[-1].timestamp:%Y-%m}",
                )
                prefix = (
                    f"{period_display_name(period.display_name, language)}: Dönem tüketimi mevcut değil. Tarihli tarihsel tüketimi gösteriyorum: "
                    if tr
                    else f"{period_display_name(period.display_name, language)}: Period consumption is unavailable. Showing dated historical consumption instead: "
                )
                meters = [
                    m
                    for m in await service.meters(actual)
                    if m.metric_id == metric.metric_id
                ]
        rows = [
            {
                "meter": m.name,
                "consumption": m.consumption,
                "period_start": actual.start.isoformat(),
                "period_end": actual.end.isoformat(),
                "unit_group": metric.unit_group,
            }
            for m in meters
        ]
        if not meters or any(m.consumption is None for m in meters):
            headline = (
                "Reneryo bu dönem için sayaç tüketimi döndürmedi."
                if tr
                else "Reneryo returned no meter consumption for this period."
            )
        else:
            headline = "; ".join(f"{m.name}: {format_localized_number(m.consumption, language)}" for m in meters)
            headline += (
                ". Reneryo dönem tüketimi; gözlenen veriye dayanır, tam kapsam garantisi değildir."
                if tr
                else ". Reneryo period consumption from observed data; full coverage is not guaranteed."
            )
        return FactoryAnswer(
            prefix
            + (
                ("En son mevcut dönem " if tr else "Latest available period ")
                if not explicit_window
                else ""
            )
            + f"{period_display_name(actual.display_name, language)}: "
            + headline,
            evidence=rows,
            period=actual,
            **common,
        )
    if request.kind == "amount" and (not explicit_window or fallback):
        points = points[-1:]
        actual = TimePeriod(
            points[0].timestamp,
            next_month(points[0].timestamp),
            f"{points[0].timestamp:%Y-%m}",
        )
    rows = [
        {
            "time": p.timestamp.isoformat(),
            "value": p.value,
            "samples": p.sample_count,
            "aggregation": aggregation,
            "unit_group": metric.unit_group,
        }
        for p in points
    ]
    preview = "; ".join(
        f"{p.timestamp.isoformat() if aggregation != 'MONTHLY' else p.timestamp.strftime('%Y-%m')}: {format_localized_number(p.value, language)}"
        for p in points[-3:]
    )
    label = (
        ("Reneryo aylık dönem değerleri" if tr else "Reneryo monthly period values")
        if aggregation == "MONTHLY"
        else ("Reneryo günlük dönem değerleri" if tr else "Reneryo daily period values")
    )
    headline = (
        prefix
        + f"{metric.name}, {period_display_name(actual.display_name, language)}. {label}: {preview}. {source_enum_label(metric.unit_group, language)}. "
    )
    headline += (
        f"{len(points)} dönem gösteriliyor" if tr else f"Showing {len(points)} periods"
    )
    if total_count is not None:
        headline += (
            f"; toplam {total_count} mevcut dönem."
            if tr
            else f" of {total_count} available periods."
        )
    else:
        headline += "."
    headline += (
        " Gözlenen veriye dayanır; çok aylı toplam hesaplanmadı."
        if tr
        else " Based on observed data; no multi-month total has been calculated."
    )
    return FactoryAnswer(headline, evidence=rows, period=actual, **common)


def _fallback(label, tr):
    label = period_display_name(label, "tr-TR" if tr else "en-US")
    return (
        f"{label} döneminde gözlem yok. Mevcut tarihsel veriyi gösteriyorum: "
        if tr
        else f"No observations for {label}. Showing available historical data instead: "
    )
