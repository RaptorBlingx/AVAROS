"""Bounded post-wake utterance capture for 16 kHz PCM streams.

The wake phrase is handled by openWakeWord.  This module starts a fresh,
language-neutral capture window after detection and uses an adaptive energy
gate to find speech onset and end-of-utterance silence.  It deliberately does
not inspect words, so the wake phrase cannot bias the request language.
"""

from __future__ import annotations

import math
import os
from collections import deque
from dataclasses import dataclass
from enum import Enum

import numpy as np

SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2


class CaptureStatus(str, Enum):
    COMPLETE = "complete"
    SILENCE_TIMEOUT = "silence_timeout"
    MAX_DURATION = "max_duration"


@dataclass(frozen=True)
class CaptureResult:
    status: CaptureStatus
    pcm: bytes = b""


@dataclass(frozen=True)
class CaptureConfig:
    start_timeout_ms: int = 6_000
    max_duration_ms: int = 15_000
    end_silence_ms: int = 800
    min_speech_ms: int = 240
    wake_tail_ms: int = 240
    pre_roll_ms: int = 240
    energy_floor: float = 300.0
    energy_ratio: float = 2.5
    onset_frames: int = 2

    @classmethod
    def from_env(cls) -> CaptureConfig:
        return cls(
            start_timeout_ms=_env_int(
                "UTTERANCE_START_TIMEOUT_MS", 6_000, 1_000, 15_000
            ),
            max_duration_ms=_env_int(
                "UTTERANCE_MAX_DURATION_MS", 15_000, 2_000, 30_000
            ),
            end_silence_ms=_env_int("UTTERANCE_END_SILENCE_MS", 800, 300, 3_000),
            min_speech_ms=_env_int("UTTERANCE_MIN_SPEECH_MS", 240, 80, 2_000),
            wake_tail_ms=_env_int("UTTERANCE_WAKE_TAIL_MS", 240, 0, 1_000),
            pre_roll_ms=_env_int("UTTERANCE_PRE_ROLL_MS", 240, 0, 1_000),
            energy_floor=_env_float("UTTERANCE_ENERGY_FLOOR", 300.0, 50.0, 5_000.0),
            energy_ratio=_env_float("UTTERANCE_ENERGY_RATIO", 2.5, 1.2, 10.0),
            onset_frames=_env_int("UTTERANCE_ONSET_FRAMES", 2, 1, 10),
        )


class UtteranceCapture:
    """Stateful VAD/endpointer for audio immediately following a wake event."""

    def __init__(self, config: CaptureConfig | None = None) -> None:
        self.config = config or CaptureConfig.from_env()
        self.total_samples = 0
        self.wake_tail_samples = _samples(self.config.wake_tail_ms)
        self.start_timeout_samples = _samples(self.config.start_timeout_ms)
        self.max_samples = _samples(self.config.max_duration_ms)
        self.end_silence_samples = _samples(self.config.end_silence_ms)
        self.min_speech_samples = _samples(self.config.min_speech_ms)
        self.pre_roll_samples = _samples(self.config.pre_roll_ms)
        self.noise_rms = max(1.0, self.config.energy_floor / self.config.energy_ratio)
        self.onset_count = 0
        self.started = False
        self.speech_samples = 0
        self.trailing_silence_samples = 0
        self.pre_roll: deque[bytes] = deque()
        self.pre_roll_size = 0
        self.captured = bytearray()

    def process_audio(self, pcm: bytes) -> CaptureResult | None:
        if not pcm:
            return None
        # Ignore an odd trailing byte rather than interpreting a partial sample.
        pcm = pcm[: len(pcm) - (len(pcm) % BYTES_PER_SAMPLE)]
        if not pcm:
            return None
        sample_count = len(pcm) // BYTES_PER_SAMPLE
        self.total_samples += sample_count

        if self.total_samples <= self.wake_tail_samples:
            return None

        rms = _rms(pcm)
        threshold = max(
            self.config.energy_floor,
            self.noise_rms * self.config.energy_ratio,
        )
        voiced = rms >= threshold

        if not self.started:
            self._append_pre_roll(pcm, sample_count)
            if voiced:
                self.onset_count += 1
            else:
                self.onset_count = 0
                # Slowly adapt only from non-voice frames.
                self.noise_rms = (self.noise_rms * 0.9) + (rms * 0.1)

            if self.onset_count >= self.config.onset_frames:
                self.started = True
                self.captured.extend(b"".join(self.pre_roll))
                self.speech_samples = self.pre_roll_size
                self.trailing_silence_samples = 0
                return None

            if self.total_samples >= self.start_timeout_samples:
                return CaptureResult(CaptureStatus.SILENCE_TIMEOUT)
            return None

        self.captured.extend(pcm)
        if voiced:
            self.speech_samples += sample_count
            self.trailing_silence_samples = 0
        else:
            self.trailing_silence_samples += sample_count

        if self.total_samples >= self.max_samples:
            return CaptureResult(CaptureStatus.MAX_DURATION, bytes(self.captured))
        if (
            self.speech_samples >= self.min_speech_samples
            and self.trailing_silence_samples >= self.end_silence_samples
        ):
            return CaptureResult(CaptureStatus.COMPLETE, bytes(self.captured))
        return None

    def _append_pre_roll(self, pcm: bytes, sample_count: int) -> None:
        if self.pre_roll_samples <= 0:
            return
        self.pre_roll.append(pcm)
        self.pre_roll_size += sample_count
        while self.pre_roll and self.pre_roll_size > self.pre_roll_samples:
            removed = self.pre_roll.popleft()
            self.pre_roll_size -= len(removed) // BYTES_PER_SAMPLE


def _rms(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return math.sqrt(float(np.mean(samples * samples)))


def _samples(milliseconds: int) -> int:
    return int(SAMPLE_RATE * milliseconds / 1_000)


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
