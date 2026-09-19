"""Tests for post-wake VAD and bounded utterance capture."""

from __future__ import annotations

import numpy as np

from services.wakeword.utterance import (
    CaptureConfig,
    CaptureStatus,
    UtteranceCapture,
)


def _frame(amplitude: int, milliseconds: int = 80) -> bytes:
    sample_count = 16_000 * milliseconds // 1_000
    return np.full(sample_count, amplitude, dtype=np.int16).tobytes()


def test_capture_ends_after_post_speech_silence() -> None:
    capture = UtteranceCapture(
        CaptureConfig(
            wake_tail_ms=0,
            pre_roll_ms=160,
            onset_frames=2,
            min_speech_ms=160,
            end_silence_ms=240,
            start_timeout_ms=2_000,
            max_duration_ms=5_000,
        )
    )

    assert capture.process_audio(_frame(2_000)) is None
    assert capture.process_audio(_frame(2_000)) is None
    assert capture.process_audio(_frame(2_000)) is None
    assert capture.process_audio(_frame(0)) is None
    assert capture.process_audio(_frame(0)) is None
    result = capture.process_audio(_frame(0))

    assert result is not None
    assert result.status == CaptureStatus.COMPLETE
    assert len(result.pcm) > 0


def test_capture_times_out_when_no_request_follows_wake_word() -> None:
    capture = UtteranceCapture(
        CaptureConfig(
            wake_tail_ms=0,
            start_timeout_ms=1_000,
            max_duration_ms=5_000,
        )
    )

    result = None
    for _ in range(13):
        result = capture.process_audio(_frame(0))
        if result is not None:
            break

    assert result is not None
    assert result.status == CaptureStatus.SILENCE_TIMEOUT
    assert result.pcm == b""


def test_wake_tail_is_not_included_in_request_audio() -> None:
    capture = UtteranceCapture(
        CaptureConfig(
            wake_tail_ms=240,
            pre_roll_ms=160,
            onset_frames=2,
            min_speech_ms=160,
            end_silence_ms=240,
            start_timeout_ms=2_000,
            max_duration_ms=5_000,
        )
    )

    for _ in range(3):
        assert capture.process_audio(_frame(9_000)) is None
    assert capture.process_audio(_frame(2_000)) is None
    assert capture.process_audio(_frame(2_000)) is None
    assert capture.process_audio(_frame(0)) is None
    assert capture.process_audio(_frame(0)) is None
    result = capture.process_audio(_frame(0))

    assert result is not None
    samples = np.frombuffer(result.pcm, dtype=np.int16)
    assert 9_000 not in samples

