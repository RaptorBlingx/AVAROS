/**
 * Three-mode voice interaction toggle service.
 *
 * Controls how voice interaction is initiated:
 *   - **wake-word:** Hands-free — mic always on, TF.js model listens for
 *     "hey avaros", then STT pipeline picks up the utterance.
 *   - **push-to-talk:** Manual — user clicks a button to start/stop
 *     recording.  No model loaded, no continuous audio stream.
 *   - **text:** Keyboard-only — all audio services stopped, mic released.
 *
 * All three modes converge to the same HiveMind `sendUtterance()` call.
 *
 * Switching modes cleans up the previous mode's resources (model, mic,
 * audio stream) before activating the new one.
 */

import { WakeWordService } from "./wake-word";
import { STTService } from "./stt";

// ── Types ──────────────────────────────────────────────

export type VoiceMode = "wake-word" | "push-to-talk" | "text";

type ModeChangeCallback = (mode: VoiceMode) => void;
type VoidCallback = () => void;

// ── Service ────────────────────────────────────────────

export class VoiceModeService {
  private _mode: VoiceMode;
  private wakeWordService: WakeWordService;
  private sttService: STTService;
  private modeChangeCallbacks: ModeChangeCallback[] = [];

  constructor(wakeWord: WakeWordService, stt: STTService) {
    this.wakeWordService = wakeWord;
    this.sttService = stt;
    this._mode = "text"; // safe default — no audio resources used
  }

  // ── Public API ─────────────────────────────────────

  /** Current interaction mode. */
  getMode(): VoiceMode {
    return this._mode;
  }

  /**
   * Switch to a new voice interaction mode.
   *
   * Tears down the previous mode's audio resources before
   * activating the new one.
   *
   * @param mode - Target mode.
   */
  async setMode(mode: VoiceMode): Promise<void> {
    if (mode === this._mode) return;

    // Tear down previous mode
    await this.deactivateMode(this._mode);

    // Activate new mode
    await this.activateMode(mode);

    this._mode = mode;
    this.fireModeChange(mode);
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
   * - **wake-word:** Load TF.js model (if needed), start always-on listening.
   * - **push-to-talk:** Nothing to pre-load — user triggers recording.
   * - **text:** Nothing to start.
   */
  private async activateMode(mode: VoiceMode): Promise<void> {
    switch (mode) {
      case "wake-word":
        if (!this.wakeWordService.isModelLoaded()) {
          await this.wakeWordService.initialize();
        }
        await this.wakeWordService.startListening();
        break;

      case "push-to-talk":
        // STT service is created lazily per recording session
        break;

      case "text":
        // No audio resources needed
        break;
    }
  }

  /**
   * Deactivate / tear down the given mode.
   *
   * - **wake-word:** Stop the model, release continuous audio stream.
   * - **push-to-talk:** Stop any in-progress STT session.
   * - **text:** No-op.
   */
  private async deactivateMode(mode: VoiceMode): Promise<void> {
    switch (mode) {
      case "wake-word":
        this.wakeWordService.stopListening();
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
