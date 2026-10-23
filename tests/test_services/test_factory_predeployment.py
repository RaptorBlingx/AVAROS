"""Adversarial regressions from the API-backed pre-deployment review.

Synthetic API responses deliberately preserve Reneryo's inclusive upper bound.
The real client must normalize that contract before the dialogue sees any data.
"""

from datetime import datetime, timedelta

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.clients.reneryo import ReneryoClient
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMeter, ReneryoTrendPoint
from skill.services.factory_questions import classify_factory_question
from skill.services.futuregen import FutureGenService
from skill.services.futuregen_responses import meter_inventory_headline
from tests.test_services.test_factory_questions import Source, date
from tests.test_services.test_finding_collection_dialogue import _message, _Skill


def harness(source=None):
    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    skill._futuregen_service = FutureGenService(source or Source())
    return skill


def ask(skill, text, language="en-US"):
    assert handle_reneryo_query(skill, _message(text, language))
    return skill.spoken[-1][1]["meta"]["avaros_response"]


@pytest.mark.parametrize(
    "question,language",
    [
        ("Elektriği ne kadar kullandık?", "tr-TR"),
        ("Elektriği göster", "tr-TR"),
        ("What did we consume in the last 30 days?", "en-US"),
        ("What is our electrical usage?", "en-US"),
        ("How many units did we make?", "en-US"),
        ("Kaç adet ürettik?", "tr-TR"),
    ],
)
def test_alternative_amount_questions_return_dated_history_not_legacy_zero(
    question, language
):
    r = ask(harness(), question, language)
    if "last 30 days" in question:
        assert r["response_type"] == "unavailable" and not r["evidence_rows"]
        return
    assert r["evidence_rows"]
    assert "2020-06" in r["headline"]
    assert "0,00" not in r["headline"] and "0.00" not in r["headline"]
    assert r["response_type"] != "regression"


@pytest.mark.parametrize(
    "question,language",
    [
        ("What is our gas consumption?", "en-US"),
        ("Show water consumption", "en-US"),
        ("Show gas readings", "en-US"),
        ("Show compressed air consumption", "en-US"),
        ("Doğalgaz tüketimimiz ne kadar?", "tr-TR"),
        ("Su tüketimini göster", "tr-TR"),
        ("Basınçlı hava tüketimi ne kadar?", "tr-TR"),
        ("Show electricity consumption for Line 1", "en-US"),
        ("How much electricity was used by the oven in June 2020?", "en-US"),
        ("1 numaralı hattın elektrik tüketimi ne kadar?", "tr-TR"),
        ("Haziran 2020 fırının elektrik tüketimi ne kadar?", "tr-TR"),
        ("Show electricity consumption at Plant B", "en-US"),
        ("Show electricity consumption for an unknown department", "en-US"),
    ],
)
def test_unsupported_resource_or_entity_never_substitutes_factory_measurements(
    question, language
):
    source = Source()
    r = ask(harness(source), question, language)
    assert r["response_type"] == "clarification"
    assert not r["evidence_rows"]
    assert not source.calls


@pytest.mark.parametrize(
    "question,expected",
    [
        ("How much electricity did we consume on June 15 2020?", date(2020, 6, 15)),
        ("What is electricity consumption for 2020-06-15?", date(2020, 6, 15)),
        ("15 Haziran 2020 elektrik tüketimini göster", date(2020, 6, 15)),
        ("2020-06-15 elektrik tüketimi ne kadar?", date(2020, 6, 15)),
    ],
)
def test_single_days_never_become_whole_years(question, expected):
    source = Source()
    ask(harness(source), question)
    assert source.calls[0][1:3] == (expected, expected + timedelta(days=1))


@pytest.mark.parametrize(
    "question",
    [
        "Show electricity consumption in June",
        "2020 Haziran elektrik tüketimini göster",
        "Show electricity consumption in 2020 June",
        "Haziran ayında elektrik tüketimi ne kadar?",
        "Show electricity consumption in 2024 and 2025",
        "2024 ve 2025 elektrik tüketimini göster",
        "Electricity consumption Q1 2020",
        "2020 ilk çeyrek elektrik tüketimi",
        "Show electricity consumption in November 2099",
        "Kasım 2099 elektrik tüketimini göster",
        "Electricity consumption on June 99 2020",
        "99 Haziran 2020 elektrik tüketimi",
    ],
)
def test_ambiguous_invalid_unsupported_or_future_dates_clarify_without_domain_query(
    question,
):
    source = Source()
    r = ask(harness(source), question)
    assert r["response_type"] == "clarification"
    assert not source.calls


