"""Natural bilingual summaries for Future Gen inventory queries."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime

from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import (
    MdspFindingList,
    ReneryoMeter,
    ReneryoMetric,
    ReneryoRegression,
)
from skill.services.language import is_turkish


def reneryo_capabilities_headline(language: str) -> str:
    """Describe only the conversational capabilities in the Future Gen slice."""
    if is_turkish(language):
        return (
            "Future Gen için sayaçları, metrikleri, eğilimleri, regresyon "
            "analizlerini ve etkin MDSP bulgularını açıklayabilirim. Seçili bir "
            "bulgunun nedenini, kanıtını, dönemini ve ilgili varlığı da takip "
            "edebilirim. Türkçe ve İngilizce çalışırım; salt okunurum."
        )
    return (
        "For Future Gen, I can explain meters, metrics, trends, regression "
        "analyses, and active MDSP findings. I can also follow a selected "
        "finding through its trigger, evidence, period, affected entity, and "
        "related metric. I work in English and Turkish and am read-only."
    )


def regression_inventory_headline(
    rows: Iterable[ReneryoRegression], language: str
) -> str:
    """Describe saved models using only Reneryo-exposed metadata."""
    models = list(rows)
    turkish = is_turkish(language)
    if not models:
        return (
            "Reneryo'da kayıtlı regresyon modeli bulunmuyor."
            if turkish
            else "Reneryo has no saved regression models."
        )

    type_counts = Counter(row.regression_type.lower() for row in models)
    type_summary = _type_summary(type_counts, turkish=turkish)
    periods = _unique(_localized_period(row.period, turkish=turkish) for row in models)
    drivers = _unique(name for row in models for name in row.driver_names if name)
    r_squared = [row.r_squared for row in models if row.r_squared is not None]
    primary_count = sum(1 for row in models if row.primary)

    if turkish:
        headline = (
            f"Reneryo'da {len(models)} kayıtlı regresyon modeli var: {type_summary}."
        )
        if periods:
            headline += f" Model dönemleri {_natural_join(periods, turkish=True)}."
        if drivers:
            headline += f" Sürücüler: {_natural_join(drivers, turkish=True)}."
        if r_squared:
            headline += f" R² aralığı {_range(r_squared, turkish=True)}."
        headline += (
            f" {primary_count} model birincil olarak işaretli."
            if primary_count
            else " Hiçbiri birincil model olarak işaretli değil."
        )
        return headline

    headline = f"Reneryo has {len(models)} saved regression models: {type_summary}."
    if periods:
        headline += f" Their periods are {_natural_join(periods)}."
    if drivers:
        headline += f" Their drivers are {_natural_join(drivers)}."
    if r_squared:
        headline += f" R-squared ranges from {_range(r_squared)}."
    headline += (
        f" {primary_count} model is marked primary."
        if primary_count == 1
        else f" {primary_count} models are marked primary."
        if primary_count
        else " None is marked as the primary model."
    )
    return headline


def regression_detail_headline(row: ReneryoRegression, language: str) -> str:
    """Describe one saved model using only Reneryo-owned metadata."""
    turkish = is_turkish(language)
    drivers = _natural_join(list(row.driver_names), turkish=turkish) or "—"
    slices = _natural_join(list(row.slice_names), turkish=turkish) or "—"
    period = _localized_period(row.period, turkish=turkish)
    training = f"{row.train_start.date()} – {row.train_end.date()}"
    r_squared = f"{row.r_squared:.3f}" if row.r_squared is not None else "—"
    rmse = f"{row.rmse:.3f}" if row.rmse is not None else "—"
    if turkish:
        primary = "birincil" if row.primary else "birincil değil"
        regression_type = {
            "advanced": "gelişmiş",
            "linear": "doğrusal",
        }.get(row.regression_type.lower(), row.regression_type)
        return (
            f"Bu {regression_type} regresyon modeli {period} dönemlidir ve {primary}. "
            f"Sürücüler: {drivers}. Bağlı dilimler: {slices}. Eğitim dönemi {training}; "
            f"R² {r_squared}, RMSE {rmse}."
        )
    primary = "primary" if row.primary else "not primary"
    return (
        f"This {row.regression_type} regression model has a {period} period and is {primary}. "
        f"Drivers: {drivers}. Linked slices: {slices}. Its training period is {training}; "
        f"R-squared is {r_squared} and RMSE is {rmse}."
    )


def meter_inventory_headline(
    rows: Iterable[ReneryoMeter], period: TimePeriod, language: str
) -> str:
    """Describe meter identity and make a zero-period result unambiguous."""
    meters = list(rows)
    turkish = is_turkish(language)
    if not meters:
        return (
            "İstenen dönem için Reneryo'da sayaç bulunamadı."
            if turkish
            else "Reneryo returned no meters for the requested period."
        )

    names = _unique(row.name for row in meters if row.name)
    resources = _unique(row.energy_resource for row in meters if row.energy_resource)
    metrics = _unique(row.metric_name for row in meters if row.metric_name)
    slices = _unique(name for row in meters for name in row.slice_names if name)
    missing = any(row.consumption is None for row in meters)
    total = sum(row.consumption for row in meters if row.consumption is not None)
    has_positive_consumption = any((row.consumption or 0) > 0 for row in meters)

    if turkish:
        period_name = _turkish_period_label(period.display_name)
        headline = (
            f"Reneryo'da {len(meters)} sayaç var: {_natural_join(names, turkish=True)}."
        )
        if resources:
            headline += f" Enerji kaynağı {_natural_join(resources, turkish=True)}."
        if metrics:
            headline += f" Bağlı metrik: {_natural_join(metrics, turkish=True)}."
        if slices:
            headline += f" Kapsadığı bölüm: {_natural_join(slices, turkish=True)}."
        if missing:
            headline += f" {period_name} dönemi için tüketim verisi eksik; eksik veri sıfır tüketim değildir."
        elif has_positive_consumption:
            headline += f" {period_name} dönemi tüketimi {total:,.2f}."
        else:
            headline += (
                f" {period_name} dönemi için dönen tüketim 0,00; bu, "
                "sayacın mevcut olmadığını veya fabrikanın hiç tüketim yapmadığını göstermez."
            )
        return headline

    headline = f"Reneryo has {len(meters)} meter: {_natural_join(names)}."
    if len(meters) != 1:
        headline = f"Reneryo has {len(meters)} meters: {_natural_join(names)}."
    if resources:
        headline += f" The energy resource is {_natural_join(resources)}."
    if metrics:
        headline += f" It is linked to {_natural_join(metrics)}."
    if slices:
        headline += f" It covers {_natural_join(slices)}."
    if missing:
        headline += f" Consumption data for {period.display_name} is missing; missing data is not zero consumption."
    elif has_positive_consumption:
        headline += f" Consumption for {period.display_name} totals {total:,.2f}."
    else:
        headline += (
            f" The returned consumption for {period.display_name} is 0.00; that "
            "does not mean the meter is absent or the factory used no energy."
        )
    return headline


def metric_inventory_headline(rows: Iterable[ReneryoMetric], language: str) -> str:
    """Summarize the metric inventory and its observable data watermark."""
    metrics = list(rows)
    turkish = is_turkish(language)
    if not metrics:
        return (
            "Future Gen için kullanılabilir metrik bulunmuyor."
            if turkish
            else "Future Gen has no available metrics."
        )
    names = _unique(row.name for row in metrics if row.name)
    observed = [row.last_value_at for row in metrics if row.last_value_at is not None]
    newest = max(observed) if observed else None
    if turkish:
        headline = (
            f"Future Gen için {len(metrics)} metrik var: "
            f"{_natural_join(names, turkish=True)}."
        )
        if newest:
            headline += (
                f" Bu envanterdeki en güncel metrik gözlemi {_timestamp(newest)}."
            )
        return headline
    headline = f"Future Gen has {len(metrics)} metrics: {_natural_join(names)}."
    if newest:
        headline += (
            f" The newest metric observation in this inventory is {_timestamp(newest)}."
        )
    return headline


def metric_detail_headline(row: ReneryoMetric, language: str) -> str:
    """Describe one context-selected metric using Reneryo-owned metadata."""
    observed = _timestamp(row.last_value_at) if row.last_value_at else None
    value = f"{row.last_value:,.2f}" if row.last_value is not None else None
    if is_turkish(language):
        headline = (
            f"İlgili metrik {row.name}; türü {row.metric_type}, "
            f"kaynak grubu {row.unit_group}."
        )
        if value and observed:
            headline += f" Son gözlemi {observed} tarihinde {value}."
        elif observed:
            headline += f" Son gözlem zamanı {observed}."
        return headline
    headline = (
        f"The related metric is {row.name}; its type is {row.metric_type} "
        f"and its resource group is {row.unit_group}."
    )
    if value and observed:
        headline += f" Its latest observation was {value} at {observed}."
    elif observed:
        headline += f" Its latest observation time was {observed}."
    return headline


def finding_inventory_headline(result: MdspFindingList, language: str) -> str:
    """Summarize finding counts by severity and domain."""
    turkish = is_turkish(language)
    severities = Counter(finding.severity.upper() for finding in result.findings)
    domains = Counter(finding.domain.upper() for finding in result.findings)
    if turkish:
        return (
            f"{result.active_count} etkin bulgu var: {severities.get('HIGH', 0)} "
            f"yüksek, {severities.get('MEDIUM', 0)} orta ve "
            f"{severities.get('LOW', 0)} düşük önem düzeyinde. "
            f"{_domain_summary(domains, turkish=True)}."
        )
    return (
        f"There are {result.active_count} active findings: "
        f"{severities.get('HIGH', 0)} high, {severities.get('MEDIUM', 0)} medium "
        f"and {severities.get('LOW', 0)} low. {_domain_summary(domains)}."
    )


def _type_summary(counts: Counter[str], *, turkish: bool) -> str:
    parts = []
    for name in ("advanced", "linear"):
        count = counts.get(name, 0)
        if not count:
            continue
        localized = (
            {"advanced": "gelişmiş", "linear": "doğrusal"}[name] if turkish else name
        )
        parts.append(f"{count} {localized}")
    return _natural_join(parts, turkish=turkish)


def _domain_summary(counts: Counter[str], *, turkish: bool = False) -> str:
    labels = {
        "METRICS": ("metrik", "concern metrics"),
        "TRENDS": ("eğilim", "concern trends"),
        "SEU": ("ÖET", "concern significant energy uses"),
        "REGRESSION": ("regresyon", "concern regression analysis"),
    }
    parts = []
    for domain, (turkish_label, english_label) in labels.items():
        count = counts.get(domain, 0)
        if count:
            parts.append(
                f"{count} tanesi {turkish_label} alanında"
                if turkish
                else f"{count} {english_label}"
            )
    return _natural_join(parts, turkish=turkish) or (
        "Alan bilgisi bulunmuyor" if turkish else "No domain breakdown is available"
    )


def _localized_period(value: str, *, turkish: bool) -> str:
    normalized = value.strip().upper()
    if turkish:
        return {"DAILY": "günlük", "WEEKLY": "haftalık", "MONTHLY": "aylık"}.get(
            normalized, value.lower()
        )
    return normalized.lower()


def _turkish_period_label(value: str) -> str:
    normalized = value.strip().lower()
    return {
        "latest available": "mevcut en güncel",
        "last month": "geçen ay",
        "last 4 weeks": "son dört hafta",
        "past 30 days": "son 30 gün",
        "last 30 days": "son 30 gün",
    }.get(normalized, value)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _natural_join(values: Iterable[str], turkish: bool = False) -> str:
    items = list(values)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    conjunction = " ve " if turkish else " and "
    if len(items) == 2:
        return conjunction.join(items)
    return f"{', '.join(items[:-1])}{conjunction}{items[-1]}"


def _range(values: Iterable[float], *, turkish: bool = False) -> str:
    numbers = list(values)
    separator = " ile " if turkish else " to "
    return f"{min(numbers):.3f}{separator}{max(numbers):.3f}"


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")
