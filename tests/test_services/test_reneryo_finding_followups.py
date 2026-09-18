from dataclasses import replace
from datetime import datetime, timezone

from skill._reneryo_handlers import (
    _conversation_language,
    _is_finding_list,
    _query_period,
    _signed_language,
    _update_message_language,
)
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import LocalizedText, MdspFinding
from skill.services.conversation_state import DialogueState
from skill.services.finding_explanation import finding_headline


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
        evidence={
            "lagHours": 566,
            "allowedLagHours": 72,
            "inferredCadenceSeconds": 86_400,
            "observedSampleCount": 968,
            "lastObservationAt": "2026-08-24T21:00:00.000Z",
            "sourceWatermark": "2026-09-17T10:38:13.000Z",
            "currentSiblingResourceId": "current-resource",
        },
        assumptions=(),
        evaluation_start=datetime(2023, 9, 18, 10, 0, tzinfo=timezone.utc),
        evaluation_end=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        source_watermark=None,
        deep_link=None,
        provisional=True,
        metric_name="Cooling degree days - Open Weather",
        rule_id="metric-resource-relative-freshness",
        rule_version=2,
    )


def _recent_gap_finding() -> MdspFinding:
    return MdspFinding(
        finding_id="gap-finding",
        status="ACTIVE",
        severity="MEDIUM",
        domain="METRICS",
        entity_type="INTEGRATION_SOURCE",
        entity_id="integration:OPEN_WEATHER",
        title=LocalizedText(
            en="Recent data gaps detected for OPEN_WEATHER",
            tr="OPEN_WEATHER için yakın tarihli veri boşlukları algılandı",
        ),
        summary=LocalizedText(
            en="5 resource(s) share recent gaps; the longest lasted 29 hours.",
            tr="5 kaynak yakın tarihli veri boşluklarını paylaşıyor; en uzunu 29 saat sürdü.",
        ),
        evidence={
            "source": "OPEN_WEATHER",
            "affectedResourceCount": 5,
            "recentGapCount": 4,
            "longestGap": {
                "start": "2026-09-06T01:53:46.000Z",
                "end": "2026-09-07T06:24:38.000Z",
                "durationSeconds": 102652,
            },
        },
        assumptions=(),
        evaluation_start=datetime(2023, 9, 18, 10, 53, tzinfo=timezone.utc),
        evaluation_end=datetime(2026, 9, 17, 10, 53, tzinfo=timezone.utc),
        source_watermark=datetime(2026, 9, 17, 10, 38, tzinfo=timezone.utc),
        deep_link=None,
        provisional=True,
        rule_id="metric-source-recent-continuity",
        rule_version=1,
    )


def _regression_cadence_finding() -> MdspFinding:
    return MdspFinding(
        finding_id="regression-cadence",
        status="ACTIVE",
        severity="MEDIUM",
        domain="REGRESSION",
        entity_type="ADVANCED_REGRESSION_RESULT",
        entity_id="regression-1",
        title=LocalizedText(
            en="Regression period is finer than its driver data",
            tr="Regresyon dönemi sürücü verisinden daha ayrıntılı",
        ),
        summary=LocalizedText(
            en="At least one driver updates too slowly.",
            tr="En az bir sürücü çok yavaş güncelleniyor.",
        ),
        evidence={
            "period": "DAILY",
            "incompatibleDrivers": [
                {
                    "id": "production-metric",
                    "name": "Tesis Toplam Üretim Miktarı",
                    "fastestCadenceSeconds": 2_678_400,
                    "regressionPeriodSeconds": 86_400,
                }
            ],
        },
        assumptions=(),
        evaluation_start=datetime(2023, 9, 18, tzinfo=timezone.utc),
        evaluation_end=datetime(2026, 9, 17, tzinfo=timezone.utc),
        source_watermark=None,
        deep_link=None,
        provisional=True,
        rule_id="regression-driver-cadence-compatibility",
        rule_version=1,
    )


def test_english_finding_explanation_is_natural():
    answer = finding_headline(
        _recent_gap_finding(), "explain this decision-support finding", "en-US"
    )

    assert "4 significant data gaps" in answer
    assert "5 OpenWeather resources" in answer
    assert "29 hours" in answer
    assert "resource(s)" not in answer
    assert "OPEN_WEATHER" not in answer


def test_turkish_finding_explanation_is_natural():
    answer = finding_headline(_recent_gap_finding(), "bu bulguyu açıkla", "tr-TR")

    assert "4 önemli veri boşluğu" in answer
    assert "5 OpenWeather kaynağını" in answer
    assert "29 saat" in answer
    assert "resource(s)" not in answer
    assert "OPEN_WEATHER" not in answer


