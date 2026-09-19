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
      onListenToggle={vi.fn()}
      onCancelRequest={onCancelRequest}
      onInputChange={vi.fn()}
      onSend={vi.fn()}
      onModeChange={vi.fn()}
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
        onListenToggle={vi.fn()}
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onModeChange={onModeChange}
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
});
