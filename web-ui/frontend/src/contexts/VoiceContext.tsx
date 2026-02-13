/**
 * React context that orchestrates STT, TTS, HiveMind, and Wake Word
 * detection into a unified voice interaction layer.
 *
 * State machine:
 *   wake_word_listening → (detection) → listening → processing → speaking → wake_word_listening
 *   idle → listening → processing → speaking → idle  (push-to-talk / text)
 *
 * The VoiceProvider must be placed inside HiveMindProvider since
 * it depends on the HiveMind service for message transport.
 *
 * Usage:
 *   <HiveMindProvider>
 *     <VoiceProvider>
 *       ...
 *     </VoiceProvider>
 *   </HiveMindProvider>
 *
 *   const { startListening, voiceState, speak, voiceMode } = useVoice();
 */

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
import {
  checkMicrophonePermission,
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  requestMicrophonePermission,
  type PermissionState,
} from "../services/audio-permissions";
import { STTService, type STTResult } from "../services/stt";
import { TTSService } from "../services/tts";
import {
  WakeWordService,
  type WakeWordState,
} from "../services/wake-word";
import { VoiceModeService } from "../services/voice-mode";

// ── Types ──────────────────────────────────────────────

export type VoiceMode = "text" | "push-to-talk" | "wake-word";

export type VoiceState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

interface VoiceContextValue {
  /** Current voice interaction state */
  voiceState: VoiceState;
  /** Current interaction mode */
  voiceMode: VoiceMode;
  /** Microphone permission state */
  micPermission: PermissionState;
  /** True when the Web Speech API (STT) is available */
  sttSupported: boolean;
  /** True when the speechSynthesis API (TTS) is available */
  ttsSupported: boolean;

  // ── STT ──────────────────────────────────────────
  /** Start microphone listening. Requests permission if needed. */
  startListening: () => Promise<void>;
  /** Stop microphone listening */
  stopListening: () => void;
  /** Partial transcript while user is still speaking */
  interimTranscript: string;
  /** Final transcript from the last utterance */
  finalTranscript: string;

  // ── TTS ──────────────────────────────────────────
  /** Speak text aloud */
  speak: (text: string) => Promise<void>;
  /** Stop current speech */
  stopSpeaking: () => void;
  /** True while TTS is producing audio */
  isSpeaking: boolean;

  // ── Wake word ────────────────────────────────────
  /** Current wake word engine state */
  wakeWordState: WakeWordState;
  /** Whether wake word mode is currently active */
  wakeWordEnabled: boolean;
  /** Wake word detection sensitivity (0–1) */
  wakeWordSensitivity: number;
  /** Adjust wake word sensitivity */
  setWakeWordSensitivity: (value: number) => void;
  /** True while the TF.js model is loading */
  isModelLoading: boolean;

  // ── Configuration ────────────────────────────────
  /** Switch voice interaction mode */
  setVoiceMode: (mode: VoiceMode) => Promise<void>;
  /** Set STT and TTS language */
  setLanguage: (lang: string) => void;
  /** Available TTS voices */
  availableVoices: SpeechSynthesisVoice[];
  /** Select a TTS voice by name */
  setTTSVoice: (voiceName: string) => void;

  // ── Permission ───────────────────────────────────
  /** Trigger browser microphone permission dialog */
  requestMicPermission: () => Promise<PermissionState>;
}

const VoiceContext = createContext<VoiceContextValue | null>(null);

// ── Provider ───────────────────────────────────────────

interface VoiceProviderProps {
  children: ReactNode;
}

