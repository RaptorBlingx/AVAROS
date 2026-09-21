"""Bounded, local post-wake utterance capture at 16 kHz.

The wake phrase is handled by openWakeWord. This module begins after the
widget has played its readiness acknowledgement, then uses the Silero VAD
already shipped with openWakeWord. It never inspects words, so the wake phrase
cannot influence request-language detection.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np

SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2
VAD_FRAME_SAMPLES = 480  # Silero's native 30 ms frame at 16 kHz.
VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * BYTES_PER_SAMPLE


class CaptureStatus(str, Enum):
    COMPLETE = "complete"
    SILENCE_TIMEOUT = "silence_timeout"
    MAX_DURATION = "max_duration"


@dataclass(frozen=True)
class CaptureDiagnostics:
    """Non-content timing and VAD measurements suitable for service logs."""

    duration_ms: int
    speech_ms: int
    last_speech_ms: int
    last_speech_probability: float
    trailing_silence_ms: int
    trailing_max_voice_probability: float
    max_voice_probability: float
    last_voice_probability: float


@dataclass(frozen=True)
class CaptureResult:
    status: CaptureStatus
    pcm: bytes = b""
    diagnostics: CaptureDiagnostics | None = None


@dataclass(frozen=True)
class CaptureConfig:
    # These match the prior widget's 10-second command window, while allowing
    # normal pauses after the acknowledgement and inside a request.
    start_timeout_ms: int = 10_000
    max_duration_ms: int = 20_000
    end_silence_ms: int = 1_200
    min_speech_ms: int = 240
    wake_tail_ms: int = 0
    pre_roll_ms: int = 240
    speech_start_probability: float = 0.55
    onset_frames: int = 2

    @classmethod
    def from_env(cls) -> "CaptureConfig":
        return cls(
            start_timeout_ms=_env_int("UTTERANCE_START_TIMEOUT_MS", 10_000, 1_000, 20_000),
            max_duration_ms=_env_int("UTTERANCE_MAX_DURATION_MS", 20_000, 2_000, 30_000),
            end_silence_ms=_env_int("UTTERANCE_END_SILENCE_MS", 1_200, 300, 3_000),
            min_speech_ms=_env_int("UTTERANCE_MIN_SPEECH_MS", 240, 80, 2_000),
            wake_tail_ms=_env_int("UTTERANCE_WAKE_TAIL_MS", 0, 0, 1_000),
            pre_roll_ms=_env_int("UTTERANCE_PRE_ROLL_MS", 240, 0, 1_000),
            speech_start_probability=_env_float("UTTERANCE_SPEECH_START_PROBABILITY", 0.55, 0.1, 0.95),
            onset_frames=_env_int("UTTERANCE_ONSET_FRAMES", 2, 1, 10),
        )


class SileroVoiceActivityDetector:
    """Small adapter around openWakeWord's bundled local Silero VAD."""

    def __init__(self) -> None:
        # openWakeWord already depends on onnxruntime and installs this model;
        # do not add another VAD service, model download, or browser path.
        from openwakeword.vad import VAD

        self._vad = VAD(n_threads=1)

    def __call__(self, samples: np.ndarray) -> float:
        return float(self._vad.predict(samples, frame_size=VAD_FRAME_SAMPLES))


