// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WidgetPanel } from "./WidgetPanel";

function renderPanel(
  visualState: "processing" | "speaking",
  processing: boolean,
) {
  const onCancelRequest = vi.fn();
  const onStopSpeaking = vi.fn();

  render(
    <WidgetPanel
      mode="text"
      disabledModes={[]}
      messages={[]}
      connectionState="connected"
      listeningSupported
      listeningActive={false}
      micError={null}
      inputValue=""
      processing={processing}
      sendDisabled
      visualState={visualState}
      voiceTurnStatus={null}
      wakeVoiceLanguage="en-US"
      onListenToggle={vi.fn()}
      onCancelRequest={onCancelRequest}
      onInputChange={vi.fn()}
      onSend={vi.fn()}
      onModeChange={vi.fn()}
      onWakeVoiceLanguageChange={vi.fn()}
      onClear={vi.fn()}
      onStopSpeaking={onStopSpeaking}
      brandLogoSrc="/logo.svg"
      wakeWordLabel="Hey Jarvis"
      avarosUrl="https://avaros.example.com/"
    />,
  );

  return { onCancelRequest, onStopSpeaking };
}

describe("embedded WidgetPanel interruption", () => {
  it("can cancel a request even in text mode", () => {
    const { onCancelRequest } = renderPanel("processing", true);

    fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));

    expect(onCancelRequest).toHaveBeenCalledOnce();
  });

  it("can stop a response even in text mode", () => {
    const { onStopSpeaking } = renderPanel("speaking", false);

    fireEvent.click(screen.getByRole("button", { name: "Stop response" }));

    expect(onStopSpeaking).toHaveBeenCalledOnce();
  });

  it("offers an explicit wake-word enable action from text mode", () => {
    const onModeChange = vi.fn();
    render(
      <WidgetPanel
        mode="text"
        disabledModes={[]}
        messages={[]}
        connectionState="connected"
        listeningSupported
        listeningActive={false}
        micError={null}
        inputValue=""
        processing={false}
        sendDisabled
        visualState="idle"
        voiceTurnStatus={null}
        wakeVoiceLanguage="en-US"
        onListenToggle={vi.fn()}
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onModeChange={onModeChange}
        onWakeVoiceLanguageChange={vi.fn()}
        onClear={vi.fn()}
        brandLogoSrc="/logo.svg"
        wakeWordLabel="Hey Jarvis"
        avarosUrl="https://avaros.example.com/"
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /switch to wake-word mode/i,
      }),
    );

    expect(onModeChange).toHaveBeenCalledWith("wake-word");
  });

  it("shows a voice transcript with its recognized language", () => {
    render(
      <WidgetPanel
        mode="wake-word"
        disabledModes={[]}
        messages={[
          {
            id: "voice-1",
            source: "user",
            text: "Aktif bulguları göster",
            timestamp: new Date("2026-09-21T12:00:00Z"),
            inputKind: "voice",
            language: "tr-TR",
          },
        ]}
        connectionState="connected"
        listeningSupported
        listeningActive={false}
        micError={null}
        inputValue=""
        processing
        sendDisabled
        visualState="processing"
        voiceTurnStatus="processing"
        wakeVoiceLanguage="tr-TR"
        onListenToggle={vi.fn()}
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onModeChange={vi.fn()}
        onWakeVoiceLanguageChange={vi.fn()}
        onClear={vi.fn()}
        brandLogoSrc="/logo.svg"
        wakeWordLabel="Hey Jarvis"
        avarosUrl="https://avaros.example.com/"
      />,
    );

    expect(screen.getByText("Aktif bulguları göster")).toBeTruthy();
    expect(screen.getByLabelText("Recognized Turkish").textContent).toBe("TR");
    expect(screen.getByText("Understanding your request…")).toBeTruthy();
  });

  it("lets the user choose the fixed hands-free transcription language", () => {
    const onWakeVoiceLanguageChange = vi.fn();
    render(
      <WidgetPanel
        mode="wake-word"
        disabledModes={[]}
        messages={[]}
        connectionState="connected"
        listeningSupported
        listeningActive={false}
        micError={null}
        inputValue=""
        processing={false}
        sendDisabled={false}
        visualState="idle"
        voiceTurnStatus="armed"
        wakeVoiceLanguage="en-US"
        onListenToggle={vi.fn()}
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onModeChange={vi.fn()}
        onWakeVoiceLanguageChange={onWakeVoiceLanguageChange}
        onClear={vi.fn()}
        brandLogoSrc="/logo.svg"
        wakeWordLabel="Hey Jarvis"
        avarosUrl="https://avaros.example.com/"
      />,
    );

    expect(screen.getByRole("button", { name: "EN" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "TR" }));
    expect(onWakeVoiceLanguageChange).toHaveBeenCalledWith("tr-TR");
  });
});
