"""Small, dependency-free language helpers shared by skill services."""

from __future__ import annotations

import re
import unicodedata

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
