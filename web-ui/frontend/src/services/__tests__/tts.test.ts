/**
 * Unit tests for the TTS (Text-to-Speech) service.
 *
 * Mocks the speechSynthesis API to test utterance creation,
 * voice selection, queue management, and configuration.
 */

// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TTSService, type TTSState } from "../tts";

// ── Mock SpeechSynthesis ───────────────────────────────

class MockSpeechSynthesisUtterance {
  text: string;
  lang = "";
  rate = 1;
  pitch = 1;
  volume = 1;
  voice: MockSpeechSynthesisVoice | null = null;

  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onboundary: ((event: { name: string; charIndex: number }) => void) | null =
    null;

  constructor(text: string) {
    this.text = text;
  }

  // Test helper: simulate speech completion
  complete(): void {
    this.onstart?.();
    this.onend?.();
  }

  // Test helper: simulate speech start
  startSpeaking(): void {
    this.onstart?.();
  }
}

interface MockSpeechSynthesisVoice {
  name: string;
  lang: string;
  default: boolean;
  localService: boolean;
  voiceURI: string;
}

const MOCK_VOICES: MockSpeechSynthesisVoice[] = [
  {
    name: "Google US English",
    lang: "en-US",
    default: true,
    localService: false,
    voiceURI: "Google US English",
  },
  {
    name: "Google UK English",
    lang: "en-GB",
    default: false,
    localService: false,
    voiceURI: "Google UK English",
  },
  {
    name: "Google Deutsch",
    lang: "de-DE",
    default: false,
    localService: true,
    voiceURI: "Google Deutsch",
  },
  {
    name: "Google Türkçe",
    lang: "tr-TR",
    default: false,
    localService: true,
    voiceURI: "Google Türkçe",
  },
];

let lastUtterance: MockSpeechSynthesisUtterance | null = null;
let speakCalled = false;
let cancelCalled = false;

function createMockSpeechSynthesis() {
  return {
    speak: (utterance: MockSpeechSynthesisUtterance) => {
      speakCalled = true;
      lastUtterance = utterance;
      // Auto-fire onstart after speak is called
      utterance.onstart?.();
    },
    cancel: () => {
      cancelCalled = true;
    },
    pause: vi.fn(),
    resume: vi.fn(),
    getVoices: () => MOCK_VOICES as unknown as SpeechSynthesisVoice[],
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    speaking: false,
    pending: false,
    paused: false,
    onvoiceschanged: null,
  };
}

// ── Test setup ─────────────────────────────────────────

