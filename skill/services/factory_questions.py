"""Read-only factory questions grounded in Reneryo's own dated aggregates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from skill.domain.models import TimePeriod
from skill.services.futuregen import match_metric, next_month
from skill.services.language import is_turkish, normalize_phrase
from skill.services.period_resolution import extract_period_phrase


@dataclass(frozen=True)
class FactoryRequest:
    kind: str
    metric_hint: str
    utterance: str


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


def classify_factory_question(utterance, state) -> FactoryRequest | None:
    text = normalize_phrase(utterance)
    # Keep evidence, policy and analysis requests in their established handlers.
    if _has(
        text,
        "finding",
        "bulgu",
        "rule",
        "kural",
        "regression",
        "regresyon",
        "meters",
        "sayaçlar",
        "sayaclar",
        "metrics",
        "metrikler",
        "why",
        "neden",
        "not",
        "değil",
        "degil",
        "weather",
        "temperature",
        "humidity",
        "hava",
        "sıcaklık",
        "nem",
        "turn off",
        "turn on",
        "shut",
        "stop",
        "start",
        "switch",
        "kapat",
        "aç",
        "durdur",
        "başlat",
    ):
        return None
    energy = _has(
        text,
        "electric",
        "elektrik",
        "energy",
        "enerji",
        "consumption",
        "tüket",
        "tuket",
    )
    production = _has(text, "production", "produce", "output", "üret", "uret")
    follow_up = (
        state.operation == "factory_history"
        and bool(state.metric_name)
        and _has(
            text,
            "and",
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
        )
    )
    if not energy and not production and not follow_up:
        return None
    hint = (
        "electricity" if energy else "production" if production else state.metric_name
    )
    if (
        follow_up
        and not energy
        and not production
        and state.period
        and not re.search(r"\b\d{4}\b", text)
    ):
        dated = f"{utterance} {state.period.start.year}"
        if extract_period_phrase(dated):
            utterance = dated
    if energy and production:
        return FactoryRequest("clarify", "", utterance)
    if _has(
        text,
        "forecast",
        "predict",
        "tahmin",
        "cost",
        "maliyet",
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
        "verim",
        "azalt",
        "maksimum",
        "maximum",
        "minimum",
        "average",
        "ortalama",
    ):
        return FactoryRequest("unsupported", hint, utterance)
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
        # Route a context-only trend using the retained metric as well.
        return None
    if _has(
        text,
        "updated",
        "update",
        "fresh",
        "last data",
        "last observation",
        "observation",
        "güncel",
        "guncel",
        "son veri",
        "ne zaman",
    ):
        return FactoryRequest("freshness", hint, utterance)
    if _has(
        text,
        "reading",
        "counter",
        "cumulative",
        "sayaç değeri",
        "sayac degeri",
        "birikimli",
        "değer",
        "deger",
    ):
        return FactoryRequest("reading", hint, utterance)
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
        return FactoryRequest("history", hint, utterance)
    if (
        energy
        or production
        or extract_period_phrase(utterance)
        or _has(text, "how much", "ne kadar", "show", "göster", "goster")
    ):
        return FactoryRequest("amount", hint, utterance)
    return None


async def answer_factory_question(service, request, period, language) -> FactoryAnswer:
    tr = is_turkish(language)
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
            headline += f"{metric.last_value:g}; {date}; {metric.unit_group}. "
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

    phrase = extract_period_phrase(request.utterance)
    year = re.search(r"\b(19\d{2}|20\d{2})\b", request.utterance)
    if year and not phrase:
        y = int(year.group(1))
        period = TimePeriod(
            datetime(y, 1, 1, tzinfo=timezone.utc),
            datetime(y + 1, 1, 1, tzinfo=timezone.utc),
            str(y),
        )
        phrase = str(y)
    explicit_window = bool(phrase and phrase not in {"latest", "en güncel"})
    points = (
        await service.reneryo.metric_values(
            metric.metric_id, period.start, period.end, "MONTHLY"
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
    if not points:
        points, total_count = await service.reneryo.recent_metric_values(metric)
    if not points:
        return FactoryAnswer(
            (
                "Reneryo dönem değerleri döndürmedi. "
                if tr
                else "Reneryo returned no period values. "
            )
            + (
                f"Son kayıt zamanı: {metric.last_value_at.isoformat()}."
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
            headline = "; ".join(f"{m.name}: {m.consumption:g}" for m in meters)
            headline += (
                ". Reneryo dönem tüketimi; gözlenen veriye dayanır, tam kapsam garantisi değildir."
                if tr
                else ". Reneryo period consumption from observed data; full coverage is not guaranteed."
            )
        return FactoryAnswer(
            prefix + f"{actual.display_name}: " + headline,
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
            "aggregation": "MONTHLY",
            "unit_group": metric.unit_group,
        }
        for p in points
    ]
    preview = "; ".join(f"{p.timestamp:%Y-%m}: {p.value:g}" for p in points[-3:])
    label = "Reneryo aylık dönem değerleri" if tr else "Reneryo monthly period values"
    headline = (
        prefix
        + f"{metric.name}, {actual.display_name}. {label}: {preview}. {metric.unit_group}. "
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
    return (
        f"{label} döneminde gözlem yok. Mevcut tarihsel veriyi gösteriyorum: "
        if tr
        else f"No observations for {label}. Showing available historical data instead: "
    )
