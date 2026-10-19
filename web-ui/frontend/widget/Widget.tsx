import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import { normalizeUtteranceForIntent } from "../src/services/intent-normalizer";
import { BackendWakeWordService } from "../src/services/wake-word-backend";
import type { DetectionPayload } from "../src/services/wake-word-backend";
import { ConnectionManager } from "./ConnectionManager";
import {
  detectWidgetLanguage,
  normalizeWidgetLanguage,
  responseLanguage,
} from "./language";
import { WidgetButton } from "./WidgetButton";
import { WidgetPanel } from "./WidgetPanel";
import { resolveServerTtsUrl, splitWidgetTtsText } from "./tts";
import type {
  ChatMessage,
  WidgetConfig,
  WidgetConnectionState,
  WidgetDefaultMode,
  WidgetMode,
  WidgetPublicApi,
  WidgetTheme,
  WidgetVisualState,
  VoiceTurnStatus,
} from "./types";

type WidgetProps = {
  config: WidgetConfig;
  configError: string | null;
  onReady: (api: Omit<WidgetPublicApi, "destroy">) => void;
};

type BrowserSpeechRecognitionCtor = {
  new (): SpeechRecognition;
};

type BrowserAudioContextCtor = {
  new (): AudioContext;
};

type WakeVoiceLanguage = "en-US" | "tr-TR";

function normalizeWakeVoiceLanguage(value: unknown): WakeVoiceLanguage {
  return normalizeWidgetLanguage(value) as WakeVoiceLanguage;
}

