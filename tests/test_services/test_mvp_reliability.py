"""One terminal response, truthful unavailable data and safe chat boundaries."""

from copy import deepcopy
from types import MethodType
from unittest.mock import AsyncMock, Mock

import pytest

from skill import AVAROSSkill
from skill._handlers import handle_metric_query_fallback
from skill._reneryo_handlers import try_arbitrate_legacy_intent
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.request_boundary import read_only_request_kind
from tests.test_services.test_comparison_followups import comparison_skill, route
from tests.test_services.test_explicit_query_scope import setup_skill, widget_message
from tests.test_services.test_finding_collection_dialogue import _Service


def safe_skill():
    skill = setup_skill()
    skill.log = Mock()
    skill._ensure_runtime_services = lambda: None
    skill._check_profile_mismatch = lambda: None
    skill.response_builder = Mock()
    skill._safe_dispatch = MethodType(AVAROSSkill._safe_dispatch, skill)
    return skill


@pytest.mark.parametrize("language,text", [
    ("en-US", "List active findings"), ("tr-TR", "Aktif bulguları listele"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_mdsp_failure_is_terminal_and_next_turn_recovers(language, text, entry):
    skill = safe_skill()
    skill._response_language = language
    skill._futuregen_service = _Service()
    service = skill._futuregen_service
    original = service.filtered_findings
    service.filtered_findings = AsyncMock(side_effect=AdapterError(
        message="503", code="MDSP_REQUEST_FAILED",
        user_message="Decision-support findings are temporarily unavailable.",
    ))
    message = widget_message(text, language)
    before = deepcopy((message.data, message.context))
    assert (handle_metric_query_fallback(skill, message) if entry == "fallback"
            else try_arbitrate_legacy_intent(skill, message, "help"))
    assert len(skill.spoken) == 1
    metadata = skill.spoken[0][1]["meta"]["avaros_response"]
    assert metadata["response_type"] == "error" and metadata["language"] == language
    assert not metadata["evidence_rows"]
    service.filtered_findings.assert_awaited_once()
    assert (message.data, message.context) == before
    service.filtered_findings = original
    assert handle_metric_query_fallback(skill, widget_message(text, language))
    assert len(skill.spoken) == 2
    assert skill.spoken[-1][1]["meta"]["avaros_response"]["response_type"] == "findings"


BOUNDARIES = [
    ("Change the OEE threshold to 80 percent", "en-US", "settings"),
    ("Set the OEE target to 85 percent", "en-US", "settings"),
    ("Change the language to Turkish", "en-US", "settings"),
    ("Disable alerts", "en-US", "settings"),
    ("Open settings", "en-US", "settings"),
    ("OEE eşiğini yüzde 80 olarak değiştir", "tr-TR", "settings"),
    ("OEE hedefini yüzde 85 olarak ayarla", "tr-TR", "settings"),
    ("Dili Türkçe olarak değiştir", "tr-TR", "settings"),
    ("Uyarıları kapat", "tr-TR", "settings"),
    ("Turn off Line 1", "en-US", "control"),
    ("Stop production", "en-US", "control"),
    ("Please start Line 1", "en-US", "control"),
    ("Hat 1'i kapat", "tr-TR", "control"),
    ("Hat 1'i durdur", "tr-TR", "control"),
    ("Hat 1'i calistir", "tr-TR", "control"),
]


@pytest.mark.parametrize("text,language,kind", BOUNDARIES)
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_commands_stop_before_data_lookup_preserving_input_and_state(text, language, kind, entry):
    skill = safe_skill()
    skill._response_language = language
    skill._semantic_resolver.resolve.side_effect = AssertionError("must not resolve")
    skill._get_asset_registry = Mock(side_effect=AssertionError("must not read"))
    skill._futuregen_service.metrics = AsyncMock(side_effect=AssertionError("must not read"))
    skill._futuregen_service.evaluate = AsyncMock(side_effect=AssertionError("must not evaluate"))
    message = widget_message(text, language)
    before = deepcopy((message.data, message.context))
    assert read_only_request_kind(text) == kind
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        # Exercise the real activation/arbitration wrapper, regardless of what
        # registered data intent OVOS incorrectly selected for the command.
        skill._sync_response_language = lambda _message: None
        skill.settings_service = None
        handler = Mock(side_effect=AssertionError("must not dispatch data"))
        AVAROSSkill._guard_intent_activation(skill, "kpi.oee", handler)(message)
        handler.assert_not_called()
    assert len(skill.spoken) == 1
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "read_only_boundary"
    assert response["language"] == language and not response["evidence_rows"]
    assert (message.data, message.context) == before
    skill._futuregen_service.evaluate.assert_not_called()


@pytest.mark.parametrize("text", [
    "What is the OEE target for Line 1?", "Show OEE threshold for Line 1",
    "How has production changed?", "Show the start time for Line 1",
    "Start time for production", "Stop date for production",
    "Run evaluation", "Evaluate the factory data", "Start an evaluation",
    "Verileri değerlendir", "Fabrika verilerinde neleri kontrol etmeliyim?",
    "What should I check now?", "Dün Hat 1 OEE değerini göster",
    "Hat 1 OEE hedefi nedir?", "OEE hedefini nasıl hesaplıyorsun?",
    "Compare OEE for Line 1 and Line 2", "What if production increases?",
])
def test_data_review_evaluation_and_simulation_are_not_control_commands(text):
    assert not read_only_request_kind(text)


@pytest.mark.parametrize("language,text,followup", [
    ("en-US", "Show OEE for Line 1 yesterday", "And today?"),
    ("tr-TR", "Dün Hat 1 OEE değerini göster", "Peki bugün?"),
])
@pytest.mark.parametrize("code", ["GENERIC_REST_CONNECTION_FAILED", "GENERIC_REST_TIMEOUT", "GENERIC_REST_SERVER_ERROR", "GENERIC_REST_NO_DATA"])
def test_failed_scoped_kpi_retains_frame_for_period_recovery(language, text, followup, code):
    skill = comparison_skill(language)
    original = skill.dispatcher.get_kpi
    skill.dispatcher.get_kpi = Mock(side_effect=AdapterError(message="down", code=code))
    response = route(skill, text, language)
    assert len(skill.spoken) == 1
    assert response["response_type"] == "unavailable" and not response["evidence_rows"]
    state = skill._dialogue_state_store.get("collection-session")
    assert state.metrics == (CanonicalMetric.OEE,) and state.asset_ids == ("Line-1",)
    assert state.period.start == TimePeriod.from_natural_language("yesterday").start
    skill.dispatcher.get_kpi = Mock(wraps=original)
    assert route(skill, followup, language)["response_type"] == "kpi"
    assert skill.dispatcher.get_kpi.call_args.kwargs["asset_id"] == "Line-1"
    assert skill.dispatcher.get_kpi.call_args.kwargs["metric"] is CanonicalMetric.OEE
    assert skill.dispatcher.get_kpi.call_args.kwargs["period"].start == TimePeriod.today().start


@pytest.mark.parametrize("language,text", [
    ("en-US", "Evaluate the factory data"),
    ("tr-TR", "Verileri değerlendir"),
])
def test_evaluation_is_not_repeated_when_following_findings_read_fails(language, text):
    skill = safe_skill()
    skill._response_language = language
    service = _Service()
    skill._futuregen_service = service
    service.evaluate = AsyncMock(wraps=service.evaluate)
    service.filtered_findings = AsyncMock(side_effect=AdapterError(
        message="503", code="MDSP_REQUEST_FAILED",
        user_message="Decision-support findings are temporarily unavailable.",
    ))
    assert handle_metric_query_fallback(skill, widget_message(text, language))
    assert len(skill.spoken) == 1
    service.evaluate.assert_awaited_once_with("futuregen")
    service.filtered_findings.assert_awaited_once()
