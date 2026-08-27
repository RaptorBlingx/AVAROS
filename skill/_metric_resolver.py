"""Metric resolution helpers for free-form utterance parsing."""

from __future__ import annotations

import re

from skill.domain.models import CanonicalMetric
from skill.services.language import normalize_phrase

_UTTERANCE_PHRASE_MAP: tuple[tuple[CanonicalMetric, tuple[str, ...]], ...] = (
    (
        CanonicalMetric.STORAGE_STATE_OF_CHARGE,
        (
            "battery state of charge",
            "battery charge level",
            "storage state of charge",
            "storage charge level",
            "battery soc",
        ),
    ),
    (CanonicalMetric.STORAGE_POWER, ("battery power", "storage power")),
    (
        CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL,
        (
            "grid import energy",
            "energy imported from grid",
            "imported energy",
            "grid bought energy",
        ),
    ),
    (
        CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL,
        (
            "grid export energy",
            "energy exported to grid",
            "exported energy",
            "grid sold energy",
        ),
    ),
    (CanonicalMetric.GRID_POWER, ("grid power", "grid exchange power")),
    (
        CanonicalMetric.ENERGY_PRODUCTION_TOTAL,
        (
            "total production energy",
            "produced energy",
            "generated energy",
            "production energy",
        ),
    ),
    (
        CanonicalMetric.PRODUCTION_POWER,
        (
            "production power",
            "generated power",
            "generation power",
        ),
    ),
    (
        CanonicalMetric.CONSUMPTION_POWER,
        (
            "consumption power",
            "power consumption",
            "consumed power",
            "current demand",
            "current consumption",
        ),
    ),
    (
        CanonicalMetric.OEE,
        (
            "oee",
            "overall equipment effectiveness",
            "equipment effectiveness",
        ),
    ),
    (
        CanonicalMetric.SCRAP_RATE,
        (
            "scrap rate",
            "scrap",
            "waste rate",
            "waste",
        ),
    ),
    (
        CanonicalMetric.ENERGY_PER_UNIT,
        (
            "energy per unit",
            "power per unit",
            "electricity per unit",
            "energy consumption per unit",
            "specific energy",
            "specific power",
        ),
    ),
    (
        CanonicalMetric.ENERGY_TOTAL,
        (
            "total energy",
            "energy total",
            "total power",
            "total electricity",
            "energy consumption",
            "power consumption",
        ),
    ),
    (
        CanonicalMetric.PEAK_DEMAND,
        (
            "peak demand",
            "maximum demand",
            "max demand",
            "peak power demand",
        ),
    ),
    (CanonicalMetric.PEAK_TARIFF_EXPOSURE, ("peak tariff exposure", "tariff exposure")),
    (CanonicalMetric.REWORK_RATE, ("rework rate", "rework")),
    (CanonicalMetric.MATERIAL_EFFICIENCY, ("material efficiency",)),
    (CanonicalMetric.RECYCLED_CONTENT, ("recycled content",)),
    (CanonicalMetric.SUPPLIER_LEAD_TIME, ("supplier lead time", "lead time")),
    (CanonicalMetric.SUPPLIER_DEFECT_RATE, ("supplier defect rate", "defect rate")),
    (CanonicalMetric.SUPPLIER_ON_TIME, ("supplier on time", "on time delivery")),
    (
        CanonicalMetric.SUPPLIER_CO2_PER_KG,
        (
            "supplier co2 per kg",
            "supplier co 2 per kg",
            "supplier co two per kg",
            "supplier carbon dioxide per kilogram",
            "supplier emissions per kilogram",
        ),
    ),
    (CanonicalMetric.THROUGHPUT, ("throughput",)),
    (CanonicalMetric.CYCLE_TIME, ("cycle time",)),
    (CanonicalMetric.CHANGEOVER_TIME, ("changeover time", "change over time")),
    (
        CanonicalMetric.CO2_PER_UNIT,
        (
            "co2 per unit",
            "co 2 per unit",
            "co two per unit",
            "carbon dioxide per unit",
            "emissions per unit",
        ),
    ),
    (
        CanonicalMetric.CO2_TOTAL,
        (
            "co2 total",
            "co 2 total",
            "co two total",
            "total co2",
            "total co 2",
            "total co two",
            "total carbon",
            "total carbon emissions",
            "total emissions",
        ),
    ),
    (
        CanonicalMetric.CO2_PER_BATCH,
        (
            "co2 per batch",
            "co 2 per batch",
            "co two per batch",
            "carbon dioxide per batch",
            "emissions per batch",
        ),
    ),
)

