"""Same-origin WebSocket proxy for HiveMind browser voice clients.

The browser connects to ``/hivemind/`` on the same origin as the Web UI.
This keeps voice working when an operator changes ``AVAROS_WEB_PORT`` and
avoids exposing Docker-internal hostnames to the browser.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os

import aiohttp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, WebSocket
from services.reneryo_sessions import ReneryoSession, validate_session
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/hivemind", tags=["hivemind"])

_DEFAULT_BACKEND_URL = "ws://hivemind:5678/"
_BACKEND_TIMEOUT_SECONDS = 5


def _backend_ws_url() -> str:
    """Return the Docker-internal HiveMind WebSocket endpoint."""
    url = os.environ.get("HIVEMIND_BACKEND_URL", _DEFAULT_BACKEND_URL).strip()
    if not url:
        return _DEFAULT_BACKEND_URL
    if not url.startswith(("ws://", "wss://")):
        raise ValueError("HIVEMIND_BACKEND_URL must use ws:// or wss://")
    return url if url.endswith("/") else f"{url}/"


@router.websocket("/")
async def hivemind_proxy(websocket: WebSocket) -> None:
    """Bridge a browser WebSocket to the internal HiveMind service."""
    authorization = websocket.query_params.get("authorization", "").strip()
    session_token = websocket.query_params.get("session", "").strip()
    reneryo_session = None
    if session_token:
        try:
            reneryo_session = validate_session(
                session_token,
                websocket.headers.get("origin", ""),
            )
            authorization = _server_hivemind_authorization()
        except ValueError as exc:
            await websocket.accept()
            await websocket.close(code=1008, reason=str(exc))
            return
    await websocket.accept()

    if not authorization:
        await websocket.close(code=1008, reason="HiveMind authorization required")
        return

    timeout = aiohttp.ClientTimeout(
        total=None,
        sock_connect=_BACKEND_TIMEOUT_SECONDS,
    )
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.ws_connect(
                _backend_ws_url(),
                headers={"X-HiveMind-Auth": authorization},
                max_msg_size=0,
            ) as backend,
        ):
            await _bridge_websockets(websocket, backend, reneryo_session)
    except (aiohttp.ClientError, ValueError) as exc:
        logger.warning("HiveMind websocket proxy failed: %s", exc)
        await websocket.close(code=1011, reason="HiveMind backend unavailable")


async def _bridge_websockets(
    client: WebSocket,
    backend: aiohttp.ClientWebSocketResponse,
    reneryo_session: ReneryoSession | None = None,
) -> None:
    """Forward text and binary frames in both directions."""

    async def _client_to_backend() -> None:
        while True:
            try:
                message = await client.receive()
            except WebSocketDisconnect:
                break

            message_type = message.get("type")
            if message_type == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await backend.send_bytes(message["bytes"])
            elif message.get("text") is not None:
                text = message["text"]
                if reneryo_session:
                    text = _browser_to_backend(text, reneryo_session)
                await backend.send_str(text)

        await backend.close()

    async def _backend_to_client() -> None:
        async for message in backend:
            if message.type == aiohttp.WSMsgType.TEXT:
                text = message.data
                if reneryo_session:
                    text = _backend_to_browser(text)
                await client.send_text(text)
            elif message.type == aiohttp.WSMsgType.BINARY:
                await client.send_bytes(message.data)
            elif message.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            }:
                break

        await client.close()

    tasks = {
        asyncio.create_task(_client_to_backend()),
        asyncio.create_task(_backend_to_client()),
    }
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*done, *pending, return_exceptions=True)


def _server_hivemind_authorization() -> str:
    name = os.environ.get("HIVEMIND_CLIENT_NAME", "avaros-web-client")
    key = os.environ.get("HIVEMIND_CLIENT_KEY", "")
    if not key:
        raise ValueError("Server HiveMind client is not configured")
    return base64.b64encode(f"{name}:{key}".encode()).decode()


def _browser_to_backend(raw: str, session: ReneryoSession) -> str:
    payload = json.loads(raw)
    envelope = payload
    bus = envelope.get("payload") if isinstance(envelope, dict) else None
    if isinstance(bus, dict):
        data = bus.get("data")
        if isinstance(data, dict) and session.language.lower().startswith("tr"):
            # The deployed OVOS intent pipeline is trained under en-US. Keep the
            # signed Turkish locale in context for response localization while
            # routing the bilingual Reneryo vocabulary through that pipeline.
            data["lang"] = "en-US"
        context = bus.setdefault("context", {})
        if isinstance(context, dict):
            context["reneryo_context"] = {
                "organization_id": session.organization_id,
                "finding_id": session.finding_id,
                "entity_id": session.entity_id,
                "metric_name": session.metric_name,
            }
            nested = context.setdefault("session", {})
            if isinstance(nested, dict):
                nested["lang"] = session.language
    return _encrypt(json.dumps(envelope, separators=(",", ":")))


def _backend_to_browser(raw: str) -> str:
    return _decrypt(raw)


def _crypto_key() -> bytes | None:
    key = os.environ.get("HIVEMIND_CLIENT_CRYPTO_KEY", "").encode()
    if not key:
        return None
    if len(key) not in (16, 24, 32):
        raise ValueError("HIVEMIND_CLIENT_CRYPTO_KEY must be an AES key")
    return key


def _encrypt(raw: str) -> str:
    key = _crypto_key()
    if key is None:
        return raw
    nonce = os.urandom(16)
    ciphertext = AESGCM(key).encrypt(nonce, raw.encode(), None)
    return json.dumps({"nonce": nonce.hex(), "ciphertext": ciphertext.hex()})


def _decrypt(raw: str) -> str:
    envelope = json.loads(raw)
    if not isinstance(envelope, dict) or "ciphertext" not in envelope:
        return raw
    key = _crypto_key()
    if key is None:
        raise ValueError("Encrypted HiveMind response received without a crypto key")
    nonce = bytes.fromhex(str(envelope["nonce"]))
    ciphertext = bytes.fromhex(str(envelope["ciphertext"]))
    if envelope.get("tag"):
        ciphertext += bytes.fromhex(str(envelope["tag"]))
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode()
