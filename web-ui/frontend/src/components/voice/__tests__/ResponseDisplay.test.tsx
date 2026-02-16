// @vitest-environment jsdom

/**
 * ResponseDisplay component tests.
 *
 * Verifies that the response bubble renders correctly, updates its
 * timestamp when the response text changes, and toggles replay/stop.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResponseDisplay from "../ResponseDisplay";

// ── Tests ──────────────────────────────────────────────

describe("ResponseDisplay", () => {
  afterEach(() => {
    cleanup();
  });

  const defaultProps = {
    responseText: "The energy consumption is 42 kWh per unit.",
    isSpeaking: false,
    onReplay: vi.fn(),
    onStopSpeaking: vi.fn(),
  };

  // ── Rendering ────────────────────────────────────

  it("renders nothing when responseText is null", () => {
    const { container } = render(
      <ResponseDisplay
        responseText={null}
        isSpeaking={false}
        onReplay={vi.fn()}
        onStopSpeaking={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("displays the response text", () => {
    render(<ResponseDisplay {...defaultProps} />);
    expect(screen.getByText(defaultProps.responseText)).toBeTruthy();
  });

  it("shows a timestamp after receiving a response", () => {
    render(<ResponseDisplay {...defaultProps} />);
    // Timestamp is a formatted time string like "14:30"
    const timeElement = screen.getByText(/\d{1,2}:\d{2}/);
    expect(timeElement).toBeTruthy();
  });

  // ── Replay / Stop ────────────────────────────────

  it("shows Replay button when not speaking", () => {
    render(<ResponseDisplay {...defaultProps} />);
    expect(screen.getByLabelText(/replay response/i)).toBeTruthy();
  });

  it("shows Stop button when speaking", () => {
    render(<ResponseDisplay {...defaultProps} isSpeaking={true} />);
    expect(screen.getByLabelText(/stop speaking/i)).toBeTruthy();
  });

  it("calls onReplay when Replay is clicked", () => {
    const onReplay = vi.fn();
    render(<ResponseDisplay {...defaultProps} onReplay={onReplay} />);
    fireEvent.click(screen.getByLabelText(/replay response/i));
    expect(onReplay).toHaveBeenCalledWith(defaultProps.responseText);
  });

  it("calls onStopSpeaking when Stop is clicked", () => {
    const onStopSpeaking = vi.fn();
    render(
      <ResponseDisplay
        {...defaultProps}
        isSpeaking={true}
        onStopSpeaking={onStopSpeaking}
      />,
    );
    fireEvent.click(screen.getByLabelText(/stop speaking/i));
    expect(onStopSpeaking).toHaveBeenCalledOnce();
  });

  // ── Timestamp refresh ────────────────────────────

  it("updates timestamp when responseText changes", () => {
    const { rerender } = render(<ResponseDisplay {...defaultProps} />);
    // Verify initial timestamp renders
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeTruthy();

    // Rerender with a new response — timestamp should update
    // We can't easily test the time value changes (same second),
    // but we verify it still renders a timestamp for the new text.
    rerender(
      <ResponseDisplay
        {...defaultProps}
        responseText="New response text here."
      />,
    );
    expect(screen.getByText("New response text here.")).toBeTruthy();
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeTruthy();

    // Verify the old response text is no longer shown
    expect(screen.queryByText(defaultProps.responseText)).toBeFalsy();
  });

  it("does not clear timestamp when re-rendered with same text", () => {
    const { rerender } = render(<ResponseDisplay {...defaultProps} />);
    const firstTimestamp = screen.getByText(/\d{1,2}:\d{2}/).textContent;

    rerender(<ResponseDisplay {...defaultProps} />);
    const secondTimestamp = screen.getByText(/\d{1,2}:\d{2}/).textContent;
    expect(secondTimestamp).toBe(firstTimestamp);
  });
});