_TURKISH_PHRASE_MAP: tuple[tuple[CanonicalMetric, tuple[str, ...]], ...] = (
    (CanonicalMetric.STORAGE_STATE_OF_CHARGE, ("batarya doluluk oranı", "batarya şarj seviyesi", "depolama şarj durumu")),
    (CanonicalMetric.STORAGE_POWER, ("batarya gücü", "depolama gücü")),
    (CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL, ("şebekeden alınan enerji", "şebeke ithalat enerjisi")),
    (CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL, ("şebekeye verilen enerji", "şebeke ihracat enerjisi")),
    (CanonicalMetric.GRID_POWER, ("şebeke gücü", "şebeke alışveriş gücü")),
    (CanonicalMetric.ENERGY_PRODUCTION_TOTAL, ("toplam üretim enerjisi", "üretilen enerji")),
    (CanonicalMetric.PRODUCTION_POWER, ("üretim gücü", "üretilen güç")),
    (CanonicalMetric.CONSUMPTION_POWER, ("tüketim gücü", "güç tüketimi", "anlık tüketim")),
    (CanonicalMetric.OEE, ("oee", "toplam ekipman etkinliği", "ekipman etkinliği")),
    (CanonicalMetric.SCRAP_RATE, ("hurda oranı", "fire oranı", "atık oranı", "hurda", "fire")),
    (CanonicalMetric.ENERGY_PER_UNIT, ("birim başına enerji", "birim enerji tüketimi", "özgül enerji")),
    (CanonicalMetric.ENERGY_TOTAL, ("toplam enerji", "enerji tüketimi", "tüketilen enerji")),
    (CanonicalMetric.PEAK_DEMAND, ("pik talep", "maksimum talep", "en yüksek talep")),
    (CanonicalMetric.PEAK_TARIFF_EXPOSURE, ("pik tarife maruziyeti", "tarife maruziyeti")),
    (CanonicalMetric.REWORK_RATE, ("yeniden işleme oranı", "tekrar işleme oranı")),
    (CanonicalMetric.MATERIAL_EFFICIENCY, ("malzeme verimliliği",)),
    (CanonicalMetric.RECYCLED_CONTENT, ("geri dönüştürülmüş içerik", "geri dönüşüm oranı")),
    (CanonicalMetric.SUPPLIER_LEAD_TIME, ("tedarikçi teslim süresi", "tedarik süresi")),
    (CanonicalMetric.SUPPLIER_DEFECT_RATE, ("tedarikçi hata oranı", "tedarikçi kusur oranı")),
    (CanonicalMetric.SUPPLIER_ON_TIME, ("zamanında teslim oranı", "tedarikçi zamanında teslim")),
    (CanonicalMetric.SUPPLIER_CO2_PER_KG, ("tedarikçi kilogram başına karbon", "tedarikçi kilogram başına co2")),
    (CanonicalMetric.THROUGHPUT, ("üretim hızı", "çıktı hızı", "üretim miktarı")),
    (CanonicalMetric.CYCLE_TIME, ("çevrim süresi", "döngü süresi")),
    (CanonicalMetric.CHANGEOVER_TIME, ("ürün değişim süresi", "değişim süresi")),
    (CanonicalMetric.CO2_PER_UNIT, ("birim başına co2", "birim başına karbon")),
    (CanonicalMetric.CO2_TOTAL, ("toplam co2", "toplam karbon", "toplam karbon emisyonu")),
    (CanonicalMetric.CO2_PER_BATCH, ("parti başına co2", "parti başına karbon")),
)


