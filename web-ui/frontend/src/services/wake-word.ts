/**
 * Browser-side wake word detection using TensorFlow.js Speech Commands.
 * Lazy-loads TF.js (~2 MB) only when wake-word mode is activated.
 */

import {
  DEFAULT_CONFIG,
  WAKE_WORD_LABEL,
  type StateCallback,
  type VoidCallback,
  type WakeWordConfig,
  type WakeWordState,
} from "./wake-word-types";
import {
  findTopScore,
  isSuppressionActive,
  isWakeWordLabel,
} from "./wake-word-detection";

// Re-export types for consumer convenience
export type { WakeWordConfig, WakeWordState } from "./wake-word-types";

export class WakeWordService {
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

  /** Current service state. */
  get state(): WakeWordState {
    return this._state;
  }

  /** True when the model has been loaded and is ready. */
  isModelLoaded(): boolean {
    return this.recognizer !== null || this.transferRecognizer !== null;
  }

  /**
   * Lazy-load TF.js and the Speech Commands model.
   * Call once; subsequent calls are no-ops if already loaded.
   */
  async initialize(): Promise<void> {
    if (this.isModelLoaded()) return;
    if (!this.isBrowserCompatible()) {
      this.setState("unsupported");
      throw new Error("Browser does not support AudioContext / getUserMedia");
    }

    this.setState("loading");

    try {
      const [tf, sc] = await Promise.all([
        import("@tensorflow/tfjs"),
        import("@tensorflow-models/speech-commands"),
      ]);

      await tf.ready();
      this.speechCommands = sc;
      this.recognizer = sc.create("BROWSER_FFT");
      await this.recognizer.ensureModelLoaded();

      if (this.config.modelUrl) {
        await this.loadCustomModel(this.config.modelUrl);
      }

      this.setState("idle");
    } catch (err) {
      this.setState("error");
      throw err;
    }
  }

  /** Begin always-on wake word detection. */
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
          overlapFactor: 0.5,
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
  async dispose(): Promise<void> {
    this.stopListening();
    await this.safeStopRecognizer(this.transferRecognizer);
    this.transferRecognizer = null;
    await this.safeStopRecognizer(this.recognizer);
    this.recognizer = null;
    this.speechCommands = null;
    this.detectedCallbacks = [];
    this.stateCallbacks = [];
    this.setState("idle");
  }

  /** Subscribe to wake word detection events. Returns unsubscribe function. */
  onDetected(callback: VoidCallback): VoidCallback {
    this.detectedCallbacks.push(callback);
    return () => {
      this.detectedCallbacks = this.detectedCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /** Subscribe to state transitions. Returns unsubscribe function. */
  onStateChange(callback: StateCallback): VoidCallback {
    this.stateCallbacks.push(callback);
    return () => {
      this.stateCallbacks = this.stateCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /** Adjust detection sensitivity (0.0–1.0). */
  setSensitivity(value: number): void {
    this.config.sensitivity = Math.max(0, Math.min(1, value));
  }

  /** Return the current sensitivity threshold. */
  getSensitivity(): number {
    return this.config.sensitivity;
  }

  /** Load a pre-trained transfer-learning model for "hey avaros". */
  async loadCustomModel(url: string): Promise<void> {
    if (!this.recognizer || !this.speechCommands) {
      throw new Error("Base model must be loaded first");
    }

    try {
      this.transferRecognizer = this.recognizer.createTransfer(WAKE_WORD_LABEL);
      await this.transferRecognizer.load(url);
      this.usingTransferModel = true;
    } catch {
      this.transferRecognizer = null;
      this.usingTransferModel = false;
    }
  }

  /** Handle a spectrogram result, check for wake word match. */
  private handleSpectrogramResult(
    result: import("@tensorflow-models/speech-commands").SpeechCommandRecognizerResult,
  ): void {
    const scores = result.scores as Float32Array;
    const labels = this.getActiveRecognizer()?.wordLabels() ?? [];
    const top = findTopScore(scores, labels);

    if (!top) return;
    if (!isWakeWordLabel(top.label, this.usingTransferModel)) return;
    if (top.score < this.config.sensitivity) return;
    if (isSuppressionActive(this.lastDetection, this.config.suppressionPeriod)) {
      return;
    }

    this.lastDetection = Date.now();
    this.setState("detected");
    this.fireDetected();

    setTimeout(() => {
      if (this._state === "detected") this.setState("listening");
    }, 100);
  }

  private getActiveRecognizer() {
    return this.transferRecognizer ?? this.recognizer ?? null;
  }

  private isBrowserCompatible(): boolean {
    if (typeof window === "undefined") return false;
    return (
      "AudioContext" in window &&
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia
    );
  }

  /** Safely stop a recognizer, swallowing "already stopped" errors. */
  private async safeStopRecognizer(
    recognizer: import("@tensorflow-models/speech-commands").SpeechCommandRecognizer | null,
  ): Promise<void> {
    if (!recognizer) return;
    try {
      await recognizer.stopListening();
    } catch {
      // Already stopped — ignore
    }
  }

  /** Pause listening when tab hidden, resume when visible. */
  private installVisibilityHandler(): void {
    if (this.visibilityHandler) return;

    this.visibilityHandler = () => {
      if (document.hidden && this._state === "listening") {
        this.wasListeningBeforeHidden = true;
        const active = this.getActiveRecognizer();
        if (active?.isListening()) active.stopListening();
        this.setState("idle");
      } else if (!document.hidden && this.wasListeningBeforeHidden) {
        this.wasListeningBeforeHidden = false;
        void this.startListening();
      }
    };

    document.addEventListener("visibilitychange", this.visibilityHandler);
  }

  private removeVisibilityHandler(): void {
    if (this.visibilityHandler) {
      document.removeEventListener("visibilitychange", this.visibilityHandler);
      this.visibilityHandler = null;
    }
    this.wasListeningBeforeHidden = false;
  }

  private setState(next: WakeWordState): void {
    if (this._state === next) return;
    this._state = next;
    for (const cb of this.stateCallbacks) cb(next);
  }

  private fireDetected(): void {
    for (const cb of this.detectedCallbacks) cb();
  }
}
