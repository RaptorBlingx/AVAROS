"""Behaviour tests with synthetic data: dates, counter semantics and dialogue."""

from datetime import datetime, timezone

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.clients.reneryo import ReneryoClient
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMeter, ReneryoMetric, ReneryoTrendPoint
from skill.services.conversation_state import DialogueState
from skill.services.factory_questions import (
    answer_factory_question,
    classify_factory_question,
)
from skill.services.futuregen import FutureGenService
from tests.test_services.test_finding_collection_dialogue import _message, _Skill


def date(y, m, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc)


class Source:
    def __init__(self, values=True, amount=25):
        self.values = values
        self.amount = amount
        self.calls = []

    async def list_metrics(self):
        return [
            ReneryoMetric(
                "e",
                "Tesis Toplam Elektrik Tüketimi",
                "COUNTER",
                "ENERGY",
                9000,
                date(2020, 7),
            ),
            ReneryoMetric(
                "p",
                "Tesis Toplam Üretim Miktarı",
                "COUNTER",
                "PIECE",
                5000,
                date(2020, 7),
            ),
        ]

    async def metric_values(self, metric_id, start, end, period):
        self.calls.append((metric_id, start, end, period))
        return (
            [ReneryoTrendPoint(date(2020, 6), 12, 1)]
            if self.values and start.year == 2020
            else []
        )

    async def recent_metric_values(self, metric, count=12):
        return (
            (
                [
                    ReneryoTrendPoint(date(2020, 5), 10, 1),
                    ReneryoTrendPoint(date(2020, 6), 12, 1),
                ],
                6,
            )
            if self.values
            else ([], 0)
        )

    async def list_meters(self, start, end):
        self.calls.append(("meter", start, end))
        return [
            ReneryoMeter(
                "m", "Synthetic meter", "electricity", self.amount, "e", "Electricity"
            )
        ]


QUESTIONS = [
    ("What is our electricity consumption?", "amount"),
    ("How much energy did we use today?", "amount"),
    ("Show electricity consumption last month", "amount"),
    ("Show latest electricity consumption", "amount"),
    ("How much electricity was consumed in June 2020?", "amount"),
    ("Show energy use in 2020", "amount"),
    ("What did we produce in June 2020?", "amount"),
    ("How much production do we have?", "amount"),
    ("Show latest production", "amount"),
    ("Show factory output last month", "amount"),
    ("How much was produced today?", "amount"),
    ("What is the latest electricity reading?", "reading"),
    ("Show the energy counter", "reading"),
    ("Show cumulative production reading", "reading"),
    ("When was electricity last updated?", "freshness"),
    ("How fresh is production data?", "freshness"),
    ("What is the last electricity observation?", "freshness"),
    ("Show electricity history", "history"),
    ("Show available production data", "history"),
    ("List historical energy records", "history"),
    ("Show production history in 2020", "history"),
    ("Show electricity data from May to June 2020", "history"),
    ("Elektrik tüketimimiz ne kadar?", "amount"),
    ("Bugün ne kadar enerji tükettik?", "amount"),
    ("Geçen ay elektrik tüketimini göster", "amount"),
    ("Son elektrik tüketimini göster", "amount"),
    ("Haziran 2020 elektrik tüketimi ne kadar?", "amount"),
    ("2020 enerji tüketimini göster", "amount"),
    ("Haziran 2020 üretim miktarı ne kadar?", "amount"),
    ("Ne kadar ürettik?", "amount"),
    ("Son üretim miktarını göster", "amount"),
    ("Bugün üretimimiz ne kadar?", "amount"),
    ("Geçen ay üretimi göster", "amount"),
    ("Son elektrik değerini göster", "reading"),
    ("Birikimli üretim değerini göster", "reading"),
    ("Elektrik verisi ne zaman kaydedildi?", "freshness"),
    ("Üretim verisi ne kadar güncel?", "freshness"),
    ("Son elektrik verisi ne zaman?", "freshness"),
    ("Elektrik geçmişini göster", "history"),
    ("Mevcut üretim verisini göster", "history"),
    ("Enerji kayıtlarını göster", "history"),
    ("2020 üretim geçmişini göster", "history"),
    ("Mayıs ile Haziran 2020 elektrik verisini göster", "history"),
]


@pytest.mark.parametrize("question,kind", QUESTIONS)
def test_many_natural_questions_reach_grounded_answer(question, kind):
    request = classify_factory_question(question, DialogueState())
    assert request is not None
    assert request.kind == kind
    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    skill._futuregen_service = FutureGenService(Source())
    assert handle_reneryo_query(
        skill,
        _message(
            question, "tr-TR" if QUESTIONS.index((question, kind)) >= 22 else "en-US"
        ),
    )
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    from skill.services.period_resolution import extract_period_phrase
    explicit = extract_period_phrase(question)
    if explicit and not response["evidence_rows"]:
        assert response["response_type"] == "unavailable"
    else:
        assert response["evidence_rows"]
    assert "9000" not in response["headline"] or kind == "reading"
    assert "5000" not in response["headline"] or kind == "reading"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
