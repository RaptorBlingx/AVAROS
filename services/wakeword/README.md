# AVAROS Wake-Word Detection Service

Browser-audio voice gateway wrapping
[openWakeWord](https://github.com/dscripka/openWakeWord) for wake detection and
a pinned local [whisper.cpp](https://github.com/ggml-org/whisper.cpp) build for
English/Turkish transcription and request-language detection. No audio or text
is sent to a paid inference API.

## Quick Start

```bash
cd services/wakeword
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9999
```

Or via Docker Compose (from the project root):

```bash
docker compose -f docker/docker-compose.avaros.yml up avaros-wakeword
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WAKEWORD_MODEL` | `hey_avaros` | Active wake-word model label/name |
| `WAKEWORD_THRESHOLD` | `0.5` | Detection confidence threshold (0.0–1.0) |
| `WAKEWORD_MODEL_PATH` | *(unset)* | Absolute path to a custom `.onnx`/`.tflite` model file. When set, bypasses the openWakeWord registry. |
| `WAKEWORD_MODEL_LABEL` | *(derived)* | Display label for the active model. Defaults to filename stem of `WAKEWORD_MODEL_PATH` or the `WAKEWORD_MODEL` value. |
| `WAKEWORD_PRELOAD_MODELS` | `0` | When `1`, preload registry model files at service startup to avoid first-connection download delay. |
| `WAKEWORD_CONFIRMATION_FRAMES` | `3` | Consecutive above-threshold frames required before emitting a detection event. At 80 ms/frame, 3 = 240 ms sustained confidence. |
| `WAKEWORD_DETECTION_COOLDOWN_SECONDS` | `1.2` | Suppresses duplicate detection events from the same spoken wake phrase. Useful when `WAKEWORD_CONFIRMATION_FRAMES=1` for demo responsiveness. |
| `ASR_THREADS` | `2` | CPU threads used by the serial local whisper.cpp worker. |
| `ASR_TIMEOUT_SECONDS` | `20` | Hard timeout for one local transcription. |
| `UTTERANCE_START_TIMEOUT_MS` | `10000` | Maximum wait for speech after AVAROS's readiness acknowledgement. |
| `UTTERANCE_MAX_DURATION_MS` | `20000` | Maximum post-wake request capture. |
| `UTTERANCE_END_SILENCE_MS` | `1200` | Local-VAD silence that ends a started request. |
| `UTTERANCE_SPEECH_START_PROBABILITY` | `0.55` | Silero probability required to classify a frame as speech. |

If `WAKEWORD_MODEL_PATH` is configured but the file does not exist, service startup falls back to the registry model. If that model is unavailable, it falls back to `hey_jarvis`.

### Available Models

The built-in openWakeWord registry ships with:

- `hey_jarvis`
- `alexa`
- `hey_mycroft`
- `timer`
- `weather`

Custom local model files are also supported (for example
`/app/models/hey_avaros.onnx`) via `WAKEWORD_MODEL_PATH` and
`WAKEWORD_MODEL_LABEL`.

## API

### `GET /health`

Readiness probe.

```json
{
  "status": "ok",
  "models_loaded": ["hey_avaros"],
  "version": "0.2.0",
  "model_mode": "custom_path",
  "configured_threshold": 0.85,
  "threshold": 0.85,
  "threshold_source": "configured",
  "active_session_count": 0,
  "active_session_thresholds": [],
  "active_session_threshold_min": 0.85,
  "active_session_threshold_max": 0.85,
  "active_session_threshold_avg": 0.85,
  "confirmation_frames": 5
}
```

### `WS /ws/detect`

Stream raw 16 kHz signed-16-bit-LE mono PCM binary frames continuously. The
embedded widget first opts into post-wake capture with
`{"command":"set_utterance_capture","enabled":true}`. Without that opt-in,
the endpoint retains its original detection-only behavior for the full AVAROS
UI. The service first emits the wake event:

```json
{
  "event": "detected",
  "model": "hey_avaros",
  "score": 0.9231,
  "timestamp": "2026-03-04T12:00:00+00:00"
}
```

The widget pauses microphone streaming, speaks its readiness acknowledgement,
then sends `{"command":"start_utterance_capture","language":"en-US"}` (or
`tr-TR`). The service captures only
the following request and emits `utterance_processing` when VAD reaches the
end of the turn. The browser must stop sending microphone audio at that point
but keep the socket open. A successful local transcription is returned as:

```json
{
  "event": "transcript",
  "text": "Geçen ay ne değişti?",
  "language": "tr-TR",
  "ended_by": "complete"
}
```

Recoverable failures use `{"event":"utterance_error","code":"..."}`. Codes
are `silence_timeout`, `no_speech`, `language_invalid`, `asr_timeout`,
`asr_unavailable`, and `asr_failed`. The next wake cycle begins only after the
client calls `startListening()` again; that command resets detector state.

## Architecture Notes

- **Per-connection model instances.** The openWakeWord preprocessor is
  stateful (mel-spectrogram buffers, raw audio ring-buffer). Each
  WebSocket connection gets its own `WakeWordDetector` (~250 ms load).
- **Targeted model loading.** Only the configured model is loaded, not
  all pretrained models. The `openwakeword.models` registry maps clean
  names to `.onnx` file paths.
- **Frame buffering.** The detector accumulates incoming PCM until a
  complete 80 ms frame (1280 samples / 2560 bytes) is available.
- **Multi-frame confirmation.** A single above-threshold frame does
  **not** trigger detection. The detector requires
  `WAKEWORD_CONFIRMATION_FRAMES` (default 3) consecutive frames above
  threshold before emitting a `"detected"` event. A single
  below-threshold frame resets the counter. This prevents impulse noise
  (coughs, clicks, "Hey Car…") from producing false wake events.
- **Runtime sensitivity.** The frontend sends `set_sensitivity` via
  WebSocket. The backend maps this to a threshold update using an
  inverted scale: `threshold = 1.0 - sensitivity`. A direct
  `set_threshold` command is also available for ops use.
- **Language separation.** openWakeWord sees the wake phrase. The widget's
  explicit EN/TR hands-free selection accompanies a fresh capture window and
  is passed to local whisper.cpp, so “Hey Jarvis” never becomes part of the
  request and each request has an intentional transcription language.
- **End-of-turn.** The local Silero VAD bundled with openWakeWord provides
  probability-based onset and endpointing, pre-roll, 1.2-second end silence,
  a ten-second no-speech timeout, and a 20-second cap. The service logs only
  timing, last-speech/trailing VAD probabilities, end reason, and ASR
  language/duration—never raw audio or transcription text.
- **Bounded inference.** whisper.cpp runs with the quantized multilingual base
  model, two CPU threads, a global one-request-at-a-time lock, and private
  temporary WAV/JSON files that are deleted after every request.

## Custom Model Deployment

When deploying a custom model (e.g. `hey_avaros.onnx`), the
recommended approach is a **host volume mount**:

```yaml
# docker-compose snippet
volumes:
  - ../services/wakeword/models:/app/models
environment:
  WAKEWORD_MODEL_PATH: /app/models/hey_avaros.onnx
  WAKEWORD_MODEL_LABEL: hey_avaros
```

**Important:** Because the model is volume-mounted, rebuilding the
Docker image does **not** replace the active model. To deploy a new
model version:

1. Replace the `.onnx` file on the host.
2. Restart the container (`docker compose restart avaros-wakeword`).

The model file is intentionally **not** committed to git (binary
artefact). Verify the active model at runtime via `GET /health`:

```bash
curl -s http://localhost:9999/health | jq .
```
