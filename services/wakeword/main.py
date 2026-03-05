"""FastAPI microservice for wake-word detection over WebSocket.

Endpoints
---------
- ``GET  /health``        — readiness probe with loaded-model metadata.
- ``WS   /ws/detect``     — streams PCM audio in, detection events out.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from detector import WakeWordDetector, _resolve_model_path

SERVICE_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("avaros-wakeword")


# ── Startup validation ──────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ANN201
    """Validate model config on startup; no teardown needed."""
    model = _model_name()
    try:
        _resolve_model_path(model)
        logger.info("Model '%s' validated in openWakeWord registry.", model)
    except ValueError as exc:
        logger.critical("Startup validation failed: %s", exc)
        raise SystemExit(1) from exc
    yield


app = FastAPI(title="avaros-wakeword", version=SERVICE_VERSION, lifespan=lifespan)


# ── Configuration helpers ──────────────────────────────


def _model_name() -> str:
    """Return the configured wake-word model name."""
    return os.environ.get("WAKEWORD_MODEL", "hey_jarvis")


def _threshold() -> float:
    """Return the configured detection threshold (0–1)."""
    raw = os.environ.get("WAKEWORD_THRESHOLD", "0.5")
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.5


# ── Health endpoint ────────────────────────────────────


@app.get("/health")
def health() -> dict[str, Any]:
    """Return service status and configured model info.

    Returns:
        JSON with ``status``, ``models_loaded``, and ``version``.
    """
    return {
        "status": "ok",
        "models_loaded": [_model_name()],
        "version": SERVICE_VERSION,
    }


# ── WebSocket detection endpoint ───────────────────────


@app.websocket("/ws/detect")
async def ws_detect(websocket: WebSocket) -> None:
    """Accept PCM frames and send detection events.

    Protocol
    --------
    - Client sends raw 16 kHz signed-16-bit-LE PCM as binary frames.
    - Server responds **only** on detection (no chatter on silence).
    - Server cleans up model state when the client disconnects.
    """
    await websocket.accept()
    logger.info("WebSocket connected: %s", websocket.client)

    try:
        detector = WakeWordDetector(
            model_name=_model_name(),
            threshold=_threshold(),
        )
    except ValueError as exc:
        logger.error("Failed to create detector: %s", exc)
        await websocket.close(code=1008, reason=str(exc))
        return

    try:
        while True:
            pcm_frame: bytes = await websocket.receive_bytes()
            event = detector.process_audio(pcm_frame)
            if event is not None:
                await websocket.send_json(asdict(event))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", websocket.client)
    finally:
        detector.close()
