/**
 * Custom hook for wake word detection and voice mode management.
 *
 * Manages BackendWakeWordService + VoiceModeService lifecycle, state,
 * and event subscriptions. Extracted from VoiceContext to keep file
 * sizes under 300 lines.
 *
 * Priority: BackendWakeWordService (openWakeWord via WebSocket) is the
 * sole wake word engine.  If unavailable, the hook degrades to
 * push-to-talk mode (no privacy-leaking continuous STT fallback).
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { BackendWakeWordService } from "../services/wake-word-backend";
import type {
  BackendWakeWordState,
  DetectionPayload,
  WakeWordState,
} from "../services/wake-word-backend";
import { VoiceModeService, type VoiceMode } from "../services/voice-mode";
import type { STTService } from "../services/stt";

const VOICE_MODE_STORAGE_KEY = "avaros-voice-mode";
const WAKE_WORD_URL_STORAGE_KEY = "avaros_wake_word_url";

function getInitialVoiceMode(): VoiceMode {
  if (typeof window === "undefined") return "text";
  const raw = window.localStorage.getItem(VOICE_MODE_STORAGE_KEY);
  if (raw === "wake-word" || raw === "push-to-talk" || raw === "text") {
    return raw;
  }
  return "text";
}

function getConfiguredWakeWordUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const raw = window.localStorage.getItem(WAKE_WORD_URL_STORAGE_KEY);
  const value = raw?.trim();
  return value ? value : undefined;
}

// ── Types ──────────────────────────────────────────────

export interface UseWakeWordResult {
  wakeWordState: WakeWordState;
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
 * Initializes BackendWakeWordService and VoiceModeService, wires events,
 * and provides state + setters for use in VoiceContext.
 */
export function useWakeWord(options: UseWakeWordOptions): UseWakeWordResult {
  const { sttRef, onDetected } = options;

  const backendWakeWordRef = useRef<BackendWakeWordService | null>(null);
  const voiceModeRef = useRef<VoiceModeService | null>(null);

  const [wakeWordState, setWakeWordState] = useState<WakeWordState>("idle");
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(0.75);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>(getInitialVoiceMode);
  const [isBackendWakeWord, setIsBackendWakeWord] = useState(false);

  const wakeWordEnabled = voiceMode === "wake-word";

  const ensureVoiceModeService = useCallback((): VoiceModeService | null => {
    if (voiceModeRef.current) {
      return voiceModeRef.current;
    }

    if (!sttRef.current || !backendWakeWordRef.current) {
      return null;
    }

    voiceModeRef.current = new VoiceModeService(
      backendWakeWordRef.current,
      sttRef.current,
    );

    return voiceModeRef.current;
  }, [sttRef]);

  // Initialize services
  useEffect(() => {
    if (!backendWakeWordRef.current) {
      const configuredUrl = getConfiguredWakeWordUrl();
      backendWakeWordRef.current = configuredUrl
        ? new BackendWakeWordService({ wsUrl: configuredUrl })
        : new BackendWakeWordService();
    }

    ensureVoiceModeService();

    return () => {
      backendWakeWordRef.current?.dispose();
    };
  }, [ensureVoiceModeService]);

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
      const service = ensureVoiceModeService();
      if (!service) {
        throw new Error("Voice mode service is not ready");
      }

      await service.setMode(mode);
      const effectiveMode = service.getMode();
      setIsBackendWakeWord(service.isUsingBackend());
      if (effectiveMode !== "wake-word") {
        sttRef.current?.stop();
      }
      setVoiceModeState(effectiveMode);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(VOICE_MODE_STORAGE_KEY, effectiveMode);
      }
    },
    [ensureVoiceModeService, sttRef],
  );

  const setWakeWordSensitivity = useCallback((value: number) => {
    setWakeWordSensitivityState(value);
    backendWakeWordRef.current?.setSensitivity(value);
  }, []);

  return {
    wakeWordState,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    voiceMode,
    setVoiceMode,
    isBackendWakeWord,
  };
}
