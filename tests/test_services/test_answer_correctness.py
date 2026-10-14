"""D02–D05 regressions using synthetic inventory and recorded domain calls."""

import pytest
from unittest.mock import AsyncMock

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.exceptions import AdapterError, ValidationError
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric
from skill.services.conversation_state import DialogueState
from skill.services.dia_query import parse_structured_query
from skill.services.futuregen import FutureGenService
from tests.test_services.test_factory_questions import Source, date
from tests.test_services.test_finding_collection_dialogue import _Skill, _message
from tests.test_services.test_explicit_query_scope import ASSETS


def harness(source=None):
    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    skill._futuregen_service = FutureGenService(source or Source())
    return skill


def response(skill):
    return skill.spoken[-1][1]["meta"]["avaros_response"]


@pytest.mark.parametrize("text,language", [
    ("How much did electricity cost us in June 2020?", "en-US"),
    ("Haziran 2020’de elektrik için ne kadar ödedik?", "tr-TR"),
    ("How much did we pay for electricity in June 2020?", "en-US"),
    ("What was our electricity bill in June 2020?", "en-US"),
    ("How much money did we spend on electricity?", "en-US"),
    ("Haziran 2020 elektrik faturası ne kadardı?", "tr-TR"),
    ("Elektrik için ne kadar para harcadık?", "tr-TR"),
    ("Elektriğe kaç lira ödedik?", "tr-TR"),
])
def test_cost_never_executes_consumption(text, language):
    skill = harness()
    assert handle_reneryo_query(skill, _message(text, language))
    assert not response(skill)["evidence_rows"]
    assert response(skill)["response_type"] == "unavailable"
    assert ("cost" if language == "en-US" else "maliyet") in response(skill)["headline"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", [
    ("How much electricity will we use next month?", "en-US"),
    ("Gelecek ay ne kadar elektrik tüketeceğiz?", "tr-TR"),
    ("How much electricity did we use last year?", "en-US"),
    ("Geçen yıl ne kadar elektrik tükettik?", "tr-TR"),
    ("Show electricity consumption tomorrow", "en-US"),
    ("Yarın elektrik tüketimini göster", "tr-TR"),
    ("Show electricity consumption over the last six months", "en-US"),
    ("Son altı ay elektrik tüketimini göster", "tr-TR"),
    ("Show electricity trend next month", "en-US"),
    ("Gelecek ay elektrik eğilimini göster", "tr-TR"),
])
def test_unhandled_period_never_defaults_to_latest(text, language):
    skill = harness()
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "clarification"
    assert not response(skill)["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,canonical", [
    ("How much electricity did we use in the previous month?", "last month"),
    ("Önceki ay ne kadar elektrik tükettik?", "geçen ay"),
    ("Dun ne kadar elektrik tukettik?", "dün"),
])
def test_supported_relative_period_reaches_domain_before_disclosed_history(text, canonical):
    skill = harness()
    assert handle_reneryo_query(skill, _message(text))
    expected = TimePeriod.from_natural_language(canonical)
    calls = skill._futuregen_service.reneryo.calls
    assert calls and calls[0][0] == "e"
    assert calls[0][1:3] == (expected.start, expected.end)


@pytest.mark.parametrize("text", ["What is the OEE of Line 10 today?", "Hat 10’un bugünkü OEE değeri ne?"])
def test_asset_query_keeps_today(text):
    query = parse_structured_query(text, assets=ASSETS)
    assert not query.ambiguity
    assert query.asset_ids == ("Line-10",)
    expected = TimePeriod.today()
    assert query.period is not None
    assert query.period.start == expected.start
    assert query.period.end.date() == expected.end.date()


