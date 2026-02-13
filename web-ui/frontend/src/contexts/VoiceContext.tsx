/**
 * React context that orchestrates STT, TTS, and HiveMind into a
 * unified voice interaction layer.
 *
 * State machine: idle → listening → processing → speaking → idle
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
 *   const { startListening, voiceState, speak } = useVoice();
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

  // ── Configuration ────────────────────────────────
  /** Switch voice interaction mode */
  setVoiceMode: (mode: VoiceMode) => void;
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

  // ── State ──────────────────────────────────────────
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceMode, setVoiceMode] = useState<VoiceMode>("push-to-talk");
  const [micPermission, setMicPermission] =
    useState<PermissionState>("prompt");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [availableVoices, setAvailableVoices] = useState<
    SpeechSynthesisVoice[]
  >([]);

  const sttSupported = isSpeechRecognitionSupported();
  const ttsSupported = isSpeechSynthesisSupported();

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
        window.speechSynthesis.addEventListener(
          "voiceschanged",
          loadVoices,
        );
      }
    }

    // Check initial mic permission (without triggering dialog)
    void checkMicrophonePermission().then(setMicPermission);

    return () => {
      // Cleanup voices listener
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.removeEventListener(
          "voiceschanged",
          () => {},
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
    if (ttsRef.current) {
      ttsRef.current.setRate(ttsRef.current.getState() === "idle" ? 1.0 : 1.0);
      // Update TTS language by setting the voice config
      // The TTSService will pick the right voice on next speak()
    }
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
    (mode: VoiceMode) => {
      setVoiceMode(mode);
      if (sttRef.current) {
        sttRef.current.setContinuous(mode === "wake-word");
      }
    },
    [],
  );

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
