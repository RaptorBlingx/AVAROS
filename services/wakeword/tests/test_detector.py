"""Unit tests for ``WakeWordDetector``.

Uses the real openWakeWord library where possible (silence test) and a
mock ``Model`` for deterministic detection tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from detector import (
    BYTES_PER_FRAME,
    DetectionEvent,
    WakeWordDetector,
    _resolve_model_path,
)


# ── Helpers ───────────────────────────────────────────────


def _silence_frame() -> bytes:
    """Return one 80 ms frame of silence (all zeros)."""
    return b"\x00" * BYTES_PER_FRAME


def _mock_oww_model(predict_key: str, score: float) -> MagicMock:
    """Build a mock that mimics ``openwakeword.model.Model``."""
    mock = MagicMock()
    mock.predict.return_value = {predict_key: score}
    mock.models = {predict_key: MagicMock()}
    return mock


# ── DetectionEvent (frozen dataclass) ─────────────────────


class TestDetectionEvent:
    """DEC-004 compliance: DetectionEvent must be immutable."""

    def test_creation_returns_correct_fields(self) -> None:
        """DetectionEvent stores all fields correctly."""
        # Arrange
        event = DetectionEvent(
            event="detected",
            model="hey_jarvis",
            score=0.95,
            timestamp="2026-03-04T12:00:00+00:00",
        )

        # Assert
        assert event.event == "detected"
        assert event.model == "hey_jarvis"
        assert event.score == 0.95
        assert event.timestamp == "2026-03-04T12:00:00+00:00"

    def test_immutability_raises_frozen_error(self) -> None:
        """DetectionEvent rejects attribute mutation (DEC-004)."""
        # Arrange
        event = DetectionEvent(
            event="detected",
            model="hey_jarvis",
            score=0.95,
            timestamp="2026-03-04T12:00:00+00:00",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.score = 0.5  # type: ignore[misc]


# ── Model path resolution ────────────────────────────────


class TestResolveModelPath:
    """Tests for the ``_resolve_model_path`` helper."""

    def test_known_model_returns_path(self) -> None:
        """A model present in the registry resolves correctly."""
        # Arrange & Act
        path = _resolve_model_path("hey_jarvis")

        # Assert
        assert path.endswith(".onnx") or path.endswith(".tflite")
        assert "hey_jarvis" in path

    def test_unknown_model_raises_value_error(self) -> None:
        """An unknown model name raises ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="not found"):
            _resolve_model_path("nonexistent_model_xyz")


# ── WakeWordDetector with mock model ─────────────────────


class TestDetectorWithMock:
    """Deterministic tests using an injected mock model."""

    def test_process_audio_detects_above_threshold(self) -> None:
        """Detection event returned when score ≥ threshold."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.92)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )

        # Act
        result = detector.process_audio(_silence_frame())

        # Assert
        assert result is not None
        assert isinstance(result, DetectionEvent)
        assert result.event == "detected"
        assert result.model == "hey_jarvis"
        assert result.score == 0.92

    def test_process_audio_silent_below_threshold(self) -> None:
        """No event returned when score < threshold."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.1)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )

        # Act
        result = detector.process_audio(_silence_frame())

        # Assert
        assert result is None

    def test_process_audio_empty_bytes_returns_none(self) -> None:
        """Empty input produces no detection."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )

        # Act
        result = detector.process_audio(b"")

        # Assert
        assert result is None

    def test_process_audio_buffers_partial_frames(self) -> None:
        """Partial data is buffered; no inference until a full frame."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.92)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )
        half_frame = b"\x00" * (BYTES_PER_FRAME // 2)

        # Act — first half: no inference
        result1 = detector.process_audio(half_frame)

        # Assert
        assert result1 is None
        mock_model.predict.assert_not_called()

        # Act — second half completes the frame
        result2 = detector.process_audio(half_frame)

        # Assert
        assert result2 is not None
        mock_model.predict.assert_called_once()

    def test_loaded_models_returns_configured_name(self) -> None:
        """``loaded_models`` reports the canonical model name."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )

        # Act & Assert
        assert detector.loaded_models == ["hey_jarvis"]

    def test_close_clears_buffer(self) -> None:
        """``close()`` resets internal state."""
        # Arrange
        mock_model = _mock_oww_model("hey_jarvis", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            _model=mock_model,
        )
        detector.process_audio(b"\x00" * 100)  # partial buffer

        # Act
        detector.close()

        # Assert
        assert len(detector._buffer) == 0


# ── WakeWordDetector with real openWakeWord ──────────────


class TestDetectorWithCustomPath:
    """Tests for custom model path loading."""

    def test_custom_path_calls_ensure_preprocessing_assets(self) -> None:
        """Custom path loading ensures preprocessing assets exist."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.88)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        # Act
        with patch("detector._ensure_preprocessing_assets") as mock_preproc, \
             patch("openwakeword.model.Model", mock_model_cls):
            detector = WakeWordDetector(
                model_name="hey_avaros",
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Assert
        mock_preproc.assert_called_once()
        detector.close()

    def test_custom_path_loads_model_with_correct_path(self) -> None:
        """Custom path is passed to the Model constructor."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.88)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        # Act
        with patch("detector._ensure_preprocessing_assets"), \
             patch("openwakeword.model.Model", mock_model_cls):
            detector = WakeWordDetector(
                model_name="hey_avaros",
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Assert — first attempt uses wakeword_models=[path]
        mock_model_cls.assert_called_once_with(
            wakeword_models=["/app/models/hey_avaros.onnx"],
        )
        detector.close()

    def test_custom_path_detector_processes_audio(self) -> None:
        """Detector with custom path produces detection events."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.88)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        with patch("detector._ensure_preprocessing_assets"), \
             patch("openwakeword.model.Model", mock_model_cls):
            detector = WakeWordDetector(
                model_name="hey_avaros",
                threshold=0.5,
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Act
        result = detector.process_audio(_silence_frame())

        # Assert
        assert result is not None
        assert result.model == "hey_avaros"
        assert result.score == 0.88
        detector.close()

    def test_custom_path_skips_registry_lookup(self) -> None:
        """Custom path does not call _ensure_openwakeword_assets."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.0)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        # Act
        with patch("detector._ensure_preprocessing_assets"), \
             patch("detector._ensure_openwakeword_assets") as mock_oww, \
             patch("openwakeword.model.Model", mock_model_cls):
            WakeWordDetector(
                model_name="hey_avaros",
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Assert
        mock_oww.assert_not_called()

    def test_no_custom_path_uses_registry(self) -> None:
        """Without custom_model_path, registry loading is used."""
        # Arrange & Act & Assert — existing behavior still works
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
        )
        assert detector._predict_key.startswith("hey_jarvis")
        detector.close()


class TestDetectorWithRealModel:
    """Integration-style tests using the actual openWakeWord library."""

    def test_silence_produces_no_detection(self) -> None:
        """Ten frames of silence should not trigger a detection."""
        # Arrange
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
        )

        # Act — feed 10 frames of silence
        detections = []
        for _ in range(10):
            event = detector.process_audio(_silence_frame())
            if event is not None:
                detections.append(event)

        # Assert
        assert detections == []
        detector.close()

    def test_predict_key_resolved_correctly(self) -> None:
        """The detector resolves a predict key starting with the model name."""
        # Arrange & Act
        detector = WakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
        )

        # Assert
        assert detector._predict_key.startswith("hey_jarvis")
        detector.close()
