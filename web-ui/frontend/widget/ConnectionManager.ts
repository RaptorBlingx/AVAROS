import type { WidgetConnectionState } from "./types";

type BusMessage = {
  type: string;
  data: Record<string, unknown>;
  context?: Record<string, unknown>;
};

type HiveMindEnvelope = {
  msg_type: string;
  payload?: unknown;
};

type EncryptedEnvelope = {
  ciphertext: string;
  nonce: string;
  tag?: string;
};

type StateListener = (state: WidgetConnectionState) => void;
type SpeakListener = (text: string) => void;
type EventListener = (message: BusMessage) => void;

const DEFAULT_SESSION_SITE = "default";
const MAX_RECONNECT_DELAY_MS = 30000;

function makeSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `widget-${Date.now()}`;
}

function tryJsonParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractSpeakText(payload: unknown): string | null {
  if (!isBusMessage(payload)) return null;
  if (payload.type !== "speak") return null;
  const text = payload.data.utterance;
  return typeof text === "string" && text.trim() ? text : null;
}

function isBusMessage(payload: unknown): payload is BusMessage {
  if (!payload || typeof payload !== "object") return false;
  const message = payload as { type?: unknown; data?: unknown };
  return typeof message.type === "string" && Boolean(message.data && typeof message.data === "object");
}

function makePaddingSafeUserAgent(name: string, key: string): string {
  const baseName = name.trim() || "widget";
  const totalLen = baseName.length + 1 + key.length; // "<name>:<key>"
  const remainder = totalLen % 3;
  if (remainder === 0) return baseName;
  return `${baseName}${"x".repeat(3 - remainder)}`;
}

async function importSecretKey(rawKey: string): Promise<CryptoKey> {
  const encoded = new TextEncoder().encode(rawKey);
  return crypto.subtle.importKey("raw", encoded, "AES-GCM", false, ["decrypt"]);
}

function hexToBytes(hex: string): Uint8Array {
  const matches = hex.match(/.{1,2}/g);
  if (!matches) return new Uint8Array(0);
  return new Uint8Array(matches.map((byte) => parseInt(byte, 16)));
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function decryptMessage(
  hexCiphertext: string,
  hexNonce: string,
  secretKey: string,
): Promise<string> {
  const nonceBytes = hexToBytes(hexNonce);
  const nonce = new Uint8Array(nonceBytes.buffer.slice(0)) as Uint8Array & {
    buffer: ArrayBuffer;
  };
  const cipherBytes = hexToBytes(hexCiphertext);
  const ciphertext = new Uint8Array(cipherBytes.buffer.slice(0)) as Uint8Array & {
    buffer: ArrayBuffer;
  };
  const key = await importSecretKey(secretKey);
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    ciphertext,
  );
  return new TextDecoder().decode(decrypted);
}

function normalizeWsHost(rawHost: string): string {
  const host = rawHost.trim();
  if (!host) return host;

  if (host.startsWith("ws://") || host.startsWith("wss://")) {
    return host;
  }
  if (host.startsWith("http://")) {
    return `ws://${host.slice("http://".length)}`;
  }
  if (host.startsWith("https://")) {
    return `wss://${host.slice("https://".length)}`;
  }
  if (host.startsWith("//")) {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}${host}`;
  }

  // If scheme is omitted, assume ws://.
  return `ws://${host}`;
}

export class ConnectionManager {
  private ws: WebSocket | null = null;
  private state: WidgetConnectionState = "disconnected";
  private readonly host: string;
  private readonly clientName: string;
  private readonly accessKey: string;
  private readonly accessSecret: string;
  private readonly encryptionKey: string;
  private readonly sessionId = makeSessionId();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private readonly stateListeners = new Set<StateListener>();
  private readonly speakListeners = new Set<SpeakListener>();
  private readonly eventListeners = new Map<string, Set<EventListener>>();
  private decryptionKeysPromise: Promise<string[]> | null = null;
  private disposed = false;
  private helloSent = false;

  constructor(
    host: string,
    clientName: string,
    accessKey: string,
    accessSecret = "",
    encryptionKey = "",
  ) {
    this.host = host;
    this.clientName = clientName;
    this.accessKey = accessKey;
    this.accessSecret = accessSecret;
    this.encryptionKey = encryptionKey;
  }

  onState(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => this.stateListeners.delete(listener);
  }

