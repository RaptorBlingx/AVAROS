from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import (
    LocalizedText,
    MdspEvaluation,
    MdspFinding,
    MdspFindingList,
    MdspNextReview,
    ReneryoMetric,
    ReneryoTrend,
    ReneryoTrendPoint,
)
from skill.services.conversation_state import DialogueStateStore
from skill.services.dia_dialogue import try_handle_structured_query
from skill.services.finding_collection import (
    FindingFilters,
    filters_for,
    is_evaluation_request,
    selection_index,
    selection_requested,
)
from skill.services.semantic_resolver import SemanticAction, SemanticResolution


def _finding(identifier: str, severity: str = "MEDIUM") -> MdspFinding:
    return MdspFinding(
        finding_id=identifier,
        status="ACTIVE",
        severity=severity,
        domain="METRICS",
        entity_type="METRIC_RESOURCE",
        entity_id=f"resource-{identifier}",
        title=LocalizedText(
            en=f"Finding {identifier}", tr=f"Bulgu {identifier}"
        ),
        summary=LocalizedText(en="Source trails.", tr="Kaynak geride kalıyor."),
        evidence={
            "metricName": "Cooling degree days - Open Weather",
            "lagHours": 566,
            "allowedLagHours": 72,
            "inferredCadenceSeconds": 86_400,
            "observedSampleCount": 968,
            "lastObservationAt": "2026-08-24T21:00:00.000Z",
            "sourceWatermark": "2026-09-17T10:38:13.000Z",
            "currentSiblingResourceId": "current-resource",
        },
        assumptions=(),
        evaluation_start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        evaluation_end=datetime(2026, 9, 17, tzinfo=timezone.utc),
        source_watermark=None,
        deep_link=None,
        provisional=True,
        metric_name="Cooling degree days - Open Weather",
        rule_id="metric-resource-relative-freshness",
        rule_version=2,
    )


class _Service:
    def __init__(self) -> None:
        self.rows = (_finding("one", "MEDIUM"), _finding("two", "LOW"))
        self.evaluations = 0
        self.requests: list[FindingFilters] = []

    async def evaluate(self, _organization_id: str) -> MdspEvaluation:
        self.evaluations += 1
        return MdspEvaluation("run-1", None, 12, 2, 0)

    async def filtered_findings(
        self, _organization_id: str, *, status: str, severity: str = "", domain: str = ""
    ) -> MdspFindingList:
        filters = FindingFilters(status, severity, domain)
        self.requests.append(filters)
        rows = tuple(
            row
            for row in self.rows
            if (not severity or row.severity == severity)
            and (not domain or row.domain == domain)
        )
        return MdspFindingList(rows, 2, 0, {"MEDIUM": 1, "LOW": 1})

    async def finding(self, _organization_id: str, identifier: str) -> MdspFinding:
        return next(row for row in self.rows if row.finding_id == identifier)

    async def trend(self, _utterance, period) -> ReneryoTrend:
        return ReneryoTrend(
            metric=ReneryoMetric(
                "production",
                "Tesis Toplam Üretim Miktarı",
                "COUNTER",
                "PIECE",
                last_value_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            ),
            period_label=period.display_name,
            aggregation="DAILY",
            points=(),
            direction="unavailable",
            change_percent=None,
        )

    async def metrics(self):
        return [
            ReneryoMetric("humidity", "Humidity - Open Weather", "GAUGE", "RATE"),
            ReneryoMetric(
                "electricity", "Tesis Toplam Elektrik Tüketimi", "COUNTER", "ENERGY"
            ),
        ]


class _Dispatcher:
    @staticmethod
    def _run_async(coroutine):
        return asyncio.run(coroutine)


class _Skill:
    def __init__(self) -> None:
        self._loaded_profile = "reneryo"
        self._response_language = "en-US"
        self._dialogue_state_store = DialogueStateStore()
        self._futuregen_service = _Service()
        self.dispatcher = _Dispatcher()
        self.spoken: list[tuple[str, dict]] = []

    @staticmethod
    def _extract_utterance_text(message) -> str:
        return message.data["utterance"]

    @staticmethod
    def _safe_dispatch(_name: str, callback):
        return callback()

    def speak(self, text: str, **kwargs) -> None:
        self.spoken.append((text, kwargs))


