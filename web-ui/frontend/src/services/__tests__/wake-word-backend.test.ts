/**
 * Unit tests for BackendWakeWordService.
 *
 * Mocks WebSocket, getUserMedia, AudioContext, and AudioWorklet to test
 * the lifecycle, detection events, reconnection logic, and cleanup.
 */

// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  BackendWakeWordService,
  type BackendWakeWordState,
} from "../wake-word-backend";

// ── Mock WebSocket ─────────────────────────────────────

class MockWebSocket {
  static CONNECTING = 0 as const;
  static OPEN = 1 as const;
  static CLOSING = 2 as const;
  static CLOSED = 3 as const;

  readonly CONNECTING = 0 as const;
  readonly OPEN = 1 as const;
  readonly CLOSING = 2 as const;
  readonly CLOSED = 3 as const;

  readyState: number = MockWebSocket.CONNECTING;
  binaryType = "blob";
  url: string;
  sentMessages: (string | ArrayBuffer)[] = [];

  onopen: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string | ArrayBuffer): void {
    this.sentMessages.push(data);
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }

  /** Simulate server opening the connection. */
  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.({});
  }

  /** Simulate a message from the server. */
  simulateMessage(data: string): void {
    this.onmessage?.({ data });
  }

  /** Simulate unexpected close. */
  simulateClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }

  /** Track all instances for test access. */
  static instances: MockWebSocket[] = [];
  static reset(): void {
    MockWebSocket.instances = [];
  }

  static lastInstance(): MockWebSocket | undefined {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }
}

// ── Mock Audio APIs ────────────────────────────────────

function createMockMediaStream(): MediaStream {
  const track = {
    stop: vi.fn(),
    kind: "audio",
    enabled: true,
  };
  return {
    getTracks: () => [track],
    getAudioTracks: () => [track],
  } as unknown as MediaStream;
}

function createMockAudioContext(): AudioContext {
  const mockWorkletNode = {
    port: { onmessage: null as ((e: unknown) => void) | null },
    connect: vi.fn(),
    disconnect: vi.fn(),
  };

  const mockSourceNode = {
    connect: vi.fn(),
    disconnect: vi.fn(),
  };

  return {
    sampleRate: 48000,
    createMediaStreamSource: vi.fn().mockReturnValue(mockSourceNode),
    createScriptProcessor: vi.fn().mockReturnValue({
      onaudioprocess: null,
      connect: vi.fn(),
      disconnect: vi.fn(),
    }),
    audioWorklet: {
      addModule: vi.fn().mockRejectedValue(new Error("No AudioWorklet")),
    },
    close: vi.fn().mockResolvedValue(undefined),
    destination: {},
  } as unknown as AudioContext;
}

// ── Test Setup ─────────────────────────────────────────

let service: BackendWakeWordService;

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.reset();

  // Install mock WebSocket globally
  vi.stubGlobal("WebSocket", MockWebSocket);

  // Mock getUserMedia
  vi.stubGlobal("navigator", {
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue(createMockMediaStream()),
    },
  });

  // Mock AudioContext
  vi.stubGlobal("AudioContext", vi.fn().mockImplementation(createMockAudioContext));

  service = new BackendWakeWordService({
    wsUrl: "ws://test:9999/ws/detect",
  });
});

