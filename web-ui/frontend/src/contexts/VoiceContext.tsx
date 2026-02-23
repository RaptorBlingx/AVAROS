/** React context orchestrating STT, TTS, HiveMind, and Wake Word. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useHiveMind } from "./HiveMindContext";
import type { VoiceContextValue, VoiceState } from "./voice-types";
import {
  checkMicrophonePermission,
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  requestMicrophonePermission,
  type PermissionState,
} from "../services/audio-permissions";
import { STTService, type STTResult } from "../services/stt";
import { TTSService } from "../services/tts";
import { VoiceMetricsService } from "../services/voice-metrics";
import { useWakeWord } from "../hooks/useWakeWord";

// Re-export types for consumer convenience
export type { VoiceMode } from "../services/voice-mode";
export type { VoiceState } from "./voice-types";

const VoiceContext = createContext<VoiceContextValue | null>(null);

function normalizeTranscriptForIntent(raw: string): string {
  let text = raw.trim();
  if (!text) return text;

  // Common STT substitutions observed in MVP testing.
  text = text.replace(/°/g, " degrees");
  text = text.replace(/\bwhat if (you|u)\b/gi, "what if we");
  text = text.replace(/\btrain\b/gi, "trend");
  text = text.replace(/\bv\s*s\b/gi, "vs");
  text = text.replace(/\bverse us\b/gi, "versus");
  text = text.replace(/\bverses\b/gi, "versus");
  text = text.replace(
    /\bwhich uses more energy\b.+\b(vs|versus|or)\b.+/gi,
    "which uses more energy",
  );
  text = text.replace(
    /\bwhich is more efficient\b.+\b(vs|versus|or)\b.+/gi,
    "which is more efficient",
  );
  text = text.replace(
    /\bcompare\b.+\b(energy|power)\b.+\b(vs|versus|and|or)\b.+/gi,
    "compare energy",
  );
  text = text.replace(
    /\b(show|display)\s+(scrap|waste)\s+trend\b/gi,
    "$1 $2 rate trend",
  );
  text = text.replace(/\b(scrap|waste)\s+trend\b/gi, "$1 rate trend");
  text = text.replace(
    /\bcheck production on amalie\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production on a money\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production on anomaly\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production anomal(y|ies)\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\b(show|display)\s+production\s+anomal(y|ies)\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bproduction\s+anomal(y|ies)\b/gi,
    "check production anomaly",
  );

  text = text.replace(
    /\bwhat is temperature (increase|increases|increased|raise|raises|raised)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat is temperature (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we decrease temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if temperature (increase|increases|increased|raise|raises|raised)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if we (increase|increases|increased|raise|raises|raised)\s+temperature\s+by\s+([0-9]+(?:\.[0-9]+)?)\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if temperature (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we decrease temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if we (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+temperature\s+by\s+([0-9]+(?:\.[0-9]+)?)\b/gi,
    "what if we decrease temperature by $2 degrees",
  );

  return text.replace(/[.!?]+$/g, "").trim();
}

function isIncompleteIntentText(raw: string): boolean {
  const text = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!text) return true;

  const exactIncomplete = new Set([
    "what if",
    "show",
    "show me",
    "what is",
    "what's",
    "check",
  ]);
  if (exactIncomplete.has(text)) return true;

  const hasAmount =
    /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/.test(
      text,
    );
  if (text.startsWith("what if") && !hasAmount) return true;
  return false;
}

const WAKE_WORD_ARM_MS = 10000;
const WAKE_WORD_PROMPT = "How can I help you?";
const WAKE_WORD_PROMPT_COOLDOWN_MS = 5000;

/** Ignore STT results that are our own TTS prompt (avoids acoustic feedback loop). */
function isOwnPromptEcho(transcript: string): boolean {
  const n = transcript.trim().toLowerCase().replace(/\s+/g, " ");
  const patterns = [
    "how can i help you",
    "hey can i help you",
    "how can i help",
    "hey can i help",
  ];
  return patterns.some(
    (p) => n === p || n.startsWith(p + " ") || n.includes(" " + p),
  );
}

