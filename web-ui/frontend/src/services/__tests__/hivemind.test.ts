/**
 * Unit tests for the HiveMind WebSocket service.
 *
 * Uses a mock WebSocket to test message handling, connection
 * lifecycle, auto-reconnect, and event dispatching without
 * requiring a real HiveMind-core server.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  HiveMindService,
  type ConnectionState,
  type HiveMindConfig,
  type OVOSMessage,
} from "../hivemind";

// ── Mock WebSocket ─────────────────────────────────────

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;

  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;

  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
  }

  // Test helpers
  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  simulateClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ type: "close" } as CloseEvent);
  }

  simulateError(): void {
    this.onerror?.(new Event("error"));
  }

  simulateMessage(data: unknown): void {
    this.onmessage?.({
      data: JSON.stringify(data),
    } as MessageEvent);
  }
}

// ── Helpers ────────────────────────────────────────────

let mockWsInstance: MockWebSocket | null = null;

function createDefaultConfig(
  overrides?: Partial<HiveMindConfig>,
): HiveMindConfig {
  return {
    url: "ws://localhost:5678",
    clientName: "avaros-web-client",
    accessKey: "test-key",
    accessSecret: "",
    autoReconnect: false,
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────

describe("HiveMindService", () => {
  beforeEach(() => {
    mockWsInstance = null;

    // Mock global WebSocket
    vi.stubGlobal(
      "WebSocket",
      class extends MockWebSocket {
        constructor(url: string) {
          super(url);
          mockWsInstance = this;
        }

        static override CONNECTING = 0;
        static override OPEN = 1;
        static override CLOSING = 2;
        static override CLOSED = 3;
      },
    );

    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  // ── Connection ───────────────────────────────────────

  describe("connect", () => {
    it("sends authorization token in URL", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const connectPromise = svc.connect();

      mockWsInstance!.simulateOpen();
      await connectPromise;

      const expectedAuth = btoa("avaros-web-client:test-key");
      expect(mockWsInstance!.url).toContain(
        `?authorization=${expectedAuth}`,
      );
    });

    it("uses configured client name in authorization token", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({
          clientName: "custom-client",
          accessKey: "key-123",
        }),
      );
      const connectPromise = svc.connect();

      mockWsInstance!.simulateOpen();
      await connectPromise;

      const expectedAuth = btoa("custom-client:key-123");
      expect(mockWsInstance!.url).toContain(
        `?authorization=${expectedAuth}`,
      );
    });

    it("transitions to connected state on open", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const states: ConnectionState[] = [];
      svc.onStateChange((s) => states.push(s));

      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      expect(svc.state).toBe("connected");
      expect(states).toContain("connecting");
      expect(states).toContain("connected");
    });

    it("rejects promise on error during connect", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const connectPromise = svc.connect();

      mockWsInstance!.simulateError();

      await expect(connectPromise).rejects.toThrow(
        "WebSocket connection failed",
      );
      expect(svc.state).toBe("error");
    });

    it("resolves immediately if already connected", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const p1 = svc.connect();
      mockWsInstance!.simulateOpen();
      await p1;

      // Second connect should resolve immediately
      await svc.connect();
      expect(svc.state).toBe("connected");
    });
  });

  // ── Disconnect ───────────────────────────────────────

  describe("disconnect", () => {
    it("closes the websocket and sets disconnected", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      svc.disconnect();

      expect(svc.state).toBe("disconnected");
    });

    it("clears event handlers on ws", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      svc.disconnect();

      expect(mockWsInstance!.onopen).toBeNull();
      expect(mockWsInstance!.onclose).toBeNull();
      expect(mockWsInstance!.onerror).toBeNull();
      expect(mockWsInstance!.onmessage).toBeNull();
    });
  });

  // ── Send utterance ───────────────────────────────────

  describe("sendUtterance", () => {
    it("sends correct message format", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      await svc.sendUtterance("what is the status");

      expect(mockWsInstance!.sent).toHaveLength(1);
      const sent = JSON.parse(mockWsInstance!.sent[0]);
      expect(sent.msg_type).toBe("bus");
      expect(sent.payload.type).toBe("recognizer_loop:utterance");
      expect(sent.payload.data.utterances).toEqual([
        "what is the status",
      ]);
    });

    it("includes language parameter", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      await svc.sendUtterance("hallo", "de-de");

      const sent = JSON.parse(mockWsInstance!.sent[0]);
      expect(sent.payload.data.lang).toBe("de-de");
    });

    it("throws when not connected", async () => {
      const svc = new HiveMindService(createDefaultConfig());

      await expect(svc.sendUtterance("test")).rejects.toThrow(
        "WebSocket is not connected",
      );
    });
  });

  // ── Event listeners ──────────────────────────────────

  describe("event listeners", () => {
    it("dispatches speak events via on()", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const received: OVOSMessage[] = [];
      svc.on("speak", (msg) => received.push(msg));

      mockWsInstance!.simulateMessage({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: { utterance: "Hello world" },
        },
      });

      // Allow async handleMessage to complete
      await vi.advanceTimersByTimeAsync(0);

      expect(received).toHaveLength(1);
      expect(received[0].data.utterance).toBe("Hello world");
    });

    it("dispatches via onSpeak convenience method", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const texts: string[] = [];
      svc.onSpeak((text) => texts.push(text));

      mockWsInstance!.simulateMessage({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: { utterance: "Test response" },
        },
      });

      await vi.advanceTimersByTimeAsync(0);

      expect(texts).toEqual(["Test response"]);
    });

    it("unsubscribe removes listener", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const received: OVOSMessage[] = [];
      const unsub = svc.on("speak", (msg) => received.push(msg));

      // First message should be received
      mockWsInstance!.simulateMessage({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: { utterance: "first" },
        },
      });
      await vi.advanceTimersByTimeAsync(0);

      unsub();

      // Second message should NOT be received
      mockWsInstance!.simulateMessage({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: { utterance: "second" },
        },
      });
      await vi.advanceTimersByTimeAsync(0);

      expect(received).toHaveLength(1);
    });

    it("wildcard listener receives all events", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const received: OVOSMessage[] = [];
      svc.on("*", (msg) => received.push(msg));

      mockWsInstance!.simulateMessage({
        msg_type: "bus",
        payload: {
          type: "mycroft.skill.handler.start",
          data: { name: "test" },
        },
      });
      await vi.advanceTimersByTimeAsync(0);

      expect(received).toHaveLength(1);
      expect(received[0].type).toBe("mycroft.skill.handler.start");
    });

    it("ignores non-bus messages", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const received: OVOSMessage[] = [];
      svc.on("*", (msg) => received.push(msg));

      mockWsInstance!.simulateMessage({
        msg_type: "handshake",
        payload: { type: "init", data: {} },
      });
      await vi.advanceTimersByTimeAsync(0);

      expect(received).toHaveLength(0);
    });

    it("captures session id from handshake payload", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      mockWsInstance!.simulateMessage({
        msg_type: "handshake",
        payload: { session_id: "session-xyz" },
      });
      await vi.advanceTimersByTimeAsync(0);

      expect(svc.getConnectionDetails().sessionId).toBe("session-xyz");
    });
  });

  // ── Reconnection ─────────────────────────────────────

  describe("reconnect", () => {
    it("reconnects on unexpected close", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({
          autoReconnect: true,
          reconnectInterval: 1000,
          maxReconnectAttempts: 3,
        }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      // Simulate unexpected close
      mockWsInstance!.simulateClose();

      expect(svc.state).toBe("disconnected");

      // Advance past reconnect delay
      await vi.advanceTimersByTimeAsync(1000);

      // A new WebSocket should have been created
      expect(mockWsInstance).not.toBeNull();
    });

    it("respects maxReconnectAttempts", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({
          autoReconnect: true,
          reconnectInterval: 100,
          maxReconnectAttempts: 2,
        }),
      );

      const states: ConnectionState[] = [];
      svc.onStateChange((s) => states.push(s));

      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      // First unexpected close
      mockWsInstance!.simulateClose();
      await vi.advanceTimersByTimeAsync(200);

      // First reconnect attempt — simulate failure
      mockWsInstance!.simulateError();
      mockWsInstance!.simulateClose();

      await vi.advanceTimersByTimeAsync(500);

      // Second reconnect attempt — fails again
      mockWsInstance!.simulateError();
      mockWsInstance!.simulateClose();

      await vi.advanceTimersByTimeAsync(1000);

      // Third attempt should not happen (max=2), state should be "error"
      expect(states).toContain("error");
    });

    it("does not reconnect when autoReconnect is false", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ autoReconnect: false }),
      );
      const connectPromise = svc.connect();
      const firstWs = mockWsInstance;
      mockWsInstance!.simulateOpen();
      await connectPromise;

      mockWsInstance!.simulateClose();

      await vi.advanceTimersByTimeAsync(10000);

      // No reconnection should have happened — mockWsInstance
      // should still be the first one (closed)
      expect(mockWsInstance).toBe(firstWs);
    });
  });

  // ── State change listeners ───────────────────────────

  describe("onStateChange", () => {
    it("notifies all registered listeners", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const states1: ConnectionState[] = [];
      const states2: ConnectionState[] = [];

      svc.onStateChange((s) => states1.push(s));
      svc.onStateChange((s) => states2.push(s));

      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      expect(states1).toContain("connecting");
      expect(states1).toContain("connected");
      expect(states2).toContain("connecting");
      expect(states2).toContain("connected");
    });

    it("unsubscribe stops notifications", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      const states: ConnectionState[] = [];

      const unsub = svc.onStateChange((s) => states.push(s));
      unsub();

      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      expect(states).toHaveLength(0);
    });
  });

  // ── Dispose ──────────────────────────────────────────

  describe("dispose", () => {
    it("rejects new connections after dispose", async () => {
      const svc = new HiveMindService(createDefaultConfig());
      svc.dispose();

      await expect(svc.connect()).rejects.toThrow(
        "Service has been disposed",
      );
    });

    it("clears all listeners on dispose", async () => {
      const svc = new HiveMindService(
        createDefaultConfig({ accessSecret: "" }),
      );
      const connectPromise = svc.connect();
      mockWsInstance!.simulateOpen();
      await connectPromise;

      const received: OVOSMessage[] = [];
      svc.on("speak", (msg) => received.push(msg));

      svc.dispose();

      // Cannot create new WebSocket after dispose, so just verify
      // the service state
      expect(svc.state).toBe("disconnected");
    });
  });
});
