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
import { normalizeUtteranceForIntent } from "../services/intent-normalizer";
import { STTService, type STTResult } from "../services/stt";
import { TTSService } from "../services/tts";
import { VoiceMetricsService } from "../services/voice-metrics";
import {
  isIncompleteIntentText,
  isLikelyNoiseUtterance,
  isOwnPromptEcho,
} from "../services/voice-guards";
import { useWakeWord } from "../hooks/useWakeWord";

// Re-export types for consumer convenience
export type { VoiceMode } from "../services/voice-mode";
export type { VoiceState } from "./voice-types";

const VoiceContext = createContext<VoiceContextValue | null>(null);

const WAKE_WORD_ARM_MS = 10000;
const WAKE_WORD_PROMPT = "How can I help you?";
const WAKE_WORD_POST_SESSION_COOLDOWN_MS = 2000;
const WAKE_WORD_CAPTURE_TIMEOUT_MS = 10000;
const SPEAK_EVENT_DEDUP_MS = 1200;

type WakeInteractionPhase =
  | "idle"
  | "prompting"
  | "capturing"
  | "awaiting_response"
  | "speaking_response"
  | "cooldown";

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
  const [isWakeWordArmed, setIsWakeWordArmed] = useState(false);
  const [wakeWordDetectedAt, setWakeWordDetectedAt] = useState(0);
  const [availableVoices, setAvailableVoices] = useState<
    SpeechSynthesisVoice[]
  >([]);
  const [ttsRate, setTTSRateState] = useState(1.0);
  const [ttsVolume, setTTSVolumeState] = useState(1.0);
  const isSpeakingRef = useRef(false);
  const lastTtsUtteranceRef = useRef("");
  const pauseDetectionRef = useRef<(() => void) | null>(null);
  const resumeDetectionRef = useRef<(() => void) | null>(null);
  const wakeWordDetectionPausedRef = useRef(false);
  const wakeWordSessionPhaseRef = useRef<WakeInteractionPhase>("idle");
  const wakeWordSessionCooldownUntilRef = useRef(0);
  const wakeWordCaptureTimeoutRef = useRef<number | null>(null);
  const lastBusSpeakRef = useRef<{ text: string; at: number }>({
    text: "",
    at: 0,
  });

  const sttSupported = isSpeechRecognitionSupported();
  const ttsSupported = isSpeechSynthesisSupported();
  const interimTranscriptRef = useRef("");
  const finalTranscriptRef = useRef("");
  const wakeWordArmedUntilRef = useRef(0);

  const { sendUtterance, on, isConnected } = useHiveMind();

  // Keep STT service ready as early as possible so wake-word auto-start
  // does not miss the first page-load window.
  if (sttSupported && !sttRef.current) {
    sttRef.current = new STTService({
      continuous: false,
      interimResults: true,
      silenceTimeout: 1200,
    });
  }

  const armWakeWordCommandWindow = useCallback(() => {
    wakeWordArmedUntilRef.current = Date.now() + WAKE_WORD_ARM_MS;
    setIsWakeWordArmed(true);
  }, []);
  const clearWakeWordCommandWindow = useCallback(() => {
    wakeWordArmedUntilRef.current = 0;
    setIsWakeWordArmed(false);
  }, []);
  const isWakeWordCommandWindowOpen = useCallback(() => {
    return Date.now() < wakeWordArmedUntilRef.current;
  }, []);
  const setWakeWordSessionPhase = useCallback((phase: WakeInteractionPhase) => {
    wakeWordSessionPhaseRef.current = phase;
  }, []);
  const clearWakeWordCaptureTimeout = useCallback(() => {
    if (wakeWordCaptureTimeoutRef.current !== null) {
      window.clearTimeout(wakeWordCaptureTimeoutRef.current);
      wakeWordCaptureTimeoutRef.current = null;
    }
  }, []);
  const resumeWakeWordDetection = useCallback(() => {
    if (!wakeWordDetectionPausedRef.current) return;
    wakeWordDetectionPausedRef.current = false;
    resumeDetectionRef.current?.();
  }, []);
  const finishWakeWordSession = useCallback(
    (cooldownMs = WAKE_WORD_POST_SESSION_COOLDOWN_MS) => {
      clearWakeWordCaptureTimeout();
      clearWakeWordCommandWindow();
      wakeWordSessionCooldownUntilRef.current = Date.now() + cooldownMs;
      setWakeWordSessionPhase("cooldown");
      sttRef.current?.stop();
      setInterimTranscript("");
      setFinalTranscript("");
      setVoiceState("idle");
      window.setTimeout(() => {
        if (wakeWordSessionPhaseRef.current !== "cooldown") return;
        if (Date.now() < wakeWordSessionCooldownUntilRef.current) return;
        setWakeWordSessionPhase("idle");
        resumeWakeWordDetection();
      }, cooldownMs);
    },
    [
      clearWakeWordCaptureTimeout,
      clearWakeWordCommandWindow,
      resumeWakeWordDetection,
      setWakeWordSessionPhase,
    ],
  );
  const startWakeWordCommandCapture = useCallback(async () => {
    if (wakeWordSessionPhaseRef.current !== "prompting") return;
    const stt = sttRef.current;
    if (!stt) {
      finishWakeWordSession();
      return;
    }

    armWakeWordCommandWindow();
    setWakeWordSessionPhase("capturing");
    clearWakeWordCaptureTimeout();
    wakeWordCaptureTimeoutRef.current = window.setTimeout(() => {
      if (wakeWordSessionPhaseRef.current === "capturing") {
        finishWakeWordSession();
      }
    }, WAKE_WORD_CAPTURE_TIMEOUT_MS);

    // Avoid InvalidStateError when recognition is already active.
    if (stt.getState() === "listening") {
      setVoiceState("listening");
      return;
    }

    try {
      await stt.start();
      setVoiceState("listening");
    } catch {
      // Web Speech start can race after stop/speak; retry once shortly.
      window.setTimeout(() => {
        if (wakeWordSessionPhaseRef.current !== "capturing") return;
        void stt.start().catch(() => {
          finishWakeWordSession();
        });
        setVoiceState("listening");
      }, 220);
    }
  }, [
    armWakeWordCommandWindow,
    clearWakeWordCaptureTimeout,
    finishWakeWordSession,
    setWakeWordSessionPhase,
  ]);
  const promptWakeWordReady = useCallback(async () => {
    if (!ttsRef.current) return;
    lastTtsUtteranceRef.current = WAKE_WORD_PROMPT;
    try {
      await ttsRef.current.speak(WAKE_WORD_PROMPT);
    } catch {
      // Some browsers intermittently drop the first utterance; retry once.
      ttsRef.current.stop();
      await new Promise<void>((resolve) => {
        window.setTimeout(() => resolve(), 120);
      });
      await ttsRef.current.speak(WAKE_WORD_PROMPT);
    }
  }, []);
  // ── Wake word detection ────────────────────────────
  const onWakeWordDetected = useCallback(() => {
    if (isSpeakingRef.current) {
      return;
    }
    if (wakeWordSessionPhaseRef.current !== "idle") {
      return;
    }
    if (Date.now() < wakeWordSessionCooldownUntilRef.current) {
      return;
    }
    metricsRef.current.reset();
    metricsRef.current.mark("wake_word_detected");
    setWakeWordSessionPhase("prompting");
    setWakeWordDetectedAt(Date.now());
    setInterimTranscript("");
    setFinalTranscript("");
    sttRef.current?.stop();
    // Pause wake-word detection during the interaction cycle to prevent
    // re-triggers from TTS echo or ambient sound.
    if (!wakeWordDetectionPausedRef.current) {
      pauseDetectionRef.current?.();
      wakeWordDetectionPausedRef.current = true;
    }
    void promptWakeWordReady()
      .catch(() => {
        finishWakeWordSession();
      })
      .finally(() => {
        if (wakeWordSessionPhaseRef.current === "prompting") {
          void startWakeWordCommandCapture();
        }
      });
  }, [
    finishWakeWordSession,
    promptWakeWordReady,
    setWakeWordSessionPhase,
    startWakeWordCommandCapture,
  ]);

  const {
    wakeWordState,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    wakeWordLabel,
    voiceMode,
    setVoiceMode,
    pauseDetection,
    resumeDetection,
  } = useWakeWord({ sttRef, onDetected: onWakeWordDetected });

  // Keep refs in sync so onWakeWordDetected (defined before the hook) can call them.
  useEffect(() => {
    pauseDetectionRef.current = pauseDetection;
    resumeDetectionRef.current = resumeDetection;
  }, [pauseDetection, resumeDetection]);

  useEffect(() => {
    interimTranscriptRef.current = interimTranscript;
  }, [interimTranscript]);

  useEffect(() => {
    finalTranscriptRef.current = finalTranscript;
  }, [finalTranscript]);

  useEffect(() => {
    if (!isWakeWordArmed) return;
    const timer = window.setTimeout(() => {
      clearWakeWordCommandWindow();
    }, WAKE_WORD_ARM_MS);
    return () => window.clearTimeout(timer);
  }, [isWakeWordArmed, clearWakeWordCommandWindow]);

  useEffect(() => {
    if (voiceMode === "wake-word") return;
    clearWakeWordCaptureTimeout();
    clearWakeWordCommandWindow();
    wakeWordSessionCooldownUntilRef.current = 0;
    setWakeWordSessionPhase("idle");
    wakeWordDetectionPausedRef.current = false;
  }, [
    voiceMode,
    clearWakeWordCaptureTimeout,
    clearWakeWordCommandWindow,
    setWakeWordSessionPhase,
  ]);

  useEffect(() => {
    return () => {
      clearWakeWordCaptureTimeout();
    };
  }, [clearWakeWordCaptureTimeout]);

  // ── Initialize STT / TTS ───────────────────────────
  useEffect(() => {
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
          if (isOwnPromptEcho(transcript, lastTtsUtteranceRef.current)) return;
          if (wakeWordSessionPhaseRef.current !== "capturing") {
            setFinalTranscript("");
            setInterimTranscript("");
            setVoiceState("idle");
            return;
          }
          // In wake-word mode, STT is only active during the command window
          // (after the backend openWakeWord detected the wake phrase).
          // Accept the transcript as a command — no text-based wake word
          // parsing needed (the backend already validated detection).
          if (isWakeWordCommandWindowOpen()) {
            clearWakeWordCommandWindow();
            clearWakeWordCaptureTimeout();
            setWakeWordSessionPhase("awaiting_response");
          } else {
            // STT fired outside the command window — discard.
            finishWakeWordSession();
            return;
          }
        }
        if (!transcript.trim() || isLikelyNoiseUtterance(transcript)) {
          if (voiceMode === "wake-word") {
            finishWakeWordSession();
            return;
          }
          setFinalTranscript("");
          setInterimTranscript("");
          setVoiceState("idle");
          return;
        }
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

      // Safety guard: in wake-word mode, ignore any STT tail activity
      // unless we're inside the explicit post-wake command window.
      if (
        voiceMode === "wake-word" &&
        (
          wakeWordSessionPhaseRef.current !== "capturing"
          || !isWakeWordCommandWindowOpen()
        )
      ) {
        setFinalTranscript("");
        setInterimTranscript("");
        setVoiceState("idle");
        return;
      }

      // If engine emitted only interim text, promote it to final so
      // the utterance can still be sent to HiveMind.
      if (!final && interim) {
        if (voiceMode === "wake-word") {
          clearWakeWordCommandWindow();
          clearWakeWordCaptureTimeout();
          setWakeWordSessionPhase("awaiting_response");
        }
        setFinalTranscript(interim);
        setInterimTranscript("");
        setVoiceState("processing");
        return;
      }

      // Nothing recognized: do not stay stuck in "processing".
      if (!final) {
        if (voiceMode === "wake-word") {
          finishWakeWordSession();
          return;
        }
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
    isWakeWordCommandWindowOpen,
    clearWakeWordCommandWindow,
    clearWakeWordCaptureTimeout,
    finishWakeWordSession,
    setWakeWordSessionPhase,
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
          if (wakeWordSessionPhaseRef.current === "speaking_response") {
            finishWakeWordSession();
          }
        }
      }
    });
  }, [
    finishWakeWordSession,
  ]);

  // ── Auto-send final transcript to HiveMind ─────────
  useEffect(() => {
    const transcript = finalTranscript.trim();
    if (!transcript) return;
    if (!isConnected) {
      if (voiceMode === "wake-word") {
        finishWakeWordSession();
      }
      return;
    }
    const normalizedTranscript = normalizeUtteranceForIntent(transcript);
    if (isIncompleteIntentText(normalizedTranscript)) {
      if (voiceMode === "wake-word") {
        finishWakeWordSession();
        return;
      }
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
        if (voiceMode === "wake-word") {
          finishWakeWordSession();
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    finalTranscript,
    finishWakeWordSession,
    isConnected,
    sendUtterance,
    voiceMode,
  ]);

  // ── Auto-speak HiveMind responses ──────────────────
  useEffect(() => {
    return on("speak", (msg) => {
      metricsRef.current.mark("response_received");
      const text = (msg.data.utterance as string | undefined) ?? "";
      const normalized = text.trim();
      if (normalized && ttsRef.current) {
        if (
          voiceMode === "wake-word" &&
          wakeWordSessionPhaseRef.current === "awaiting_response"
        ) {
          setWakeWordSessionPhase("speaking_response");
        }
        const now = Date.now();
        if (
          lastBusSpeakRef.current.text === normalized &&
          now - lastBusSpeakRef.current.at < SPEAK_EVENT_DEDUP_MS
        ) {
          return;
        }
        lastBusSpeakRef.current = { text: normalized, at: now };
        lastTtsUtteranceRef.current = normalized;
        metricsRef.current.mark("tts_started");
        void ttsRef.current.speak(normalized);
      }
    });
  }, [on, setWakeWordSessionPhase, voiceMode]);

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
    if (voiceMode === "wake-word" && wakeWordSessionPhaseRef.current !== "idle") {
      finishWakeWordSession(0);
    }
    sttRef.current?.stop();
    ttsRef.current?.stop();
    clearWakeWordCaptureTimeout();
    clearWakeWordCommandWindow();
    setInterimTranscript("");
    setFinalTranscript("");
    setVoiceState("idle");
  }, [
    clearWakeWordCaptureTimeout,
    clearWakeWordCommandWindow,
    finishWakeWordSession,
    voiceMode,
  ]);

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
      isWakeWordArmed,
      wakeWordDetectedAt,
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
      setWakeWordSensitivity,
      isModelLoading,
      wakeWordLabel,
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
      isWakeWordArmed,
      wakeWordDetectedAt,
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
      setWakeWordSensitivity,
      isModelLoading,
      wakeWordLabel,
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
