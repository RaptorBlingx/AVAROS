"""Widget TypeScript -> signed proxy -> backend handlers, synthetic APIs.

Requires frontend npm dependencies and Node. This exercises the request payload
and deterministic dialogue path, not a running WebSocket/OVOS recognizer.
"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from skill._helpers import extract_utterance_text, sync_response_language
from skill import AVAROSSkill
from skill._handlers import handle_metric_query_fallback
from skill._reneryo_handlers import handle_reneryo_query
from skill.services.response_builder import create_response_builder
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.helpers.stub_adapter import StubAdapter
from tests.test_services.test_explicit_query_scope import ASSETS, UNSUPPORTED, setup_skill
from tests.test_services.test_period_resolution import TIME_REQUESTS
from skill.services.conversation_state import DialogueState
from skill.domain.models import CanonicalMetric, TimePeriod
from unittest.mock import Mock
from skill.services.dia_dialogue import try_handle_structured_query
from tests.test_services.test_factory_predeployment import harness
from tests.test_services.test_factory_questions import QUESTIONS
from tests.test_services.test_finding_collection_dialogue import _message, _Skill
from tests.test_services.test_evaluation_routing import EXPLICIT_REQUESTS, REVIEW_QUESTIONS
from tests.test_services.test_natural_paraphrases import FRESHNESS, CHANGE, OWNERS, REVIEWS
from tests.test_services.test_comparison_followups import NATURAL, PRONOUNS, PERIODS, comparison_skill


COMPARISONS = [
    "Compare energy consumption of boiler 1 vs boiler 2 yesterday",
    "Compare electricity consumption between boiler 1 and boiler 2 yesterday",
    "Dün kazan 1 ile kazan 2 elektrik tüketimini karşılaştır",
]
FOLLOWUPS = [
    "Show electricity consumption", "And June?",
    "Elektrik tüketimini göster", "Peki Haziran?",
]
FINDINGS = [
    "List active findings", "Explain the first one", "What evidence supports this finding?",
    "Etkin bulguları listele", "İlk bulguyu açıkla", "Bu bulguyu hangi kanıt destekliyor?",
]
CONFIGURED = [
    ("Show OEE for Line 10 today", "en-US", "kpi.oee", ["Line-10"]),
    ("Hat 10 OEE değerini dün göster", "tr-TR", "kpi.oee", ["Line-10"]),
    ("Show OEE for Line 10 in June 2020", "en-US", "kpi.oee", ["Line-10"]),
    ("Hat 10 OEE değerini Haziran 2020 için göster", "tr-TR", "kpi.oee", ["Line-10"]),
    ("Show overall equipment effectiveness for Line 10", "en-US", "kpi.oee", ["Line-10"]),
    ("Hat 10 toplam ekipman etkinliği değerini göster", "tr-TR", "kpi.oee", ["Line-10"]),
    ("Compare overall equipment effectiveness for Line 1 and Line 10", "en-US", "compare.metric", ["Line-1", "Line-10"]),
    ("Hat 1, Hat 10 toplam ekipman etkinliği değerlerini karşılaştır", "tr-TR", "compare.metric", ["Line-1", "Line-10"]),
    ("Compare OEE for Line 1, and Line 10 yesterday", "en-US", "compare.metric", ["Line-1", "Line-10"]),
    ("Show OEE for Line 10 yesterday?", "en-US", "kpi.oee", ["Line-10"]),
    ("Hat 10 OEE değerini göster!", "tr-TR", "kpi.oee", ["Line-10"]),
    ("Compare OEE for Line 1 and Line 10 yesterday!", "en-US", "compare.metric", ["Line-1", "Line-10"]),
    ("Hat 1 ve Hat 10 OEE değerlerini karşılaştır?", "tr-TR", "compare.metric", ["Line-1", "Line-10"]),
]
METERS = ["List all meters", "Tüm sayaçları listele"]


@pytest.fixture(scope="module")
def widget_payloads():
    frontend = Path(__file__).resolve().parents[2] / "web-ui" / "frontend"
    typescript = frontend / "node_modules" / "typescript"
    if not shutil.which("node") or not typescript.exists():
        pytest.skip("Node and frontend npm dependencies are required")
    requests = [text for text, _kind in QUESTIONS] + COMPARISONS + FOLLOWUPS + FINDINGS + METERS + [row[0] for row in UNSUPPORTED + CONFIGURED + TIME_REQUESTS]
    requests += [text for text, _language in EXPLICIT_REQUESTS + REVIEW_QUESTIONS + OWNERS + REVIEWS]
    requests += [text for text, _language, _identifier in FRESHNESS + CHANGE]
    requests += [text for text, _language, _metric in NATURAL] + [text for text, _language in PRONOUNS + PERIODS]
    requests += ["Compare OEE for Line 1 and Line 2 today"]
    script = r"""