def resolve_metric_from_utterance(utterance: str) -> CanonicalMetric | None:
    """Resolve canonical metric from free-form utterance.

    Args:
        utterance: Raw user utterance text.

    Returns:
        Matching canonical metric or ``None`` if not recognized.
    """
    if not utterance:
        return None

    normalized = normalize_phrase(utterance)

    co2_like = bool(
        re.search(r"\bco\s*2\b", normalized)
        or re.search(r"\bco2\b", normalized)
        or re.search(r"\bco\s*two\b", normalized)
        or "carbon dioxide" in normalized
        or "carbon emissions" in normalized
        or "carbon" in normalized
    )
    total_like = bool(
        "total" in normalized
        or re.search(r"\btot\w*\b", normalized)
        or "emissions" in normalized
    )
    batch_like = "batch" in normalized
    if co2_like and total_like:
        return CanonicalMetric.CO2_TOTAL
    if co2_like and batch_like:
        return CanonicalMetric.CO2_PER_BATCH

    for metric, phrases in _TURKISH_PHRASE_MAP:
        if any(phrase in normalized for phrase in phrases):
            return metric

    energy_total_like = (
        "per unit" not in normalized
        and (
            re.search(r"\benergy\b(?:\s+\w+){0,3}\s+\b(?:consumed|used)\b", normalized)
            or re.search(r"\b(?:consume|consumed|use|used)\b(?:\s+\w+){0,3}\s+\benergy\b", normalized)
        )
    )
    if energy_total_like:
        return CanonicalMetric.ENERGY_TOTAL

    # Resolve directional live-energy language before the broad bare
    # ``energy``/``power`` fallbacks below. These word orders are common in
    # natural questions but are not contiguous noun phrases.
    if "power" in normalized and re.search(
        r"\b(?:produc(?:e|es|ing|ed)|generat(?:e|es|ing|ed))\b", normalized
    ):
        return CanonicalMetric.PRODUCTION_POWER
    if "energy" in normalized and "grid" in normalized and re.search(
        r"\b(?:import(?:s|ing|ed)?|bought|buy)\b", normalized
    ):
        return CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL
    if "energy" in normalized and "grid" in normalized and re.search(
        r"\b(?:export(?:s|ing|ed)?|sold|sell)\b", normalized
    ):
        return CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL
    if "energy" in normalized and re.search(
        r"\b(?:produc(?:e|es|ing|ed)|generat(?:e|es|ing|ed))\b", normalized
    ):
        return CanonicalMetric.ENERGY_PRODUCTION_TOTAL

    # Verb phrasing commonly used for live energy systems does not contain
    # the noun "consumption", e.g. "How much power is the site consuming?".
    if "power" in normalized and re.search(r"\bconsum(?:e|es|ing|ed)\b", normalized):
        return CanonicalMetric.CONSUMPTION_POWER

    for metric, phrases in _UTTERANCE_PHRASE_MAP:
        if any(phrase in normalized for phrase in phrases):
            return metric

    for metric in CanonicalMetric:
        canonical_phrase = metric.value.replace("_", " ")
        if canonical_phrase in normalized:
            return metric

    # Bare "co2" or "carbon" without qualifier → default to co2_per_unit
    if co2_like:
        return CanonicalMetric.CO2_PER_UNIT

    # Bare "energy" or "power" without qualifier → default to energy_per_unit
    if re.search(r"\benergy\b", normalized) or re.search(r"\bpower\b", normalized):
        return CanonicalMetric.ENERGY_PER_UNIT

    return None
