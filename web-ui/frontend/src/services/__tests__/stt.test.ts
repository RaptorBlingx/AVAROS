/**
 * Unit tests for the STT (Speech-to-Text) service.
 *
 * Mocks the Web Speech API's SpeechRecognition to test recognition
 * lifecycle, result handling, silence detection, and error paths.
 */

// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { STTService, type STTResult, type STTState } from "../stt";

// ── Mock SpeechRecognition ─────────────────────────────

class MockSpeechRecognition {
  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;

  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  onspeechend: (() => void) | null = null;

  started = false;
  stopped = false;

  start(): void {
    this.started = true;
  }

  stop(): void {
    this.stopped = true;
  }

  // Test helpers
  simulateResult(transcript: string, confidence: number, isFinal: boolean): void {
    const event = {
      resultIndex: 0,
      results: [
        {
          0: { transcript, confidence },
          isFinal,
          length: 1,
        },
      ],
    };
    this.onresult?.(event);
  }

  simulateError(error: string): void {
    this.onerror?.({ error });
  }

  simulateEnd(): void {
    this.onend?.();
  }

  simulateSpeechEnd(): void {
    this.onspeechend?.();
  }
}

let mockInstance: MockSpeechRecognition | null = null;

// ── Test setup ─────────────────────────────────────────

