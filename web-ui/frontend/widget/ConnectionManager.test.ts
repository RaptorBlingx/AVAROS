// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectionManager } from "./ConnectionManager";

describe("ConnectionManager", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses the short-lived session token instead of browser credentials", () => {
    const sockets: string[] = [];
    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      readonly readyState = MockWebSocket.CONNECTING;
      constructor(url: string) {
        sockets.push(url);
      }
    }
    vi.stubGlobal("crypto", { randomUUID: () => "widget-test-session" });
    vi.stubGlobal("WebSocket", MockWebSocket);

    const manager = new ConnectionManager(
      "wss://avaros.example.com/hivemind/",
      "widget",
      "",
      "",
      "",
      "en-US",
      "signed value",
    );
    manager.connect();

    expect(sockets).toEqual([
      "wss://avaros.example.com/hivemind/?session=signed%20value",
    ]);
    expect(sockets[0]).not.toContain("authorization=");
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
    const spoken: string[] = [];
    manager.onSpeak((text) => spoken.push(text));

    const sendPromise = manager.sendUtterance("energy last week");
    const socket = MockWebSocket.instances[0];
    expect(socket.sentMessages).toEqual([]);

    socket.simulateOpen();
    await sendPromise;

    expect(socket.sentMessages).toHaveLength(2);
    expect(socket.sentMessages[0]).toContain('"msg_type":"hello"');
    expect(socket.sentMessages[1]).toContain("energy last week");

    await manager.interrupt();
    const eventTypes = socket.sentMessages
      .map((raw) => JSON.parse(raw))
      .filter((message) => message.msg_type === "bus")
      .map((message) => message.payload.type);
    expect(eventTypes).toEqual([
      "recognizer_loop:utterance",
      "mycroft.stop",
      "mycroft.audio.speech.stop",
    ]);

    const utterance = socket.sentMessages
      .map((raw) => JSON.parse(raw))
      .find((message) => message.payload?.type === "recognizer_loop:utterance");
    socket.onmessage?.({
      data: JSON.stringify({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: { utterance: "late cancelled response" },
          context: {
            client_request_id: utterance.payload.context.client_request_id,
          },
        },
      }),
    });
    await Promise.resolve();
    expect(spoken).toEqual([]);
  });

  it("propagates the per-response locale and uses it for the next utterance", async () => {
    class MockWebSocket {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
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
      }

      simulateOpen(): void {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.();
      }

      static instances: MockWebSocket[] = [];
    }

    vi.stubGlobal("crypto", {
      getRandomValues: (buffer: Uint8Array) => buffer,
      randomUUID: () => "widget-language-session",
    });
    vi.stubGlobal("WebSocket", MockWebSocket);

    const manager = new ConnectionManager(
      "wss://avaros.example.com/hivemind/",
      "widget",
      "access-key",
      "",
      "",
      "en-US",
    );
    const spoken: Array<[string, string]> = [];
    manager.onSpeak((text, language) => spoken.push([text, language]));
    manager.connect();
    const socket = MockWebSocket.instances[0];
    socket.simulateOpen();

    socket.onmessage?.({
      data: JSON.stringify({
        msg_type: "bus",
        payload: {
          type: "speak",
          data: {
            utterance: "Beş kaynakta veri boşluğu bulundu.",
            meta: {
              avaros_response: { language: "tr-TR" },
            },
          },
          context: {},
        },
      }),
    });
    await Promise.resolve();

    expect(spoken).toEqual([
      ["Beş kaynakta veri boşluğu bulundu.", "tr-TR"],
    ]);

    await manager.sendUtterance("kanıtı göster");
    const utterance = socket.sentMessages
      .map((raw) => JSON.parse(raw))
      .find((message) => message.payload?.type === "recognizer_loop:utterance");
    expect(utterance.payload.data.lang).toBe("tr-TR");
    expect(utterance.payload.context.session.lang).toBe("tr-TR");
  });
});