function parseWakeWordUtterance(raw: string): {
  hasWakeWord: boolean;
  command: string;
} {
  const cleaned = raw.trim();
  if (!cleaned) return { hasWakeWord: false, command: "" };

  const match = cleaned.match(/^(hey|ok|okay)\b[\s,.:;-]*(.*)$/i);
  if (!match) return { hasWakeWord: false, command: cleaned };
  const tail = (match[2] ?? "").trim();
  if (!tail) return { hasWakeWord: true, command: "" };

  const parts = tail.split(/\s+/).filter(Boolean);
  const first = (parts[0] ?? "").toLowerCase().replace(/[^a-z]/g, "");
  const looksLikeAlias = /^(avaros|abaros|alvaros|albertos|alberto)$/.test(
    first,
  );
  if (looksLikeAlias) {
    parts.shift();
    return { hasWakeWord: true, command: parts.join(" ").trim() };
  }

  return { hasWakeWord: false, command: cleaned };
}

interface VoiceProviderProps {
  children: ReactNode;
}

export function VoiceProvider({ children }: VoiceProviderProps) {
  const sttRef = useRef<STTService | null>(null);
  const ttsRef = useRef<TTSService | null>(null);
  const metricsRef = useRef(new VoiceMetricsService());
  const voicesChangedHandlerRef = useRef<(() => void) | null>(null);

  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [micPermission, setMicPermission] = useState<PermissionState>("prompt");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [availableVoices, setAvailableVoices] = useState<
    SpeechSynthesisVoice[]
  >([]);
  const [ttsRate, setTTSRateState] = useState(1.0);
  const [ttsVolume, setTTSVolumeState] = useState(1.0);
  const isSpeakingRef = useRef(false);
  const wakeWordPromptCooldownUntilRef = useRef(0);

  const sttSupported = isSpeechRecognitionSupported();
  const ttsSupported = isSpeechSynthesisSupported();
  const interimTranscriptRef = useRef("");
  const finalTranscriptRef = useRef("");
  const wakeWordArmedUntilRef = useRef(0);

  const { sendUtterance, on, isConnected } = useHiveMind();
  const armWakeWordCommandWindow = useCallback(() => {
    wakeWordArmedUntilRef.current = Date.now() + WAKE_WORD_ARM_MS;
  }, []);
  const clearWakeWordCommandWindow = useCallback(() => {
    wakeWordArmedUntilRef.current = 0;
  }, []);
  const isWakeWordCommandWindowOpen = useCallback(() => {
    return Date.now() < wakeWordArmedUntilRef.current;
  }, []);
  const promptWakeWordReady = useCallback(async () => {
    if (!ttsRef.current) return;
    wakeWordPromptCooldownUntilRef.current =
      Date.now() + WAKE_WORD_PROMPT_COOLDOWN_MS;
    await ttsRef.current.speak(WAKE_WORD_PROMPT);
  }, []);
  // ── Wake word detection ────────────────────────────
  const onWakeWordDetected = useCallback(() => {
    if (isSpeakingRef.current) {
      return;
    }
    if (Date.now() < wakeWordPromptCooldownUntilRef.current) {
      return;
    }
    metricsRef.current.reset();
    metricsRef.current.mark("wake_word_detected");
    armWakeWordCommandWindow();
    setInterimTranscript("");
    setFinalTranscript("");
    void promptWakeWordReady()
      .catch(() => undefined)
      .finally(() => {
        void sttRef.current?.start();
      });
  }, [armWakeWordCommandWindow, promptWakeWordReady]);

  const {
    wakeWordState,
    wakeWordFallbackActive,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    voiceMode,
    setVoiceMode,
  } = useWakeWord({ sttRef, onDetected: onWakeWordDetected });

  useEffect(() => {
    interimTranscriptRef.current = interimTranscript;
  }, [interimTranscript]);

  useEffect(() => {
    finalTranscriptRef.current = finalTranscript;
  }, [finalTranscript]);

  // ── Initialize STT / TTS ───────────────────────────
  useEffect(() => {
    if (sttSupported && !sttRef.current) {
      sttRef.current = new STTService({
        continuous: false,
        interimResults: true,
        silenceTimeout: 1200,
      });
    }

    if (ttsSupported && !ttsRef.current) {
      ttsRef.current = new TTSService();
      // Voice UX baseline: keep AVAROS replies in clear English.
      ttsRef.current.setLanguage("en-US");
      const loadVoices = () => {
        const voices = ttsRef.current?.getAvailableVoices() ?? [];
        setAvailableVoices(voices);

        // Prefer high-quality English voices when available (macOS/Safari first).
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
          if (hit) {
            ttsRef.current?.setVoice(hit.voice.name);
            break;
          }
        }
      };
      loadVoices();
      if (typeof window !== "undefined" && window.speechSynthesis) {
        voicesChangedHandlerRef.current = loadVoices;
        window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
      }
    }

    void checkMicrophonePermission().then(setMicPermission);

    return () => {
      if (
        typeof window !== "undefined" &&
        window.speechSynthesis &&
        voicesChangedHandlerRef.current
      ) {
        window.speechSynthesis.removeEventListener(
          "voiceschanged",
          voicesChangedHandlerRef.current,
        );
      }
    };
  }, [sttSupported, ttsSupported]);

  // ── Wire STT events ────────────────────────────────
  useEffect(() => {
    const stt = sttRef.current;
    if (!stt) return;

    const unsubResult = stt.onResult((result: STTResult) => {
      if (result.isFinal) {
        if (isSpeakingRef.current) return;
        metricsRef.current.mark("stt_completed");
        let transcript = result.transcript;
        if (voiceMode === "wake-word") {
          if (isOwnPromptEcho(transcript)) return;
          const parsed = parseWakeWordUtterance(transcript);
          if (parsed.hasWakeWord && parsed.command) {
            clearWakeWordCommandWindow();
            transcript = parsed.command;
          } else if (parsed.hasWakeWord && !parsed.command) {
            armWakeWordCommandWindow();
            setFinalTranscript("");
            setInterimTranscript("");
            setVoiceState("listening");
            promptWakeWordReady();
            return;
          } else if (wakeWordFallbackActive && isWakeWordCommandWindowOpen()) {
            clearWakeWordCommandWindow();
          } else if (!wakeWordFallbackActive && isWakeWordCommandWindowOpen()) {
            clearWakeWordCommandWindow();
          } else {
            setFinalTranscript("");
            setInterimTranscript("");
            setVoiceState("listening");
            return;
          }
        }
        if (!transcript.trim()) return;
        setFinalTranscript(transcript);
        setInterimTranscript("");
      } else {
        setInterimTranscript(result.transcript);
      }
    });

    const unsubState = stt.onStateChange((state) => {
      switch (state) {
        case "listening":
          metricsRef.current.mark("stt_started");
          setVoiceState("listening");
          break;
        case "processing":
          setVoiceState("processing");
          break;
        case "error":
          setVoiceState("error");
          break;
        case "idle":
          setVoiceState((prev) => (prev === "listening" ? "idle" : prev));
          break;
      }
    });

    const unsubError = stt.onError(() => setVoiceState("error"));
    const unsubSilence = stt.onSilenceDetected(() => {
      const interim = interimTranscriptRef.current.trim();
      const final = finalTranscriptRef.current.trim();

      // If engine emitted only interim text, promote it to final so
      // the utterance can still be sent to HiveMind.
      if (!final && interim) {
        setFinalTranscript(interim);
        setInterimTranscript("");
        setVoiceState("processing");
        return;
      }

      // Nothing recognized: do not stay stuck in "processing".
      if (!final) {
        setVoiceState("idle");
        return;
      }

      setVoiceState("processing");
    });

    return () => {
      unsubResult();
      unsubState();
      unsubError();
      unsubSilence();
    };
  }, [
    sttSupported,
    voiceMode,
    wakeWordFallbackActive,
    armWakeWordCommandWindow,
    promptWakeWordReady,
    isWakeWordCommandWindowOpen,
    clearWakeWordCommandWindow,
  ]);

  // ── Wire TTS events ────────────────────────────────
  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  useEffect(() => {
    const tts = ttsRef.current;
    if (!tts) return;

    return tts.onStateChange((state) => {
      if (state === "speaking") {
        setIsSpeaking(true);
        setVoiceState("speaking");
      } else {
        setIsSpeaking(false);
        if (state === "idle") {
          metricsRef.current.mark("tts_completed");
          metricsRef.current.toConsoleLog();
          setVoiceState("idle");
        }
      }
    });
  }, [ttsSupported]);

  // ── Auto-send final transcript to HiveMind ─────────
  useEffect(() => {
    const transcript = finalTranscript.trim();
    if (!transcript || !isConnected) return;
    const normalizedTranscript = normalizeTranscriptForIntent(transcript);
    if (isIncompleteIntentText(normalizedTranscript)) {
      setVoiceState("idle");
      return;
    }

    let cancelled = false;
    metricsRef.current.mark("utterance_sent");

    void sendUtterance(normalizedTranscript)
      .then(() => {
        if (cancelled) return;
        // Stay in "processing" until OVOS responds
        setVoiceState("processing");
      })
      .catch(() => {
        if (cancelled) return;
        setVoiceState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [finalTranscript, isConnected, sendUtterance]);

  // ── Auto-speak HiveMind responses ──────────────────
  useEffect(() => {
    return on("speak", (msg) => {
      metricsRef.current.mark("response_received");
      const text = (msg.data.utterance as string | undefined) ?? "";
      if (text && ttsRef.current) {
        metricsRef.current.mark("tts_started");
        void ttsRef.current.speak(text);
      }
    });
  }, [on]);

  // ── Actions ────────────────────────────────────────

  const startListening = useCallback(async () => {
    if (!sttRef.current) return;
    if (micPermission !== "granted") {
      const result = await requestMicrophonePermission();
      setMicPermission(result);
      if (result !== "granted") return;
    }
    metricsRef.current.reset();
    metricsRef.current.mark("stt_started");
    setInterimTranscript("");
    setFinalTranscript("");
    await sttRef.current.start();
  }, [micPermission]);

  const stopListening = useCallback(() => {
    sttRef.current?.stop();
  }, []);

  const cancelCurrentQuery = useCallback(() => {
    sttRef.current?.stop();
    ttsRef.current?.stop();
    setInterimTranscript("");
    setFinalTranscript("");
    setVoiceState("idle");
  }, []);

  const clearQuery = useCallback(() => {
    setInterimTranscript("");
    setFinalTranscript("");
  }, []);

  const speakText = useCallback(async (text: string) => {
    if (!ttsRef.current) return;
    await ttsRef.current.speak(text);
  }, []);

  const stopSpeaking = useCallback(() => {
    ttsRef.current?.stop();
  }, []);

  const setLanguage = useCallback((lang: string) => {
    sttRef.current?.setLanguage(lang);
    ttsRef.current?.setLanguage(lang);
  }, []);

  const setTTSVoice = useCallback((voiceName: string) => {
    ttsRef.current?.setVoice(voiceName);
  }, []);

  const setTTSRate = useCallback((rate: number) => {
    const normalized = Math.max(0.5, Math.min(2, rate));
    setTTSRateState(normalized);
    ttsRef.current?.setRate(normalized);
  }, []);

  const setTTSVolume = useCallback((volume: number) => {
    const normalized = Math.max(0, Math.min(1, volume));
    setTTSVolumeState(normalized);
    ttsRef.current?.setVolume(normalized);
  }, []);

  const requestMicPermission =
    useCallback(async (): Promise<PermissionState> => {
      const result = await requestMicrophonePermission();
      setMicPermission(result);
      return result;
    }, []);

  // ── Context value ──────────────────────────────────

  const value = useMemo<VoiceContextValue>(
    () => ({
      voiceState,
      voiceMode,
      micPermission,
      sttSupported,
      ttsSupported,
      startListening,
      stopListening,
      cancelCurrentQuery,
      clearQuery,
      interimTranscript,
      finalTranscript,
      speak: speakText,
      stopSpeaking,
      isSpeaking,
      wakeWordState,
      wakeWordEnabled,
      wakeWordSensitivity,
      wakeWordFallbackActive,
      setWakeWordSensitivity,
      isModelLoading,
      setVoiceMode,
      setLanguage,
      availableVoices,
      setTTSVoice,
      ttsRate,
      setTTSRate,
      ttsVolume,
      setTTSVolume,
      requestMicPermission,
    }),
    [
      voiceState,
      voiceMode,
      micPermission,
      sttSupported,
      ttsSupported,
      startListening,
      stopListening,
      cancelCurrentQuery,
      clearQuery,
      interimTranscript,
      finalTranscript,
      speakText,
      stopSpeaking,
      isSpeaking,
      wakeWordState,
      wakeWordEnabled,
      wakeWordSensitivity,
      wakeWordFallbackActive,
      setWakeWordSensitivity,
      isModelLoading,
      setVoiceMode,
      setLanguage,
      availableVoices,
      setTTSVoice,
      ttsRate,
      setTTSRate,
      ttsVolume,
      setTTSVolume,
      requestMicPermission,
    ],
  );

  return (
    <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>
  );
}

/** Access voice interaction state and controls. */
export function useVoice(): VoiceContextValue {
  const context = useContext(VoiceContext);
  if (!context) {
    throw new Error("useVoice must be used within a VoiceProvider");
  }
  return context;
}
