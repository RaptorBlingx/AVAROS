"""Scope validation across FutureGen fallback, direct and registered routes."""

from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from skill._handlers import handle_metric_query_fallback
from skill import AVAROSSkill
from skill._helpers import extract_utterance_text, sync_response_language
from skill._reneryo_handlers import handle_reneryo_query, try_arbitrate_legacy_intent
from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.domain.exceptions import AdapterError
from skill.services.conversation_state import DialogueState
from skill.services.dia_dialogue import try_handle_structured_query
from skill.services.response_builder import create_response_builder
from skill.services.semantic_resolver import SemanticAction, SemanticResolution
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.helpers.stub_adapter import StubAdapter
from tests.test_services.test_factory_predeployment import harness
from tests.test_services.test_factory_questions import Source
from tests.test_services.test_finding_collection_dialogue import _message


UNSUPPORTED = [
    ("Compare energy consumption of boiler 1 vs boiler 2 yesterday", "en-US"),
    ("Compare electricity consumption between boiler 1 and boiler 2 yesterday", "en-US"),
    ("Which uses more energy, boiler 1 versus boiler 2 yesterday?", "en-US"),
    ("Which is more efficient, boiler 1 or boiler 2 today?", "en-US"),
    ("Show compressor train energy consumption yesterday", "en-US"),
    ("Show electricity trend for boiler 1", "en-US"),
    ("Show humidity trend for Alpha", "en-US"),
    ("Show electricity consumption for unconfigured inverter X", "en-US"),
    ("Dün kazan 1 ile kazan 2 elektrik tüketimini karşılaştır", "tr-TR"),
    ("Kazan 1 ve kazan 2 enerji tüketimini kıyasla", "tr-TR"),
    ("Dun kazan 1 ile kazan 2 enerji tuketimini karsilastir", "tr-TR"),
    ("Kompressör hattının elektrik tüketimini göster", "tr-TR"),
    ("Alpha'nın elektrik tüketimini göster", "tr-TR"),
    ("Kazan 1 elektrik eğilimini göster", "tr-TR"),
    ("Compare OEE for Line 1, Line 2 and Alpha", "en-US"),
    ("Compare OEE Line 1 vs Line 2 vs Alpha", "en-US"),
    ("Hat 1, Hat 2 ve Alpha OEE değerlerini karşılaştır", "tr-TR"),
    ("Can you compare OEE for Line 1, Line 2 and Alpha?", "en-US"),
    ("Compare OEE for Line 1, Line 2 and 99", "en-US"),
    ("Show boiler99 electricity consumption", "en-US"),
    ("Show electricity consumption for meter Alpha", "en-US"),
    ("compare energy", "en-US"),
    ("Enerji tüketimini karşılaştır", "tr-TR"),
    ("Show boiler 1 pressure", "en-US"),
    ("Kazan 1 basıncını göster", "tr-TR"),
    ("Show OEE for Line-1-auxiliary", "en-US"),
]
ASSETS = [
    Asset("Line-1", "Line 1", "line", aliases=["Hat 1"]),
    Asset("Line-2", "Line 2", "line", aliases=["Hat 2"]),
    Asset("Line-10", "Line 10", "line", aliases=["Hat 10"]),
]


def setup_skill(source=None):
    skill = harness(source)
    skill._get_asset_registry = lambda: ASSETS
    skill._semantic_resolver = Mock()
    # Even a confident single-metric semantic result cannot erase scope.
    skill._semantic_resolver.resolve.return_value = SemanticResolution(
        SemanticAction.METRIC_DETAIL, "en-US", .99, .1,
        slots={"metric_name": "Tesis Toplam Elektrik Tüketimi"},
    )
    return skill


def widget_message(text, language):
    message = _message(text, language)
    message.context["source"] = "avaros-widget"
    message.context["reneryo_widget_session_validated"] = True
    message.data["__intent__"] = {"confidence": .99}
    return message


