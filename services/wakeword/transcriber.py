"""Local selected-language transcription through a pinned whisper.cpp binary."""

from __future__ import annotations

import json
import logging
import os
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

_WHISPER_LANGUAGE = {"en-US": "en", "tr-TR": "tr"}


class TranscriptionError(RuntimeError):
    """A safe, classified local-ASR failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str


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

    @property
    def available(self) -> bool:
        return Path(self.executable).is_file() and Path(self.model_path).is_file()

    def transcribe(self, pcm: bytes, language: str) -> TranscriptionResult:
        if not self.available:
            raise TranscriptionError("asr_unavailable")
        if not pcm:
            raise TranscriptionError("no_speech")
        whisper_language = _WHISPER_LANGUAGE.get(language)
        if whisper_language is None:
            raise TranscriptionError("language_invalid")

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
                whisper_language,
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
                text = " ".join(
                    str(segment.get("text", "")).strip()
                    for segment in payload.get("transcription", [])
                    if str(segment.get("text", "")).strip()
                ).strip()
            except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise TranscriptionError("asr_failed") from exc

            if not text:
                raise TranscriptionError("no_speech")
            return TranscriptionResult(text, language)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))