async def test_empty_explicit_window_does_not_substitute_years_old_consumption(language):
    source = Source()
    period = TimePeriod(date(2026, 10), date(2026, 11), "October 2026")
    answer = await answer_factory_question(
        FutureGenService(source),
        classify_factory_question(
            "electricity consumption this month", DialogueState()
        ),
        period,
        language,
    )
    assert answer.period == period
    assert not answer.evidence
    assert "2020-06" not in answer.headline
    assert "9000" not in answer.headline
    assert source.calls == [("e", period.start, period.end, "DAILY")]



@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, None])
async def test_zero_is_reported_only_from_domain_consumption_not_missing_value(amount):
    answer = await answer_factory_question(
        FutureGenService(Source(amount=amount)),
        classify_factory_question("electricity consumption", DialogueState()),
        TimePeriod(date(2026, 10), date(2026, 11), "October"),
        "en-US",
    )
    assert answer.evidence[0]["consumption"] == amount
    assert ("no meter consumption" in answer.headline) == (amount is None)


@pytest.mark.asyncio
async def test_no_period_data_never_returns_counter_as_consumption():
    answer = await answer_factory_question(
        FutureGenService(Source(values=False)),
        classify_factory_question("electricity consumption", DialogueState()),
        TimePeriod(date(2026, 10), date(2026, 11), "October"),
        "en-US",
    )
    assert "no period values" in answer.headline
    assert "9000" not in answer.headline
    assert "01 July 2020" in answer.headline


@pytest.mark.asyncio
async def test_multi_month_production_shows_domain_buckets_without_invented_sum():
    answer = await answer_factory_question(
        FutureGenService(Source()),
        classify_factory_question("production history", DialogueState()),
        TimePeriod(date(2026, 10), date(2026, 11), "October"),
        "en-US",
    )
    assert len(answer.evidence) == 2
    assert "no combined total" in answer.headline
    assert "5000" not in answer.headline


@pytest.mark.asyncio
async def test_trend_fallback_keeps_actual_bucket_dates_and_counter_delta_values():
    trend = await FutureGenService(Source()).trend(
        "electricity", TimePeriod(date(2026, 10), date(2026, 11), "October")
    )
    assert trend.requested_period_label == "October"
    assert trend.period_start == date(2020, 5)
    assert trend.period_end == date(2020, 7)
    assert trend.change_percent == 20


def test_followup_retains_metric_and_historical_year():
    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    skill._futuregen_service = FutureGenService(Source())
    assert handle_reneryo_query(skill, _message("Show electricity consumption"))
    assert handle_reneryo_query(skill, _message("And June?"))
    assert skill._futuregen_service.reneryo.calls[-1][1] == date(2020, 6)
    assert handle_reneryo_query(skill, _message("When was the last reading recorded?"))
    assert "01 July 2020" in skill.spoken[-1][0]


@pytest.mark.parametrize(
    "question",
    [
        "electricity forecast",
        "production cost",
        "energy per unit",
        "enerji tasarrufu",
        "electricity and production",
    ],
)
def test_unsupported_derived_or_ambiguous_questions_do_not_invent_answers(question):
    request = classify_factory_question(question, DialogueState())
    assert request.kind in {"unsupported", "clarify"}


@pytest.mark.parametrize(
    "question",
    [
        "Show electricity trend",
        "Elektrik eğilimini göster",
        "Explain electricity findings",
        "Humidity today",
        "Why did production drop?",
        "List energy meters",
        "What are the regression drivers?",
        "Turn off the electricity",
    ],
)
def test_existing_or_control_flows_are_not_hijacked(question):
    assert (
        classify_factory_question(
            question,
            DialogueState(operation="factory_history", metric_name="Electricity"),
        )
        is None
    )


@pytest.mark.asyncio
async def test_recent_history_uses_descending_domain_query_and_preserves_zero():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})

    async def get(path, params):
        assert path == "/a/metric/values/e"
        assert params["descending"] == "true"
        assert params["period"] == "MONTHLY"
        assert params["count"] == "12"
        assert params["datetimeMin"].startswith("1900")
        return {
            "recordCount": 30,
            "records": [
                {"datetime": date(2020, 6).isoformat(), "value": 0, "sampleCount": 1},
                {
                    "datetime": date(2020, 5).isoformat(),
                    "value": None,
                    "sampleCount": 0,
                },
            ],
        }

    client._get = get
    points, count = await client.recent_metric_values(
        (await Source().list_metrics())[0]
    )
    assert count == 30
    assert len(points) == 1 and points[0].value == 0