beforeEach(() => {
  lastUtterance = null;
  speakCalled = false;
  cancelCalled = false;

  vi.stubGlobal("speechSynthesis", createMockSpeechSynthesis());
  vi.stubGlobal(
    "SpeechSynthesisUtterance",
    MockSpeechSynthesisUtterance,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ── Tests ──────────────────────────────────────────────

describe("TTSService", () => {
  describe("browser support detection", () => {
    it("test_tts_supported_detection", () => {
      const tts = new TTSService();
      expect(tts.isSupported()).toBe(true);
    });

    it("test_tts_unsupported_when_no_api", () => {
      vi.unstubAllGlobals();
      const win = window as unknown as Record<string, unknown>;
      delete win.speechSynthesis;

      const tts = new TTSService();
      expect(tts.isSupported()).toBe(false);
      expect(tts.getState()).toBe("unsupported");
    });
  });

  describe("speak and utterance creation", () => {
    it("test_speak_creates_utterance", async () => {
      const tts = new TTSService();
      const promise = tts.speak("Hello, world");

      // Complete the utterance so the promise resolves
      lastUtterance!.onend?.();
      await promise;

      expect(speakCalled).toBe(true);
      expect(lastUtterance).not.toBeNull();
      expect(lastUtterance!.text).toBe("Hello, world");
    });

    it("test_speak_applies_language", async () => {
      const tts = new TTSService({ language: "tr-TR" });
      const promise = tts.speak("Merhaba");

      lastUtterance!.onend?.();
      await promise;

      expect(lastUtterance!.lang).toBe("tr-TR");
    });

    it("test_speak_throws_when_unsupported", async () => {
      vi.unstubAllGlobals();
      const win = window as unknown as Record<string, unknown>;
      delete win.speechSynthesis;

      const tts = new TTSService();
      await expect(tts.speak("test")).rejects.toThrow("not supported");
    });
  });

  describe("stop and cancel", () => {
    it("test_stop_cancels_speech", () => {
      const tts = new TTSService();
      void tts.speak("test");

      tts.stop();

      expect(cancelCalled).toBe(true);
      expect(tts.getState()).toBe("idle");
    });
  });

  describe("voice selection", () => {
    it("test_voice_selection", async () => {
      const tts = new TTSService();
      tts.setVoice("Google UK English");

      const promise = tts.speak("test");
      lastUtterance!.onend?.();
      await promise;

      expect(lastUtterance!.voice).not.toBeNull();
      expect((lastUtterance!.voice as MockSpeechSynthesisVoice).name).toBe(
        "Google UK English",
      );
    });

    it("test_get_available_voices", () => {
      const tts = new TTSService();
      const voices = tts.getAvailableVoices();

      expect(voices.length).toBe(MOCK_VOICES.length);
    });

    it("test_get_voices_for_language", () => {
      const tts = new TTSService();
      const enVoices = tts.getVoicesForLanguage("en");

      expect(enVoices.length).toBe(2);
    });
  });

  describe("rate, pitch, volume", () => {
    it("test_rate_pitch_volume_applied", async () => {
      const tts = new TTSService({
        rate: 1.5,
        pitch: 0.8,
        volume: 0.6,
      });

      const promise = tts.speak("test");
      lastUtterance!.onend?.();
      await promise;

      expect(lastUtterance!.rate).toBe(1.5);
      expect(lastUtterance!.pitch).toBe(0.8);
      expect(lastUtterance!.volume).toBe(0.6);
    });

    it("test_set_rate_clamps_values", () => {
      const tts = new TTSService();

      tts.setRate(20);
      void tts.speak("test");
      expect(lastUtterance!.rate).toBe(10); // clamped to max

      tts.stop();
    });

    it("test_set_volume_clamps_values", () => {
      const tts = new TTSService();

      tts.setVolume(-1);
      void tts.speak("test");
      expect(lastUtterance!.volume).toBe(0); // clamped to min
    });
  });

  describe("queue management", () => {
    it("test_speak_queues_when_already_speaking", async () => {
      const tts = new TTSService();

      // First speak — starts immediately
      const promise1 = tts.speak("first");
      expect(tts.getState()).toBe("speaking");

      // Second speak — should be queued, not reject
      const promise2 = tts.speak("second");

      // Complete first utterance → should start second
      const firstUtterance = lastUtterance;
      firstUtterance!.onend?.();

      // Complete second utterance
      lastUtterance!.onend?.();

      await Promise.all([promise1, promise2]);
      expect(tts.getState()).toBe("idle");
    });
  });

  describe("state change events", () => {
    it("test_state_change_fires_on_speak", async () => {
      const tts = new TTSService();
      const states: TTSState[] = [];
      tts.onStateChange((s) => states.push(s));

      const promise = tts.speak("test");
      lastUtterance!.onend?.();
      await promise;

      expect(states).toContain("speaking");
      expect(states).toContain("idle");
    });

    it("test_unsubscribe_state_callback", async () => {
      const tts = new TTSService();
      const states: TTSState[] = [];
      const unsub = tts.onStateChange((s) => states.push(s));

      const promise = tts.speak("test");
      expect(states).toContain("speaking");

      unsub();
      lastUtterance!.onend?.();
      await promise;

      // "idle" after unsub should not appear
      const idleCount = states.filter((s) => s === "idle").length;
      expect(idleCount).toBe(0);
    });
  });

  describe("word boundary events", () => {
    it("test_word_boundary_fires", async () => {
      const tts = new TTSService();
      const boundaries: number[] = [];
      tts.onWordBoundary((idx) => boundaries.push(idx));

      const promise = tts.speak("hello world");

      // Simulate word boundary
      lastUtterance!.onboundary?.({ name: "word", charIndex: 6 });
      lastUtterance!.onend?.();
      await promise;

      expect(boundaries).toContain(6);
    });
  });
});
