import { useCallback, useEffect, useState } from "react";

import {
  getAlertConfig,
  saveAlertConfig,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { AlertConfigResponse, SeverityLevel } from "../../api/types";
import LoadingSpinner from "../common/LoadingSpinner";
import Tooltip from "../common/Tooltip";

type AlertSettingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

const INTERVAL_PRESETS: { label: string; value: number }[] = [
  { label: "1 hour", value: 3600 },
  { label: "4 hours", value: 14400 },
  { label: "8 hours", value: 28800 },
  { label: "24 hours", value: 86400 },
];

const SEVERITY_OPTIONS: { label: string; value: SeverityLevel }[] = [
  { label: "Low", value: "low" },
  { label: "Medium", value: "medium" },
  { label: "High", value: "high" },
  { label: "Critical", value: "critical" },
];

const COOLDOWN_PRESETS: { label: string; value: number }[] = [
  { label: "15 minutes", value: 15 },
  { label: "30 minutes", value: 30 },
  { label: "1 hour", value: 60 },
  { label: "2 hours", value: 120 },
  { label: "4 hours", value: 240 },
];

const THRESHOLD_PRESETS: {
  label: string;
  description: string;
  value: number;
}[] = [
  {
    label: "High sensitivity",
    description: "Flags ~5% of readings — use on tightly controlled lines",
    value: 2.0,
  },
  {
    label: "Balanced (recommended)",
    description: "Industry SPC standard — flags ~0.3% of readings",
    value: 3.0,
  },
  {
    label: "Low sensitivity",
    description: "Only flags extreme outliers — good for noisy equipment",
    value: 4.0,
  },
];

const CUSTOM_SENTINEL = -1;

const selectClasses =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200";

const inputClasses =
  "mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200";

function isPreset(value: number, presets: { value: number }[]): boolean {
  return presets.some((p) => p.value === value);
}

function formatSeconds(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  const h = seconds / 3600;
  return h === 1 ? "1 hour" : `${h} hours`;
}

export default function AlertSettingsSection({
  onNotify,
}: AlertSettingsSectionProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<AlertConfigResponse>({
    enabled: true,
    interval_seconds: 14400,
    severity_threshold: "medium",
    cooldown_minutes: 60,
    monitored_pairs: [],
    z_score_threshold: 2.0,
  });
  const [customInterval, setCustomInterval] = useState(false);
  const [customCooldown, setCustomCooldown] = useState(false);
  const [intervalMinutes, setIntervalMinutes] = useState(240);
  const [cooldownMinutes, setCooldownMinutes] = useState(60);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAlertConfig();
      setConfig(data);
      // Detect non-preset values → show custom inputs
      if (!isPreset(data.interval_seconds, INTERVAL_PRESETS)) {
        setCustomInterval(true);
        setIntervalMinutes(Math.round(data.interval_seconds / 60));
      }
      if (!isPreset(data.cooldown_minutes, COOLDOWN_PRESETS)) {
        setCustomCooldown(true);
        setCooldownMinutes(data.cooldown_minutes);
      }
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const saved = await saveAlertConfig(config);
      setConfig(saved);
      onNotify("success", "Proactive monitoring settings saved.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }, [config, onNotify]);

  if (loading) {
    return (
      <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
        <LoadingSpinner label="Loading alert settings..." size="sm" />
      </div>
    );
  }

  return (
    <section className="space-y-5">
      {/* Enable toggle */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-3 cursor-pointer">
          <div className="relative">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, enabled: e.target.checked }))
              }
              className="sr-only peer"
            />
            <div className="h-6 w-11 rounded-full bg-slate-300 transition-colors peer-checked:bg-cyan-500 peer-focus-visible:ring-2 peer-focus-visible:ring-cyan-400 dark:bg-slate-600" />
            <div className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
          </div>
          <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
            Enable proactive monitoring
          </span>
        </label>
        <Tooltip
          content="When enabled, AVAROS runs background anomaly and drift checks on a schedule and announces results via voice — even when you haven't asked."
          ariaLabel="Help for proactive monitoring toggle"
        />
      </div>

      {config.enabled && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Check frequency */}
          <div>
            <div className="mb-1 flex items-center gap-1.5">
              <label
                htmlFor="alert-interval"
                className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
              >
                Check Frequency
              </label>
              <Tooltip
                content="How often AVAROS queries the platform for each monitored metric and asset. Lower values catch issues faster but increase API load."
                ariaLabel="Help for check frequency"
              />
            </div>
            <select
              id="alert-interval"
              value={customInterval ? CUSTOM_SENTINEL : config.interval_seconds}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (v === CUSTOM_SENTINEL) {
                  setCustomInterval(true);
                  setIntervalMinutes(Math.round(config.interval_seconds / 60));
                } else {
                  setCustomInterval(false);
                  setConfig((prev) => ({ ...prev, interval_seconds: v }));
                }
              }}
              className={selectClasses}
            >
              {INTERVAL_PRESETS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
              <option value={CUSTOM_SENTINEL}>Custom…</option>
            </select>
            {customInterval && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={intervalMinutes}
                  onChange={(e) => {
                    const mins = Math.max(1, Math.min(1440, Number(e.target.value) || 1));
                    setIntervalMinutes(mins);
                    setConfig((prev) => ({ ...prev, interval_seconds: mins * 60 }));
                  }}
                  className={inputClasses}
                  aria-label="Custom interval in minutes"
                />
                <span className="mt-1.5 shrink-0 text-xs text-slate-500 dark:text-slate-400">
                  minutes
                </span>
              </div>
            )}
          </div>

          {/* Minimum severity */}
          <div>
            <div className="mb-1 flex items-center gap-1.5">
              <label
                htmlFor="alert-severity"
                className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
              >
                Min. Severity to Alert
              </label>
              <Tooltip
                content="Only anomalies or drifts at this severity level or above will trigger a voice alert. Lower-severity detections are still logged but stay silent."
                ariaLabel="Help for minimum severity"
              />
            </div>
            <select
              id="alert-severity"
              value={config.severity_threshold}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  severity_threshold: e.target.value as SeverityLevel,
                }))
              }
              className={selectClasses}
            >
              {SEVERITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Cooldown */}
          <div>
            <div className="mb-1 flex items-center gap-1.5">
              <label
                htmlFor="alert-cooldown"
                className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
              >
                Alert Cooldown
              </label>
              <Tooltip
                content="After voicing an alert for a specific metric + asset, AVAROS will not repeat that same alert until this cooldown period has passed — even if the anomaly persists."
                ariaLabel="Help for alert cooldown"
              />
            </div>
            <select
              id="alert-cooldown"
              value={customCooldown ? CUSTOM_SENTINEL : config.cooldown_minutes}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (v === CUSTOM_SENTINEL) {
                  setCustomCooldown(true);
                  setCooldownMinutes(config.cooldown_minutes);
                } else {
                  setCustomCooldown(false);
                  setConfig((prev) => ({ ...prev, cooldown_minutes: v }));
                }
              }}
              className={selectClasses}
            >
              {COOLDOWN_PRESETS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
              <option value={CUSTOM_SENTINEL}>Custom…</option>
            </select>
            {customCooldown && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={cooldownMinutes}
                  onChange={(e) => {
                    const mins = Math.max(1, Math.min(1440, Number(e.target.value) || 1));
                    setCooldownMinutes(mins);
                    setConfig((prev) => ({ ...prev, cooldown_minutes: mins }));
                  }}
                  className={inputClasses}
                  aria-label="Custom cooldown in minutes"
                />
                <span className="mt-1.5 shrink-0 text-xs text-slate-500 dark:text-slate-400">
                  minutes
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detection Sensitivity — shown always (affects both manual queries and background checks) */}
      <div>
        <div className="mb-1 flex items-center gap-1.5">
          <label
            htmlFor="alert-threshold"
            className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
          >
            Detection Sensitivity
          </label>
          <Tooltip
            content="Controls how unusual a reading must be before AVAROS calls it an anomaly. Higher sensitivity catches more issues but may produce false alarms on naturally variable processes. Lower sensitivity only flags extreme outliers. The industry standard for stable manufacturing lines (SPC / Six Sigma) is 'Balanced'."
            ariaLabel="Help for detection sensitivity"
          />
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {THRESHOLD_PRESETS.map((preset) => (
            <label
              key={preset.value}
              className={`flex cursor-pointer flex-col rounded-lg border p-3 transition-colors ${
                config.z_score_threshold === preset.value
                  ? "border-cyan-400 bg-cyan-50 dark:border-cyan-500 dark:bg-cyan-900/20"
                  : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-600 dark:bg-slate-800 dark:hover:border-slate-500"
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="z_score_threshold"
                  value={preset.value}
                  checked={config.z_score_threshold === preset.value}
                  onChange={() =>
                    setConfig((prev) => ({
                      ...prev,
                      z_score_threshold: preset.value,
                    }))
                  }
                  className="accent-cyan-500"
                />
                <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                  {preset.label}
                </span>
              </div>
              <span className="mt-1 pl-5 text-xs text-slate-500 dark:text-slate-400">
                {preset.description}
              </span>
            </label>
          ))}
        </div>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-400">
        {config.enabled
          ? `AVAROS will check all supported metrics every ${
              isPreset(config.interval_seconds, INTERVAL_PRESETS)
                ? INTERVAL_PRESETS.find((o) => o.value === config.interval_seconds)?.label ?? formatSeconds(config.interval_seconds)
                : formatSeconds(config.interval_seconds)
            } and announce anomalies or drifts with ${config.severity_threshold} severity or above.`
          : "Background anomaly and drift checks are disabled. Enable to receive proactive voice alerts."}
      </p>

      {/* Save button */}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className="btn-brand-primary rounded-lg px-5 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Alert Settings"}
        </button>
      </div>
    </section>
  );
}
