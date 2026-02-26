"""Metric resolution helpers for free-form utterance parsing."""

from __future__ import annotations

import re

from skill.domain.models import CanonicalMetric

_UTTERANCE_PHRASE_MAP: tuple[tuple[CanonicalMetric, tuple[str, ...]], ...] = (
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


def resolve_metric_from_utterance(utterance: str) -> CanonicalMetric | None:
    """Resolve canonical metric from free-form utterance.

    Args:
        utterance: Raw user utterance text.

    Returns:
        Matching canonical metric or ``None`` if not recognized.
    """
    if not utterance:
        return None

    normalized_utterance = (
        utterance.lower()
        .replace("₂", "2")
        .replace("₀", "0")
    )
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized_utterance)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    co2_like = bool(
        re.search(r"\bco\s*2\b", normalized)
        or re.search(r"\bco2\b", normalized)
        or re.search(r"\bco\s*two\b", normalized)
        or "carbon dioxide" in normalized
        or "carbon emissions" in normalized
    )
    total_like = bool(
        "total" in normalized
        or re.search(r"\btot\w*\b", normalized)
        or "emissions" in normalized
    )
    if co2_like and total_like:
        return CanonicalMetric.CO2_TOTAL

    for metric, phrases in _UTTERANCE_PHRASE_MAP:
        if any(phrase in normalized for phrase in phrases):
            return metric

    return None
