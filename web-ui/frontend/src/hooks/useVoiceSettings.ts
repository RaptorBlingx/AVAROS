import { useCallback, useMemo, useState } from "react";

import type { VoiceMode } from "../contexts/voice-types";

export type STTEngine = "browser" | "server";
export type TTSEngine = "browser" | "server";

export type VoiceSettingsState = {
  voiceMode: VoiceMode;
  wakeWordEnabled: boolean;
  wakeWordSensitivity: number;
  sttEngine: STTEngine;
  ttsEngine: TTSEngine;
  language: string;
  ttsVoice: string;
  ttsRate: number;
  ttsVolume: number;
};

const STORAGE_KEYS = {
  voiceMode: "avaros_voice_mode",
  wakeWordEnabled: "avaros_voice_wake_word_enabled",
  wakeWordSensitivity: "avaros_wake_word_sensitivity",
  sttEngine: "avaros_stt_engine",
  language: "avaros_voice_language",
  ttsEngine: "avaros_tts_engine",
  ttsVoice: "avaros_tts_voice",
  ttsRate: "avaros_tts_rate",
  ttsVolume: "avaros_tts_volume",
} as const;

export const DEFAULT_VOICE_SETTINGS: VoiceSettingsState = {
  voiceMode: "push-to-talk",
  wakeWordEnabled: true,
  wakeWordSensitivity: 0.75,
  sttEngine: "browser",
  ttsEngine: "browser",
  language: "en-US",
  ttsVoice: "",
  ttsRate: 1,
  ttsVolume: 1,
};

function isVoiceMode(value: string): value is VoiceMode {
  return value === "wake-word" || value === "push-to-talk" || value === "text";
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function parseBoolean(raw: string | null, fallback: boolean): boolean {
  if (raw === "true") return true;
  if (raw === "false") return false;
  return fallback;
}

function parseNumber(raw: string | null, fallback: number): number {
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function safeNumber(value: unknown, fallback: number): number {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
      ? Number(value)
      : Number.NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readInitialSettings(): VoiceSettingsState {
  if (typeof window === "undefined") {
    return DEFAULT_VOICE_SETTINGS;
  }

  const storedMode = localStorage.getItem(STORAGE_KEYS.voiceMode) ?? "";
  const voiceMode: VoiceMode = isVoiceMode(storedMode)
    ? storedMode
    : DEFAULT_VOICE_SETTINGS.voiceMode;

  const sttEngineRaw = localStorage.getItem(STORAGE_KEYS.sttEngine);
  const sttEngine: STTEngine =
    sttEngineRaw === "server" ? "server" : DEFAULT_VOICE_SETTINGS.sttEngine;

  const ttsEngineRaw = localStorage.getItem(STORAGE_KEYS.ttsEngine);
  const ttsEngine: TTSEngine =
    ttsEngineRaw === "server" ? "server" : DEFAULT_VOICE_SETTINGS.ttsEngine;

  return {
    voiceMode,
    wakeWordEnabled: parseBoolean(
      localStorage.getItem(STORAGE_KEYS.wakeWordEnabled),
      DEFAULT_VOICE_SETTINGS.wakeWordEnabled,
    ),
    wakeWordSensitivity: clamp(
      parseNumber(
        localStorage.getItem(STORAGE_KEYS.wakeWordSensitivity),
        DEFAULT_VOICE_SETTINGS.wakeWordSensitivity,
      ),
      0,
      1,
    ),
    sttEngine,
    ttsEngine,
    language:
      localStorage.getItem(STORAGE_KEYS.language) ??
      DEFAULT_VOICE_SETTINGS.language,
    ttsVoice:
      localStorage.getItem(STORAGE_KEYS.ttsVoice) ??
      DEFAULT_VOICE_SETTINGS.ttsVoice,
    ttsRate: clamp(
      parseNumber(
        localStorage.getItem(STORAGE_KEYS.ttsRate),
        DEFAULT_VOICE_SETTINGS.ttsRate,
      ),
      0.5,
      2,
    ),
    ttsVolume: clamp(
      parseNumber(
        localStorage.getItem(STORAGE_KEYS.ttsVolume),
        DEFAULT_VOICE_SETTINGS.ttsVolume,
      ),
      0,
      1,
    ),
  };
}

function persistSetting<K extends keyof VoiceSettingsState>(
  key: K,
  value: VoiceSettingsState[K],
): void {
  if (typeof window === "undefined") return;
  const storageKey = STORAGE_KEYS[key];
  localStorage.setItem(storageKey, String(value));
}

export function useVoiceSettings(): {
  voiceMode: VoiceMode;
  wakeWordEnabled: boolean;
  wakeWordSensitivity: number;
  sttEngine: STTEngine;
  ttsEngine: TTSEngine;
  language: string;
  ttsVoice: string;
  ttsRate: number;
  ttsVolume: number;
  updateSetting: (key: string, value: unknown) => void;
  resetDefaults: () => void;
} {
  const [settings, setSettings] = useState<VoiceSettingsState>(() =>
    readInitialSettings(),
  );

  const updateSetting = useCallback((key: string, value: unknown) => {
    setSettings((prev) => {
      const next = { ...prev };

      switch (key) {
        case "voiceMode":
          if (typeof value === "string" && isVoiceMode(value)) {
            next.voiceMode = value;
          }
          break;
        case "wakeWordEnabled":
          next.wakeWordEnabled = Boolean(value);
          break;
        case "wakeWordSensitivity":
          next.wakeWordSensitivity = clamp(
            safeNumber(value, prev.wakeWordSensitivity),
            0,
            1,
          );
          break;
        case "sttEngine":
          next.sttEngine = value === "server" ? "server" : "browser";
          break;
        case "ttsEngine":
          next.ttsEngine = value === "server" ? "server" : "browser";
          break;
        case "language":
          if (typeof value === "string" && value.trim()) {
            next.language = value;
          }
          break;
        case "ttsVoice":
          next.ttsVoice = typeof value === "string" ? value : "";
          break;
        case "ttsRate":
          next.ttsRate = clamp(safeNumber(value, prev.ttsRate), 0.5, 2);
          break;
        case "ttsVolume":
          next.ttsVolume = clamp(safeNumber(value, prev.ttsVolume), 0, 1);
          break;
        default:
          return prev;
      }

      if (!next.wakeWordEnabled && next.voiceMode === "wake-word") {
        next.voiceMode = "push-to-talk";
      }

      (Object.keys(STORAGE_KEYS) as Array<keyof typeof STORAGE_KEYS>).forEach(
        (storageField) => {
          persistSetting(storageField, next[storageField]);
        },
      );

      return next;
    });
  }, []);

  const resetDefaults = useCallback(() => {
    setSettings(DEFAULT_VOICE_SETTINGS);
    if (typeof window === "undefined") return;
    Object.keys(localStorage).forEach((key) => {
      if (
        key.startsWith("avaros_voice_") ||
        key.startsWith("avaros_tts_") ||
        key.startsWith("avaros_stt_") ||
        key.startsWith("avaros_wake_word_")
      ) {
        localStorage.removeItem(key);
      }
    });
  }, []);

  return useMemo(
    () => ({
      ...settings,
      updateSetting,
      resetDefaults,
    }),
    [settings, updateSetting, resetDefaults],
  );
}
