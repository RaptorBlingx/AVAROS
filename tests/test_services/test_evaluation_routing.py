"""D01: user intent gates evaluation before the authenticated MDSP client."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import AsyncMock, Mock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.clients.mdsp import MdspClient
from skill.domain.exceptions import AdapterError
from skill.services.finding_collection import is_evaluation_request
from skill.services.futuregen import FutureGenService
from skill.services.semantic_resolver import SemanticAction, SemanticResolution
from tests.test_services.test_finding_collection_dialogue import (
    _message,
    _response_type,
    _Skill,
)

REVIEW_QUESTIONS = [
    ("What should I check in the factory data?", "en-US"),
    ("Fabrika verilerinde neleri kontrol etmeliyim?", "tr-TR"),
    ("What should I check now?", "en-US"),
    ("Şimdi neyi kontrol etmeliyim?", "tr-TR"),
]
EXPLICIT_REQUESTS = [
    ("Analyze the current data and tell me what needs attention.", "en-US"),
    ("Güncel veriyi analiz et ve dikkat gerektirenleri anlat.", "tr-TR"),
    ("Can you evaluate the current data?", "en-US"),
    ("Güncel veriyi değerlendirir misin?", "tr-TR"),
    ("Run a fresh decision-support analysis of current Reneryo data.", "en-US"),
    ("Güncel Reneryo verileri için yeni bir karar destek analizi çalıştır.", "tr-TR"),
    ("Run a new MDSP evaluation.", "en-US"),
    ("MDSP değerlendirmesini başlat.", "tr-TR"),
    ("Check current data now.", "en-US"),
    ("Şimdi güncel veriyi kontrol et.", "tr-TR"),
    ("Güncel veriyi analiz et ve neleri kontrol etmeliyim söyle.", "tr-TR"),
]


@pytest.fixture
def mdsp_http():
    """Loopback-only synthetic API with the existing token/org authorization contract."""
    calls = []
    evaluations = []
    finding = {
        "id": "one",
        "status": "ACTIVE",
        "severity": "MEDIUM",
        "domain": "METRICS",
        "title": {"en": "Synthetic finding", "tr": "Sentetik bulgu"},
        "summary": {"en": "Synthetic summary", "tr": "Sentetik özet"},
        "evaluationWindow": {
            "start": "2026-09-01T00:00:00Z",
            "end": "2026-09-17T00:00:00Z",
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            token = self.headers.get("Authorization")
            organization = self.headers.get("X-Organization-Id")
            calls.append((self.command, self.path, token, organization))
            if token != "Bearer synthetic-token":
                status, payload = 401, {"error": "Unauthorized"}
            elif organization != "futuregen":
                status, payload = 403, {"error": "Organization is not permitted"}
            elif self.command == "POST" and self.path == "/v1/evaluations/manual":
                evaluations.append(organization)
                status, payload = 201, {
                    "runId": "synthetic-run",
                    "evaluatedResourceCount": 1,
                    "activeFindingCount": 1,
                    "resolvedFindingCount": 0,
                }
            elif self.command == "GET" and self.path == "/v1/findings/one":
                status, payload = 200, finding
            elif self.command == "GET" and self.path == "/v1/findings?status=ACTIVE":
                status, payload = 200, {
                    "records": [finding],
                    "summary": {
                        "active": 1,
                        "resolved": 0,
                        "bySeverity": {"medium": 1},
                    },
                }
            else:
                status, payload = 404, {"error": "Not found"}
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    skill = _Skill()
    client = MdspClient(f"http://127.0.0.1:{server.server_port}", "synthetic-token")
    reneryo = Mock(list_metrics=AsyncMock(return_value=[]))
    skill._futuregen_service = FutureGenService(reneryo, client)
    try:
        yield skill, calls, evaluations, client
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("question,language", REVIEW_QUESTIONS)
@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("semantic_evaluation", [False, True])
def test_review_question_only_reads_existing_findings(
    mdsp_http, question, language, selected, semantic_evaluation
):
    skill, calls, evaluations, _client = mdsp_http
    if selected:
        assert handle_reneryo_query(skill, _message("List active findings", language))
        assert handle_reneryo_query(skill, _message("Explain the first one", language))
    if semantic_evaluation:
        skill._semantic_resolver = Mock()
        skill._semantic_resolver.resolve.return_value = SemanticResolution(
            action=SemanticAction.FINDINGS_EVALUATE,
            language=language,
            confidence=1.0,
            margin=1.0,
        )
    calls.clear()

    assert handle_reneryo_query(skill, _message(question, language))

    assert _response_type(skill) == ("finding" if selected else "findings")
    assert [(method, path) for method, path, *_ in calls] == [
        ("GET", "/v1/findings/one" if selected else "/v1/findings?status=ACTIVE")
    ]
    assert not evaluations
    if selected:
        assert (
            skill._dialogue_state_store.get("collection-session").active_finding_id
            == "one"
        )
        assert skill.spoken[-1][0] == (
            "Bu bulgu için desteklenen bir sonraki inceleme önerisi mevcut değil."
            if language == "tr-TR"
            else "No supported next review is available for this finding."
        )


@pytest.mark.parametrize("question,language", EXPLICIT_REQUESTS)
def test_explicit_evaluation_uses_authenticated_scoped_post(
    mdsp_http, question, language
):
    skill, calls, evaluations, _client = mdsp_http

    assert handle_reneryo_query(skill, _message(question, language))

    assert _response_type(skill) == "evaluation"
    assert evaluations == ["futuregen"]
    assert calls == [
        ("POST", "/v1/evaluations/manual", "Bearer synthetic-token", "futuregen"),
        ("GET", "/v1/findings?status=ACTIVE", "Bearer synthetic-token", "futuregen"),
    ]


@pytest.mark.parametrize("question,language", EXPLICIT_REQUESTS[:2])
@pytest.mark.parametrize("unauthorized", ["token", "organization"])
def test_explicit_evaluation_cannot_bypass_mdsp_authorization(
    mdsp_http, question, language, unauthorized
):
    skill, calls, evaluations, client = mdsp_http
    message = _message(question, language)
    if unauthorized == "token":
        client._service_token = "wrong-token"
    else:
        message.context["reneryo_context"]["organization_id"] = "other-tenant"

    with pytest.raises(AdapterError) as error:
        handle_reneryo_query(skill, message)

    assert error.value.status_code == (401 if unauthorized == "token" else 403)
    assert len(calls) == 1 and calls[0][0] == "POST"
    assert not evaluations


INFORMATION_REQUESTS = [
    "How do I evaluate current data?",
    "Should I analyze the data now?",
    "What does the current data assessment mean?",
    "Explain how to run a check on current data.",
    "Güncel veriyi nasıl analiz etmeliyim?",
    "Veriyi nasıl değerlendiririm?",
    "Güncel veriyi kontrol etme.",
    "Güncel veriyi değerlendirme.",
    "Güncel veriyi analiz etme, bulguları göster.",
    "Do not evaluate the data; list findings.",
    "Güncel veriyi analiz et komutunu açıkla.",
    "Veriyi nasıl kontrol et?",
    "Güncel veriyi kontrol et lütfen derken neyi kastediyorsun?",
    "Tell me about the current data analysis.",
]


@pytest.mark.parametrize("text", INFORMATION_REQUESTS)
def test_information_and_negation_are_not_evaluation_permission(text):
    assert not is_evaluation_request(text)


@pytest.mark.parametrize("text", INFORMATION_REQUESTS)
def test_semantic_evaluation_cannot_authorize_information_or_negation(mdsp_http, text):
    skill, calls, evaluations, _client = mdsp_http
    skill._semantic_resolver = Mock()
    skill._semantic_resolver.resolve.return_value = SemanticResolution(
        action=SemanticAction.FINDINGS_EVALUATE,
        language="en-US",
        confidence=1.0,
        margin=1.0,
    )

    assert handle_reneryo_query(skill, _message(text))

    assert _response_type(skill) in {"clarification", "findings"}
    assert all(method == "GET" for method, *_ in calls)
    assert not evaluations
