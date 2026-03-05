/**
 * Backend wake-word detection using openWakeWord over WebSocket.
 *
 * Streams microphone audio (resampled to 16 kHz int16 PCM) to the
 * openWakeWord backend via a WebSocket connection.  The backend runs
 * inference and sends detection events back.
 *
 * Architecture:
 *   Browser → getUserMedia → AudioWorklet (resample) → WebSocket → Backend
 *   Backend → openWakeWord → "detected" event → WebSocket → Browser
 *
 * Connection resilience:
 *   On disconnect, retries with exponential backoff (1 s → 2 s → 4 s …
 *   max 30 s).  While disconnected, `isAvailable()` returns `false` and
 *   callers should degrade to push-to-talk mode.
 */

// ── Types ──────────────────────────────────────────────

export type BackendWakeWordState =
  | "idle"
  | "connecting"
  | "listening"
  | "detected"
  | "error"
  | "unsupported";

/**
 * Canonical wake word state exposed to UI consumers.
 *
 * Matches the legacy TF.js `WakeWordState` shape so existing context/types
 * keep working after the TF.js removal (P6-E08).
 */
export type WakeWordState =
  | "idle"
  | "loading"
  | "listening"
  | "detected"
  | "error"
  | "unsupported";

export interface BackendWakeWordConfig {
  /** WebSocket URL for the wake word backend. */
  wsUrl: string;
  /** Detection sensitivity sent to the backend (0–1, default 0.5). */
  sensitivity: number;
}

type VoidCallback = () => void;
type StateCallback = (state: BackendWakeWordState) => void;

/** Payload delivered to detection callbacks. */
export interface DetectionPayload {
  model: string;
  score: number;
}

type DetectionCallback = (payload: DetectionPayload) => void;

/** Shape of a detection event from the backend. */
interface DetectionEvent {
  event: "detected";
  model: string;
  score: number;
  timestamp: string;
}

// ── Defaults ───────────────────────────────────────────

const DEFAULT_WS_URL = resolveDefaultWsUrl();

const DEFAULT_CONFIG: BackendWakeWordConfig = {
  wsUrl: DEFAULT_WS_URL,
  sensitivity: 0.5,
};

/** Exponential backoff parameters. */
const BACKOFF_INITIAL_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
const BACKOFF_MULTIPLIER = 2;

/**
 * Resolve the default WebSocket URL from environment or hostname.
 *
 * Priority: VITE_WAKEWORD_URL env → current hostname with port 9999.
 */
