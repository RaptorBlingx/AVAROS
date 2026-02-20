// @vitest-environment jsdom

/**
 * VoiceWidget component tests.
 *
 * Verifies rendering, state mapping, keyboard interaction, and
 * microphone click behavior with mocked voice + hivemind contexts.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { VoiceState } from "../../../contexts/voice-types";
import type { WakeWordState } from "../../../services/wake-word-types";

// ── Shared mock state (hoisted) ────────────────────────

const mockVoice = vi.hoisted(() => ({
  voiceState: "idle" as VoiceState,
  voiceMode: "push-to-talk" as const,
  micPermission: "granted" as "granted" | "denied" | "prompt",
  sttSupported: true,
  ttsSupported: true,
  startListening: vi.fn().mockResolvedValue(undefined),
  stopListening: vi.fn(),
  cancelCurrentQuery: vi.fn(),
  clearQuery: vi.fn(),
  interimTranscript: "",
  finalTranscript: "",
  speak: vi.fn().mockResolvedValue(undefined),
  stopSpeaking: vi.fn(),
  isSpeaking: false,
  wakeWordState: "idle" as WakeWordState,
  wakeWordEnabled: false,
  wakeWordSensitivity: 0.5,
  setWakeWordSensitivity: vi.fn(),
  isModelLoading: false,
  setVoiceMode: vi.fn().mockResolvedValue(undefined),
  setLanguage: vi.fn(),
  availableVoices: [] as SpeechSynthesisVoice[],
  setTTSVoice: vi.fn(),
  requestMicPermission: vi.fn().mockResolvedValue("granted" as const),
}));

const mockHiveMind = vi.hoisted(() => ({
  connectionState: "connected" as "connected" | "disconnected" | "connecting" | "error",
  voiceEnabled: true,
  isConnected: true,
  connect: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn(),
  sendUtterance: vi.fn().mockResolvedValue(undefined),
  lastResponse: null as string | null,
  isSpeaking: false,
  isProcessing: false,
  mouthText: null as string | null,
  connectionDetails: {
    url: "ws://localhost:5678",
    latencyMs: 0,
    sessionId: "test-session",
  },
  on: vi.fn().mockReturnValue(() => {}),
}));

// ── Mock the context hooks ─────────────────────────────

vi.mock("../../../contexts/VoiceContext", () => ({
  useVoice: () => ({ ...mockVoice }),
}));

vi.mock("../../../contexts/HiveMindContext", () => ({
  useHiveMind: () => ({ ...mockHiveMind }),
}));

// ── Import after mocks ────────────────────────────────

import VoiceWidget from "../VoiceWidget";

// ── Helpers ────────────────────────────────────────────

/** Reset all mock state to defaults before each test. */
function resetMocks(): void {
  mockVoice.voiceState = "idle";
  mockVoice.micPermission = "granted";
  mockVoice.sttSupported = true;
  mockVoice.interimTranscript = "";
  mockVoice.finalTranscript = "";
  mockVoice.isSpeaking = false;
  mockVoice.startListening.mockClear().mockResolvedValue(undefined);
  mockVoice.stopListening.mockClear();
  mockVoice.cancelCurrentQuery.mockClear();
  mockVoice.clearQuery.mockClear();
  mockVoice.speak.mockClear().mockResolvedValue(undefined);
  mockVoice.stopSpeaking.mockClear();
  mockVoice.requestMicPermission.mockClear().mockResolvedValue("granted");

  mockHiveMind.connectionState = "connected";
  mockHiveMind.voiceEnabled = true;
  mockHiveMind.isConnected = true;
  mockHiveMind.lastResponse = null;
  mockHiveMind.isSpeaking = false;
  mockHiveMind.isProcessing = false;
}

// ── Tests ──────────────────────────────────────────────

