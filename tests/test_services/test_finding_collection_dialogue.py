from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.reneryo_models import (
    LocalizedText,
    MdspEvaluation,
    MdspFinding,
    MdspFindingList,
)
from skill.services.conversation_state import DialogueStateStore
from skill.services.finding_collection import (
    FindingFilters,
    filters_for,
    is_evaluation_request,
    selection_index,
)


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


def test_english_evaluation_collection_filter_selection_and_followup():
    skill = _Skill()

    assert handle_reneryo_query(
        skill, _message("Analyze the current data and tell me what needs attention.")
    )
    assert skill._futuregen_service.evaluations == 1
    assert _response_type(skill) == "evaluation"
    assert "fresh evaluation" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("List them."))
    assert _response_type(skill) == "findings"
    assert "Finding one" in skill.spoken[-1][0]
    assert "Finding two" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Only the medium ones."))
    assert "1 active medium findings" in skill.spoken[-1][0]
    assert skill._futuregen_service.requests[-1] == FindingFilters("ACTIVE", "MEDIUM", "")

    assert handle_reneryo_query(skill, _message("Explain the first one."))
    assert "about 566 hours behind" in skill.spoken[-1][0]
    assert _response_type(skill) == "finding"

    assert handle_reneryo_query(skill, _message("Why was it triggered?"))
    assert "larger of 48 hours or three observed cadences" in skill.spoken[-1][0]
    state = skill._dialogue_state_store.get("collection-session")
    assert state is not None and state.active_finding_id == "one"
    assert state.selected_finding_from_collection is True


def test_existing_findings_read_does_not_trigger_evaluation():
    skill = _Skill()

    assert handle_reneryo_query(skill, _message("What active decision-support findings are there?"))

    assert skill._futuregen_service.evaluations == 0
    assert _response_type(skill) == "findings"


def test_turkish_evaluation_collection_selection_and_followup():
    skill = _Skill()

    assert handle_reneryo_query(
        skill, _message("Güncel veriyi analiz et ve dikkat gerektirenleri anlat.", "tr-TR")
    )
    assert skill._futuregen_service.evaluations == 1
    assert "yeni değerlendirmeyi tamamladı" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Bunları listele.", "tr-TR"))
    assert "Bulgu one" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Sadece orta olanları göster.", "tr-TR"))
    assert "1 etkin orta bulgu" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("İlkini açıkla.", "tr-TR"))
    assert "yaklaşık 566 saat gerisinde" in skill.spoken[-1][0]

    assert handle_reneryo_query(skill, _message("Bu bulgu neden oluştu?", "tr-TR"))
    assert "48 saat ile gözlenen veri sıklığının üç katından" in skill.spoken[-1][0]
