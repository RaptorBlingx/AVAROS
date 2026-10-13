"""Widget TypeScript -> signed proxy -> backend handlers, synthetic APIs.

Requires frontend npm dependencies and Node. This exercises the request payload
and deterministic dialogue path, not a running WebSocket/OVOS recognizer.
"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from skill._helpers import extract_utterance_text
from skill.services.dia_dialogue import try_handle_structured_query
from tests.test_services.test_factory_predeployment import harness
from tests.test_services.test_factory_questions import QUESTIONS
from tests.test_services.test_finding_collection_dialogue import _message, _Skill


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
METERS = ["List all meters", "Tüm sayaçları listele"]


@pytest.fixture(scope="module")
def widget_payloads():
    frontend = Path(__file__).resolve().parents[2] / "web-ui" / "frontend"
    typescript = frontend / "node_modules" / "typescript"
    if not shutil.which("node") or not typescript.exists():
        pytest.skip("Node and frontend npm dependencies are required")
    requests = [text for text, _kind in QUESTIONS] + COMPARISONS + FOLLOWUPS + FINDINGS + METERS
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