def _message(utterance: str, language: str = "en-US"):
    return type(
        "Message",
        (),
        {
            "data": {"utterance": utterance},
            "context": {
                "session": {"session_id": "collection-session", "lang": language},
                "reneryo_context": {
                    "organization_id": "futuregen",
                    "language": language,
                },
            },
        },
    )()


def _response_type(skill: _Skill) -> str:
    return skill.spoken[-1][1]["meta"]["avaros_response"]["response_type"]


def test_filter_parser_inherits_collection_filters_and_accepts_turkish():
    prior = type(
        "State",
        (),
        {
            "finding_status": "ACTIVE",
            "finding_severity": "",
            "finding_domain": "REGRESSION",
        },
    )()

    filters = filters_for("sadece orta olanları göster", prior)

    assert filters == FindingFilters(status="ACTIVE", severity="MEDIUM", domain="REGRESSION")
    assert is_evaluation_request("Güncel veriyi analiz et ve dikkat gerektirenleri anlat.")


def test_ordinal_selection_is_limited_to_current_result_ids():
    state = type("State", (), {"finding_ids": ("one", "two")})()

    assert selection_index("Tell me more about number two.", state) == 1
    assert selection_index("Üçüncüyü açıkla.", state) is None


def test_selection_covers_displayed_ordinals_and_never_guesses_corrupt_speech():
    state = type("State", (), {"finding_ids": tuple(str(i) for i in range(9))})()

    assert selection_index("Show the fifth one", state) == 4
    assert selection_index("Dokuzuncusunu açıkla", state) == 8
    assert selection_index("İkinciyi açıkla", state) == 1
    assert selection_index("Birinciyi açıkla", state) == 0
    assert selection_index("Explain number 5", state) == 4
    assert selection_index("Birkinci bulbuyu açıkla", state) is None
    assert selection_requested("Birkinci bulbuyu açıkla", state)
    assert selection_index("2. bulbuyor açıkla", state) is None
    assert selection_requested("2. bulbuyor açıkla", state)
    assert selection_requested("2. olana açıkla", state)
    assert selection_index("Show the first and second", state) is None


def test_contextual_ordinal_selection_tolerates_small_en_tr_asr_variations():
    state = type("State", (), {"finding_ids": ("one", "two", "three")})()

    assert selection_index("İlki açıkla.", state) == 0
    assert selection_index("İlkin açıkla.", state) == 0
    assert selection_index("Birincisini açıkla.", state) == 0
    assert selection_index("İkincini anlat.", state) == 1
    assert selection_index("Üçüncüsünü göster.", state) == 2
    assert selection_index("Explain the firs one.", state) == 0
    assert selection_index("Tell me about the secon item.", state) == 1
    assert selection_index("Show the thrd one.", state) == 2

    # A near-match is not treated as a selector without an explicit action.
    assert selection_index("ilkin var mı", state) is None
    assert selection_index("firs finding", state) is None


def test_english_evaluation_collection_filter_selection_and_followup():
    skill = _Skill()

    assert handle_reneryo_query(
        skill, _message("Analyze the current data and tell me what needs attention.")
    )
    assert skill._futuregen_service.evaluations == 1
    assert _response_type(skill) == "evaluation"
    assert "fresh evaluation" in skill.spoken[-1][0]
    assert "Finding one" not in skill.spoken[-1][0]
    assert "Severity mix: 0 high, 1 medium, and 1 low." in skill.spoken[-1][0]
    assert "medium-priority findings cover metrics" in skill.spoken[-1][0]
    assert "List them" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("List them."))
    assert _response_type(skill) == "findings"
    assert "Finding one" in skill.spoken[-1][0]
    assert "Finding two" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Only the medium ones."))
    assert "1 active medium findings" in skill.spoken[-1][0]
    assert skill._futuregen_service.requests[-1] == FindingFilters(
        "ACTIVE", "MEDIUM", ""
    )

    assert handle_reneryo_query(skill, _message("Explain the firs one."))
    assert "about 566 hours behind" in skill.spoken[-1][0]
    assert _response_type(skill) == "finding"

    assert handle_reneryo_query(skill, _message("Why was it triggered?"))
    assert "larger of 48 hours or three observed cadences" in skill.spoken[-1][0]
    state = skill._dialogue_state_store.get("collection-session")
    assert state is not None and state.active_finding_id == "one"
    assert state.selected_finding_from_collection is True


