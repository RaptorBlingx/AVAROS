/**
 * Browser Speech-to-Text service using the Web Speech API.
 *
 * Provides push-to-talk and continuous listening modes with
 * silence detection, interim results, and configurable language.
 * Chrome/Edge recommended — Firefox has limited SpeechRecognition support.
 */

// ── Types ──────────────────────────────────────────────

export type STTState =
  | "idle"
  | "listening"
  | "processing"
  | "error"
  | "unsupported";

export interface STTResult {
  /** Transcribed text */
  transcript: string;
  /** Recognition confidence (0–1) */
  confidence: number;
  /** True when this is the final result for the utterance */
  isFinal: boolean;
}

export interface STTConfig {
  /** BCP-47 language tag, e.g. "en-US" or "tr-TR" */
  language: string;
  /** True for continuous listening (wake word mode) */
  continuous: boolean;
  /** True to receive partial transcripts while speaking */
  interimResults: boolean;
  /** Milliseconds of silence before auto-stop in push-to-talk (default 2000) */
  silenceTimeout: number;
}

type ResultCallback = (result: STTResult) => void;
type StateCallback = (state: STTState) => void;
type ErrorCallback = (error: string) => void;
type VoidCallback = () => void;

// ── Default config ─────────────────────────────────────

const DEFAULT_CONFIG: STTConfig = {
  language: "en-US",
  continuous: false,
  interimResults: true,
  silenceTimeout: 2000,
};

// ── Browser compatibility shim ─────────────────────────

function getSpeechRecognitionCtor(): typeof SpeechRecognition | null {
  if (typeof window === "undefined") return null;

  return (
    (window as unknown as Record<string, unknown>)
      .SpeechRecognition as typeof SpeechRecognition ??
    (window as unknown as Record<string, unknown>)
      .webkitSpeechRecognition as typeof SpeechRecognition ??
    null
  );
}

// ── Service ────────────────────────────────────────────

export class STTService {
  private recognition: SpeechRecognition | null = null;
  private config: STTConfig;
  private state: STTState;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;

