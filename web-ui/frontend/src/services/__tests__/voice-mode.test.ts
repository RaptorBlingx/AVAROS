/**
 * Unit tests for the VoiceModeService (three-mode toggle).
 *
 * Tests mode switching lifecycle: wake-word ↔ push-to-talk ↔ text,
 * resource cleanup on mode transitions, and event callbacks.
 */

// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  VoiceModeService,
  type VoiceMode,
} from "../voice-mode";

// ── Minimal stubs for dependencies ─────────────────────

/**
 * Stub WakeWordService with the methods VoiceModeService calls.
 */
function createMockWakeWord() {
  return {
    isModelLoaded: vi.fn().mockReturnValue(false),
    initialize: vi.fn().mockResolvedValue(undefined),
    startListening: vi.fn().mockResolvedValue(undefined),
    stopListening: vi.fn(),
    dispose: vi.fn(),
    setSensitivity: vi.fn(),
    state: "idle" as string,
    onDetected: vi.fn().mockReturnValue(() => {}),
    onStateChange: vi.fn().mockReturnValue(() => {}),
    getSensitivity: vi.fn().mockReturnValue(0.75),
  };
}

/**
 * Stub STTService with the methods VoiceModeService calls.
 */
function createMockSTT() {
  return {
    start: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn(),
    isSupported: vi.fn().mockReturnValue(true),
    setLanguage: vi.fn(),
    setContinuous: vi.fn(),
    getState: vi.fn().mockReturnValue("idle"),
    onResult: vi.fn().mockReturnValue(() => {}),
    onStateChange: vi.fn().mockReturnValue(() => {}),
    onError: vi.fn().mockReturnValue(() => {}),
    onSilenceDetected: vi.fn().mockReturnValue(() => {}),
  };
}

// ── Test setup ─────────────────────────────────────────

let mockWakeWord: ReturnType<typeof createMockWakeWord>;
let mockSTT: ReturnType<typeof createMockSTT>;

beforeEach(() => {
  mockWakeWord = createMockWakeWord();
  mockSTT = createMockSTT();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ──────────────────────────────────────────────

describe("VoiceModeService", () => {
  describe("default state", () => {
    it("test_default_mode_is_text", () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      expect(svc.getMode()).toBe("text");
    });
  });

  describe("mode switching", () => {
    it("test_switch_to_wake_word_starts_listening", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      await svc.setMode("wake-word");

      expect(svc.getMode()).toBe("wake-word");
      expect(mockWakeWord.initialize).toHaveBeenCalled();
      expect(mockWakeWord.startListening).toHaveBeenCalled();
    });

    it("test_switch_to_wake_word_skips_init_if_loaded", async () => {
      mockWakeWord.isModelLoaded.mockReturnValue(true);

      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      await svc.setMode("wake-word");

      expect(mockWakeWord.initialize).not.toHaveBeenCalled();
      expect(mockWakeWord.startListening).toHaveBeenCalled();
    });

    it("test_switch_to_push_to_talk_stops_wake_word", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      // First enter wake word mode
      await svc.setMode("wake-word");

      // Now switch to push-to-talk
      await svc.setMode("push-to-talk");

      expect(svc.getMode()).toBe("push-to-talk");
      expect(mockWakeWord.stopListening).toHaveBeenCalled();
    });

    it("test_switch_to_text_stops_all_audio", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      // Enter push-to-talk, then switch to text
      await svc.setMode("push-to-talk");
      await svc.setMode("text");

      expect(svc.getMode()).toBe("text");
      expect(mockSTT.stop).toHaveBeenCalled();
    });

    it("test_switch_to_text_from_wake_word_stops_model", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      await svc.setMode("wake-word");
      await svc.setMode("text");

      expect(svc.getMode()).toBe("text");
      expect(mockWakeWord.stopListening).toHaveBeenCalled();
    });

    it("test_same_mode_is_noop", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      await svc.setMode("text"); // Already text — should be no-op

      expect(mockWakeWord.stopListening).not.toHaveBeenCalled();
      expect(mockSTT.stop).not.toHaveBeenCalled();
    });
  });

  describe("mode change events", () => {
    it("test_mode_change_callback", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      const modes: VoiceMode[] = [];
      svc.onModeChange((m) => modes.push(m));

      await svc.setMode("push-to-talk");
      await svc.setMode("wake-word");
      await svc.setMode("text");

      expect(modes).toEqual(["push-to-talk", "wake-word", "text"]);
    });

    it("test_unsubscribe_mode_change", async () => {
      const svc = new VoiceModeService(
        mockWakeWord as never,
        mockSTT as never,
      );

      const modes: VoiceMode[] = [];
      const unsub = svc.onModeChange((m) => modes.push(m));

      await svc.setMode("push-to-talk");
      expect(modes).toHaveLength(1);

      unsub();

      await svc.setMode("text");
      expect(modes).toHaveLength(1); // No new callback
    });
  });
});
