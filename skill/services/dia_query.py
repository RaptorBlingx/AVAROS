"""Deterministic operation/entity parsing for manufacturing dialogue."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from enum import Enum

from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill._metric_resolver import resolve_metric_from_utterance
from skill.services.language import normalize_phrase
from skill.services.query_scope import asset_label_pattern, is_comparison_request


class QueryOperation(str, Enum):
    KPI = "kpi"
    SUMMARY = "summary"
    COMPARE = "compare"
    RANK = "rank"
    AVERAGE = "average"
    TREND = "trend"
    DEFINE = "define"
    TARGET = "target"
    DIAGNOSE = "diagnose"
    RECOMMEND = "recommend"
    WHAT_IF = "what_if"
    STATUS = "status"
    CAPABILITIES = "capabilities"
    CONTROL = "control"
    ANOMALY = "anomaly"
    DRIFT = "drift"
    FORECAST = "forecast"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StructuredQuery:
    operation: QueryOperation
    metrics: tuple[CanonicalMetric, ...]
    asset_ids: tuple[str, ...]
    period: TimePeriod | None
    aggregation: str
    detail_level: str
    ambiguity: str
    original_utterance: str
    scope_kind: str = ""


_METRIC_ALIASES: dict[CanonicalMetric, tuple[str, ...]] = {
    CanonicalMetric.OEE: ("oee", "overall equipment effectiveness", "equipment effectiveness"),
    CanonicalMetric.ENERGY_PER_UNIT: ("energy per unit", "specific energy", "power per unit"),
    CanonicalMetric.ENERGY_TOTAL: ("total energy", "energy consumed", "energy consumption", "power consumption"),
    CanonicalMetric.PEAK_DEMAND: ("peak demand", "maximum demand", "peak power"),
    CanonicalMetric.PEAK_TARIFF_EXPOSURE: ("peak tariff exposure", "tariff exposure"),
    CanonicalMetric.SCRAP_RATE: ("scrap rate", "scrap", "waste rate"),
    CanonicalMetric.REWORK_RATE: ("rework rate", "rework"),
    CanonicalMetric.MATERIAL_EFFICIENCY: ("material efficiency",),
    CanonicalMetric.RECYCLED_CONTENT: ("recycled content",),
    CanonicalMetric.SUPPLIER_LEAD_TIME: ("supplier lead time", "lead time"),
    CanonicalMetric.SUPPLIER_DEFECT_RATE: ("supplier defect rate", "supplier defects"),
    CanonicalMetric.SUPPLIER_ON_TIME: ("supplier on time", "on time delivery"),
    CanonicalMetric.SUPPLIER_CO2_PER_KG: ("supplier co2 per kg", "supplier carbon per kilogram"),
    CanonicalMetric.THROUGHPUT: ("throughput", "production rate"),
    CanonicalMetric.CYCLE_TIME: ("cycle time",),
    CanonicalMetric.CHANGEOVER_TIME: ("changeover time", "change over time"),
    CanonicalMetric.CO2_PER_UNIT: ("co2 per unit", "carbon per unit", "emissions per unit"),
    CanonicalMetric.CO2_TOTAL: ("total co2", "co2 total", "total carbon", "total emissions"),
    CanonicalMetric.CO2_PER_BATCH: ("co2 per batch", "carbon per batch"),
    CanonicalMetric.CONSUMPTION_POWER: (
        "consumption power", "power consumption", "consumed power",
        "current demand", "current consumption",
    ),
    CanonicalMetric.PRODUCTION_POWER: (
        "production power", "generated power", "generation power",
    ),
    CanonicalMetric.STORAGE_STATE_OF_CHARGE: (
        "battery state of charge", "battery charge level",
        "storage state of charge", "storage charge level", "battery soc",
    ),
    CanonicalMetric.STORAGE_POWER: ("battery power", "storage power"),
    CanonicalMetric.GRID_POWER: ("grid power", "grid exchange power"),
    CanonicalMetric.ENERGY_PRODUCTION_TOTAL: (
        "total production energy", "produced energy", "generated energy",
        "production energy",
    ),
    CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL: (
        "grid import energy", "energy imported from grid", "imported energy",
        "grid bought energy",
    ),
    CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL: (
        "grid export energy", "energy exported to grid", "exported energy",
        "grid sold energy",
    ),
}


def parse_structured_query(
    utterance: str,
    *,
    assets: list[Asset],
    prior=None,
    timezone_name: str = "UTC",
) -> StructuredQuery:
    """Resolve operation first, then every metric, asset, period, and scope."""
    text = normalize_phrase(utterance)
    operation = _resolve_operation(text)
    metrics = _resolve_metrics(text)
    if (
        not metrics
        and operation is QueryOperation.TREND
        and re.search(r"\benergy\b", text)
        and not re.search(r"\b(total|consumed|consumption)\b", text)
    ):
        # Preserve the established "energy trend" command as the normalized
        # energy-per-unit rate. Explicit consumption/total wording continues
        # to resolve to total energy.
        metrics = [CanonicalMetric.ENERGY_PER_UNIT]
    if not metrics and operation is QueryOperation.COMPARE:
        from skill._reneryo_handlers import _matches_registered_utterance

        # Preserve the existing compare.energy handler's metric contract for
        # its registered phrases. Explicit consumption already resolves to
        # ENERGY_TOTAL above and must never be replaced by this shorthand.
        if _matches_registered_utterance("compare.energy", text):
            metrics = [CanonicalMetric.ENERGY_PER_UNIT]
    asset_ids, scope_kind = _resolve_assets(text, assets)
    period, period_error = _resolve_period(text, timezone_name)

    configured_asset_keys = {
        _normalize(label)
        for asset in assets
        for label in (asset.asset_id, asset.display_name, *asset.aliases)
    }
    unknown_lines = [
        f"Line-{suffix}"
        for suffix in re.findall(r"\b(?:line|hat)[\s-]+(\d+)\b", text)
        if _normalize(f"Line-{suffix}") not in configured_asset_keys
    ]

    if prior is not None:
        if not metrics and _looks_like_follow_up(text):
            metrics = list(prior.metrics)
        if not asset_ids and _looks_like_follow_up(text):
            if "compare them" in text and prior.answer_evidence:
                asset_ids = list(dict.fromkeys(
                    str(row.get("asset_id", ""))
                    for row in prior.answer_evidence
                    if str(row.get("asset_id", ""))
                ))
            else:
                asset_ids = list(prior.asset_ids)
        if period is None and ("same period" in text or _looks_like_follow_up(text)):
            period = prior.period
        if operation is QueryOperation.UNKNOWN and _looks_like_follow_up(text):
            try:
                operation = QueryOperation(prior.operation)
            except ValueError:
                operation = QueryOperation.KPI
        if "what does that mean" in text:
            operation = QueryOperation.DEFINE
        if re.fullmatch(r"why\??", text):
            operation = QueryOperation.DIAGNOSE

    ambiguity = period_error
    if unknown_lines:
        available = ", ".join(asset.display_name for asset in assets[:10])
        ambiguity = f"{unknown_lines[0]} is not configured. Available assets: {available}."
    if "energy cost" in text or "cost of energy" in text:
        ambiguity = "Energy cost is not a configured canonical metric."
        metrics = []

    return StructuredQuery(
        operation=operation,
        metrics=tuple(metrics),
        asset_ids=tuple(asset_ids),
        period=period,
        aggregation=_requested_aggregation(text),
        detail_level="detailed" if "detail" in text else "normal",
        ambiguity=ambiguity,
        original_utterance=utterance,
        scope_kind=scope_kind,
    )


def is_manufacturing_query(query: StructuredQuery) -> bool:
    return bool(
        query.metrics
        or query.asset_ids
        or query.scope_kind
        or query.operation not in {QueryOperation.UNKNOWN, QueryOperation.STATUS, QueryOperation.CAPABILITIES}
    )


def _resolve_operation(text: str) -> QueryOperation:
    ordered = (
        (QueryOperation.CONTROL, r"\b(turn on|turn off|start|stop|power on|power off|aç|kapat|çalıştır|durdur)\b"),
        (QueryOperation.WHAT_IF, r"\b(what if|simulate|scenario|ne olur|simüle et|senaryo)\b"),
        (QueryOperation.ANOMALY, r"\b(anomal|unusual pattern|spike|anomali|olağan dışı)"),
        (QueryOperation.DRIFT, r"\b(drift|degradation|sapma|kademeli değiş)"),
        (QueryOperation.FORECAST, r"\b(forecast|predict|projection|tahmin|öngör|beklenen)"),
        (QueryOperation.DIAGNOSE, r"\b(why|cause|diagnos|explain the change)\b"),
        (QueryOperation.RECOMMEND, r"\b(recommend|what should|how can|improve)\b"),
        (QueryOperation.COMPARE, r"\b(compare|versus|vs\.?|difference between|karşılaştır|farkı)\b"),
        (QueryOperation.RANK, r"\b(rank|ranking|best|worst|top|bottom)\b"),
        (QueryOperation.TREND, r"\b(trend|trended|trending|changed|change over|over time|eğilim|nasıl değişti)\b"),
        (QueryOperation.DEFINE, r"\b(define|definition|what is|what does|calculated|calculation|formula)\b"),
        (QueryOperation.AVERAGE, r"\b(average|mean|ortalama)\b"),
        (QueryOperation.TARGET, r"\b(target|objective|goal|good|bad|acceptable|on track)\b"),
        (QueryOperation.SUMMARY, r"\b(summary|overview|factory performance|how is the factory|headline|özet|fabrika performansı)\b"),
        (QueryOperation.STATUS, r"\b(system status|data status|connection status|freshness|sistem durumu|bağlantı durumu)\b"),
        (QueryOperation.CAPABILITIES, r"\b(help|capabilities|what can you do|yardım|ne(?:ler)? yapabilirsin|yetenekler)\b"),
    )
    for operation, pattern in ordered:
        if re.search(pattern, text) or (
            operation is QueryOperation.COMPARE and is_comparison_request(text)
        ):
            if operation is QueryOperation.DEFINE and _resolve_metrics(text) and not re.search(
                r"\b(define|definition|what does|calculated|calculation|formula|mean)\b",
                text,
            ):
                continue
            return operation
    return QueryOperation.KPI if _resolve_metrics(text) else QueryOperation.UNKNOWN


def _resolve_metrics(text: str) -> list[CanonicalMetric]:
    normalized = text.replace("₂", "2")
    if "power" in normalized and re.search(
        r"\b(?:produc(?:e|es|ing|ed)|generat(?:e|es|ing|ed))\b", normalized
    ):
        return [CanonicalMetric.PRODUCTION_POWER]
    if "power" in normalized and re.search(r"\bconsum(?:e|es|ing|ed)\b", normalized):
        return [CanonicalMetric.CONSUMPTION_POWER]
    if "energy" in normalized and "grid" in normalized and re.search(
        r"\b(?:import(?:s|ing|ed)?|bought|buy)\b", normalized
    ):
        return [CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL]
    if "energy" in normalized and "grid" in normalized and re.search(
        r"\b(?:export(?:s|ing|ed)?|sold|sell)\b", normalized
    ):
        return [CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL]
    if "energy" in normalized and re.search(
        r"\b(?:produc(?:e|es|ing|ed)|generat(?:e|es|ing|ed))\b", normalized
    ):
        return [CanonicalMetric.ENERGY_PRODUCTION_TOTAL]
    if (
        "per unit" not in normalized
        and (
            re.search(r"\benergy\b(?:\s+\w+){0,3}\s+\b(?:consumed|used)\b", normalized)
            or re.search(r"\b(?:consume|consumed|use|used)\b(?:\s+\w+){0,3}\s+\benergy\b", normalized)
        )
    ):
        return [CanonicalMetric.ENERGY_TOTAL]
    matches: list[tuple[int, int, CanonicalMetric]] = []
    for metric, aliases in _METRIC_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            match = re.search(rf"\b{re.escape(alias)}\b", normalized)
            if match:
                matches.append((match.start(), -len(alias), metric))
                break
    matches.sort()
    resolved: list[CanonicalMetric] = []
    for _, _, metric in matches:
        if metric not in resolved:
            resolved.append(metric)
    if resolved:
        return resolved

    turkish_metric = resolve_metric_from_utterance(normalized)
    if turkish_metric is not None:
        return [turkish_metric]

    tokens = re.findall(r"[\w]+", normalized, flags=re.UNICODE)
    phrases = [alias for aliases in _METRIC_ALIASES.values() for alias in aliases]
    for width in (3, 2, 1):
        for index in range(len(tokens) - width + 1):
            candidate = " ".join(tokens[index:index + width])
            close = difflib.get_close_matches(candidate, phrases, n=1, cutoff=0.88)
            if close:
                alias = close[0]
                return [metric for metric, aliases in _METRIC_ALIASES.items() if alias in aliases]
    return []


def _resolve_assets(text: str, assets: list[Asset]) -> tuple[list[str], str]:
    if re.search(r"\b(all lines|every line|all assets|factory wide|factory-wide|tüm hatlar|bütün hatlar|tüm varlıklar)\b", text):
        return [asset.asset_id for asset in assets], "all_assets"
    found: list[tuple[int, str]] = []
    normalized_text = normalize_phrase(text)
    for asset in assets:
        labels = [asset.asset_id, asset.display_name, *asset.aliases]
        positions = [
            match.start()
            for label in labels if _normalize(label)
            for match in re.finditer(
                asset_label_pattern(label), normalized_text
            )
        ]
        if positions:
            found.append((min(position for position in positions if position >= 0), asset.asset_id))
    found.sort()
    resolved = list(dict.fromkeys(asset_id for _, asset_id in found))
    if resolved:
        return resolved, ""
    if "supplier" in text:
        suppliers = [asset.asset_id for asset in assets if asset.asset_type == "supplier"]
        return suppliers, "suppliers"
    return [], ""


def _resolve_period(text: str, timezone_name: str) -> tuple[TimePeriod | None, str]:
    patterns = (
        r"\b(?:bugün|dün|bu hafta|geçen hafta|son hafta|son (?:2|iki) hafta|bu ay|geçen ay|son ay|son (?:30|otuz) gün|şimdi|şu anda|en güncel)\b",
        r"\b(?:ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\s+\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\s+(?:ile|ila)\s+\d{4}-\d{2}-\d{2}(?:\s+arası)?\b",
        r"\b(?:today|yesterday|this week|last week|this month|last month|past month|past \d+ days|last \d+ days|right now|latest|current)\b",
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\s+(?:to|through|until)\s+\d{4}-\d{2}-\d{2}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return TimePeriod.from_natural_language(
                match.group(0),
                timezone_name=timezone_name,
            ), ""
        except ValueError as exc:
            return None, str(exc)
    if re.search(
        r"\b(next|tomorrow|quarter|year|before|after|since|until)\b",
        text,
    ):
        return (
            None,
            (
                "Unsupported time period. Try today, yesterday, last week, "
                "last month, past 30 days, a named month, or an explicit date range."
            ),
        )
    return None, ""


def _requested_aggregation(text: str) -> str:
    if re.search(r"\b(total|sum|toplam)\b", text):
        return "sum"
    if re.search(r"\b(peak|maximum|max|pik|maksimum)\b", text):
        return "max"
    if re.search(r"\b(average|mean|ortalama)\b", text):
        return "average"
    if re.search(r"\b(current|latest|right now)\b", text):
        return "latest"
    return ""


def _looks_like_follow_up(text: str) -> bool:
    return bool(re.match(r"^(and|what about|how about|use the same|compare them|why|what does that mean)\b", text))


def _normalize(value: str) -> str:
    normalized = normalize_phrase(value).replace("-", " ")
    number_words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "bir": "1",
        "iki": "2",
        "üç": "3",
        "dört": "4",
        "beş": "5",
        "altı": "6",
        "yedi": "7",
        "sekiz": "8",
        "dokuz": "9",
    }
    for word, digit in number_words.items():
        normalized = re.sub(rf"\b{word}\b", digit, normalized)
    return normalized
