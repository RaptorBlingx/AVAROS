"""Independent task questions and source-call assertions for PR71 systemic fixes.

All data are synthetic. These deterministic contract tests do not certify audio.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from skill._handlers import (
    _resolve_whatif_target_value,
    _whatif_percentages,
    _whatif_quantity_text,
)
from skill._helpers import parse_period, request_timezone
from skill.domain.exceptions import ValidationError
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMeter, ReneryoMetric
from skill.services.futuregen import FutureGenService
from skill.services.futuregen_responses import (
    format_reneryo_value,
    meter_inventory_headline,
    metric_inventory_headline,
)
from skill.services.language import speech_text
from skill.services.period_resolution import (
    extract_period_phrase,
    remove_period_reference,
    unsupported_period_reference,
)
from skill.services.quantities import parse_number_words, quantity_number
from skill.services.reneryo_periods import history_resolution, meter_window_exact

UTC = timezone.utc
NOW = datetime(2026, 10, 15, 22, 30, tzinfo=UTC)  # 16 October, 01:30 in Istanbul


@pytest.mark.parametrize(
    "phrase,start,end",
    [
        ("today", "2026-10-15T21:00:00+00:00", NOW.isoformat()),
        ("bugün", "2026-10-15T21:00:00+00:00", NOW.isoformat()),
        ("yesterday", "2026-10-14T21:00:00+00:00", "2026-10-15T21:00:00+00:00"),
        ("dün", "2026-10-14T21:00:00+00:00", "2026-10-15T21:00:00+00:00"),
        ("this week", "2026-10-11T21:00:00+00:00", NOW.isoformat()),
        ("bu ay", "2026-09-30T21:00:00+00:00", NOW.isoformat()),
        ("last month", "2026-08-31T21:00:00+00:00", "2026-09-30T21:00:00+00:00"),
        ("2026-10-15", "2026-10-14T21:00:00+00:00", "2026-10-15T21:00:00+00:00"),
    ],
)
def test_local_calendar_boundaries_share_one_clock(phrase, start, end):
    result = TimePeriod.from_natural_language(
        phrase, timezone_name="Europe/Istanbul", now=NOW
    )
    assert result.start.isoformat() == start
    assert result.end.isoformat() == end


@pytest.mark.parametrize("day,hours", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_dst_calendar_day_keeps_local_midnights(day, hours):
    result = TimePeriod.from_natural_language(
        day, timezone_name="Europe/Berlin", now=datetime(2026, 11, 1, tzinfo=UTC)
    )
    assert (result.end - result.start).total_seconds() == hours * 3600


def test_month_and_year_boundary_and_rolling_elapsed_days():
    now = datetime(2025, 12, 31, 22, 30, tzinfo=UTC)
    period = TimePeriod.from_natural_language(
        "this month", now=now, timezone_name="Europe/Istanbul"
    )
    assert period.start == datetime(2025, 12, 31, 21, tzinfo=UTC)
    rolling = TimePeriod.from_natural_language(
        "last 2 weeks", now=NOW, timezone_name="Europe/Berlin"
    )
    assert rolling.end == NOW and rolling.end - rolling.start == timedelta(days=14)


def profile_skill(bindings):
    profile = SimpleNamespace(
        extra_settings={
            "site_timezone": "Europe/London",
            "organization_timezones": bindings,
        }
    )
    return SimpleNamespace(
        settings_service=SimpleNamespace(get_profile=lambda _: profile),
        _resolve_active_profile=lambda: "reneryo",
    )


def test_timezone_is_bound_to_signed_org_and_ignores_client_claims():
    skill = profile_skill({"factory-a": "Europe/Istanbul"})
    message = SimpleNamespace(
        context={
            "reneryo_context": {
                "organization_id": "factory-a",
                "timezone": "America/New_York",
            }
        }
    )
    assert request_timezone(skill, message) == "Europe/Istanbul"
    assert parse_period(skill, "today", message, now=NOW).start.hour == 21
    message.context["reneryo_context"]["organization_id"] = "factory-b"
    with pytest.raises(ValidationError):
        parse_period(skill, "today", message, now=NOW)
    assert parse_period(skill, "last 10 days", message, now=NOW).end == NOW
    assert parse_period(skill, "latest", message, now=NOW).end == NOW


@pytest.mark.parametrize(
    "text,days",
    [
        ("Could I see outdoor temperature over the past ten days?", 10),
        ("Dış sıcaklığın son on gündeki eğilimini getir.", 10),
        ("Past twenty-one days for humidity, please.", 21),
        ("Nemin son yirmi bir gün içindeki seyri nasıl?", 21),
        ("Use the last three weeks for production.", 21),
        ("Üretim için son üç haftayı kullan.", 21),
    ],
)
def test_spoken_duration_reaches_exact_window(text, days):
    phrase = extract_period_phrase(text)
    assert phrase and not unsupported_period_reference(text)
    result = TimePeriod.from_natural_language(phrase, now=NOW)
    assert result.end == NOW and result.end - result.start == timedelta(days=days)
    assert not extract_period_phrase(remove_period_reference(text))


@pytest.mark.parametrize(
    "text",
    [
        "Show temperature over the past umpteen days.",
        "Son birkaç günün sıcaklık eğilimini getir.",
        "Use the past ten months for electricity.",
        "Son on ayın tüketimi ne?",
        "Show humidity for the past ten point five days.",
    ],
)
def test_unresolved_explicit_duration_cannot_default(text):
    phrase = extract_period_phrase(text)
    if phrase:
        with pytest.raises(ValueError):
            TimePeriod.from_natural_language(phrase, now=NOW)
    else:
        assert unsupported_period_reference(text)


@pytest.mark.parametrize(
    "words,expected",
    [
        ("ninety", "90"),
        ("doksan", "90"),
        ("one hundred and twenty three", "123"),
        ("yüz yirmi üç", "123"),
        ("ten point five", "10.5"),
        ("on virgül beş", "10.5"),
        ("ten twenty", None),
        ("on yirmi", None),
    ],
)
def test_shared_number_grammar(words, expected):
    assert parse_number_words(words) == expected


@pytest.mark.parametrize(
    "text,number",
    [
        ("What if OEE increases by ten percent?", 10),
        ("OEE yüzde on artarsa ne olur?", 10),
        ("OEE yüzde on virgül beş düşerse?", 10.5),
    ],
)
def test_scenario_spoken_change_is_not_five_percent_default(text, number):
    assert _whatif_percentages(_whatif_quantity_text(text)) == [number]


@pytest.mark.parametrize(
    "text", ["What if OEE reaches ninety percent?", "OEE yüzde doksan olursa ne olur?"]
)
def test_spoken_absolute_target(text):
    assert _resolve_whatif_target_value(text) == 90


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_ambiguous_trend_cannot_depend_on_inventory_order(reverse):
    metrics = [
        ReneryoMetric("inside", "Indoor Temperature", "GAUGE", "TEMPERATURE"),
        ReneryoMetric("outside", "Outdoor Temperature", "GAUGE", "TEMPERATURE"),
    ]
    source = SimpleNamespace(
        list_metrics=AsyncMock(return_value=metrics[::-1] if reverse else metrics),
        metric_values=AsyncMock(return_value=[]),
    )
    with pytest.raises(ValidationError, match="Ambiguous"):
        await FutureGenService(source).trend(
            "Show temperature trend over the past ten days.",
            TimePeriod.rolling_days(10, now=NOW),
        )
    source.metric_values.assert_not_called()
    result = await FutureGenService(source).trend(
        "Show Outdoor Temperature trend over the past ten days.",
        TimePeriod.rolling_days(10, now=NOW),
    )
    assert result.metric.metric_id == "outside"
    assert source.metric_values.call_args.args[0] == "outside"


@pytest.mark.asyncio
async def test_explicit_empty_trend_does_not_fetch_other_history():
    metric = ReneryoMetric("outside", "Outdoor Temperature", "GAUGE", "TEMPERATURE")
    source = SimpleNamespace(
        metric_values=AsyncMock(return_value=[]), recent_metric_values=AsyncMock()
    )
    result = await FutureGenService(source).trend(
        "Outdoor Temperature yesterday", TimePeriod.yesterday(now=NOW), metric=metric
    )
    assert not result.points
    source.recent_metric_values.assert_not_called()


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
def test_mixed_units_remain_individual_values(language):
    meters = [
        ReneryoMeter(
            "a", "Electricity", "ELECTRIC", 100, "e", "Energy", unit_group="ENERGY"
        ),
        ReneryoMeter(
            "b", "Water", "WATER", 5, "w", "Water volume", unit_group="VOLUME"
        ),
    ]
    text = meter_inventory_headline(meters, TimePeriod.yesterday(now=NOW), language)
    assert "105" not in text and "100 kWh" in text and "5 m³" in text
    assert "105" not in text and "totals" not in text
    assert (
        "kilovatsaat" in speech_text(text, language)
        if language == "tr-TR"
        else "kilowatt hours" in speech_text(text, language)
    )


def test_local_bucket_contract_and_small_quantity_presentation():
    local_month = TimePeriod.from_natural_language(
        "last month", now=NOW, timezone_name="Europe/Istanbul"
    )
    assert history_resolution(local_month, "MONTHLY") == "HOURLY"
    assert not meter_window_exact(local_month.start, local_month.end)
    for value in [59645.93, 0.00000000423, -0.00004]:
        for language in ["en-US", "tr-TR"]:
            display = format_reneryo_value(value, "ENERGY", language)
            speech = speech_text(display, language)
            assert "e-" not in speech and "e+" not in speech
            if language == "en-US":
                assert quantity_number(value, language, grouped=False) in speech
            else:
                from skill.services.turkish_speech import spoken_number
                assert spoken_number(quantity_number(value, language, grouped=False)) in speech


def test_long_inventory_has_compact_headline():
    rows = [
        ReneryoMetric(str(i), f"Source {i}", "GAUGE", "TEMPERATURE") for i in range(20)
    ]
    assert "17 more" in metric_inventory_headline(rows, "en-US")
    assert "Source 19" not in metric_inventory_headline(rows, "en-US")


@pytest.mark.parametrize("entry", ["metric_fallback", "intent_failure", "registered"])
@pytest.mark.parametrize(
    "question",
    [
        "Compare OEE for Line 1 and Line 2 today.",
        "Hat 1 ve Hat 2 için bugünkü OEE değerlerini karşılaştır.",
    ],
)
def test_scoped_handoff_converges_for_all_existing_entries(
    entry, question, monkeypatch
):
    from skill import _handlers, _reneryo_handlers
    from tests.test_services.test_explicit_query_scope import ASSETS
    from tests.test_services.test_factory_predeployment import harness
    from tests.test_services.test_finding_collection_dialogue import _message

    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    skill._sync_response_language = lambda _: None
    structured = Mock(return_value=True)
    monkeypatch.setattr(
        "skill.services.dia_dialogue.try_handle_structured_query", structured
    )
    message = _message(question)
    message.context["reneryo_widget_session_validated"] = True
    if entry == "metric_fallback":
        _handlers.handle_metric_query_fallback(skill, message)
    elif entry == "intent_failure":
        _handlers.handle_intent_failure(skill, message)
    else:
        assert _reneryo_handlers.try_arbitrate_legacy_intent(
            skill, message, "compare.oee"
        )
    structured.assert_called_once()
    assert not skill.spoken


@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_unbound_timezone_stops_before_source_reads(entry):
    from skill._reneryo_handlers import (
        handle_reneryo_query,
        try_arbitrate_legacy_intent,
    )
    from tests.test_services.test_factory_predeployment import harness
    from tests.test_services.test_finding_collection_dialogue import _message

    skill = harness()
    skill.settings_service = profile_skill({}).settings_service
    skill._resolve_active_profile = lambda: "reneryo"
    message = _message("Show production today.")
    assert (
        handle_reneryo_query(skill, message)
        if entry == "fallback"
        else try_arbitrate_legacy_intent(skill, message, "kpi.production")
    )
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "clarification"
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize(
    "text",
    ["OEE rises ten percent", "OEE increases by ten percent", "OEE yüzde on artarsa"],
)
def test_percentage_suffix_and_prefix_share_grammar(text):
    assert _whatif_percentages(_whatif_quantity_text(text)) == [10]


def test_turkish_attached_target_suffix_and_quantity_names():
    assert _resolve_whatif_target_value("OEE yüzde doksana çıkarsa ne olur?") == 90
    from skill.services.quantities import normalize_quantity_expressions

    assert (
        normalize_quantity_expressions("Line Ten temperature") == "line ten temperature"
    )
    assert normalize_quantity_expressions("On Bir Fırını") == "on bir fırını"


@pytest.mark.parametrize(
    "text", ["Show temperature today and yesterday.", "Bugün ve dün sıcaklığı göster."]
)
def test_two_relative_periods_cannot_silently_choose_one(text):
    assert unsupported_period_reference(text)


def test_naive_request_clock_cannot_use_machine_timezone():
    with pytest.raises(ValueError, match="clock"):
        TimePeriod.from_natural_language("today", now=datetime(2026, 10, 16, 1, 30, tzinfo=None))  # noqa: DTZ001 - intentional invalid clock


def test_request_clock_survives_handoffs_without_wire_context_changes():
    from skill._helpers import request_clock

    message = SimpleNamespace(
        context={"reneryo_context": {"organization_id": "factory-a"}}
    )
    clock = request_clock(message)
    assert request_clock(message) is clock
    period = parse_period(
        profile_skill({"factory-a": "Europe/Istanbul"}), "today", message
    )
    assert period.end == clock
    assert message.context == {"reneryo_context": {"organization_id": "factory-a"}}


def test_ambiguous_new_subject_clears_previous_trend_subject():
    from skill._reneryo_handlers import handle_reneryo_query
    from skill.services.conversation_state import DialogueState
    from tests.test_services.test_factory_predeployment import harness
    from tests.test_services.test_finding_collection_dialogue import _message

    source = SimpleNamespace(
        list_metrics=AsyncMock(
            return_value=[
                ReneryoMetric("inside", "Indoor Temperature", "GAUGE", "TEMPERATURE"),
                ReneryoMetric("outside", "Outdoor Temperature", "GAUGE", "TEMPERATURE"),
            ]
        ),
        metric_values=AsyncMock(),
    )
    skill = harness(source)
    skill._dialogue_state_store.put(
        "collection-session", DialogueState(operation="trend", metric_name="Humidity")
    )
    assert handle_reneryo_query(skill, _message("Show temperature trend."))
    assert (
        skill.spoken[-1][1]["meta"]["avaros_response"]["response_type"]
        == "clarification"
    )
    assert not skill._dialogue_state_store.get("collection-session").metric_name
    source.metric_values.assert_not_called()


@pytest.mark.parametrize("text", [
    "What if OEE increases by ten percent for Line 2?",
    "What if OEE drops ten point five percent for Line 2?",
    "Hat 2 için OEE yüzde on artarsa ne olur?",
    "Hat 2 OEE yüzde on virgül beş düşerse ne olur?",
])
def test_spoken_quantity_survives_scope_validation_before_scenario(text):
    from skill.services.query_scope import entity_scope
    from tests.test_services.test_explicit_query_scope import ASSETS
    assert entity_scope(text, ASSETS) == (True, False)


def test_scope_quantity_normalization_preserves_registered_asset_names():
    from skill.domain.models import Asset
    from skill.services.query_scope import entity_scope
    assert entity_scope("Show OEE for By Ten Percent", [Asset("source", "By Ten Percent", "line")]) == (True, False)


@pytest.mark.parametrize("text", ["Show OEE for Line 2 over the past ten days.", "Hat 2 OEE değerini son on gün için göster."])
def test_registered_handler_uses_shared_spoken_period_and_original_over_slot(text):
    from skill._metric_handlers import _resolve_handler_period
    skill = profile_skill({"factory-a": "UTC"})
    message = SimpleNamespace(data={"utterance": text, "period": "last week"}, context={"reneryo_context": {"organization_id": "factory-a"}})
    period = _resolve_handler_period(skill, message)
    assert period.end - period.start == timedelta(days=10)
    assert message.data["utterance"] == text


def test_registered_handler_cannot_default_unresolved_duration():
    from skill._metric_handlers import _resolve_handler_period
    message = SimpleNamespace(data={"utterance": "Show OEE for Line 2 over the past umpteen days.", "period": "today"}, context={})
    with pytest.raises(ValidationError):
        _resolve_handler_period(profile_skill({}), message)


def test_semantic_period_slot_cannot_introduce_a_window_absent_from_source():
    from skill._reneryo_handlers import _query_period
    with pytest.raises(ValueError, match="grounded"):
        _query_period(SimpleNamespace(), "Show temperature trend", None, "last month")


@pytest.mark.asyncio
async def test_inherited_requested_period_cannot_fetch_another_history():
    metric = ReneryoMetric("outside", "Outdoor Temperature", "GAUGE", "TEMPERATURE")
    source = SimpleNamespace(metric_values=AsyncMock(return_value=[]), recent_metric_values=AsyncMock())
    await FutureGenService(source).trend("Show its trend", TimePeriod.from_natural_language("january 2025"), metric=metric, allow_history_fallback=False)
    source.recent_metric_values.assert_not_called()


@pytest.mark.parametrize("text,expected", [
    ("Geçen takvim ayının sıcaklık eğilimini göster.", "geçen ay"),
    ("Geçen haftasının elektrik verisi", "geçen hafta"),
    ("Bu ayın üretimini göster.", "bu ay"),
    ("Bu haftanın sıcaklık eğilimi", "bu hafta"),
])
def test_shared_calendar_grammar_retains_turkish_case_and_possession(text, expected):
    assert extract_period_phrase(text) == expected
    assert not unsupported_period_reference(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("language,word", [("en-US", "hourly"), ("tr-TR", "saatlik")])
async def test_factory_narrates_the_resolution_actually_requested_from_reneryo(language, word):
    from skill.domain.reneryo_models import ReneryoTrendPoint
    from skill.services.conversation_state import DialogueState
    from skill.services.factory_questions import (
        answer_factory_question,
        classify_factory_question,
    )
    period = TimePeriod.yesterday(now=NOW, timezone_name="Europe/Istanbul")
    metric = ReneryoMetric("p", "Production", "COUNTER", "PIECE")
    source = SimpleNamespace(list_metrics=AsyncMock(return_value=[metric]), metric_values=AsyncMock(return_value=[ReneryoTrendPoint(period.start + timedelta(hours=6), 450, 1)]))
    answer = await answer_factory_question(FutureGenService(source), classify_factory_question("Show production yesterday", DialogueState()), period, language)
    assert source.metric_values.call_args.args[3] == "HOURLY"
    assert word in answer.headline