function getSpeechRecognitionCtor(): BrowserSpeechRecognitionCtor | null {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: BrowserSpeechRecognitionCtor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function getAudioContextCtor(): BrowserAudioContextCtor | null {
  const audioWindow = window as typeof window & {
    AudioContext?: BrowserAudioContextCtor;
    webkitAudioContext?: BrowserAudioContextCtor;
  };
  return audioWindow.AudioContext ?? audioWindow.webkitAudioContext ?? null;
}

function pickInitialMode(
  disabledModes: WidgetMode[],
  defaultMode?: WidgetDefaultMode,
): WidgetMode {
  const explicitDefault = defaultMode === "inherit" ? undefined : defaultMode;
  const preferredOrder: WidgetMode[] = explicitDefault
    ? [explicitDefault, "push-to-talk", "wake-word", "text"]
    : ["push-to-talk", "wake-word", "text"];
  const nextMode = preferredOrder.find((mode) => !disabledModes.includes(mode));
  return nextMode ?? "text";
}

function isWidgetMode(value: unknown): value is WidgetMode {
  return value === "wake-word" || value === "push-to-talk" || value === "text";
}

async function fetchInheritedVoiceMode(avarosUrl: string): Promise<WidgetMode | null> {
  try {
    const response = await fetch(new URL("/voice/preferences", avarosUrl), {
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { voice_mode?: unknown };
    return isWidgetMode(data.voice_mode) ? data.voice_mode : null;
  } catch {
    return null;
  }
}

/** Cooldown to suppress duplicate events from one spoken wake phrase. */
const WAKE_WORD_PROMPT_COOLDOWN_MS = 3000;
const WAKE_WORD_REARM_DELAY_MS = 600;
const RESPONSE_FALLBACK_TIMEOUT_MS = 25000;
const SPEECH_EVENT_DEDUP_MS = 1200;
const SERVER_TTS_FETCH_TIMEOUT_MS = 15000;

function makeMessage(
  source: "user" | "avaros",
  text: string,
  details: Pick<ChatMessage, "inputKind" | "language" | "inventoryNames"> = {},
): ChatMessage {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${source}-${Date.now()}`,
    source,
    text,
    timestamp: new Date(),
    ...details,
  };
}

function deriveTheme(theme: WidgetTheme): "light" | "dark" {
  if (theme === "light") return "light";
  if (theme === "dark") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function pickPreferredVoice(
  voices: SpeechSynthesisVoice[],
  language: string,
): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const languagePrefix = language.toLowerCase().split("-")[0];
  const matching = voices.find((voice) => voice.lang.toLowerCase().startsWith(languagePrefix));
  if (matching) return matching;
  return null;
}

export function Widget({ config, configError, onReady }: WidgetProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const managerRef = useRef<ConnectionManager | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const activeTtsAudioRef = useRef<HTMLAudioElement | null>(null);
  const activeTtsAudioContextRef = useRef<AudioContext | null>(null);
  const activeTtsSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const activeTtsGainRef = useRef<GainNode | null>(null);
  const activeTtsPlaybackCancelRef = useRef<(() => void) | null>(null);
  const activeTtsObjectUrlsRef = useRef<Set<string>>(new Set());
  const activeTtsAbortControllersRef = useRef<Set<AbortController>>(new Set());
  const ttsPlaybackTokenRef = useRef(0);
  const fallbackTimerRef = useRef<number | null>(null);
  const completionTimerRef = useRef<number | null>(null);
  const modeRef = useRef<WidgetMode>(
    pickInitialMode(config.disabledModes, config.defaultMode),
  );
  const wakeWordArmedRef = useRef(false);
  // Text turns may keep using bilingual dialogue routing. Hands-free turns
  // deliberately retain the user's explicit EN/TR choice across text/session
  // locale changes.
  const wakeVoiceLanguageRef = useRef(normalizeWakeVoiceLanguage(config.language));
  const pendingVoiceResponseLanguageRef = useRef<WakeVoiceLanguage | null>(null);
  const responseResolvedRef = useRef(true);
  const ttsVoiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const activeLanguageRef = useRef(normalizeWidgetLanguage(config.language));
  const backendWakeWordRef = useRef<BackendWakeWordService | null>(null);
  const wakeWordPromptCooldownRef = useRef(0);
  const lastAssistantSpeechRef = useRef<{ text: string; at: number }>({
    text: "",
    at: 0,
  });
  const appendMessageRef = useRef<(msg: ChatMessage) => void>(() => {});
  const speakAssistantTextRef = useRef<
    (text: string, language?: string) => Promise<void>
  >(async () => {});
  const sendTextRef = useRef<
    (text: string, language?: string, inputKind?: "text" | "voice") => Promise<void>
  >(
    async () => {},
  );
  const resumeWakeWordRef = useRef<() => void>(() => {});

  const [panelOpen, setPanelOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [processing, setProcessing] = useState(false);
  const [connectionState, setConnectionState] = useState<WidgetConnectionState>("disconnected");
  const [mode, setMode] = useState<WidgetMode>(
    pickInitialMode(config.disabledModes, config.defaultMode),
  );
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(deriveTheme(config.theme));
  const [isTtsSpeaking, setIsTtsSpeaking] = useState(false);
  const isTtsSpeakingRef = useRef(false);
  const setTtsSpeakingRef = useRef<(v: boolean) => void>(() => {});
  setTtsSpeakingRef.current = (value: boolean) => {
    isTtsSpeakingRef.current = value;
    setIsTtsSpeaking(value);
  };
  const [micActive, setMicActive] = useState(false);
  const [micPermission, setMicPermission] = useState<
    "prompt" | "granted" | "denied" | "unsupported"
  >("prompt");
  const [micError, setMicError] = useState<string | null>(null);
  const [wakeWordArmed, setWakeWordArmed] = useState(false);
  const [wakeWordLabel, setWakeWordLabel] = useState("Hey Jarvis");
  const [wakeVoiceLanguage, setWakeVoiceLanguage] = useState<WakeVoiceLanguage>(
    normalizeWakeVoiceLanguage(config.language),
  );
  const [ttsVoice, setTtsVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [voiceTurnStatus, setVoiceTurnStatus] = useState<VoiceTurnStatus | null>(null);

  useEffect(() => {
    if (config.defaultMode !== "inherit") return;
    let cancelled = false;

    void fetchInheritedVoiceMode(config.avarosUrl).then((inheritedMode) => {
      if (cancelled || !inheritedMode) return;
      if (config.disabledModes.includes(inheritedMode)) return;
      modeRef.current = inheritedMode;
      setMode(inheritedMode);
    });

    return () => {
      cancelled = true;
    };
  }, [config.avarosUrl, config.defaultMode, config.disabledModes]);

  useEffect(() => {
    ttsVoiceRef.current = ttsVoice;
  }, [ttsVoice]);

  useEffect(() => {
    const language = normalizeWidgetLanguage(config.language);
    const wakeLanguage = normalizeWakeVoiceLanguage(config.language);
    activeLanguageRef.current = language;
    wakeVoiceLanguageRef.current = wakeLanguage;
    setWakeVoiceLanguage(wakeLanguage);
    managerRef.current?.setLanguage(language);
  }, [config.language]);

  const selectWakeVoiceLanguage = useCallback((language: WakeVoiceLanguage) => {
    wakeVoiceLanguageRef.current = language;
    setWakeVoiceLanguage(language);
  }, []);

  const ttsWatcherRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTtsWatcher = useCallback(() => {
    if (ttsWatcherRef.current !== null) {
      clearInterval(ttsWatcherRef.current);
      ttsWatcherRef.current = null;
    }
  }, []);

  const cleanupServerTtsAudio = useCallback(() => {
    const cancelPlayback = activeTtsPlaybackCancelRef.current;
    activeTtsPlaybackCancelRef.current = null;
    if (cancelPlayback) {
      cancelPlayback();
    }

    const source = activeTtsSourceRef.current;
    if (source) {
      source.onended = null;
      try { source.stop(); } catch { /* source may already be stopped */ }
      try { source.disconnect(); } catch { /* already disconnected */ }
      activeTtsSourceRef.current = null;
    }

    const gain = activeTtsGainRef.current;
    if (gain) {
      try { gain.disconnect(); } catch { /* already disconnected */ }
      activeTtsGainRef.current = null;
    }

    const audio = activeTtsAudioRef.current;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
      audio.src = "";
      audio.load?.();
      activeTtsAudioRef.current = null;
    }
    for (const objectUrl of activeTtsObjectUrlsRef.current) {
      URL.revokeObjectURL(objectUrl);
    }
    activeTtsObjectUrlsRef.current.clear();
  }, []);

  const stopAssistantSpeech = useCallback(() => {
    ttsPlaybackTokenRef.current += 1;
    clearTtsWatcher();
    for (const controller of activeTtsAbortControllersRef.current) {
      controller.abort();
    }
    activeTtsAbortControllersRef.current.clear();
    cleanupServerTtsAudio();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setTtsSpeakingRef.current?.(false);
  }, [cleanupServerTtsAudio, clearTtsWatcher]);

  const speakAssistantText = useCallback(
    async (text: string, language = activeLanguageRef.current): Promise<void> => {
      const cleaned = text.trim();
      if (!cleaned) return;
      const speechLanguage = normalizeWidgetLanguage(language);
      activeLanguageRef.current = speechLanguage;
      managerRef.current?.setLanguage(speechLanguage);

      stopAssistantSpeech();
      const playbackToken = ttsPlaybackTokenRef.current;
      setTtsSpeakingRef.current?.(true);

      // Pause browser STT during TTS to avoid echo pickup.
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch { /* already stopped */ }
      }

      const finishCurrentSpeech = () => {
        if (playbackToken !== ttsPlaybackTokenRef.current) return;
        clearTtsWatcher();
        cleanupServerTtsAudio();
        setTtsSpeakingRef.current?.(false);
      };

      const playBrowserSpeech = (): Promise<boolean> => {
        if (!("speechSynthesis" in window)) return Promise.resolve(false);
        if (playbackToken !== ttsPlaybackTokenRef.current) return Promise.resolve(true);

        return new Promise<boolean>((resolve) => {
          let settled = false;
          const finish = (played: boolean) => {
            if (settled) return;
            settled = true;
            finishCurrentSpeech();
            resolve(played);
          };

          const utterance = new SpeechSynthesisUtterance(cleaned);
          utterance.lang = speechLanguage;
          const voice = pickPreferredVoice(
            window.speechSynthesis.getVoices(),
            speechLanguage,
          );
          ttsVoiceRef.current = voice;
          if (voice) {
            utterance.voice = voice;
          }

          utterance.onend = () => finish(true);
          utterance.onerror = () => finish(false);

          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(utterance);

          ttsWatcherRef.current = setInterval(() => {
            if (!window.speechSynthesis.speaking) {
              finish(true);
            }
          }, 200);
        });
      };

      const abortServerFetches = () => {
        for (const controller of activeTtsAbortControllersRef.current) {
          controller.abort();
        }
        activeTtsAbortControllersRef.current.clear();
      };

      const fetchServerClip = async (
        chunk: string,
      ): Promise<{ blob: Blob } | null> => {
        const controller = new AbortController();
        activeTtsAbortControllersRef.current.add(controller);
        const timeout = window.setTimeout(() => {
          controller.abort();
        }, SERVER_TTS_FETCH_TIMEOUT_MS);
        try {
          const response = await fetch(resolveServerTtsUrl(config.avarosUrl), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: chunk, language: speechLanguage }),
            signal: controller.signal,
          });
          if (!response.ok || playbackToken !== ttsPlaybackTokenRef.current) {
            return null;
          }
          const blob = await response.blob();
          if (playbackToken !== ttsPlaybackTokenRef.current) return null;
          return { blob };
        } catch {
          return null;
        } finally {
          window.clearTimeout(timeout);
          activeTtsAbortControllersRef.current.delete(controller);
        }
      };

      const cleanupHtmlAudioClip = (
        audio: HTMLAudioElement,
        objectUrl: string,
      ) => {
        audio.onended = null;
        audio.onerror = null;
        if (activeTtsAudioRef.current === audio) {
          activeTtsAudioRef.current = null;
        }
        if (activeTtsObjectUrlsRef.current.has(objectUrl)) {
          URL.revokeObjectURL(objectUrl);
          activeTtsObjectUrlsRef.current.delete(objectUrl);
        }
      };

      const cleanupWebAudioClip = (
        source: AudioBufferSourceNode,
        gain: GainNode,
      ) => {
        source.onended = null;
        if (activeTtsSourceRef.current === source) {
          activeTtsSourceRef.current = null;
        }
        if (activeTtsGainRef.current === gain) {
          activeTtsGainRef.current = null;
        }
        try { source.disconnect(); } catch { /* already disconnected */ }
        try { gain.disconnect(); } catch { /* already disconnected */ }
      };

      const playServerClipWithAudioElement = (blob: Blob): Promise<void> => {
        return new Promise<void>((resolve, reject) => {
          if (
            typeof Audio === "undefined" ||
            typeof URL === "undefined" ||
            typeof URL.createObjectURL !== "function"
          ) {
            reject(new Error("HTMLAudioElement playback unavailable"));
            return;
          }

          const objectUrl = URL.createObjectURL(blob);
          activeTtsObjectUrlsRef.current.add(objectUrl);
          const audio = new Audio(objectUrl);
          audio.preload = "auto";
          activeTtsAudioRef.current = audio;

          let settled = false;
          const finish = () => {
            if (settled) return;
            settled = true;
            if (activeTtsPlaybackCancelRef.current === finish) {
              activeTtsPlaybackCancelRef.current = null;
            }
            cleanupHtmlAudioClip(audio, objectUrl);
            resolve();
          };
          activeTtsPlaybackCancelRef.current = finish;

          audio.onended = finish;
          audio.onerror = () => {
            if (activeTtsPlaybackCancelRef.current === finish) {
              activeTtsPlaybackCancelRef.current = null;
            }
            cleanupHtmlAudioClip(audio, objectUrl);
            reject(new Error("Server TTS playback failed"));
          };
          void audio.play().catch((error) => {
            if (activeTtsPlaybackCancelRef.current === finish) {
              activeTtsPlaybackCancelRef.current = null;
            }
            cleanupHtmlAudioClip(audio, objectUrl);
            reject(error);
          });
        });
      };

      const playServerClipWithWebAudio = async (blob: Blob): Promise<boolean> => {
        const AudioContextCtor = getAudioContextCtor();
        if (!AudioContextCtor) return false;
        if (playbackToken !== ttsPlaybackTokenRef.current) return true;

        let context = activeTtsAudioContextRef.current;
        if (!context || context.state === "closed") {
          context = new AudioContextCtor();
          activeTtsAudioContextRef.current = context;
        }
        if (context.state === "suspended") {
          await context.resume();
        }
        if (playbackToken !== ttsPlaybackTokenRef.current) return true;

        let buffer: AudioBuffer;
        try {
          const arrayBuffer = await blob.arrayBuffer();
          if (playbackToken !== ttsPlaybackTokenRef.current) return true;
          buffer = await context.decodeAudioData(arrayBuffer);
        } catch {
          return false;
        }
        if (playbackToken !== ttsPlaybackTokenRef.current) return true;

        await new Promise<void>((resolve, reject) => {
          const source = context.createBufferSource();
          const gain = context.createGain();
          source.buffer = buffer;
          source.connect(gain);
          gain.connect(context.destination);

          activeTtsSourceRef.current = source;
          activeTtsGainRef.current = gain;

          let settled = false;
          const finish = () => {
            if (settled) return;
            settled = true;
            if (activeTtsPlaybackCancelRef.current === finish) {
              activeTtsPlaybackCancelRef.current = null;
            }
            cleanupWebAudioClip(source, gain);
            resolve();
          };
          activeTtsPlaybackCancelRef.current = finish;

          source.onended = finish;

          try {
            const startAt = context.currentTime + 0.015;
            const duration = Math.max(0, buffer.duration);
            const fadeSeconds = Math.min(0.025, Math.max(0.005, duration / 8));
            gain.gain.cancelScheduledValues(startAt);
            gain.gain.setValueAtTime(0, startAt);
            gain.gain.linearRampToValueAtTime(1, startAt + fadeSeconds);
            if (duration > fadeSeconds * 3) {
              gain.gain.setValueAtTime(1, startAt + duration - fadeSeconds);
              gain.gain.linearRampToValueAtTime(0, startAt + duration);
            }
            source.start(startAt);
          } catch (error) {
            if (activeTtsPlaybackCancelRef.current === finish) {
              activeTtsPlaybackCancelRef.current = null;
            }
            cleanupWebAudioClip(source, gain);
            reject(error);
          }
        });
        return true;
      };

      const playServerClip = async (blob: Blob): Promise<void> => {
        const playedWithWebAudio = await playServerClipWithWebAudio(blob);
        if (playedWithWebAudio) return;
        await playServerClipWithAudioElement(blob);
      };

      const playServerSpeech = async (): Promise<boolean> => {
        if (typeof fetch === "undefined") {
          return false;
        }

        const chunks = splitWidgetTtsText(cleaned);
        if (chunks.length === 0) return false;
        let nextClipPromise: Promise<{ blob: Blob } | null> | null =
          fetchServerClip(chunks[0]);
        let playedAny = false;

        try {
          for (let index = 0; index < chunks.length; index += 1) {
            if (playbackToken !== ttsPlaybackTokenRef.current) return true;
            const clip = await nextClipPromise;
            nextClipPromise =
              index + 1 < chunks.length
                ? fetchServerClip(chunks[index + 1])
                : null;
            if (!clip) {
              if (!playedAny) {
                abortServerFetches();
                return false;
              }
              return true;
            }
            if (playbackToken !== ttsPlaybackTokenRef.current) {
              return true;
            }
            await playServerClip(clip.blob);
            playedAny = true;
          }
          return playedAny;
        } catch {
          abortServerFetches();
          return playedAny;
        }
      };

      try {
        if (config.ttsEngine === "server") {
          const played = await playServerSpeech();
          if (!played) {
            await playBrowserSpeech();
          }
        } else {
          const played = await playBrowserSpeech();
          if (!played) {
            await playServerSpeech();
          }
        }
      } finally {
        finishCurrentSpeech();
      }
    },
    [
      cleanupServerTtsAudio,
      clearTtsWatcher,
      config.avarosUrl,
      config.ttsEngine,
      stopAssistantSpeech,
    ],
  );

  speakAssistantTextRef.current = speakAssistantText;

  // ── Backend Wake Word lifecycle ────────────────────

  const disposeBackendWakeWord = useCallback(() => {
    backendWakeWordRef.current?.dispose();
    backendWakeWordRef.current = null;
  }, []);

  const ensureConnected = useCallback(() => {
    if (configError) return;
    if (!managerRef.current) return;
    managerRef.current.connect();
  }, [configError]);

  const requestMicPermission = useCallback(async (): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission("unsupported");
      setMicError("Microphone API is unavailable in this browser.");
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission("granted");
      setMicError(null);
      return true;
    } catch (error) {
      if (
        error instanceof DOMException &&
        (error.name === "NotAllowedError" || error.name === "PermissionDeniedError")
      ) {
        setMicPermission("denied");
        setMicError("Microphone permission blocked. Allow access and retry.");
        return false;
      }
      setMicPermission("denied");
      setMicError("Could not access microphone.");
      return false;
    }
  }, []);

  const clearFallbackTimer = useCallback(() => {
    if (fallbackTimerRef.current !== null) {
      window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
  }, []);

  const clearCompletionTimer = useCallback(() => {
    if (completionTimerRef.current !== null) {
      window.clearTimeout(completionTimerRef.current);
      completionTimerRef.current = null;
    }
  }, []);

  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (
        last &&
        last.source === message.source &&
        last.text.trim() === message.text.trim()
      ) {
        return prev;
      }
      return [...prev.slice(-49), message];
    });
  }, []);

  const resolveAssistantMessage = useCallback(
    (text: string, language = activeLanguageRef.current, speechText?: string, inventoryNames?: string[]) => {
      const cleaned = text.trim();
      if (!cleaned) return;
      const responseLocale = pendingVoiceResponseLanguageRef.current
        ?? normalizeWidgetLanguage(language);
      pendingVoiceResponseLanguageRef.current = null;
      activeLanguageRef.current = responseLocale;
      managerRef.current?.setLanguage(responseLocale);
      responseResolvedRef.current = true;
      clearFallbackTimer();
      clearCompletionTimer();
      setProcessing(false);
      if (modeRef.current === "wake-word") {
        setVoiceTurnStatus("responding");
      }
      appendMessage(makeMessage("avaros", cleaned, { language: responseLocale.startsWith("tr") ? "tr-TR" : "en-US", inventoryNames }));
      const now = Date.now();
      const isDuplicateSpeech =
        lastAssistantSpeechRef.current.text === cleaned &&
        now - lastAssistantSpeechRef.current.at < SPEECH_EVENT_DEDUP_MS;
      lastAssistantSpeechRef.current = { text: cleaned, at: now };
      if (!isDuplicateSpeech) {
        void speakAssistantText(speechText?.trim() || cleaned, responseLocale).finally(() => {
          if (modeRef.current === "wake-word") {
            setVoiceTurnStatus("rearming");
          }
          resumeWakeWordRef.current();
        });
      } else {
        if (modeRef.current === "wake-word") {
          setVoiceTurnStatus("rearming");
        }
        resumeWakeWordRef.current();
      }
    },
    [appendMessage, clearCompletionTimer, clearFallbackTimer, speakAssistantText],
  );

  const handleCancelRequest = useCallback(() => {
    responseResolvedRef.current = true;
    pendingVoiceResponseLanguageRef.current = null;
    clearFallbackTimer();
    clearCompletionTimer();
    stopAssistantSpeech();
    void managerRef.current?.interrupt().catch(() => undefined);
    setProcessing(false);
    appendMessage(makeMessage("avaros", "Request cancelled."));
    resumeWakeWordRef.current();
  }, [
    appendMessage,
    clearCompletionTimer,
    clearFallbackTimer,
    stopAssistantSpeech,
  ]);

  const handleStopResponse = useCallback(() => {
    stopAssistantSpeech();
    void managerRef.current?.interrupt().catch(() => undefined);
  }, [stopAssistantSpeech]);

  const stopListening = useCallback(() => {
    if (modeRef.current === "wake-word") {
      backendWakeWordRef.current?.stopListening();
      wakeWordArmedRef.current = false;
      setWakeWordArmed(false);
      setMicActive(false);
      return;
    }

    const recognition = recognitionRef.current;
    if (!recognition) {
      setMicActive(false);
      return;
    }

    recognition.onstart = null;
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    recognitionRef.current = null;

    try {
      recognition.stop();
    } catch {
      // Ignore stop errors from closed recognizers.
    }

    setMicActive(false);
  }, []);

  const sendText = useCallback(
    async (
      text: string,
      explicitLanguage?: string,
      inputKind: "text" | "voice" = "text",
    ) => {
      const cleaned = text.trim();
      if (!cleaned) return;
      if (configError) return;
      ensureConnected();
      const manager = managerRef.current;
      if (!manager) return;

      const toSend = normalizeUtteranceForIntent(cleaned);
      const requestLanguage = explicitLanguage
        ? normalizeWidgetLanguage(explicitLanguage)
        : detectWidgetLanguage(cleaned, activeLanguageRef.current);
      activeLanguageRef.current = requestLanguage;
      manager.setLanguage(requestLanguage);
      if (inputKind === "voice") {
        pendingVoiceResponseLanguageRef.current = normalizeWakeVoiceLanguage(requestLanguage);
      }

      appendMessage(
        makeMessage("user", cleaned, {
          inputKind,
          language:
            inputKind === "voice"
              ? requestLanguage === "tr-TR"
                ? "tr-TR"
                : "en-US"
              : undefined,
        }),
      );
      setProcessing(true);
      if (inputKind === "voice") {
        setVoiceTurnStatus("processing");
      }
      responseResolvedRef.current = false;
      clearFallbackTimer();
      clearCompletionTimer();
      fallbackTimerRef.current = window.setTimeout(() => {
        responseResolvedRef.current = true;
        pendingVoiceResponseLanguageRef.current = null;
        setProcessing(false);
        appendMessage(
          makeMessage(
            "avaros",
            "No response from AVAROS for this command. Check platform connectivity.",
          ),
        );
        resumeWakeWordRef.current();
      }, RESPONSE_FALLBACK_TIMEOUT_MS);

      try {
        await manager.sendUtterance(toSend, requestLanguage);
      } catch {
        clearFallbackTimer();
        clearCompletionTimer();
        responseResolvedRef.current = true;
        pendingVoiceResponseLanguageRef.current = null;
        setProcessing(false);
        appendMessage(makeMessage("avaros", "Send failed. Check connection."));
        resumeWakeWordRef.current();
      }
    },
    [
      appendMessage,
      clearCompletionTimer,
      clearFallbackTimer,
      configError,
      ensureConnected,
      config.language,
      config.sessionToken,
    ],
  );

  const startListening = useCallback(async () => {
    if (configError) return;

    if (!window.isSecureContext && window.location.hostname !== "localhost") {
      setMicError("Microphone requires localhost or HTTPS.");
      return;
    }

    const activeMode = modeRef.current;
    if (activeMode === "text") {
      setMicError("Text mode active. Switch to voice mode.");
      return;
    }
    if (micPermission !== "granted") {
      const granted = await requestMicPermission();
      if (!granted) {
        setMicError("Allow microphone first.");
        return;
      }
    }

    if (activeMode === "wake-word") {
      const wakeWord = backendWakeWordRef.current;
      if (!wakeWord) {
        setMicError("Wake-word service is reconnecting. Try again shortly.");
        return;
      }
      try {
        await wakeWord.initialize();
        await wakeWord.startListening();
        setMicActive(true);
        setMicError(null);
      } catch {
        setMicActive(false);
        setMicError("Wake-word service unavailable. Use push-to-talk or text.");
      }
      return;
    }

    const RecognitionCtor = getSpeechRecognitionCtor();
    if (!RecognitionCtor) {
      setMicError("Speech recognition not supported in this browser.");
      return;
    }

    if (recognitionRef.current) {
      stopListening();
    }
    setMicError(null);

    const recognition = new RecognitionCtor();
    recognitionRef.current = recognition;
    recognition.lang = activeLanguageRef.current;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    // Never use continuous mode. In wake-word mode the backend handles
    // passive listening; browser STT only captures one command at a time.
    recognition.continuous = false;

    recognition.onstart = () => {
      setMicActive(true);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result.isFinal) continue;
        const transcript = result[0]?.transcript?.trim();
        if (!transcript) continue;

        // Send the command to AVAROS.
        wakeWordArmedRef.current = false;
        setWakeWordArmed(false);
        void sendText(transcript);
        stopListening();
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech" || event.error === "aborted") {
        // In wake-word armed mode, silence means user didn't follow up.
        if (wakeWordArmedRef.current) {
          wakeWordArmedRef.current = false;
          setWakeWordArmed(false);
        }
        return;
      }
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setMicError("Microphone permission blocked. Allow access and retry.");
      } else if (event.error === "audio-capture") {
        setMicError("No microphone detected on this device.");
      } else if (event.error === "no-speech") {
        setMicError("No speech detected. Try again.");
      } else {
        setMicError("Voice capture failed. Try again.");
      }
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setMicActive(false);
      // If wake-word armed but no command captured, disarm.
      if (wakeWordArmedRef.current) {
        wakeWordArmedRef.current = false;
        setWakeWordArmed(false);
      }
    };

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setMicActive(false);
      setMicError("Could not start microphone.");
    }
  }, [
    config.language,
    config.sessionToken,
    configError,
    micPermission,
    requestMicPermission,
    sendText,
    stopListening,
  ]);

  useEffect(() => {
    if (!config.autoOpen) return;
    setPanelOpen(true);
    ensureConnected();
  }, [config.autoOpen, ensureConnected]);

  const initialPromptSentRef = useRef(false);
  useEffect(() => {
    if (!config.initialPrompt || initialPromptSentRef.current) return;
    if (connectionState !== "connected") return;
    initialPromptSentRef.current = true;
    void sendText(config.initialPrompt);
  }, [config.initialPrompt, connectionState, sendText]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    wakeWordArmedRef.current = wakeWordArmed;
  }, [wakeWordArmed]);

  // Keep refs current so the onDetected handler never captures stale callbacks.
  appendMessageRef.current = appendMessage;
  sendTextRef.current = sendText;

  resumeWakeWordRef.current = () => {
    if (modeRef.current !== "wake-word") return;
    if (isTtsSpeakingRef.current) return;
    setVoiceTurnStatus("rearming");
    window.setTimeout(() => {
      if (modeRef.current !== "wake-word" || isTtsSpeakingRef.current) return;
      const wakeWord = backendWakeWordRef.current;
      if (!wakeWord) return;
      void wakeWord
        .initialize()
        .then(() => wakeWord.startListening())
        .then(() => {
          setMicActive(true);
          setMicError(null);
          setVoiceTurnStatus("armed");
        })
        .catch(() => {
          setMicActive(false);
          setMicError("Wake-word service disconnected. Use push-to-talk or text.");
        });
    }, WAKE_WORD_REARM_DELAY_MS);
  };

  // ── Backend Wake Word: lifecycle + detection (single effect) ──
  useEffect(() => {
    if (mode !== "wake-word") {
      backendWakeWordRef.current?.dispose();
      backendWakeWordRef.current = null;
      return;
    }

    if (backendWakeWordRef.current) return;
    const bww = new BackendWakeWordService({
      wsUrl: config.wakeWordUrl,
      sessionToken: config.sessionToken,
      captureUtterance: true,
    });
    backendWakeWordRef.current = bww;

    const unsubState = bww.onStateChange((state) => {
      if (state === "listening" || state === "capturing") {
        setMicActive(true);
        setMicError(null);
        setVoiceTurnStatus(
          state === "capturing" || wakeWordArmedRef.current
            ? "listening"
            : "armed",
        );
      } else if (state === "processing" || state === "idle") {
        setMicActive(false);
        if (state === "processing" && wakeWordArmedRef.current) {
          setVoiceTurnStatus("transcribing");
        }
      } else if (state === "error") {
        setMicActive(false);
        setMicError("Wake-word service disconnected. Reconnecting…");
      }
    });

    // Wire onDetected BEFORE startListening to avoid losing events.
    const unsubDetected = bww.onDetected((_payload: DetectionPayload) => {
      setWakeWordLabel(bww.getWakeWordLabel());
      // Cooldown: suppress re-triggers within a short window (e.g. TTS echo).
      if (Date.now() < wakeWordPromptCooldownRef.current) return;
      if (
        isTtsSpeakingRef.current ||
        ("speechSynthesis" in window && window.speechSynthesis.speaking)
      ) return;

      wakeWordPromptCooldownRef.current = Date.now() + WAKE_WORD_PROMPT_COOLDOWN_MS;
      // Restore the proven interaction cadence: stop passive microphone
      // streaming, acknowledge the wake, then open a fresh local-ASR command
      // window. This prevents a natural pause after the wake phrase from
      // consuming the no-speech timeout.
      bww.pauseAudioCapture();
      setPanelOpen(true);
      wakeWordArmedRef.current = true;
      setWakeWordArmed(true);
      setVoiceTurnStatus("wake-detected");
      ensureConnected();
      const promptLanguage = wakeVoiceLanguageRef.current;
      const prompt =
        promptLanguage === "tr-TR"
          ? "Size nasıl yardımcı olabilirim?"
          : "How can I help you?";
      appendMessageRef.current(makeMessage("avaros", prompt));
      setVoiceTurnStatus("acknowledging");
      void speakAssistantTextRef.current(prompt, promptLanguage).finally(() => {
        if (modeRef.current !== "wake-word" || !wakeWordArmedRef.current) return;
        if (isTtsSpeakingRef.current) return;
        void bww.startUtteranceCapture(wakeVoiceLanguageRef.current).catch(() => {
          wakeWordArmedRef.current = false;
          setWakeWordArmed(false);
          setMicActive(false);
          setMicError("Could not start listening. Please say the wake word again.");
          resumeWakeWordRef.current();
        });
      });
    });
    const unsubTranscript = bww.onTranscript((payload) => {
      wakeWordArmedRef.current = false;
      setWakeWordArmed(false);
      setMicActive(false);
      if (!payload.text) {
        resumeWakeWordRef.current();
        return;
      }
      // The final local-ASR result is already known here. Show exactly what
      // was heard before conversational routing begins.
      void sendTextRef.current(payload.text, wakeVoiceLanguageRef.current, "voice");
    });
    const unsubUtteranceError = bww.onUtteranceError((payload) => {
      wakeWordArmedRef.current = false;
      setWakeWordArmed(false);
      setMicActive(false);
      const isTurkish = wakeVoiceLanguageRef.current === "tr-TR";
      const message =
        payload.code === "silence_timeout" || payload.code === "no_speech"
          ? isTurkish
            ? "Konuşma duyulmadı. Lütfen tekrar \"Hey Jarvis\" deyin."
            : `I didn't hear a request. Please say "${bww.getWakeWordLabel()}" again.`
          : "Local speech recognition failed. Please try again or use push-to-talk/text.";
      setMicError(message);
      appendMessageRef.current(makeMessage("avaros", message));
      setVoiceTurnStatus("rearming");
      resumeWakeWordRef.current();
    });

    // Initialize and start listening after handler is wired.
    void (async () => {
      try {
        await bww.initialize();
        setWakeWordLabel(await bww.refreshWakeWordLabel());
        await bww.startListening();
        setVoiceTurnStatus("armed");
      } catch (error) {
        // Backend unavailable — degrade to push-to-talk.
        bww.dispose();
        backendWakeWordRef.current = null;
        if (
          error instanceof DOMException &&
          (error.name === "NotAllowedError" || error.name === "PermissionDeniedError")
        ) {
          setMicPermission("denied");
          setMicError("Microphone permission blocked. Allow access and retry.");
        } else {
          setMicError("Wake-word service unavailable. Push-to-talk is still available.");
        }
        setMode((prev) => (prev === "wake-word" ? "push-to-talk" : prev));
        modeRef.current = "push-to-talk";
        setVoiceTurnStatus(null);
      }
    })();

    return () => {
      unsubDetected();
      unsubTranscript();
      unsubUtteranceError();
      unsubState();
      bww.dispose();
      backendWakeWordRef.current = null;
    };
  }, [config.sessionToken, config.wakeWordUrl, ensureConnected, mode]);

  useEffect(() => {
    if (mode !== "wake-word") {
      setVoiceTurnStatus(null);
      return;
    }
    if (isTtsSpeaking && voiceTurnStatus === "responding") {
      setVoiceTurnStatus("speaking");
    }
  }, [isTtsSpeaking, mode, voiceTurnStatus]);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;

    const syncVoices = () => {
      const voices = synth.getVoices();
      setTtsVoice(pickPreferredVoice(voices, activeLanguageRef.current));
    };

    syncVoices();
    synth.addEventListener("voiceschanged", syncVoices);
    return () => synth.removeEventListener("voiceschanged", syncVoices);
  }, [config.language]);

  useEffect(() => {
    if (!navigator.permissions) return;
    void navigator.permissions
      .query({ name: "microphone" as PermissionName })
      .then((result) => {
        if (result.state === "granted") {
          setMicPermission("granted");
        } else if (result.state === "denied") {
          setMicPermission("denied");
        } else {
          setMicPermission("prompt");
        }
        result.onchange = () => {
          if (result.state === "granted") setMicPermission("granted");
          else if (result.state === "denied") setMicPermission("denied");
          else setMicPermission("prompt");
        };
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (configError) {
      setConnectionState("error");
      return;
    }

    const manager = new ConnectionManager(
      config.host,
      config.clientName,
      config.accessKey,
      config.accessSecret,
      config.encryptionKey,
      config.language,
      config.sessionToken,
    );
    managerRef.current = manager;
    if (config.autoOpen) {
      manager.connect();
    }
    const offState = manager.onState((nextState) => {
      setConnectionState(nextState);
    });
    const offSpeak = manager.onSpeak((text, language, speechText, inventoryNames) => {
      resolveAssistantMessage(text, language, speechText, inventoryNames);
    });
    const offMouthText = manager.on("enclosure.mouth.text", (message) => {
      // This is a fallback for replies without a speak event. A separate
      // speech rendering must not replace the displayed headline or play twice.
      if (responseResolvedRef.current) return;
      const maybeText =
        (message.data.text as string | undefined) ??
        (message.data.utterance as string | undefined) ??
        "";
      if (!maybeText.trim()) return;
      resolveAssistantMessage(
        maybeText,
        responseLanguage(message, activeLanguageRef.current),
      );
    });
    const offComplete = manager.on("mycroft.skill.handler.complete", (message) => {
      if (responseResolvedRef.current) return;
      clearCompletionTimer();
      const errorText =
        (message.data.exception as string | undefined) ??
        (message.data.error as string | undefined) ??
        "";
      completionTimerRef.current = window.setTimeout(() => {
        if (responseResolvedRef.current) return;
        if (errorText.trim()) {
          const cleaned = errorText
            .replace(/^\[[^\]]+\]\s*/u, "")
            .trim();
          resolveAssistantMessage(`Request failed: ${cleaned || "Unknown error."}`);
          return;
        }
        resolveAssistantMessage(
          "Request completed, but AVAROS did not return spoken output.",
        );
      }, 700);
    });

    return () => {
      offState();
      offSpeak();
      offMouthText();
      offComplete();
      manager.destroy();
      managerRef.current = null;
      clearFallbackTimer();
      clearCompletionTimer();
      stopListening();
      disposeBackendWakeWord();
      stopAssistantSpeech();
      const ttsAudioContext = activeTtsAudioContextRef.current;
      activeTtsAudioContextRef.current = null;
      void ttsAudioContext?.close().catch(() => undefined);
      responseResolvedRef.current = true;
      setWakeWordArmed(false);
    };
  }, [
    appendMessage,
    clearCompletionTimer,
    clearFallbackTimer,
    config.accessKey,
    config.accessSecret,
    config.autoOpen,
    config.clientName,
    config.encryptionKey,
    config.host,
    config.language,
    config.sessionToken,
    configError,
    disposeBackendWakeWord,
    resolveAssistantMessage,
    stopAssistantSpeech,
    stopListening,
  ]);

  useEffect(() => {
    if (config.theme !== "auto") {
      setResolvedTheme(config.theme);
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => {
      setResolvedTheme(media.matches ? "dark" : "light");
    };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [config.theme]);

  useEffect(() => {
    if (!panelOpen) {
      if (mode !== "wake-word") {
        stopListening();
      }
      setWakeWordArmed(false);
      return;
    }

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (processing) {
          handleCancelRequest();
          return;
        }
        setPanelOpen(false);
      }
    };

    const onOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current) return;
      const path = event.composedPath();
      if (path.includes(rootRef.current)) return;
      setPanelOpen(false);
    };

    window.addEventListener("keydown", onEscape);
    document.addEventListener("mousedown", onOutsideClick);
    return () => {
      window.removeEventListener("keydown", onEscape);
      document.removeEventListener("mousedown", onOutsideClick);
    };
  }, [panelOpen, stopListening, mode, processing, handleCancelRequest]);

  useEffect(() => {
    // In wake-word mode, the backend service handles passive listening.
    // Browser STT is only started on-demand after detection.
    if (mode !== "wake-word") {
      setWakeWordArmed(false);
    }
  }, [mode]);

  useEffect(() => {
    onReady({
      open: () => {
        ensureConnected();
        setPanelOpen(true);
      },
      close: () => setPanelOpen(false),
      activateVoice: () => {
        ensureConnected();
        if (!config.disabledModes.includes("wake-word")) {
          setMode("wake-word");
        }
        void requestMicPermission()
          .then((granted) => {
            if (!granted) return;
            void startListening();
          })
          .catch(() => undefined);
      },
      send: (text: string) => {
        setPanelOpen(true);
        void sendText(text);
      },
      isConnected: () => {
        if (!managerRef.current?.isConnected()) return false;
        if (modeRef.current !== "wake-word") return true;
        return backendWakeWordRef.current?.isAvailable() ?? false;
      },
    });
  }, [
    config.disabledModes,
    ensureConnected,
    onReady,
    requestMicPermission,
    sendText,
    startListening,
  ]);

  const visualState: WidgetVisualState = useMemo(() => {
    if (configError) return "disabled";
    if (connectionState === "error") return "error";
    if (
      processing ||
      voiceTurnStatus === "transcribing" ||
      voiceTurnStatus === "processing" ||
      voiceTurnStatus === "responding"
    ) return "processing";
    if (voiceTurnStatus === "speaking") return "speaking";
    if (isTtsSpeaking) return "speaking";
    const isPassiveWakeWordListening =
      mode === "wake-word" && micActive && !wakeWordArmed && !panelOpen;
    if (isPassiveWakeWordListening) return "idle";
    if (micActive || (mode === "wake-word" && panelOpen)) return "listening";
    if (connectionState === "disconnected" && mode !== "wake-word") return "error";
    return "idle";
  }, [
    configError,
    connectionState,
    micActive,
    mode,
    panelOpen,
    processing,
    isTtsSpeaking,
    wakeWordArmed,
    voiceTurnStatus,
  ]);

  const connectionTooltip =
    configError ??
    (connectionState === "connected"
      ? "Connected"
      : connectionState === "connecting"
        ? "Connecting..."
        : connectionState === "error"
          ? "Disconnected"
          : "Disconnected");

  const sendDisabled =
    processing || !inputValue.trim() || connectionState !== "connected" || Boolean(configError);

  const listeningSupported = mode !== "text" && getSpeechRecognitionCtor() !== null;

  const wrapperStyle: CSSProperties = {
    left: config.position.endsWith("left") ? `${config.offsetX}px` : "auto",
    right: config.position.endsWith("right") ? `${config.offsetX}px` : "auto",
    top: config.position.startsWith("top") ? `${config.offsetY}px` : "auto",
    bottom: config.position.startsWith("bottom") ? `${config.offsetY}px` : "auto",
  };

  return (
    <div ref={rootRef} className={`aw-widget aw-widget--${resolvedTheme}`} style={wrapperStyle}>
      {panelOpen ? (
        <div className="aw-widget-panel-anchor">
          <WidgetPanel
            mode={mode}
            disabledModes={config.disabledModes}
            messages={messages}
            connectionState={connectionState}
            listeningSupported={listeningSupported}
            listeningActive={micActive}
            micError={micError}
            inputValue={inputValue}
            processing={processing}
            sendDisabled={sendDisabled}
            visualState={visualState}
            voiceTurnStatus={voiceTurnStatus}
            wakeVoiceLanguage={wakeVoiceLanguage}
            onListenToggle={() => {
              if (micActive) {
                stopListening();
                return;
              }
              void startListening();
            }}
            onCancelRequest={handleCancelRequest}
            onInputChange={setInputValue}
            onSend={() => {
              const toSend = inputValue;
              setInputValue("");
              void sendText(toSend);
            }}
            onClear={() => setMessages([])}
            onStopSpeaking={handleStopResponse}
            brandLogoSrc={config.logoSrc}
            wakeWordLabel={wakeWordLabel}
            avarosUrl={config.avarosUrl}
            onModeChange={(nextMode) => {
              if (config.disabledModes.includes(nextMode)) return;
              stopListening();
              setWakeWordArmed(false);
              setMode(nextMode);
            }}
            onWakeVoiceLanguageChange={selectWakeVoiceLanguage}
          />
        </div>
      ) : null}

      <WidgetButton
        visualState={visualState}
        connectionState={connectionState}
        size={config.size}
        label={config.label}
        open={panelOpen}
        tooltip={connectionTooltip}
        wakeWordEnabled={mode === "wake-word" && micActive && !configError}
        wakeWordLabel={wakeWordLabel}
        onClick={() => {
          ensureConnected();
          setPanelOpen((prev) => !prev);
        }}
      />
    </div>
  );
}