  onSpeak(listener: SpeakListener): () => void {
    this.speakListeners.add(listener);
    return () => this.speakListeners.delete(listener);
  }

  on(eventType: string, listener: EventListener): () => void {
    const listeners = this.eventListeners.get(eventType) ?? new Set<EventListener>();
    listeners.add(listener);
    this.eventListeners.set(eventType, listeners);
    return () => {
      const existing = this.eventListeners.get(eventType);
      if (!existing) return;
      existing.delete(listener);
      if (existing.size === 0) {
        this.eventListeners.delete(eventType);
      }
    };
  }

  isConnected(): boolean {
    return this.state === "connected";
  }

  getState(): WidgetConnectionState {
    return this.state;
  }

  connect(): void {
    if (this.disposed) return;
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.cancelReconnect();
    this.setState("connecting");

    const candidateUrls = this.buildWebSocketUrls();

    const tryConnect = (urlIndex: number): void => {
      const wsUrl = candidateUrls[urlIndex];
      if (!wsUrl) {
        this.ws = null;
        this.setState("error");
        this.scheduleReconnect();
        return;
      }

      let advanced = false;
      const advanceToNextUrl = (): void => {
        if (advanced || this.state !== "connecting") return;
        advanced = true;
        this.ws = null;
        tryConnect(urlIndex + 1);
      };

      try {
        this.ws = new WebSocket(wsUrl);
      } catch {
        advanceToNextUrl();
        return;
      }

      this.ws.onopen = () => {
        this.reconnectAttempt = 0;
        this.helloSent = false;
        this.setState("connected");
        this.sendHello();
      };

      this.ws.onmessage = (event) => {
        void this.handleMessage(String(event.data));
      };

      this.ws.onerror = () => {
        if (this.state === "connecting") {
          advanceToNextUrl();
        }
      };

      this.ws.onclose = (event) => {
        const wasConnecting = this.state === "connecting";
        this.ws = null;
        this.helloSent = false;

        if (this.disposed) {
          this.setState("disconnected");
          return;
        }

        if (wasConnecting) {
          advanceToNextUrl();
          return;
        }

        if (event.code === 1008 || event.code === 4001 || event.code === 4003) {
          this.setState("error");
          return;
        }

        this.setState("disconnected");
        this.scheduleReconnect();
      };
    };

    tryConnect(0);
  }

  disconnect(): void {
    this.cancelReconnect();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      if (
        this.ws.readyState === WebSocket.CONNECTING ||
        this.ws.readyState === WebSocket.OPEN
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
    this.helloSent = false;
    this.setState("disconnected");
  }

  destroy(): void {
    this.disposed = true;
    this.disconnect();
    this.stateListeners.clear();
    this.speakListeners.clear();
    this.eventListeners.clear();
  }

  async sendUtterance(text: string): Promise<void> {
    const cleaned = text.trim();
    if (!cleaned) return;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected");
    }

    const busMessage: BusMessage = {
      type: "recognizer_loop:utterance",
      data: {
        utterances: [cleaned],
        lang: "en-us",
      },
      context: {
        source: "avaros-widget",
        platform: "AVAROS-Widget-v1",
        session: {
          session_id: this.sessionId,
          site_id: DEFAULT_SESSION_SITE,
        },
      },
    };

    const envelope: HiveMindEnvelope = {
      msg_type: "bus",
      payload: busMessage,
    };
    this.ws.send(JSON.stringify(envelope));
  }

  private sendHello(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || this.helloSent) {
      return;
    }

    const envelope: HiveMindEnvelope = {
      msg_type: "hello",
      payload: {
        site_id: DEFAULT_SESSION_SITE,
        session: {
          session_id: this.sessionId,
          site_id: DEFAULT_SESSION_SITE,
          lang: "en-us",
          context: {},
          active_skills: [],
          utterance_states: {},
        },
      },
    };

