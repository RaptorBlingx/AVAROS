"""D08 paraphrases must reuse grounded operations, scope and period contracts."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import LocalizedText, MdspNextReview
from skill.services.conversation_state import DialogueState
from skill.services.factory_questions import classify_factory_question, is_historical_change_question
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_factory_questions import Source, date
from tests.test_services.test_finding_collection_dialogue import _Skill, _message

FRESHNESS = [
    ("When was our electricity data last updated?", "en-US", "e"),
    ("Elektrik verimiz en son ne zaman güncellendi?", "tr-TR", "e"),
    ("Elektrik verimizin en son ne zaman güncellendiğini göster", "tr-TR", "e"),
    ("Elektrik verimiz en son ne zaman guncellendi?", "tr-TR", "e"),
    ("How up to date is our production data?", "en-US", "p"),
    ("Üretim verilerimiz ne kadar güncel?", "tr-TR", "p"),
    ("How recent is our electricity data?", "en-US", "e"),
    ("Üretim verilerimiz güncel mi?", "tr-TR", "p"),
]
CHANGE = [
    ("How did electricity consumption change from May to June 2020?", "en-US", "e"),
    ("Mayıs ile Haziran 2020 arasında elektrik tüketimi nasıl değişti?", "tr-TR", "e"),
    ("How has production changed from May to June 2020?", "en-US", "p"),
    ("Mayıs ile Haziran 2020 arasında üretim nasıl değişti?", "tr-TR", "p"),
    ("Did electricity consumption increase from May to June 2020?", "en-US", "e"),
    ("Mayıs ile Haziran 2020 arasında elektrik tüketimi arttı mı?", "tr-TR", "e"),
    ("Mayis ile Haziran 2020 arasinda uretim nasil degisti?", "tr-TR", "p"),
]
OWNERS = [
    ("Who is responsible for it?", "en-US"),
    ("Who owns this finding?", "en-US"),
    ("Who should look into this?", "en-US"),
    ("Bunun sorumlusu kim?", "tr-TR"),
    ("Bu bulgudan kim sorumlu?", "tr-TR"),
    ("Bunu kim incelemeli?", "tr-TR"),
    ("Buna kim bakmalı?", "tr-TR"),
]
REVIEWS = [
    ("What should we look at next?", "en-US"),
    ("What should we inspect next?", "en-US"),
    ("What needs reviewing?", "en-US"),
    ("Sonra neyi incelemeliyiz?", "tr-TR"),
    ("Sırada neyi kontrol etmeliyim?", "tr-TR"),
    ("Neyi incelemem gerekiyor?", "tr-TR"),
]


def ask(skill, text, language):
    message = _message(text, language)
    message.context["reneryo_widget_session_validated"] = True
    before = deepcopy((message.data, message.context))
    assert handle_reneryo_query(skill, message)
    assert (message.data, message.context) == before
    return response(skill)


@pytest.mark.parametrize("text,language,identifier", FRESHNESS)
def test_freshness_is_inventory_timestamp_not_history_or_consumption(text, language, identifier):
    source = Source()
    skill = harness(source)
    answer = ask(skill, text, language)
    metric = next(m for m in asyncio.run(source.list_metrics()) if m.metric_id == identifier)
    assert answer["headline"] == f"{metric.name}: " + (
        "son kayıt zamanı 2020-07-01T00:00:00+00:00." if language == "tr-TR"
        else "latest recorded timestamp 2020-07-01T00:00:00+00:00."
    )
    assert source.calls == []
    assert answer["evidence_rows"][0]["recorded_at"] == metric.last_value_at.isoformat()


@pytest.mark.parametrize("text,language,identifier", CHANGE)
@pytest.mark.parametrize("available", [True, False])
def test_change_question_preserves_subject_operation_and_dates(text, language, identifier, available):
    source = Source(values=available)
    skill = harness(source)
    answer = ask(skill, text, language)
    assert answer["response_type"] == "trend"
    assert source.calls[0] == (identifier, date(2020, 5), date(2020, 7), "DAILY")
    assert not any(call[0] == "meter" for call in source.calls)
    if available:
        assert [row["value"] for row in answer["evidence_rows"]] == [12]
        assert "a trend cannot be calculated" in answer["headline"] or "eğilim hesaplanamıyor" in answer["headline"]
    else:
        assert not answer["evidence_rows"]
        assert "No observations" in answer["headline"] or "gözlem bulunamadı" in answer["headline"]


@pytest.mark.parametrize("language,queries", [
    ("en-US", ["How up to date is our production data?", "How recent is that data?", "How has it changed in the same period?"]),
    ("tr-TR", ["Üretim verilerimiz ne kadar güncel?", "Bu veri en son ne zaman güncellendi?", "Aynı dönemde nasıl değişti?"]),
])
def test_short_followups_keep_existing_production_period_and_change_operation(language, queries):
    source = Source()
    skill = harness(source)
    period = TimePeriod(date(2020, 5), date(2020, 7), "May–June 2020")
    skill._dialogue_state_store.put("collection-session", DialogueState(operation="factory_history", metric_name="Tesis Toplam Üretim Miktarı", period=period))
    for text in queries:
        answer = ask(skill, text, language)
        assert "Tesis Toplam Üretim Miktarı" in answer["headline"]
    assert answer["response_type"] == "trend"
    assert source.calls == [("p", period.start, period.end, "DAILY")]


def selected_finding():
    skill = _Skill()
    ask(skill, "List active findings", "en-US")
    ask(skill, "Explain the first one", "en-US")
    skill._futuregen_service.finding = AsyncMock(wraps=skill._futuregen_service.finding)
    return skill


@pytest.mark.parametrize("text,language", OWNERS)
def test_owner_paraphrase_uses_selected_scoped_finding_and_existing_abstention(text, language):
    skill = selected_finding()
    answer = ask(skill, text, language)
    assert answer["headline"] == (
        "Bu bulgu için Reneryo'da onaylı bir sorumlu ataması sağlanmadı." if language == "tr-TR"
        else "No approved Reneryo owner assignment is available for this finding."
    )
    skill._futuregen_service.finding.assert_awaited_once_with("futuregen", "one")
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("text,language", REVIEWS)
@pytest.mark.parametrize("has_policy", [False, True])
def test_review_paraphrase_narrates_source_policy_or_abstains_without_evaluation(text, language, has_policy):
    skill = selected_finding()
    if has_policy:
        review = MdspNextReview(code="synthetic", version=1, instruction=LocalizedText(en="Review recorded observations.", tr="Kayıtlı gözlemleri inceleyin."), rationale=LocalizedText(en="Observed lag.", tr="Gözlenen gecikme."), evidence_keys=("lagHours",), policy_status="PROVISIONAL", assessment_run_id="synthetic-run", review_link=None)
        skill._futuregen_service.rows = (replace(skill._futuregen_service.rows[0], next_review=review), *skill._futuregen_service.rows[1:])
    answer = ask(skill, text, language)
    assert answer["headline"] == (
        ("Geçici inceleme önerisi: Kayıtlı gözlemleri inceleyin." if language == "tr-TR" else "Provisional next review: Review recorded observations.") if has_policy else
        ("Bu bulgu için desteklenen bir sonraki inceleme önerisi mevcut değil." if language == "tr-TR" else "No supported next review is available for this finding.")
    )
    skill._futuregen_service.finding.assert_awaited_once_with("futuregen", "one")
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("text", [
    "Elektrik verimini göster", "Elektrik verimliliğini göster", "Elektrik verimimizi göster",
    "Elektrik verimiz için verimlilik hesapla", "How did energy efficiency change from May to June 2020?",
])
def test_efficiency_remains_unsupported_even_with_our_data_word(text):
    request = classify_factory_question(text, DialogueState())
    assert request and request.kind == "unsupported"


@pytest.mark.parametrize("text", [
    "Change the electricity settings", "Elektrik ayarlarını değiştir",
    "How will electricity consumption change next month?", "Gelecek ay elektrik nasıl değişecek?",
    "How can we change production?", "Üretimi nasıl değiştirebiliriz?",
])
def test_past_change_recognizer_does_not_add_control_forecast_or_advice(text):
    assert not is_historical_change_question(text)


@pytest.mark.parametrize("text,language", [
    ("How did electricity cost change from May to June 2020?", "en-US"),
    ("Mayıs ile Haziran 2020 arasında elektrik maliyeti nasıl değişti?", "tr-TR"),
    ("How will electricity consumption change next month?", "en-US"),
    ("Gelecek ay elektrik tüketimi nasıl değişecek?", "tr-TR"),
])
def test_unsupported_requests_do_not_execute_domain_reads(text, language):
    skill = harness()
    ask(skill, text, language)
    assert skill._futuregen_service.reneryo.calls == []


@pytest.mark.parametrize("text,language", [("How did humidity change from May to June 2020?", "en-US"), ("Mayıs ile Haziran 2020 arasında nem nasıl değişti?", "tr-TR")])
def test_explicit_missing_subject_does_not_reuse_production(text, language):
    skill = harness()
    skill._dialogue_state_store.put("collection-session", DialogueState(operation="trend", metric_name="Tesis Toplam Üretim Miktarı", period=TimePeriod(date(2020, 5), date(2020, 7), "May–June 2020")))
    answer = ask(skill, text, language)
    assert answer["response_type"] == "unavailable"
    assert skill._futuregen_service.reneryo.calls == []


@pytest.mark.parametrize("text,language", [
    ("What should we look at next for Line 99?", "en-US"),
    ("Hat 99 için neyi incelemem gerekiyor?", "tr-TR"),
])
def test_review_paraphrase_never_discards_explicit_equipment_scope(text, language):
    skill = selected_finding()
    skill._get_asset_registry = lambda: []
    answer = ask(skill, text, language)
    assert answer["response_type"] == "clarification"
    skill._futuregen_service.finding.assert_not_awaited()
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("text", ["How recent is that data?", "When was it last updated?", "How has it changed in the same period?"])
def test_factory_followups_do_not_borrow_a_selected_findings_metric(text):
    state = DialogueState(operation="finding", metric_name="Tesis Toplam Üretim Miktarı", active_finding_id="one")
    assert classify_factory_question(text, state) is None
