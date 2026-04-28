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
const WAKE_WORD_POST_SESSION_COOLDOWN_MS = 2000;
const WAKE_WORD_CAPTURE_TIMEOUT_MS = 10000;
const WAKE_WORD_CAPTURE_START_RETRY_MS = 220;
const WAKE_WORD_CAPTURE_MAX_START_RETRIES = 2;
const SPEAK_EVENT_DEDUP_MS = 1200;
const VOICE_DEBUG_BUILD_TAG = "voice-debug-2026-04-28-r5";
const WAKE_WORD_POST_RESUME_DETECTION_SUPPRESSION_MS = 1500;
/** Safety net: force-finish any wake-word session stuck longer than this. */
const WAKE_WORD_SESSION_SAFETY_TIMEOUT_MS = 30000;
/** If no speak event arrives within this time after entering awaiting_response, finish the session. */
const WAKE_WORD_RESPONSE_TIMEOUT_MS = 10000;
const WAKE_WORD_TTS_WATCHDOG_MIN_MS = 8000;
const WAKE_WORD_TTS_WATCHDOG_MAX_MS = 30000;
const WAKE_WORD_TTS_WATCHDOG_MS_PER_CHAR = 90;

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
  const wakeWordResumeAtRef = useRef(0);
  const wakeWordSuppressDetectionsUntilRef = useRef(0);
  const wakeWordCaptureTimeoutRef = useRef<number | null>(null);
  const wakeWordCaptureStartRetryRef = useRef(0);
  const wakeWordCaptureStartInFlightRef = useRef(false);
  const wakeWordSessionSafetyTimerRef = useRef<number | null>(null);
  const wakeWordResponseTimerRef = useRef<number | null>(null);
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

  useEffect(() => {
    console.info(`[AVAROS-DEBUG] VoiceContext build: ${VOICE_DEBUG_BUILD_TAG}`);
  }, []);

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
    const prev = wakeWordSessionPhaseRef.current;
    wakeWordSessionPhaseRef.current = phase;
    console.log(`[AVAROS-DEBUG] phase: ${prev} → ${phase}`);
  }, []);
  const clearWakeWordCaptureTimeout = useCallback(() => {
    if (wakeWordCaptureTimeoutRef.current !== null) {
      window.clearTimeout(wakeWordCaptureTimeoutRef.current);
      wakeWordCaptureTimeoutRef.current = null;
    }
  }, []);
  const resumeWakeWordDetection = useCallback(() => {
    const now = Date.now();
    wakeWordResumeAtRef.current = now;
    wakeWordSuppressDetectionsUntilRef.current =
      now + WAKE_WORD_POST_RESUME_DETECTION_SUPPRESSION_MS;
    console.log(
      `[AVAROS-DEBUG] resumeWakeWordDetection called, paused=${wakeWordDetectionPausedRef.current}, hasResumeFn=${!!resumeDetectionRef.current}, suppressMs=${WAKE_WORD_POST_RESUME_DETECTION_SUPPRESSION_MS}`,
    );
    if (!wakeWordDetectionPausedRef.current) return;
    wakeWordDetectionPausedRef.current = false;
    resumeDetectionRef.current?.();
    console.log(`[AVAROS-DEBUG] resumeDetection invoked`);
  }, []);
  const clearWakeWordSessionSafetyTimer = useCallback(() => {
    if (wakeWordSessionSafetyTimerRef.current !== null) {
      window.clearTimeout(wakeWordSessionSafetyTimerRef.current);
      wakeWordSessionSafetyTimerRef.current = null;
    }
  }, []);
  const clearWakeWordResponseTimer = useCallback(() => {
    if (wakeWordResponseTimerRef.current !== null) {
      window.clearTimeout(wakeWordResponseTimerRef.current);
      wakeWordResponseTimerRef.current = null;
    }
  }, []);
  const finishWakeWordSession = useCallback(
    (cooldownMs = WAKE_WORD_POST_SESSION_COOLDOWN_MS) => {
      console.log(`[AVAROS-DEBUG] finishWakeWordSession called, cooldown=${cooldownMs}ms, currentPhase=${wakeWordSessionPhaseRef.current}`);
      clearWakeWordCaptureTimeout();
      clearWakeWordCommandWindow();
      clearWakeWordSessionSafetyTimer();
      clearWakeWordResponseTimer();
      wakeWordCaptureStartRetryRef.current = 0;
      wakeWordCaptureStartInFlightRef.current = false;
      wakeWordSessionCooldownUntilRef.current = Date.now() + cooldownMs;
      setWakeWordSessionPhase("cooldown");
      sttRef.current?.stop();
      setInterimTranscript("");
      setFinalTranscript("");
      setVoiceState("idle");
      window.setTimeout(() => {
        console.log(`[AVAROS-DEBUG] cooldown timer fired, phase=${wakeWordSessionPhaseRef.current}, pastCooldown=${Date.now() >= wakeWordSessionCooldownUntilRef.current}`);
        if (wakeWordSessionPhaseRef.current !== "cooldown") return;
        if (Date.now() < wakeWordSessionCooldownUntilRef.current) return;
        setWakeWordSessionPhase("idle");
        resumeWakeWordDetection();
      }, cooldownMs);
    },
    [
      clearWakeWordCaptureTimeout,
      clearWakeWordCommandWindow,
      clearWakeWordResponseTimer,
      clearWakeWordSessionSafetyTimer,
      resumeWakeWordDetection,
      setWakeWordSessionPhase,
    ],
  );

  const startWakeWordSessionSafetyTimer = useCallback(() => {
    clearWakeWordSessionSafetyTimer();
    wakeWordSessionSafetyTimerRef.current = window.setTimeout(() => {
      const phase = wakeWordSessionPhaseRef.current;
      if (phase !== "idle" && phase !== "cooldown") {
        console.warn(
          "[AVAROS] Wake-word session safety timeout — phase was stuck at:",
          phase,
        );
        finishWakeWordSession();
      }
    }, WAKE_WORD_SESSION_SAFETY_TIMEOUT_MS);
  }, [clearWakeWordSessionSafetyTimer, finishWakeWordSession]);

  const startWakeWordResponseTimer = useCallback(() => {
    clearWakeWordResponseTimer();
    wakeWordResponseTimerRef.current = window.setTimeout(() => {
      if (wakeWordSessionPhaseRef.current === "awaiting_response") {
        console.warn(
          "[AVAROS-DEBUG] No response received within timeout — finishing session",
        );
        finishWakeWordSession();
      }
    }, WAKE_WORD_RESPONSE_TIMEOUT_MS);
  }, [clearWakeWordResponseTimer, finishWakeWordSession]);

  const startWakeWordTtsWatchdog = useCallback((text: string) => {
    clearWakeWordResponseTimer();
    const timeoutMs = Math.min(
      WAKE_WORD_TTS_WATCHDOG_MAX_MS,
      Math.max(
        WAKE_WORD_TTS_WATCHDOG_MIN_MS,
        text.length * WAKE_WORD_TTS_WATCHDOG_MS_PER_CHAR,
      ),
    );
    wakeWordResponseTimerRef.current = window.setTimeout(() => {
      if (wakeWordSessionPhaseRef.current === "speaking_response") {
        console.warn(
          "[AVAROS-DEBUG] TTS watchdog fired — finishing wake-word session",
        );
        finishWakeWordSession();
      }
    }, timeoutMs);
  }, [clearWakeWordResponseTimer, finishWakeWordSession]);

  const startWakeWordCommandCapture = useCallback(async () => {
    const phase = wakeWordSessionPhaseRef.current;
    if (phase !== "prompting" && phase !== "capturing") return;
    const stt = sttRef.current;
    if (!stt) {
      finishWakeWordSession();
      return;
    }

    if (phase === "prompting") {
      armWakeWordCommandWindow();
      setWakeWordSessionPhase("capturing");
      clearWakeWordCaptureTimeout();
      wakeWordCaptureTimeoutRef.current = window.setTimeout(() => {
        if (wakeWordSessionPhaseRef.current === "capturing") {
          finishWakeWordSession();
        }
      }, WAKE_WORD_CAPTURE_TIMEOUT_MS);
      wakeWordCaptureStartRetryRef.current = 0;
    }

    if (!isWakeWordCommandWindowOpen()) {
      finishWakeWordSession();
      return;
    }

    // Avoid InvalidStateError when recognition is already active.
    if (stt.getState() === "listening") {
      wakeWordCaptureStartRetryRef.current = 0;
      setVoiceState("listening");
      return;
    }

    if (wakeWordCaptureStartInFlightRef.current) {
      return;
    }
    wakeWordCaptureStartInFlightRef.current = true;

    try {
      await stt.start();
      wakeWordCaptureStartRetryRef.current = 0;
      setVoiceState("listening");
    } catch {
      // Web Speech start can race after stop; retry shortly before giving up.
      wakeWordCaptureStartRetryRef.current += 1;
      if (wakeWordCaptureStartRetryRef.current > WAKE_WORD_CAPTURE_MAX_START_RETRIES) {
        finishWakeWordSession();
        return;
      }
      window.setTimeout(() => {
        if (wakeWordSessionPhaseRef.current !== "capturing") return;
        void startWakeWordCommandCapture();
      }, WAKE_WORD_CAPTURE_START_RETRY_MS);
    } finally {
      wakeWordCaptureStartInFlightRef.current = false;
    }
  }, [
    armWakeWordCommandWindow,
    clearWakeWordCaptureTimeout,
    finishWakeWordSession,
    isWakeWordCommandWindowOpen,
    setWakeWordSessionPhase,
  ]);

  // ── Wake word detection ────────────────────────────
  const onWakeWordDetected = useCallback((payload?: {
    model: string;
    score: number;
  }) => {
    const now = Date.now();
    const sinceResume = wakeWordResumeAtRef.current
      ? now - wakeWordResumeAtRef.current
      : null;
    console.log(
      `[AVAROS-DEBUG] onWakeWordDetected: speaking=${isSpeakingRef.current}, phase=${wakeWordSessionPhaseRef.current}, inCooldown=${now < wakeWordSessionCooldownUntilRef.current}, sinceResumeMs=${sinceResume ?? "n/a"}, score=${payload?.score?.toFixed?.(4) ?? "n/a"}, model=${payload?.model ?? "n/a"}`,
    );
    if (now < wakeWordSuppressDetectionsUntilRef.current) {
      console.log(
        `[AVAROS-DEBUG] onWakeWordDetected REJECTED: within post-resume suppression window (remainingMs=${wakeWordSuppressDetectionsUntilRef.current - now})`,
      );
      return;
    }
    if (isSpeakingRef.current) {
      console.log(`[AVAROS-DEBUG] onWakeWordDetected REJECTED: still speaking`);
      return;
    }
    if (wakeWordSessionPhaseRef.current !== "idle") {
      console.log(`[AVAROS-DEBUG] onWakeWordDetected REJECTED: phase not idle`);
      return;
    }
    if (now < wakeWordSessionCooldownUntilRef.current) {
      console.log(`[AVAROS-DEBUG] onWakeWordDetected REJECTED: in cooldown`);
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
    console.log(
      `[AVAROS-DEBUG] onWakeWordDetected ACCEPTED: starting capture cycle`,
    );
    startWakeWordSessionSafetyTimer();
    void startWakeWordCommandCapture();
  }, [
    setWakeWordSessionPhase,
    startWakeWordCommandCapture,
    startWakeWordSessionSafetyTimer,
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
    clearWakeWordSessionSafetyTimer();
    clearWakeWordResponseTimer();
    wakeWordSessionCooldownUntilRef.current = 0;
    wakeWordResumeAtRef.current = 0;
    wakeWordSuppressDetectionsUntilRef.current = 0;
    setWakeWordSessionPhase("idle");
    wakeWordDetectionPausedRef.current = false;
  }, [
    voiceMode,
    clearWakeWordCaptureTimeout,
    clearWakeWordCommandWindow,
    clearWakeWordResponseTimer,
    clearWakeWordSessionSafetyTimer,
    setWakeWordSessionPhase,
  ]);

  useEffect(() => {
    return () => {
      clearWakeWordCaptureTimeout();
      clearWakeWordSessionSafetyTimer();
      clearWakeWordResponseTimer();
    };
  }, [clearWakeWordCaptureTimeout, clearWakeWordResponseTimer, clearWakeWordSessionSafetyTimer]);

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
        console.log(`[AVAROS-DEBUG] STT final: "${transcript.slice(0, 60)}", confidence=${result.confidence.toFixed(3)}, phase=${wakeWordSessionPhaseRef.current}`);
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
            startWakeWordResponseTimer();
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
        console.log(
          `[AVAROS-DEBUG] STT accepted final transcript for send: "${transcript.slice(0, 80)}"`,
        );
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
          console.log(`[AVAROS-DEBUG] STT went idle, phase=${wakeWordSessionPhaseRef.current}, commandWindowOpen=${voiceMode === "wake-word" ? isWakeWordCommandWindowOpen() : 'n/a'}`);
          if (
            voiceMode === "wake-word" &&
            wakeWordSessionPhaseRef.current === "capturing" &&
            isWakeWordCommandWindowOpen()
          ) {
            console.log(`[AVAROS-DEBUG] STT idle → re-starting capture`);
            void startWakeWordCommandCapture();
            return;
          }
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
          // In wake-word mode we require a true final transcript to avoid
          // accidental commands from ambient audio.
          console.warn(
            `[AVAROS-DEBUG] Wake-word silence with interim-only transcript dropped: "${interim.slice(0, 80)}"`,
          );
          finishWakeWordSession();
          return;
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
    startWakeWordCommandCapture,
    startWakeWordResponseTimer,
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
      console.log(`[AVAROS-DEBUG] TTS state: ${state}, sessionPhase=${wakeWordSessionPhaseRef.current}`);
      if (state === "speaking") {
        setIsSpeaking(true);
        setVoiceState("speaking");
      } else {
        setIsSpeaking(false);
        if (state === "idle" || state === "error") {
          if (state === "idle") {
            metricsRef.current.mark("tts_completed");
            metricsRef.current.toConsoleLog();
          }
          setVoiceState("idle");
          const sessionPhase = wakeWordSessionPhaseRef.current;
          if (
            sessionPhase !== "idle" &&
            sessionPhase !== "cooldown"
          ) {
            console.log(`[AVAROS-DEBUG] TTS ${state} + phase '${sessionPhase}' → calling finishWakeWordSession`);
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
    console.log(
      `[AVAROS-DEBUG] sendUtterance: "${normalizedTranscript.slice(0, 80)}", voiceMode=${voiceMode}, phase=${wakeWordSessionPhaseRef.current}`,
    );

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
      console.log(`[AVAROS-DEBUG] speak event: "${normalized.slice(0, 60)}…", phase=${wakeWordSessionPhaseRef.current}, voiceMode=${voiceMode}`);
      if (normalized && ttsRef.current) {
        const now = Date.now();
        if (
          lastBusSpeakRef.current.text === normalized &&
          now - lastBusSpeakRef.current.at < SPEAK_EVENT_DEDUP_MS
        ) {
          console.log(`[AVAROS-DEBUG] speak event DEDUPED (same text within ${SPEAK_EVENT_DEDUP_MS}ms)`);
          return;
        }
        // Transition phase AFTER dedup — otherwise a deduped event sets
        // phase to "speaking_response" without starting TTS, and the
        // session never finishes.
        if (voiceMode === "wake-word") {
          const phase = wakeWordSessionPhaseRef.current;
          if (
            phase === "awaiting_response" ||
            phase === "capturing" ||
            phase === "prompting"
          ) {
            setWakeWordSessionPhase("speaking_response");
            startWakeWordTtsWatchdog(normalized);
          } else {
            console.warn(`[AVAROS-DEBUG] speak event: phase '${phase}' not transitioned to speaking_response`);
          }
        }
        lastBusSpeakRef.current = { text: normalized, at: now };
        lastTtsUtteranceRef.current = normalized;
        metricsRef.current.mark("tts_started");
        void ttsRef.current.speak(normalized).catch(() => undefined);
      }
    });
  }, [on, setWakeWordSessionPhase, startWakeWordTtsWatchdog, voiceMode]);

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
