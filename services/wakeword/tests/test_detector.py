"""Unit tests for ``WakeWordDetector``.

Uses the real openWakeWord library where possible (silence test) and a
mock ``Model`` for deterministic detection tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.wakeword.detector import (
    BYTES_PER_FRAME,
    DEFAULT_CONFIRMATION_FRAMES,
    DetectionEvent,
    WakeWordDetector,
    _ensure_openwakeword_assets,
    _resolve_model_path,
)


# ── Helpers ───────────────────────────────────────────────


def _silence_frame() -> bytes:
    """Return one 80 ms frame of silence (all zeros)."""
    return b"\x00" * BYTES_PER_FRAME


def _mock_oww_model(predict_key: str, score: float) -> MagicMock:
    """Build a mock that mimics ``openwakeword.model.Model``.

    If *score* is a single float the mock returns that value on
    every ``predict()`` call.  For variable-score sequences use
    ``_mock_oww_model_sequence`` instead.
    """
    mock = MagicMock()
    mock.predict.return_value = {predict_key: score}
    mock.models = {predict_key: MagicMock()}
    return mock


def _mock_oww_model_sequence(
    predict_key: str,
    scores: list[float],
) -> MagicMock:
    """Build a mock model that returns *scores* in order.

    After the sequence is exhausted the last value is repeated.
    """
    mock = MagicMock()
    remaining = list(scores)

    def _predict(_samples: object) -> dict[str, float]:
        value = remaining.pop(0) if remaining else scores[-1]
        return {predict_key: value}

    mock.predict.side_effect = _predict
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
            model="hey_avaros",
            score=0.95,
            timestamp="2026-03-04T12:00:00+00:00",
        )

        # Assert
        assert event.event == "detected"
        assert event.model == "hey_avaros"
        assert event.score == 0.95
        assert event.timestamp == "2026-03-04T12:00:00+00:00"

    def test_immutability_raises_frozen_error(self) -> None:
        """DetectionEvent rejects attribute mutation (DEC-004)."""
        # Arrange
        event = DetectionEvent(
            event="detected",
            model="hey_avaros",
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
        path = _resolve_model_path("alexa")

        # Assert
        assert path.endswith(".onnx") or path.endswith(".tflite")
        assert "alexa" in path

    def test_unknown_model_raises_value_error(self) -> None:
        """An unknown model name raises ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="not found"):
            _resolve_model_path("nonexistent_model_xyz")


class TestEnsureOpenWakewordAssets:
    """Tests for local cache model path resolution."""

    def test_downloads_model_when_missing(self) -> None:
        """Missing model file triggers an explicit download attempt."""
        with patch(
            "services.wakeword.detector._resolve_model_path",
            return_value="/pkg/resources/models/hey_jarvis_v0.1.tflite",
        ), patch(
            "services.wakeword.detector._ensure_preprocessing_assets",
        ), patch(
            "services.wakeword.detector.os.path.exists",
            side_effect=[False, True],
        ), patch(
            "openwakeword.utils.download_models",
        ) as mock_download:
            path = _ensure_openwakeword_assets("hey_jarvis")

        assert path == "/pkg/resources/models/hey_jarvis_v0.1.tflite"
        mock_download.assert_called_once_with(
            target_directory="/pkg/resources/models"
        )


# ── WakeWordDetector with mock model ─────────────────────


