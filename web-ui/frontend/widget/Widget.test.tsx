// @vitest-environment jsdom

import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Widget } from "./Widget";
import type { WidgetConfig } from "./types";

const managerConstructorCalls = vi.hoisted(() => [] as unknown[][]);
const managerConnect = vi.hoisted(() => vi.fn());
const managerSetLanguage = vi.hoisted(() => vi.fn());
const managerSpeakListeners = vi.hoisted(
  () => [] as Array<(text: string, language: string) => void>,
);

vi.mock("./ConnectionManager", () => ({
  ConnectionManager: class {
    constructor(...args: unknown[]) {
      managerConstructorCalls.push(args);
    }

    onState(listener: (state: string) => void) {
      listener("disconnected");
      return () => undefined;
    }

    onSpeak(listener: (text: string, language: string) => void) {
      managerSpeakListeners.push(listener);
      return () => undefined;
    }

    on() {
      return () => undefined;
    }

    connect() {
      managerConnect();
    }
    setLanguage(language: string) {
      managerSetLanguage(language);
    }
    async sendUtterance() {}
    async interrupt() {}
    destroy() {}
    isConnected() {
      return false;
    }
  },
}));

vi.mock("./WidgetButton", () => ({ WidgetButton: () => null }));
vi.mock("./WidgetPanel", () => ({ WidgetPanel: () => null }));

describe("Widget connection configuration", () => {
  beforeEach(() => {
    managerConstructorCalls.length = 0;
    managerSpeakListeners.length = 0;
    managerConnect.mockClear();
    managerSetLanguage.mockClear();
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  it("passes the signed Reneryo session to the connection manager", async () => {
    const config: WidgetConfig = {
      host: "wss://avaros.example.com/hivemind/",
      clientName: "widget",
      accessKey: "",
      sessionToken: "signed-reneryo-session",
      position: "bottom-right",
      theme: "light",
      size: "medium",
      offsetX: 20,
      offsetY: 20,
      label: "",
      disabledModes: ["wake-word", "push-to-talk"],
      defaultMode: "text",
      logoSrc: "/widget-logo.svg",
      avarosUrl: "https://avaros.example.com/",
      wakeWordUrl: "wss://avaros.example.com/wakeword/ws/detect",
      ttsEngine: "browser",
      language: "en-US",
      autoOpen: true,
    };

    render(<Widget config={config} configError={null} onReady={vi.fn()} />);

    await waitFor(() => expect(managerConstructorCalls).toHaveLength(1));
    expect(managerConstructorCalls[0][6]).toBe("signed-reneryo-session");
    expect(managerConnect).toHaveBeenCalledOnce();
  });

  it("sends the response locale to server TTS after a mid-session switch", async () => {
    const ttsRequests: Array<{ text: string; language: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (typeof init?.body === "string") {
          ttsRequests.push(JSON.parse(init.body));
        }
        return {
          ok: true,
          blob: async () => new Blob(["wav"], { type: "audio/wav" }),
        };
      }),
    );

    const config: WidgetConfig = {
      host: "wss://avaros.example.com/hivemind/",
      clientName: "widget",
      accessKey: "",
      sessionToken: "signed-reneryo-session",
      position: "bottom-right",
      theme: "light",
      size: "medium",
      offsetX: 20,
      offsetY: 20,
      label: "",
      disabledModes: ["wake-word", "push-to-talk"],
      defaultMode: "text",
      logoSrc: "/widget-logo.svg",
      avarosUrl: "https://avaros.example.com/",
      wakeWordUrl: "wss://avaros.example.com/wakeword/ws/detect",
      ttsEngine: "server",
      language: "en-US",
      autoOpen: true,
    };

    render(<Widget config={config} configError={null} onReady={vi.fn()} />);
    await waitFor(() => expect(managerSpeakListeners).toHaveLength(1));

    act(() => {
      managerSpeakListeners[0]("Beş kaynakta veri boşluğu bulundu.", "tr-TR");
    });

    await waitFor(() => expect(ttsRequests).not.toHaveLength(0));
    expect(ttsRequests[0]).toEqual({
      text: "Beş kaynakta veri boşluğu bulundu.",
      language: "tr-TR",
    });
    expect(managerSetLanguage).toHaveBeenCalledWith("tr-TR");
  });
});
