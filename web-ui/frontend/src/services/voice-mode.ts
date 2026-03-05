/**
 * Three-mode voice interaction toggle service.
 *
 * Controls how voice interaction is initiated:
 *   - **wake-word:** Hands-free — backend openWakeWord listens for the
 *     wake phrase via WebSocket, then STT pipeline picks up the utterance.
 *     Falls back to push-to-talk if the backend is unreachable.
 *   - **push-to-talk:** Manual — user clicks a button to start/stop
 *     recording.  No model loaded, no continuous audio stream.
 *   - **text:** Keyboard-only — all audio services stopped, mic released.
 *
 * All three modes converge to the same HiveMind `sendUtterance()` call.
 *
 * Switching modes cleans up the previous mode's resources (model, mic,
 * audio stream) before activating the new one.
 */

import { BackendWakeWordService } from "./wake-word-backend";
import { STTService } from "./stt";

// ── Types ──────────────────────────────────────────────

export type VoiceMode = "wake-word" | "push-to-talk" | "text";

type ModeChangeCallback = (mode: VoiceMode) => void;
type VoidCallback = () => void;

// ── Service ────────────────────────────────────────────

export class VoiceModeService {
  private _mode: VoiceMode;
  private backendWakeWord: BackendWakeWordService;
  private sttService: STTService;
  private modeChangeCallbacks: ModeChangeCallback[] = [];
  private _usingBackend = false;

  constructor(
    backendWakeWord: BackendWakeWordService,
    stt: STTService,
  ) {
    this.backendWakeWord = backendWakeWord;
    this.sttService = stt;
    this._mode = "text"; // safe default — no audio resources used
  }

  // ── Public API ─────────────────────────────────────

  /** Current interaction mode. */
  getMode(): VoiceMode {
    return this._mode;
  }

  /** True if the current wake-word session uses the backend service. */
  isUsingBackend(): boolean {
    return this._usingBackend;
  }

  /**
   * Switch to a new voice interaction mode.
   *
   * Tears down the previous mode's audio resources before
   * activating the new one.  For wake-word mode, prefers the
   * backend service when available, falling back to push-to-talk.
   *
   * @param mode - Target mode.
   * @returns The effective mode (may differ from requested if fallback occurred).
   */
  async setMode(mode: VoiceMode): Promise<VoiceMode> {
    if (mode === this._mode) return this._mode;

    // Tear down previous mode
    await this.deactivateMode(this._mode);

    // Activate new mode — may return a different effective mode
    const effectiveMode = await this.activateMode(mode);

    this._mode = effectiveMode;
    this.fireModeChange(effectiveMode);
    return effectiveMode;
  }

  // ── Events ─────────────────────────────────────────

  /**
   * Subscribe to mode change events.
   *
   * @returns Unsubscribe function.
   */
  onModeChange(callback: ModeChangeCallback): VoidCallback {
    this.modeChangeCallbacks.push(callback);
    return () => {
      this.modeChangeCallbacks = this.modeChangeCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  // ── Internal: mode lifecycle ───────────────────────

  /**
   * Activate the given mode.
   *
   * - **wake-word:** Try backend service (if available).
   *     If backend is unavailable, degrade to push-to-talk.
   * - **push-to-talk:** Nothing to pre-load — user triggers recording.
   * - **text:** Nothing to start.
   *
   * @returns The effective mode (may differ if wake-word degraded).
   */
  private async activateMode(mode: VoiceMode): Promise<VoiceMode> {
    switch (mode) {
      case "wake-word":
        return await this.activateWakeWord();

      case "push-to-talk":
        this._usingBackend = false;
        return "push-to-talk";

      case "text":
        this._usingBackend = false;
        return "text";
    }
  }

  /**
   * Attempt to activate wake word via the backend service.
   *
   * Proactively checks `isAvailable()` as a gate.  Falls back to
   * push-to-talk when the backend is unreachable or fails during
   * initialization (per DEC-033 — backend only, no TF.js fallback).
   *
   * @returns Effective mode — "wake-word" on success, "push-to-talk" on degradation.
   */
  private async activateWakeWord(): Promise<VoiceMode> {
    try {
      // Proactive availability gate: if already connected, skip init
      if (this.backendWakeWord.isAvailable()) {
        await this.backendWakeWord.startListening();
        this._usingBackend = true;
        return "wake-word";
      }

      // Not yet connected — try to initialize
      await this.backendWakeWord.initialize();
      await this.backendWakeWord.startListening();
      this._usingBackend = true;
      return "wake-word";
    } catch {
      // Backend unavailable — degrade to push-to-talk
      console.warn(
        "Backend wake word service unavailable, " +
          "degrading to push-to-talk.",
      );
      this._usingBackend = false;
      return "push-to-talk";
    }
  }

  /**
   * Deactivate / tear down the given mode.
   *
   * - **wake-word:** Stop the backend wake word service.
   * - **push-to-talk:** Stop any in-progress STT session.
   * - **text:** No-op.
   */
  private async deactivateMode(mode: VoiceMode): Promise<void> {
    switch (mode) {
      case "wake-word":
        this.backendWakeWord.stopListening();
        this._usingBackend = false;
        break;

      case "push-to-talk":
        this.sttService.stop();
        break;

      case "text":
        // Nothing to tear down
        break;
    }
  }

  // ── Event dispatch ─────────────────────────────────

  private fireModeChange(mode: VoiceMode): void {
    for (const cb of this.modeChangeCallbacks) {
      cb(mode);
    }
  }
}