def test_native_ovos_and_signed_widget_take_same_grounded_path():
    from skill.services.dia_dialogue import try_handle_structured_query

    for widget in (False, True):
        skill = _Skill()
        skill._parse_period = TimePeriod.from_natural_language
        skill._futuregen_service = FutureGenService(Source())
        message = _message("How much electricity did we use today?")
        if widget:
            message.context["reneryo_widget_session_validated"] = True
        else:
            message.context.pop("reneryo_context")
        assert try_handle_structured_query(skill, message)
        response = skill.spoken[-1][1]["meta"]["avaros_response"]
        assert response["response_type"] == "unavailable"
        assert not response["evidence_rows"]
        assert not skill._futuregen_service.reneryo.calls



@pytest.mark.parametrize(
    "question, start, end",
    [
        ("Show production history in 2020", date(2020, 1), date(2021, 1)),
        ("2020 elektrik eğilimini göster", date(2020, 1), date(2021, 1)),
        (
            "Electricity consumption from 2020-05-01 to 2020-06-30",
            date(2020, 5),
            date(2020, 7),
        ),
        (
            "2020-05-01 ile 2020-06-30 elektrik tüketimini göster",
            date(2020, 5),
            date(2020, 7),
        ),
    ],
)
def test_explicit_years_and_date_ranges_do_not_silently_use_recent_window(
    question, start, end
):
    from skill._reneryo_handlers import _query_period

    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    period = _query_period(skill, question, None)
    assert (period.start, period.end) == (start, end)


@pytest.mark.asyncio
async def test_ambiguous_inventory_requires_metric_selection():
    class Many(Source):
        async def list_metrics(self):
            metrics = await super().list_metrics()
            return metrics + [
                ReneryoMetric("other", "Other electricity", "COUNTER", "ENERGY")
            ]

    answer = await answer_factory_question(
        FutureGenService(Many()),
        classify_factory_question("electricity consumption", DialogueState()),
        TimePeriod(date(2020, 5), date(2020, 7), "May–June"),
        "en-US",
    )
    assert answer.response_type == "clarification"
    assert len(answer.evidence) == 2


@pytest.mark.asyncio
async def test_missing_latest_metadata_does_not_prevent_historical_query():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})
    called = []

    async def get(path, params):
        called.append(path)
        return {
            "recordCount": 1,
            "records": [
                {"datetime": date(2020, 6).isoformat(), "value": 12, "sampleCount": 1}
            ],
        }

    client._get = get
    points, count = await client.recent_metric_values(
        ReneryoMetric("p", "Production", "COUNTER", "PIECE")
    )
    assert called == ["/a/metric/values/p"]
    assert len(points) == count == 1


@pytest.mark.asyncio
async def test_all_history_uses_full_paginated_domain_reader():
    class AllHistory(Source):
        async def metric_values(self, metric_id, start, end, period):
            self.calls.append((metric_id, start, end, period))
            return [
                ReneryoTrendPoint(date(1990 + i // 12, 1 + i % 12), i, 1)
                for i in range(150)
            ]

    source = AllHistory()
    answer = await answer_factory_question(
        FutureGenService(source),
        classify_factory_question("Show all production history", DialogueState()),
        TimePeriod(date(2026, 10), date(2026, 11), "October"),
        "en-US",
    )
    assert source.calls[0][1] == date(1900, 1)
    assert source.calls[0][-1] == "MONTHLY"
    assert len(answer.evidence) == 150
    assert "150" in answer.headline


@pytest.mark.asyncio
async def test_named_selection_resolves_multiple_metrics():
    class Many(Source):
        async def list_metrics(self):
            metrics = await super().list_metrics()
            return metrics + [
                ReneryoMetric(
                    "other",
                    "Other electricity",
                    "COUNTER",
                    "ENERGY",
                    123,
                    date(2020, 7),
                )
            ]

    answer = await answer_factory_question(
        FutureGenService(Many()),
        classify_factory_question(
            "Show Other electricity counter reading", DialogueState()
        ),
        TimePeriod(date(2020, 5), date(2020, 7), "May–June"),
        "en-US",
    )
    assert answer.metric_name == "Other electricity"
    assert answer.evidence[0]["value"] == 123
    assert "cumulative" in answer.headline


@pytest.mark.asyncio
async def test_api_error_is_not_treated_as_empty_data():
    from skill.domain.exceptions import AdapterError

    class Failed(Source):
        async def metric_values(self, *args):
            raise AdapterError(
                message="Denied",
                code="RENERYO_REQUEST_FAILED",
                platform="reneryo",
                status_code=403,
            )

        async def recent_metric_values(self, *args):
            pytest.fail("Access failures must not be bypassed with a history query")

    with pytest.raises(AdapterError):
        await answer_factory_question(
            FutureGenService(Failed()),
            classify_factory_question(
                "Electricity consumption June 2020", DialogueState()
            ),
            TimePeriod(date(2020, 6), date(2020, 7), "June 2020"),
            "en-US",
        )
