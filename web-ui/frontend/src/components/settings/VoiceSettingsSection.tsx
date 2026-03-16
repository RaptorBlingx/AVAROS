import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useVoice } from "../../contexts/VoiceContext";
import type { VoiceMode } from "../../contexts/voice-types";
import {
  DEFAULT_VOICE_SETTINGS,
  useVoiceSettings,
} from "../../hooks/useVoiceSettings";
import MicrophoneTest from "./MicrophoneTest";

type VoiceSettingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

const PREVIEW_TEXT = "Hello, I am AVAROS, your manufacturing assistant.";

export default function VoiceSettingsSection({
  onNotify,
}: VoiceSettingsSectionProps) {
  const {
    voiceMode,
    setVoiceMode,
    wakeWordState,
    setWakeWordSensitivity,
    isModelLoading,
    wakeWordLabel,
    setLanguage,
    availableVoices,
    setTTSVoice,
    ttsSupported,
    speak,
    stopSpeaking,
    ttsRate,
    setTTSRate,
    ttsVolume,
    setTTSVolume,
    requestMicPermission,
  } = useVoice();
  const settings = useVoiceSettings();
  const wakeWordDisplay = useMemo(
    () => wakeWordLabel || "Hey Avaros",
    [wakeWordLabel],
  );

  const didApplyInitialSettings = useRef(false);
  const wakeWordTestTimerRef = useRef<number | null>(null);
  const wakeWordTestRestoreModeRef = useRef<VoiceMode | null>(null);
  const [wakeWordTestStatus, setWakeWordTestStatus] = useState<{
    running: boolean;
    tone: "neutral" | "success" | "warning";
    message: string;
  }>({
    running: false,
    tone: "neutral",
    message: `Run wake-word test for 10 seconds, then say "${wakeWordDisplay}".`,
  });

  const voicesByLanguage = useMemo(() => {
    const map = new Map<string, SpeechSynthesisVoice[]>();
    availableVoices.forEach((voice) => {
      const key = voice.lang || "unknown";
      const bucket = map.get(key) ?? [];
      bucket.push(voice);
      map.set(key, bucket);
    });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [availableVoices]);

  const applySettingsToVoiceContext = useCallback(async () => {
    const modeToApply =
      settings.wakeWordEnabled || settings.voiceMode !== "wake-word"
        ? settings.voiceMode
        : "push-to-talk";

    try {
      await setVoiceMode(modeToApply);
    } catch {
      onNotify("error", "Could not apply saved voice mode. Using fallback mode.");
      await setVoiceMode("push-to-talk").catch(() => undefined);
    }

    setWakeWordSensitivity(settings.wakeWordSensitivity);
    setLanguage(settings.language);
    if (settings.ttsVoice) {
      setTTSVoice(settings.ttsVoice);
    }
    setTTSRate(settings.ttsRate);
    setTTSVolume(settings.ttsVolume);
  }, [
    onNotify,
    setLanguage,
    setTTSRate,
    setTTSVoice,
    setTTSVolume,
    setVoiceMode,
    setWakeWordSensitivity,
    settings.language,
    settings.ttsRate,
    settings.ttsVoice,
    settings.ttsVolume,
    settings.voiceMode,
    settings.wakeWordEnabled,
    settings.wakeWordSensitivity,
  ]);

  useEffect(() => {
    if (didApplyInitialSettings.current) return;
    didApplyInitialSettings.current = true;
    void applySettingsToVoiceContext();
  }, [applySettingsToVoiceContext]);

  useEffect(() => {
    if (!settings.ttsVoice && availableVoices.length > 0) {
      const preferred =
        availableVoices.find((voice) => voice.lang.toLowerCase().startsWith("en")) ??
        availableVoices[0];
      settings.updateSetting("ttsVoice", preferred.name);
      setTTSVoice(preferred.name);
    }
  }, [availableVoices, settings, setTTSVoice]);

  useEffect(() => {
    return () => {
      if (wakeWordTestTimerRef.current !== null) {
        window.clearTimeout(wakeWordTestTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!wakeWordTestStatus.running) return;
    if (wakeWordState !== "detected") return;

    if (wakeWordTestTimerRef.current !== null) {
      window.clearTimeout(wakeWordTestTimerRef.current);
      wakeWordTestTimerRef.current = null;
    }

    const restore = wakeWordTestRestoreModeRef.current;
    if (restore && restore !== "wake-word") {
      void setVoiceMode(restore).catch(() => undefined);
    }
    wakeWordTestRestoreModeRef.current = null;

    setWakeWordTestStatus({
      running: false,
      tone: "success",
      message: "Detection successful ✓",
    });
  }, [setVoiceMode, wakeWordState, wakeWordTestStatus.running]);

  const handleModeChange = useCallback(
    async (mode: VoiceMode) => {
      settings.updateSetting("voiceMode", mode);
      if (mode === "wake-word") {
        settings.updateSetting("wakeWordEnabled", true);
      }
      try {
        await setVoiceMode(mode);
      } catch {
        onNotify("error", "Could not switch voice mode.");
      }
    },
    [onNotify, setVoiceMode, settings],
  );

  const handleWakeWordToggle = useCallback(
    async (enabled: boolean) => {
      settings.updateSetting("wakeWordEnabled", enabled);

      if (!enabled) {
        if (settings.voiceMode === "wake-word") {
          settings.updateSetting("voiceMode", "push-to-talk");
          await setVoiceMode("push-to-talk").catch(() => undefined);
        }
        return;
      }

      if (settings.voiceMode === "wake-word") {
        await setVoiceMode("wake-word").catch(() => undefined);
        return;
      }

      // Warm up wake-word model in background without changing persisted mode.
      try {
        const restoreMode = settings.voiceMode;
        await setVoiceMode("wake-word");
        await setVoiceMode(restoreMode);
      } catch {
        onNotify(
          "error",
          "Wake-word model could not be preloaded. It will retry when wake-word mode is selected.",
        );
      }
    },
    [onNotify, setVoiceMode, settings],
  );

  const handleWakeWordSensitivity = useCallback(
    (value: number) => {
      settings.updateSetting("wakeWordSensitivity", value);
      setWakeWordSensitivity(value);
    },
    [setWakeWordSensitivity, settings],
  );

  const handleLanguageChange = useCallback(
    (value: string) => {
      settings.updateSetting("language", value);
      setLanguage(value);
    },
    [setLanguage, settings],
  );

  const handleVoiceChange = useCallback(
    (voiceName: string) => {
      settings.updateSetting("ttsVoice", voiceName);
      setTTSVoice(voiceName);
    },
    [setTTSVoice, settings],
  );

  const handleRateChange = useCallback(
    (value: number) => {
      settings.updateSetting("ttsRate", value);
      setTTSRate(value);
    },
    [setTTSRate, settings],
  );

  const handleVolumeChange = useCallback(
    (value: number) => {
      settings.updateSetting("ttsVolume", value);
      setTTSVolume(value);
    },
    [setTTSVolume, settings],
  );

  const handlePreview = useCallback(async () => {
    if (!ttsSupported) {
      onNotify("error", "TTS is not supported in this browser.");
      return;
    }
    stopSpeaking();
    try {
      await speak(PREVIEW_TEXT);
    } catch {
      onNotify("error", "Could not play voice preview.");
    }
  }, [onNotify, speak, stopSpeaking, ttsSupported]);

  const handleWakeWordTest = useCallback(async () => {
    if (wakeWordTestStatus.running) return;
    if (!settings.wakeWordEnabled) {
      setWakeWordTestStatus({
        running: false,
        tone: "warning",
        message: "Enable Wake Word before running test.",
      });
      return;
    }

    const permission = await requestMicPermission();
    if (permission !== "granted") {
      setWakeWordTestStatus({
        running: false,
        tone: "warning",
        message:
          "Microphone access is required for wake-word test. Please allow permission.",
      });
      return;
    }

    const previousMode = voiceMode;
    wakeWordTestRestoreModeRef.current = previousMode;

    if (previousMode !== "wake-word") {
      try {
        await setVoiceMode("wake-word");
      } catch {
        setWakeWordTestStatus({
          running: false,
          tone: "warning",
          message:
            "Wake Word is not available in current environment. Use Push-to-Talk.",
        });
        wakeWordTestRestoreModeRef.current = null;
        return;
      }
    }

    setWakeWordTestStatus({
      running: true,
      tone: "neutral",
      message: `Listening for 10 seconds. Say "${wakeWordDisplay}" clearly.`,
    });

    wakeWordTestTimerRef.current = window.setTimeout(() => {
      const restore = wakeWordTestRestoreModeRef.current;
      if (restore && restore !== "wake-word") {
        void setVoiceMode(restore).catch(() => undefined);
      }
      wakeWordTestRestoreModeRef.current = null;
      setWakeWordTestStatus({
        running: false,
        tone: "warning",
        message: `Not detected. Try saying "${wakeWordDisplay}" clearly.`,
      });
    }, 10000);
  }, [
    requestMicPermission,
    settings.wakeWordEnabled,
    setVoiceMode,
    voiceMode,
    wakeWordDisplay,
    wakeWordTestStatus.running,
  ]);

  const handleResetDefaults = useCallback(async () => {
    if (!window.confirm("Reset all voice settings to defaults?")) return;
    settings.resetDefaults();

    setWakeWordSensitivity(DEFAULT_VOICE_SETTINGS.wakeWordSensitivity);
    setLanguage(DEFAULT_VOICE_SETTINGS.language);
    setTTSRate(DEFAULT_VOICE_SETTINGS.ttsRate);
    setTTSVolume(DEFAULT_VOICE_SETTINGS.ttsVolume);
    setTTSVoice("");
    await setVoiceMode(DEFAULT_VOICE_SETTINGS.voiceMode).catch(() => undefined);
    onNotify("success", "Voice settings reset to defaults.");
  }, [
    onNotify,
    setLanguage,
    setTTSRate,
    setTTSVoice,
    setTTSVolume,
    setVoiceMode,
    setWakeWordSensitivity,
    settings,
  ]);

  const wakeWordStatusText = useMemo(() => {
    if (!settings.wakeWordEnabled) return "Service disabled";
    if (isModelLoading) return "Connecting...";
    if (wakeWordState === "listening" || wakeWordState === "detected") {
      return "Connected ✓";
    }
    if (wakeWordState === "unsupported") return "Service not available";
    if (wakeWordState === "error") return "Connection failed";
    return "Service idle";
  }, [isModelLoading, settings.wakeWordEnabled, wakeWordState]);

  const wakeWordConnected =
    settings.wakeWordEnabled &&
    (wakeWordState === "listening" || wakeWordState === "detected");

  const wakeWordTestToneClass =
    wakeWordTestStatus.tone === "success"
      ? "text-emerald-700 dark:text-emerald-300"
      : wakeWordTestStatus.tone === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : "text-slate-600 dark:text-slate-300";

  return (
    <section className="space-y-4">
      <div className="brand-surface reveal-in rounded-xl p-4">
        <div className="mb-4 flex items-center gap-2">
          <span aria-hidden="true" className="text-lg">
            🎙️
          </span>
          <p className="m-0 text-sm font-semibold uppercase tracking-[0.08em] text-slate-700 dark:text-slate-200">
            Voice & Audio
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-xs font-semibold uppercase text-slate-500">
              Default Interaction Mode
            </legend>
            {[
              {
                mode: "wake-word" as VoiceMode,
                label: "Wake Word",
                description: `Say "${wakeWordDisplay}" to activate — mic stays on`,
              },
              {
                mode: "push-to-talk" as VoiceMode,
                label: "Push-to-Talk",
                description: "Click the mic button to speak",
              },
              {
                mode: "text" as VoiceMode,
                label: "Text Only",
                description: "Type your queries — no microphone needed",
              },
            ].map((item) => (
              <label
                key={item.mode}
                className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700"
              >
                <input
                  type="radio"
                  name="voice-mode"
                  checked={settings.voiceMode === item.mode}
                  onChange={() => void handleModeChange(item.mode)}
                  className="mt-0.5"
                />
                <span>
                  <span className="block font-semibold text-slate-800 dark:text-slate-100">
                    {item.label}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    {item.description}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>

          <div className="space-y-3 rounded-lg border border-slate-200 p-3 dark:border-slate-700">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                Wake Word
              </span>
              <button
                type="button"
                onClick={() => void handleWakeWordToggle(!settings.wakeWordEnabled)}
                className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold transition ${
                  settings.wakeWordEnabled
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"
                    : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-200"
                }`}
              >
                {settings.wakeWordEnabled ? "On" : "Off"}
              </button>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`inline-block h-2.5 w-2.5 rounded-full ${
                  wakeWordConnected
                    ? "bg-emerald-500"
                    : settings.wakeWordEnabled
                      ? "bg-red-500"
                      : "bg-slate-400"
                }`}
                title={wakeWordConnected ? "Connected" : "Disconnected"}
              />
              <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                {wakeWordStatusText}
              </p>
            </div>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Sensitivity ({settings.wakeWordSensitivity.toFixed(2)})
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={settings.wakeWordSensitivity}
                onChange={(event) =>
                  handleWakeWordSensitivity(Number(event.target.value))
                }
                className="w-full"
                disabled={!settings.wakeWordEnabled}
              />
              <div className="mt-1 flex justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>Low</span>
                <span>Medium</span>
                <span>High</span>
              </div>
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Service URL
              </span>
              <input
                type="text"
                placeholder="ws://localhost:9999/ws/detect"
                value={settings.wakeWordUrl ?? ""}
                onChange={(event) =>
                  settings.updateSetting("wakeWordUrl", event.target.value)
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                disabled={!settings.wakeWordEnabled}
              />
              <span className="mt-0.5 block text-[11px] text-slate-400">
                Auto-populated from VITE_WAKEWORD_URL or Docker env
              </span>
            </label>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void handleWakeWordTest()}
                disabled={wakeWordTestStatus.running}
                className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                {wakeWordTestStatus.running ? "Listening..." : "Test Wake Word"}
              </button>
              <p className={`m-0 text-xs ${wakeWordTestToneClass}`}>
                {wakeWordTestStatus.message}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="brand-surface reveal-in rounded-xl p-4 space-y-4">
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            STT Settings
          </p>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              STT Engine
            </span>
            <select
              value={settings.sttEngine}
              onChange={(event) =>
                settings.updateSetting("sttEngine", event.target.value)
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="browser">Browser Native</option>
              <option value="server" disabled>
                Server-side (Coming soon)
              </option>
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Language
            </span>
            <select
              value={settings.language}
              onChange={(event) => handleLanguageChange(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="en-US">English (US)</option>
              <option value="en-GB">English (UK)</option>
              <option value="tr-TR" disabled>
                Turkish (Coming soon)
              </option>
            </select>
          </label>

          <MicrophoneTest />
        </div>

        <div className="brand-surface reveal-in rounded-xl p-4 space-y-4">
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            TTS Settings
          </p>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              TTS Engine
            </span>
            <select
              value={settings.ttsEngine}
              onChange={(event) =>
                settings.updateSetting("ttsEngine", event.target.value)
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="browser">Browser Native</option>
              <option value="server" disabled>
                Server-side (Coming soon)
              </option>
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Voice
            </span>
            <select
              value={settings.ttsVoice}
              onChange={(event) => handleVoiceChange(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              {voicesByLanguage.map(([language, voices]) => (
                <optgroup key={language} label={language}>
                  {voices.map((voice) => (
                    <option key={`${language}-${voice.name}`} value={voice.name}>
                      {voice.name} ({voice.lang})
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Speech Rate ({ttsRate.toFixed(2)})
            </span>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.05}
              value={ttsRate}
              onChange={(event) => handleRateChange(Number(event.target.value))}
              className="w-full"
            />
            <div className="mt-1 flex justify-between text-[11px] text-slate-500 dark:text-slate-400">
              <span>Slow</span>
              <span>Normal</span>
              <span>Fast</span>
            </div>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Volume ({ttsVolume.toFixed(2)})
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={ttsVolume}
              onChange={(event) => handleVolumeChange(Number(event.target.value))}
              className="w-full"
            />
          </label>

          <button
            type="button"
            onClick={() => void handlePreview()}
            className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
          >
            Preview Voice
          </button>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void handleResetDefaults()}
          className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:border-rose-500/50 dark:bg-rose-950/40 dark:text-rose-200"
        >
          Reset Voice Settings
        </button>
      </div>
    </section>
  );
}