  private resultCallbacks: ResultCallback[] = [];
  private stateCallbacks: StateCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];
  private silenceCallbacks: VoidCallback[] = [];

  constructor(config?: Partial<STTConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.state = this.isSupported() ? "idle" : "unsupported";
  }

  // ── Lifecycle ──────────────────────────────────────

  /**
   * Start speech recognition.
   *
   * Requests microphone permission (via the browser) and begins
   * listening.  Resolves once recognition has started.
   *
   * @throws Error if the browser does not support SpeechRecognition
   */
  async start(): Promise<void> {
    if (!this.isSupported()) {
      this.setState("unsupported");
      throw new Error("SpeechRecognition is not supported in this browser");
    }

    // Tear down any previous instance
    this.cleanup();

    this.setupRecognition();

    try {
      this.recognition!.start();
      this.setState("listening");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to start recognition";
      this.setState("error");
      this.fireError(message);
      throw err;
    }
  }

  /** Stop recognition and clean up resources. */
  stop(): void {
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        // Already stopped — ignore
      }
    }
    this.clearSilenceTimer();
    this.setState("idle");
  }

  /** True when the Web Speech API is available. */
  isSupported(): boolean {
    return getSpeechRecognitionCtor() !== null;
  }

  // ── Event subscriptions ────────────────────────────

  /**
   * Subscribe to recognition results.
   *
   * @returns Unsubscribe function.
   */
  onResult(callback: ResultCallback): VoidCallback {
    this.resultCallbacks.push(callback);
    return () => {
      this.resultCallbacks = this.resultCallbacks.filter(
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

  /**
   * Subscribe to error events.
   *
   * @returns Unsubscribe function.
   */
  onError(callback: ErrorCallback): VoidCallback {
    this.errorCallbacks.push(callback);
    return () => {
      this.errorCallbacks = this.errorCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /**
   * Subscribe to silence detection (push-to-talk auto-stop).
   *
   * @returns Unsubscribe function.
   */
  onSilenceDetected(callback: VoidCallback): VoidCallback {
    this.silenceCallbacks.push(callback);
    return () => {
      this.silenceCallbacks = this.silenceCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  // ── Configuration ──────────────────────────────────

  /** Change the recognition language. Takes effect on next `start()`. */
  setLanguage(lang: string): void {
    this.config.language = lang;
  }

  /** Toggle continuous vs push-to-talk mode. Takes effect on next `start()`. */
  setContinuous(continuous: boolean): void {
    this.config.continuous = continuous;
  }

  /** Get current state. */
  getState(): STTState {
    return this.state;
  }

  // ── Internal ───────────────────────────────────────

  private setupRecognition(): void {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.lang = this.config.language;
    recognition.continuous = this.config.continuous;
    recognition.interimResults = this.config.interimResults;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      this.handleResult(event);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      this.handleError(event);
    };

    recognition.onend = () => {
      this.handleEnd();
    };

    recognition.onspeechend = () => {
      // Browser says speech ended — start silence timer as backup
      if (!this.config.continuous) {
        this.handleSilenceDetection();
      }
    };

    this.recognition = recognition;
  }

  private handleResult(event: SpeechRecognitionEvent): void {
    // Reset silence timer on every result (user is still speaking)
    this.resetSilenceTimer();

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const speechResult = event.results[i];
      const result: STTResult = {
        transcript: speechResult[0].transcript,
        confidence: speechResult[0].confidence,
        isFinal: speechResult.isFinal,
      };

      this.fireResult(result);

      if (result.isFinal && !this.config.continuous) {
        // In push-to-talk, transition to processing on final result
        this.setState("processing");
      }
    }
  }

  private handleError(event: SpeechRecognitionErrorEvent): void {
    // "aborted" fires when we call stop() — not a real error
    if (event.error === "aborted") return;

    const message = `Speech recognition error: ${event.error}`;
    this.setState("error");
    this.fireError(message);
  }

  private handleEnd(): void {
    this.clearSilenceTimer();

    // In continuous mode, restart automatically unless in error state
    if (this.config.continuous && this.state === "listening") {
      try {
        this.recognition?.start();
      } catch {
        this.setState("idle");
      }
      return;
    }

    // If not already idle (e.g. we set processing), keep that state
    if (this.state === "listening") {
      this.setState("idle");
    }
  }

  private handleSilenceDetection(): void {
    if (this.config.continuous) return;

    this.clearSilenceTimer();
    this.silenceTimer = setTimeout(() => {
      this.fireSilence();
      this.stop();
    }, this.config.silenceTimeout);
  }

  private resetSilenceTimer(): void {
    this.clearSilenceTimer();

    if (!this.config.continuous) {
      this.silenceTimer = setTimeout(() => {
        this.fireSilence();
        this.stop();
      }, this.config.silenceTimeout);
    }
  }

  private clearSilenceTimer(): void {
    if (this.silenceTimer !== null) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  private cleanup(): void {
    this.clearSilenceTimer();
    if (this.recognition) {
      this.recognition.onresult = null;
      this.recognition.onerror = null;
      this.recognition.onend = null;
      this.recognition.onspeechend = null;
      try {
        this.recognition.stop();
      } catch {
        // Already stopped
      }
      this.recognition = null;
    }
  }

  // ── Event emitters ─────────────────────────────────

  private setState(state: STTState): void {
    if (this.state === state) return;
    this.state = state;
    for (const cb of this.stateCallbacks) {
      cb(state);
    }
  }

  private fireResult(result: STTResult): void {
    for (const cb of this.resultCallbacks) {
      cb(result);
    }
  }

  private fireError(message: string): void {
    for (const cb of this.errorCallbacks) {
      cb(message);
    }
  }

  private fireSilence(): void {
    for (const cb of this.silenceCallbacks) {
      cb();
    }
  }
}
