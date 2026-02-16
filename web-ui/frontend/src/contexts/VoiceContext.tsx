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

interface VoiceProviderProps {
  children: ReactNode;
}

export function VoiceProvider({ children }: VoiceProviderProps) {
  const sttRef = useRef<STTService | null>(null);
  const ttsRef = useRef<TTSService | null>(null);
  const metricsRef = useRef(new VoiceMetricsService());
  const voicesChangedHandlerRef = useRef<(() => void) | null>(null);

  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
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

  const { sendUtterance, on, isConnected } = useHiveMind();

  // ── Wake word detection ────────────────────────────
  const onWakeWordDetected = useCallback(() => {
    metricsRef.current.reset();
    metricsRef.current.mark("wake_word_detected");
    setInterimTranscript("");
    setFinalTranscript("");
    void sttRef.current?.start();
  }, []);

  const {
    wakeWordState,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    voiceMode,
    setVoiceMode,
  } = useWakeWord({ sttRef, onDetected: onWakeWordDetected });

  // ── Initialize STT / TTS ───────────────────────────
  useEffect(() => {
    if (sttSupported && !sttRef.current) {
      sttRef.current = new STTService({
        continuous: false,
        interimResults: true,
      });
    }

    if (ttsSupported && !ttsRef.current) {
      ttsRef.current = new TTSService();
      const loadVoices = () => {
        setAvailableVoices(ttsRef.current?.getAvailableVoices() ?? []);
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
        metricsRef.current.mark("stt_completed");
        setFinalTranscript(result.transcript);
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
          setVoiceState((prev) =>
            prev === "listening" ? "idle" : prev,
          );
          break;
      }
    });

    const unsubError = stt.onError(() => setVoiceState("error"));
    const unsubSilence = stt.onSilenceDetected(() => setVoiceState("processing"));

    return () => { unsubResult(); unsubState(); unsubError(); unsubSilence(); };
  }, [sttSupported]);

  // ── Wire TTS events ────────────────────────────────
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
    if (!finalTranscript || !isConnected) return;
    metricsRef.current.mark("utterance_sent");
    void sendUtterance(finalTranscript).then(() =>
      setVoiceState("processing"),
    );
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

  const requestMicPermission = useCallback(
    async (): Promise<PermissionState> => {
      const result = await requestMicrophonePermission();
      setMicPermission(result);
      return result;
    },
    [],
  );

  // ── Context value ──────────────────────────────────

  const value = useMemo<VoiceContextValue>(() => ({
    voiceState, voiceMode, micPermission, sttSupported, ttsSupported,
    startListening, stopListening, interimTranscript, finalTranscript,
    speak: speakText, stopSpeaking, isSpeaking,
    wakeWordState, wakeWordEnabled, wakeWordSensitivity,
    setWakeWordSensitivity, isModelLoading,
    setVoiceMode, setLanguage, availableVoices, setTTSVoice,
    requestMicPermission,
  }), [
    voiceState, voiceMode, micPermission, sttSupported, ttsSupported,
    startListening, stopListening, interimTranscript, finalTranscript,
    speakText, stopSpeaking, isSpeaking,
    wakeWordState, wakeWordEnabled, wakeWordSensitivity,
    setWakeWordSensitivity, isModelLoading,
    setVoiceMode, setLanguage, availableVoices, setTTSVoice,
    requestMicPermission,
  ]);

  return (
    <VoiceContext.Provider value={value}>
      {children}
    </VoiceContext.Provider>
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
