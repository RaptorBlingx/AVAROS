/**
 * Type definitions for the Voice interaction context.
 *
 * Extracted from VoiceContext.tsx to keep file sizes under 300 lines.
 */

import type { VoiceMode } from "../services/voice-mode";
import type { WakeWordState } from "../services/wake-word-backend";
import type { PermissionState } from "../services/audio-permissions";

// Re-export for consumer convenience
export type { VoiceMode } from "../services/voice-mode";

export type VoiceState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

export interface VoiceContextValue {
  voiceState: VoiceState;
  voiceMode: VoiceMode;
  isWakeWordArmed: boolean;
  wakeWordDetectedAt: number;
  micPermission: PermissionState;
  sttSupported: boolean;
  ttsSupported: boolean;

  startListening: () => Promise<void>;
  stopListening: () => void;
  cancelCurrentQuery: () => void;
  clearQuery: () => void;
  interimTranscript: string;
  finalTranscript: string;

  speak: (text: string) => Promise<void>;
  stopSpeaking: () => void;
  isSpeaking: boolean;

  wakeWordState: WakeWordState;
  wakeWordEnabled: boolean;
  wakeWordSensitivity: number;
  setWakeWordSensitivity: (value: number) => void;
  isModelLoading: boolean;
  wakeWordLabel: string;

  setVoiceMode: (mode: VoiceMode) => Promise<void>;
  setLanguage: (lang: string) => void;
  availableVoices: SpeechSynthesisVoice[];
  setTTSVoice: (voiceName: string) => void;
  ttsRate: number;
  setTTSRate: (rate: number) => void;
  ttsVolume: number;
  setTTSVolume: (volume: number) => void;
  requestMicPermission: () => Promise<PermissionState>;
}
