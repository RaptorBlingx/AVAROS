/**
 * HiveMind WebSocket client service for AVAROS.
 *
 * Implements the HiveMind protocol for browser-to-OVOS communication
 * via HiveMind-core. Handles connection lifecycle, authentication,
 * message routing, auto-reconnect with exponential backoff, and
 * AES-GCM encryption.
 *
 * Protocol reference: JarbasHiveMind/HiveMind-js (static/js/hivemind.js)
 */

// ── Types ──────────────────────────────────────────────

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export interface HiveMindConfig {
  /** WebSocket URL, e.g. ws://localhost:5678 or wss://host/hivemind */
  url: string;
  /** Client name from HiveMind credential store */
  clientName?: string;
  /** Client access key from HiveMind credential store */
  accessKey: string;
  /** Client crypto/secret key (used for AES-GCM encryption) */
  accessSecret: string;
  /** Whether to auto-reconnect on close (default: true) */
  autoReconnect?: boolean;
  /** Base reconnect interval in ms (default: 2000) */
  reconnectInterval?: number;
  /** Max reconnect attempts before giving up (default: 8) */
  maxReconnectAttempts?: number;
}

export interface OVOSMessage {
  type: string;
  data: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface HiveMindConnectionDetails {
  url: string;
  latencyMs: number | null;
  sessionId: string | null;
}

interface HiveMindEnvelope {
  msg_type: string;
  payload: OVOSMessage;
}

interface EncryptedEnvelope {
  ciphertext: string;
  nonce: string;
  tag?: string;
}

type MessageCallback = (msg: OVOSMessage) => void;
type StateCallback = (state: ConnectionState) => void;

// ── Crypto helpers ─────────────────────────────────────

async function importSecretKey(
  rawKey: string,
): Promise<CryptoKey> {
  const encoded = new TextEncoder().encode(rawKey);
  return crypto.subtle.importKey("raw", encoded, "AES-GCM", false, [
    "encrypt",
    "decrypt",
  ]);
}

function hexToBytes(hex: string): Uint8Array {
  const matches = hex.match(/.{1,2}/g);
  if (!matches) return new Uint8Array(0);
  return new Uint8Array(matches.map((b) => parseInt(b, 16)));
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function encryptMessage(
  text: string,
  secretKey: string,
): Promise<EncryptedEnvelope> {
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const key = await importSecretKey(secretKey);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(text),
  );
  return {
    nonce: bytesToHex(iv),
    ciphertext: bytesToHex(new Uint8Array(ciphertext)),
  };
}

async function decryptMessage(
  hexCiphertext: string,
  hexIv: string,
  secretKey: string,
): Promise<string> {
  const ivBytes = hexToBytes(hexIv);
  const iv = new Uint8Array(ivBytes.buffer.slice(0)) as Uint8Array & { buffer: ArrayBuffer };
  const key = await importSecretKey(secretKey);
  const ciphertextBytes = hexToBytes(hexCiphertext);
  const data = new Uint8Array(ciphertextBytes.buffer.slice(0)) as Uint8Array & { buffer: ArrayBuffer };
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    data,
  );
  return new TextDecoder().decode(decrypted);
}

// ── Service ────────────────────────────────────────────

export class HiveMindService {
  private ws: WebSocket | null = null;
  private config: HiveMindConfig;
  private _state: ConnectionState = "disconnected";
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private eventListeners = new Map<string, Set<MessageCallback>>();
  private stateListeners = new Set<StateCallback>();
  private disposed = false;
  private connectStartedAt: number | null = null;
  private connectionLatencyMs: number | null = null;
  private sessionId: string | null = null;

  constructor(config: HiveMindConfig) {
    this.config = {
      clientName: "avaros-web-client",
      autoReconnect: true,
      reconnectInterval: 2000,
      maxReconnectAttempts: 8,
      ...config,
    };
  }

  // ── Connection lifecycle ─────────────────────────────

  get state(): ConnectionState {
    return this._state;
  }

