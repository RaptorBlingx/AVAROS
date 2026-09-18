from datetime import datetime, timezone

import pytest

from skill._reneryo_handlers import _deterministic_action, _query_period
from skill.domain.models import TimePeriod
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
