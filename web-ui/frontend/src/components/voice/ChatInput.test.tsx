// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatInput from "./ChatInput";

describe("ChatInput interruption", () => {
  it("shows a cancel control while a text request is processing", () => {
    const onInterrupt = vi.fn();

    render(
      <ChatInput
        isConnected
        disabled
        interruptLabel="Cancel request"
        onInterrupt={onInterrupt}
        onSend={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));

    expect(onInterrupt).toHaveBeenCalledOnce();
    expect(
      (screen.getByLabelText("Chat message input") as HTMLInputElement)
        .readOnly,
    ).toBe(true);
  });

  it("shows a stop-response control while AVAROS is speaking", () => {
    render(
      <ChatInput
        isConnected
        disabled={false}
        interruptLabel="Stop response"
        onInterrupt={vi.fn()}
        onSend={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Stop response" }).hidden,
    ).toBe(false);
  });
});
