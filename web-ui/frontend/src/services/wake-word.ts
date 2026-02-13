/**
 * Browser-side wake word detection using TensorFlow.js Speech Commands.
 *
 * Listens continuously for "hey avaros" using a pre-trained transfer-learning
 * model.  When the wake word is detected the registered callbacks fire and
 * the service enters a suppression window to avoid rapid-fire triggers.
 *
 * The module lazy-loads TensorFlow.js so the ~2 MB bundle cost is only paid
 * when wake-word mode is actually activated.
 *
 * Performance targets:
 *   - Model load time: < 5 s
 *   - Inference latency: ~10 ms per frame
 *   - CPU usage while listening: < 15 %
 *   - False positive rate: < 1 per 5 min of ambient noise
 */

// ── Types ──────────────────────────────────────────────

export type WakeWordState =
  | "idle"
  | "loading"
  | "listening"
  | "detected"
  | "error"
  | "unsupported";

export interface WakeWordConfig {
  /** Detection threshold, 0.0 – 1.0 (default 0.75) */
  sensitivity: number;
  /** Milliseconds to ignore subsequent detections after a hit (default 2000) */
  suppressionPeriod: number;
  /** URL to a custom transfer-learning model, or null for the built-in base */
  modelUrl: string | null;
}

type VoidCallback = () => void;
type StateCallback = (state: WakeWordState) => void;

// ── Defaults ───────────────────────────────────────────

const DEFAULT_CONFIG: WakeWordConfig = {
  sensitivity: 0.75,
  suppressionPeriod: 2000,
  modelUrl: null,
};

/**
 * The label the transfer-learning model uses for the wake word.
 * During base-model-only mode we fall back to a built-in keyword.
 */
const WAKE_WORD_LABEL = "hey avaros";

/** Fallback keyword from the base model for PoC use. */
const BASE_MODEL_FALLBACK_LABEL = "_background_noise_";

// ── Service ────────────────────────────────────────────

export class WakeWordService {
  // TF.js modules — loaded lazily
  private speechCommands: typeof import("@tensorflow-models/speech-commands") | null = null;
  private recognizer: import("@tensorflow-models/speech-commands").SpeechCommandRecognizer | null = null;
  private transferRecognizer: import("@tensorflow-models/speech-commands").TransferSpeechCommandRecognizer | null = null;

  private _state: WakeWordState = "idle";
  private config: WakeWordConfig;
  private lastDetection = 0;
  private usingTransferModel = false;

  private detectedCallbacks: VoidCallback[] = [];
  private stateCallbacks: StateCallback[] = [];

  private visibilityHandler: (() => void) | null = null;
  private wasListeningBeforeHidden = false;