function resolveDefaultWsUrl(): string {
  /* c8 ignore start — env-dependent */
  if (typeof import.meta !== "undefined") {
    const envUrl =
      (import.meta as unknown as Record<string, Record<string, string>>).env
      ?.VITE_WAKEWORD_URL;
    if (envUrl) return envUrl;
  }

  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.hostname}:9999/ws/detect`;
  }
  /* c8 ignore stop */

  return "ws://localhost:9999/ws/detect";
}

// ── Service ────────────────────────────────────────────

/**
 * Backend wake-word detection via openWakeWord WebSocket.
 *
 * This is the sole wake word engine in the frontend (DEC-033).
 * Voice mode orchestration always uses this service for wake-word mode.
 */
export class BackendWakeWordService {
  private _state: BackendWakeWordState = "idle";
  private config: BackendWakeWordConfig;
  private detectedCallbacks: DetectionCallback[] = [];
  private stateCallbacks: StateCallback[] = [];

  // WebSocket
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = BACKOFF_INITIAL_MS;
  private shouldReconnect = false;

  // Audio pipeline
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;

  // ScriptProcessor fallback resampling state
  private _spResampleRatio = 1;
  private _spBuffer: Int16Array = new Int16Array(0);
  private _spOffset = 0;

  constructor(config?: Partial<BackendWakeWordConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // ── Public state ───────────────────────────────────

  get state(): BackendWakeWordState {
    return this._state;
  }

  /** True when the WebSocket is open and ready to receive audio. */
  isModelLoaded(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Check if the backend wakeword service is reachable.
   *
   * Returns `true` when the WebSocket connection is open.
   */
  isAvailable(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // ── Lifecycle ──────────────────────────────────────

  /**
   * Open a WebSocket connection to the openWakeWord backend.
   *
   * Resolves once the connection is established, or rejects on failure.
   * If a connection is already open, this is a no-op.
   */
  async initialize(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;
    await this.connect();
  }

  /**
   * Start streaming microphone audio to the backend.
   *
   * Requests microphone access, sets up an AudioWorklet (with
   * ScriptProcessorNode fallback) for PCM resampling, and forwards
   * binary frames over the WebSocket.
   */
  async startListening(): Promise<void> {
    if (this._state === "listening") return;

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      await this.initialize();
    }

    // Send sensitivity configuration
    this.sendSensitivity();

    await this.startAudioCapture();
    this.setState("listening");
  }

  /**
   * Stop streaming audio (keep WebSocket open for quick restart).
   *
   * Releases the microphone and tears down the audio pipeline.
   */
  stopListening(): void {
    this.stopAudioCapture();
    if (this._state === "listening" || this._state === "detected") {
      this.setState("idle");
    }
  }

  /**
   * Tear down everything — WebSocket, audio, timers.
   */
  dispose(): void {
    this.shouldReconnect = false;
    this.clearReconnectTimer();
    this.stopAudioCapture();
    this.closeWebSocket();
    this.detectedCallbacks = [];
    this.stateCallbacks = [];
    this.setState("idle");
  }

  // ── Events ─────────────────────────────────────────

  /**
   * Register a callback for wake word detection events.
   *
   * @param callback - Receives model name and confidence score.
   * @returns Unsubscribe function.
   */
  onDetected(callback: DetectionCallback): VoidCallback {
    this.detectedCallbacks.push(callback);
    return () => {
      this.detectedCallbacks = this.detectedCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /**
   * Register a callback for state change events.
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

  /** Set detection sensitivity (0–1). Sends to backend if connected. */
  setSensitivity(value: number): void {
    this.config.sensitivity = Math.max(0, Math.min(1, value));
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendSensitivity();
    }
  }

  getSensitivity(): number {
    return this.config.sensitivity;
  }

  /** Return the configured WebSocket URL. */
  getWsUrl(): string {
    return this.config.wsUrl;
  }

  // ── WebSocket management ───────────────────────────

  /**
   * Open a WebSocket and wire event handlers.
   *
   * Resolves when the connection opens; rejects on error/close before open.
   */
  private connect(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      this.setState("connecting");

      try {
        this.ws = new WebSocket(this.config.wsUrl);
        this.ws.binaryType = "arraybuffer";
      } catch (err) {
        this.setState("error");
        reject(err);
        return;
      }

      this.ws.onopen = () => {
        this.reconnectDelay = BACKOFF_INITIAL_MS;
        resolve();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        this.handleMessage(event);
      };

      this.ws.onerror = () => {
        // onerror fires before onclose — rejection handled in onclose
      };

      this.ws.onclose = () => {
        const wasConnecting = this._state === "connecting";
        this.setState("error");

        if (wasConnecting) {
          reject(new Error("WebSocket connection failed"));
        }

        this.scheduleReconnect();
      };
    });
  }

  /** Parse incoming JSON detection events. */
  private handleMessage(event: MessageEvent): void {
    if (typeof event.data !== "string") return;

    try {
      const payload = JSON.parse(event.data) as DetectionEvent;
      if (payload.event === "detected") {
        this.setState("detected");
        this.fireDetected({
          model: payload.model,
          score: payload.score,
        });

        // Return to listening state after brief detection indicator
        setTimeout(() => {
          if (this._state === "detected") {
            this.setState("listening");
          }
        }, 500);
      }
    } catch {
      // Ignore malformed messages
    }
  }

  /** Send sensitivity config to the backend. */
  private sendSensitivity(): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        command: "set_sensitivity",
        value: this.config.sensitivity,
      }),
    );
  }

  /** Close the WebSocket connection. */
  private closeWebSocket(): void {
    if (this.ws) {
      // Remove handlers to prevent reconnect from onclose
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;

      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  // ── Reconnection ───────────────────────────────────

  /** Schedule a reconnection attempt with exponential backoff. */
  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;

    this.clearReconnectTimer();

    this.reconnectTimer = setTimeout(() => {
      if (!this.shouldReconnect) return;

      this.connect().catch(() => {
        // Connection failed — next scheduleReconnect handles backoff
      });
    }, this.reconnectDelay);

    // Increase delay for next attempt
    this.reconnectDelay = Math.min(
      this.reconnectDelay * BACKOFF_MULTIPLIER,
      BACKOFF_MAX_MS,
    );
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // ── Audio pipeline ─────────────────────────────────

  /**
   * Set up microphone → AudioWorklet → WebSocket pipeline.
   *
   * Tries AudioWorklet first (modern browsers); falls back to
   * ScriptProcessorNode for older environments.
   */
  private async startAudioCapture(): Promise<void> {
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: { ideal: 16000 },
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    this.audioContext = new AudioContext();
    this.sourceNode = this.audioContext.createMediaStreamSource(
      this.mediaStream,
    );

    try {
      await this.setupAudioWorklet();
    } catch {
      this.setupScriptProcessor();
    }
  }

  /**
   * Set up AudioWorklet-based resampling pipeline.
   *
   * Loads the worklet module, creates a node, and wires the message
   * port to forward PCM frames over the WebSocket.
   */
  private async setupAudioWorklet(): Promise<void> {
    if (!this.audioContext || !this.sourceNode) {
      throw new Error("AudioContext not ready");
    }

    // Resolve worklet URL — works with Vite's URL import or relative path
    const workletUrl = new URL(
      "./audio-processor.worklet.ts",
      import.meta.url,
    ).href;

    await this.audioContext.audioWorklet.addModule(workletUrl);

    this.workletNode = new AudioWorkletNode(
      this.audioContext,
      "pcm-resampler",
    );

    this.workletNode.port.onmessage = (event: MessageEvent) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(event.data as ArrayBuffer);
      }
    };

    this.sourceNode.connect(this.workletNode);
    // Connect to destination to keep the audio graph alive
    this.workletNode.connect(this.audioContext.destination);
  }

  /**
   * Fallback: ScriptProcessorNode for browsers without AudioWorklet.
   *
   * Performs the same resampling (linear interpolation → 16 kHz int16)
   * in the main thread. Deprecated API but widely supported.
   */
  private setupScriptProcessor(): void {
    if (!this.audioContext || !this.sourceNode) return;

    const bufferSize = 4096;
    const samplesPerFrame = 1280;
    this.scriptProcessor = this.audioContext.createScriptProcessor(
      bufferSize,
      1,
      1,
    );

    this._spResampleRatio = this.audioContext.sampleRate / 16000;
    this._spBuffer = new Int16Array(samplesPerFrame);
    this._spOffset = 0;

    this.scriptProcessor.onaudioprocess = (
      event: AudioProcessingEvent,
    ) => {
      const input = event.inputBuffer.getChannelData(0);
      this.resampleAndSend(input);
    };

    this.sourceNode.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.audioContext.destination);
  }

  /**
   * Resample float32 audio and send complete frames over WebSocket.
   *
   * Used by the ScriptProcessorNode fallback path.
   */
  private resampleAndSend(source: Float32Array): void {
    const ratio = this._spResampleRatio;
    const srcLen = source.length;
    const outputCount = Math.floor(srcLen / ratio);
    const samplesPerFrame = 1280;

    for (let i = 0; i < outputCount; i++) {
      const srcIndex = i * ratio;
      const idx = Math.floor(srcIndex);
      const frac = srcIndex - idx;

      const s0 = source[idx] ?? 0;
      const s1 = source[Math.min(idx + 1, srcLen - 1)] ?? 0;
      const interpolated = s0 + frac * (s1 - s0);

      const clamped = Math.max(-1, Math.min(1, interpolated));
      this._spBuffer[this._spOffset++] = Math.round(clamped * 32767);

      if (this._spOffset >= samplesPerFrame) {
        this.sendPCMFrame(this._spBuffer);
        this._spBuffer = new Int16Array(samplesPerFrame);
        this._spOffset = 0;
      }
    }
  }

  /** Send a completed PCM frame to the backend. */
  private sendPCMFrame(frame: Int16Array): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(frame.buffer);
    }
  }

  /** Release microphone and audio resources. */
  private stopAudioCapture(): void {
    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      this.workletNode.disconnect();
      this.workletNode = null;
    }

    if (this.scriptProcessor) {
      this.scriptProcessor.onaudioprocess = null;
      this.scriptProcessor.disconnect();
      this.scriptProcessor = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }

    if (this.mediaStream) {
      for (const track of this.mediaStream.getTracks()) {
        track.stop();
      }
      this.mediaStream = null;
    }

    if (this.audioContext) {
      void this.audioContext.close();
      this.audioContext = null;
    }
  }

  // ── Internal helpers ───────────────────────────────

  private setState(state: BackendWakeWordState): void {
    if (state === this._state) return;
    this._state = state;
    for (const cb of this.stateCallbacks) {
      cb(state);
    }
  }

  private fireDetected(payload: DetectionPayload): void {
    for (const cb of this.detectedCallbacks) {
      cb(payload);
    }
  }
}