@pytest.mark.parametrize("text,language", [("Show humidity trend.", "en-US"), ("Nem eğilimini göster.", "tr-TR")])
def test_explicit_missing_metric_cannot_retry_previous_subject(text, language):
    skill = harness()
    skill._dialogue_state_store.put("collection-session", DialogueState(
        operation="factory_history", metric_name="Tesis Toplam Üretim Miktarı",
        period=TimePeriod(date(2020, 6), date(2020, 7), "June 2020"),
    ))
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "unavailable"
    assert not response(skill)["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", [
    ("Do not show findings; show metrics instead.", "en-US"),
    ("Bulguları gösterme, onun yerine metrikleri göster.", "tr-TR"),
    ("Show metrics, not findings.", "en-US"),
    ("Show metrics instead of findings.", "en-US"),
    ("Metrikleri göster, bulguları değil.", "tr-TR"),
    ("Bulgular yerine metrikleri göster.", "tr-TR"),
])
def test_replacement_operation_excludes_findings(text, language):
    skill = _Skill()
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "metrics"
    assert not skill._futuregen_service.requests
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("seed,correction,language", [
    ("Show electricity consumption in June 2020.", "No, production instead.", "en-US"),
    ("Haziran 2020 elektrik tüketimini göster.", "Elektrik değil, üretimi göster.", "tr-TR"),
])
def test_metric_correction_preserves_period_amount(seed, correction, language):
    skill = harness()
    assert handle_reneryo_query(skill, _message(seed, language))
    skill._futuregen_service.reneryo.calls.clear()
    assert handle_reneryo_query(skill, _message(correction, language))
    assert response(skill)["response_type"] == "information"
    calls = skill._futuregen_service.reneryo.calls
    assert calls[0][:3] == ("p", date(2020, 6), date(2020, 7))
    assert all(call[0] == "p" for call in calls)
    assert "5,000" not in response(skill)["headline"]


@pytest.mark.parametrize("text,language", [
    ("Do not show findings", "en-US"), ("Bulguları gösterme", "tr-TR"),
    ("Do not show findings; do not show metrics", "en-US"),
    ("Elektrik değil", "tr-TR"),
])
def test_bare_or_contradictory_exclusion_clarifies_without_execution(text, language):
    skill = _Skill()
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "clarification"
    assert not skill._futuregen_service.requests
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("exception", [AdapterError, ValidationError])
@pytest.mark.parametrize("text,language", [
    ("Show humidity trend", "en-US"), ("Nem eğilimini göster", "tr-TR"),
])
def test_failed_explicit_trend_executes_once_and_clears_stale_metric(exception, text, language):
    skill = harness()
    service = skill._futuregen_service
    service.trend = AsyncMock(side_effect=exception("Synthetic failure", code="TEST_FAILURE"))
    skill._dialogue_state_store.put("collection-session", DialogueState(
        operation="trend", metric_name="Tesis Toplam Üretim Miktarı",
    ))
    with pytest.raises(exception, match="Synthetic failure"):
        handle_reneryo_query(skill, _message(text, language))
    service.trend.assert_awaited_once()
    assert service.trend.call_args.args[0] == text
    assert not skill._dialogue_state_store.get("collection-session").metric_name


class HumiditySource(Source):
    async def list_metrics(self):
        return [*await super().list_metrics(), ReneryoMetric("h", "Humidity", "GAUGE", "RATE")]


@pytest.mark.parametrize("text,language", [
    ("Show humidity trend", "en-US"), ("Nem eğilimini göster", "tr-TR"),
])
def test_configured_metric_without_observations_stays_on_requested_subject(text, language):
    skill = harness(HumiditySource(values=False))
    skill._dialogue_state_store.put("collection-session", DialogueState(
        operation="factory_history", metric_name="Tesis Toplam Üretim Miktarı",
    ))
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "trend"
    assert "Humidity" in response(skill)["headline"]
    assert not response(skill)["evidence_rows"]
    assert all(call[0] == "h" for call in skill._futuregen_service.reneryo.calls)


@pytest.mark.parametrize("text,language", [
    ("Show its trend", "en-US"), ("Eğilimini göster", "tr-TR"),
])
def test_subject_free_trend_followup_retains_metric(text, language):
    skill = harness()
    skill._dialogue_state_store.put("collection-session", DialogueState(
        operation="trend", metric_name="Tesis Toplam Üretim Miktarı",
        period=TimePeriod(date(2020, 6), date(2020, 7), "June 2020"),
    ))
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)["response_type"] == "trend"
    assert all(call[0] == "p" for call in skill._futuregen_service.reneryo.calls)
