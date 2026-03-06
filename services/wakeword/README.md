# AVAROS Wake-Word Detection Service

Lightweight microservice wrapping [openWakeWord](https://github.com/dscripka/openWakeWord)
for browser-based wake-word detection over WebSocket.

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
  "version": "0.1.0"
}
```

### `WS /ws/detect`

Stream raw 16 kHz signed-16-bit-LE PCM binary frames. Server replies
with a JSON message **only** when a wake word is detected:

```json
{
  "event": "detected",
  "model": "hey_avaros",
  "score": 0.9231,
  "timestamp": "2026-03-04T12:00:00+00:00"
}
```

## Architecture Notes

- **Per-connection model instances.** The openWakeWord preprocessor is
  stateful (mel-spectrogram buffers, raw audio ring-buffer). Each
  WebSocket connection gets its own `WakeWordDetector` (~250 ms load).
- **Targeted model loading.** Only the configured model is loaded, not
  all pretrained models. The `openwakeword.models` registry maps clean
  names to `.onnx` file paths.
- **Frame buffering.** The detector accumulates incoming PCM until a
  complete 80 ms frame (1280 samples / 2560 bytes) is available.