@pytest.mark.parametrize(
    "question,language",
    [
        ("Show electricity readings in May 2020", "en-US"),
        ("Show electricity meter readings in May 2020", "en-US"),
        ("Show production readings from May to July 2020", "en-US"),
        ("Mayıs 2020 elektrik sayaç değerlerini göster", "tr-TR"),
        ("Mayıs ile Temmuz 2020 birikimli üretim değerlerini göster", "tr-TR"),
    ],
)
def test_dated_readings_explain_access_limitation_without_substituting_latest_counter(
    question, language
):
    r = ask(harness(), question, language)
    assert r["response_type"] == "unavailable"
    assert not r["evidence_rows"]
    assert "9000" not in r["headline"] and "5000" not in r["headline"]
    assert "2020" in r["headline"]


@pytest.mark.parametrize(
    "first,followup,language",
    [
        ("Show electricity consumption in May 2020", "And production?", "en-US"),
        ("Show electricity consumption in May 2020", "What about production?", "en-US"),
        ("Mayıs 2020 elektrik tüketimini göster", "Üretim?", "tr-TR"),
        ("Mayıs 2020 elektrik tüketimini göster", "Peki üretim?", "tr-TR"),
        (
            "Show production in May 2020",
            "Show electricity for the same period",
            "en-US",
        ),
        ("Mayıs 2020 üretimi göster", "Aynı dönem için elektriği göster", "tr-TR"),
    ],
)
def test_metric_switch_retains_explicit_period_and_year(first, followup, language):
    skill = harness()
    ask(skill, first, language)
    r = ask(skill, followup, language)
    state = skill._dialogue_state_store.get("collection-session")
    assert state.period.start == date(2020, 5) and state.period.end == date(2020, 6)
    expected = (
        "Üretim"
        if "production" in followup or "üretim" in followup.lower()
        else "Elektrik"
    )
    assert expected in state.metric_name
    assert "2020" in r["headline"]


@pytest.mark.parametrize("question", ["And June?", "Peki Haziran?"])
def test_month_followup_of_cross_year_history_requires_year(question):
    skill = harness()
    ask(skill, "Show production history")
    state = skill._dialogue_state_store.get("collection-session")
    state.period = TimePeriod(date(2019, 8), date(2020, 7), "2019-08 – 2020-06")
    skill._dialogue_state_store.put("collection-session", state)
    r = ask(skill, question)
    assert r["response_type"] == "clarification"
    assert skill._dialogue_state_store.get("collection-session").period == state.period


@pytest.mark.parametrize(
    "first,followup,language",
    [
        ("Show electricity trend from May to June 2020", "And July?", "en-US"),
        ("Mayıs ile Haziran 2020 elektrik eğilimini göster", "Peki Temmuz?", "tr-TR"),
    ],
)
def test_trend_followup_retains_metric_and_year(first, followup, language):
    skill = harness()
    ask(skill, first, language)
    skill._futuregen_service.reneryo.calls.clear()
    r = ask(skill, followup, language)
    call = skill._futuregen_service.reneryo.calls[0]
    assert call[0] == "e" and call[1] == date(2020, 7)
    assert r["response_type"] == "trend"


@pytest.mark.parametrize(
    "question,language",
    [
        ("What period does this cover?", "en-US"),
        ("Hangi dönemi kapsıyor?", "tr-TR"),
        ("When was it recorded?", "en-US"),
        ("Son veri ne zaman kaydedildi?", "tr-TR"),
    ],
)
def test_factory_topic_switch_suspends_previously_selected_finding(question, language):
    skill = harness()
    state = skill._dialogue_state_store.get("collection-session")
    from skill.services.conversation_state import DialogueState

    skill._dialogue_state_store.put(
        "collection-session",
        DialogueState(
            operation="finding",
            active_finding_id="old-finding",
            entity_id="old-resource",
            finding_ids=("old-finding",),
            selected_finding_from_collection=True,
        ),
    )
    ask(skill, "What is our electricity consumption?")
    r = ask(skill, question, language)
    state = skill._dialogue_state_store.get("collection-session")
    assert not state.active_finding_id and not state.finding_ids and not state.entity_id
    assert "finding" not in r["response_type"]
    assert "2020" in r["headline"]


@pytest.mark.parametrize(
    "question",
    [
        "En güncel elektrik tüketimini göster",
        "En güncel üretim miktarını göster",
        "Haziran 2020 elektrik tüketim değerini göster",
        "Haziran 2020 üretim değerini göster",
        "Show latest electricity consumption",
        "Show latest production",
    ],
)
def test_latest_and_value_words_do_not_override_period_amount_intent(question):
    r = ask(harness(), question, "tr-TR" if "göster" in question else "en-US")
    assert "cumulative" not in r["headline"] and "birikimli" not in r["headline"]
    assert "recorded_at" not in r["evidence_rows"][0]
    assert "2020-06" in r["headline"] or "2020" in r["headline"]


