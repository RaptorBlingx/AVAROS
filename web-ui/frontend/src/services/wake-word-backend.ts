/**
 * Backend wake-word detection fallback using openWakeWord.
 *
 * This is a **stub** — the interface is defined so the `VoiceModeService`
 * and `VoiceContext` can reference it, but the full implementation
 * (streaming raw PCM audio over a WebSocket to a Python backend that
 * runs openWakeWord) is deferred to P5-L06 unless the browser-side
 * TensorFlow.js approach proves inadequate.
 *
 * Architecture:
 *   Browser → getUserMedia → PCM frames → WebSocket → Backend
 *   Backend → openWakeWord → "detected" event → WebSocket → Browser
 *
 * openWakeWord provides higher accuracy (~95 %) but adds ~200 ms
 * latency and requires a backend process.
 */

// ── Types ──────────────────────────────────────────────

export type BackendWakeWordState =
  | "idle"
  | "connecting"
  | "listening"
  | "detected"
  | "error"
  | "unsupported";

export interface BackendWakeWordConfig {
  /** WebSocket URL for the wake word backend, e.g. ws://localhost:9999/wakeword */
  wsUrl: string;
  /** Detection sensitivity sent to the backend (0–1, default 0.5) */
  sensitivity: number;
}

type VoidCallback = () => void;
type StateCallback = (state: BackendWakeWordState) => void;

// ── Defaults ───────────────────────────────────────────

const DEFAULT_CONFIG: BackendWakeWordConfig = {
  wsUrl: "ws://localhost:9999/wakeword",
  sensitivity: 0.5,
};

// ── Stub service ───────────────────────────────────────

/**
 * Backend wake-word detection via openWakeWord (stub).
 *
 * All public methods follow the same contract as `WakeWordService`,
 * allowing the two implementations to be swapped via a common interface.
 *
 * **Not implemented** — every method is a safe no-op or throws
 * `"Not implemented"`.  Full implementation in a future task.
 */
export class BackendWakeWordService {
  private _state: BackendWakeWordState = "idle";
  private config: BackendWakeWordConfig;
  private detectedCallbacks: VoidCallback[] = [];
  private stateCallbacks: StateCallback[] = [];

  constructor(config?: Partial<BackendWakeWordConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // ── Public state ───────────────────────────────────

  get state(): BackendWakeWordState {
    return this._state;
  }

  isModelLoaded(): boolean {
    return false;
  }

  // ── Lifecycle (stubs) ──────────────────────────────

  async initialize(): Promise<void> {
    throw new Error(
      "BackendWakeWordService is a stub — not implemented. " +
        "Use WakeWordService (TF.js) for browser-side detection.",
    );
  }

  async startListening(): Promise<void> {
    throw new Error("BackendWakeWordService.startListening() not implemented");
  }

  stopListening(): void {
    // No-op stub
  }

  dispose(): void {
    this.detectedCallbacks = [];
    this.stateCallbacks = [];
    this._state = "idle";
  }

  // ── Events ─────────────────────────────────────────

  onDetected(callback: VoidCallback): VoidCallback {
    this.detectedCallbacks.push(callback);
    return () => {
      this.detectedCallbacks = this.detectedCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  onStateChange(callback: StateCallback): VoidCallback {
    this.stateCallbacks.push(callback);
    return () => {
      this.stateCallbacks = this.stateCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  // ── Configuration ──────────────────────────────────

  setSensitivity(value: number): void {
    this.config.sensitivity = Math.max(0, Math.min(1, value));
  }

  getSensitivity(): number {
    return this.config.sensitivity;
  }

  /** Return the configured WebSocket URL. */
  getWsUrl(): string {
    return this.config.wsUrl;
  }
}
