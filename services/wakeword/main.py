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
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if __package__:
    # Package import path (used by tests and repo-root execution).
    from .detector import (
        DEFAULT_CONFIRMATION_FRAMES,
        WakeWordDetector,
        _ensure_openwakeword_assets,
        _resolve_model_path,
    )
else:
    # Script-style import path (used by container CMD: uvicorn main:app).
    from detector import (  # type: ignore[no-redef]
        DEFAULT_CONFIRMATION_FRAMES,
        WakeWordDetector,
        _ensure_openwakeword_assets,
        _resolve_model_path,
    )

SERVICE_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("avaros-wakeword")

MAX_WS_CLOSE_REASON_BYTES = 120
_THRESHOLD_LOCK = threading.Lock()
_SESSION_THRESHOLDS: dict[str, float] = {}
_FALLBACK_MODEL_NAME = "hey_jarvis"


def _preload_registry_assets_enabled() -> bool:
    """Return whether registry model assets should be preloaded at startup."""
    raw = os.environ.get("WAKEWORD_PRELOAD_MODELS", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


# ── Startup validation ──────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ANN201
    """Validate model config on startup; no teardown needed."""
    configured_model = _model_name()
    custom_path = _custom_model_path()
    active_model = configured_model
    active_custom_path: str | None = None
    forced_fallback_model = False

    if custom_path:
        if os.path.isfile(custom_path):
            active_custom_path = custom_path
            logger.info(
                "Custom model validated: %s (label=%s)",
                active_custom_path,
                _model_label(
                    model_name=active_model,
                    custom_model_path=active_custom_path,
                ),
            )
        else:
            logger.warning(
                "WAKEWORD_MODEL_PATH='%s' does not exist; "
                "falling back to registry model '%s'.",
                custom_path,
                configured_model,
            )

    if active_custom_path is None:
        resolver = (
            _ensure_openwakeword_assets
            if _preload_registry_assets_enabled()
            else _resolve_model_path
        )
        try:
            resolver(active_model)
            logger.info(
                "Model '%s' validated in openWakeWord registry.",
                active_model,
            )
        except ValueError as exc:
            if active_model != _FALLBACK_MODEL_NAME:
                try:
                    resolver(_FALLBACK_MODEL_NAME)
                    logger.warning(
                        "Configured model '%s' is unavailable (%s); "
                        "falling back to '%s'.",
                        active_model,
                        exc,
                        _FALLBACK_MODEL_NAME,
                    )
                    active_model = _FALLBACK_MODEL_NAME
                    forced_fallback_model = True
                except ValueError as fallback_exc:
                    logger.critical(
                        "Startup validation failed: %s (fallback '%s' "
                        "also failed: %s)",
                        exc,
                        _FALLBACK_MODEL_NAME,
                        fallback_exc,
                    )
                    raise SystemExit(1) from fallback_exc
            else:
                logger.critical("Startup validation failed: %s", exc)
                raise SystemExit(1) from exc

    if forced_fallback_model:
        active_label = _FALLBACK_MODEL_NAME
    else:
        active_label = _model_label(
            model_name=active_model,
            custom_model_path=active_custom_path,
        )

    application.state.wakeword_model_name = active_model
    application.state.wakeword_model_label = active_label
    application.state.wakeword_custom_model_path = active_custom_path
    yield


app = FastAPI(title="avaros-wakeword", version=SERVICE_VERSION, lifespan=lifespan)


# ── Configuration helpers ──────────────────────────────


def _model_name() -> str:
    """Return the configured wake-word model name."""
    return os.environ.get("WAKEWORD_MODEL", "hey_avaros")


def _custom_model_path() -> str | None:
    """Return the custom model file path, or ``None`` for registry mode."""
    return os.environ.get("WAKEWORD_MODEL_PATH") or None


def _model_label(
    *,
    model_name: str | None = None,
    custom_model_path: str | None = None,
) -> str:
    """Return the display label for the active model.

    Priority: ``WAKEWORD_MODEL_LABEL`` env var > filename stem of
    ``WAKEWORD_MODEL_PATH`` > ``WAKEWORD_MODEL``.

    Returns:
        Human-readable model label.
    """
    label = os.environ.get("WAKEWORD_MODEL_LABEL")
    if label:
        return label
    custom_path = custom_model_path if custom_model_path is not None else _custom_model_path()
    if custom_path:
        return os.path.splitext(os.path.basename(custom_path))[0]
    return model_name or _model_name()


def _runtime_model_config(application: FastAPI) -> tuple[str, str, str | None]:
    """Return active model config, preferring startup-resolved state."""
    state = application.state
    if hasattr(state, "wakeword_model_name"):
        model_name = state.wakeword_model_name
        custom_model_path = state.wakeword_custom_model_path
        model_label = state.wakeword_model_label
        return model_name, model_label, custom_model_path

    model_name = _model_name()
    custom_model_path = _custom_model_path()
    if custom_model_path and not os.path.isfile(custom_model_path):
        custom_model_path = None
    model_label = _model_label(
        model_name=model_name,
        custom_model_path=custom_model_path,
    )
    return model_name, model_label, custom_model_path


def _threshold() -> float:
    """Return the configured detection threshold (0–1)."""
    raw = os.environ.get("WAKEWORD_THRESHOLD", "0.5")
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.5


def _confirmation_frames() -> int:
    """Return the required consecutive above-threshold frames.

    Configurable via ``WAKEWORD_CONFIRMATION_FRAMES``.
    Default: ``DEFAULT_CONFIRMATION_FRAMES`` (3 → 240 ms at 80 ms/frame).

    Returns:
        Positive integer ≥ 1.
    """
    raw = os.environ.get(
        "WAKEWORD_CONFIRMATION_FRAMES",
        str(DEFAULT_CONFIRMATION_FRAMES),
    )
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_CONFIRMATION_FRAMES


def _safe_close_reason(reason: str) -> str:
    """Return a WebSocket close reason that fits protocol limits."""
    encoded = reason.encode("utf-8")
    if len(encoded) <= MAX_WS_CLOSE_REASON_BYTES:
        return reason
    return encoded[:MAX_WS_CLOSE_REASON_BYTES].decode("utf-8", errors="ignore")


def _detector_threshold(detector: WakeWordDetector) -> float:
    """Read current threshold from detector runtime info.

    Falls back to env-configured threshold when detector metadata is
    unavailable (e.g. mocked tests).
    """
    info = getattr(detector, "config_info", None)
    if isinstance(info, dict):
        value = info.get("threshold")
        if isinstance(value, (int, float)):
            return float(value)
    return _threshold()


def _register_session(session_id: str, detector: WakeWordDetector) -> None:
    """Store runtime threshold for a new websocket session."""
    with _THRESHOLD_LOCK:
        _SESSION_THRESHOLDS[session_id] = _detector_threshold(detector)


def _update_session_threshold(session_id: str, detector: WakeWordDetector) -> None:
    """Update runtime threshold for an existing websocket session."""
    with _THRESHOLD_LOCK:
        _SESSION_THRESHOLDS[session_id] = _detector_threshold(detector)


def _unregister_session(session_id: str) -> None:
    """Remove runtime threshold for a closed websocket session."""
    with _THRESHOLD_LOCK:
        _SESSION_THRESHOLDS.pop(session_id, None)


def _active_session_thresholds() -> list[float]:
    """Return current runtime thresholds for all live websocket sessions."""
    with _THRESHOLD_LOCK:
        return [round(value, 4) for value in _SESSION_THRESHOLDS.values()]


# ── Health endpoint ────────────────────────────────────


@app.get("/health")
def health() -> dict[str, Any]:
    """Return service status and runtime configuration.

    Exposes enough metadata to verify which model artefact is active
    and whether runtime settings match expectations.  Does **not**
    expose secrets.

    Returns:
        JSON with ``status``, ``models_loaded``, ``version``,
        ``model_mode``, runtime threshold fields, and
        ``confirmation_frames``.
    """
    model_name, model_label, custom_model_path = _runtime_model_config(app)

    active_thresholds = _active_session_thresholds()
    configured_threshold = _threshold()

    if active_thresholds:
        threshold_min = min(active_thresholds)
        threshold_max = max(active_thresholds)
        threshold_avg = round(sum(active_thresholds) / len(active_thresholds), 4)
        threshold_source = "active_session_avg"
        runtime_threshold = threshold_avg
    else:
        threshold_min = configured_threshold
        threshold_max = configured_threshold
        threshold_avg = configured_threshold
        threshold_source = "configured"
        runtime_threshold = configured_threshold

    return {
        "status": "ok",
        "models_loaded": [model_label],
        "version": SERVICE_VERSION,
        "model_mode": "custom_path" if custom_model_path else "registry",
        "model_name": model_name,
        "configured_threshold": configured_threshold,
        "threshold": runtime_threshold,
        "threshold_source": threshold_source,
        "active_session_count": len(active_thresholds),
        "active_session_thresholds": active_thresholds,
        "active_session_threshold_min": threshold_min,
        "active_session_threshold_max": threshold_max,
        "active_session_threshold_avg": threshold_avg,
        "confirmation_frames": _confirmation_frames(),
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
    session_id = str(id(websocket))
    model_name, model_label, custom_model_path = _runtime_model_config(app)

    try:
        detector = WakeWordDetector(
            model_name=model_name,
            display_name=model_label,
            threshold=_threshold(),
            custom_model_path=custom_model_path,
            confirmation_frames=_confirmation_frames(),
        )
        _register_session(session_id, detector)
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

                command = payload.get("command")
                configured_floor = _threshold()
                if command == "set_sensitivity":
                    value = payload.get("value")
                    if isinstance(value, (int, float)):
                        # Sensitivity is inverted: higher sensitivity
                        # = easier to trigger = lower threshold.
                        new_threshold = 1.0 - float(value)
                        # Enforce server-configured floor — no client
                        # can push the threshold below the configured
                        # WAKEWORD_THRESHOLD.
                        if new_threshold < configured_floor:
                            logger.warning(
                                "Client requested threshold %.2f via "
                                "set_sensitivity(%.2f) but floor is %.2f; "
                                "clamping to floor.",
                                new_threshold,
                                float(value),
                                configured_floor,
                            )
                            new_threshold = configured_floor
                        detector.update_threshold(new_threshold)
                        _update_session_threshold(session_id, detector)
                        logger.info(
                            "Threshold set to %.2f via set_sensitivity(%.2f)",
                            new_threshold,
                            float(value),
                        )
                    continue
                if command == "set_threshold":
                    value = payload.get("value")
                    if isinstance(value, (int, float)):
                        new_threshold = float(value)
                        if new_threshold < configured_floor:
                            logger.warning(
                                "Client requested threshold %.2f via "
                                "set_threshold but floor is %.2f; "
                                "clamping to floor.",
                                new_threshold,
                                configured_floor,
                            )
                            new_threshold = configured_floor
                        detector.update_threshold(new_threshold)
                        _update_session_threshold(session_id, detector)
                        logger.info(
                            "Threshold set to %.2f via set_threshold",
                            new_threshold,
                        )
                    continue
                logger.debug("Ignoring unsupported websocket command: %s", payload)
                continue

            pcm_frame = message.get("bytes")
            if not pcm_frame:
                continue

            event = detector.process_audio(pcm_frame)
            if event is not None:
                logger.warning(
                    "DETECTION FIRED: model=%s score=%.4f session=%s",
                    event.model,
                    event.score,
                    session_id,
                )
                await websocket.send_json(asdict(event))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", websocket.client)
    finally:
        _unregister_session(session_id)
        detector.close()
