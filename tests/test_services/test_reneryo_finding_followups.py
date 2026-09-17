from datetime import datetime, timezone

from skill._reneryo_handlers import (
    _finding_headline,
    _is_finding_list,
    _query_period,
    _signed_language,
)
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import LocalizedText, MdspFinding


def _finding() -> MdspFinding:
    return MdspFinding(
        finding_id="finding-1",
        status="ACTIVE",
        severity="LOW",
        domain="METRICS",
        entity_type="METRIC_RESOURCE",
        entity_id="resource-1",
        title=LocalizedText(en="Source lag detected", tr="Kaynak gecikmesi algılandı"),
        summary=LocalizedText(en="The source trails.", tr="Kaynak geride kalıyor."),
        evidence={"lagHours": 566, "observedSampleCount": 968},
        assumptions=(),
        evaluation_start=datetime(2023, 9, 18, 10, 0, tzinfo=timezone.utc),
        evaluation_end=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        source_watermark=None,
        deep_link=None,
        provisional=True,
        metric_name="Cooling degree days - Open Weather",
    )


def test_finding_period_follow_up_uses_evaluation_window():
    answer = _finding_headline(
        _finding(), "what period does this finding cover", "en-US"
    )

    assert "2023-09-18 10:00 UTC" in answer
    assert "2026-09-17 10:00 UTC" in answer


def test_finding_entity_follow_up_uses_signed_finding_entity():
    answer = _finding_headline(
        _finding(), "which entity does this finding affect", "en-US"
    )

    assert "Cooling degree days - Open Weather" in answer
    assert "resource-1" in answer


def test_finding_evidence_follow_up_is_localized():
    answer = _finding_headline(
        _finding(), "bu bulguyu hangi kanıt destekliyor", "tr-TR"
    )

    assert answer.startswith("Bu bulgunun kanıtı:")
    assert "lagHours: 566" in answer


class _PeriodParser:
    def __init__(self):
        self.values = []

    def _parse_period(self, value):
        self.values.append(value)
        return TimePeriod.from_natural_language(value)


def test_query_period_extracts_english_phrase_from_full_request():
    skill = _PeriodParser()

    period = _query_period(
        skill, "Show the cooling degree days trend for last month", None
    )

    assert skill.values == ["last month"]
    assert period.display_name == "last month"


def test_query_period_extracts_normalized_turkish_phrase():
    skill = _PeriodParser()

    period = _query_period(
        skill, "Geçen ay için soğutma derece gün eğilimini göster", None
    )

    assert skill.values == ["geçen ay"]
    assert period.display_name == "geçen ay"


def test_signed_language_is_read_from_trusted_session_context():
    message = type("Message", (), {"context": {"session": {"lang": "tr-TR"}}})()

    assert _signed_language(message) == "tr-TR"


def test_explicit_finding_list_overrides_active_finding_context():
    assert _is_finding_list("list decision support findings")
    assert _is_finding_list("karar destek bulgularını listele")
    assert not _is_finding_list("explain this finding")