def test_selected_finding_next_review_conversation_stays_with_mdsp_assessment():
    skill = _Skill()
    review = MdspNextReview(
        code="metric-resource-relative-freshness-review",
        version=1,
        instruction=LocalizedText(
            en="Review the recorded observations for this resource.",
            tr="Bu kaynağın kayıtlı gözlemlerini inceleyin.",
        ),
        rationale=LocalizedText(
            en="The observed lag exceeds the provisional gate.",
            tr="Gözlenen gecikme geçici sınırı aşıyor.",
        ),
        evidence_keys=("lagHours", "allowedLagHours"),
        policy_status="PROVISIONAL",
        assessment_run_id="run-1",
        review_link="/measurements/metric/values/graph/metric-1",
    )
    skill._futuregen_service.rows = (
        replace(skill._futuregen_service.rows[0], next_review=review),
        skill._futuregen_service.rows[1],
    )

    assert handle_reneryo_query(skill, _message("List the active findings."))
    assert handle_reneryo_query(skill, _message("Explain the first one."))
    for prompt, expected in (
        ("What should we do about this?", "Review the recorded observations"),
        ("Why are you recommending that?", "lagHours"),
        ("Who should handle it?", "No approved Reneryo owner"),
        ("Can you take action on it?", "cannot change records or models"),
    ):
        assert handle_reneryo_query(skill, _message(prompt))
        assert expected in skill.spoken[-1][0]
        assert _response_type(skill) == "finding"
    assert skill._futuregen_service.evaluations == 0


def test_existing_findings_read_does_not_trigger_evaluation():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("What active decision-support findings are there?"))

    assert skill._futuregen_service.evaluations == 0
    assert _response_type(skill) == "findings"


def test_selected_finding_followups_and_asr_ordinal_request():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("List active findings"))
    assert handle_reneryo_query(skill, _message("Explain the first one"))
    assert handle_reneryo_query(skill, _message("What does this finding mean?"))
    assert _response_type(skill) == "finding"
    assert handle_reneryo_query(
        skill, _message("What should we do about this finding?")
    )
    assert _response_type(skill) == "finding"
    assert handle_reneryo_query(skill, _message("Birkinci bulbuyu açıkla", "tr-TR"))
    assert _response_type(skill) == "clarification"
    assert "Hangi bulguyu" in skill.spoken[-1][0]
    assert handle_reneryo_query(skill, _message("Birkinci bulbuyu açıkla", "tr-TR"))
    assert _response_type(skill) == "clarification"
    assert handle_reneryo_query(skill, _message("İkinci bulguyu açıkla", "tr-TR"))
    assert _response_type(skill) == "finding"
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "two"
    assert skill._futuregen_service.evaluations == 0


def test_all_findings_clears_collection_filters():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("List active findings"))
    assert handle_reneryo_query(skill, _message("Only the medium ones"))
    assert skill._futuregen_service.requests[-1] == FindingFilters(
        "ACTIVE", "MEDIUM", ""
    )
    assert handle_reneryo_query(skill, _message("Show all findings"))
    assert skill._futuregen_service.requests[-1] == FindingFilters("ACTIVE", "", "")
    assert handle_reneryo_query(skill, _message("Sadece orta olanları göster", "tr-TR"))
    assert handle_reneryo_query(skill, _message("Hepsini göster", "tr-TR"))
    assert skill._futuregen_service.requests[-1] == FindingFilters("ACTIVE", "", "")


def test_negated_evaluation_lists_without_running_analysis():
    skill = _Skill()

    assert handle_reneryo_query(
        skill, _message("Do not evaluate the data; just list findings")
    )
    assert _response_type(skill) == "findings"
    assert skill._futuregen_service.evaluations == 0


