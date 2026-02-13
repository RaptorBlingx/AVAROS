# AVAROS Wake Word Model — "Hey AVAROS"

## Overview

This directory is the home for the pre-trained TensorFlow.js transfer-learning
model that recognises the wake word **"hey avaros"**.

Until a fully trained model is available the service falls back to the built-in
base model keywords shipped with `@tensorflow-models/speech-commands`.

## Model files (when trained)

```
public/models/wake-word/
├── model.json          # TF.js model topology + weight manifest
├── group1-shard1of1.bin  # Binary weight file(s)
└── README.md           # This file
```

## Training workflow

1. **Collect positive samples** — Record ~50-100 clips of "hey avaros"
   from at least 3 different speakers at various distances and noise levels.
2. **Collect negative samples** — Record ~100 clips of silence, random
   speech, and common manufacturing-floor sounds.
3. **Create the base recognizer:**
   ```js
   import * as speechCommands from "@tensorflow-models/speech-commands";
   const base = speechCommands.create("BROWSER_FFT");
   await base.ensureModelLoaded();
   ```
4. **Create a transfer recognizer and add examples:**
   ```js
   const transfer = base.createTransfer("hey avaros");
   // For each audio sample:
   await transfer.collectExample("hey avaros");    // positive
   await transfer.collectExample("_background_noise_"); // negative
   ```
5. **Train:**
   ```js
   await transfer.train({ epochs: 25, batchSize: 16 });
   ```
6. **Export the model:**
   ```js
   const savedArtifacts = transfer.save();
   // Download model.json + weight files
   ```
7. **Place files** in this directory and commit.

## Model metadata

| Property | Value |
|----------|-------|
| Base model | `BROWSER_FFT` (18-word speech commands) |
| Transfer label | `hey avaros` |
| Sample rate | 44100 Hz (browser default) |
| Frame duration | 23 ms (~43 frames/s) |
| Model size target | < 5 MB total |
| Min accuracy target | ≥ 70 % recall @ ≤ 1 FP / 5 min |

## Browser requirements

- AudioContext API (Chrome, Edge, Firefox, Safari 14.1+)
- `navigator.mediaDevices.getUserMedia` (HTTPS required in production)
- WebGL or WASM backend for TensorFlow.js

## Notes

- The base model ships 18 common English keywords ("yes", "no", "up",
  "down", etc.) and is useful for a proof-of-concept demo even before
  the custom wake word is trained.
- For higher accuracy on noisy factory floors, the backend fallback
  (openWakeWord via WebSocket) can be enabled — see
  `services/wake-word-backend.ts`.
- TensorFlow.js adds ~2 MB to the bundle. The service lazy-loads the
  library only when wake-word mode is activated.