class TestDetectorWithMock:
    """Deterministic tests using an injected mock model."""

    def test_process_audio_detects_above_threshold(self) -> None:
        """Detection event returned after sustained above-threshold frames."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.92)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            _model=mock_model,
        )

        # Act — feed enough frames to satisfy confirmation window
        result = None
        for _ in range(DEFAULT_CONFIRMATION_FRAMES):
            result = detector.process_audio(_silence_frame())
            if result is not None:
                break

        # Assert
        assert result is not None
        assert isinstance(result, DetectionEvent)
        assert result.event == "detected"
        assert result.model == "hey_avaros"
        assert result.score == 0.92

    def test_process_audio_silent_below_threshold(self) -> None:
        """No event returned when score < threshold."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.1)
        detector = WakeWordDetector(
            model_name="hey_avaros",
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
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
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
        mock_model = _mock_oww_model("hey_avaros", score=0.92)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=1,
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
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            _model=mock_model,
        )

        # Act & Assert
        assert detector.loaded_models == ["hey_avaros"]

    def test_close_clears_buffer(self) -> None:
        """``close()`` resets internal state."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            _model=mock_model,
        )
        detector.process_audio(b"\x00" * 100)  # partial buffer

        # Act
        detector.close()

        # Assert
        assert len(detector._buffer) == 0
        assert detector._confirmation_count == 0


# ── WakeWordDetector with real openWakeWord ──────────────


class TestDetectorWithCustomPath:
    """Tests for custom model path loading."""

    def test_custom_path_calls_ensure_preprocessing_assets(self) -> None:
        """Custom path loading ensures preprocessing assets exist."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.88)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        # Act
        with patch("services.wakeword.detector._ensure_preprocessing_assets") as mock_preproc, \
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
        with patch("services.wakeword.detector._ensure_preprocessing_assets"), \
             patch("openwakeword.model.Model", mock_model_cls):
            detector = WakeWordDetector(
                model_name="hey_avaros",
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Assert — first attempt uses wakeword_models=[path] with ONNX framework.
        mock_model_cls.assert_called_once()
        kwargs = mock_model_cls.call_args.kwargs
        assert kwargs["wakeword_models"] == ["/app/models/hey_avaros.onnx"]
        assert kwargs["inference_framework"] == "onnx"
        detector.close()

    def test_custom_path_detector_processes_audio(self) -> None:
        """Detector with custom path produces detection events."""
        # Arrange
        mock_model_instance = _mock_oww_model("hey_avaros", score=0.88)
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        with patch("services.wakeword.detector._ensure_preprocessing_assets"), \
             patch("openwakeword.model.Model", mock_model_cls):
            detector = WakeWordDetector(
                model_name="hey_avaros",
                threshold=0.5,
                custom_model_path="/app/models/hey_avaros.onnx",
            )

        # Act — need DEFAULT_CONFIRMATION_FRAMES frames for detection
        result = None
        for _ in range(DEFAULT_CONFIRMATION_FRAMES):
            result = detector.process_audio(_silence_frame())
            if result is not None:
                break

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
        with patch("services.wakeword.detector._ensure_preprocessing_assets"), \
             patch("services.wakeword.detector._ensure_openwakeword_assets") as mock_oww, \
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
            model_name="alexa",
            threshold=0.5,
        )
        assert detector._predict_key.startswith("alexa")
        detector.close()


class TestDetectorWithRealModel:
    """Integration-style tests using the actual openWakeWord library."""

    def test_silence_produces_no_detection(self) -> None:
        """Ten frames of silence should not trigger a detection."""
        # Arrange
        detector = WakeWordDetector(
            model_name="alexa",
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
            model_name="alexa",
            threshold=0.5,
        )

        # Assert
        assert detector._predict_key.startswith("alexa")
        detector.close()


# ── Confirmation guard-rail tests ─────────────────────────