def test_negated_evaluation_cannot_be_resurrected_by_semantic_fallback():
    skill = _Skill()
    resolution = SemanticResolution(
        action=SemanticAction.FINDINGS_EVALUATE,
        language="en-US",
        confidence=0.9,
        margin=0.1,
    )

    assert handle_reneryo_query(
        skill, _message("Do not evaluate the data"), semantic_resolution=resolution
    )
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("transcript", ["2. bulbuyor açıkla.", "2. olana açıkla."])
def test_unclear_asr_ordinal_clarifies_without_evaluating(transcript):
    skill = _Skill()
    assert handle_reneryo_query(skill, _message("Aktif bulguları listele", "tr-TR"))

    assert handle_reneryo_query(skill, _message(transcript, "tr-TR"))
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


def test_signed_widget_structured_entry_resolves_correct_ordinal_and_rejects_unclear_one():
    skill = _Skill()
    assert handle_reneryo_query(skill, _message("Aktif bulguları listele", "tr-TR"))
    clear = _message("İkinciyi açıkla.", "tr-TR")
    clear.context["reneryo_widget_session_validated"] = True
    assert try_handle_structured_query(skill, clear)
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "two"

    unclear = _message("2. bulbuyor açıkla.", "tr-TR")
    unclear.context["reneryo_widget_session_validated"] = True
    assert try_handle_structured_query(skill, unclear)
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize(
    ("utterance", "language", "expected_label"),
    [
        ("Show the electricity trend from May to June 2026", "en-US", "May–June 2026"),
        (
            "Mayıs ile Haziran 2026 arasında elektrik eğilimini göster",
            "tr-TR",
            "Mayıs–Haziran 2026",
        ),
    ],
)
def test_signed_widget_month_range_reaches_trend_with_both_observations(
    utterance, language, expected_label
):
    skill = _Skill()
    skill._parse_period = TimePeriod.from_natural_language
    periods = []

    async def trend(_utterance, period):
        periods.append(period)
        return ReneryoTrend(
            metric=ReneryoMetric("electricity", "Electricity", "COUNTER", "ENERGY"),
            period_label=period.display_name,
            aggregation="DAILY",
            points=(
                ReneryoTrendPoint(datetime(2026, 5, 31, tzinfo=timezone.utc), 100, 1),
                ReneryoTrendPoint(datetime(2026, 6, 30, tzinfo=timezone.utc), 124.3, 1),
            ),
            direction="increasing",
            change_percent=24.3,
        )

    skill._futuregen_service.trend = trend
    message = _message(utterance, language)
    message.context["reneryo_widget_session_validated"] = True

    assert try_handle_structured_query(skill, message)
    assert _response_type(skill) == "trend"
    assert periods[0].start == datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert periods[0].end == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert expected_label in skill.spoken[-1][0]
    assert "24.3" in skill.spoken[-1][0]


def test_correct_turkish_ordinal_and_mistranscribed_period_keep_finding():
    skill = _Skill()
    assert handle_reneryo_query(skill, _message("Aktif bulguları listele", "tr-TR"))

    assert handle_reneryo_query(skill, _message("İkinciyi açıkla.", "tr-TR"))
    assert _response_type(skill) == "finding"
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "two"
    assert handle_reneryo_query(
        skill, _message("Bu bulgur hangi dönemi katsoyor.", "tr-TR")
    )
    assert _response_type(skill) == "finding"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize(
    "transcript", ["2. bulbuyor açıkla.", "2. olana açıkla.", "İkinciye açıklar."]
)
def test_semantic_evaluation_requires_explicit_analysis_request(transcript):
    skill = _Skill()
    resolution = SemanticResolution(
        action=SemanticAction.FINDINGS_EVALUATE,
        language="tr-TR",
        confidence=0.9,
        margin=0.1,
    )

    assert handle_reneryo_query(
        skill, _message(transcript, "tr-TR"), semantic_resolution=resolution
    )
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


