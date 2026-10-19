"""PR #71: retain legacy energy contracts and scoped simulation dispatch."""

from copy import deepcopy
from types import MethodType
from unittest.mock import AsyncMock, Mock

import pytest

from skill import AVAROSSkill
from skill._handlers import handle_metric_query_fallback
from skill.adapters.generic_rest import GenericRestAdapter
from skill.domain.models import CanonicalMetric
from skill.services.dia_dialogue import try_handle_structured_query
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.test_adapters.test_generic_rest import _StubSettingsService
from tests.test_services.test_comparison_followups import comparison_skill
from tests.test_services.test_explicit_query_scope import widget_message


def make_skill(language, kind="item"):
    skill = comparison_skill(language)
    skill._response_language = language
    skill._resolve_asset_name_for_voice = lambda asset_id: asset_id
    skill.log = Mock()
    skill._ensure_runtime_services = lambda: None
    skill._check_profile_mismatch = lambda: None
    for name in ("_safe_dispatch", "_sync_response_language", "_is_whatif_query",
                 "_resolve_metric_from_utterance", "handle_whatif_scenario",
                 "_resolve_asset_id", "_canonicalize_asset_id",
                 "_extract_line_assets_from_text"):
        setattr(skill, name, MethodType(getattr(AVAROSSkill, name), skill))
    asset = {"display_name": "Line 1", "metric_resources": {"energy_total": "synthetic-id"}}
    endpoint = "/api/u/measurement/metric/item/{resource_id}"
    if kind == "aggregate":
        asset.update(capability_mode="energy_only", native_metric_bindings={
            "energy_total": {"strategy": "asset_consumption_total",
                             "default_period_mode": "aggregate_total",
                             "aggregate_start_iso": "2021-02-01T00:00:00Z"},
        })
    elif kind == "series":
        endpoint = "/series/{resource_id}?from={start_date}&to={end_date}"
    elif kind == "native_item":
        asset["native_metric_bindings"] = {"energy_total": {
            "strategy": "metric_item_last_value", "resource_id": "synthetic-id",
        }}
    settings = _StubSettingsService({"energy_total": {
        "endpoint": endpoint, "json_path": "$.lastValue", "unit": "kWh",
    }}, {"Line-1": asset})
    from types import SimpleNamespace
    settings.get_profile = lambda _: SimpleNamespace(extra_settings={"organization_timezones": {"futuregen": "UTC"}})
    skill.settings_service = settings
    adapter = GenericRestAdapter("https://synthetic.invalid", "synthetic-token",
                                 settings_service=settings)
    # Stub only HTTP/session I/O; request building, native bindings and parsing
    # remain real. No external endpoint is contacted by these tests.
    adapter._ensure_read_session = AsyncMock()
    adapter._fetch_complete_mapped_payload = AsyncMock(return_value={"lastValue": 123456})
    adapter._retry_fetch = AsyncMock(return_value={"lastValue": 123456, "records": [
        {"id": "Line-1", "name": "Line 1", "consumption": 42},
    ]})
    skill.dispatcher = QueryDispatcher(adapter=adapter, settings_service=settings)
    skill.dispatcher.get_kpi = Mock(wraps=skill.dispatcher.get_kpi)
    return skill, adapter


def send(skill, text, language, entry="fallback"):
    message = widget_message(text, language)
    before = deepcopy((message.data, message.context))
    skill._sync_response_language(message)
    if entry == "registered":
        AVAROSSkill._guard_intent_activation(
            skill, "kpi.energy.total", Mock(side_effect=AssertionError("unexpected handoff")),
        )(message)
    elif entry == "structured":
        assert try_handle_structured_query(skill, message, include_simple_kpi=True)
    else:
        assert handle_metric_query_fallback(skill, message)
    assert (message.data, message.context) == before
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["language"] == language
    return response


@pytest.mark.parametrize("language,text", [
    ("en-US", "Show total energy for Line 1 today"),
    ("tr-TR", "Hat 1 toplam enerji değerini bugün göster"),
])
@pytest.mark.parametrize("kind", ["item", "aggregate", "native_item"])
@pytest.mark.parametrize("entry", ["fallback", "registered", "structured"])
def test_cumulative_mapping_never_becomes_period_consumption(language, text, kind, entry):
    skill, adapter = make_skill(language, kind)
    response = send(skill, text, language, entry)
    assert response["response_type"] == "unavailable"
    assert not response["evidence_rows"]
    assert "123456" not in response["headline"]
    adapter._fetch_complete_mapped_payload.assert_not_awaited()
    adapter._retry_fetch.assert_not_awaited()
    assert len(skill.spoken) == 1


