"""Regression tests for Turkish language support."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from skill._metric_resolver import resolve_metric_from_utterance
from skill._slot_resolution import extract_line_assets_from_text
from skill._helpers import sync_response_language
from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult
from skill.services.response_builder import TurkishResponseBuilder, create_response_builder
from skill.services.dia_query import QueryOperation, parse_structured_query


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("Hat 1 için birim başına enerji nedir", CanonicalMetric.ENERGY_PER_UNIT),
        ("toplam enerji tüketimini göster", CanonicalMetric.ENERGY_TOTAL),
        ("şebekeye verilen enerji", CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL),
        ("batarya doluluk oranı", CanonicalMetric.STORAGE_STATE_OF_CHARGE),
        ("hurda oranı nasıl", CanonicalMetric.SCRAP_RATE),
        ("toplam ekipman etkinliği", CanonicalMetric.OEE),
        ("çevrim süresi", CanonicalMetric.CYCLE_TIME),
        ("toplam karbon emisyonu", CanonicalMetric.CO2_TOTAL),
    ],
)
def test_turkish_metric_resolution(utterance: str, expected: CanonicalMetric) -> None:
    assert resolve_metric_from_utterance(utterance) is expected


def test_turkish_line_asset_resolution() -> None:
    assert extract_line_assets_from_text(None, "Hat iki ile hat üç karşılaştır") == ["Line-2", "Line-3"]
    assert extract_line_assets_from_text(None, "hat 1 ve hat 2") == ["Line-1", "Line-2"]


@pytest.mark.parametrize("phrase", ["bugün", "dün", "geçen hafta", "son iki hafta", "geçen ay", "son 30 gün"])
def test_turkish_period_resolution(phrase: str) -> None:
    assert TimePeriod.from_natural_language(phrase).display_name == phrase


def test_turkish_named_month_and_iso_range() -> None:
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    month = TimePeriod.from_natural_language("temmuz 2026", now=now)
    date_range = TimePeriod.from_natural_language(
        "2026-07-10 ile 2026-07-12 arası", now=now
    )
    assert month.display_name == "temmuz 2026"
    assert month.start.month == 7
    assert date_range.display_name == "2026-07-10 ile 2026-07-12 arası"


def test_response_builder_factory_preserves_english_and_selects_turkish() -> None:
    assert type(create_response_builder("en-US")).__name__ == "ResponseBuilder"
    assert isinstance(create_response_builder("tr-TR"), TurkishResponseBuilder)


def test_hivemind_message_language_selects_turkish_response_builder() -> None:
    skill = SimpleNamespace(
        lang="en-us",
        response_builder=create_response_builder("en-US"),
        _response_language="en-US",
        _resolve_asset_name_for_voice=lambda asset_id: asset_id,
    )
    message = SimpleNamespace(
        data={"lang": "tr-tr"},
        context={"session": {"lang": "tr-tr"}},
    )

    assert sync_response_language(skill, message) == "tr-TR"
    assert isinstance(skill.response_builder, TurkishResponseBuilder)


def test_turkish_kpi_response() -> None:
    result = KPIResult(
        metric=CanonicalMetric.OEE,
        value=82.5,
        unit="%",
        asset_id="Line-1",
        period=TimePeriod.from_natural_language("bugün"),
        timestamp=datetime.now(tz=timezone.utc),
    )
    response = TurkishResponseBuilder().format_kpi_result(result)
    assert response == "Line 1 için toplam ekipman etkinliği bugün yüzde 82.5."


def test_turkish_locale_has_resource_parity_with_english() -> None:
    locale_root = Path(__file__).parents[1] / "skill" / "locale"
    english = {path.name for path in (locale_root / "en-us").iterdir() if path.is_file()}
    turkish = {path.name for path in (locale_root / "tr-tr").iterdir() if path.is_file()}
    assert turkish == english


def test_turkish_structured_comparison_resolves_operation_entities_and_period() -> None:
    assets = [
        Asset("Line-1", "Hat 1", "line", aliases=["birinci hat"]),
        Asset("Line-2", "Hat 2", "line", aliases=["ikinci hat"]),
    ]
    query = parse_structured_query(
        "Hat 1 ile Hat 2 için geçen hafta hurda oranını karşılaştır",
        assets=assets,
    )

    assert query.operation is QueryOperation.COMPARE
    assert query.metrics == (CanonicalMetric.SCRAP_RATE,)
    assert query.asset_ids == ("Line-1", "Line-2")
    assert query.period is not None
    assert query.period.display_name == "geçen hafta"
