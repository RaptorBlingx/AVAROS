import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createPlatformConfig,
  getPlatformConfig,
  resetPlatformConfig,
  testConnection,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  PlatformConfigRequest,
  PlatformConfigResponse,
  PlatformType,
} from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";

type PlatformConfigSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

function createPayload(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
}): PlatformConfigRequest {
  return {
    platform_type: config.platformType,
    api_url: config.platformType === "mock" ? "" : config.apiUrl.trim(),
    api_key: config.platformType === "mock" ? "" : config.apiKey.trim(),
    extra_settings: {},
  };
}

function validate(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
}): string {
  if (config.platformType === "mock") {
    return "";
  }
  if (!config.apiUrl.trim()) {
    return "API URL is required.";
  }
  if (!/^https?:\/\//i.test(config.apiUrl.trim())) {
    return "API URL must start with http:// or https://.";
  }
  if (!config.apiKey.trim()) {
    return "API key is required.";
  }
  return "";
}

export default function PlatformConfigSection({
  onNotify,
}: PlatformConfigSectionProps) {
  const { isDark } = useTheme();
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [config, setConfig] = useState<PlatformConfigResponse | null>(null);
  const [platformType, setPlatformType] = useState<PlatformType>("mock");
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [inlineMessage, setInlineMessage] = useState("");
  const [inlineError, setInlineError] = useState("");

  const isMock = useMemo(() => platformType === "mock", [platformType]);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setInlineError("");
    try {
      const data = await getPlatformConfig();
      setConfig(data);
      setPlatformType(data.platform_type);
      setApiUrl(data.api_url);
      setApiKey("");
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const handleSave = useCallback(async () => {
    const validationError = validate({ platformType, apiUrl, apiKey });
    setInlineError(validationError);
    setInlineMessage("");
    if (validationError) {
      return;
    }
    setSaving(true);
    try {
      const payload = createPayload({ platformType, apiUrl, apiKey });
      const saved = await createPlatformConfig(payload);
      setConfig(saved);
      setEditing(false);
      setApiKey("");
      onNotify("success", "Platform config updated.");
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setSaving(false);
    }
  }, [apiKey, apiUrl, onNotify, platformType]);

  const handleReset = useCallback(async () => {
    setSaving(true);
    setInlineError("");
    setInlineMessage("");
    try {
      await resetPlatformConfig();
      await loadConfig();
      setEditing(false);
      onNotify("success", "Platform config reset to mock.");
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setSaving(false);
    }
  }, [loadConfig, onNotify]);

  const handleTest = useCallback(async () => {
    const validationError = validate({
      platformType,
      apiUrl,
      apiKey: isMock ? "" : apiKey,
    });
    setInlineError(validationError);
    setInlineMessage("");
    if (validationError) {
      return;
    }
    setTesting(true);
    try {
      const payload = createPayload({ platformType, apiUrl, apiKey });
      const result = await testConnection(payload);
      setInlineMessage(result.message);
      onNotify(result.success ? "success" : "error", result.message);
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setTesting(false);
    }
  }, [apiKey, apiUrl, isMock, onNotify, platformType]);

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
              isDark
                ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
                : "border-slate-300 bg-white text-slate-700"
            }`}
            onClick={() => setEditing((prev) => !prev)}
          >
            {editing ? "Cancel" : "Edit"}
          </button>
          <button
            type="button"
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
              isDark
                ? "border-rose-400 bg-rose-950/60 text-rose-200 hover:bg-rose-900/60"
                : "border-rose-300 bg-rose-50 text-rose-700"
            }`}
            onClick={() => void handleReset()}
            disabled={saving}
          >
            Reset
          </button>
        </div>
      </header>

      {loading ? (
        <div className="rounded-lg border opacity-50 border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          <LoadingSpinner label="Loading platform config..." size="sm" />
        </div>
      ) : (
        <div className="reveal-in rounded-xl border border-sky-200 bg-sky-50/70 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Platform
              </span>
              <select
                value={platformType}
                onChange={(event) =>
                  setPlatformType(event.target.value as PlatformType)
                }
                disabled={!editing || saving}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="mock">Mock</option>
                <option value="reneryo">RENERYO</option>
                <option value="custom_rest">Custom REST</option>
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                API URL
              </span>
              <input
                type="url"
                value={apiUrl}
                onChange={(event) => setApiUrl(event.target.value)}
                disabled={!editing || saving || isMock}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>

            <label className="block md:col-span-2">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                API Key
              </span>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={
                  editing
                    ? "Enter API key to update"
                    : config?.api_key ?? "****"
                }
                disabled={!editing || saving || isMock}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>
          </div>

          {inlineError && (
            <ErrorMessage title="Platform config error" message={inlineError} />
          )}
          {inlineMessage && (
            <p className="m-0 mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {inlineMessage}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleTest()}
              disabled={testing || saving}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                isDark
                  ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
                  : "border-slate-300 bg-white text-slate-700"
              }`}
            >
              {testing ? "Testing..." : "Test Connection"}
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                  isDark
                    ? "border-slate-400 bg-white text-slate-900"
                    : "border-sky-300 bg-sky-50 text-sky-700"
                }`}
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
