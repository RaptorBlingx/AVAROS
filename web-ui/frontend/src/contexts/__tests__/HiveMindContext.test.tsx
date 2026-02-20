// @vitest-environment jsdom

import { render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { HiveMindProvider, useHiveMind } from "../HiveMindContext";
import { getVoiceConfig } from "../../api/client";

vi.mock("../../api/client", () => ({
  getVoiceConfig: vi.fn(),
}));

const mockState = vi.hoisted(() => ({
  latest: null as null | { emit: (eventType: string, msg?: unknown) => void },
  listeners: {} as Record<string, Array<(msg: unknown) => void>>,
  stateListeners: [] as Array<
    (state: "disconnected" | "connecting" | "connected" | "error") => void
  >,
}));

vi.mock("../../services/hivemind", () => {
  class MockHiveMindService {
    constructor() {
      mockState.latest = this;
    }

    on(eventType: string, callback: (msg: unknown) => void): () => void {
      if (!mockState.listeners[eventType]) {
        mockState.listeners[eventType] = [];
      }
      mockState.listeners[eventType].push(callback);
      return () => {
        mockState.listeners[eventType] = mockState.listeners[eventType].filter(
          (cb) => cb !== callback,
        );
      };
    }

    onSpeak(callback: (text: string) => void): () => void {
      return this.on("speak", (msg) => {
        const payload = msg as { data?: { utterance?: string } };
        if (payload.data?.utterance) {
          callback(payload.data.utterance);
        }
      });
    }

    onStateChange(
      callback: (state: "disconnected" | "connecting" | "connected" | "error") => void,
    ): () => void {
      mockState.stateListeners.push(callback);
      return () => {
        const index = mockState.stateListeners.indexOf(callback);
        if (index >= 0) {
          mockState.stateListeners.splice(index, 1);
        }
      };
    }

    connect(): Promise<void> {
      mockState.stateListeners.forEach((cb) => cb("connected"));
      return Promise.resolve();
    }

    disconnect(): void {
      mockState.stateListeners.forEach((cb) => cb("disconnected"));
    }

    sendUtterance(): Promise<void> {
      return Promise.resolve();
    }

    getConnectionDetails() {
      return {
        url: "ws://localhost:5678",
        latencyMs: 12,
        sessionId: "session-abc",
      };
    }

    dispose(): void {
      // no-op for test
    }

    emit(eventType: string, msg: unknown = {}): void {
      for (const cb of mockState.listeners[eventType] ?? []) {
        cb(msg);
      }
      for (const cb of mockState.listeners["*"] ?? []) {
        cb(msg);
      }
    }
  }

  return {
    HiveMindService: MockHiveMindService,
  };
});

type Snapshot = {
  isConnected: boolean;
  isSpeaking: boolean;
  isProcessing: boolean;
};

let snapshot: Snapshot = {
  isConnected: false,
  isSpeaking: false,
  isProcessing: false,
};

function Probe() {
  const ctx = useHiveMind();

  useEffect(() => {
    snapshot = {
      isConnected: ctx.isConnected,
      isSpeaking: ctx.isSpeaking,
      isProcessing: ctx.isProcessing,
    };
  }, [ctx.isConnected, ctx.isSpeaking, ctx.isProcessing]);

  return null;
}

describe("HiveMindContext event state mapping", () => {
  beforeEach(() => {
    snapshot = { isConnected: false, isSpeaking: false, isProcessing: false };
    mockState.latest = null;
    Object.keys(mockState.listeners).forEach((key) => {
      mockState.listeners[key] = [];
    });
    mockState.stateListeners.length = 0;

    vi.mocked(getVoiceConfig).mockResolvedValue({
      hivemind_url: "ws://localhost:5678",
      hivemind_name: "avaros-web-client",
      hivemind_key: "test-key",
      hivemind_secret: "test-secret",
      voice_enabled: true,
    });
  });

  it("maps audio_output_start/end to isSpeaking", async () => {
    render(
      <HiveMindProvider>
        <Probe />
      </HiveMindProvider>,
    );

    await waitFor(() => {
      expect(mockState.latest).not.toBeNull();
    });

    mockState.latest?.emit("recognizer_loop:audio_output_start", {
      type: "recognizer_loop:audio_output_start",
      data: {},
    });

    await waitFor(() => {
      expect(snapshot.isSpeaking).toBe(true);
    });

    mockState.latest?.emit("recognizer_loop:audio_output_end", {
      type: "recognizer_loop:audio_output_end",
      data: {},
    });

    await waitFor(() => {
      expect(snapshot.isSpeaking).toBe(false);
    });
  });

  it("auto-connects on initial load", async () => {
    render(
      <HiveMindProvider>
        <Probe />
      </HiveMindProvider>,
    );

    await waitFor(() => {
      expect(snapshot.isConnected).toBe(true);
    });
  });

  it("maps handler.start/complete to isProcessing", async () => {
    render(
      <HiveMindProvider>
        <Probe />
      </HiveMindProvider>,
    );

    await waitFor(() => {
      expect(mockState.latest).not.toBeNull();
    });

    mockState.latest?.emit("mycroft.skill.handler.start", {
      type: "mycroft.skill.handler.start",
      data: {},
    });

    await waitFor(() => {
      expect(snapshot.isProcessing).toBe(true);
    });

    mockState.latest?.emit("mycroft.skill.handler.complete", {
      type: "mycroft.skill.handler.complete",
      data: {},
    });

    await waitFor(() => {
      expect(snapshot.isProcessing).toBe(false);
    });
  });

  it("delivers events to subscriptions created before service init", async () => {
    function EarlySubscriber() {
      const ctx = useHiveMind();

      useEffect(() => {
        return ctx.on("speak", () => {
          snapshot = {
            ...snapshot,
            isSpeaking: true,
          };
        });
      }, [ctx]);

      return null;
    }

    render(
      <HiveMindProvider>
        <EarlySubscriber />
      </HiveMindProvider>,
    );

    await waitFor(() => {
      expect(mockState.latest).not.toBeNull();
    });

    mockState.latest?.emit("speak", {
      type: "speak",
      data: { utterance: "hello" },
    });

    await waitFor(() => {
      expect(snapshot.isSpeaking).toBe(true);
    });
  });
});