class UtteranceCapture:
    """Stateful local VAD/endpointer for an acknowledged post-wake request."""

    def __init__(
        self,
        config: CaptureConfig | None = None,
        *,
        voice_probability: Callable[[np.ndarray], float] | None = None,
    ) -> None:
        self.config = config or CaptureConfig.from_env()
        self._voice_probability = voice_probability or SileroVoiceActivityDetector()
        self.total_samples = 0
        self.wake_tail_samples = _samples(self.config.wake_tail_ms)
        self.start_timeout_samples = _samples(self.config.start_timeout_ms)
        self.max_samples = _samples(self.config.max_duration_ms)
        self.end_silence_samples = _samples(self.config.end_silence_ms)
        self.min_speech_samples = _samples(self.config.min_speech_ms)
        self.pre_roll_samples = _samples(self.config.pre_roll_ms)
        self.onset_count = 0
        self.started = False
        self.speech_samples = 0
        self.last_speech_samples = 0
        self.last_speech_probability = 0.0
        self.trailing_silence_samples = 0
        self.trailing_max_voice_probability = 0.0
        self.pre_roll: deque[bytes] = deque()
        self.pre_roll_size = 0
        self.captured = bytearray()
        self._pending_pcm = bytearray()
        self._max_voice_probability = 0.0
        self._last_voice_probability = 0.0

    def process_audio(self, pcm: bytes) -> CaptureResult | None:
        if not pcm:
            return None
        self._pending_pcm.extend(pcm[: len(pcm) - (len(pcm) % BYTES_PER_SAMPLE)])
        while len(self._pending_pcm) >= VAD_FRAME_BYTES:
            frame = bytes(self._pending_pcm[:VAD_FRAME_BYTES])
            del self._pending_pcm[:VAD_FRAME_BYTES]
            result = self._process_frame(frame)
            if result is not None:
                return result
        return None

    def _process_frame(self, pcm: bytes) -> CaptureResult | None:
        self.total_samples += VAD_FRAME_SAMPLES
        if self.total_samples <= self.wake_tail_samples:
            return None

        samples = np.frombuffer(pcm, dtype=np.int16)
        probability = max(0.0, min(1.0, self._voice_probability(samples)))
        self._last_voice_probability = probability
        self._max_voice_probability = max(self._max_voice_probability, probability)
        # A single semantic voice threshold is deliberately used for both
        # onset and endpointing. The earlier 0.35 continuation threshold
        # allowed weak non-speech posterior values to reset silence forever.
        # Natural pauses remain protected by end_silence_ms, not by treating
        # uncertain audio as continuing speech.
        voiced = probability >= self.config.speech_start_probability

        if not self.started:
            self._append_pre_roll(pcm)
            self.onset_count = self.onset_count + 1 if voiced else 0
            if self.onset_count >= self.config.onset_frames:
                self.started = True
                self.captured.extend(b"".join(self.pre_roll))
                self.speech_samples = self.pre_roll_size
                self.last_speech_samples = self.total_samples
                self.last_speech_probability = probability
                self.trailing_silence_samples = 0
                self.trailing_max_voice_probability = 0.0
                return None
            if self.total_samples >= self.start_timeout_samples:
                return CaptureResult(CaptureStatus.SILENCE_TIMEOUT, diagnostics=self.diagnostics())
            return None

        self.captured.extend(pcm)
        if voiced:
            self.speech_samples += VAD_FRAME_SAMPLES
            self.last_speech_samples = self.total_samples
            self.last_speech_probability = probability
            self.trailing_silence_samples = 0
            self.trailing_max_voice_probability = 0.0
        else:
            self.trailing_silence_samples += VAD_FRAME_SAMPLES
            self.trailing_max_voice_probability = max(
                self.trailing_max_voice_probability,
                probability,
            )

        if self.total_samples >= self.max_samples:
            return CaptureResult(CaptureStatus.MAX_DURATION, bytes(self.captured), self.diagnostics())
        if self.speech_samples >= self.min_speech_samples and self.trailing_silence_samples >= self.end_silence_samples:
            return CaptureResult(CaptureStatus.COMPLETE, bytes(self.captured), self.diagnostics())
        return None

    def diagnostics(self) -> CaptureDiagnostics:
        return CaptureDiagnostics(
            duration_ms=_milliseconds(self.total_samples),
            speech_ms=_milliseconds(self.speech_samples),
            last_speech_ms=_milliseconds(self.last_speech_samples),
            last_speech_probability=round(self.last_speech_probability, 3),
            trailing_silence_ms=_milliseconds(self.trailing_silence_samples),
            trailing_max_voice_probability=round(
                self.trailing_max_voice_probability,
                3,
            ),
            max_voice_probability=round(self._max_voice_probability, 3),
            last_voice_probability=round(self._last_voice_probability, 3),
        )

    def _append_pre_roll(self, pcm: bytes) -> None:
        if self.pre_roll_samples <= 0:
            return
        self.pre_roll.append(pcm)
        self.pre_roll_size += VAD_FRAME_SAMPLES
        while self.pre_roll and self.pre_roll_size > self.pre_roll_samples:
            self.pre_roll.popleft()
            self.pre_roll_size -= VAD_FRAME_SAMPLES


def _samples(milliseconds: int) -> int:
    return int(SAMPLE_RATE * milliseconds / 1_000)


def _milliseconds(samples: int) -> int:
    return int(samples * 1_000 / SAMPLE_RATE)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))