@pytest.mark.parametrize("text,language", UNSUPPORTED)
@pytest.mark.parametrize("entry", ["fallback", "direct", "registered"])
def test_unknown_scope_never_becomes_factory_data(text, language, entry):
    source = Source()
    skill = setup_skill(source)
    message = widget_message(text, language)
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    elif entry == "direct":
        assert handle_reneryo_query(skill, message)
    else:
        assert try_arbitrate_legacy_intent(skill, message, "compare.energy")
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "clarification"
    assert response["language"] == language
    assert not response["evidence_rows"]
    assert not source.calls
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize("text,language", [
    ("And boiler 99 electricity yesterday?", "en-US"),
    ("Peki kazan 99 elektrik tüketimi?", "tr-TR"),
    ("Compare OEE for Line 1, Line 2 and boiler 99", "en-US"),
    ("Hat 1, Hat 2 ve kazan 99 OEE değerlerini karşılaştır", "tr-TR"),
    ("Compare them and Alpha", "en-US"),
])
def test_explicit_unknown_entity_cannot_reuse_known_or_prior_assets(text, language):
    skill = setup_skill()
    skill._dialogue_state_store.put("collection-session", DialogueState(
        operation="kpi", metric_name="Tesis Toplam Elektrik Tüketimi",
        metrics=(CanonicalMetric.OEE,), asset_ids=("Line-1", "Line-2"),
        period=TimePeriod.latest(),
    ))
    assert handle_metric_query_fallback(skill, widget_message(text, language))
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "clarification"
    assert not response["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls
    state = skill._dialogue_state_store.get("collection-session")
    assert not state.asset_ids and not state.metrics and not state.metric_name
    assert state.pending_clarification == "equipment scope"
    assert handle_metric_query_fallback(skill, widget_message("Compare them", language))
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", [
    ("Compare OEE for Line 1 and Line 10 yesterday", "en-US"),
    ("Hat 1 ve Hat 10 OEE değerlerini karşılaştır", "tr-TR"),
    ("How does OEE for Line 1 stack up against Line 2?", "en-US"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_resolved_comparison_uses_existing_asset_dispatcher(text, language, entry):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.response_builder = create_response_builder(language)
    comparison = Mock(wraps=skill.dispatcher.compare)
    skill.dispatcher.compare = comparison
    message = widget_message(text, language)
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        assert try_arbitrate_legacy_intent(skill, message, "compare.metric")
    expected = ["Line-1", "Line-10"] if "10" in text else ["Line-1", "Line-2"]
    assert comparison.call_args.kwargs["asset_ids"] == expected
    assert comparison.call_args.kwargs["metric"] is CanonicalMetric.OEE
    assert not skill._futuregen_service.reneryo.calls
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize("text,language", [
    ("Show OEE for Line 10 yesterday", "en-US"),
    ("Hat 10 OEE değerini göster", "tr-TR"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_resolved_single_asset_uses_mapped_kpi_not_factory_data(text, language, entry):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.response_builder = create_response_builder(language)
    kpi = Mock(wraps=skill.dispatcher.get_kpi)
    skill.dispatcher.get_kpi = kpi
    message = widget_message(text, language)
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        assert try_arbitrate_legacy_intent(skill, message, "kpi.oee")
    assert kpi.call_args.kwargs["asset_id"] == "Line-10"
    assert kpi.call_args.kwargs["metric"] is CanonicalMetric.OEE
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("entry", ["fallback", "registered"])
def test_unavailable_comparison_binding_does_not_retry_factory_data(entry):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.dispatcher.compare = Mock(side_effect=AdapterError(
        "Comparison is unavailable", code="ASSET_METRIC_UNAVAILABLE",
    ))
    message = widget_message("Compare OEE for Line 1 and Line 2", "en-US")
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        assert try_arbitrate_legacy_intent(skill, message, "compare.energy")
    skill.dispatcher.compare.assert_called_once()
    assert skill.spoken[-1][1]["meta"]["avaros_response"]["response_type"] == "clarification"
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,metric", [
    ("Compare energy between Line 1 and Line 2", CanonicalMetric.ENERGY_PER_UNIT),
    ("Which is more efficient Line 1 or Line 2", CanonicalMetric.ENERGY_PER_UNIT),
    ("Compare energy consumption of Line 1 vs Line 2 yesterday", CanonicalMetric.ENERGY_TOTAL),
])
def test_registered_energy_comparison_contract_and_explicit_consumption(text, metric):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.response_builder = create_response_builder("en-US")
    comparison = Mock(wraps=skill.dispatcher.compare)
    skill.dispatcher.compare = comparison
    message = widget_message(text, "en-US")
    message.data.update(asset_a="Line-1", asset_b="Line-10")
    assert try_arbitrate_legacy_intent(skill, message, "compare.energy")
    assert comparison.call_args.kwargs["metric"] is metric
    assert comparison.call_args.kwargs["asset_ids"] == ["Line-1", "Line-2"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("text,language", [
    ("Do not compare OEE for Line 1 and Line 2", "en-US"),
    ("Hat 1 ve Hat 2 OEE değerlerini karşılaştırma", "tr-TR"),
    ("Compare OEE for Line 1 and Line 2, not Line 10", "en-US"),
    ("Hat 1 ve Hat 2 OEE değerlerini kıyaslama", "tr-TR"),
])
def test_negated_comparison_is_not_executed(text, language):
    skill = setup_skill()
    assert handle_metric_query_fallback(skill, widget_message(text, language))
    assert not skill._futuregen_service.reneryo.calls
    assert skill.spoken[-1][1]["meta"]["avaros_response"]["response_type"] == "clarification"


def test_exact_inventory_metric_name_with_equipment_term_remains_supported():
    class NamedSource(Source):
        async def list_metrics(self):
            rows = await super().list_metrics()
            return [replace(rows[0], name="Boiler 1 electricity consumption"), rows[1]]

    skill = setup_skill(NamedSource())
    assert handle_metric_query_fallback(skill, widget_message(
        "Show Boiler 1 electricity consumption yesterday", "en-US",
    ))
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] != "clarification"
    assert response["evidence_rows"]


@pytest.mark.parametrize("text", [
    "List electricity meters", "What meters record our electricity?", "What meters are configured?",
])
def test_existing_meter_inventory_is_not_equipment_scope(text):
    skill = setup_skill()
    assert handle_metric_query_fallback(skill, widget_message(text, "en-US"))
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "meters"
    assert response["evidence_rows"]


def test_non_reneryo_profile_keeps_existing_comparison_path():
    skill = setup_skill()
    skill._loaded_profile = "generic_rest"
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.response_builder = create_response_builder("en-US")
    assert try_handle_structured_query(skill, widget_message("Compare OEE for Line 1 and Line 2", "en-US"))
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("language,text", [
    ("en-US", "Compare energy consumption of boiler 1 vs boiler 2 yesterday"),
    ("tr-TR", "Dün kazan 1 ile kazan 2 elektrik tüketimini karşılaştır"),
])
@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
def test_signed_proxy_payload_reaches_scope_guard(monkeypatch, language, text, entry):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "web-ui"))
    monkeypatch.setenv("AVAROS_WIDGET_SESSION_SECRET", "synthetic-secret-" * 3)
    monkeypatch.setenv("HIVEMIND_CLIENT_CRYPTO_KEY", "0123456789abcdef")
    from routers.hivemind import _backend_to_browser, _browser_to_backend
    from services.reneryo_sessions import issue_session, validate_session

    token, _ = issue_session({
        "organization_id": "futuregen", "language": language,
        "origin": "https://futuregen.reneryo.com",
    })
    session = validate_session(token, "https://futuregen.reneryo.com")
    raw = json.dumps({
        "msg_type": "bus", "payload": {
            "type": "recognizer_loop:utterance",
            "data": {"utterances": [text], "lang": language},
            "context": {"source": "avaros-widget", "session": {"session_id": "scope-session"}},
        },
    })
    forwarded = json.loads(_backend_to_browser(_browser_to_backend(raw, session)))["payload"]
    message = _message(text, language)
    message.data = forwarded["data"]
    message.context = forwarded["context"]
    # Loose recognizer slots must not override explicit unknown entities.
    message.data.update(asset_a="Line-1", asset_b="Line-2", metric="energy")
    assert message.data["utterances"] == [text]
    assert message.context["reneryo_widget_session_validated"] is True
    assert message.context["reneryo_context"]["organization_id"] == "futuregen"

    skill = setup_skill()
    skill.settings_service = None
    skill._resolve_asset_name_for_voice = lambda identifier: identifier
    skill._extract_utterance_text = lambda msg: extract_utterance_text(skill, msg)
    skill._sync_response_language = lambda msg: sync_response_language(skill, msg)
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        legacy = Mock()
        guarded = AVAROSSkill._guard_intent_activation(skill, "compare.energy", legacy)
        guarded(message)
        legacy.assert_not_called()
    response = skill.spoken[-1][1]["meta"]["avaros_response"]
    assert response["response_type"] == "clarification"
    assert response["language"] == language
    assert not response["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls
