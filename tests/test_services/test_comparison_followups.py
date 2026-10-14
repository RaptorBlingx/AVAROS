"""Bilingual comparison frames, scoped routing and truthful limitations."""

from unittest.mock import Mock

import pytest

from skill._handlers import handle_metric_query_fallback
from skill._reneryo_handlers import try_arbitrate_legacy_intent
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.conversation_state import DialogueState
from skill.services.dia_query import QueryOperation, parse_structured_query, is_period_follow_up
from skill.services.response_builder import create_response_builder
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.helpers.stub_adapter import StubAdapter
from tests.test_services.test_explicit_query_scope import setup_skill, widget_message, ASSETS
from tests.test_services.test_factory_predeployment import ask, harness

NATURAL = [
    ("Which line had better OEE yesterday, Line 1 or Line 2?", "en-US", CanonicalMetric.OEE),
    ("Dün Hat 1 mi yoksa Hat 2 mi daha iyi OEE değerine sahipti?", "tr-TR", CanonicalMetric.OEE),
    ("Which line consumed more energy yesterday, Line 1 or Line 2?", "en-US", CanonicalMetric.ENERGY_TOTAL),
    ("Dün Hat 1 mi yoksa Hat 2 mi daha fazla enerji tüketti?", "tr-TR", CanonicalMetric.ENERGY_TOTAL),
]
PRONOUNS = [("Compare them.", "en-US"), ("İkisini karşılaştır.", "tr-TR"), ("Onları karşılaştır.", "tr-TR")]
PERIODS = [("And yesterday?", "en-US"), ("Peki dün?", "tr-TR"), ("And June 2020?", "en-US"), ("Peki Haziran 2020?", "tr-TR")]


def comparison_skill(language):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.dispatcher.compare = Mock(wraps=skill.dispatcher.compare)
    skill.response_builder = create_response_builder(language)
    return skill


def route(skill, text, language, entry="fallback"):
    skill._response_language = language
    skill.response_builder = create_response_builder(language)
    message = widget_message(text, language)
    assert (handle_metric_query_fallback(skill, message) if entry == "fallback"
            else try_arbitrate_legacy_intent(skill, message, "kpi.oee"))
    assert message.data["utterance"] == text if "utterance" in message.data else True
    assert message.context["reneryo_context"]["organization_id"] == "futuregen"
    return skill.spoken[-1][1]["meta"]["avaros_response"]


@pytest.mark.parametrize("text,language,metric", NATURAL)
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_natural_comparison_is_not_a_kpi_collection(text, language, metric, entry):
    skill = comparison_skill(language)
    response = route(skill, text, language, entry)
    assert response["response_type"] == "comparison"
    assert response["language"] == language
    query = skill.dispatcher.compare.call_args.kwargs
    assert query["metric"] == metric and query["asset_ids"] == ["Line-1", "Line-2"]
    assert query["period"].start == TimePeriod.from_natural_language("yesterday").start
    assert not skill._futuregen_service.reneryo.calls
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize("text,language", PRONOUNS + PERIODS)
def test_followups_keep_metric_participants_and_explicit_period(text, language):
    skill = comparison_skill("en-US")
    route(skill, "Compare OEE for Line 1 and Line 2 today", "en-US")
    response = route(skill, text, language)
    assert response["response_type"] == "comparison" and response["language"] == language
    query = skill.dispatcher.compare.call_args.kwargs
    assert query["metric"] == CanonicalMetric.OEE
    assert query["asset_ids"] == ["Line-1", "Line-2"]
    assert query["period"].start == TimePeriod.from_natural_language("today" if (text, language) in PRONOUNS else "June 2020" if "2020" in text else "yesterday").start
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", PRONOUNS)
@pytest.mark.parametrize("prior", [None, DialogueState(operation="findings"), DialogueState(operation="compare", metrics=(CanonicalMetric.OEE,), asset_ids=("Line-1",))])
def test_pronouns_without_two_grounded_participants_clarify(text, language, prior):
    skill = comparison_skill(language)
    if prior: skill._dialogue_state_store.put("collection-session", prior)
    assert route(skill, text, language)["response_type"] == "clarification"
    skill.dispatcher.compare.assert_not_called()
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text", ["And boiler 99 yesterday?", "Peki kazan 99 dün?", "And electricity yesterday?", "Peki bulgular?", "And yesterday at 10:00?"])
def test_only_period_shorthand_enters_asset_followup(text):
    assert not is_period_follow_up(text)