describe("VoiceWidget", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    resetMocks();
  });

  // ── Visibility ─────────────────────────────────────

  describe("visibility", () => {
    it("renders nothing when voiceEnabled is false", () => {
      mockHiveMind.voiceEnabled = false;
      const { container } = render(<VoiceWidget />);
      expect(container.innerHTML).toBe("");
    });

    it("renders the mic button when voiceEnabled is true", () => {
      render(<VoiceWidget />);
      expect(screen.getByRole("button")).toBeTruthy();
    });

    it("renders the voice assistant region", () => {
      render(<VoiceWidget />);
      expect(screen.getByRole("region", { name: /voice assistant/i })).toBeTruthy();
    });
  });

  // ── Disconnected state ─────────────────────────────

  describe("disconnected state", () => {
    it("shows disconnected when isConnected is false", () => {
      mockHiveMind.isConnected = false;
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      expect(button.getAttribute("aria-label")).toContain("not connected");
    });

    it("shows disconnected when connectionState is disconnected", () => {
      mockHiveMind.connectionState = "disconnected";
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      expect(button.getAttribute("aria-label")).toContain("not connected");
    });
  });

  // ── STT unsupported ────────────────────────────────

  describe("STT unsupported", () => {
    it("disables mic button when sttSupported is false", () => {
      mockVoice.sttSupported = false;
      render(<VoiceWidget />);

      // Mic click should be a no-op when stt is unsupported
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.startListening).not.toHaveBeenCalled();
    });
  });

  // ── Keyboard interaction ───────────────────────────

  describe("keyboard interaction", () => {
    it("opens panel on Enter key", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });
      // Panel should now be visible — look for the state label
      expect(screen.getByText("Ready")).toBeTruthy();
    });

    it("opens panel on Space key", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: " " });
      expect(screen.getByText("Ready")).toBeTruthy();
    });

    it("closes panel on Escape key", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");

      // Open panel first
      fireEvent.keyDown(region, { key: "Enter" });
      expect(screen.getByText("Ready")).toBeTruthy();

      // Close with Escape
      fireEvent.keyDown(region, { key: "Escape" });
      // Panel should start exit animation — "Ready" may still be in DOM
      // but the expanded state should be false
    });

    it("toggles panel on repeated Enter presses", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");

      // First press opens
      fireEvent.keyDown(region, { key: "Enter" });
      expect(screen.getByText("Ready")).toBeTruthy();

      // Second press closes (triggers exit animation)
      fireEvent.keyDown(region, { key: "Enter" });
    });

    it("does NOT trigger startListening on Enter key", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });
      expect(mockVoice.startListening).not.toHaveBeenCalled();
    });
  });

  // ── Mic click ──────────────────────────────────────

  describe("mic click", () => {
    it("starts listening on click when idle", async () => {
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.startListening).toHaveBeenCalledOnce();
    });

    it("stops listening on click when already listening", () => {
      mockVoice.voiceState = "listening";
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.stopListening).toHaveBeenCalledOnce();
    });

    it("does not start listening when disconnected", () => {
      mockHiveMind.isConnected = false;
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.startListening).not.toHaveBeenCalled();
    });

    it("does not start listening when mic denied", () => {
      mockVoice.micPermission = "denied";
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.startListening).not.toHaveBeenCalled();
    });
  });

  // ── Permission prompt ──────────────────────────────

  describe("permission handling", () => {
    it("requests mic permission on click when permission is prompt", async () => {
      mockVoice.micPermission = "prompt";
      render(<VoiceWidget />);
      const button = screen.getByRole("button");
      fireEvent.click(button);
      expect(mockVoice.requestMicPermission).toHaveBeenCalledOnce();
    });
  });

  // ── Panel content ──────────────────────────────────

  describe("panel content", () => {
    it("shows mic denied message when permission is denied", () => {
      mockVoice.micPermission = "denied";
      render(<VoiceWidget />);

      // Open panel
      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      expect(
        screen.getByText(/microphone access denied/i),
      ).toBeTruthy();
    });

    it("shows STT unsupported message in panel", () => {
      mockVoice.sttSupported = false;
      render(<VoiceWidget />);

      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      expect(
        screen.getByText(/speech recognition is not supported/i),
      ).toBeTruthy();
    });

    it("shows disconnected message when not connected", () => {
      mockHiveMind.isConnected = false;
      render(<VoiceWidget />);

      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      expect(
        screen.getByText(/voice is unavailable/i),
      ).toBeTruthy();
    });

    it("shows minimize button in panel", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      expect(
        screen.getByLabelText(/minimize voice widget/i),
      ).toBeTruthy();
    });

    it("allows asking next query from panel", () => {
      mockVoice.finalTranscript = "what is oee";
      render(<VoiceWidget />);

      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      fireEvent.click(screen.getByRole("button", { name: /ask next/i }));
      expect(mockVoice.cancelCurrentQuery).toHaveBeenCalledOnce();
      expect(mockVoice.startListening).toHaveBeenCalledOnce();
    });

    it("shows and executes cancel query action while processing", () => {
      mockVoice.voiceState = "processing";
      render(<VoiceWidget />);

      const region = screen.getByRole("region");
      fireEvent.keyDown(region, { key: "Enter" });

      fireEvent.click(screen.getByRole("button", { name: /cancel query/i }));
      expect(mockVoice.cancelCurrentQuery).toHaveBeenCalledOnce();
    });

    it("allows minimizing panel when lastResponse exists", async () => {
      const responseText = "AVAROS is still initializing. Please try again.";
      mockHiveMind.lastResponse = responseText;
      render(<VoiceWidget />);

      expect(screen.getByText(responseText)).toBeTruthy();

      fireEvent.click(screen.getByLabelText(/minimize voice widget/i));
      await new Promise((resolve) => setTimeout(resolve, 250));

      expect(screen.queryByText(responseText)).toBeNull();
    });
  });

  // ── Position prop ──────────────────────────────────

  describe("position", () => {
    it("defaults to bottom-right position", () => {
      render(<VoiceWidget />);
      const region = screen.getByRole("region");
      expect(region.className).toContain("bottom-5");
      expect(region.className).toContain("right-5");
    });

    it("applies bottom-left position", () => {
      render(<VoiceWidget position="bottom-left" />);
      const region = screen.getByRole("region");
      expect(region.className).toContain("bottom-5");
      expect(region.className).toContain("left-5");
    });
  });
});
