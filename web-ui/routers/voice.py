"""Voice configuration endpoints for HiveMind WebSocket bridge."""

from __future__ import annotations

import os
import logging
import shutil
import subprocess
import tempfile
import threading
import wave
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from config import (
    PIPER_CONFIG_PATH,
    PIPER_LENGTH_SCALE,
    PIPER_MODEL_PATH,
    PIPER_NOISE_SCALE,
    PIPER_NOISE_W_SCALE,
    SERVER_TTS_ENABLED,
    SERVER_TTS_ENGINE,
    SERVER_TTS_MAX_CHARS,
    SERVER_TTS_TIMEOUT_SECONDS,
)
from dependencies import get_settings_service
from schemas.voice import (
    VoiceConfigResponse,
    VoicePreferencesRequest,
    VoicePreferencesResponse,
)
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
public_router = APIRouter(tags=["voice"])
logger = logging.getLogger("uvicorn.error")

_CORS_TTS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
}
_CORS_PREF_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
}
_VOICE_MODE_SETTING_KEY = "voice_mode"
_DEFAULT_VOICE_MODE = "push-to-talk"
_VALID_VOICE_MODES = {"wake-word", "push-to-talk", "text"}
_PIPER_MAX_SYNTH_VOLUME = 0.72
_PIPER_OUTPUT_GAIN = 0.65
_PIPER_SENTENCE_SILENCE_SECONDS = 0.15
_PIPER_VOICE_LOCK = threading.Lock()
_PIPER_SYNTH_LOCK = threading.Lock()
_PIPER_VOICE: Any | None = None
_PIPER_VOICE_KEY: tuple[str, str | None] | None = None