beforeEach(() => {
  mockInstance = null;

  // Install mock on window
  vi.stubGlobal(
    "SpeechRecognition",
    class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  mockInstance = null;
});

// ── Tests ──────────────────────────────────────────────

describe("STTService", () => {
  describe("browser support detection", () => {
    it("test_stt_supported_detection", () => {
      const stt = new STTService();
      expect(stt.isSupported()).toBe(true);
    });

    it("test_stt_unsupported_when_no_api", () => {
      vi.unstubAllGlobals();
      // Remove SpeechRecognition from window
      const win = window as unknown as Record<string, unknown>;
      const original = win.SpeechRecognition;
      delete win.SpeechRecognition;
      delete win.webkitSpeechRecognition;

      const stt = new STTService();
      expect(stt.isSupported()).toBe(false);
      expect(stt.getState()).toBe("unsupported");

      // Restore
      win.SpeechRecognition = original;
    });
  });

  describe("start and recognition instance", () => {
    it("test_start_creates_recognition_instance", async () => {
      const stt = new STTService();
      await stt.start();

      expect(mockInstance).not.toBeNull();
      expect(mockInstance!.started).toBe(true);
      expect(stt.getState()).toBe("listening");
    });

    it("test_start_applies_language_config", async () => {
      const stt = new STTService({ language: "tr-TR" });
      await stt.start();

      expect(mockInstance!.lang).toBe("tr-TR");
    });

    it("test_start_applies_continuous_config", async () => {
      const stt = new STTService({ continuous: true });
      await stt.start();

      expect(mockInstance!.continuous).toBe(true);
    });

    it("test_start_applies_interim_results_config", async () => {
      const stt = new STTService({ interimResults: false });
      await stt.start();

      expect(mockInstance!.interimResults).toBe(false);
    });
  });

  describe("result handling", () => {
    it("test_result_callback_fires_on_recognition", async () => {
      const stt = new STTService();
      const results: STTResult[] = [];
      stt.onResult((r) => results.push(r));

      await stt.start();
      mockInstance!.simulateResult("hello world", 0.95, true);

      expect(results).toHaveLength(1);
      expect(results[0].transcript).toBe("hello world");
      expect(results[0].confidence).toBe(0.95);
      expect(results[0].isFinal).toBe(true);
    });

    it("test_interim_result_fires_callback", async () => {
      const stt = new STTService();
      const results: STTResult[] = [];
      stt.onResult((r) => results.push(r));

      await stt.start();
      mockInstance!.simulateResult("hel", 0.5, false);

      expect(results).toHaveLength(1);
      expect(results[0].transcript).toBe("hel");
      expect(results[0].isFinal).toBe(false);
    });

    it("test_final_result_sets_processing_in_push_to_talk", async () => {
      const stt = new STTService({ continuous: false });
      const states: STTState[] = [];
      stt.onStateChange((s) => states.push(s));

      await stt.start();
      mockInstance!.simulateResult("test", 0.9, true);

      expect(states).toContain("processing");
    });
  });

  describe("silence detection", () => {
    it("test_silence_timeout_stops_recognition", async () => {
      vi.useFakeTimers();

      const stt = new STTService({ silenceTimeout: 1000, continuous: false });
      const silenceEvents: boolean[] = [];
      stt.onSilenceDetected(() => silenceEvents.push(true));

      await stt.start();

      // Trigger speech end → starts silence timer
      mockInstance!.simulateSpeechEnd();

      // Advance past timeout
      vi.advanceTimersByTime(1001);

      expect(silenceEvents).toHaveLength(1);

      vi.useRealTimers();
    });

    it("test_silence_timer_resets_on_new_result", async () => {
      vi.useFakeTimers();

      const stt = new STTService({ silenceTimeout: 1000, continuous: false });
      const silenceEvents: boolean[] = [];
      stt.onSilenceDetected(() => silenceEvents.push(true));

      await stt.start();

      // New result starts silence timer
      mockInstance!.simulateResult("hello", 0.8, false);
      vi.advanceTimersByTime(500);

      // Another result resets the timer
      mockInstance!.simulateResult("hello world", 0.85, false);
      vi.advanceTimersByTime(500);

      // Only 500ms since last result — no silence yet
      expect(silenceEvents).toHaveLength(0);

      // Now pass the full timeout from last result
      vi.advanceTimersByTime(501);
      expect(silenceEvents).toHaveLength(1);

      vi.useRealTimers();
    });

    it("test_no_silence_detection_in_continuous_mode", async () => {
      vi.useFakeTimers();

      const stt = new STTService({ silenceTimeout: 500, continuous: true });
      const silenceEvents: boolean[] = [];
      stt.onSilenceDetected(() => silenceEvents.push(true));

      await stt.start();
      mockInstance!.simulateSpeechEnd();

      vi.advanceTimersByTime(1000);

      expect(silenceEvents).toHaveLength(0);

      vi.useRealTimers();
    });
  });

  describe("stop and cleanup", () => {
    it("test_stop_cleans_up", async () => {
      const stt = new STTService();
      await stt.start();

      stt.stop();

      expect(stt.getState()).toBe("idle");
    });

    it("test_stop_when_not_started_is_safe", () => {
      const stt = new STTService();
      // Should not throw
      stt.stop();
      expect(stt.getState()).toBe("idle");
    });
  });

  describe("language change", () => {
    it("test_language_change_applied", async () => {
      const stt = new STTService({ language: "en-US" });

      stt.setLanguage("de-DE");
      await stt.start();

      expect(mockInstance!.lang).toBe("de-DE");
    });
  });

  describe("error handling", () => {
    it("test_error_callback_on_recognition_error", async () => {
      const stt = new STTService();
      const errors: string[] = [];
      stt.onError((e) => errors.push(e));

      await stt.start();
      mockInstance!.simulateError("network");

      expect(errors).toHaveLength(1);
      expect(errors[0]).toContain("network");
      expect(stt.getState()).toBe("error");
    });

    it("test_aborted_error_is_ignored", async () => {
      const stt = new STTService();
      const errors: string[] = [];
      stt.onError((e) => errors.push(e));

      await stt.start();
      mockInstance!.simulateError("aborted");

      // "aborted" fires when we call stop() and should be ignored
      expect(errors).toHaveLength(0);
    });

    it("test_start_throws_when_unsupported", async () => {
      vi.unstubAllGlobals();
      const win = window as unknown as Record<string, unknown>;
      delete win.SpeechRecognition;
      delete win.webkitSpeechRecognition;

      const stt = new STTService();
      await expect(stt.start()).rejects.toThrow("not supported");
    });
  });

  describe("event unsubscription", () => {
    it("test_unsubscribe_stops_callbacks", async () => {
      const stt = new STTService();
      const results: STTResult[] = [];
      const unsub = stt.onResult((r) => results.push(r));

      await stt.start();
      mockInstance!.simulateResult("first", 0.9, true);
      expect(results).toHaveLength(1);

      unsub();
      mockInstance!.simulateResult("second", 0.9, true);
      expect(results).toHaveLength(1); // No new result
    });
  });

  describe("state change subscriptions", () => {
    it("test_state_change_fires_on_transitions", async () => {
      const stt = new STTService();
      const states: STTState[] = [];
      stt.onStateChange((s) => states.push(s));

      await stt.start();
      expect(states).toContain("listening");

      stt.stop();
      expect(states).toContain("idle");
    });
  });
});
