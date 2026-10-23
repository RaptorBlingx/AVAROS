"""Natural bilingual summaries for Future Gen inventory queries."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from skill.services.quantities import quantity_number
from skill.services.response_localization import source_metric_label
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import (
    MdspFindingList,
    ReneryoMeter,
    ReneryoMetric,
    ReneryoRegression,
)
from skill.services.language import (
    is_turkish, period_display_name, format_localized_number, source_enum_label, format_observation_time,
)


def reneryo_capabilities_headline(language: str) -> str:
    """Describe only the conversational capabilities in the Future Gen slice."""
    if is_turkish(language):
        return (
            "Future Gen için sayaçları, metrikleri, eğilimleri, regresyon "
            "analizlerini ve etkin MDSP bulgularını açıklayabilirim. Seçili bir "
            "bulgunun nedenini, kanıtını, dönemini ve ilgili varlığı da takip "
            "edebilirim. Türkçe ve İngilizce yanıt verebilirim."
        )
    return (
        "For Future Gen, I can explain meters, metrics, trends, regression "
        "analyses, and active MDSP findings. I can also follow a selected "
        "finding through its trigger, evidence, period, affected entity, and "
        "related metric. I can answer in English and Turkish."
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
    drivers = _unique(source_metric_label(name, language) for row in models for name in row.driver_names if name)
    r_squared = [row.r_squared for row in models if row.r_squared is not None]
    primary_count = sum(1 for row in models if row.primary)

    if turkish:
        headline = (
            f"Reneryo'da {len(models)} kayıtlı regresyon modeli var: {type_summary}."
        )
        if len(type_counts) == 1 and next(iter(type_counts)) in {"advanced", "linear"}:
            kind = {"advanced": "gelişmiş", "linear": "doğrusal"}[next(iter(type_counts))]
            headline = f"Reneryo'da {len(models)} kayıtlı regresyon modeli var; tümü {kind} türde."
        if periods:
            headline += f" Model dönemleri {_natural_join(periods, turkish=True)}."
        if drivers:
            headline += f" Açıklayıcı değişkenler: {_natural_join(drivers, turkish=True)}."
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
    drivers = _natural_join([source_metric_label(name, language) for name in row.driver_names], turkish=turkish) or "—"
    slices = _natural_join(list(row.slice_names), turkish=turkish) or "—"
    period = _localized_period(row.period, turkish=turkish)
    training = f"{row.train_start.date()} – {row.train_end.date()}"
    r_squared = format_localized_number(row.r_squared, language, ".3f") if row.r_squared is not None else "—"
    rmse = format_localized_number(row.rmse, language, ".3f") if row.rmse is not None else "—"
    if turkish:
        primary = "birincil" if row.primary else "birincil değil"
        regression_type = {
            "advanced": "gelişmiş",
            "linear": "doğrusal",
        }.get(row.regression_type.lower(), row.regression_type)
        return (
            f"Bu {regression_type} regresyon modeli {period} dönemlidir ve {primary}. "
            f"Açıklayıcı değişkenler: {drivers}. Bağlı dilimler: {slices}. Eğitim dönemi {training}; "
            f"R² {r_squared}, RMSE {rmse}."
        )
    primary = "primary" if row.primary else "not primary"
    return (
        f"This {row.regression_type} regression model has a {period} period and is {primary}. "
        f"Drivers: {drivers}. Linked slices: {slices}. Its training period is {training}; "
        f"R-squared is {r_squared} and RMSE is {rmse}."
    )


def meter_inventory_headline(
    rows: Iterable[ReneryoMeter], period: TimePeriod, language: str, *, exact_window: bool = True
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
    resources = _unique(source_enum_label(row.energy_resource, language) for row in meters if row.energy_resource)
    metrics = _unique(source_metric_label(row.metric_name, language) for row in meters if row.metric_name)
    slices = _unique(name for row in meters for name in row.slice_names if name)
    period_name = period_display_name(period.display_name, language)
    headline = (
        f"Reneryo'da {len(meters)} sayaç var: {_natural_join(names, turkish=True)}."
        if turkish else
        f"Reneryo has {len(meters)} {'meter' if len(meters) == 1 else 'meters'}: {_natural_join(names)}."
    )
    if metrics:
        headline += (" Bağlı metrik: " if turkish else " It is linked to ") + _natural_join(metrics, turkish) + "."
    if resources:
        headline += (" Enerji kaynağı " if turkish else " The energy resource is ") + _natural_join(resources, turkish) + "."
    if slices:
        headline += (" Kapsadığı bölüm: " if turkish else " It covers ") + _natural_join(slices, turkish) + "."
    if not exact_window:
        return headline + (" Reneryo veri aralıkları bu dönemle örtüşmediği için kesin dönem tüketimi veremiyorum." if turkish else
                           " Exact period consumption is unavailable because Reneryo aggregate boundaries do not match this window.")
    # Reneryo supplies individual meter values, not a cross-meter aggregate.
    # Even compatible meters can overlap; adding them here would invent a total.
    values = []
    for meter in meters[:3]:
        value = (format_reneryo_value(meter.consumption, meter.unit_group, language)
                 if meter.consumption is not None else
                 "veri eksik" if turkish else "data missing")
        values.append(f"{meter.name}: {value}")
    headline += f" {period_name} " + ("dönemi tüketimi: " if turkish else "consumption: ") + "; ".join(values) + "."
    if any(m.consumption is None for m in meters):
        headline += (" Eksik veri sıfır tüketim değildir." if turkish else " Missing data is not zero consumption.")
    elif any(m.consumption == 0 for m in meters):
        headline += (" Dönen 0,00, fabrikanın hiç tüketim yapmadığını göstermez." if turkish else
                     " A returned 0.00 does not mean the factory used no energy.")
    if len(meters) > 1:
        headline += (" Sayaç değerlerini toplamadım; ayrı değerler ayrıntılarda mevcut." if turkish else
                     " Meter values are kept separate; individual values are in the details.")
    return headline


def metric_inventory_headline(
    rows: Iterable[ReneryoMetric], language: str, *, timezone_name: str | None = None, include_timezone: bool = False,
) -> str:
    """Summarize the metric inventory and its observable data watermark."""
    metrics = list(rows)
    turkish = is_turkish(language)
    if not metrics:
        return (
            "Future Gen için kullanılabilir metrik bulunmuyor."
            if turkish
            else "Future Gen has no available metrics."
        )
    names = _unique(source_metric_label(row.name, language) for row in metrics if row.name)
    observed = [row.last_value_at for row in metrics if row.last_value_at is not None]
    newest = max(observed) if observed else None
    if turkish:
        headline = (
            f"Future Gen için {len(metrics)} metrik var: "
            f"{_natural_join(names, turkish=True)}."
        )
        if newest:
            headline += (
                f" Bu envanterdeki en güncel metrik gözlemi {format_observation_time(newest, language, timezone_name, include_timezone=include_timezone)}."
            )
        return headline
    noun = "metric" if len(metrics) == 1 else "metrics"
    headline = f"Future Gen has {len(metrics)} {noun}: {_natural_join(names)}."
    if newest:
        headline += (
            f" The newest metric observation in this inventory is {format_observation_time(newest, language, timezone_name, include_timezone=include_timezone)}."
        )
    return headline


def metric_detail_headline(row: ReneryoMetric, language: str, *, value_only: bool = False, timestamp_only: bool = False, timezone_name: str | None = None, include_timezone: bool = False) -> str:
    """Describe one context-selected metric using Reneryo-owned metadata."""
    observed = format_observation_time(row.last_value_at, language, timezone_name, include_timezone=include_timezone) if row.last_value_at else None
    value = format_reneryo_value(row.last_value, row.unit_group, language) if row.last_value is not None else None
    name = source_metric_label(row.name, language)
    if is_turkish(language):
        subject = name[:1].upper() + name[1:]
        if timestamp_only:
            return (f"{subject} için son ölçüm {observed} tarihinde kaydedildi." if observed
                    else f"{subject} için ölçümün kayıt zamanı mevcut değil.")
        if value_only:
            if value is None:
                return f"{subject} için kayıtlı değer yok."
            headline = (f"Son ölçümde {name} {value}." if row.metric_type == "GAUGE"
                        else f"{subject} için son kayıtlı değer {value}.")
        else:
            headline = f"{subject}, {source_enum_label(row.metric_type, language)} türünde bir ölçüm."
            if value is not None:
                headline += f" Son kayıtlı değer {value}."
        if observed:
            headline += f" Kayıt zamanı: {observed}."
        if row.metric_type == "COUNTER" and value is not None:
            headline += " Bu birikimli sayaç değeridir; dönem tüketimi veya üretimi değildir."
        return headline
    if timestamp_only:
        return (f"{row.name}: latest recorded timestamp {observed}." if observed
                else f"{row.name}: no observation timestamp is available.")
    if value_only:
        if value is None:
            return f"{row.name}: no recorded value is available."
        headline = f"{row.name}: {value}" + (f"; {observed}" if observed else "") + "."
        if row.metric_type == "COUNTER":
            headline += " This is a cumulative counter reading, not period consumption or production."
        return headline
    headline = (
        f"The related metric is {row.name}; its type is {source_enum_label(row.metric_type, language)} "
        f"and its unit group is {source_enum_label(row.unit_group, language)}."
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
        f"{'There is' if result.active_count == 1 else 'There are'} {result.active_count} active {'finding' if result.active_count == 1 else 'findings'}: "
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


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _natural_join(values: Iterable[str], turkish: bool = False) -> str:
    items = list(values)
    if not items:
        return ""
    if len(items) > 5:
        return _natural_join(items[:3], turkish) + (f" ve {len(items) - 3} tane daha" if turkish else f" and {len(items) - 3} more")
    if len(items) == 1:
        return items[0]
    conjunction = " ve " if turkish else " and "
    if len(items) == 2:
        return conjunction.join(items)
    return f"{', '.join(items[:-1])}{conjunction}{items[-1]}"


def _range(values: Iterable[float], *, turkish: bool = False) -> str:
    numbers = list(values)
    separator = " ile " if turkish else " to "
    language = "tr-TR" if turkish else "en-US"
    return f"{format_localized_number(min(numbers), language, '.3f')}{separator}{format_localized_number(max(numbers), language, '.3f')}"


def format_reneryo_value(value: float, unit_group: str, language: str) -> str:
    """Display Reneryo base units (UtilUnit), without altering source evidence."""
    displayed = value * 100 if unit_group == "RATE" else value
    number = quantity_number(displayed, language)
    if unit_group == "RATE":
        return f"%{number}" if is_turkish(language) else f"{number}%"
    # PRECIPITATION's base unit is PRECIPITATION_MILIMETER_PER_METRE_SQUARE ("mm/m²").
    units = {"ENERGY": "kWh", "TEMPERATURE": "°C", "VOLUME": "m³", "WEIGHT": "kg", "PRECIPITATION": "mm/m²",
             "PIECE": "adet" if is_turkish(language) else "unit" if value == 1 else "units"}
    return f"{number} {units.get(unit_group, source_enum_label(unit_group, language))}".strip()


def temperature_trend_headline(trend, language: str) -> str:
    """Describe Reneryo Celsius endpoints without an origin-dependent ratio."""
    first, last = trend.points[0].value, trend.points[-1].value
    delta = last - first
    start = format_reneryo_value(first, "TEMPERATURE", language)
    end = format_reneryo_value(last, "TEMPERATURE", language)
    difference = format_reneryo_value(abs(delta), "TEMPERATURE", language)
    period = period_display_name(trend.period_label, language)
    if is_turkish(language):
        name = source_metric_label(trend.metric.name, language)
        period_phrase = period if period in {"bugün", "dün", "geçen hafta", "geçen ay"} else period + " döneminde"
        prefix = f"{period_phrase[:1].upper() + period_phrase[1:]} {name}"
        if delta == 0:
            return f"{prefix}: ilk ve son ölçüm {start}; net değişim yok."
        # Two decimals are sufficient for normal temperatures; preserve tiny
        # nonzero changes and retain full precision in the evidence rows.
        from decimal import Decimal

        rounded = Decimal(str(abs(delta))).quantize(Decimal("0.01"))
        if rounded:
            difference = format_reneryo_value(float(rounded), "TEMPERATURE", language)
        approximate = "yaklaşık " if rounded and rounded != Decimal(str(abs(delta))) else ""
        direction, noun = ("yükseldi", "artış") if delta > 0 else ("düştü", "düşüş")
        change = f"{approximate}{difference} {noun} var."
        return f"{prefix} {start}'den {end}'ye {direction}. {change[:1].upper() + change[1:]}"
    if delta == 0:
        return f"{trend.metric.name}, {period}: first and last values were {start}; no net change."
    direction = "rise" if delta > 0 else "drop"
    return f"{trend.metric.name}, {period}: first {start}, last {end}; a {direction} of {difference}."
