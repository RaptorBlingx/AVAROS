"""Local multilingual transcription through a pinned whisper.cpp binary."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

try:
    from .utterance import SAMPLE_RATE
except ImportError:  # container imports main.py as a top-level module
    from utterance import SAMPLE_RATE  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

_LANGUAGE_RE = re.compile(
    r"auto-detected language:\s*([a-z]{2,3})\s*\(p\s*=\s*([0-9.]+)\)",
    re.IGNORECASE,
)
_LANGUAGE_MAP = {"en": "en-US", "tr": "tr-TR"}


class TranscriptionError(RuntimeError):
    """A safe, classified local-ASR failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    language_confidence: float


class LocalWhisperTranscriber:
    """Run one bounded whisper.cpp transcription at a time.

    Serializing inference prevents concurrent browser sessions from exhausting
    the small demo host. Audio lives only in a private temporary directory and
    is removed as soon as the subprocess finishes.
    """

    _inference_lock = threading.Lock()

    def __init__(self) -> None:
        self.executable = os.environ.get(
            "ASR_WHISPER_EXECUTABLE",
            "/usr/local/bin/whisper-cli",
        )
        self.model_path = os.environ.get(
            "ASR_WHISPER_MODEL_PATH",
            "/app/asr-models/ggml-base-q5_1.bin",
        )
        self.threads = _env_int("ASR_THREADS", 2, 1, 4)
        self.timeout_seconds = _env_int("ASR_TIMEOUT_SECONDS", 20, 5, 60)
        self.min_language_confidence = _env_float(
            "ASR_MIN_LANGUAGE_CONFIDENCE", 0.55, 0.0, 1.0
        )

    @property
    def available(self) -> bool:
        return Path(self.executable).is_file() and Path(self.model_path).is_file()

    def transcribe(self, pcm: bytes) -> TranscriptionResult:
        if not self.available:
            raise TranscriptionError("asr_unavailable")
        if not pcm:
            raise TranscriptionError("no_speech")

        with self._inference_lock, tempfile.TemporaryDirectory(
            prefix="avaros-asr-"
        ) as directory:
            root = Path(directory)
            wav_path = root / "utterance.wav"
            output_path = root / "result"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(pcm)

            command = [
                self.executable,
                "-m",
                self.model_path,
                "-f",
                str(wav_path),
                "-l",
                "auto",
                "-t",
                str(self.threads),
                "-nt",
                "-oj",
                "-of",
                str(output_path),
                "-bs",
                "1",
                "-bo",
                "1",
                "-nf",
                "-sns",
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise TranscriptionError("asr_timeout") from exc
            except OSError as exc:
                logger.warning("Local ASR process could not start: %s", exc)
                raise TranscriptionError("asr_unavailable") from exc

            if completed.returncode != 0:
                logger.warning(
                    "Local ASR failed with exit code %d",
                    completed.returncode,
                )
                raise TranscriptionError("asr_failed")

            try:
                payload = json.loads(output_path.with_suffix(".json").read_text())
                detected = str(payload["result"]["language"]).lower()
                text = " ".join(
                    str(segment.get("text", "")).strip()
                    for segment in payload.get("transcription", [])
                    if str(segment.get("text", "")).strip()
                ).strip()
            except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise TranscriptionError("asr_failed") from exc

            probability_match = _LANGUAGE_RE.search(completed.stderr)
            confidence = (
                float(probability_match.group(2))
                if probability_match and probability_match.group(1).lower() == detected
                else 0.0
            )
            language = _LANGUAGE_MAP.get(detected)
            if language is None or confidence < self.min_language_confidence:
                raise TranscriptionError("language_ambiguous")
            if not text:
                raise TranscriptionError("no_speech")
            return TranscriptionResult(text, language, confidence)


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
