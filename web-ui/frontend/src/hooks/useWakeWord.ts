/**
 * Custom hook for wake word detection and voice mode management.
 *
 * Manages WakeWordService + VoiceModeService lifecycle, state, and
 * event subscriptions. Extracted from VoiceContext to keep file sizes
 * under 300 lines.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { WakeWordService } from "../services/wake-word";
import type { WakeWordState } from "../services/wake-word-types";
import { VoiceModeService, type VoiceMode } from "../services/voice-mode";
import type { STTService } from "../services/stt";

const VOICE_MODE_STORAGE_KEY = "avaros-voice-mode";

function getInitialVoiceMode(): VoiceMode {
  if (typeof window === "undefined") return "text";
  const raw = window.localStorage.getItem(VOICE_MODE_STORAGE_KEY);
  if (raw === "wake-word" || raw === "push-to-talk" || raw === "text") {
    return raw;
  }
  return "text";
}

// ── Types ──────────────────────────────────────────────

export interface UseWakeWordResult {
  wakeWordState: WakeWordState;
  wakeWordFallbackActive: boolean;
  wakeWordEnabled: boolean;
  wakeWordSensitivity: number;
  setWakeWordSensitivity: (value: number) => void;
  isModelLoading: boolean;
  voiceMode: VoiceMode;
  setVoiceMode: (mode: VoiceMode) => Promise<void>;
}

interface UseWakeWordOptions {
  /** STT service ref — used to toggle continuous mode on mode switch. */
  sttRef: React.RefObject<STTService | null>;
  /** Called when the wake word is detected (typically starts STT). */
  onDetected: () => void;
}

// ── Hook ───────────────────────────────────────────────

/**
 * Manage wake word detection and three-mode voice toggle.
 *
 * Initializes WakeWordService and VoiceModeService, wires events,
 * and provides state + setters for use in VoiceContext.
 */
export function useWakeWord(options: UseWakeWordOptions): UseWakeWordResult {
  const { sttRef, onDetected } = options;

  const wakeWordRef = useRef<WakeWordService | null>(null);
  const voiceModeRef = useRef<VoiceModeService | null>(null);

  const [wakeWordState, setWakeWordState] = useState<WakeWordState>("idle");
  const [wakeWordFallbackActive, setWakeWordFallbackActive] = useState(false);
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(0.75);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>(getInitialVoiceMode);

  const wakeWordEnabled = voiceMode === "wake-word";

  const ensureVoiceModeService = useCallback((): VoiceModeService | null => {
    if (voiceModeRef.current) {
      return voiceModeRef.current;
    }

    if (!sttRef.current || !wakeWordRef.current) {
      return null;
    }

    voiceModeRef.current = new VoiceModeService(
      wakeWordRef.current,
      sttRef.current,
    );

    return voiceModeRef.current;
  }, [sttRef]);

  // Initialize services
  useEffect(() => {
    if (!wakeWordRef.current) {
      wakeWordRef.current = new WakeWordService({
        sensitivity: wakeWordSensitivity,
      });
    }

    ensureVoiceModeService();

    return () => {
      void wakeWordRef.current?.dispose();
    };
  }, [ensureVoiceModeService]);

  // Wire wake word events
  useEffect(() => {
    const ww = wakeWordRef.current;
    if (!ww) return;

    const unsubState = ww.onStateChange((state) => {
      setWakeWordState(state);
      setIsModelLoading(state === "loading");
    });

    const unsubDetected = ww.onDetected(onDetected);

    return () => {
      unsubState();
      unsubDetected();
    };
  }, [onDetected]);

  const setVoiceMode = useCallback(
    async (mode: VoiceMode) => {
      const activateWakeWordFallback = async () => {
        if (!sttRef.current) {
          throw new Error("STT service is not ready");
        }
        // Fallback mode: keep wake-word UX by using continuous STT and
        // filtering utterances by "hey avaros" in VoiceContext.
        sttRef.current.setContinuous(true);
        await sttRef.current.start();
        setWakeWordFallbackActive(true);
        setWakeWordState("listening");
        setIsModelLoading(false);
        setVoiceModeState("wake-word");
        if (typeof window !== "undefined") {
          window.localStorage.setItem(VOICE_MODE_STORAGE_KEY, "wake-word");
        }
      };

      const service = ensureVoiceModeService();
      try {
        if (!service) {
          if (mode === "wake-word") {
            await activateWakeWordFallback();
            return;
          }
          throw new Error("Voice mode service is not ready");
        }

        await service.setMode(mode);
        setWakeWordFallbackActive(false);
        if (mode !== "wake-word") {
          sttRef.current?.stop();
        }
        setVoiceModeState(mode);
        sttRef.current?.setContinuous(mode === "wake-word");
        if (typeof window !== "undefined") {
          window.localStorage.setItem(VOICE_MODE_STORAGE_KEY, mode);
        }
      } catch (error) {
        if (mode === "wake-word") {
          try {
            await activateWakeWordFallback();
            return;
          } catch (fallbackError) {
            console.warn("Wake-word mode failed to start.", error, fallbackError);
          }
        }
        setWakeWordFallbackActive(false);
        sttRef.current?.setContinuous(false);
        throw error;
      }
    },
    [ensureVoiceModeService, sttRef],
  );

  const setWakeWordSensitivity = useCallback((value: number) => {
    setWakeWordSensitivityState(value);
    wakeWordRef.current?.setSensitivity(value);
  }, []);

  return {
    wakeWordState,
    wakeWordFallbackActive,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    voiceMode,
    setVoiceMode,
  };
}
