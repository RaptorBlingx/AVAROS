// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WidgetButton } from "./WidgetButton";

describe("WidgetButton wake-word state", () => {
  it("keeps the enabled state visible while the widget is collapsed", () => {
    render(
      <WidgetButton
        visualState="idle"
        connectionState="disconnected"
        size="small"
        label=""
        open={false}
        onClick={vi.fn()}
        tooltip="Disconnected"
        wakeWordEnabled
        wakeWordLabel="Hey Jarvis"
      />,
    );

    expect(screen.getByText("Wake on")).toBeTruthy();
    expect(
      screen.getByRole("button", {
        name: /wake word enabled, listening for Hey Jarvis/i,
      }),
    ).toBeTruthy();
  });
});
