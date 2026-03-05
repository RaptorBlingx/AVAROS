/**
 * Custom hook for wake word detection and voice mode management.
 *
 * Manages WakeWordService + BackendWakeWordService + VoiceModeService
 * lifecycle, state, and event subscriptions. Extracted from VoiceContext
 * to keep file sizes under 300 lines.
 *
 * Priority: BackendWakeWordService (openWakeWord via WebSocket) is tried
 * first.  If unavailable, the hook degrades to push-to-talk mode.
 * The TF.js WakeWordService is kept for backward compat (P6-E08 removes).
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { WakeWordService } from "../services/wake-word";
import { BackendWakeWordService } from "../services/wake-word-backend";
import type {
  BackendWakeWordState,
  DetectionPayload,
} from "../services/wake-word-backend";
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
  /** True when the backend openWakeWord service is being used. */
  isBackendWakeWord: boolean;
}

interface UseWakeWordOptions {
  /** STT service ref — used to toggle continuous mode on mode switch. */
  sttRef: React.RefObject<STTService | null>;
  /** Called when wake word is detected; payload is available for backend path. */
  onDetected: (payload?: DetectionPayload) => void;
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
  const backendWakeWordRef = useRef<BackendWakeWordService | null>(null);
  const voiceModeRef = useRef<VoiceModeService | null>(null);

  const [wakeWordState, setWakeWordState] = useState<WakeWordState>("idle");
  const [wakeWordFallbackActive, setWakeWordFallbackActive] = useState(false);
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(0.75);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>(getInitialVoiceMode);
  const [isBackendWakeWord, setIsBackendWakeWord] = useState(false);

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
      backendWakeWordRef.current,
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

    if (!backendWakeWordRef.current) {
      backendWakeWordRef.current = new BackendWakeWordService();
    }

    ensureVoiceModeService();

    return () => {
      void wakeWordRef.current?.dispose();
      backendWakeWordRef.current?.dispose();
    };
  }, [ensureVoiceModeService]);

  // Wire wake word events (TF.js)
  useEffect(() => {
    const ww = wakeWordRef.current;
    if (!ww) return;

    const unsubState = ww.onStateChange((state) => {
      if (!isBackendWakeWord) {
        setWakeWordState(state);
        setIsModelLoading(state === "loading");
      }
    });

    const unsubDetected = ww.onDetected(() => {
      if (!isBackendWakeWord) {
        onDetected();
      }
    });

    return () => {
      unsubState();
      unsubDetected();
    };
  }, [onDetected, isBackendWakeWord]);

  // Wire backend wake word events
  useEffect(() => {
    const bww = backendWakeWordRef.current;
    if (!bww) return;

    const unsubState = bww.onStateChange((state: BackendWakeWordState) => {
      // Map backend states to WakeWordState where possible
      const stateMap: Record<BackendWakeWordState, WakeWordState> = {
        idle: "idle",
        connecting: "loading",
        listening: "listening",
        detected: "detected",
        error: "error",
        unsupported: "unsupported",
      };
      setWakeWordState(stateMap[state]);
      setIsModelLoading(state === "connecting");
      setIsBackendWakeWord(
        state === "listening" || state === "detected",
      );
    });

    const unsubDetected = bww.onDetected((payload) => onDetected(payload));

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
        const effectiveMode = service.getMode();
        setWakeWordFallbackActive(false);
        setIsBackendWakeWord(service.isUsingBackend());
        if (effectiveMode !== "wake-word") {
          sttRef.current?.stop();
        }
        setVoiceModeState(effectiveMode);
        sttRef.current?.setContinuous(effectiveMode === "wake-word");
        if (typeof window !== "undefined") {
          window.localStorage.setItem(VOICE_MODE_STORAGE_KEY, effectiveMode);
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
    isBackendWakeWord,
  };
}