@pytest.mark.parametrize(
    "question",
    [
        "How old is the electricity data?",
        "Is electricity consumption current?",
        "Üretim ne kadar eski?",
        "Elektrik verisi güncel mi?",
    ],
)
def test_freshness_questions_answer_timestamp_not_amount_or_series(question):
    r = ask(harness(), question)
    assert r["evidence_rows"][0]["recorded_at"] == date(2020, 7).isoformat()


@pytest.mark.parametrize(
    "question",
    [
        "Show the electricity metric",
        "Explain the electricity metric",
        "Show the electricity meter",
        "Elektrik metriğini açıkla",
        "Elektrik sayacını göster",
    ],
)
def test_explicit_inventory_intents_are_left_to_existing_handlers(question):
    from skill.services.conversation_state import DialogueState

    assert classify_factory_question(question, DialogueState()) is None
    r = ask(harness(), question)
    assert r["response_type"] in {"metrics", "meters"}


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
def test_missing_meter_calculation_keeps_requested_window(language):
    class MissingInWindow(Source):
        async def list_meters(self, start, end):
            amount = None if end == date(2020, 6, 16) else 25
            self.calls.append(("meter", start, end))
            return [
                ReneryoMeter(
                    "m", "Synthetic meter", "electricity", amount, "e", "Electricity"
                )
            ]

    skill = harness(MissingInWindow())
    r = ask(skill, "Electricity consumption from 2020-06-01 to 2020-06-15", language)
    assert "2020-06-01" in r["headline"] and "2020-06-15" in r["headline"]
    assert r["evidence_rows"][0]["consumption"] is None
    assert skill._dialogue_state_store.get("collection-session").period.start == date(2020, 6)
    assert skill._dialogue_state_store.get("collection-session").period.end == date(2020, 6, 16)


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
def test_missing_inventory_consumption_is_not_formatted_as_zero(language):
    row = ReneryoMeter("m", "Synthetic meter", "electricity", None, "e", "Electricity")
    r = meter_inventory_headline(
        [row], TimePeriod(date(2020, 6), date(2020, 7), "June 2020"), language
    )
    assert "0.00" not in r and "0,00" not in r


@pytest.mark.asyncio
async def test_api_inclusive_end_and_prior_bucket_are_excluded_from_evidence():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})

    async def get(path, params):
        assert datetime.fromisoformat(params["datetimeMax"]) < date(2020, 7)
        return {
            "recordCount": 3,
            "records": [
                {"datetime": date(2020, 5).isoformat(), "value": 5, "sampleCount": 1},
                {"datetime": date(2020, 6).isoformat(), "value": 0, "sampleCount": 1},
                {"datetime": date(2020, 7).isoformat(), "value": 9, "sampleCount": 1},
            ],
        }

    client._get = get
    points = await client.metric_values("p", date(2020, 6), date(2020, 7), "MONTHLY")
    assert points == [ReneryoTrendPoint(date(2020, 6), 0, 1)]


@pytest.mark.asyncio
async def test_meter_api_uses_exclusive_end_adapted_to_reneryo_contract():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})

    async def get(path, params):
        if path == "/a/meter/item":
            assert params["datetimeMin"] == date(2020, 6).isoformat()
            assert datetime.fromisoformat(params["datetimeMax"]) == date(
                2020, 7
            ) - timedelta(microseconds=1)
        return {"records": []}

    client._get = get
    assert await client.list_meters(date(2020, 6), date(2020, 7)) == []


@pytest.mark.parametrize(
    "question,language",
    [
        ("What period does this cover?", "en-US"),
        ("Hangi dönemi kapsıyor?", "tr-TR"),
    ],
)
def test_signed_widget_page_context_does_not_reseed_a_previous_topic(
    question, language
):
    skill = harness()

    def widget_ask(text):
        message = _message(text, language)
        message.context["reneryo_context"].update(
            finding_id="old-finding",
            entity_id="old-resource",
            metric_name="Old page metric",
        )
        assert handle_reneryo_query(skill, message)
        return skill.spoken[-1][1]["meta"]["avaros_response"]

    widget_ask("What is our electricity consumption?")
    r = widget_ask(question)
    state = skill._dialogue_state_store.get("collection-session")
    assert not state.active_finding_id and not state.entity_id
    assert state.metric_name == "Tesis Toplam Elektrik Tüketimi"
    assert "2020-06" in r["headline"]