class TestConfirmationLogic:
    """Tests for multi-frame confirmation before detection."""

    def test_single_spike_does_not_trigger_detection(self) -> None:
        """One above-threshold frame followed by below-threshold is not detected."""
        # Arrange — spike then silence
        scores = [0.9, 0.1, 0.1, 0.1, 0.1]
        mock_model = _mock_oww_model_sequence("hey_avaros", scores)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=3,
            _model=mock_model,
        )

        # Act
        results = [
            detector.process_audio(_silence_frame()) for _ in range(len(scores))
        ]

        # Assert — no detection at all
        assert all(r is None for r in results)

    def test_sustained_frames_trigger_detection(self) -> None:
        """Three consecutive above-threshold frames trigger detection."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.85)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=3,
            _model=mock_model,
        )

        # Act
        r1 = detector.process_audio(_silence_frame())
        r2 = detector.process_audio(_silence_frame())
        r3 = detector.process_audio(_silence_frame())

        # Assert — first two build confirmation, third triggers
        assert r1 is None
        assert r2 is None
        assert r3 is not None
        assert r3.event == "detected"
        assert r3.score == 0.85

    def test_interrupted_confirmation_resets_counter(self) -> None:
        """A low-confidence frame resets the confirmation counter."""
        # Arrange — two high, one low, then three high → detect on 6th
        scores = [0.9, 0.9, 0.1, 0.9, 0.9, 0.9]
        mock_model = _mock_oww_model_sequence("hey_avaros", scores)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=3,
            _model=mock_model,
        )

        # Act
        results = [
            detector.process_audio(_silence_frame()) for _ in range(6)
        ]

        # Assert — only frame 6 (index 5) triggers detection
        assert results[:5] == [None, None, None, None, None]
        assert results[5] is not None
        assert results[5].event == "detected"

    def test_confirmation_frames_default_matches_constant(self) -> None:
        """Default confirmation_frames matches DEFAULT_CONFIRMATION_FRAMES."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            _model=mock_model,
        )

        # Assert
        assert detector._confirmation_required == DEFAULT_CONFIRMATION_FRAMES

    def test_confirmation_count_resets_after_detection(self) -> None:
        """After detection the counter resets so next detection needs full window."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.9)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=2,
            _model=mock_model,
        )

        # Act — first detection at frame 2
        r1 = detector.process_audio(_silence_frame())
        r2 = detector.process_audio(_silence_frame())
        assert r1 is None
        assert r2 is not None

        # Act — next detection needs another 2 frames
        r3 = detector.process_audio(_silence_frame())
        r4 = detector.process_audio(_silence_frame())
        assert r3 is None
        assert r4 is not None


# ── Runtime threshold update tests ────────────────────────


class TestThresholdUpdate:
    """Tests for ``update_threshold()`` runtime changes."""

    def test_update_threshold_changes_detection_gate(self) -> None:
        """Raising threshold prevents previously-detectable scores."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.6)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=1,
            _model=mock_model,
        )

        # Act — detects at threshold 0.5
        r1 = detector.process_audio(_silence_frame())
        assert r1 is not None

        # Act — raise threshold above model score
        detector.update_threshold(0.8)
        r2 = detector.process_audio(_silence_frame())

        # Assert
        assert r2 is None

    def test_update_threshold_clamps_to_safe_range(self) -> None:
        """Threshold is clamped to [MIN_THRESHOLD, MAX_THRESHOLD]."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            _model=mock_model,
        )

        # Act & Assert — below min
        detector.update_threshold(0.0)
        assert detector._threshold == 0.1

        # Act & Assert — above max
        detector.update_threshold(1.0)
        assert detector._threshold == 0.95

    def test_update_threshold_resets_confirmation(self) -> None:
        """Threshold change resets partial confirmation count."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.9)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            confirmation_frames=3,
            _model=mock_model,
        )

        # Act — accumulate 2 confirmations
        detector.process_audio(_silence_frame())
        detector.process_audio(_silence_frame())
        assert detector._confirmation_count == 2

        # Act — threshold change resets counter
        detector.update_threshold(0.6)
        assert detector._confirmation_count == 0


# ── Config info tests ─────────────────────────────────────


class TestConfigInfo:
    """Tests for ``config_info`` property."""

    def test_config_info_registry_mode(self) -> None:
        """Config info correctly reports registry mode."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            display_name="Hey AVAROS",
            threshold=0.7,
            confirmation_frames=5,
            _model=mock_model,
        )

        # Act
        info = detector.config_info

        # Assert
        assert info["model_label"] == "Hey AVAROS"
        assert info["model_name"] == "hey_avaros"
        assert info["mode"] == "registry"
        assert info["custom_model_path"] is None
        assert info["threshold"] == 0.7
        assert info["confirmation_frames"] == 5

    def test_config_info_custom_path_mode(self) -> None:
        """Config info correctly reports custom_path mode."""
        # Arrange
        mock_model = _mock_oww_model("hey_avaros", score=0.0)
        detector = WakeWordDetector(
            model_name="hey_avaros",
            threshold=0.5,
            custom_model_path="/app/models/hey_avaros.onnx",
            _model=mock_model,
        )

        # Act
        info = detector.config_info

        # Assert
        assert info["mode"] == "custom_path"
        assert info["custom_model_path"] == "/app/models/hey_avaros.onnx"
