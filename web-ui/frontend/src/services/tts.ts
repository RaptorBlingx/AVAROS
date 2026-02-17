/**
 * Browser Text-to-Speech service using the speechSynthesis API.
 *
 * Provides queued speech output with voice selection, rate/pitch/volume
 * control, and word-boundary events.  Works in all modern browsers.
 */

// ── Types ──────────────────────────────────────────────

export type TTSState = "idle" | "speaking" | "error" | "unsupported";

export interface TTSConfig {
  /** BCP-47 language tag, e.g. "en-US" or "tr-TR" */
  language: string;
  /** Specific voice name, or null for browser default */
  voice: string | null;
  /** Speech rate, 0.1–10 (default 1.0) */
  rate: number;
  /** Pitch, 0–2 (default 1.0) */
  pitch: number;
  /** Volume, 0–1 (default 1.0) */
  volume: number;
}

type StateCallback = (state: TTSState) => void;
type WordBoundaryCallback = (charIndex: number) => void;
type VoidCallback = () => void;

// ── Default config ─────────────────────────────────────

const DEFAULT_CONFIG: TTSConfig = {
  language: "en-US",
  voice: null,
  rate: 1.0,
  pitch: 1.0,
  volume: 1.0,
};

// ── Service ────────────────────────────────────────────

export class TTSService {
  private synth: SpeechSynthesis | null = null;
  private config: TTSConfig;
  private state: TTSState;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private queue: string[] = [];
  private voicesLoaded = false;

  private stateCallbacks: StateCallback[] = [];
  private wordBoundaryCallbacks: WordBoundaryCallback[] = [];

  constructor(config?: Partial<TTSConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    if (this.isSupported()) {
      this.synth = window.speechSynthesis;
      this.state = "idle";
      this.loadVoices();
    } else {
      this.state = "unsupported";
    }
  }

  // ── Lifecycle ──────────────────────────────────────

  /**
   * Speak the given text.
   *
   * If already speaking, the text is queued and spoken after the
   * current utterance finishes.  Resolves when the utterance
   * (or the last queued utterance) completes.
   *
   * @param text - The text to speak.
   */
  async speak(text: string): Promise<void> {
    if (!this.synth) {
      throw new Error("SpeechSynthesis is not supported in this browser");
    }

    if (this.state === "speaking") {
      this.queue.push(text);
      return;
    }

    return this.speakImmediate(text);
  }

  /** Cancel current speech and clear the queue. */
  stop(): void {
    this.queue = [];
    this.currentUtterance = null;
    this.synth?.cancel();
    this.setState("idle");
  }

  /** Pause current speech. */
  pause(): void {
    this.synth?.pause();
  }

  /** Resume paused speech. */
  resume(): void {
    this.synth?.resume();
  }

  /** True when the speechSynthesis API is available. */
  isSupported(): boolean {
    return (
      typeof window !== "undefined" && "speechSynthesis" in window
    );
  }

  // ── Voice management ───────────────────────────────

  /** Return all available voices. */
  getAvailableVoices(): SpeechSynthesisVoice[] {
    return this.synth?.getVoices() ?? [];
  }

  /**
   * Set the active voice by name.
   *
   * @param voiceName - The `SpeechSynthesisVoice.name` to select.
   */
  setVoice(voiceName: string): void {
    this.config.voice = voiceName;
  }

  /**
   * Return voices that match the given language prefix.
   *
   * @param lang - Language code, e.g. "en" or "en-US".
   */
  getVoicesForLanguage(lang: string): SpeechSynthesisVoice[] {
    const prefix = lang.toLowerCase();
    return this.getAvailableVoices().filter((v) =>
      v.lang.toLowerCase().startsWith(prefix),
    );
  }

  // ── Event subscriptions ────────────────────────────

