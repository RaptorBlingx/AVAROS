from datetime import datetime, timezone

import pytest

from skill._reneryo_handlers import _deterministic_action, _query_period
from skill.domain.models import TimePeriod, CanonicalMetric
from skill.services.conversation_state import DialogueState
from skill.services.period_resolution import extract_period_phrase
from skill.services.semantic_resolver import SemanticAction


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("Show the trend for the previous calendar month.", "last month"),
        ("Show the trend for the prior calendar month.", "last month"),
        ("Use the preceding four weeks.", "last 4 weeks"),
        ("Compare the last 30 days.", "last 30 days"),
        ("What changed during the previous week?", "last week"),
        ("Geçen ayın eğilimini göster.", "geçen ay"),
        ("Geçen takvim ayında nasıl değişmiş?", "geçen ay"),
        ("Son dört haftayı karşılaştır.", "son dört hafta"),
        ("Son 30 gün için eğilim nedir?", "son 30 gün"),
        ("Show the electricity trend for June 2026.", "june 2026"),
        ("Show production trend in July 2026.", "july 2026"),
        ("Haziran 2026 için elektrik eğilimini göster.", "haziran 2026"),
        ("Temmuz 2026'da üretim eğilimini göster.", "temmuz 2026"),
        ("Show the electricity trend from May to June 2026.", "may to june 2026"),
        ("Show the production trend from June 2026 to July 2026.", "june 2026 to july 2026"),
        ("Mayıs ile Haziran 2026 arasında elektrik eğilimini göster.", "mayıs ile haziran 2026"),
        ("Haziran 2026 ile Temmuz 2026 arasında üretim eğilimini göster.", "haziran 2026 ile temmuz 2026"),
    ],
)
def test_extract_period_phrase_normalizes_natural_forms(utterance, expected):
    assert extract_period_phrase(utterance) == expected


def test_previous_calendar_month_is_calendar_bounded():
    period = TimePeriod.from_natural_language(
        "previous calendar month",
        now=datetime(2026, 9, 18, 12, tzinfo=timezone.utc),
    )

    assert period.start == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert period.end == datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_preceding_four_weeks_is_a_rolling_28_day_period():
    period = TimePeriod.from_natural_language("preceding four weeks")

    assert 27.99 < (period.end - period.start).total_seconds() / 86_400 < 28.01


@pytest.mark.parametrize(
    "utterance",
    [
        "Show its trend over the preceding four weeks.",
        "Son dört haftadaki eğilimi nedir?",
    ],
)
def test_trend_action_and_period_are_classified_independently(utterance):
    normalized = utterance.casefold()
    assert _deterministic_action(normalized, DialogueState()) is SemanticAction.TREND_SHOW

    skill = type(
        "PeriodSkill",
        (),
        {"_parse_period": staticmethod(TimePeriod.from_natural_language)},
    )()
    period = _query_period(skill, utterance, None)

    assert 27.99 < (period.end - period.start).total_seconds() / 86_400 < 28.01


@pytest.mark.parametrize(
    ("utterance", "month"),
    [
        ("Show the electricity trend for June 2026.", 6),
        ("Show the production trend for July 2026.", 7),
        ("Haziran 2026 için elektrik eğilimini göster.", 6),
        ("Temmuz 2026'da üretim eğilimini göster.", 7),
    ],
)
def test_explicit_named_month_trend_uses_calendar_window(utterance, month):
    assert _deterministic_action(utterance.casefold(), DialogueState()) is SemanticAction.TREND_SHOW
    skill = type(
        "PeriodSkill",
        (),
        {"_parse_period": staticmethod(TimePeriod.from_natural_language)},
    )()

    period = _query_period(skill, utterance, None)

    assert period.start == datetime(2026, month, 1, tzinfo=timezone.utc)
    assert period.end == datetime(2026, month + 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("utterance", "first_month", "last_month"),
    [
        ("Show the electricity trend from May to June 2026.", 5, 6),
        ("Show the production trend from June 2026 to July 2026.", 6, 7),
        ("Mayıs ile Haziran 2026 arasında elektrik eğilimini göster.", 5, 6),
        ("Haziran 2026 ile Temmuz 2026 arasında üretim eğilimini göster.", 6, 7),
    ],
)
def test_named_month_range_trend_includes_both_months(utterance, first_month, last_month):
    assert _deterministic_action(utterance.casefold(), DialogueState()) is SemanticAction.TREND_SHOW
    skill = type(
        "PeriodSkill",
        (),
        {"_parse_period": staticmethod(TimePeriod.from_natural_language)},
    )()

    period = _query_period(skill, utterance, None)

    assert period.start == datetime(2026, first_month, 1, tzinfo=timezone.utc)
    assert period.end == datetime(2026, last_month + 1, 1, tzinfo=timezone.utc)


