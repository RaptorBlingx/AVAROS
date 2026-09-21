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


def test_transcriber_passes_selected_turkish_to_whisper(
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
        assert command[command.index("-l") + 1] == "tr"
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = transcriber.transcribe(b"\x00\x00" * 16_000, "tr-TR")

    assert result.text == "Geçen ay ne değişti?"
    assert result.language == "tr-TR"


def test_transcriber_rejects_an_unsupported_selected_language(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = _configured_transcriber(tmp_path, monkeypatch)

    with pytest.raises(TranscriptionError, match="language_invalid"):
        transcriber.transcribe(b"\x00\x00" * 16_000, "de-DE")
