"""Synthetic acceptance contracts for request-scoped timestamp presentation.

These assert rendering and source preservation, not real microphone/TTS quality.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from skill._helpers import request_timezone
from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.domain.results import KPIResult
from skill.services.dia_response import speak_with_evidence
from skill.services.factory_questions import FactoryRequest, answer_factory_question
from skill.services.futuregen import FutureGenService
from skill.services.language import format_observation_time, speech_text
from skill.services.response_builder import ResponseBuilder, TurkishResponseBuilder
from tests.test_services.test_finding_collection_dialogue import _message, _Skill

UTC = timezone.utc
OBSERVED = datetime(2026, 12, 31, 22, 30, tzinfo=UTC)


@pytest.mark.parametrize("language,expected", [
    ("en-US", "01 January 2027 01:30 (Europe/Istanbul, UTC+03:00)"),
    ("tr-TR", "01.01.2027 01:30 (Europe/Istanbul, UTC+03:00)"),
])
def test_verified_zone_changes_presentation_across_year_boundary(language, expected):
    assert format_observation_time(OBSERVED, language, "Europe/Istanbul") == expected
    assert OBSERVED.isoformat() == "2026-12-31T22:30:00+00:00"
    spoken = speech_text(expected, language)
    assert "01:30" in spoken and "UTC" in spoken
    assert ("1 Ocak 2027" in spoken and "İstanbul saati" in spoken) if language == "tr-TR" else "Istanbul time" in spoken
    assert "3 saat" in spoken if language == "tr-TR" else "3 hours" in spoken


@pytest.mark.parametrize("instant,expected", [
    ("2026-10-25T00:30:00+00:00", "25 October 2026 02:30 (Europe/Berlin, UTC+02:00)"),
    ("2026-10-25T01:30:00+00:00", "25 October 2026 02:30 (Europe/Berlin, UTC+01:00)"),
    ("2026-03-29T00:30:00+00:00", "29 March 2026 01:30 (Europe/Berlin, UTC+01:00)"),
    ("2026-03-29T01:30:00+00:00", "29 March 2026 03:30 (Europe/Berlin, UTC+02:00)"),
])
def test_dst_repeated_hour_stays_distinguishable(instant, expected):
    rendered = format_observation_time(datetime.fromisoformat(instant), "en-US", "Europe/Berlin")
    assert rendered == expected
    assert "UTC plus" in speech_text(rendered, "en-US")


def test_fractional_offset_is_audible():
    rendered = format_observation_time(OBSERVED, "tr-TR", "Asia/Kathmandu")
    assert "UTC+05:45" in rendered
    assert "UTC artı 5 saat 45 dakika" in speech_text(rendered, "tr-TR")


@pytest.mark.parametrize("binding", [None, "", "Invalid/Zone", "../Europe/Istanbul"])
def test_missing_or_invalid_binding_retains_explicit_utc(binding):
    source = OBSERVED.astimezone(timezone(timedelta(hours=-5)))
    assert format_observation_time(source, "en-US", binding) == "31 December 2026 22:30 UTC"


def test_naive_time_never_acquires_an_invented_instant():
    assert format_observation_time(OBSERVED.replace(tzinfo=None), "tr-TR", "Europe/Istanbul") == "31.12.2026 22:30"


def configured_skill(bindings):
    skill = _Skill()
    skill.settings_service = SimpleNamespace(get_profile=lambda _: SimpleNamespace(
        extra_settings={"site_timezone": "Europe/London", "organization_timezones": bindings},
    ))
    return skill


@pytest.mark.parametrize("language,question", [
    ("en-US", "When was the last electricity reading recorded?"),
    ("tr-TR", "Son elektrik değeri ne zaman kaydedildi?"),
])
@pytest.mark.parametrize("binding", ["Europe/Istanbul", "Invalid/Zone", None])
def test_signed_freshness_preserves_utc_evidence_and_ignores_client_zone(language, question, binding):
    skill = configured_skill({"futuregen": binding})
    metric = ReneryoMetric("energy", "Tesis Toplam Elektrik Tüketimi", "COUNTER", "ENERGY", 9000, OBSERVED)
    source = SimpleNamespace(list_metrics=AsyncMock(return_value=[metric]))
    skill._futuregen_service = FutureGenService(source)
    message = _message(question, language)
    message.context["timezone"] = "America/New_York"
    message.context["reneryo_context"]["timezone"] = "America/New_York"
    assert handle_reneryo_query(skill, message)
    spoken, kwargs = skill.spoken[-1]
    response = kwargs["meta"]["avaros_response"]
    assert len(skill.spoken) == 1 and response["response_type"] == "information"
    assert response["evidence_rows"][0]["recorded_at"] == OBSERVED.isoformat()
    assert response["evidence_rows"][0]["value"] == 9000
    assert "America/New_York" not in response["headline"]
    if binding == "Europe/Istanbul":
        assert "01:30" in spoken and "01:30" in response["headline"]
        assert "Europe/Istanbul" in response["headline"]
    else:
        assert "22:30 UTC" in spoken and "22:30 UTC" in response["headline"]


@pytest.mark.parametrize("language,question", [
    ("en-US", "List all metrics"), ("tr-TR", "Tüm metrikleri listele"),
    ("en-US", "What is the current humidity value?"), ("tr-TR", "En son nem değeri nedir?"),
    ("en-US", "Show humidity trend in January 2025"), ("tr-TR", "Ocak 2025 nem eğilimini göster"),
])
def test_inventory_value_and_empty_trend_use_same_zone(language, question):
    skill = configured_skill({"futuregen": "Europe/Istanbul"})
    metric = ReneryoMetric("humidity", "Humidity - Open Weather", "GAUGE", "RATE", .94, OBSERVED)
    source = SimpleNamespace(list_metrics=AsyncMock(return_value=[metric]), metric_values=AsyncMock(return_value=[]))
    skill._futuregen_service = FutureGenService(source)
    assert handle_reneryo_query(skill, _message(question, language))
    spoken, kwargs = skill.spoken[-1]
    response = kwargs["meta"]["avaros_response"]
    assert "01:30" in response["headline"] and "Europe/Istanbul" in response["headline"]
    assert "01:30" in spoken and "UTC" in spoken
    if source.metric_values.called:
        args = source.metric_values.call_args.args
        assert args[:3] == ("humidity", datetime(2024, 12, 31, 21, tzinfo=UTC), datetime(2025, 1, 31, 21, tzinfo=UTC))


@pytest.mark.asyncio
@pytest.mark.parametrize("language,question", [
    ("en-US", "Show humidity history yesterday"), ("tr-TR", "Dünkü nem geçmişini göster"),
])
async def test_hourly_history_preserves_source_instants_and_requested_bounds(language, question):
    metric = ReneryoMetric("humidity", "Humidity - Open Weather", "GAUGE", "RATE", .94, OBSERVED)
    source = SimpleNamespace(list_metrics=AsyncMock(return_value=[metric]), metric_values=AsyncMock(return_value=[ReneryoTrendPoint(OBSERVED, .94, 2)]))
    period = TimePeriod.yesterday(now=datetime(2027, 1, 2, 0, tzinfo=UTC), timezone_name="Europe/Istanbul")
    answer = await answer_factory_question(
        FutureGenService(source), FactoryRequest("history", "humidity", question),
        period, language, timezone_name="Europe/Istanbul",
    )
    assert "01:30" in answer.headline and "Europe/Istanbul" in answer.headline
    assert answer.evidence[0]["time"] == OBSERVED.isoformat()
    assert source.metric_values.call_args.args[1:3] == (
        datetime(2026, 12, 31, 21, tzinfo=UTC), datetime(2027, 1, 1, 21, tzinfo=UTC),
    )


@pytest.mark.parametrize("language,question", [
    ("en-US", "What evidence supports this finding?"), ("tr-TR", "Bu bulgunun kanıtlarını açıkla"),
    ("en-US", "What period does this finding cover?"), ("tr-TR", "Bu bulgu hangi dönemi kapsıyor?"),
])
def test_mdsp_observation_narration_localizes_without_mutating_evidence(language, question):
    skill = configured_skill({"futuregen": "Europe/Istanbul"})
    finding = skill._futuregen_service.rows[0]
    finding = replace(finding, evidence={**finding.evidence, "lastObservationAt": OBSERVED.isoformat()})
    skill._futuregen_service.rows = (finding,)
    before = deepcopy(finding.evidence)
    message = _message(question, language)
    message.context["reneryo_context"]["finding_id"] = finding.finding_id
    assert handle_reneryo_query(skill, message)
    spoken, kwargs = skill.spoken[-1]
    response = kwargs["meta"]["avaros_response"]
    assert "01:30" in spoken and "Europe/Istanbul" in response["headline"]
    assert response["evidence_rows"][0]["lastObservationAt"] == OBSERVED.isoformat()
    assert finding.evidence == before and skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("language,builder", [("en-US", ResponseBuilder), ("tr-TR", TurkishResponseBuilder)])
def test_canonical_latest_kpi_keeps_source_metadata(language, builder):
    result = KPIResult(metric=CanonicalMetric.OEE, value=82, unit="%", asset_id="Line-2", period=TimePeriod.latest(), timestamp=OBSERVED, source_observed_at=OBSERVED)
    skill = Mock(_response_language=language)
    text = builder().format_kpi_result(result, timezone_name="Europe/Istanbul")
    speak_with_evidence(skill, text, result)
    response = skill.speak.call_args.kwargs["meta"]["avaros_response"]
    assert "01:30" in response["headline"] and "01:30" in response["speech_text"]
    assert response["source_times"]["observed_at"] == OBSERVED.isoformat()
    assert response["evidence_rows"][0]["observation_time"] == OBSERVED.isoformat()
    assert result.source_observed_at is OBSERVED


def test_organizations_and_turns_do_not_reuse_another_timezone():
    skill = configured_skill({"futuregen": "Europe/Istanbul", "other": "America/New_York"})
    message = _message("When was this recorded?")
    assert request_timezone(skill, message) == "Europe/Istanbul"
    message.context["reneryo_context"]["organization_id"] = "other"
    assert request_timezone(skill, message) == "America/New_York"
    message.context["reneryo_context"]["organization_id"] = "unconfigured"
    assert request_timezone(skill, message) is None