  connect(): Promise<void> {
    if (this.disposed) {
      return Promise.reject(new Error("Service has been disposed"));
    }
    if (this.ws?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      this.setState("connecting");
      this.connectStartedAt = Date.now();

      const authToken = btoa(
        `${this.config.clientName}:${this.config.accessKey}`,
      );
      const wsUrl = `${this.config.url}?authorization=${authToken}`;

      try {
        this.ws = new WebSocket(wsUrl);
      } catch (err) {
        this.setState("error");
        reject(err);
        return;
      }

      this.ws.onopen = () => {
        if (this.connectStartedAt !== null) {
          this.connectionLatencyMs = Date.now() - this.connectStartedAt;
        }
        this.connectStartedAt = null;
        this.reconnectAttempts = 0;
        this.setState("connected");
        resolve();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        void this.handleMessage(event);
      };

      this.ws.onerror = () => {
        if (this._state === "connecting") {
          this.setState("error");
          reject(new Error("WebSocket connection failed"));
        }
      };

      this.ws.onclose = () => {
        const wasConnecting = this._state === "connecting";
        this.connectStartedAt = null;
        this.setState("disconnected");
        if (!wasConnecting) {
          this.scheduleReconnect();
        }
      };
    });
  }

  disconnect(): void {
    this.cancelReconnect();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
    this.setState("disconnected");
  }

  dispose(): void {
    this.disposed = true;
    this.disconnect();
    this.eventListeners.clear();
    this.stateListeners.clear();
  }

  getConnectionDetails(): HiveMindConnectionDetails {
    return {
      url: this.config.url,
      latencyMs: this.connectionLatencyMs,
      sessionId: this.sessionId,
    };
  }

  // ── Message sending ──────────────────────────────────

  async sendUtterance(
    text: string,
    lang = "en-us",
  ): Promise<void> {
    const payload: OVOSMessage = {
      type: "recognizer_loop:utterance",
      data: { utterances: [text], lang },
      context: {
        source: "avaros-web-ui",
        destination: "HiveMind",
        platform: "AVAROS-WebUI-v1",
      },
    };
    await this.sendBusMessage(payload);
  }

  async sendBusMessage(payload: OVOSMessage): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected");
    }

    const envelope: HiveMindEnvelope = {
      msg_type: "bus",
      payload,
    };

    if (this.config.accessSecret) {
      const encrypted = await encryptMessage(
        JSON.stringify(envelope),
        this.config.accessSecret,
      );
      this.ws.send(JSON.stringify(encrypted));
    } else {
      this.ws.send(JSON.stringify(envelope));
    }
  }

  // ── Event listening ──────────────────────────────────

  /**
   * Subscribe to an OVOS messagebus event type.
   *
   * Returns an unsubscribe function.
   */
  on(eventType: string, callback: MessageCallback): () => void {
    let listeners = this.eventListeners.get(eventType);
    if (!listeners) {
      listeners = new Set();
      this.eventListeners.set(eventType, listeners);
    }
    listeners.add(callback);

    return () => {
      listeners?.delete(callback);
      if (listeners?.size === 0) {
        this.eventListeners.delete(eventType);
      }
    };
  }

  /**
   * Convenience: subscribe to ``speak`` events.
   *
   * Returns an unsubscribe function.
   */
  onSpeak(
    callback: (
      text: string,
      metadata?: Record<string, unknown>,
    ) => void,
  ): () => void {
    return this.on("speak", (msg) => {
      const utterance = msg.data.utterance as string | undefined;
      if (utterance !== undefined) {
        callback(utterance, msg.data);
      }
    });
  }

  /**
   * Subscribe to connection state changes.
   *
   * Returns an unsubscribe function.
   */
  onStateChange(callback: StateCallback): () => void {
    this.stateListeners.add(callback);
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  // ── Internal ─────────────────────────────────────────

  private async handleMessage(event: MessageEvent): Promise<void> {
    let parsed: unknown;
    try {
      parsed = JSON.parse(event.data as string);
    } catch {
      return; // ignore non-JSON messages
    }

    const envelope = parsed as Record<string, unknown>;

    // Handle encrypted messages
    if (
      this.config.accessSecret &&
      typeof envelope.ciphertext === "string"
    ) {
      try {
        const ciphertext = envelope.tag
          ? (envelope.ciphertext as string) + (envelope.tag as string)
          : (envelope.ciphertext as string);
        const decrypted = await decryptMessage(
          ciphertext,
          envelope.nonce as string,
          this.config.accessSecret,
        );
        parsed = JSON.parse(decrypted);
      } catch {
        return; // decryption failed — skip
      }
    }

    this.updateSessionId(parsed);

    const msg = parsed as HiveMindEnvelope;

    if (msg.msg_type === "bus" && msg.payload) {
      this.dispatchEvent(msg.payload);
    }
  }

  private updateSessionId(envelope: unknown): void {
    const root = envelope as Record<string, unknown>;
    const payload =
      (root.payload as Record<string, unknown> | undefined) ?? {};
    const payloadContext =
      (payload.context as Record<string, unknown> | undefined) ?? {};

    const candidate =
      payloadContext.session_id ??
      payloadContext.session ??
      payload.session_id ??
      payload.session ??
      root.session_id ??
      root.session;

    if (typeof candidate === "string" && candidate.length > 0) {
      this.sessionId = candidate;
    }
  }

  private dispatchEvent(message: OVOSMessage): void {
    // Notify specific event listeners
    const listeners = this.eventListeners.get(message.type);
    if (listeners) {
      for (const cb of listeners) {
        try {
          cb(message);
        } catch {
          // listener error should not break dispatch
        }
      }
    }

    // Also notify wildcard listeners
    const wildcardListeners = this.eventListeners.get("*");
    if (wildcardListeners) {
      for (const cb of wildcardListeners) {
        try {
          cb(message);
        } catch {
          // listener error should not break dispatch
        }
      }
    }
  }

  private setState(newState: ConnectionState): void {
    if (this._state === newState) return;
    this._state = newState;
    for (const cb of this.stateListeners) {
      try {
        cb(newState);
      } catch {
        // state listener error should not break state transition
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.disposed) return;
    if (!this.config.autoReconnect) return;
    if (
      this.reconnectAttempts >=
      (this.config.maxReconnectAttempts ?? 8)
    ) {
      this.setState("error");
      return;
    }

    const baseInterval = this.config.reconnectInterval ?? 2000;
    // Exponential backoff: 2s, 4s, 8s, 16s... capped at 30s
    const delay = Math.min(
      baseInterval * Math.pow(2, this.reconnectAttempts),
      30_000,
    );
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      if (this.disposed) return;
      void this.connect().catch(() => {
        // connect rejection already triggers onclose → scheduleReconnect
      });
    }, delay);
  }

  private cancelReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }
}