export function VoiceProvider({ children }: VoiceProviderProps) {
  // ── Refs for services ──────────────────────────────
  const sttRef = useRef<STTService | null>(null);
  const ttsRef = useRef<TTSService | null>(null);
  const wakeWordRef = useRef<WakeWordService | null>(null);
  const voiceModeRef = useRef<VoiceModeService | null>(null);
  const voicesChangedHandlerRef = useRef<(() => void) | null>(null);

  // ── State ──────────────────────────────────────────
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>("push-to-talk");
  const [micPermission, setMicPermission] =
    useState<PermissionState>("prompt");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [availableVoices, setAvailableVoices] = useState<
    SpeechSynthesisVoice[]
  >([]);
  const [wakeWordState, setWakeWordState] = useState<WakeWordState>("idle");
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(0.75);
  const [isModelLoading, setIsModelLoading] = useState(false);

  const sttSupported = isSpeechRecognitionSupported();
  const ttsSupported = isSpeechSynthesisSupported();
  const wakeWordEnabled = voiceMode === "wake-word";

  // ── HiveMind integration ───────────────────────────
  const { sendUtterance, on, isConnected } = useHiveMind();

  // ── Initialize services ────────────────────────────
  useEffect(() => {
    if (sttSupported && !sttRef.current) {
      sttRef.current = new STTService({
        continuous: false,
        interimResults: true,
      });
    }

    if (ttsSupported && !ttsRef.current) {
      ttsRef.current = new TTSService();
      // Populate available voices (may load asynchronously in Chrome)
      const loadVoices = () => {
        const voices = ttsRef.current?.getAvailableVoices() ?? [];
        setAvailableVoices(voices);
      };
      loadVoices();
      if (typeof window !== "undefined" && window.speechSynthesis) {
        voicesChangedHandlerRef.current = loadVoices;
        window.speechSynthesis.addEventListener(
          "voiceschanged",
          loadVoices,
        );
      }
    }

    // Initialize wake word service (model loaded lazily on mode switch)
    if (!wakeWordRef.current) {
      wakeWordRef.current = new WakeWordService({
        sensitivity: wakeWordSensitivity,
      });
    }

    // Initialize voice mode service
    if (!voiceModeRef.current && sttRef.current && wakeWordRef.current) {
      voiceModeRef.current = new VoiceModeService(
        wakeWordRef.current,
        sttRef.current,
      );
    }

    // Check initial mic permission (without triggering dialog)
    void checkMicrophonePermission().then(setMicPermission);

    return () => {
      // Cleanup voices listener
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
      // Cleanup wake word
      wakeWordRef.current?.dispose();
    };
  }, [sttSupported, ttsSupported]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Wire STT events ────────────────────────────────
  useEffect(() => {
    const stt = sttRef.current;
    if (!stt) return;

    const unsubResult = stt.onResult((result: STTResult) => {
      if (result.isFinal) {
        setFinalTranscript(result.transcript);
        setInterimTranscript("");
      } else {
        setInterimTranscript(result.transcript);
      }
    });

    const unsubState = stt.onStateChange((state) => {
      switch (state) {
        case "listening":
          setVoiceState("listening");
          break;
        case "processing":
          setVoiceState("processing");
          break;
        case "error":
          setVoiceState("error");
          break;
        case "idle":
          // Only go idle if we're not processing or speaking
          setVoiceState((prev) =>
            prev === "listening" ? "idle" : prev,
          );
          break;
      }
    });

    const unsubError = stt.onError(() => {
      setVoiceState("error");
    });

    const unsubSilence = stt.onSilenceDetected(() => {
      // Silence triggers transition to processing
      setVoiceState("processing");
    });

    return () => {
      unsubResult();
      unsubState();
      unsubError();
      unsubSilence();
    };
  }, [sttSupported]);

  // ── Wire TTS events ────────────────────────────────
  useEffect(() => {
    const tts = ttsRef.current;
    if (!tts) return;

    const unsub = tts.onStateChange((state) => {
      if (state === "speaking") {
        setIsSpeaking(true);
        setVoiceState("speaking");
      } else {
        setIsSpeaking(false);
        if (state === "idle") {
          setVoiceState("idle");
        }
      }
    });

    return unsub;
  }, [ttsSupported]);

  // ── Wire wake word events ──────────────────────────
  useEffect(() => {
    const ww = wakeWordRef.current;
    if (!ww) return;

    const unsubState = ww.onStateChange((state) => {
      setWakeWordState(state);
      if (state === "loading") {
        setIsModelLoading(true);
      } else {
        setIsModelLoading(false);
      }
    });

    const unsubDetected = ww.onDetected(() => {
      // Wake word detected — start STT to capture the actual utterance
      if (sttRef.current) {
        setInterimTranscript("");
        setFinalTranscript("");
        void sttRef.current.start();
      }
    });

    return () => {
      unsubState();
      unsubDetected();
    };
  }, [sttSupported]);

  // ── Auto-send final transcript to HiveMind ─────────
  useEffect(() => {
    if (!finalTranscript || !isConnected) return;

    void sendUtterance(finalTranscript).then(() => {
      // Stay in "processing" until OVOS responds
      setVoiceState("processing");
    });
  }, [finalTranscript, isConnected, sendUtterance]);

  // ── Auto-speak HiveMind responses ──────────────────
  useEffect(() => {
    const unsub = on("speak", (msg) => {
      const text =
        (msg.data.utterance as string | undefined) ?? "";
      if (text && ttsRef.current) {
        void ttsRef.current.speak(text);
      }
    });
    return unsub;
  }, [on]);

  // ── Actions ────────────────────────────────────────

  const startListening = useCallback(async () => {
    if (!sttRef.current) return;

    // Request mic permission if needed
    if (micPermission !== "granted") {
      const result = await requestMicrophonePermission();
      setMicPermission(result);
      if (result !== "granted") return;
    }

    setInterimTranscript("");
    setFinalTranscript("");
    await sttRef.current.start();
  }, [micPermission]);

  const stopListening = useCallback(() => {
    sttRef.current?.stop();
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

  const requestMicPermission = useCallback(async (): Promise<PermissionState> => {
    const result = await requestMicrophonePermission();
    setMicPermission(result);
    return result;
  }, []);

  const handleSetVoiceMode = useCallback(
    async (mode: VoiceMode) => {
      if (voiceModeRef.current) {
        await voiceModeRef.current.setMode(
          mode as import("../services/voice-mode").VoiceMode,
        );
      }
      setVoiceModeState(mode);
      if (sttRef.current) {
        sttRef.current.setContinuous(mode === "wake-word");
      }
    },
    [],
  );

  const handleSetWakeWordSensitivity = useCallback((value: number) => {
    setWakeWordSensitivityState(value);
    wakeWordRef.current?.setSensitivity(value);
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
      interimTranscript,
      finalTranscript,
      speak: speakText,
      stopSpeaking,
      isSpeaking,
      wakeWordState,
      wakeWordEnabled,
      wakeWordSensitivity,
      setWakeWordSensitivity: handleSetWakeWordSensitivity,
      isModelLoading,
      setVoiceMode: handleSetVoiceMode,
      setLanguage,
      availableVoices,
      setTTSVoice,
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
      interimTranscript,
      finalTranscript,
      speakText,
      stopSpeaking,
      isSpeaking,
      wakeWordState,
      wakeWordEnabled,
      wakeWordSensitivity,
      handleSetWakeWordSensitivity,
      isModelLoading,
      handleSetVoiceMode,
      setLanguage,
      availableVoices,
      setTTSVoice,
      requestMicPermission,
    ],
  );

  return (
    <VoiceContext.Provider value={value}>
      {children}
    </VoiceContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────

/**
 * Access voice interaction state and controls.
 *
 * Must be used within a VoiceProvider (which itself must be
 * inside a HiveMindProvider).
 */
export function useVoice(): VoiceContextValue {
  const context = useContext(VoiceContext);
  if (!context) {
    throw new Error("useVoice must be used within a VoiceProvider");
  }
  return context;
}
