/**
 * Text-to-Speech service using server-backed media playback when enabled,
 * with browser speechSynthesis as the fallback.
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
  /** Prefer same-origin server-generated WAV audio before browser TTS */
  serverAudio: boolean;
  /** Server TTS endpoint returning audio/wav */
  serverEndpoint: string;
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
  serverAudio: false,
  serverEndpoint: "/voice/tts",
};

const SERVER_TTS_CHUNK_MAX_CHARS = 170;
const SERVER_TTS_FETCH_TIMEOUT_MS = 15000;

// ── Service ────────────────────────────────────────────

export class TTSService {
  private synth: SpeechSynthesis | null = null;
  private config: TTSConfig;
  private state: TTSState;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private currentAudio: HTMLAudioElement | null = null;
  private currentAudioObjectUrl = "";
  private currentFetchController: AbortController | null = null;
  private queue: string[] = [];
  private voicesLoaded = false;
  private stopToken = 0;

  private stateCallbacks: StateCallback[] = [];
  private wordBoundaryCallbacks: WordBoundaryCallback[] = [];

  constructor(config?: Partial<TTSConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    if (this.isSupported()) {
      this.synth = this.isSpeechSynthesisSupported()
        ? window.speechSynthesis
        : null;
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
    if (!this.isSupported()) {
      throw new Error("Text-to-speech is not supported in this browser");
    }
    console.trace(`[AVAROS-DEBUG] TTS.speak called: "${text.slice(0, 60)}"`);
    const utterances = this.splitForPlayback(text);
    if (utterances.length === 0) return;

    if (this.state === "speaking") {
      this.queue.push(...utterances);
      return;
    }

    const [first, ...rest] = utterances;
    this.queue.push(...rest);
    return this.speakImmediate(first);
  }

  /** Cancel current speech and clear the queue. */
  stop(): void {
    this.stopToken += 1;
    this.queue = [];
    this.currentUtterance = null;
    this.currentFetchController?.abort();
    this.currentFetchController = null;
    if (this.currentAudio) {
      this.currentAudio.onended = null;
      this.currentAudio.onerror = null;
      this.currentAudio.pause();
      this.currentAudio.src = "";
      this.currentAudio.load?.();
      this.currentAudio = null;
    }
    if (this.currentAudioObjectUrl && typeof URL !== "undefined") {
      URL.revokeObjectURL(this.currentAudioObjectUrl);
      this.currentAudioObjectUrl = "";
    }
    this.synth?.cancel();
    this.setState("idle");
  }

  /** Pause current speech. */
  pause(): void {
    this.currentAudio?.pause();
    this.synth?.pause();
  }

  /** Resume paused speech. */
  resume(): void {
    void this.currentAudio?.play().catch(() => undefined);
    this.synth?.resume();
  }

  /** True when any TTS playback path is available. */
  isSupported(): boolean {
    return this.canUseServerAudio() || this.isSpeechSynthesisSupported();
  }

  /** True when the speechSynthesis API is available. */
  private isSpeechSynthesisSupported(): boolean {
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
    if (this.canUseServerAudio()) {
      return this.speakWithServerAudio(text).catch((error: unknown) => {
        if (!this.synth) throw error;
        return this.speakWithSpeechSynthesis(text);
      });
    }
    return this.speakWithSpeechSynthesis(text);
  }

  private canUseServerAudio(): boolean {
    return (
      this.config.serverAudio &&
      typeof window !== "undefined" &&
      typeof fetch !== "undefined" &&
      typeof Audio !== "undefined" &&
      typeof URL !== "undefined" &&
      typeof URL.createObjectURL === "function"
    );
  }

  private speakWithServerAudio(text: string): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const token = this.stopToken;
      this.setState("speaking");

      void (async () => {
        let objectUrl = "";
        const controller =
          typeof AbortController !== "undefined"
            ? new AbortController()
            : null;
        const fetchTimeout = window.setTimeout(() => {
          controller?.abort();
        }, SERVER_TTS_FETCH_TIMEOUT_MS);
        this.currentFetchController = controller;
        try {
          const response = await fetch(this.config.serverEndpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller?.signal,
            body: JSON.stringify({
              text,
              language: this.config.language,
              rate: this.config.rate,
              pitch: this.config.pitch,
              volume: this.config.volume,
            }),
          });
          if (!response.ok) {
            throw new Error(`Server TTS failed: ${response.status}`);
          }
          if (token !== this.stopToken) {
            if (this.currentFetchController === controller) {
              this.currentFetchController = null;
            }
            resolve();
            return;
          }
          const blob = await response.blob();
          objectUrl = URL.createObjectURL(blob);
          this.currentAudioObjectUrl = objectUrl;
          const audio = new Audio(objectUrl);
          audio.volume = this.config.volume;
          this.currentAudio = audio;

          const cleanup = () => {
            const urlToRevoke = objectUrl;
            objectUrl = "";
            if (this.currentAudio === audio) {
              this.currentAudio = null;
            }
            if (this.currentAudioObjectUrl === urlToRevoke) {
              this.currentAudioObjectUrl = "";
            }
            if (this.currentFetchController === controller) {
              this.currentFetchController = null;
            }
            if (urlToRevoke) {
              URL.revokeObjectURL(urlToRevoke);
            }
          };

          audio.onended = () => {
            cleanup();
            this.processQueue(resolve);
          };
          audio.onerror = () => {
            cleanup();
            this.setState("error");
            reject(new Error("Server TTS playback failed"));
          };
          await audio.play();
        } catch (error) {
          if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
          }
          if (this.currentAudioObjectUrl === objectUrl) {
            this.currentAudioObjectUrl = "";
          }
          this.currentAudio = null;
          if (this.currentFetchController === controller) {
            this.currentFetchController = null;
          }
          if (token !== this.stopToken) {
            resolve();
            return;
          }
          this.setState("idle");
          reject(error instanceof Error ? error : new Error("Server TTS failed"));
        } finally {
          window.clearTimeout(fetchTimeout);
        }
      })();
    });
  }

  private speakWithSpeechSynthesis(text: string): Promise<void> {
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

  private splitForPlayback(text: string): string[] {
    const normalized = text.replace(/\s+/g, " ").trim();
    if (!normalized) return [];
    if (
      !this.canUseServerAudio() ||
      normalized.length <= SERVER_TTS_CHUNK_MAX_CHARS
    ) {
      return [normalized];
    }

    const sentences = this.splitIntoSentences(normalized);
    const chunks: string[] = [];
    let current = "";

    for (const sentence of sentences) {
      if (!sentence) continue;
      if (sentence.length > SERVER_TTS_CHUNK_MAX_CHARS) {
        if (current) {
          chunks.push(current);
          current = "";
        }
        chunks.push(...this.splitLongSentence(sentence));
        continue;
      }

      const next = current ? `${current} ${sentence}` : sentence;
      if (next.length > SERVER_TTS_CHUNK_MAX_CHARS && current) {
        chunks.push(current);
        current = sentence;
      } else {
        current = next;
      }
    }

    if (current) chunks.push(current);
    return chunks;
  }

  private splitLongSentence(sentence: string): string[] {
    const chunks: string[] = [];
    let current = "";
    for (const word of sentence.split(/\s+/)) {
      const next = current ? `${current} ${word}` : word;
      if (next.length > SERVER_TTS_CHUNK_MAX_CHARS && current) {
        chunks.push(current);
        current = word;
      } else {
        current = next;
      }
    }
    if (current) chunks.push(current);
    return chunks;
  }

  private splitIntoSentences(text: string): string[] {
    const sentences: string[] = [];
    let start = 0;

    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (!".!?;".includes(char)) continue;

      const prev = text[index - 1] ?? "";
      const next = text[index + 1] ?? "";
      if (char === "." && /\d/.test(prev) && /\d/.test(next)) continue;

      if (next && !/\s/.test(next)) continue;

      const sentence = text.slice(start, index + 1).trim();
      if (sentence) sentences.push(sentence);
      start = index + 1;
      while (start < text.length && /\s/.test(text[start])) start += 1;
      index = start - 1;
    }

    const rest = text.slice(start).trim();
    if (rest) sentences.push(rest);
    return sentences.length > 0 ? sentences : [text];
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
