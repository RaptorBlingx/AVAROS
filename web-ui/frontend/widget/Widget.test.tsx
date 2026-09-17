// @vitest-environment jsdom

import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Widget } from "./Widget";
import type { WidgetConfig } from "./types";

const managerConstructorCalls = vi.hoisted(() => [] as unknown[][]);

vi.mock("./ConnectionManager", () => ({
  ConnectionManager: class {
    constructor(...args: unknown[]) {
      managerConstructorCalls.push(args);
    }

    onState(listener: (state: string) => void) {
      listener("disconnected");
      return () => undefined;
    }

    onSpeak() {
      return () => undefined;
    }

    on() {
      return () => undefined;
    }

    connect() {}
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
      autoOpen: false,
    };

    render(<Widget config={config} configError={null} onReady={vi.fn()} />);

    await waitFor(() => expect(managerConstructorCalls).toHaveLength(1));
    expect(managerConstructorCalls[0][6]).toBe("signed-reneryo-session");
  });
});