def test_recent_gap_period_uses_rule_lookback_and_actual_gap_interval():
    answer = finding_headline(
        _recent_gap_finding(), "what period does this finding cover", "en-US"
    )

    assert "most recent 30-day lookback window" in answer
    assert "2026-09-06 01:53 UTC" in answer
    assert "2026-09-07 06:24 UTC" in answer
    assert "29 hours" in answer
    assert "2023-09-18" not in answer


def test_finding_entity_follow_up_uses_signed_finding_entity():
    answer = finding_headline(
        _finding(), "which entity does this finding affect", "en-US"
    )

    assert "Cooling degree days - Open Weather" in answer
    assert "resource-1" in answer


def test_finding_evidence_follow_up_is_localized():
    answer = finding_headline(
        _recent_gap_finding(), "bu bulguyu hangi kanıt destekliyor", "tr-TR"
    )

    assert "5 OpenWeather kaynağında" in answer
    assert "4 yakın tarihli önemli boşluk" in answer
    assert "2026-09-06 01:53 UTC" in answer
    assert "29 saat" in answer
    assert "affectedResourceCount" not in answer
    assert "recentGapCount" not in answer


def test_english_evidence_is_humanized_without_raw_keys():
    answer = finding_headline(
        _recent_gap_finding(), "what evidence supports this finding", "en-US"
    )

    assert "4 recent significant gaps across 5 OpenWeather resources" in answer
    assert "2026-09-06 01:53 UTC" in answer
    assert "29 hours" in answer
    assert "affectedResourceCount" not in answer
    assert "recentGapCount" not in answer


def test_regression_explain_and_trigger_have_distinct_meaning():
    finding = _regression_cadence_finding()

    explanation = finding_headline(
        finding, "Explain this decision-support finding", "en-US"
    )
    trigger = finding_headline(finding, "Why did this finding trigger?", "en-US")

    assert "model period is finer than its supporting data" in explanation
    assert "slower than 1.5 times the model period" in trigger
    assert "limit is 1.5 days" in trigger
    assert explanation != trigger


def test_source_lag_explain_and_trigger_have_distinct_meaning():
    finding = _finding()

    explanation = finding_headline(finding, "Explain this finding", "en-US")
    trigger = finding_headline(finding, "Why did this finding trigger?", "en-US")

    assert "about 566 hours behind" in explanation
    assert "larger of 48 hours or three observed cadences" in trigger
    assert "allowed lag was 72 hours" in trigger
    assert "severity is low" in trigger
    assert explanation != trigger


def test_regression_trigger_is_natural_in_turkish():
    answer = finding_headline(
        _regression_cadence_finding(), "Bu bulgu neden oluştu?", "tr-TR"
    )

    assert "model döneminin 1,5 katından" in answer
    assert "yaklaşık 31 günde bir" in answer
    assert "izin verilen sınır 1,5 gündür" in answer


def test_regression_entity_follow_up_retains_active_result_context():
    answer = finding_headline(
        _regression_cadence_finding(),
        "Which entity does this finding affect?",
        "en-US",
    )

    assert "daily advanced-regression result regression-1" in answer
    assert "Tesis Toplam Üretim Miktarı" in answer


def _message(language: str):
    return type(
        "Message",
        (),
        {
            "context": {
                "reneryo_context": {"language": language},
                "session": {"lang": language, "session_id": "same-session"},
            }
        },
    )()


def test_english_to_turkish_switch_updates_same_session_context():
    state = DialogueState(language="en-US")
    message = _message("en-US")

    language = _conversation_language("Bu bulgu neden oluştu?", state, message, "en-US")
    _update_message_language(message, language)
    state = replace(state, language=language)

    assert state.language == "tr-TR"
    assert message.context["reneryo_context"]["language"] == "tr-TR"
    assert message.context["session"]["lang"] == "tr-TR"
    assert "tetiklenir" in finding_headline(
        _recent_gap_finding(), "Bu bulgu neden oluştu?", language
    )


def test_turkish_to_english_switch_updates_same_session_context():
    state = DialogueState(language="tr-TR")
    message = _message("tr-TR")

    language = _conversation_language(
        "What evidence supports this finding?", state, message, "tr-TR"
    )
    _update_message_language(message, language)
    state = replace(state, language=language)

    assert state.language == "en-US"
    assert message.context["reneryo_context"]["language"] == "en-US"
    assert message.context["session"]["lang"] == "en-US"
    assert "recent significant gaps" in finding_headline(
        _recent_gap_finding(), "What evidence supports this finding?", language
    )


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


def test_signed_language_prefers_reneryo_context_forwarded_by_proxy():
    message = type(
        "Message",
        (),
        {
            "context": {
                "reneryo_context": {"language": "tr-TR"},
                "session": {"lang": "en-US"},
            }
        },
    )()

    assert _signed_language(message) == "tr-TR"


def test_explicit_finding_list_overrides_active_finding_context():
    assert _is_finding_list("list decision support findings")
    assert _is_finding_list("karar destek bulgularını listele")
    assert not _is_finding_list("explain this finding")
