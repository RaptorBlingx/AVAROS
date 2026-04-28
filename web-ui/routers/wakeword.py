"""Same-origin proxy endpoints for the wake-word backend.

The frontend connects to ``/wakeword/ws/detect`` on the same origin as
the Web UI. Nginx exposes that route in HTTPS deployments, but users
also access the FastAPI Web UI directly on port 8080 during demos and
development. These routes make both entry points behave the same.
"""

from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from fastapi import APIRouter, HTTPException, Response, WebSocket
from starlette.websockets import WebSocketDisconnect


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/wakeword", tags=["wakeword"])

_DEFAULT_BACKEND_URL = "http://avaros-wakeword:9999"
_BACKEND_TIMEOUT_SECONDS = 5


def _backend_http_url() -> str:
    """Return the wake-word backend HTTP base URL."""
    return os.environ.get("WAKEWORD_BACKEND_URL", _DEFAULT_BACKEND_URL).rstrip("/")


def _backend_ws_url() -> str:
    """Return the wake-word backend WebSocket URL."""
    base_url = _backend_http_url()
    if base_url.startswith("https://"):
        return f"wss://{base_url.removeprefix('https://')}/ws/detect"
    if base_url.startswith("http://"):
        return f"ws://{base_url.removeprefix('http://')}/ws/detect"
    return f"{base_url}/ws/detect"


@router.get("/health")
async def wakeword_health() -> Response:
    """Proxy wake-word backend health through the Web UI origin."""
    timeout = aiohttp.ClientTimeout(total=_BACKEND_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{_backend_http_url()}/health") as response:
                body = await response.read()
                media_type = response.headers.get("content-type", "application/json")
                return Response(
                    content=body,
                    status_code=response.status,
                    media_type=media_type,
                )
    except aiohttp.ClientError as exc:
        logger.warning("Wake-word health proxy failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Wake-word backend is unavailable",
        ) from exc


@router.websocket("/ws/detect")
async def wakeword_detect(websocket: WebSocket) -> None:
    """Proxy browser wake-word WebSocket traffic to the backend service."""
    await websocket.accept()
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=_BACKEND_TIMEOUT_SECONDS)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(_backend_ws_url(), max_msg_size=0) as backend:
                await _bridge_websockets(websocket, backend)
    except aiohttp.ClientError as exc:
        logger.warning("Wake-word websocket proxy failed: %s", exc)
        await websocket.close(code=1011, reason="Wake-word backend unavailable")


async def _bridge_websockets(
    client: WebSocket,
    backend: aiohttp.ClientWebSocketResponse,
) -> None:
    """Forward text/binary frames between browser and wake-word backend."""

    async def _client_to_backend() -> None:
        while True:
            try:
                message = await client.receive()
            except WebSocketDisconnect:
                break

            message_type = message.get("type")
            if message_type == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                await backend.send_bytes(message["bytes"])
            elif "text" in message and message["text"] is not None:
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

