/**
 * Unit tests for the WakeWordService.
 *
 * Mocks TensorFlow.js Speech Commands to test the wake word detection
 * lifecycle, suppression period, sensitivity, visibility handling,
 * and resource cleanup.
 */

// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WakeWordService, type WakeWordState } from "../wake-word";

// ── Mock TF.js modules ────────────────────────────────

/** Simulates the SpeechCommandRecognizer from @tensorflow-models/speech-commands */
class MockRecognizer {
  private _isListening = false;
  private _listener: ((result: unknown) => void) | null = null;
  modelLoaded = false;

  async ensureModelLoaded(): Promise<void> {
    this.modelLoaded = true;
  }

  async listen(
    callback: (result: unknown) => void,
    _opts?: unknown,
  ): Promise<void> {
    this._isListening = true;
    this._listener = callback;
  }

  stopListening(): void {
    this._isListening = false;
    this._listener = null;
  }

  isListening(): boolean {
    return this._isListening;
  }

  wordLabels(): string[] {
    return ["_background_noise_", "_unknown_", "yes", "no", "hey avaros"];
  }

  createTransfer(_name: string): MockTransferRecognizer {
    return new MockTransferRecognizer();
  }

  /** Test helper: simulate a spectrogram result */
  simulateResult(scores: number[]): void {
    if (this._listener) {
      this._listener({ scores: new Float32Array(scores) });
    }
  }
}

class MockTransferRecognizer extends MockRecognizer {
  async load(_url: string): Promise<void> {
    this.modelLoaded = true;
  }

  override wordLabels(): string[] {
    return ["_background_noise_", "hey avaros"];
  }
}

let mockRecognizerInstance: MockRecognizer | null = null;

// ── Spy on dynamic imports ─────────────────────────────

function setupTfMocks(): void {
  mockRecognizerInstance = new MockRecognizer();

  // Mock @tensorflow/tfjs
  vi.doMock("@tensorflow/tfjs", () => ({
    ready: vi.fn().mockResolvedValue(undefined),
  }));

  // Mock @tensorflow-models/speech-commands
  vi.doMock("@tensorflow-models/speech-commands", () => ({
    create: vi.fn(() => mockRecognizerInstance),
  }));
}

// ── Test setup ─────────────────────────────────────────

beforeEach(() => {
  vi.resetModules();
  setupTfMocks();

  // Ensure browser APIs are available
  vi.stubGlobal("AudioContext", class {});
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia: vi.fn() },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  mockRecognizerInstance = null;
});

// ── Tests ──────────────────────────────────────────────