afterEach(() => {
  service.dispose();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ── Tests ──────────────────────────────────────────────

describe("BackendWakeWordService", () => {
  describe("constructor and defaults", () => {
    it("test_default_state_is_idle", () => {
      expect(service.state).toBe("idle");
    });

    it("test_custom_ws_url_is_stored", () => {
      expect(service.getWsUrl()).toBe("ws://test:9999/ws/detect");
    });

    it("test_default_sensitivity", () => {
      expect(service.getSensitivity()).toBe(0.15);
    });

    it("test_model_not_loaded_initially", () => {
      expect(service.isModelLoaded()).toBe(false);
    });

    it("test_not_available_initially", () => {
      expect(service.isAvailable()).toBe(false);
    });
  });

  describe("refreshWakeWordLabel()", () => {
    it("test_skips_cross_origin_health_fetch", async () => {
      vi.stubGlobal("window", {
        location: {
          href: "http://localhost:5173/",
          origin: "http://localhost:5173",
        },
      });
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const localService = new BackendWakeWordService({
        wsUrl: "ws://localhost:9999/ws/detect",
      });

      const label = await localService.refreshWakeWordLabel();
      expect(fetchMock).not.toHaveBeenCalled();
      expect(label).toBe("Hey Avaros");

      localService.dispose();
    });

    it("test_fetches_label_from_same_origin_health_endpoint", async () => {
      vi.stubGlobal("window", {
        location: {
          href: "http://localhost:5173/",
          origin: "http://localhost:5173",
        },
      });
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ models_loaded: ["hey_jarvis"] }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const localService = new BackendWakeWordService({
        wsUrl: "ws://localhost:5173/wakeword/ws/detect",
      });

      const label = await localService.refreshWakeWordLabel();
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:5173/wakeword/health",
        { method: "GET" },
      );
      expect(label).toBe("Hey Jarvis");
      expect(localService.getWakeWordLabel()).toBe("Hey Jarvis");

      localService.dispose();
    });
  });

  describe("initialize()", () => {
    it("test_initialize_connects_websocket", async () => {
      const initPromise = service.initialize();

      // Simulate server accepting connection
      const ws = MockWebSocket.lastInstance();
      expect(ws).toBeDefined();
      expect(ws!.url).toBe("ws://test:9999/ws/detect");
      ws!.simulateOpen();

      await initPromise;

      expect(service.isModelLoaded()).toBe(true);
      expect(service.isAvailable()).toBe(true);
    });

    it("test_initialize_sets_connecting_state", async () => {
      const states: BackendWakeWordState[] = [];
      service.onStateChange((s) => states.push(s));

      const initPromise = service.initialize();
      expect(states).toContain("connecting");

      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;
    });

    it("test_initialize_noop_when_already_connected", async () => {
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      const instanceCount = MockWebSocket.instances.length;

      // Second initialize should be a no-op
      await service.initialize();
      expect(MockWebSocket.instances.length).toBe(instanceCount);
    });

    it("test_initialize_rejects_on_connection_failure", async () => {
      const initPromise = service.initialize();

      // Simulate connection failure
      MockWebSocket.lastInstance()!.simulateClose();

      await expect(initPromise).rejects.toThrow("WebSocket connection failed");
    });

    it("test_initialize_sets_error_state_on_failure", async () => {
      const states: BackendWakeWordState[] = [];
      service.onStateChange((s) => states.push(s));

      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateClose();

      await expect(initPromise).rejects.toThrow();
      expect(states).toContain("error");
    });
  });

  describe("startListening()", () => {
    it("test_start_listening_captures_audio", async () => {
      const listenPromise = service.startListening();

      // initialize() is called internally — simulate WS open
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith(
        expect.objectContaining({
          audio: expect.objectContaining({
            channelCount: 1,
          }),
        }),
      );
      expect(service.state).toBe("listening");
    });

    it("test_start_listening_sends_sensitivity", async () => {
      service.setSensitivity(0.8);
      const listenPromise = service.startListening();

      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      const ws = MockWebSocket.lastInstance()!;
      const sensitivityMsg = ws.sentMessages.find((m) => {
        if (typeof m !== "string") return false;
        const parsed = JSON.parse(m);
        return parsed.command === "set_sensitivity";
      });

      expect(sensitivityMsg).toBeDefined();
      const parsed = JSON.parse(sensitivityMsg as string);
      expect(parsed.value).toBe(0.8);
    });

    it("test_start_listening_noop_when_already_listening", async () => {
      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      const callCount = (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mock.calls.length;

      // Second call should be a no-op
      await service.startListening();
      expect(
        (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mock.calls.length,
      ).toBe(callCount);
    });
  });

  describe("stopListening()", () => {
    it("test_stop_listening_sets_idle_state", async () => {
      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      service.stopListening();
      expect(service.state).toBe("idle");
    });

    it("test_stop_listening_noop_when_idle", () => {
      // Should not throw
      service.stopListening();
      expect(service.state).toBe("idle");
    });
  });

  describe("detection events", () => {
    it("test_detection_fires_callback", async () => {
      const detected = vi.fn();
      service.onDetected(detected);

      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      // Simulate detection event from backend
      MockWebSocket.lastInstance()!.simulateMessage(
        JSON.stringify({
          event: "detected",
          model: "hey_avaros",
          score: 0.92,
          timestamp: "2026-03-05T12:00:00Z",
        }),
      );

      expect(detected).toHaveBeenCalledOnce();
      expect(detected).toHaveBeenCalledWith({
        model: "hey_avaros",
        score: 0.92,
      });
    });

    it("test_detection_sets_detected_state_then_returns_to_listening", async () => {
      const states: BackendWakeWordState[] = [];
      service.onStateChange((s) => states.push(s));

      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      states.length = 0; // Clear previous state changes

      MockWebSocket.lastInstance()!.simulateMessage(
        JSON.stringify({
          event: "detected",
          model: "hey_avaros",
          score: 0.85,
          timestamp: "2026-03-05T12:00:00Z",
        }),
      );

      expect(states[0]).toBe("detected");

      // After 500ms the state should return to listening
      vi.advanceTimersByTime(500);
      expect(service.state).toBe("listening");
    });

    it("test_unsubscribe_stops_callback", async () => {
      const detected = vi.fn();
      const unsub = service.onDetected(detected);

      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      unsub();

      MockWebSocket.lastInstance()!.simulateMessage(
        JSON.stringify({
          event: "detected",
          model: "hey_avaros",
          score: 0.90,
          timestamp: "2026-03-05T12:00:00Z",
        }),
      );

      expect(detected).not.toHaveBeenCalled();
    });

    it("test_malformed_message_is_ignored", async () => {
      const detected = vi.fn();
      service.onDetected(detected);

      const listenPromise = service.startListening();
      MockWebSocket.lastInstance()!.simulateOpen();
      await listenPromise;

      // Send invalid JSON
      MockWebSocket.lastInstance()!.simulateMessage("not json");
      expect(detected).not.toHaveBeenCalled();

      // Send JSON without "detected" event
      MockWebSocket.lastInstance()!.simulateMessage(
        JSON.stringify({ event: "keepalive" }),
      );
      expect(detected).not.toHaveBeenCalled();
    });
  });

  describe("state change events", () => {
    it("test_state_change_callback_fires", async () => {
      const states: BackendWakeWordState[] = [];
      service.onStateChange((s) => states.push(s));

      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      expect(states).toContain("connecting");
    });

    it("test_state_change_unsubscribe", async () => {
      const states: BackendWakeWordState[] = [];
      const unsub = service.onStateChange((s) => states.push(s));

      unsub();

      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      expect(states).toHaveLength(0);
    });
  });

  describe("reconnection", () => {
    it("test_reconnect_after_disconnect_with_backoff", async () => {
      // Initialize and connect
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      const initialInstances = MockWebSocket.instances.length;

      // Simulate unexpected disconnect
      MockWebSocket.lastInstance()!.simulateClose();

      // After 1s backoff, should attempt reconnection
      vi.advanceTimersByTime(1000);
      expect(MockWebSocket.instances.length).toBe(initialInstances + 1);
    });

    it("test_reconnect_doubles_delay_on_repeated_failure", async () => {
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      // First disconnect — schedules reconnect at 1000ms, bumps to 2000ms
      MockWebSocket.lastInstance()!.simulateClose();

      // 1s — first reconnect attempt fires
      vi.advanceTimersByTime(1000);
      const afterFirst = MockWebSocket.instances.length;
      expect(afterFirst).toBeGreaterThan(1);

      // That reconnect also fails (never opens, closes immediately)
      // This triggers scheduleReconnect again, now with delay = 2000ms
      MockWebSocket.lastInstance()!.simulateClose();

      // At +1s after second close — should NOT have reconnected yet
      vi.advanceTimersByTime(1000);
      const afterWait1s = MockWebSocket.instances.length;
      expect(afterWait1s).toBe(afterFirst);

      // At +2s after second close — should reconnect now
      vi.advanceTimersByTime(1000);
      expect(MockWebSocket.instances.length).toBeGreaterThan(afterFirst);
    });

    it("test_no_reconnect_after_dispose", async () => {
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      service.dispose();
      const instancesAfterDispose = MockWebSocket.instances.length;

      // Advance time — should NOT reconnect
      vi.advanceTimersByTime(60_000);
      expect(MockWebSocket.instances.length).toBe(instancesAfterDispose);
    });
  });

  describe("sensitivity", () => {
    it("test_set_sensitivity_clamps_to_bounds", () => {
      service.setSensitivity(1.5);
      expect(service.getSensitivity()).toBe(1);

      service.setSensitivity(-0.5);
      expect(service.getSensitivity()).toBe(0);
    });

    it("test_set_sensitivity_sends_to_backend_when_connected", async () => {
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      service.setSensitivity(0.7);

      const ws = MockWebSocket.lastInstance()!;
      const sensitivityMsg = ws.sentMessages.find((m) => {
        if (typeof m !== "string") return false;
        const parsed = JSON.parse(m);
        return parsed.command === "set_sensitivity" && parsed.value === 0.7;
      });
      expect(sensitivityMsg).toBeDefined();
    });
  });

  describe("dispose()", () => {
    it("test_dispose_resets_to_idle", async () => {
      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      service.dispose();

      expect(service.state).toBe("idle");
      expect(service.isModelLoaded()).toBe(false);
      expect(service.isAvailable()).toBe(false);
    });

    it("test_dispose_clears_callbacks", async () => {
      const detected = vi.fn();
      const stateChange = vi.fn();

      service.onDetected(detected);
      service.onStateChange(stateChange);

      const initPromise = service.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise;

      service.dispose();

      // Callbacks should not fire after dispose
      stateChange.mockClear();
      detected.mockClear();

      // Creating a new connection shouldn't fire old callbacks
      const svc2 = new BackendWakeWordService({
        wsUrl: "ws://test:9999/ws/detect",
      });
      const initPromise2 = svc2.initialize();
      MockWebSocket.lastInstance()!.simulateOpen();
      await initPromise2;

      expect(stateChange).not.toHaveBeenCalled();
      svc2.dispose();
    });
  });
});