@pytest.mark.parametrize("text,language", PRONOUNS)
def test_topic_change_drops_old_comparison_candidates(text, language):
    prior = DialogueState(operation="kpi", metrics=(CanonicalMetric.THROUGHPUT,), asset_ids=("Line-2",), period=TimePeriod.today())
    query = parse_structured_query(text, assets=ASSETS, prior=prior)
    assert query.metrics == (CanonicalMetric.THROUGHPUT,) and query.asset_ids == ("Line-2",)
    assert query.operation is QueryOperation.COMPARE


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
@pytest.mark.parametrize("code", ["GENERIC_REST_NO_DATA", "GENERIC_REST_MAPPING_NOT_FOUND", "ASSET_METRIC_UNAVAILABLE"])
def test_resolved_comparison_no_data_is_not_equipment_scope(language, code):
    skill = comparison_skill(language)
    skill.dispatcher.compare.side_effect = AdapterError(message="empty", code=code, user_message="I couldn't find data for that period.")
    text = "Compare OEE for Line 1 and Line 2 yesterday" if language == "en-US" else "Dün Hat 1 ve Hat 2 OEE değerlerini karşılaştır"
    response = route(skill, text, language)
    assert response["response_type"] == "unavailable" and not response["evidence_rows"]
    assert "equipment scope" not in response["headline"] and "ekipman kapsam" not in response["headline"]
    state = skill._dialogue_state_store.get("collection-session")
    assert state.asset_ids == ("Line-1", "Line-2") and state.period.start == TimePeriod.from_natural_language("yesterday").start
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", [("Compare OEE and throughput for Line 1 and Line 2", "en-US"), ("Hat 1 ve Hat 2 OEE ve throughput değerlerini karşılaştır", "tr-TR")])
def test_multiple_metrics_are_not_silently_narrowed(text, language):
    skill = comparison_skill(language)
    response = route(skill, text, language)
    assert response["response_type"] == "clarification"
    assert ("one metric" if language == "en-US" else "tek bir metrik") in response["headline"]
    skill.dispatcher.compare.assert_not_called()


