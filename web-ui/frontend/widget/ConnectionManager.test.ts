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

  it.each([
    "Compare energy consumption of boiler 1 vs boiler 2 yesterday",
    "Show compressor train energy consumption yesterday",
    "Do not compare boiler 1 vs boiler 2; show metrics instead",
    "Show boiler 1 energy on 2026-10-12 between 08:30 and 09:45",
  ])("preserves the request on the wire after connecting: %s", async (request) => {
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

    const sendPromise = manager.sendUtterance(request, "en-US");
    const socket = MockWebSocket.instances[0];
    expect(socket.sentMessages).toEqual([]);

    socket.simulateOpen();
    await sendPromise;

    expect(socket.sentMessages).toHaveLength(2);
    expect(socket.sentMessages[0]).toContain('"msg_type":"hello"');
    const sent = JSON.parse(socket.sentMessages[1]);
    expect(sent.msg_type).toBe("bus");
    expect(sent.payload.type).toBe("recognizer_loop:utterance");
    expect(sent.payload.data).toEqual({ utterances: [request], lang: "en-US" });
    expect(sent.payload.context.source).toBe("avaros-widget");
    expect(sent.payload.context.session.lang).toBe("en-US");

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

describe("grounded display and speech", () => {
  it("keeps the display headline and spoken units from the same reply", async () => {
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

    vi.stubGlobal("crypto", {getRandomValues: (buffer: Uint8Array) => buffer, randomUUID: () => "presentation"});
    vi.stubGlobal("WebSocket", MockWebSocket);
    const manager = new ConnectionManager("wss://avaros.example.com/hivemind/", "widget", "access-key", "", "", "tr-TR");
    const reply = vi.fn();
    manager.onSpeak(reply);
    manager.connect();
    const socket = MockWebSocket.instances[0];
    socket.simulateOpen();
    socket.onmessage?.({data: JSON.stringify({msg_type: "bus", payload: {
      type: "speak", data: {utterance: "59645,93 kilovat saat. Veri kapsamı eksik olabilir.", meta: {avaros_response: {
        language: "tr-TR", headline: "59.645,93 kWh. Veri kapsamı eksik olabilir.", evidence_rows: [{name: "Ana sayaç"}],
      }}}, context: {},
    }})});
    await Promise.resolve();
    expect(reply).toHaveBeenCalledWith("59.645,93 kWh. Veri kapsamı eksik olabilir.", "tr-TR", "59645,93 kilovat saat. Veri kapsamı eksik olabilir.", ["Ana sayaç"]);
    manager.destroy();
    vi.unstubAllGlobals();
  });
});

describe("renewable signed sessions", () => {
  class Socket {
    static CONNECTING = 0;
    static OPEN = 1;
    static instances: Socket[] = [];
    readyState = 0;
    onopen: (() => void) | null = null;
    onmessage = null;
    onerror = null;
    onclose: ((event: { code: number; reason: string }) => void) | null = null;
    sent: string[] = [];
    constructor(readonly url: string) { Socket.instances.push(this); }
    send(value: string) { this.sent.push(value); }
    open() { this.readyState = 1; this.onopen?.(); }
    close(code = 1006, reason = "") { this.readyState = 3; this.onclose?.({ code, reason }); }
  }
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); Socket.instances = []; });

  it("refreshes an expired reconnect and retains the conversation session ID", async () => {
    vi.stubGlobal("WebSocket", Socket);
    const provider = vi.fn(async (force?: boolean) => force ? "fresh" : "old");
    const manager = new ConnectionManager("ws://localhost/hivemind/", "", "", "", "", "en-US", "initial", provider);
    manager.connect();
    await Promise.resolve();
    const first = Socket.instances[0];
    first.open();
    first.close(1008, "Expired widget session");
    await Promise.resolve();
    const second = Socket.instances[1];
    second.open();
    expect(second.url).toContain("session=fresh");
    expect(provider).toHaveBeenLastCalledWith(true);
    const id = (socket: Socket) => JSON.parse(socket.sent[0]).payload.session.session_id;
    expect(id(second)).toBe(id(first));
    second.close(1008, "Expired widget session");
    expect(manager.getState()).toBe("error");
    expect(Socket.instances).toHaveLength(2);
    manager.destroy();
  });

  it("does not refresh origin or signature rejections", async () => {
    vi.stubGlobal("WebSocket", Socket);
    const provider = vi.fn(async () => "signed");
    const manager = new ConnectionManager("ws://localhost/hivemind/", "", "", "", "", "en-US", "", provider);
    manager.connect(); await Promise.resolve();
    Socket.instances[0].open();
    Socket.instances[0].close(1008, "Widget session origin mismatch");
    expect(provider).toHaveBeenCalledTimes(1);
    expect(manager.getState()).toBe("error");
    manager.destroy();
  });

  it("does not open a socket after disposal during renewal", async () => {
    vi.stubGlobal("WebSocket", Socket);
    let resolve!: (token: string) => void;
    const manager = new ConnectionManager("ws://localhost/hivemind/", "", "", "", "", "en-US", "", () => new Promise(r => { resolve = r; }));
    manager.connect(); manager.destroy(); resolve("fresh");
    await Promise.resolve();
    expect(Socket.instances).toHaveLength(0);
  });
});
