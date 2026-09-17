from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from routers.hivemind import _backend_to_browser, _browser_to_backend
from services.reneryo_sessions import issue_session, validate_session


def test_session_is_signed_expiring_and_origin_bound(monkeypatch):
    monkeypatch.setenv("AVAROS_WIDGET_SESSION_SECRET", "x" * 32)
    token, expires = issue_session(
        {
            "organization_id": "org-1",
            "finding_id": "finding-1",
            "origin": "https://futuregen.reneryo.com",
            "language": "tr-TR",
        }
    )
    session = validate_session(token, "https://futuregen.reneryo.com")
    assert session.organization_id == "org-1"
    assert session.finding_id == "finding-1"
    assert expires == session.expires_at
    with pytest.raises(ValueError, match="origin"):
        validate_session(token, "https://attacker.example")


def test_proxy_injects_signed_context_and_translates_encryption(monkeypatch):
    monkeypatch.setenv("HIVEMIND_CLIENT_CRYPTO_KEY", "1234567890abcdef")
    monkeypatch.setenv("AVAROS_WIDGET_SESSION_SECRET", "x" * 32)
    token, _ = issue_session(
        {
            "organization_id": "org-1",
            "finding_id": "finding-1",
            "entity_id": "resource-1",
            "metric_name": "Electricity",
            "origin": "https://futuregen.reneryo.com",
            "language": "en-US",
        }
    )
    session = validate_session(token, "https://futuregen.reneryo.com")
    raw = json.dumps(
        {
            "msg_type": "bus",
            "payload": {"type": "recognizer_loop:utterance", "data": {}, "context": {}},
        }
    )
    encrypted = _browser_to_backend(raw, session)
    decrypted = json.loads(_backend_to_browser(encrypted))
    context = decrypted["payload"]["context"]["reneryo_context"]
    assert context == {
        "organization_id": "org-1",
        "finding_id": "finding-1",
        "entity_id": "resource-1",
        "metric_name": "Electricity",
    }


def test_proxy_preserves_private_plaintext_hivemind_transport(monkeypatch):
    monkeypatch.delenv("HIVEMIND_CLIENT_CRYPTO_KEY", raising=False)
    monkeypatch.setenv("AVAROS_WIDGET_SESSION_SECRET", "x" * 32)
    token, _ = issue_session(
        {
            "organization_id": "org-1",
            "finding_id": "finding-1",
            "origin": "https://futuregen.reneryo.com",
        }
    )
    session = validate_session(token, "https://futuregen.reneryo.com")
    raw = json.dumps(
        {
            "msg_type": "bus",
            "payload": {"type": "recognizer_loop:utterance", "data": {}, "context": {}},
        }
    )
    forwarded = json.loads(_browser_to_backend(raw, session))
    assert (
        forwarded["payload"]["context"]["reneryo_context"]["finding_id"] == "finding-1"
    )