@pytest.mark.parametrize("text,language", [("Show the electricity meter reading in June 2020.", "en-US"), ("Haziran 2020 elektrik sayaç okuma değerini göster.", "tr-TR")])
def test_historical_reading_explains_actual_interface_limitation(text, language):
    skill = harness()
    response = ask(skill, text, language)
    assert response["response_type"] == "unavailable" and not response["evidence_rows"]
    assert "historical cumulative" in response["headline"] if language == "en-US" else "tarihsel birikimli" in response["headline"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language,_metric", NATURAL)
def test_line_translation_resolves_only_existing_english_registry_labels(text, language, _metric):
    from skill.domain.models import Asset
    skill = comparison_skill(language)
    skill._get_asset_registry = lambda: [Asset("Line-1", "Line 1", "line"), Asset("Line-2", "Line 2", "line")]
    assert route(skill, text, language)["response_type"] == "comparison"
    assert skill.dispatcher.compare.call_args.kwargs["asset_ids"] == ["Line-1", "Line-2"]


@pytest.mark.parametrize("text,language", [("Which line had better OEE yesterday, Line 1 or Line 10?", "en-US"), ("Dün Hat 1 mi yoksa Hat 10 mu daha iyi OEE değerine sahipti?", "tr-TR")])
def test_natural_comparison_cannot_invent_unconfigured_line_ten(text, language):
    skill = comparison_skill(language)
    skill._get_asset_registry = lambda: ASSETS[:2]
    assert route(skill, text, language)["response_type"] == "clarification"
    skill.dispatcher.compare.assert_not_called()
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", PRONOUNS)
def test_no_candidates_survive_a_metric_and_asset_topic_change(text, language):
    from skill.services.dia_dialogue import try_handle_structured_query
    skill = comparison_skill(language)
    route(skill, "Compare OEE for Line 1 and Line 2 today", "en-US")
    topic = widget_message("What about throughput for Line 10 today?", "en-US")
    assert try_handle_structured_query(skill, topic, include_simple_kpi=True)
    state = skill._dialogue_state_store.get("collection-session")
    assert state.metrics == (CanonicalMetric.THROUGHPUT,)
    assert state.answer_evidence == ({"asset_id": "Line-10"},)
    previous_calls = skill.dispatcher.compare.call_count
    assert route(skill, text, language)["response_type"] == "clarification"
    assert skill.dispatcher.compare.call_count == previous_calls


@pytest.mark.parametrize("text,language", PRONOUNS)
def test_removed_registry_participants_are_not_reused(text, language):
    prior = DialogueState(operation="compare", metrics=(CanonicalMetric.OEE,), asset_ids=("Line-1", "Line-99"), period=TimePeriod.today())
    query = parse_structured_query(text, assets=ASSETS, prior=prior)
    assert "no longer configured" in query.ambiguity


def test_ikisini_cannot_choose_two_from_three_participants():
    query = parse_structured_query("İkisini karşılaştır", assets=ASSETS, prior=DialogueState(operation="compare", metrics=(CanonicalMetric.OEE,), asset_ids=tuple(a.asset_id for a in ASSETS)))
    assert "two assets" in query.ambiguity


@pytest.mark.parametrize("text,expected", [("And previous month?", "last month"), ("Peki önceki ay?", "geçen ay"), ("Peki son hafta?", "geçen hafta"), ("And 2020-06-15?", "2020-06-15")])
def test_period_followups_use_existing_source_period_aliases(text, expected):
    assert is_period_follow_up(text)
    prior = DialogueState(operation="compare", metrics=(CanonicalMetric.OEE,), asset_ids=("Line-1", "Line-2"), period=TimePeriod.today())
    query = parse_structured_query(text, assets=ASSETS, prior=prior)
    assert query.period.start == TimePeriod.from_natural_language(expected).start
    assert query.operation is QueryOperation.COMPARE and query.asset_ids == prior.asset_ids


@pytest.mark.parametrize("text", ["Compare energy consumed per unit for Line 1 and Line 2", "Hat 1 ve Hat 2 birim başına enerji tüketimini karşılaştır"])
def test_comparison_consumption_wording_does_not_replace_an_explicit_rate_metric(text):
    assert parse_structured_query(text, assets=ASSETS).metrics == (CanonicalMetric.ENERGY_PER_UNIT,)


@pytest.mark.parametrize("language", ["en-US", "tr-TR"])
@pytest.mark.parametrize("difference", [0, 5])
def test_total_energy_comparison_narrates_values_without_claiming_efficiency(language, difference):
    from skill.domain.results import ComparisonItem, ComparisonResult
    result = ComparisonResult(metric=CanonicalMetric.ENERGY_TOTAL, items=[ComparisonItem("Line-1", 75, 1), ComparisonItem("Line-2", 75+difference, 2)], period=TimePeriod.today(), winner_id="Line-1", difference=difference, unit="kWh", aggregation="sum")
    text = create_response_builder(language).format_comparison_result(result)
    assert "efficient" not in text and "verimli" not in text
    assert "75" in text and str(75+difference) in text
    assert ("equal" in text or "eşit" in text) if difference == 0 else ("lower" in text or "düşük" in text)
    assert result.items[0].asset_id == "Line-1" and result.items[1].value == 75+difference
