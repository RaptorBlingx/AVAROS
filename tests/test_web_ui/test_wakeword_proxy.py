"""Tests for same-origin wake-word proxy routes."""

from __future__ import annotations

import sys
from pathlib import Path

import aiohttp
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from routers import wakeword  # noqa: E402


class _FakeHealthResponse:
    status = 200
    headers = {"content-type": "application/json"}

    async def __aenter__(self) -> "_FakeHealthResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def read(self) -> bytes:
        return b'{"status":"ok","models_loaded":["hey_jarvis"]}'


class _FakeHealthSession:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.requested_url = ""

    async def __aenter__(self) -> "_FakeHealthSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def get(self, url: str) -> _FakeHealthResponse:
        self.requested_url = url
        return _FakeHealthResponse()


class _FailingSession:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FailingSession":
        raise aiohttp.ClientConnectionError("refused")

    async def __aexit__(self, *args: object) -> None:
        return None


def test_wakeword_health_is_public_same_origin_proxy(
    client_no_auth: TestClient,
    monkeypatch,
) -> None:
    """GET /wakeword/health proxies without requiring API auth."""
    monkeypatch.setattr(wakeword.aiohttp, "ClientSession", _FakeHealthSession)

    response = client_no_auth.get("/wakeword/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["models_loaded"] == ["hey_jarvis"]


def test_wakeword_health_returns_503_when_backend_unavailable(
    client_no_auth: TestClient,
    monkeypatch,
) -> None:
    """A down wake-word backend should be explicit, not a SPA 404."""
    monkeypatch.setattr(wakeword.aiohttp, "ClientSession", _FailingSession)

    response = client_no_auth.get("/wakeword/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Wake-word backend is unavailable"


def test_backend_ws_url_derives_from_backend_http_url(monkeypatch) -> None:
    """The WebSocket proxy target is derived from WAKEWORD_BACKEND_URL."""
    monkeypatch.setenv("WAKEWORD_BACKEND_URL", "http://wakeword:9999")
    assert wakeword._backend_ws_url() == "ws://wakeword:9999/ws/detect"

    monkeypatch.setenv("WAKEWORD_BACKEND_URL", "https://wakeword.example")
    assert wakeword._backend_ws_url() == "wss://wakeword.example/ws/detect"


def test_embedded_wake_socket_rejects_invalid_signed_session(
    client_no_auth: TestClient,
    monkeypatch,
) -> None:
    """Embedded microphone audio must retain the signed origin boundary."""
    monkeypatch.setattr(
        wakeword,
        "validate_session",
        lambda _token, _origin: (_ for _ in ()).throw(
            ValueError("Invalid widget session")
        ),
    )

    with pytest.raises(WebSocketDisconnect) as caught:
        with client_no_auth.websocket_connect(
            "/wakeword/ws/detect",
            headers={"origin": "https://futuregen.reneryo.com"},
        ) as socket:
            socket.send_json(
                {"command": "authenticate_widget", "session": "invalid"}
            )
            socket.receive_json()

    assert caught.value.code == 1008


def test_cross_origin_wake_socket_requires_signed_session(
    client_no_auth: TestClient,
) -> None:
    """A cross-origin page cannot bypass widget session validation."""
    with pytest.raises(WebSocketDisconnect) as caught:
        with client_no_auth.websocket_connect(
            "/wakeword/ws/detect",
            headers={"origin": "https://futuregen.reneryo.com"},
        ) as socket:
            socket.send_json({"command": "set_sensitivity", "value": 0.75})
            socket.receive_json()

    assert caught.value.code == 1008


def test_same_origin_socket_detection_honors_forwarded_headers() -> None:
    """The direct AVAROS UI remains usable behind the TLS proxy."""
    class _Socket:
        headers = {
            "origin": "https://avaros.reneryo.com",
            "host": "web-ui:8000",
            "x-forwarded-host": "avaros.reneryo.com",
            "x-forwarded-proto": "https",
        }
        url = type("URL", (), {"scheme": "ws"})()

    assert wakeword._is_same_origin_socket(_Socket())