const fs = require('fs');
const ts = require(process.argv[1]);
const source = fs.readFileSync(process.argv[2], 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;
const exported = {};
new Function('exports', js)(exported);
const requests = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(Object.fromEntries(requests.map(request =>
  [request, exported.normalizeUtteranceForIntent(request)]))));
"""
    result = subprocess.run(
        ["node", "-e", script, str(typescript),
         str(frontend / "src/services/intent-normalizer.ts")],
        input=json.dumps(requests), text=True, capture_output=True, check=True,
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(frontend.parent))
        patch.setenv("AVAROS_WIDGET_SESSION_SECRET", "test-secret-" * 4)
        patch.setenv("HIVEMIND_CLIENT_CRYPTO_KEY", "0123456789abcdef")
        from routers.hivemind import _backend_to_browser, _browser_to_backend
        from services.reneryo_sessions import issue_session, validate_session

        def forward(data, context, language):
            token, _ = issue_session({
                "organization_id": "futuregen",
                "language": language,
                "origin": "https://futuregen.reneryo.com",
            })
            session = validate_session(token, "https://futuregen.reneryo.com")
            envelope = json.dumps({
                "msg_type": "bus",
                "payload": {"type": "recognizer_loop:utterance", "data": data, "context": context},
            })
            encrypted = _browser_to_backend(envelope, session)
            return json.loads(_backend_to_browser(encrypted))["payload"]

        yield json.loads(result.stdout), forward


def ask_from_widget(skill, payloads, original, language):
    payloads, forward = payloads
    transmitted = payloads[original]
    assert transmitted == original
    message = _message(transmitted, language)
    # Same request data shape emitted by ConnectionManager.sendUtterance.
    message.data = {"utterances": [transmitted], "lang": language}
    forwarded = forward(message.data, {
        "source": "avaros-widget",
        "session": {"session_id": "collection-session", "lang": language},
    }, language)
    message.data = forwarded["data"]
    message.context = forwarded["context"]
    assert message.data["utterances"] == [original]
    assert message.context["reneryo_widget_session_validated"] is True
    assert message.context["reneryo_context"]["organization_id"] == "futuregen"
    assert message.context["reneryo_context"]["language"] == language
    skill._response_language = language
    skill._resolve_asset_name_for_voice = lambda identifier: identifier
    skill._get_asset_registry = lambda: []
    skill._extract_utterance_text = lambda msg: extract_utterance_text(skill, msg)
    assert skill._extract_utterance_text(message) == original
    assert try_handle_structured_query(skill, message)
    return skill.spoken[-1][1]["meta"]["avaros_response"]


@pytest.mark.parametrize("question,kind", QUESTIONS)
def test_supported_factory_questions_survive_widget_preprocessing(widget_payloads, question, kind):
    language = "tr-TR" if QUESTIONS.index((question, kind)) >= 22 else "en-US"
    response = ask_from_widget(harness(), widget_payloads, question, language)
    assert response["evidence_rows"]
    assert response["language"] == language


@pytest.mark.parametrize("question,language", list(zip(METERS, ["en-US", "tr-TR"])))
def test_meter_inventory_survives_widget_preprocessing(widget_payloads, question, language):
    response = ask_from_widget(harness(), widget_payloads, question, language)
    assert response["response_type"] == "meters"
    assert response["evidence_rows"][0]["id"] == "m"


@pytest.mark.parametrize("language,start", [("en-US", 0), ("tr-TR", 2)])
def test_factory_followup_keeps_subject_and_period(widget_payloads, language, start):
    skill = harness()
    ask_from_widget(skill, widget_payloads, FOLLOWUPS[start], language)
    response = ask_from_widget(skill, widget_payloads, FOLLOWUPS[start + 1], language)
    assert response["evidence_rows"]
    assert skill._futuregen_service.reneryo.calls[-1][1].month == 6
    assert skill._dialogue_state_store.get("collection-session").metric_name == "Tesis Toplam Elektrik Tüketimi"


@pytest.mark.parametrize("language,start", [("en-US", 0), ("tr-TR", 3)])
def test_finding_selection_and_evidence_followup(widget_payloads, language, start):
    skill = _Skill()
    assert ask_from_widget(skill, widget_payloads, FINDINGS[start], language)["response_type"] == "findings"
    assert ask_from_widget(skill, widget_payloads, FINDINGS[start + 1], language)["response_type"] == "finding"
    response = ask_from_widget(skill, widget_payloads, FINDINGS[start + 2], language)
    assert response["response_type"] == "finding"
    assert response["evidence_rows"]
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "one"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("question", COMPARISONS)
def test_structured_entry_rejects_unsupported_comparisons(widget_payloads, question):
    skill = harness()
    language = "tr-TR" if question.startswith("Dün") else "en-US"
    response = ask_from_widget(skill, widget_payloads, question, language)
    assert response["response_type"] == "clarification"
    assert not response["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls


def routed_widget_message(skill, payloads, text, language):
    normalized, forward = payloads
    assert normalized[text] == text
    forwarded = forward({"utterances": [normalized[text]], "lang": language}, {
        "source": "avaros-widget", "session": {"session_id": "collection-session"},
    }, language)
    message = _message(text, language)
    message.data, message.context = forwarded["data"], forwarded["context"]
    skill._extract_utterance_text = lambda msg: extract_utterance_text(skill, msg)
    skill._sync_response_language = lambda msg: sync_response_language(skill, msg)
    skill._resolve_asset_name_for_voice = lambda identifier: identifier
    assert skill._extract_utterance_text(message) == text
    return message


def route(skill, message, entry, intent="reneryo.query"):
    if entry == "fallback":
        assert handle_metric_query_fallback(skill, message)
    else:
        skill.settings_service = None
        legacy = Mock(side_effect=lambda msg: handle_reneryo_query(skill, msg))
        AVAROSSkill._guard_intent_activation(skill, intent, legacy)(message)
        if intent != "reneryo.query":
            legacy.assert_not_called()
    return skill.spoken[-1][1]["meta"]["avaros_response"]


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("question,language", REVIEW_QUESTIONS)
@pytest.mark.parametrize("selected", [False, True])
def test_widget_review_questions_remain_read_only(widget_payloads, entry, question, language, selected):
    skill = _Skill()
    if selected:
        start = 0 if language == "en-US" else 3
        ask_from_widget(skill, widget_payloads, FINDINGS[start], language)
        ask_from_widget(skill, widget_payloads, FINDINGS[start + 1], language)
    response = route(skill, routed_widget_message(skill, widget_payloads, question, language), entry, "help")
    assert response["response_type"] == ("finding" if selected else "findings")
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("question,language", EXPLICIT_REQUESTS)
def test_widget_explicit_evaluation_remains_available(widget_payloads, entry, question, language):
    skill = _Skill()
    response = route(skill, routed_widget_message(skill, widget_payloads, question, language), entry, "help")
    assert response["response_type"] == "evaluation"
    assert skill._futuregen_service.evaluations == 1


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("question,kind", QUESTIONS)
def test_combined_factory_routes_keep_grounded_answers(widget_payloads, entry, question, kind):
    language = "tr-TR" if QUESTIONS.index((question, kind)) >= 22 else "en-US"
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    response = route(skill, routed_widget_message(skill, widget_payloads, question, language), entry)
    assert response["evidence_rows"]
    assert response["language"] == language


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language", UNSUPPORTED)
def test_combined_scope_refuses_without_factory_substitution(widget_payloads, entry, text, language):
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    response = route(skill, routed_widget_message(skill, widget_payloads, text, language), entry, "compare.energy")
    assert response["response_type"] == "clarification"
    assert response["language"] == language
    assert not response["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language,intent,asset_ids", CONFIGURED)
def test_combined_configured_entities_reach_exact_dispatcher(widget_payloads, entry, text, language, intent, asset_ids):
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill._response_language = "en-US"
    skill.response_builder = create_response_builder("en-US")
    operation = "compare" if len(asset_ids) > 1 else "get_kpi"
    called = Mock(wraps=getattr(skill.dispatcher, operation))
    setattr(skill.dispatcher, operation, called)
    response = route(skill, routed_widget_message(skill, widget_payloads, text, language), entry, intent)
    assert response["response_type"] != "clarification"
    assert skill._response_language == language
    if language == "tr-TR":
        assert "ekipman etkinliği" in response["headline"].lower()
    assert (called.call_args.kwargs["asset_ids"] if operation == "compare" else [called.call_args.kwargs["asset_id"]]) == asset_ids
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("language,start", [("en-US", 0), ("tr-TR", 2)])
def test_combined_factory_followup(widget_payloads, entry, language, start):
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    for text in FOLLOWUPS[start:start+2]:
        response = route(skill, routed_widget_message(skill, widget_payloads, text, language), entry)
        assert response["evidence_rows"]
    assert skill._futuregen_service.reneryo.calls[-1][1].month == 6


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("language,start", [("en-US", 0), ("tr-TR", 3)])
def test_combined_finding_followup(widget_payloads, entry, language, start):
    skill = _Skill()
    skill._get_asset_registry = lambda: ASSETS
    for text in FINDINGS[start:start+3]:
        response = route(skill, routed_widget_message(skill, widget_payloads, text, language), entry)
        assert response["evidence_rows"]
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "one"
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language", list(zip(METERS, ["en-US", "tr-TR"])))
def test_combined_meter_inventory(widget_payloads, entry, text, language):
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    response = route(skill, routed_widget_message(skill, widget_payloads, text, language), entry)
    assert response["response_type"] == "meters"
    assert response["evidence_rows"][0]["id"] == "m"


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language", TIME_REQUESTS)
def test_widget_clock_precision_never_executes_latest_or_inherited_data(widget_payloads, entry, text, language):
    skill = setup_skill()
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    calls = {}
    for operation in ("get_kpi", "compare", "get_trend"):
        calls[operation] = Mock(wraps=getattr(skill.dispatcher, operation))
        setattr(skill.dispatcher, operation, calls[operation])
    prior = DialogueState(
        organization_id="futuregen", language=language, operation="kpi",
        metric_name="Tesis Toplam Elektrik Tüketimi",
        metrics=(CanonicalMetric.OEE,), asset_ids=("Line-10",),
        period=TimePeriod.from_natural_language("June 2020"),
    )
    skill._dialogue_state_store.put("collection-session", prior)
    message = routed_widget_message(skill, widget_payloads, text, language)
    # Slots cannot override the explicit unsupported precision in original text.
    message.data.update(period="latest", asset="Line-10", metric="oee")
    response = route(skill, message, entry, "kpi.oee")
    assert response["response_type"] == "clarification"
    assert response["language"] == language
    assert ("Saat düzeyindeki" if language == "tr-TR" else "Time-of-day") in response["headline"]
    assert not response["evidence_rows"]
    assert not skill._futuregen_service.reneryo.calls
    skill._semantic_resolver.resolve.assert_not_called()
    for called in calls.values():
        called.assert_not_called()
    state = skill._dialogue_state_store.get("collection-session")
    assert state.period == prior.period
    assert state.organization_id == "futuregen"
    assert state.pending_clarification == "time precision"


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("language,start", [("en-US", 0), ("tr-TR", 2)])
def test_supported_factory_period_followup_after_clock_clarification(widget_payloads, entry, language, start):
    skill = harness()
    skill._get_asset_registry = lambda: ASSETS
    route(skill, routed_widget_message(skill, widget_payloads, FOLLOWUPS[start], language), entry)
    calls_before = list(skill._futuregen_service.reneryo.calls)
    clock = "And at 14:30?" if language == "en-US" else "Peki saat 14:30?"
    response = route(skill, routed_widget_message(skill, widget_payloads, clock, language), entry)
    assert response["response_type"] == "clarification"
    assert skill._futuregen_service.reneryo.calls == calls_before
    response = route(skill, routed_widget_message(skill, widget_payloads, FOLLOWUPS[start+1], language), entry)
    assert response["evidence_rows"]
    assert skill._futuregen_service.reneryo.calls[-1][1].month == 6


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language,identifier", FRESHNESS + CHANGE)
def test_d08_paraphrases_survive_signed_widget_and_legacy_arbitration(widget_payloads, entry, text, language, identifier):
    skill = harness()
    message = routed_widget_message(skill, widget_payloads, text, language)
    response = route(skill, message, entry)
    source = skill._futuregen_service.reneryo
    if (text, language, identifier) in FRESHNESS:
        assert source.calls == []
        assert response["evidence_rows"][0]["recorded_at"].startswith("2020-07-01")
    else:
        assert response["response_type"] == "trend"
        assert source.calls[0][0] == identifier
        assert source.calls[0][1].isoformat().startswith("2020-05-01")
        assert source.calls[0][2].isoformat().startswith("2020-07-01")
        assert not any(call[0] == "meter" for call in source.calls)
    assert response["language"] == language


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language", OWNERS + REVIEWS)
def test_d08_signed_finding_followups_keep_selection_and_never_evaluate(widget_payloads, entry, text, language):
    skill = _Skill()
    for turn in ["List active findings", "Explain the first one", text]:
        response = route(skill, routed_widget_message(skill, widget_payloads, turn, language), entry)
    assert response["response_type"] == "finding"
    assert skill._dialogue_state_store.get("collection-session").active_finding_id == "one"
    assert skill._futuregen_service.evaluations == 0
    assert ("owner assignment" in response["headline"] or "sorumlu ataması" in response["headline"]) if (text, language) in OWNERS else ("next review" in response["headline"] or "inceleme önerisi" in response["headline"])


@pytest.mark.parametrize("entry", ["fallback", "registered-wrapper"])
@pytest.mark.parametrize("text,language", PRONOUNS + PERIODS)
def test_signed_widget_comparison_followups_preserve_frame(widget_payloads, entry, text, language):
    skill = comparison_skill("en-US")
    first = routed_widget_message(skill, widget_payloads, "Compare OEE for Line 1 and Line 2 today", "en-US")
    assert route(skill, first, entry, "kpi.oee")["response_type"] == "comparison"
    message = routed_widget_message(skill, widget_payloads, text, language)
    response = route(skill, message, entry, "kpi.oee")
    assert response["response_type"] == "comparison" and response["language"] == language
    request = skill.dispatcher.compare.call_args.kwargs
    assert request["asset_ids"] == ["Line-1", "Line-2"]
    assert request["metric"] == CanonicalMetric.OEE
    expected = "today" if (text, language) in PRONOUNS else "June 2020" if "2020" in text else "yesterday"
    assert request["period"].start == TimePeriod.from_natural_language(expected).start
    assert not skill._futuregen_service.reneryo.calls
