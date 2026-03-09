"""Wake-word detector wrapping openWakeWord.

Loads a single pre-trained model by name, runs inference on raw
16 kHz signed-16-bit-LE PCM audio, and returns detection events
when the score exceeds a configurable threshold.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
_OWW_ASSETS_READY = False

# openWakeWord uses 80 ms internal frames (1280 samples @ 16 kHz).
# Each sample is 2 bytes (int16), so one frame = 2560 bytes on the wire.
SAMPLES_PER_FRAME = 1280
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2


@dataclass(frozen=True)
class DetectionEvent:
    """Immutable wake-word detection payload (DEC-004)."""

    event: str
    model: str
    score: float
    timestamp: str


# ── Model path resolution ────────────────────────────────


def _resolve_model_path(model_name: str) -> str:
    """Look up a pre-trained model path from the openWakeWord registry.

    Args:
        model_name: Clean model name, e.g. ``"hey_avaros"``.

    Returns:
        Absolute filesystem path to the configured model file.

    Raises:
        ValueError: If *model_name* is not in the registry.
    """
    import openwakeword  # deferred so unit tests don't need the lib

    # openwakeword API changed from `models` -> `MODELS` in newer releases.
    registry = getattr(openwakeword, "MODELS", None)
    if registry is None:
        registry = getattr(openwakeword, "models", None)
    if registry is None:
        raise ValueError(
            "openWakeWord model registry not found (expected MODELS/models)"
        )

    registry = dict(registry)
    if model_name not in registry:
        available = sorted(registry.keys())
        raise ValueError(
            f"Model '{model_name}' not found in openWakeWord registry. "
            f"Available: {available}"
        )
    return registry[model_name]["model_path"]


def _get_oww_resources_dir() -> str:
    """Return the directory containing openWakeWord model/asset files.

    Derives the path from the model registry so it matches the
    location where preprocessing assets are stored alongside models.

    Returns:
        Absolute path to the resources directory.
    """
    import openwakeword  # deferred so unit tests don't need the lib

    registry = getattr(openwakeword, "MODELS", None)
    if registry is None:
        registry = getattr(openwakeword, "models", None)
    if registry:
        registry = dict(registry)
        any_model = next(iter(registry.values()))
        return os.path.dirname(any_model["model_path"])

    # Fallback: package resources directory
    return os.path.join(os.path.dirname(openwakeword.__file__), "resources")


def _ensure_preprocessing_assets() -> None:
    """Download shared preprocessing models if missing.

    openWakeWord requires ``melspectrogram`` and ``embedding_model``
    for ALL models (including custom ones).  File extension varies
    by library version (``.onnx`` or ``.tflite``).

    Raises:
        ValueError: If download fails or assets are incomplete.
    """
    global _OWW_ASSETS_READY

    if _OWW_ASSETS_READY:
        return

    resources_dir = _get_oww_resources_dir()

    def _asset_exists(stem: str) -> bool:
        """Check if an asset exists in any supported format."""
        return any(
            os.path.exists(os.path.join(resources_dir, f"{stem}{ext}"))
            for ext in (".onnx", ".tflite")
        )

    if _asset_exists("melspectrogram") and _asset_exists("embedding_model"):
        _OWW_ASSETS_READY = True
        return

    logger.info("Downloading shared preprocessing assets to %s", resources_dir)

    try:
        from openwakeword.utils import download_models

        os.makedirs(resources_dir, exist_ok=True)
        download_models(target_directory=resources_dir)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Failed to download preprocessing assets: {exc}"
        ) from exc

    if not _asset_exists("melspectrogram") or not _asset_exists("embedding_model"):
        raise ValueError("Preprocessing assets incomplete after download")

    _OWW_ASSETS_READY = True


def _ensure_openwakeword_assets(model_name: str) -> str:
    """Ensure registry model and shared preprocessing assets exist.

    Args:
        model_name: Registry model name (e.g. ``"hey_avaros"``).

    Returns:
        Absolute filesystem path to the model file.

    Raises:
        ValueError: If model not in registry or download fails.
    """
    model_path = _resolve_model_path(model_name)
    _ensure_preprocessing_assets()

    if not os.path.exists(model_path):
        raise ValueError(f"Model file missing after download: {model_path}")

    return model_path


# ── Detector ─────────────────────────────────────────────


class WakeWordDetector:
    """Per-connection, stateful wake-word detector.

    Each WebSocket connection should create its own instance because the
    underlying openWakeWord ``Model`` accumulates audio state in its
    preprocessor (mel-spectrogram buffers, raw audio ring-buffer).
    Model load time is ~250 ms for a single model, which is acceptable.
    """

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        display_name: str | None = None,
        threshold: float = 0.5,
        *,
        custom_model_path: str | None = None,
        _model: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._display_name = display_name or model_name
        self._threshold = threshold
        self._buffer = bytearray()

        if _model is not None:
            # Test-injection path — skip openWakeWord import.
            self._oww = _model
            self._predict_key = model_name
        else:
            self._oww = self._load_model(model_name, custom_model_path)
            self._predict_key = self._resolve_predict_key()

        logger.info(
            "Detector ready: model=%s, display_name=%s, predict_key=%s, threshold=%.2f",
            self._model_name,
            self._display_name,
            self._predict_key,
            self._threshold,
        )

    # ── Public API ────────────────────────────────────

    def process_audio(self, pcm_bytes: bytes) -> DetectionEvent | None:
        """Buffer incoming PCM data, run inference, return detection or None.

        Args:
            pcm_bytes: Raw signed-16-bit-LE PCM at 16 kHz.

        Returns:
            A ``DetectionEvent`` if score ≥ threshold, else ``None``.
        """
        if not pcm_bytes:
            return None

        self._buffer.extend(pcm_bytes)

        # Feed complete frames to the model.
        while len(self._buffer) >= BYTES_PER_FRAME:
            chunk = bytes(self._buffer[:BYTES_PER_FRAME])
            del self._buffer[:BYTES_PER_FRAME]
            event = self._run_inference(chunk)
            if event is not None:
                return event
        return None

    @property
    def loaded_models(self) -> list[str]:
        """Return the list of actually-loaded model names."""
        return [self._model_name]

    def close(self) -> None:
        """Release per-connection state."""
        self._buffer.clear()

    # ── Internals ─────────────────────────────────────

    def _run_inference(self, chunk: bytes) -> DetectionEvent | None:
        """Convert PCM chunk to numpy, call predict, check threshold."""
        samples = np.frombuffer(chunk, dtype=np.int16)
        predictions: dict[str, Any] = self._oww.predict(samples)
        score = float(predictions.get(self._predict_key, 0.0))

        if score < self._threshold:
            return None

        return DetectionEvent(
            event="detected",
            model=self._display_name,
            score=round(score, 4),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _load_model(
        self, model_name: str, custom_model_path: str | None = None,
    ) -> Any:
        """Load an openWakeWord model by registry name or custom path.

        Args:
            model_name: Display name (used in logs and events).
            custom_model_path: Absolute path to a custom ``.onnx``/``.tflite``
                model file.  When set, bypasses registry lookup.

        Returns:
            An ``openwakeword.model.Model`` instance.

        Raises:
            ValueError: If the model cannot be loaded.
        """
        from openwakeword.model import Model

        if custom_model_path:
            _ensure_preprocessing_assets()
            model_path = custom_model_path
            logger.info(
                "Loading custom model: %s (%s)", model_name, custom_model_path,
            )
        else:
            model_path = _ensure_openwakeword_assets(model_name)
            logger.info(
                "Loading openWakeWord model: %s (%s)", model_name, model_path,
            )

        # Build ordered list of load attempts.
        # Newer openwakeword expects canonical model names; older variants
        # accepted custom file paths through a different kwarg.
        if custom_model_path:
            model_ext = os.path.splitext(model_path)[1].lower()
            framework: str | None = None
            if model_ext == ".onnx":
                framework = "onnx"
            elif model_ext == ".tflite":
                framework = "tflite"

            attempts: tuple[dict[str, list[str]], ...] = (
                {
                    "wakeword_models": [model_path],
                    **({"inference_framework": framework} if framework else {}),
                },
                {
                    "wakeword_model_paths": [model_path],
                    **({"inference_framework": framework} if framework else {}),
                },
                {"wakeword_models": [model_path]},
                {"wakeword_model_paths": [model_path]},
            )
        else:
            attempts = (
                {"wakeword_models": [model_name]},
                {"wakeword_models": [model_path]},
                {"wakeword_model_paths": [model_path]},
            )

        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                return Model(**kwargs)
            except (TypeError, ValueError) as exc:
                last_error = exc

        if last_error is not None:
            raise ValueError(str(last_error)) from last_error
        raise ValueError(f"Unable to load model '{model_name}'")

    def _resolve_predict_key(self) -> str:
        """Discover the actual dict key returned by ``predict()``.

        When loading via ``wakeword_model_paths``, the key includes a
        version suffix (e.g. ``hey_avaros_v0.1``).  We find it by
        matching the loaded ``models`` dict.
        """
        loaded_keys = list(self._oww.models.keys())
        if not loaded_keys:
            raise RuntimeError("openWakeWord loaded zero models")

        # Exact match first, then prefix match.
        for key in loaded_keys:
            if key == self._model_name:
                return key
        for key in loaded_keys:
            if key.startswith(self._model_name):
                return key

        # Fallback: use whatever was loaded.
        return loaded_keys[0]
