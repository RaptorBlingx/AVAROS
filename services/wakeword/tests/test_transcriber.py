"""Tests for the local whisper.cpp adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.wakeword.transcriber import LocalWhisperTranscriber, TranscriptionError


def _configured_transcriber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> LocalWhisperTranscriber:
    executable = tmp_path / "whisper-cli"
    model = tmp_path / "model.bin"
    executable.write_bytes(b"binary")
    model.write_bytes(b"model")
    monkeypatch.setenv("ASR_WHISPER_EXECUTABLE", str(executable))
    monkeypatch.setenv("ASR_WHISPER_MODEL_PATH", str(model))
    return LocalWhisperTranscriber()


def test_transcriber_returns_text_and_auto_detected_turkish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = _configured_transcriber(tmp_path, monkeypatch)

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        output = Path(command[command.index("-of") + 1]).with_suffix(".json")
        output.write_text(
            json.dumps(
                {
                    "result": {"language": "tr"},
                    "transcription": [{"text": " Geçen ay ne değişti?"}],
                }
            )
        )
        return SimpleNamespace(
            returncode=0,
            stderr="auto-detected language: tr (p = 0.9876)",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = transcriber.transcribe(b"\x00\x00" * 16_000)

    assert result.text == "Geçen ay ne değişti?"
    assert result.language == "tr-TR"
    assert result.language_confidence == pytest.approx(0.9876)


def test_transcriber_rejects_language_outside_english_and_turkish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = _configured_transcriber(tmp_path, monkeypatch)

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        output = Path(command[command.index("-of") + 1]).with_suffix(".json")
        output.write_text(
            json.dumps(
                {
                    "result": {"language": "de"},
                    "transcription": [{"text": "Eine Frage"}],
                }
            )
        )
        return SimpleNamespace(
            returncode=0,
            stderr="auto-detected language: de (p = 0.9000)",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(TranscriptionError, match="language_ambiguous"):
        transcriber.transcribe(b"\x00\x00" * 16_000)