  /**
   * Subscribe to state transitions.
   *
   * @returns Unsubscribe function.
   */
  onStateChange(callback: StateCallback): VoidCallback {
    this.stateCallbacks.push(callback);
    return () => {
      this.stateCallbacks = this.stateCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  /**
   * Subscribe to word-boundary events (fired as each word is spoken).
   *
   * @returns Unsubscribe function.
   */
  onWordBoundary(callback: WordBoundaryCallback): VoidCallback {
    this.wordBoundaryCallbacks.push(callback);
    return () => {
      this.wordBoundaryCallbacks = this.wordBoundaryCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  // ── Configuration ──────────────────────────────────

  /** Set speech rate (0.1–10). */
  setRate(rate: number): void {
    this.config.rate = Math.max(0.1, Math.min(10, rate));
  }

  /** Set pitch (0–2). */
  setPitch(pitch: number): void {
    this.config.pitch = Math.max(0, Math.min(2, pitch));
  }

  /** Set volume (0–1). */
  setVolume(volume: number): void {
    this.config.volume = Math.max(0, Math.min(1, volume));
  }

  /** Set language (BCP-47 tag). Takes effect on next speak(). */
  setLanguage(lang: string): void {
    this.config.language = lang;
  }

  /** Get current state. */
  getState(): TTSState {
    return this.state;
  }

  // ── Internal ───────────────────────────────────────

  private speakImmediate(text: string): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      if (!this.synth) {
        reject(new Error("SpeechSynthesis not available"));
        return;
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = this.config.language;
      utterance.rate = this.config.rate;
      utterance.pitch = this.config.pitch;
      utterance.volume = this.config.volume;

      // Apply voice selection
      const voice = this.findVoice();
      if (voice) {
        utterance.voice = voice;
      }

      utterance.onstart = () => {
        this.setState("speaking");
      };

      utterance.onend = () => {
        this.currentUtterance = null;
        this.processQueue(resolve);
      };

      utterance.onerror = (event) => {
        // "canceled" fires when we call stop() — not a real error
        if (event.error === "canceled") {
          resolve();
          return;
        }
        this.currentUtterance = null;
        this.setState("error");
        reject(new Error(`Speech synthesis error: ${event.error}`));
      };

      utterance.onboundary = (event) => {
        if (event.name === "word") {
          this.fireWordBoundary(event.charIndex);
        }
      };

      this.currentUtterance = utterance;
      this.synth.speak(utterance);
    });
  }

  private processQueue(resolve: () => void): void {
    if (this.queue.length > 0) {
      const next = this.queue.shift()!;
      void this.speakImmediate(next).then(resolve);
    } else {
      this.setState("idle");
      resolve();
    }
  }

  private findVoice(): SpeechSynthesisVoice | null {
    const voices = this.getAvailableVoices();
    if (voices.length === 0) return null;

    // Exact name match
    if (this.config.voice) {
      const match = voices.find((v) => v.name === this.config.voice);
      if (match) return match;
    }

    // For English playback, prefer well-known high-quality voices first.
    if (this.config.language.toLowerCase().startsWith("en")) {
      const preferredEnglishVoices = [
        "Samantha",
        "Alex",
        "Karen",
        "Google US English",
        "Microsoft Zira",
      ];

      const normalized = voices.map((voice) => ({
        voice,
        name: voice.name.toLowerCase(),
        lang: voice.lang.toLowerCase(),
      }));

      for (const preferredName of preferredEnglishVoices) {
        const hit = normalized.find(
          ({ name, lang }) =>
            name.includes(preferredName.toLowerCase()) &&
            lang.startsWith("en"),
        );
        if (hit) return hit.voice;
      }
    }

    // Prefer OS/browser default voice when it matches configured language.
    const langPrefix = this.config.language.toLowerCase();
    const defaultForLang = voices.find(
      (v) => v.default && v.lang.toLowerCase().startsWith(langPrefix),
    );
    if (defaultForLang) return defaultForLang;

    // Next best: any default voice.
    const defaultVoice = voices.find((v) => v.default);
    if (defaultVoice) return defaultVoice;

    // Fall back to first voice matching the language
    const langMatch = voices.find((v) =>
      v.lang.toLowerCase().startsWith(langPrefix),
    );
    if (langMatch) return langMatch;

    // Last resort: first available voice
    return voices[0] ?? null;
  }

  /**
   * Chrome loads voices asynchronously — listen for voiceschanged.
   */
  private loadVoices(): void {
    if (!this.synth) return;

    const voices = this.synth.getVoices();
    if (voices.length > 0) {
      this.voicesLoaded = true;
      return;
    }

    // Chrome: voices arrive asynchronously
    this.synth.addEventListener("voiceschanged", () => {
      this.voicesLoaded = true;
    }, { once: true });
  }

  // ── Event emitters ─────────────────────────────────

  private setState(state: TTSState): void {
    if (this.state === state) return;
    this.state = state;
    for (const cb of this.stateCallbacks) {
      cb(state);
    }
  }

  private fireWordBoundary(charIndex: number): void {
    for (const cb of this.wordBoundaryCallbacks) {
      cb(charIndex);
    }
  }
}
