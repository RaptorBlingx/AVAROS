// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectionManager } from "./ConnectionManager";

describe("ConnectionManager", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reports an error instead of opening encrypted sockets without WebCrypto", () => {
    const sockets: string[] = [];
    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;
      readonly readyState = MockWebSocket.CONNECTING;

      constructor(url: string) {
        sockets.push(url);
      }
    }

    vi.stubGlobal("crypto", {
      getRandomValues: (buffer: Uint8Array) => buffer,
      randomUUID: () => "widget-test-session",
    });
    vi.stubGlobal("WebSocket", MockWebSocket);

    const manager = new ConnectionManager(
      "ws://avaros.example.com/hivemind/",
      "widget",
      "access-key",
      "",
      "1234567890123456",
    );
    const states: string[] = [];
    manager.onState((state) => states.push(state));

    manager.connect();

    expect(states).toEqual(["disconnected", "error"]);
    expect(sockets).toEqual([]);
  });

  it("waits for a connecting socket before sending utterances", async () => {
    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSING = 2;
      static readonly CLOSED = 3;
      readyState = MockWebSocket.CONNECTING;
      sentMessages: string[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: ((event: { code?: number }) => void) | null = null;

      constructor() {
        MockWebSocket.instances.push(this);
      }

      send(message: string): void {
        this.sentMessages.push(message);
      }

      close(): void {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.({});
      }

      simulateOpen(): void {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.();
      }

      static instances: MockWebSocket[] = [];
    }

    MockWebSocket.instances = [];
    vi.stubGlobal("crypto", {
      getRandomValues: (buffer: Uint8Array) => buffer,
      randomUUID: () => "widget-test-session",
    });
    vi.stubGlobal("WebSocket", MockWebSocket);

    const manager = new ConnectionManager(
      "wss://avaros.example.com/hivemind/",
      "widget",
      "access-key",
    );

    const sendPromise = manager.sendUtterance("energy last week");
    const socket = MockWebSocket.instances[0];
    expect(socket.sentMessages).toEqual([]);

    socket.simulateOpen();
    await sendPromise;

    expect(socket.sentMessages).toHaveLength(2);
    expect(socket.sentMessages[0]).toContain('"msg_type":"hello"');
    expect(socket.sentMessages[1]).toContain("energy last week");
  });
});