  constructor(config?: Partial<WakeWordConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // ── Public state ───────────────────────────────────

  /** Current service state. */
  get state(): WakeWordState {
    return this._state;
  }

  /** True when the model has been loaded and is ready. */
  isModelLoaded(): boolean {
    return this.recognizer !== null || this.transferRecognizer !== null;
  }

  // ── Lifecycle ──────────────────────────────────────

  /**
   * Lazy-load TensorFlow.js and the Speech Commands model.
   *
   * Heavy operation (~2–5 s).  Call once; subsequent calls are no-ops
   * if a model is already loaded.
   */
  async initialize(): Promise<void> {
    if (this.isModelLoaded()) return;
    if (!this.isBrowserCompatible()) {
      this.setState("unsupported");
      throw new Error("Browser does not support AudioContext / getUserMedia");
    }

    this.setState("loading");

    try {
      // Dynamic import keeps TF.js out of the main bundle
      const [tf, sc] = await Promise.all([
        import("@tensorflow/tfjs"),
        import("@tensorflow-models/speech-commands"),
      ]);

      // Ensure tf is ready
      await tf.ready();

      this.speechCommands = sc;

      // Create the base BROWSER_FFT recognizer
      this.recognizer = sc.create("BROWSER_FFT");
      await this.recognizer.ensureModelLoaded();

      // Attempt to load a custom "hey avaros" transfer model
      if (this.config.modelUrl) {
        await this.loadCustomModel(this.config.modelUrl);
      }

      this.setState("idle");
    } catch (err) {
      this.setState("error");
      throw err;
    }
  }

  /**
   * Begin always-on wake word detection.
   *
   * The recognizer runs at the model's native sample rate and calls
   * `handleSpectrogramResult` on every inference frame.
   *
   * @throws Error when no model has been loaded yet.
   */
  async startListening(): Promise<void> {
    if (!this.isModelLoaded()) {
      throw new Error(
        "Model not loaded — call initialize() before startListening()",
      );
    }

    if (this._state === "listening") return;

    const activeRecognizer = this.getActiveRecognizer();
    if (!activeRecognizer) {
      throw new Error("No recognizer available");
    }

    try {
      await activeRecognizer.listen(
        async (result) => this.handleSpectrogramResult(result),
        {
          probabilityThreshold: this.config.sensitivity,
          overlapFactor: 0.5, // 50 % overlap → smoother detection
          includeSpectrogram: false,
        },
      );

      this.setState("listening");
      this.installVisibilityHandler();
    } catch (err) {
      this.setState("error");
      throw err;
    }
  }

  /** Stop always-on listening. */
  stopListening(): void {
    const activeRecognizer = this.getActiveRecognizer();
    if (activeRecognizer?.isListening()) {
      activeRecognizer.stopListening();
    }

    this.removeVisibilityHandler();
    this.setState("idle");
  }

  /** Release all resources (model weights, audio streams). */
  dispose(): void {
    this.stopListening();

    if (this.transferRecognizer) {
      try {
        const result = this.transferRecognizer.stopListening();
        if (result && typeof (result as Promise<void>).catch === "function") {
          (result as Promise<void>).catch(() => {});
        }
      } catch {
        // Already stopped — ignore
      }
      this.transferRecognizer = null;
    }

    if (this.recognizer) {
      try {
        const result = this.recognizer.stopListening();
        if (result && typeof (result as Promise<void>).catch === "function") {
          (result as Promise<void>).catch(() => {});
        }
      } catch {
        // Already stopped — ignore
      }
      this.recognizer = null;
    }

    this.speechCommands = null;
    this.detectedCallbacks = [];
    this.stateCallbacks = [];
    this.setState("idle");
  }

  // ── Events ─────────────────────────────────────────

  /**
   * Subscribe to wake word detection events.
   *
   * @returns Unsubscribe function.
   */
  onDetected(callback: VoidCallback): VoidCallback {
    this.detectedCallbacks.push(callback);
    return () => {
      this.detectedCallbacks = this.detectedCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /**
   * Subscribe to state transitions.
   *
   * @returns Unsubscribe function.
   */
  onStateChange(callback: StateCallback): VoidCallback {
    this.stateCallbacks.push(callback);
    return () => {
      this.stateCallbacks = this.stateCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  // ── Configuration ──────────────────────────────────

  /**
   * Adjust detection sensitivity.
   *
   * @param value - Threshold between 0.0 (most sensitive) and 1.0.
   */
  setSensitivity(value: number): void {
    this.config.sensitivity = Math.max(0, Math.min(1, value));
  }

  /** Return the current sensitivity threshold. */
  getSensitivity(): number {
    return this.config.sensitivity;
  }

  // ── Model management ───────────────────────────────

  /**
   * Load a pre-trained transfer-learning model for "hey avaros".
   *
   * The model consists of a `model.json` manifest and binary weight
   * files located under the given URL directory.
   *
   * @param url - Base URL of the model directory (e.g. "/models/wake-word").
   */
  async loadCustomModel(url: string): Promise<void> {
    if (!this.recognizer || !this.speechCommands) {
      throw new Error("Base model must be loaded first");
    }

    try {
      this.transferRecognizer = this.recognizer.createTransfer(WAKE_WORD_LABEL);
      await this.transferRecognizer.load(url);
      this.usingTransferModel = true;
    } catch {
      // Transfer model unavailable — fall back to base model
      this.transferRecognizer = null;
      this.usingTransferModel = false;
    }
  }

  // ── Internal ───────────────────────────────────────

  /**
   * Handle a spectrogram inference result from the recognizer.
   *
   * Checks whether the top-scoring label matches the wake word and
   * whether enough time has passed since the last detection.
   */
  private handleSpectrogramResult(
    result: import("@tensorflow-models/speech-commands").SpeechCommandRecognizerResult,
  ): void {
    const scores = result.scores as Float32Array;
    const labels = this.getActiveRecognizer()?.wordLabels() ?? [];

    if (labels.length === 0 || scores.length === 0) return;

    // Find the top-scoring label
    let maxIdx = 0;
    let maxScore = scores[0];
    for (let i = 1; i < scores.length; i++) {
      if (scores[i] > maxScore) {
        maxScore = scores[i];
        maxIdx = i;
      }
    }

    const detectedLabel = labels[maxIdx];
    const isWakeWord = this.isWakeWordLabel(detectedLabel);

    if (!isWakeWord) return;
    if (maxScore < this.config.sensitivity) return;
    if (this.isSuppressionActive()) return;

    // Wake word detected!
    this.lastDetection = Date.now();
    this.setState("detected");
    this.fireDetected();

    // Return to listening after a tick (let consumers react to "detected")
    setTimeout(() => {
      if (this._state === "detected") {
        this.setState("listening");
      }
    }, 100);
  }

  /**
   * Check whether a label matches the wake word.
   *
   * In transfer-model mode, the label is the custom word.
   * In base-model mode, any non-background keyword is acceptable
   * as a proof-of-concept stand-in.
   */
  private isWakeWordLabel(label: string): boolean {
    if (this.usingTransferModel) {
      return label.toLowerCase() === WAKE_WORD_LABEL;
    }
    // PoC: accept any non-background, non-unknown label
    return (
      label !== BASE_MODEL_FALLBACK_LABEL &&
      label !== "_unknown_" &&
      label !== "background_noise"
    );
  }

  /** True when we are inside the suppression window. */
  private isSuppressionActive(): boolean {
    return Date.now() - this.lastDetection < this.config.suppressionPeriod;
  }

  /** Return whichever recognizer is currently in use. */
  private getActiveRecognizer() {
    return this.transferRecognizer ?? this.recognizer ?? null;
  }

  /** True when the browser can provide audio + run TF.js. */
  private isBrowserCompatible(): boolean {
    if (typeof window === "undefined") return false;
    return (
      "AudioContext" in window &&
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia
    );
  }

  // ── Visibility handling (CPU optimization) ─────────

  /**
   * Pause wake-word listening when the tab is hidden and resume
   * when it becomes visible again.
   */
  private installVisibilityHandler(): void {
    if (this.visibilityHandler) return;

    this.visibilityHandler = () => {
      if (document.hidden) {
        if (this._state === "listening") {
          this.wasListeningBeforeHidden = true;
          const active = this.getActiveRecognizer();
          if (active?.isListening()) {
            active.stopListening();
          }
        }
      } else if (this.wasListeningBeforeHidden) {
        this.wasListeningBeforeHidden = false;
        void this.startListening();
      }
    };

    document.addEventListener("visibilitychange", this.visibilityHandler);
  }

  /** Remove the visibility change handler. */
  private removeVisibilityHandler(): void {
    if (this.visibilityHandler) {
      document.removeEventListener("visibilitychange", this.visibilityHandler);
      this.visibilityHandler = null;
    }
    this.wasListeningBeforeHidden = false;
  }

  // ── Event dispatch ─────────────────────────────────

  private setState(next: WakeWordState): void {
    if (this._state === next) return;
    this._state = next;
    for (const cb of this.stateCallbacks) {
      cb(next);
    }
  }

  private fireDetected(): void {
    for (const cb of this.detectedCallbacks) {
      cb();
    }
  }
}
