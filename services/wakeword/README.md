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
| `WAKEWORD_MODEL_PATH` | *(unset)* | Absolute path to a custom `.onnx`/`.tflite` model file. When set, bypasses the openWakeWord registry. |
| `WAKEWORD_MODEL_LABEL` | *(derived)* | Display label for the active model. Defaults to filename stem of `WAKEWORD_MODEL_PATH` or the `WAKEWORD_MODEL` value. |
| `WAKEWORD_CONFIRMATION_FRAMES` | `3` | Consecutive above-threshold frames required before emitting a detection event. At 80 ms/frame, 3 = 240 ms sustained confidence. |

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
  "version": "0.1.0",
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