def test_mistranscribed_english_findings_list_cannot_jump_to_metric_inventory():
    skill = _Skill()
    resolution = SemanticResolution(
        action=SemanticAction.METRICS_LIST,
        language="en-US",
        confidence=0.9,
        margin=0.1,
    )

    assert handle_reneryo_query(
        skill,
        _message("List Actify Endings."),
        semantic_resolution=resolution,
    )
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize(
    "transcript", ["Bu bulgur hangi dönemi katsoyor.", "Kanıtları göster."]
)
def test_finding_followup_without_selection_clarifies_instead_of_switching_topic(
    transcript,
):
    skill = _Skill()
    assert handle_reneryo_query(skill, _message("Aktif bulguları listele", "tr-TR"))
    resolution = SemanticResolution(
        action=SemanticAction.METRICS_LIST,
        language="tr-TR",
        confidence=0.9,
        margin=0.1,
    )

    assert handle_reneryo_query(
        skill, _message(transcript, "tr-TR"), semantic_resolution=resolution
    )
    assert _response_type(skill) == "clarification"
    assert skill._futuregen_service.evaluations == 0


def test_turkish_missing_trend_is_explicit_after_a_finding_topic_change():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("List active findings"))
    assert handle_reneryo_query(skill, _message("Explain the first one"))
    assert handle_reneryo_query(skill, _message("Üretim eğilimini göster", "tr-TR"))

    assert _response_type(skill) == "trend"
    assert "gözlem bulunamadı" in skill.spoken[-1][0]
    assert "2026-07-31" in skill.spoken[-1][0]
    assert "%0.0" not in skill.spoken[-1][0]
    assert "sabit" not in skill.spoken[-1][0]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((), "No observations were returned"),
        ((10,), "only one observation was returned"),
        ((0, 10), "the first observed value is zero"),
    ],
)
def test_english_sparse_trend_explains_why_percent_is_unavailable(values, expected):
    skill = _Skill()

    async def sparse_trend(_utterance, period):
        return ReneryoTrend(
            metric=ReneryoMetric("electricity", "Electricity", "COUNTER", "ENERGY"),
            period_label=period.display_name,
            aggregation="DAILY",
            points=tuple(
                ReneryoTrendPoint(datetime(2026, 9, index + 1, tzinfo=timezone.utc), value, 1)
                for index, value in enumerate(values)
            ),
            direction="unavailable",
            change_percent=None,
        )

    skill._futuregen_service.trend = sparse_trend
    assert handle_reneryo_query(skill, _message("Show electricity trend"))
    assert expected in skill.spoken[-1][0]
    assert "0.0%" not in skill.spoken[-1][0]
    assert "stable" not in skill.spoken[-1][0]


def test_correction_changes_metric_after_finding_handoff():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("List active findings"))
    assert handle_reneryo_query(skill, _message("Explain the first one"))
    assert handle_reneryo_query(skill, _message("Not humidity, electricity"))

    assert _response_type(skill) == "metrics"
    assert "Tesis Toplam Elektrik Tüketimi" in skill.spoken[-1][0]


def test_turkish_evaluation_collection_selection_and_followup():
    skill = _Skill()

    assert handle_reneryo_query(
        skill, _message("Güncel veriyi analiz et ve dikkat gerektirenleri anlat.", "tr-TR")
    )
    assert skill._futuregen_service.evaluations == 1
    assert "değerlendirmeyi tamamladı" in skill.spoken[-1][0]
    assert "Bulgu one" not in skill.spoken[-1][0]
    assert "Önem düzeyi dağılımı: 0 yüksek, 1 orta ve 1 düşük." in skill.spoken[-1][0]
    assert "Orta öncelikli bulgular şu alanlarla ilgilidir: metrik." in skill.spoken[-1][0]
    assert "bunları listele" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Bunları listele.", "tr-TR"))
    assert "Bulgu one" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Sadece orta olanları göster.", "tr-TR"))
    assert "1 etkin orta bulgu" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("İlkin açıkla.", "tr-TR"))
    assert "yaklaşık 566 saat gerisinde" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Bu bulgu neden oluştu?", "tr-TR"))
    assert "48 saat ile gözlenen veri sıklığının üç katından" in skill.spoken[-1][0]
