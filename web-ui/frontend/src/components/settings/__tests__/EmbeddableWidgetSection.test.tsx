// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getVoiceConfig } from "../../../api/client";
import EmbeddableWidgetSection, {
  buildWidgetSnippet,
} from "../EmbeddableWidgetSection";

vi.mock("../../../api/client", () => ({
  getVoiceConfig: vi.fn(),
  toFriendlyErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const readyConfig = {
  hivemind_url: "wss://avaros.example.com/hivemind/",
  hivemind_name: "avaros-web-client",
  hivemind_key: "widget-key",
  hivemind_secret: "widget-secret",
  voice_enabled: true,
};

describe("EmbeddableWidgetSection", () => {
  const notify = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getVoiceConfig).mockResolvedValue(readyConfig);
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("generates a trusted internal widget snippet from voice config", async () => {
    render(<EmbeddableWidgetSection onNotify={notify} />);

    await waitFor(() => expect(screen.getByText("Ready")).toBeTruthy());

    const snippet = screen.getByText(/data-host=/).textContent ?? "";
    expect(snippet).toContain('src="http://localhost:3000/avaros-widget.js"');
    expect(snippet).toContain(
      'data-host="wss://avaros.example.com/hivemind/"',
    );
    expect(snippet).toContain('data-client-name="avaros-web-client"');
    expect(snippet).toContain('data-access-key="widget-key"');
    expect(snippet).toContain('data-disabled-modes="wake-word"');
  });

  it("shows not ready when voice access is not configured", async () => {
    vi.mocked(getVoiceConfig).mockResolvedValue({
      ...readyConfig,
      hivemind_key: "",
      voice_enabled: false,
    });

    render(<EmbeddableWidgetSection onNotify={notify} />);

    await waitFor(() => expect(screen.getByText("Not ready")).toBeTruthy());
    expect(
      screen.getByText(/HiveMind voice access is not configured/),
    ).toBeTruthy();
  });

  it("copies the generated snippet", async () => {
    render(<EmbeddableWidgetSection onNotify={notify} />);
    await waitFor(() => expect(screen.getByText("Ready")).toBeTruthy());

    fireEvent.click(screen.getByText("Copy Snippet"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        expect.stringContaining('data-disabled-modes="wake-word"'),
      );
    });
    expect(notify).toHaveBeenCalledWith(
      "success",
      "Widget embed snippet copied.",
    );
  });

  it("updates snippet controls", async () => {
    render(<EmbeddableWidgetSection onNotify={notify} />);
    await waitFor(() => expect(screen.getByText("Ready")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Position"), {
      target: { value: "top-left" },
    });
    fireEvent.change(screen.getByLabelText("Theme"), {
      target: { value: "dark" },
    });
    fireEvent.change(screen.getByLabelText("Size"), {
      target: { value: "large" },
    });
    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Factory assistant" },
    });

    const snippet = screen.getByText(/data-host=/).textContent ?? "";
    expect(snippet).toContain('data-position="top-left"');
    expect(snippet).toContain('data-theme="dark"');
    expect(snippet).toContain('data-size="large"');
    expect(snippet).toContain('data-label="Factory assistant"');
  });
});

describe("buildWidgetSnippet", () => {
  it("escapes HTML attribute values", () => {
    const snippet = buildWidgetSnippet({
      origin: "https://avaros.example.com/",
      voiceConfig: {
        ...readyConfig,
        hivemind_key: 'key"with&chars',
      },
      position: "bottom-right",
      theme: "auto",
      size: "medium",
      label: 'Ask "AVAROS"',
    });

    expect(snippet).toContain("key&quot;with&amp;chars");
    expect(snippet).toContain("Ask &quot;AVAROS&quot;");
  });
});
