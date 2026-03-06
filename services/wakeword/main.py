"""FastAPI microservice for wake-word detection over WebSocket.

Endpoints
---------
- ``GET  /health``        — readiness probe with loaded-model metadata.
- ``WS   /ws/detect``     — streams PCM audio in, detection events out.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if __package__:
    # Package import path (used by tests and repo-root execution).
    from .detector import WakeWordDetector, _resolve_model_path
else:
    # Script-style import path (used by container CMD: uvicorn main:app).
    from detector import WakeWordDetector, _resolve_model_path

SERVICE_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("avaros-wakeword")

MAX_WS_CLOSE_REASON_BYTES = 120


# ── Startup validation ──────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ANN201
    """Validate model config on startup; no teardown needed."""
    custom_path = _custom_model_path()
    if custom_path:
        if not os.path.isfile(custom_path):
            logger.critical(
                "WAKEWORD_MODEL_PATH='%s' does not exist.", custom_path,
            )
            raise SystemExit(1)
        logger.info(
            "Custom model validated: %s (label=%s)",
            custom_path,
            _model_label(),
        )
    else:
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


def _custom_model_path() -> str | None:
    """Return the custom model file path, or ``None`` for registry mode."""
    return os.environ.get("WAKEWORD_MODEL_PATH") or None


def _model_label() -> str:
    """Return the display label for the active model.

    Priority: ``WAKEWORD_MODEL_LABEL`` env var > filename stem of
    ``WAKEWORD_MODEL_PATH`` > ``WAKEWORD_MODEL``.

    Returns:
        Human-readable model label.
    """
    label = os.environ.get("WAKEWORD_MODEL_LABEL")
    if label:
        return label
    custom_path = _custom_model_path()
    if custom_path:
        return os.path.splitext(os.path.basename(custom_path))[0]
    return _model_name()


def _threshold() -> float:
    """Return the configured detection threshold (0–1)."""
    raw = os.environ.get("WAKEWORD_THRESHOLD", "0.5")
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.5


def _safe_close_reason(reason: str) -> str:
    """Return a WebSocket close reason that fits protocol limits."""
    encoded = reason.encode("utf-8")
    if len(encoded) <= MAX_WS_CLOSE_REASON_BYTES:
        return reason
    return encoded[:MAX_WS_CLOSE_REASON_BYTES].decode("utf-8", errors="ignore")


# ── Health endpoint ────────────────────────────────────


@app.get("/health")
def health() -> dict[str, Any]:
    """Return service status and configured model info.

    Returns:
        JSON with ``status``, ``models_loaded``, and ``version``.
    """
    return {
        "status": "ok",
        "models_loaded": [_model_label()],
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
            display_name=_model_label(),
            threshold=_threshold(),
            custom_model_path=_custom_model_path(),
        )
    except ValueError as exc:
        logger.error("Failed to create detector: %s", exc)
        await websocket.close(code=1008, reason=_safe_close_reason(str(exc)))
        return

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                logger.info("WebSocket disconnected: %s", websocket.client)
                break

            # Frontend sends JSON control messages (e.g. sensitivity).
            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.debug("Ignoring non-JSON text websocket message")
                    continue

                if payload.get("command") == "set_sensitivity":
                    logger.debug("Sensitivity update received and ignored")
                    continue
                logger.debug("Ignoring unsupported websocket command: %s", payload)
                continue

            pcm_frame = message.get("bytes")
            if not pcm_frame:
                continue

            event = detector.process_audio(pcm_frame)
            if event is not None:
                await websocket.send_json(asdict(event))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", websocket.client)
    finally:
        detector.close()