    this.ws.send(JSON.stringify(envelope));
    this.helloSent = true;
  }

  private async handleMessage(raw: string): Promise<void> {
    const parsed = tryJsonParse(raw);
    if (!isRecord(parsed)) return;

    let payloadEnvelope: unknown = parsed;
    if (typeof parsed.ciphertext === "string") {
      const encrypted = parsed as EncryptedEnvelope;
      const nonce = typeof encrypted.nonce === "string" ? encrypted.nonce : "";
      if (!nonce) return;
      const ciphertext = encrypted.tag
        ? `${encrypted.ciphertext}${encrypted.tag}`
        : encrypted.ciphertext;
      const keys = await this.getDecryptionKeys();
      let decryptedPayload: string | null = null;

      for (const key of keys) {
        try {
          decryptedPayload = await decryptMessage(ciphertext, nonce, key);
          break;
        } catch {
          // Try next key candidate.
        }
      }

      if (!decryptedPayload) return;
      payloadEnvelope = tryJsonParse(decryptedPayload);
      if (!isRecord(payloadEnvelope)) return;
    }

    const envelope = payloadEnvelope as HiveMindEnvelope;
    if (envelope.msg_type === "hello" && !this.helloSent) {
      this.sendHello();
      return;
    }

    if (envelope.msg_type !== "bus") return;
    if (isBusMessage(envelope.payload)) {
      this.dispatchEvent(envelope.payload);
    }
    const speakText = extractSpeakText(envelope.payload);
    if (!speakText) return;

    this.speakListeners.forEach((listener) => {
      try {
        listener(speakText);
      } catch {
        // Listener errors must not break dispatch.
      }
    });
  }

  private async getDecryptionKeys(): Promise<string[]> {
    if (this.decryptionKeysPromise) {
      return this.decryptionKeysPromise;
    }

    this.decryptionKeysPromise = (async () => {
      const keys = new Set<string>();
      const configured = this.encryptionKey.trim();
      const secret = this.accessSecret.trim();

      const pushIfAesLength = (value: string): void => {
        if (value.length === 16 || value.length === 24 || value.length === 32) {
          keys.add(value);
        }
      };

      pushIfAesLength(configured);
      pushIfAesLength(secret);

      if (secret.length >= 16) {
        keys.add(secret.slice(0, 16));
      }

      if (secret.length > 0) {
        const digest = await crypto.subtle.digest(
          "SHA-256",
          new TextEncoder().encode(secret),
        );
        const digestHex = bytesToHex(new Uint8Array(digest));
        keys.add(digestHex.slice(0, 16));
      }

      return Array.from(keys);
    })();

    return this.decryptionKeysPromise;
  }

  private dispatchEvent(message: BusMessage): void {
    const listeners = this.eventListeners.get(message.type);
    if (listeners) {
      listeners.forEach((listener) => {
        try {
          listener(message);
        } catch {
          // Listener errors must not break dispatch.
        }
      });
    }
  }

  private buildWebSocketUrls(): string[] {
    const normalizedHost = normalizeWsHost(this.host);
    const baseUrls = [normalizedHost];

    try {
      const parsed = new URL(normalizedHost);
      if (parsed.hostname === "localhost") {
        const fallback = new URL(normalizedHost);
        fallback.hostname = "127.0.0.1";
        baseUrls.push(fallback.toString());
      } else if (parsed.hostname === "127.0.0.1") {
        const fallback = new URL(normalizedHost);
        fallback.hostname = "localhost";
        baseUrls.push(fallback.toString());
      }
    } catch {
      // Keep original URL only.
    }

    const normalizedAccessKey = this.accessKey.trim();
    if (!normalizedAccessKey) return baseUrls;

    // HiveMind expects "<useragent>:<api_key>" where second part is api_key.
    // Because this HiveMind build does not URL-decode auth query params,
    // we prefer a useragent length that produces base64 without '=' padding.
    const preferredUserAgent = makePaddingSafeUserAgent(
      this.clientName,
      normalizedAccessKey,
    );
    const userAgents = new Set<string>([preferredUserAgent, this.clientName, "widget"]);

    const urls = new Set<string>();
    baseUrls.forEach((url) => {
      userAgents.forEach((userAgent) => {
        const authInput = `${userAgent}:${normalizedAccessKey}`;
        const authToken = btoa(authInput);
        const separator = url.includes("?") ? "&" : "?";
        urls.add(`${url}${separator}authorization=${authToken}`);
      });
    });

    return Array.from(urls);
  }

  private setState(nextState: WidgetConnectionState): void {
    if (this.state === nextState) return;
    this.state = nextState;
    this.stateListeners.forEach((listener) => {
      try {
        listener(nextState);
      } catch {
        // Listener errors must not break state transitions.
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.disposed) return;
    this.cancelReconnect();
    this.setState("disconnected");

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempt), MAX_RECONNECT_DELAY_MS);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private cancelReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
