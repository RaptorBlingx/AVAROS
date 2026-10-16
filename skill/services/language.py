"""Small, dependency-free language helpers shared by skill services."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from skill.domain.models import CanonicalMetric


SUPPORTED_LANGUAGES = ("en-US", "tr-TR")


def normalize_language_tag(language: str | None) -> str:
    """Return a canonical BCP-47 tag for the languages AVAROS supports."""
    normalized = str(language or "en-US").strip().replace("_", "-").lower()
    return "tr-TR" if normalized.startswith("tr") else "en-US"


def is_turkish(language: str | None) -> bool:
    """Return whether *language* identifies Turkish."""
    return normalize_language_tag(language) == "tr-TR"


def normalize_phrase(value: str) -> str:
    """Normalize Unicode speech text without discarding Turkish characters."""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    normalized = normalized.replace("i\u0307", "i").replace("₂", "2").replace("₀", "0")
    normalized = re.sub(r"[^\w\s-]", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized.replace("_", " ")).strip()


_TURKISH_METRIC_NAMES = {
    CanonicalMetric.ENERGY_PER_UNIT: "birim başına enerji",
    CanonicalMetric.ENERGY_TOTAL: "toplam enerji",
    CanonicalMetric.PEAK_DEMAND: "pik talep",
    CanonicalMetric.PEAK_TARIFF_EXPOSURE: "pik tarife maruziyeti",
    CanonicalMetric.CONSUMPTION_POWER: "tüketim gücü",
    CanonicalMetric.PRODUCTION_POWER: "üretim gücü",
    CanonicalMetric.ENERGY_PRODUCTION_TOTAL: "toplam üretim enerjisi",
    CanonicalMetric.GRID_POWER: "şebeke gücü",
    CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL: "şebekeden alınan toplam enerji",
    CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL: "şebekeye verilen toplam enerji",
    CanonicalMetric.STORAGE_STATE_OF_CHARGE: "batarya doluluk oranı",
    CanonicalMetric.STORAGE_POWER: "batarya gücü",
    CanonicalMetric.SCRAP_RATE: "hurda oranı",
    CanonicalMetric.REWORK_RATE: "yeniden işleme oranı",
    CanonicalMetric.MATERIAL_EFFICIENCY: "malzeme verimliliği",
    CanonicalMetric.RECYCLED_CONTENT: "geri dönüştürülmüş içerik oranı",
    CanonicalMetric.SUPPLIER_LEAD_TIME: "tedarikçi teslim süresi",
    CanonicalMetric.SUPPLIER_DEFECT_RATE: "tedarikçi hata oranı",
    CanonicalMetric.SUPPLIER_ON_TIME: "tedarikçi zamanında teslim oranı",
    CanonicalMetric.SUPPLIER_CO2_PER_KG: "tedarikçi kilogram başına karbon",
    CanonicalMetric.OEE: "toplam ekipman etkinliği",
    CanonicalMetric.THROUGHPUT: "üretim hızı",
    CanonicalMetric.CYCLE_TIME: "çevrim süresi",
    CanonicalMetric.CHANGEOVER_TIME: "ürün değişim süresi",
    CanonicalMetric.CO2_PER_UNIT: "birim başına karbon",
    CanonicalMetric.CO2_TOTAL: "toplam karbon emisyonu",
    CanonicalMetric.CO2_PER_BATCH: "parti başına karbon",
}


def metric_display_name(metric: CanonicalMetric, language: str | None) -> str:
    """Return the localized spoken name of a canonical metric."""
    if is_turkish(language):
        return _TURKISH_METRIC_NAMES.get(metric, metric.value.replace("_", " "))
    return metric.display_name


def period_display_name(value: str, language: str | None) -> str:
    """Localize a system period label without changing its dates or precision."""
    pairs = {
        "latest available": "mevcut en güncel", "today": "bugün",
        "yesterday": "dün", "last week": "geçen hafta", "last month": "geçen ay",
        "last 4 weeks": "son dört hafta", "last 30 days": "son 30 gün",
        "past 30 days": "son 30 gün", "in total": "toplam",
    }
    value = re.sub(r"^available monthly history ", "mevcut aylık geçmiş " if is_turkish(language) else "available monthly history ", value)
    normalized = normalize_phrase(value)
    normalized = {"gecen ay": "geçen ay", "gecen hafta": "geçen hafta",
                  "son dort hafta": "son dört hafta", "son 30 gun": "son 30 gün"}.get(normalized, normalized)
    if is_turkish(language):
        if normalized in pairs:
            return pairs[normalized]
    else:
        reverse = {tr: en for en, tr in pairs.items()}
        if normalized in reverse:
            return reverse[normalized]
    months = zip(
        "january february march april may june july august september october november december".split(),
        "ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split(),
    )
    for english, turkish in months:
        ascii_month = turkish.translate(str.maketrans("çğıöşü", "cgiosu"))
        if is_turkish(language):
            value = re.sub(rf"\b(?:{turkish}|{ascii_month})\b", turkish.capitalize(), value, flags=re.IGNORECASE)
        source, target = (english, turkish) if is_turkish(language) else (turkish, english)
        value = re.sub(rf"\b{source}\b", target.capitalize(), value, flags=re.IGNORECASE)
    return value


def format_localized_number(value: float, language: str | None, spec: str = "g") -> str:
    """Keep the caller's precision while using the locale's decimal separator."""
    text = format(value, spec)
    return text.translate(str.maketrans({",": ".", ".": ","})) if is_turkish(language) else text


def source_enum_label(value: str, language: str | None) -> str:
    """Translate known metadata enums, never source record names or IDs."""
    labels = {
        "ENERGY": "enerji", "PIECE": "adet", "COUNTER": "birikimli sayaç",
        "GAUGE": "anlık ölçüm", "ELECTRIC": "elektrik", "GAS": "gaz",
        "WATER": "su", "DIESEL": "dizel", "SOLID_FUEL": "katı yakıt",
        "POWER": "güç", "CURRENT": "akım", "FREQUENCY": "frekans",
        "PRECIPITATION": "yağış", "RATE": "oran", "SCALAR": "skaler",
        "TEMPERATURE": "sıcaklık", "TIME": "zaman", "VOLTAGE": "gerilim",
        "VOLUME": "hacim", "WEIGHT": "ağırlık", "APPARENT_POWER": "görünür güç",
        "REACTIVE_ENERGY": "reaktif enerji",
    }
    if is_turkish(language):
        return labels.get(value, value)
    english = {"PIECE": "units", "GAUGE": "instantaneous measurement",
               "COUNTER": "cumulative counter"}
    fallback = value.lower().replace("_", " ") if value in labels else value
    return english.get(value, fallback)


def format_observation_time(value: datetime, language: str | None) -> str:
    """Present a dated observation in UTC; never imply the site's timezone."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    stamp = value.strftime("%d.%m.%Y %H:%M" if is_turkish(language) else "%d %B %Y %H:%M")
    return stamp + (" UTC" if value.tzinfo is not None else "")
