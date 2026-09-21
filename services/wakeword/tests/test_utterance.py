"""Tests for the acknowledged post-wake VAD/endpointer."""

from __future__ import annotations

import numpy as np

from services.wakeword.utterance import (
    CaptureConfig,
    CaptureStatus,
    UtteranceCapture,
)


def _frame(amplitude: int, milliseconds: int = 30) -> bytes:
    sample_count = 16_000 * milliseconds // 1_000
    return np.full(sample_count, amplitude, dtype=np.int16).tobytes()


def _vad_for_amplitude(samples: np.ndarray) -> float:
    return 0.9 if int(np.max(np.abs(samples))) > 0 else 0.05


def _capture(**overrides: int | float) -> UtteranceCapture:
    values: dict[str, int | float] = {
        "pre_roll_ms": 120,
        "onset_frames": 2,
        "min_speech_ms": 120,
        "end_silence_ms": 240,
        "start_timeout_ms": 2_000,
        "max_duration_ms": 5_000,
    }
    values.update(overrides)
    config = CaptureConfig(**values)  # type: ignore[arg-type]
    return UtteranceCapture(config, voice_probability=_vad_for_amplitude)


def test_capture_ends_after_post_speech_silence() -> None:
    capture = _capture()

    for _ in range(8):
        assert capture.process_audio(_frame(2_000)) is None
    result = None
    for _ in range(8):
        result = capture.process_audio(_frame(0))
        if result is not None:
            break

    assert result is not None
    assert result.status == CaptureStatus.COMPLETE
    assert len(result.pcm) > 0
    assert result.diagnostics is not None
    assert result.diagnostics.max_voice_probability == 0.9


def test_capture_allows_short_pause_inside_a_request() -> None:
    capture = _capture(end_silence_ms=300)

    for _ in range(6):
        assert capture.process_audio(_frame(2_000)) is None
    # 180 ms is a natural internal pause, below the 300 ms endpoint.
    for _ in range(6):
        assert capture.process_audio(_frame(0)) is None
    for _ in range(5):
        assert capture.process_audio(_frame(2_000)) is None

    result = None
    for _ in range(10):
        result = capture.process_audio(_frame(0))
        if result is not None:
            break
    assert result is not None
    assert result.status == CaptureStatus.COMPLETE


def test_capture_times_out_when_no_request_follows_readiness() -> None:
    capture = _capture(start_timeout_ms=300)

    result = None
    for _ in range(11):
        result = capture.process_audio(_frame(0))
        if result is not None:
            break

    assert result is not None
    assert result.status == CaptureStatus.SILENCE_TIMEOUT
    assert result.pcm == b""


def test_wake_tail_is_not_included_when_compatibility_tail_is_requested() -> None:
    capture = _capture(wake_tail_ms=90)

    for _ in range(3):
        assert capture.process_audio(_frame(9_000)) is None
    for _ in range(6):
        assert capture.process_audio(_frame(2_000)) is None
    result = None
    for _ in range(10):
        result = capture.process_audio(_frame(0))
        if result is not None:
            break

    assert result is not None
    samples = np.frombuffer(result.pcm, dtype=np.int16)
    assert 9_000 not in samples