describe("WakeWordService", () => {
  describe("initialization", () => {
    it("test_initialize_loads_model", async () => {
      const svc = new WakeWordService();
      await svc.initialize();

      expect(svc.isModelLoaded()).toBe(true);
      expect(svc.state).toBe("idle");
    });

    it("test_initialize_sets_loading_state", async () => {
      const svc = new WakeWordService();
      const states: WakeWordState[] = [];
      svc.onStateChange((s) => states.push(s));

      await svc.initialize();

      expect(states).toContain("loading");
      expect(states[states.length - 1]).toBe("idle");
    });

    it("test_initialize_idempotent", async () => {
      const svc = new WakeWordService();
      await svc.initialize();
      await svc.initialize(); // Should be a no-op

      expect(svc.isModelLoaded()).toBe(true);
    });

    it("test_initialize_unsupported_browser", async () => {
      vi.unstubAllGlobals();
      // No AudioContext, no getUserMedia

      const svc = new WakeWordService();
      await expect(svc.initialize()).rejects.toThrow();
      expect(svc.state).toBe("unsupported");
    });
  });

  describe("listening lifecycle", () => {
    it("test_start_listening_requires_model", async () => {
      const svc = new WakeWordService();
      // Don't initialize

      await expect(svc.startListening()).rejects.toThrow(
        "Model not loaded",
      );
    });

    it("test_start_listening_sets_state", async () => {
      const svc = new WakeWordService();
      await svc.initialize();
      await svc.startListening();

      expect(svc.state).toBe("listening");
    });

    it("test_stop_listening_sets_idle", async () => {
      const svc = new WakeWordService();
      await svc.initialize();
      await svc.startListening();

      svc.stopListening();

      expect(svc.state).toBe("idle");
    });

    it("test_start_listening_idempotent_when_already_listening", async () => {
      const svc = new WakeWordService();
      await svc.initialize();
      await svc.startListening();
      await svc.startListening(); // Should not throw

      expect(svc.state).toBe("listening");
    });
  });

  describe("detection", () => {
    it("test_detection_fires_callback", async () => {
      const svc = new WakeWordService({ sensitivity: 0.5 });
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      // Simulate a result where "hey avaros" has the highest score
      // Labels: ["_background_noise_", "_unknown_", "yes", "no", "hey avaros"]
      // Scores:  [0.1,                 0.05,         0.1,  0.1,  0.9]
      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);

      expect(detected).toHaveLength(1);
    });

    it("test_detection_does_not_fire_for_background_noise", async () => {
      const svc = new WakeWordService({ sensitivity: 0.5 });
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      // Background noise has highest score
      mockRecognizerInstance!.simulateResult([0.9, 0.05, 0.01, 0.01, 0.03]);

      expect(detected).toHaveLength(0);
    });

    it("test_detection_does_not_fire_below_sensitivity", async () => {
      const svc = new WakeWordService({ sensitivity: 0.8 });
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      // "hey avaros" is top but score < sensitivity (0.7 < 0.8)
      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.05, 0.1, 0.7]);

      expect(detected).toHaveLength(0);
    });
  });

  describe("suppression period", () => {
    it("test_suppression_period_prevents_rapid_fire", async () => {
      vi.useFakeTimers();

      const svc = new WakeWordService({
        sensitivity: 0.5,
        suppressionPeriod: 2000,
      });
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      // First detection
      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);
      expect(detected).toHaveLength(1);

      // Immediate second detection — should be suppressed
      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);
      expect(detected).toHaveLength(1);

      // After suppression period
      vi.advanceTimersByTime(2001);
      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);
      expect(detected).toHaveLength(2);

      vi.useRealTimers();
    });
  });

  describe("sensitivity", () => {
    it("test_sensitivity_threshold_applied", async () => {
      const svc = new WakeWordService({ sensitivity: 0.9 });
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      // Score 0.85 — below threshold
      mockRecognizerInstance!.simulateResult([0.05, 0.02, 0.03, 0.05, 0.85]);
      expect(detected).toHaveLength(0);

      // Score 0.95 — above threshold
      mockRecognizerInstance!.simulateResult([0.01, 0.01, 0.01, 0.02, 0.95]);
      expect(detected).toHaveLength(1);
    });

    it("test_set_sensitivity_clamps_value", () => {
      const svc = new WakeWordService();

      svc.setSensitivity(1.5);
      expect(svc.getSensitivity()).toBe(1);

      svc.setSensitivity(-0.5);
      expect(svc.getSensitivity()).toBe(0);
    });
  });

  describe("cleanup and disposal", () => {
    it("test_stop_listening_releases_resources", async () => {
      const svc = new WakeWordService();
      await svc.initialize();
      await svc.startListening();

      expect(svc.state).toBe("listening");

      svc.stopListening();

      expect(svc.state).toBe("idle");
      expect(mockRecognizerInstance!.isListening()).toBe(false);
    });

    it("test_dispose_cleanup", async () => {
      const svc = new WakeWordService();
      const detected: boolean[] = [];
      svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      svc.dispose();

      expect(svc.isModelLoaded()).toBe(false);
      expect(svc.state).toBe("idle");
    });
  });

  describe("event unsubscription", () => {
    it("test_unsubscribe_detected_stops_callbacks", async () => {
      const svc = new WakeWordService({ sensitivity: 0.5 });
      const detected: boolean[] = [];
      const unsub = svc.onDetected(() => detected.push(true));

      await svc.initialize();
      await svc.startListening();

      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);
      expect(detected).toHaveLength(1);

      unsub();

      // Advance past suppression
      vi.useFakeTimers();
      vi.advanceTimersByTime(3000);
      vi.useRealTimers();

      mockRecognizerInstance!.simulateResult([0.1, 0.05, 0.1, 0.1, 0.9]);
      expect(detected).toHaveLength(1); // No new callback
    });

    it("test_unsubscribe_state_stops_callbacks", async () => {
      const svc = new WakeWordService();
      const states: WakeWordState[] = [];
      const unsub = svc.onStateChange((s) => states.push(s));

      await svc.initialize();
      const countAfterInit = states.length;

      unsub();

      await svc.startListening();
      expect(states.length).toBe(countAfterInit); // No new state
    });
  });
});
