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

const VOICE_MODE_STORAGE_KEY = "avaros_voice_mode";
const LEGACY_VOICE_MODE_STORAGE_KEY = "avaros-voice-mode";
const WAKE_WORD_URL_STORAGE_KEY = "avaros_wake_word_url";
const WAKE_WORD_SENSITIVITY_STORAGE_KEY = "avaros_wake_word_sensitivity";
const DEFAULT_WAKE_WORD_SENSITIVITY = 0.75;

function getInitialVoiceMode(): VoiceMode {
  if (typeof window === "undefined") return "text";
  const raw =
    window.localStorage.getItem(VOICE_MODE_STORAGE_KEY)
    ?? window.localStorage.getItem(LEGACY_VOICE_MODE_STORAGE_KEY);
  if (raw === "wake-word" || raw === "push-to-talk" || raw === "text") {
    return raw;
  }
  return "text";
}

function getInitialWakeWordSensitivity(): number {
  if (typeof window === "undefined") return DEFAULT_WAKE_WORD_SENSITIVITY;
  const raw = window.localStorage.getItem(WAKE_WORD_SENSITIVITY_STORAGE_KEY);
  if (!raw) return DEFAULT_WAKE_WORD_SENSITIVITY;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return DEFAULT_WAKE_WORD_SENSITIVITY;
  return Math.max(0, Math.min(1, parsed));
}

function getConfiguredWakeWordUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const raw = window.localStorage.getItem(WAKE_WORD_URL_STORAGE_KEY);
  const value = raw?.trim();
  if (!value) return undefined;

  const host = window.location.hostname;
  const isLocalHost = host === "localhost" || host === "127.0.0.1";

  // Hosted deployments should ignore stale localhost URLs from previous local runs.
  if (!isLocalHost && /(^wss?:\/\/)?(localhost|127\.0\.0\.1)([:/]|$)/i.test(value)) {
    return undefined;
  }

  // Avoid mixed-content websocket URLs when the app is served over HTTPS.
  if (window.location.protocol === "https:" && value.startsWith("ws://")) {
    return undefined;
  }

  return value;
}

// ── Types ──────────────────────────────────────────────

export interface UseWakeWordResult {
  wakeWordState: WakeWordState;
  wakeWordEnabled: boolean;
  wakeWordSensitivity: number;
  setWakeWordSensitivity: (value: number) => void;
  isModelLoading: boolean;
  wakeWordLabel: string;
  voiceMode: VoiceMode;
  setVoiceMode: (mode: VoiceMode) => Promise<void>;
  /** True when the backend openWakeWord service is being used. */
  isBackendWakeWord: boolean;
  /** Pause wake-word audio streaming (keeps WebSocket open for quick restart). */
  pauseDetection: () => void;
  /** Resume wake-word audio streaming after a paused interaction cycle. */
  resumeDetection: () => void;
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
  const initialWakeWordSensitivity = getInitialWakeWordSensitivity();

  const backendWakeWordRef = useRef<BackendWakeWordService | null>(null);
  const voiceModeRef = useRef<VoiceModeService | null>(null);

  const [wakeWordState, setWakeWordState] = useState<WakeWordState>("idle");
  const [wakeWordSensitivity, setWakeWordSensitivityState] = useState(
    initialWakeWordSensitivity,
  );
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [wakeWordLabel, setWakeWordLabel] = useState("Hey Avaros");
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
        ? new BackendWakeWordService({
          wsUrl: configuredUrl,
          sensitivity: initialWakeWordSensitivity,
        })
        : new BackendWakeWordService({
          sensitivity: initialWakeWordSensitivity,
        });
    }
    void backendWakeWordRef.current
      .refreshWakeWordLabel()
      .then((label) => setWakeWordLabel(label));

    ensureVoiceModeService();

    return () => {
      backendWakeWordRef.current?.dispose();
    };
  }, [ensureVoiceModeService, initialWakeWordSensitivity]);

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

    const unsubDetected = bww.onDetected((payload) => {
      console.log(
        `[AVAROS-DEBUG] wakeWord backend detected: model=${payload.model}, score=${payload.score.toFixed(4)}`,
      );
      setWakeWordLabel(bww.getWakeWordLabel());
      onDetected(payload);
    });

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
        window.localStorage.setItem(LEGACY_VOICE_MODE_STORAGE_KEY, effectiveMode);
      }
    },
    [ensureVoiceModeService, sttRef],
  );

  const setWakeWordSensitivity = useCallback((value: number) => {
    const normalized = Math.max(0, Math.min(1, value));
    setWakeWordSensitivityState(normalized);
    backendWakeWordRef.current?.setSensitivity(normalized);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        WAKE_WORD_SENSITIVITY_STORAGE_KEY,
        String(normalized),
      );
    }
  }, []);

  const pauseDetection = useCallback(() => {
    console.log(`[AVAROS-DEBUG] pauseDetection called (stopListening)`);
    backendWakeWordRef.current?.stopListening();
  }, []);

  const resumeDetection = useCallback(() => {
    const backend = backendWakeWordRef.current;
    console.log(`[AVAROS-DEBUG] resumeDetection called, hasBackend=${!!backend}`);
    if (!backend) return;

    void backend.startListening()
      .then(() => console.log(`[AVAROS-DEBUG] resumeDetection: startListening succeeded`))
      .catch((err) => {
        console.warn(`[AVAROS-DEBUG] resumeDetection: startListening failed, re-initializing`, err);
        void backend
          .initialize()
          .then(() => backend.startListening())
          .then(() => console.log(`[AVAROS-DEBUG] resumeDetection: re-init + startListening succeeded`))
          .catch((err2) => console.error(`[AVAROS-DEBUG] resumeDetection: re-init also failed`, err2));
      });
  }, []);

  return {
    wakeWordState,
    wakeWordEnabled,
    wakeWordSensitivity,
    setWakeWordSensitivity,
    isModelLoading,
    wakeWordLabel,
    voiceMode,
    setVoiceMode,
    isBackendWakeWord,
    pauseDetection,
    resumeDetection,
  };
}
