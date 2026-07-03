"""Same-origin WebSocket proxy for HiveMind browser voice clients.

The browser connects to ``/hivemind/`` on the same origin as the Web UI.
This keeps voice working when an operator changes ``AVAROS_WEB_PORT`` and
avoids exposing Docker-internal hostnames to the browser.
"""

from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from fastapi import APIRouter, WebSocket
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
    await websocket.accept()

    if not authorization:
        await websocket.close(code=1008, reason="HiveMind authorization required")
        return

    timeout = aiohttp.ClientTimeout(
        total=None,
        sock_connect=_BACKEND_TIMEOUT_SECONDS,
    )
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                _backend_ws_url(),
                headers={"X-HiveMind-Auth": authorization},
                max_msg_size=0,
            ) as backend:
                await _bridge_websockets(websocket, backend)
    except (aiohttp.ClientError, ValueError) as exc:
        logger.warning("HiveMind websocket proxy failed: %s", exc)
        await websocket.close(code=1011, reason="HiveMind backend unavailable")


async def _bridge_websockets(
    client: WebSocket,
    backend: aiohttp.ClientWebSocketResponse,
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
                await backend.send_str(message["text"])

        await backend.close()

    async def _backend_to_client() -> None:
        async for message in backend:
            if message.type == aiohttp.WSMsgType.TEXT:
                await client.send_text(message.data)
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