@pytest.mark.parametrize("language,text", [
    ("en-US", "Show total energy for Line 1"),
    ("tr-TR", "Hat 1 toplam enerji değerini göster"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_implicit_aggregate_uses_established_start_not_latest_window(language, text, entry):
    skill, adapter = make_skill(language, "aggregate")
    response = send(skill, text, language, entry)
    assert response["response_type"] == "kpi"
    period = skill.dispatcher.get_kpi.call_args.kwargs["period"]
    assert period.display_name == "in total" and period.start.year == 2021
    assert adapter._retry_fetch.call_args.args[1]["datetimeMin"].startswith("2021-02-01")
    assert skill._dialogue_state_store.get("collection-session").period == period


@pytest.mark.parametrize("language,text,followup", [
    ("en-US", "Show total energy for Line 1", "And yesterday?"),
    ("tr-TR", "Hat 1 toplam enerji değerini göster", "Peki dün?"),
])
def test_cumulative_latest_is_supported_but_period_followup_does_not_read(language, text, followup):
    skill, adapter = make_skill(language)
    assert send(skill, text, language)["response_type"] == "kpi"
    assert skill.dispatcher.get_kpi.call_args.kwargs["period"].display_name == "latest available"
    adapter._fetch_complete_mapped_payload.reset_mock()
    assert send(skill, followup, language)["response_type"] == "unavailable"
    adapter._fetch_complete_mapped_payload.assert_not_awaited()


@pytest.mark.parametrize("language,text", [
    ("en-US", "Show total energy for Line 1 in June 2020"),
    ("tr-TR", "Haziran 2020 Hat 1 toplam enerji değerini göster"),
])
def test_period_capable_generic_mapping_keeps_exact_dates(language, text):
    skill, adapter = make_skill(language, "series")
    assert send(skill, text, language)["response_type"] == "kpi"
    request = adapter._fetch_complete_mapped_payload.call_args.kwargs
    assert request["params"]["from"].startswith("2020-06-01")
    assert request["params"]["to"].startswith("2020-07-01")


@pytest.mark.parametrize("language,text", [
    ("en-US", "What if OEE reaches 90 percent for Line 2"),
    ("tr-TR", "Hat 2 OEE senaryosunu simüle et"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_scoped_whatif_reaches_existing_parser_and_simulator(language, text, entry):
    skill, _ = make_skill(language)
    from tests.helpers.stub_adapter import StubAdapter
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.dispatcher.simulate_whatif = Mock(wraps=skill.dispatcher.simulate_whatif)
    message = widget_message(text, language)
    before = deepcopy((message.data, message.context))
    skill._sync_response_language(message)
    if entry == "registered":
        AVAROSSkill._guard_intent_activation(
            skill, "whatif.scenario", skill.handle_whatif_scenario,
        )(message)
    else:
        assert handle_metric_query_fallback(skill, message)
    scenario = skill.dispatcher.simulate_whatif.call_args.args[0]
    assert scenario.asset_id == "Line-2" and scenario.target_metric is CanonicalMetric.OEE
    assert scenario.parameters[0].name == ("target_value" if language == "en-US" else "assumed_kpi_change_percent")
    assert scenario.parameters[0].proposed_value == (90 if language == "en-US" else 5)
    assert len(skill.spoken) == 1
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "what_if" and response["language"] == language
    assert (message.data, message.context) == before
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize("language,text", [
    ("en-US", "What if OEE reaches 90 percent for Line 99"),
    ("tr-TR", "Hat 99 OEE senaryosunu simüle et"),
])
def test_unknown_scope_cannot_enter_simulator(language, text):
    skill, _ = make_skill(language)
    skill.dispatcher.simulate_whatif = Mock()
    assert send(skill, text, language)["response_type"] == "clarification"
    skill.dispatcher.simulate_whatif.assert_not_called()


def test_handoff_keeps_physical_target_validation():
    skill, _ = make_skill("en-US")
    skill.dispatcher.simulate_whatif = Mock()
    response = send(skill, "What if OEE reaches 190 percent for Line 2", "en-US")
    assert response["response_type"] == "error"
    assert "outside the valid range" in response["headline"]
    skill.dispatcher.simulate_whatif.assert_not_called()
