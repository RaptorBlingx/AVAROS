"""F3 bounded conversational regressions; all domain data is synthetic."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.conversation_state import DialogueState
from skill.services.dia_query import parse_structured_query
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_comparison_followups import comparison_skill, route
from tests.test_services.test_explicit_query_scope import ASSETS
from tests.test_services.test_finding_collection_dialogue import _message, _Skill


@pytest.mark.parametrize(
    "text,action",
    [
        ("Hangi verilere dayanıyor?", "finding_evidence"),
        ("Hangi verilere dayaniyor?", "finding_evidence"),
        ("What evidence supports it?", "finding_evidence"),
        ("Şimdi neyi gözden geçirmeliyim?", "finding_next_review"),
        ("Simdi neyi gozden gecirmeliyim?", "finding_next_review"),
        ("Ne yapmamı önerirsin?", "finding_next_review"),
        ("Ne yapmami onerirsin?", "finding_next_review"),
        ("What should I review next?", "finding_next_review"),
    ],
)
def test_selected_finding_paraphrases(text, action):
    skill = _Skill()
    handle_reneryo_query(skill, _message("List active findings"))
    handle_reneryo_query(skill, _message("Explain first"))
    assert handle_reneryo_query(
        skill, _message(text, "tr-TR" if not text.startswith("What") else "en-US")
    )
    assert response(skill)["response_type"] == "finding"
    headline = response(skill)["headline"].casefold()
    assert (
        ("566" in headline and "968" in headline)
        if action == "finding_evidence"
        else ("review" in headline or "inceleme" in headline or "gözden" in headline)
    )
    assert (
        skill._dialogue_state_store.get("collection-session").active_finding_id == "one"
    )
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize(
    "text",
    [
        "Hangi verilere dayanıyor?",
        "Şimdi neyi gözden geçirmeliyim?",
        "Ne yapmamı önerirsin?",
    ],
)
def test_unselected_finding_does_not_guess(text):
    skill = _Skill()
    handle_reneryo_query(skill, _message("List active findings"))
    assert handle_reneryo_query(skill, _message(text, "tr-TR"))
    assert response(skill)["response_type"] == "clarification"
    assert "bulgu" in response(skill)["headline"]
    assert not skill._dialogue_state_store.get("collection-session").active_finding_id
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize(
    "text,language",
    [
        ("Which metric is the first one linked to?", "en-US"),
        ("İlki hangi metriğe bağlı?", "tr-TR"),
        ("Ilki hangi metrige bagli?", "tr-TR"),
    ],
)
def test_meter_link_uses_domain_id_not_metric_inventory_order(text, language):
    skill = harness()
    source = skill._futuregen_service.reneryo
    metrics = asyncio.run(source.list_metrics())
    source.list_metrics = AsyncMock(return_value=list(reversed(metrics)))
    handle_reneryo_query(skill, _message("Which meters do we have?"))
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "metrics"
    assert [r["id"] for r in response(skill)["evidence_rows"]] == ["e"]
    assert (
        skill._dialogue_state_store.get("collection-session").metric_name
        == metrics[0].name
    )


@pytest.mark.parametrize("case", ["second", "missing-link", "deleted", "ambiguous"])
def test_meter_link_unresolved_clarifies(case):
    skill = harness()
    source = skill._futuregen_service.reneryo
    meters = asyncio.run(
        source.list_meters(TimePeriod.today().start, TimePeriod.today().end)
    )
    if case == "ambiguous":
        source.list_meters = AsyncMock(
            return_value=meters + [replace(meters[0], meter_id="m2")]
        )
    handle_reneryo_query(skill, _message("Which meters do we have?"))
    if case == "missing-link":
        source.list_meters = AsyncMock(return_value=[replace(meters[0], metric_id="")])
    if case == "deleted":
        source.list_meters = AsyncMock(return_value=[])
    text = (
        "Which metric is the second one linked to?"
        if case == "second"
        else "Which metric is it linked to?"
    )
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)["response_type"] == "clarification"
    assert not response(skill)["evidence_rows"]


@pytest.mark.parametrize(
    "language,first,next_,compare",
    [
        ("en-US", "What is OEE on Line 1 today?", "What about Line 2?", "Compare them"),
        ("tr-TR", "Bugün Hat 1 OEE değeri kaç?", "Peki Hat 2?", "İkisini karşılaştır"),
    ],
)
def test_asset_pair_retains_metric_period_and_candidates(
    language, first, next_, compare
):
    skill = comparison_skill(language)
    route(skill, first, language)
    route(skill, next_, language)
    state = skill._dialogue_state_store.get("collection-session")
    assert state.metrics == (CanonicalMetric.OEE,) and state.asset_ids == ("Line-2",)
    assert state.period.start == TimePeriod.today().start
    assert route(skill, compare, language)["response_type"] == "comparison"
    assert skill.dispatcher.compare.call_args.kwargs["asset_ids"] == [
        "Line-1",
        "Line-2",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "And the previous month?",
        "Önceki ay nasıldı?",
        "Peki önceki ay?",
        "And previous month?",
    ],
)
def test_contextual_previous_month_clarifies_without_read(text):
    skill = harness()
    handle_reneryo_query(skill, _message("Show electricity consumption last month"))
    prior = skill._dialogue_state_store.get("collection-session")
    skill._futuregen_service.reneryo.calls.clear()
    assert handle_reneryo_query(
        skill, _message(text, "tr-TR" if "ay" in text else "en-US")
    )
    assert response(skill)["response_type"] == "clarification"
    assert not skill._futuregen_service.reneryo.calls
    assert skill._dialogue_state_store.get("collection-session").period == prior.period


@pytest.mark.parametrize(
    "text", ["Peki Hat 2 nem?", "Peki Hat 2 sıcaklığı?", "What about Line 2 humidity?"]
)
def test_new_unknown_metric_is_not_retained_oee(text):
    prior = DialogueState(
        metrics=(CanonicalMetric.OEE,),
        asset_ids=("Line-1",),
        operation="kpi",
        period=TimePeriod.today(),
    )
    query = parse_structured_query(text, assets=ASSETS, prior=prior)
    assert not query.metrics


def test_organization_change_clears_selected_finding_before_followup():
    skill = _Skill()
    handle_reneryo_query(skill, _message("List active findings"))
    handle_reneryo_query(skill, _message("Explain first"))
    msg = _message("Hangi verilere dayanıyor?", "tr-TR")
    msg.context["reneryo_context"]["organization_id"] = "another-org"
    handle_reneryo_query(skill, msg)
    state = skill._dialogue_state_store.get("collection-session")
    assert state is None or not state.active_finding_id


@pytest.mark.parametrize(
    "text,metric,asset,period",
    [
        (
            "Peki dün Hat 2 hurda oranı?",
            CanonicalMetric.SCRAP_RATE,
            "Line-2",
            "yesterday",
        ),
        (
            "What about Line 2 scrap rate yesterday?",
            CanonicalMetric.SCRAP_RATE,
            "Line-2",
            "yesterday",
        ),
        ("Peki Hat 10?", CanonicalMetric.OEE, "Line-10", "today"),
        ("What about Line 10?", CanonicalMetric.OEE, "Line-10", "today"),
    ],
)
def test_explicit_followup_scope_overrides_only_requested_fields(
    text, metric, asset, period
):
    prior = DialogueState(
        metrics=(CanonicalMetric.OEE,),
        asset_ids=("Line-1",),
        operation="kpi",
        period=TimePeriod.today(),
    )
    query = parse_structured_query(text, assets=ASSETS, prior=prior)
    assert query.metrics == (metric,) and query.asset_ids == (asset,)
    assert query.period.start == TimePeriod.from_natural_language(period).start


def test_canonical_failed_frame_also_retains_organization():
    skill = comparison_skill("en-US")
    route(skill, "What is OEE on Line 99 today?", "en-US")
    assert (
        skill._dialogue_state_store.get("collection-session").organization_id
        == "futuregen"
    )


@pytest.mark.parametrize("operation", ["kpi", "compare", "trend", "metric_detail"])
def test_meter_link_cannot_select_stale_meter_after_topic_change(operation):
    skill = harness()
    handle_reneryo_query(skill, _message("Which meters do we have?"))
    prior = skill._dialogue_state_store.get("collection-session")
    skill._dialogue_state_store.put(
        "collection-session", replace(prior, operation=operation)
    )
    skill._futuregen_service.reneryo.calls.clear()
    handle_reneryo_query(skill, _message("Which metric is the first one linked to?"))
    assert response(skill)["response_type"] == "clarification"
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize(
    "text,language",
    [
        ("Show its history", "en-US"),
        ("Geçmişini göster", "tr-TR"),
        ("Gecmisini goster", "tr-TR"),
    ],
)
def test_linked_metric_history_and_period_keep_metric_and_operation(text, language):
    skill = harness()
    handle_reneryo_query(skill, _message("Which meters do we have?"))
    handle_reneryo_query(skill, _message("Which metric is the first one linked to?"))
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "trend"
    assert skill._futuregen_service.reneryo.calls[-1][0] == "e"
    handle_reneryo_query(skill, _message("And June 2020?", language))
    assert response(skill)["response_type"] == "trend"
    assert skill._futuregen_service.reneryo.calls[-1][0] == "e"
    assert skill._futuregen_service.reneryo.calls[-1][1].year == 2020


def test_turkish_historical_seyir_uses_existing_direction_calculation():
    skill = harness()
    handle_reneryo_query(
        skill, _message("Elektrik tüketiminin geçmiş aylardaki seyrini göster", "tr-TR")
    )
    assert response(skill)["response_type"] == "trend"
    assert (
        "20" in response(skill)["headline"] and "artıyor" in response(skill)["headline"]
    )


@pytest.mark.parametrize(
    "text,language",
    [("What evidence supports it?", "en-US"), ("Hangi verilere dayanıyor?", "tr-TR")],
)
def test_evidence_without_selected_finding_asks_selection_without_source_read(
    text, language
):
    skill = _Skill()
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "clarification"
    assert not skill._futuregen_service.requests
    assert skill._futuregen_service.evaluations == 0