class SpeechRequest(BaseModel):
    """Text-to-speech synthesis request."""

    text: str = Field(..., min_length=1, max_length=SERVER_TTS_MAX_CHARS)
    language: str = Field(default="en-US", max_length=20)
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.0, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Trim text while preserving normal spoken punctuation."""
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("text is required")
        return cleaned


def _first_header_value(value: str | None) -> str:
    """Return the first value from a potentially comma-separated proxy header."""
    return (value or "").split(",", maxsplit=1)[0].strip()


def _request_hivemind_url(request: Request) -> str:
    """Build a same-origin HiveMind WebSocket URL from the incoming request."""
    forwarded_proto = _first_header_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _first_header_value(request.headers.get("x-forwarded-host"))
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    proto = forwarded_proto or request.url.scheme
    ws_scheme = "wss" if proto in {"https", "wss"} else "ws"
    return f"{ws_scheme}://{host}/hivemind/"


def _resolve_hivemind_url(configured_url: str, request: Request) -> str:
    """Return the browser-facing HiveMind URL.

    ``HIVEMIND_WS_URL=auto`` lets one Docker image work behind any public
    hostname because the browser receives a WebSocket URL on the same origin
    it used to open AVAROS.
    """
    normalized = configured_url.strip()
    if normalized.lower() in {"", "auto", "same-origin", "same_origin"}:
        return _request_hivemind_url(request)

    parsed = urlparse(normalized)
    if parsed.path.endswith("/hivemind") and not normalized.endswith("/"):
        return f"{normalized}/"
    return normalized


def _get_voice_mode_preference(settings_service: SettingsService) -> str:
    raw = settings_service.get_setting(
        _VOICE_MODE_SETTING_KEY,
        _DEFAULT_VOICE_MODE,
    )
    value = str(raw).strip()
    if value in _VALID_VOICE_MODES:
        return value
    return _DEFAULT_VOICE_MODE


def _voice_preferences_response(
    settings_service: SettingsService,
) -> VoicePreferencesResponse:
    return VoicePreferencesResponse(
        voice_mode=_get_voice_mode_preference(settings_service),
    )


def _espeak_voice(language: str) -> str:
    """Map a BCP-47 language tag to an espeak-ng voice name."""
    normalized = language.strip().lower()
    if normalized.startswith("tr"):
        return "tr"
    if normalized.startswith("en-gb"):
        return "en-gb"
    if normalized.startswith("en"):
        return "en-us"
    return normalized or "en-us"


def _synthesize_wav_espeak(payload: SpeechRequest) -> bytes:
    """Generate WAV bytes with the local espeak-ng fallback engine."""
    engine = shutil.which("espeak-ng")
    if not engine:
        raise HTTPException(status_code=503, detail="Server TTS engine unavailable")

    fd, wav_path = tempfile.mkstemp(prefix="avaros-tts-", suffix=".wav")
    os.close(fd)
    path = Path(wav_path)
    speed = max(80, min(450, int(175 * payload.rate)))
    amplitude = max(0, min(200, int(200 * payload.volume)))
    pitch = max(0, min(99, int(50 * payload.pitch)))
    command = [
        engine,
        "-w",
        str(path),
        "-v",
        _espeak_voice(payload.language),
        "-s",
        str(speed),
        "-a",
        str(amplitude),
        "-p",
        str(pitch),
        "--stdin",
    ]

    try:
        subprocess.run(
            command,
            input=payload.text,
            text=True,
            capture_output=True,
            check=True,
            timeout=SERVER_TTS_TIMEOUT_SECONDS,
        )
        return path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Server TTS timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=503, detail="Server TTS failed") from exc
    finally:
        path.unlink(missing_ok=True)


def _piper_engine_path() -> str | None:
    """Return the Piper binary path when the voice model is available."""
    engine = shutil.which("piper")
    model_path = Path(PIPER_MODEL_PATH)
    if not engine or not model_path.exists():
        return None
    return engine


def _piper_model_paths() -> tuple[Path, Path | None]:
    """Return configured Piper model/config paths when the model exists."""
    model_path = Path(PIPER_MODEL_PATH)
    if not model_path.exists():
        raise HTTPException(status_code=503, detail="Piper TTS engine unavailable")
    config_path = Path(PIPER_CONFIG_PATH)
    return model_path, config_path if config_path.exists() else None


def _load_piper_voice() -> Any:
    """Load and cache the Piper voice model in-process."""
    global _PIPER_VOICE, _PIPER_VOICE_KEY

    model_path, config_path = _piper_model_paths()
    key = (str(model_path), str(config_path) if config_path else None)
    with _PIPER_VOICE_LOCK:
        if _PIPER_VOICE is not None and _PIPER_VOICE_KEY == key:
            return _PIPER_VOICE

        from piper import PiperVoice

        logger.info("Loading Piper voice model once: %s", model_path)
        _PIPER_VOICE = PiperVoice.load(
            model_path,
            config_path=config_path,
        )
        _PIPER_VOICE_KEY = key
        return _PIPER_VOICE


def preload_server_tts() -> None:
    """Warm the configured server TTS engine during app startup."""
    if not SERVER_TTS_ENABLED:
        return
    if SERVER_TTS_ENGINE not in {"", "auto", "piper"}:
        return
    try:
        _load_piper_voice()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Piper TTS preload skipped: %s", exc)


def _piper_synthesis_config(payload: SpeechRequest) -> Any:
    """Build Piper synthesis config from the public request payload."""
    from piper import SynthesisConfig

    length_scale = max(0.5, min(2.0, PIPER_LENGTH_SCALE / payload.rate))
    synth_volume = max(0.0, min(_PIPER_MAX_SYNTH_VOLUME, payload.volume))
    return SynthesisConfig(
        length_scale=length_scale,
        noise_scale=PIPER_NOISE_SCALE,
        noise_w_scale=PIPER_NOISE_W_SCALE,
        volume=synth_volume,
    )


def _wav_from_piper_chunks(chunks: list[Any]) -> bytes:
    """Package Piper AudioChunk objects into a single PCM WAV."""
    if not chunks:
        raise HTTPException(status_code=503, detail="Piper TTS produced no audio")

    sample_rate = int(chunks[0].sample_rate)
    sample_width = int(chunks[0].sample_width)
    channels = int(chunks[0].sample_channels)
    silence = b"\x00" * int(
        sample_rate
        * _PIPER_SENTENCE_SILENCE_SECONDS
        * sample_width
        * channels
    )
    target = BytesIO()
    with wave.open(target, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        for index, chunk in enumerate(chunks):
            writer.writeframes(chunk.audio_int16_bytes)
            if index < len(chunks) - 1 and silence:
                writer.writeframes(silence)
    return target.getvalue()


def _synthesize_wav_piper_in_process(payload: SpeechRequest) -> bytes:
    """Generate WAV bytes with a cached in-process Piper voice."""
    voice = _load_piper_voice()
    syn_config = _piper_synthesis_config(payload)
    with _PIPER_SYNTH_LOCK:
        chunks = list(voice.synthesize(payload.text, syn_config=syn_config))
    return _scale_wav(_wav_from_piper_chunks(chunks), _PIPER_OUTPUT_GAIN)


def _synthesize_wav_piper_cli(payload: SpeechRequest) -> bytes:
    """Generate WAV bytes by spawning Piper CLI as a compatibility fallback."""
    engine = _piper_engine_path()
    if not engine:
        raise HTTPException(status_code=503, detail="Piper TTS engine unavailable")

    fd, wav_path = tempfile.mkstemp(prefix="avaros-tts-", suffix=".wav")
    os.close(fd)
    path = Path(wav_path)
    model_path = Path(PIPER_MODEL_PATH)
    config_path = Path(PIPER_CONFIG_PATH)
    length_scale = max(0.5, min(2.0, PIPER_LENGTH_SCALE / payload.rate))
    # Keep the generated waveform below Piper's clipping edge; the browser
    # still applies the user's playback volume to the resulting page media.
    synth_volume = max(0.0, min(_PIPER_MAX_SYNTH_VOLUME, payload.volume))
    command = [
        engine,
        "-m",
        str(model_path),
        "-f",
        str(path),
        "--length-scale",
        f"{length_scale:.3f}",
        "--noise-scale",
        f"{PIPER_NOISE_SCALE:.3f}",
        "--noise-w-scale",
        f"{PIPER_NOISE_W_SCALE:.3f}",
        "--sentence-silence",
        "0.15",
        "--volume",
        f"{synth_volume:.3f}",
    ]
    if config_path.exists():
        command[3:3] = ["-c", str(config_path)]

    try:
        subprocess.run(
            command,
            input=f"{payload.text}\n",
            text=True,
            capture_output=True,
            check=True,
            timeout=SERVER_TTS_TIMEOUT_SECONDS,
        )
        return _scale_wav(path.read_bytes(), _PIPER_OUTPUT_GAIN)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Piper TTS timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=503, detail="Piper TTS failed") from exc
    finally:
        path.unlink(missing_ok=True)


def _synthesize_wav_piper(payload: SpeechRequest) -> bytes:
    """Generate WAV bytes with Piper for more natural meeting-share audio."""
    try:
        return _synthesize_wav_piper_in_process(payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("In-process Piper failed; falling back to CLI: %s", exc)
        return _synthesize_wav_piper_cli(payload)


def _scale_wav(wav_bytes: bytes, gain: float) -> bytes:
    """Return a PCM WAV with a conservative gain applied to every sample."""
    if gain >= 0.999:
        return wav_bytes
    source = BytesIO(wav_bytes)
    target = BytesIO()
    try:
        with wave.open(source, "rb") as reader:
            params = reader.getparams()
            frames = reader.readframes(reader.getnframes())
    except wave.Error:
        return wav_bytes
    if params.sampwidth != 2:
        return wav_bytes

    sample_count = len(frames) // params.sampwidth
    samples = memoryview(frames).cast("h")
    scaled = bytearray(len(frames))
    out_samples = memoryview(scaled).cast("h")
    for index in range(sample_count):
        value = int(samples[index] * gain)
        out_samples[index] = max(-32768, min(32767, value))

    with wave.open(target, "wb") as writer:
        writer.setparams(params)
        writer.writeframes(scaled)
    return target.getvalue()


def _synthesize_wav(payload: SpeechRequest) -> bytes:
    """Generate WAV bytes with Piper first, falling back to espeak-ng."""
    if not SERVER_TTS_ENABLED:
        raise HTTPException(status_code=503, detail="Server TTS is disabled")

    engine = SERVER_TTS_ENGINE or "auto"
    if engine in {"auto", "piper"}:
        try:
            return _synthesize_wav_piper(payload)
        except HTTPException:
            if engine == "piper":
                raise

    if engine in {"auto", "espeak", "espeak-ng"}:
        return _synthesize_wav_espeak(payload)

    raise HTTPException(status_code=503, detail="Unsupported server TTS engine")


def _wav_response(payload: SpeechRequest, cors: bool = False) -> Response:
    headers = {"Cache-Control": "no-store"}
    if cors:
        headers.update(_CORS_TTS_HEADERS)
    return Response(
        content=_synthesize_wav(payload),
        media_type="audio/wav",
        headers=headers,
    )


async def _public_speech_payload(request: Request) -> SpeechRequest:
    """Accept JSON or text/plain for cross-origin widget playback."""
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            data = await request.json()
            return SpeechRequest.model_validate(data)
        text = (await request.body()).decode("utf-8", errors="ignore")
        return SpeechRequest(text=text)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("/config", response_model=VoiceConfigResponse)
def get_voice_config(
    request: Request,
    settings_service: SettingsService = Depends(get_settings_service),
) -> VoiceConfigResponse:
    """Return HiveMind connection config for the browser client.

    The frontend uses these values to establish a WebSocket
    connection to HiveMind-core.  When no client key is configured,
    ``voice_enabled`` is ``False`` and the UI hides
    voice features.
    """
    config = settings_service.get_voice_config()
    return VoiceConfigResponse(
        hivemind_url=_resolve_hivemind_url(config.hivemind_url, request),
        hivemind_name=config.hivemind_name,
        hivemind_key=config.hivemind_key,
        hivemind_secret=config.hivemind_secret,
        voice_enabled=bool(config.hivemind_key),
    )


@router.get("/preferences", response_model=VoicePreferencesResponse)
def get_voice_preferences(
    settings_service: SettingsService = Depends(get_settings_service),
) -> VoicePreferencesResponse:
    """Return shared voice preferences for the AVAROS UI."""
    return _voice_preferences_response(settings_service)


@router.put("/preferences", response_model=VoicePreferencesResponse)
def update_voice_preferences(
    payload: VoicePreferencesRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> VoicePreferencesResponse:
    """Persist shared voice preferences for AVAROS UI and trusted embeds."""
    settings_service.set_setting(_VOICE_MODE_SETTING_KEY, payload.voice_mode)
    return _voice_preferences_response(settings_service)


@router.post("/tts", response_class=Response)
def synthesize_speech(payload: SpeechRequest) -> Response:
    """Return response text as page-media WAV audio for meeting sharing."""
    return _wav_response(payload)


@public_router.options("/voice/tts", include_in_schema=False)
def public_tts_options() -> Response:
    """CORS preflight for embeddable widget TTS playback."""
    return Response(status_code=204, headers=_CORS_TTS_HEADERS)


@public_router.options("/voice/preferences", include_in_schema=False)
def public_voice_preferences_options() -> Response:
    """CORS preflight for embeddable widget voice preference inheritance."""
    return Response(status_code=204, headers=_CORS_PREF_HEADERS)


@public_router.get("/voice/preferences", include_in_schema=False)
def public_voice_preferences(
    settings_service: SettingsService = Depends(get_settings_service),
) -> JSONResponse:
    """Public read-only voice preference endpoint for trusted embeds."""
    return JSONResponse(
        content=_voice_preferences_response(settings_service).model_dump(),
        headers=_CORS_PREF_HEADERS,
    )


@public_router.post("/voice/tts", response_class=Response)
async def public_synthesize_speech(request: Request) -> Response:
    """Public, length-limited TTS endpoint for the embeddable widget."""
    return _wav_response(await _public_speech_payload(request), cors=True)
