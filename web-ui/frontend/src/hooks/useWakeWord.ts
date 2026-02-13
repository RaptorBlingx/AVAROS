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

// ── Types ──────────────────────────────────────────────

export interface UseWakeWordResult {
  wakeWordState: WakeWordState;
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
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(0.75);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [voiceMode, setVoiceModeState] = useState<VoiceMode>("text");

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
      const service = ensureVoiceModeService();
      if (service) {
        await service.setMode(mode);
      }
      setVoiceModeState(mode);
      sttRef.current?.setContinuous(mode === "wake-word");
    },
    [ensureVoiceModeService, sttRef],
  );

  const setWakeWordSensitivity = useCallback((value: number) => {
    setWakeWordSensitivityState(value);
    wakeWordRef.current?.setSensitivity(value);
  }, []);

  return {
    wakeWordState,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    voiceMode,
    setVoiceMode,
  };
}