@pytest.mark.parametrize(
    "question", ["Show its energy consumption", "Bunun elektrik tüketimini göster"]
)
def test_regression_entity_pronoun_is_not_replaced_by_factory_electricity(question):
    from skill.services.conversation_state import DialogueState

    skill = harness()
    skill._dialogue_state_store.put(
        "collection-session",
        DialogueState(
            operation="regression_clarification", entity_id="regression-model"
        ),
    )
    r = ask(skill, question)
    assert r["response_type"] == "clarification"
    assert not r["evidence_rows"] and not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize(
    "question",
    [
        "Show production on June 15 2020",
        "15 Haziran 2020 üretimini göster",
        "Show production on June 15th, 2020",
        "Show production on 15th June, 2020",
    ],
)
def test_partial_production_period_uses_daily_domain_values_not_a_whole_month(question):
    source = Source()
    ask(harness(source), question)
    assert source.calls[0] == ("p", date(2020, 6, 15), date(2020, 6, 16), "DAILY")


@pytest.mark.parametrize(
    "question",
    [
        "Electricity consumption from June 1 to June 15 2020",
        "1 Haziran ile 15 Haziran 2020 elektrik tüketimini göster",
    ],
)
def test_unrecognized_named_day_range_is_not_replaced_by_its_last_day(question):
    source = Source()
    r = ask(harness(source), question)
    assert r["response_type"] == "clarification" and not source.calls


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
def test_real_zero_meter_consumption_remains_a_valid_period_answer(language):
    class Zero(Source):
        async def list_meters(self, start, end):
            return [
                ReneryoMeter(
                    "m", "Synthetic meter", "electricity", 0, "e", "Electricity"
                )
            ]

    r = ask(harness(Zero()), "Show electricity consumption in June 2020", language)
    assert r["evidence_rows"][0]["consumption"] == 0
    assert r["evidence_rows"][0]["period_start"] == date(2020, 6).isoformat()
    assert "historical" not in r["headline"] and "tarihsel" not in r["headline"]


@pytest.mark.asyncio
async def test_metric_values_missing_samples_and_null_values_are_not_zero_observations():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})

    async def get(path, params):
        return {
            "recordCount": 2,
            "records": [
                {"datetime": date(2020, 6).isoformat(), "value": 0, "sampleCount": 0},
                {
                    "datetime": date(2020, 6).isoformat(),
                    "value": None,
                    "sampleCount": 1,
                },
            ],
        }

    client._get = get
    assert (
        await client.metric_values("p", date(2020, 6), date(2020, 7), "MONTHLY") == []
    )


@pytest.mark.parametrize("phrase", ["past 90 days", "son 90 gün"])
def test_numeric_relative_days_use_the_requested_duration(phrase):
    now = date(2020, 10, 5)
    period = TimePeriod.from_natural_language(phrase, now=now)
    assert period.end == now and period.start == now - timedelta(days=90)


@pytest.mark.parametrize("phrase", ["2020", "this year", "bu yıl"])
def test_calendar_year_uses_configured_timezone_without_adding_next_january(phrase):
    period = TimePeriod.from_natural_language(
        phrase, now=date(2020, 10, 5), timezone_name="Europe/Istanbul"
    )
    assert period.start == date(2019, 12, 31) + timedelta(hours=21)
    assert period.end == date(2020, 12, 31) + timedelta(hours=21)


@pytest.mark.parametrize('month,language,expected', [
    # Entirely after the last record: no data, not a boundary limitation.
    ('eylül 2026', 'tr-TR', 'Bu dönem için veri yok'),
    ('september 2026', 'en-US', 'There is no data for this period'),
    # Data exists, but Reneryo totals on UTC boundaries a local month does not match.
    ('haziran 2026', 'tr-TR', 'UTC zaman sınırlarıyla'),
    ('june 2026', 'en-US', 'UTC boundaries'),
])
def test_local_month_consumption_names_the_actual_limitation(month, language, expected):
    import asyncio
    from datetime import timezone
    from types import SimpleNamespace
    from skill.domain.models import TimePeriod
    from skill.domain.reneryo_models import ReneryoMetric
    from skill.services.factory_questions import FactoryRequest, answer_factory_question

    metric = ReneryoMetric('e', 'Tesis Toplam Elektrik Tüketimi', 'COUNTER', 'ENERGY', 1436097.5,
                           datetime(2026, 6, 30, 21, tzinfo=timezone.utc))

    async def metrics():
        return [metric]

    async def unexpected(*_args, **_kwargs):
        raise AssertionError('no Reneryo values are needed to abstain')

    service = SimpleNamespace(metrics=metrics, reneryo=SimpleNamespace(metric_values=unexpected))
    period = TimePeriod.from_natural_language(month, timezone_name='Europe/Istanbul',
                                              now=datetime(2026, 10, 23, 7, tzinfo=timezone.utc))
    request = FactoryRequest('amount', 'electricity', f'{month} elektrik tüketimi', use_period=True)
    answer = asyncio.run(answer_factory_question(service, request, period, language, timezone_name='Europe/Istanbul'))
    assert answer.response_type == 'unavailable'
    assert expected in answer.headline, answer.headline