def test_named_month_range_rejects_reversed_months():
    with pytest.raises(ValueError, match="end month"):
        TimePeriod.from_natural_language("July to June 2026")


TIME_REQUESTS = [
    ("Show OEE for Line 10 at 14:30", "en-US"),
    ("Show electricity consumption today at 14:30", "en-US"),
    ("Show latest production at 2 pm", "en-US"),
    ("Show latest production at two pm", "en-US"),
    ("Compare OEE for Line 1 and Line 10 yesterday at 14:30:15", "en-US"),
    ("Show OEE for Line 10 at noon", "en-US"),
    ("Show electricity consumption on 2020-06-15T14:30:00Z", "en-US"),
    ("And at 14:30?", "en-US"),
    ("Hat 10 OEE değerini saat 14:30 için göster", "tr-TR"),
    ("Bugün saat 14.30 elektrik tüketimini göster", "tr-TR"),
    ("Son üretim miktarını saat 14 için göster", "tr-TR"),
    ("Son üretim miktarını saat iki için göster", "tr-TR"),
    ("Dün saat 14:30 Hat 1 ve Hat 10 OEE değerlerini karşılaştır", "tr-TR"),
    ("Hat 10 OEE değerini 14.30'da göster", "tr-TR"),
    ("Peki saat 14:30?", "tr-TR"),
    ("Show OEE for Line 10 at 14 : 30", "en-US"),
]


@pytest.mark.parametrize("utterance,language", TIME_REQUESTS)
def test_unsupported_clock_precision_is_not_a_date_or_latest_window(utterance, language):
    from skill.services.period_resolution import unsupported_time_precision, unsupported_period_reference
    from skill.services.dia_query import parse_structured_query
    from tests.test_services.test_explicit_query_scope import ASSETS

    assert unsupported_time_precision(utterance)
    assert unsupported_period_reference(utterance)
    prior = DialogueState(
        operation="kpi", metrics=(CanonicalMetric.OEE,),
        asset_ids=("Line-10",), period=TimePeriod.latest(),
    )
    query = parse_structured_query(utterance, assets=ASSETS, prior=prior)
    assert "Time-of-day" in query.ambiguity
    assert query.period is None


@pytest.mark.parametrize("utterance", [
    "Show OEE for Line 10 yesterday", "Hat 10 OEE değerini dün göster",
    "Show electricity consumption on June 15 2020", "15 Haziran 2020 üretimini göster",
    "Show electricity consumption from 2020-06-01 to 2020-06-30",
    "Show electricity consumption last 30 days", "Son 30 gün elektrik tüketimini göster",
    "Show current OEE", "En güncel elektrik tüketimini göster",
    "When was electricity last updated?", "Elektrik verisi ne zaman kaydedildi?",
    "Show OEE for Line 14", "Show production of 14.30 units",
])
def test_supported_time_and_non_time_numbers_are_not_clock_qualifiers(utterance):
    from skill.services.period_resolution import unsupported_time_precision

    assert not unsupported_time_precision(utterance)
