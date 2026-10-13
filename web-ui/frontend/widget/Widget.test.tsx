// @vitest-environment jsdom

import { act, fireEvent, render, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Widget } from "./Widget";
import type { WidgetPanel } from "./WidgetPanel";
import type { WidgetConfig } from "./types";

const managerConstructorCalls = vi.hoisted(() => [] as unknown[][]);
const managerConnect = vi.hoisted(() => vi.fn());
const managerSetLanguage = vi.hoisted(() => vi.fn());
const managerSendUtterance = vi.hoisted(() => vi.fn());
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
    async sendUtterance(text: string, language: string) {
      managerSendUtterance(text, language);
    }
    async interrupt() {}
    destroy() {}
    isConnected() {
      return false;
    }
  },
}));

vi.mock("./WidgetButton", () => ({ WidgetButton: () => null }));
vi.mock("./WidgetPanel", () => ({
  WidgetPanel: (props: ComponentProps<typeof WidgetPanel>) => (
    <>
      <input aria-label="Request" value={props.inputValue}
        onChange={(event) => props.onInputChange(event.target.value)} />
      <button onClick={props.onSend}>Send</button>
      <button onClick={props.onListenToggle}>Listen</button>
      {props.messages.map((message) => <p key={message.id}>{message.text}</p>)}
    </>
  ),
}));

describe("Widget connection configuration", () => {
  afterEach(() => vi.unstubAllGlobals());

  beforeEach(() => {
    managerConstructorCalls.length = 0;
    managerSpeakListeners.length = 0;
    managerConnect.mockClear();
    managerSetLanguage.mockClear();
    managerSendUtterance.mockClear();
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  it.each([
    "Compare energy consumption of boiler 1 vs boiler 2 yesterday",
    "Show compressor train energy consumption yesterday",
    "Do not compare boiler 1 vs boiler 2; show metrics instead",
    "Show boiler 1 energy on 2026-10-12 between 08:30 and 09:45",
    "What is our electricity consumption?",
    "Elektrik tüketimimiz ne kadar?",
    "Show latest production",
    "Son üretim miktarını göster",
    "List all meters",
    "Tüm sayaçları listele",
    "List active findings",
    "Etkin bulguları listele",
    "And June?",
    "Peki Haziran?",
  ].flatMap((request) => ["text", "push-to-talk"].map((mode) => ({
    request, mode: mode as "text" | "push-to-talk",
  }))))("sends the complete $mode request with the signed session: $request", async ({ request, mode }) => {
    const recognition = {
      start: vi.fn(),
      stop: vi.fn(),
      onresult: null as ((event: SpeechRecognitionEvent) => void) | null,
    };
    vi.stubGlobal("SpeechRecognition", vi.fn(function () { return recognition; }));
    vi.stubGlobal("isSecureContext", true);
    vi.stubGlobal("navigator", {
      language: "en-US",
      mediaDevices: { getUserMedia: vi.fn(async () => ({ getTracks: () => [] })) },
    });
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
      disabledModes: ["wake-word"],
      defaultMode: mode,
      logoSrc: "/widget-logo.svg",
      avarosUrl: "https://avaros.example.com/",
      wakeWordUrl: "wss://avaros.example.com/wakeword/ws/detect",
      ttsEngine: "browser",
      language: "en-US",
      autoOpen: true,
    };

    const view = render(<Widget config={config} configError={null} onReady={vi.fn()} />);

    await waitFor(() => expect(managerConstructorCalls).toHaveLength(1));
    expect(managerConstructorCalls[0][6]).toBe("signed-reneryo-session");
    expect(managerConnect).toHaveBeenCalledOnce();
    if (mode === "text") {
      fireEvent.change(view.getByLabelText("Request"), { target: { value: request } });
      fireEvent.click(view.getByText("Send"));
    } else {
      fireEvent.click(view.getByText("Listen"));
      await waitFor(() => expect(recognition.start).toHaveBeenCalledOnce());
      act(() => recognition.onresult?.({
        resultIndex: 0,
        results: [{ isFinal: true, 0: { transcript: request } }],
      } as unknown as SpeechRecognitionEvent));
    }
    const language = /[çğıöşü]/i.test(request) ? "tr-TR" : "en-US";
    await waitFor(() => expect(managerSendUtterance).toHaveBeenCalledWith(request, language));
    expect(view.getByText(request)).toBeTruthy();
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
