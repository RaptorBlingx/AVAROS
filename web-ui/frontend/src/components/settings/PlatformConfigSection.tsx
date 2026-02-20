import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createPlatformConfig,
  getProfile,
  getPlatformConfig,
  resetPlatformConfig,
  testConnection,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  ConnectionTestResponse,
  PlatformConfigRequest,
  PlatformConfigResponse,
  PlatformType,
} from "../../api/types";
import ConnectionTestResult from "../common/ConnectionTestResult";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";
import ProfileSelector from "./ProfileSelector";

type PlatformConfigSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  onProfileSwitch?: (profileName: string, voiceReloaded: boolean) => void;
  onActiveProfileResolved?: (profileName: string) => void;
};

type AuthType = "api_key" | "cookie";

function createPayload(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
  authType: AuthType;
  seuId: string;
}): PlatformConfigRequest {
  const seuId = config.seuId.trim();
  return {
    platform_type: config.platformType,
    api_url: config.platformType === "mock" ? "" : config.apiUrl.trim(),
    api_key: config.platformType === "mock" ? "" : config.apiKey.trim(),
    extra_settings: {
      auth_type: config.authType === "cookie" ? "cookie" : "bearer",
      ...(seuId ? { seu_id: seuId } : {}),
    },
  };
}

function validate(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
  authType: AuthType;
  seuId: string;
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
    return config.authType === "cookie"
      ? "Session cookie is required."
      : "API key is required.";
  }
  return "";
}

export default function PlatformConfigSection({
  onNotify,
  onProfileSwitch,
  onActiveProfileResolved,
}: PlatformConfigSectionProps) {
  const { isDark } = useTheme();
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [config, setConfig] = useState<PlatformConfigResponse | null>(null);
  const [platformType, setPlatformType] = useState<PlatformType>("mock");
  const [authType, setAuthType] = useState<AuthType>("api_key");
  const [seuId, setSeuId] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null);
  const [inlineError, setInlineError] = useState("");
  const [profileReadOnly, setProfileReadOnly] = useState(false);

  const isMock = useMemo(() => platformType === "mock", [platformType]);
  const adapterTarget = useMemo(
    () =>
      platformType === "reneryo"
        ? "RENERYO"
        : platformType === "custom_rest"
          ? "Custom REST"
          : "Mock",
    [platformType],
  );

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setInlineError("");
    try {
      const data = await getPlatformConfig();
      setConfig(data);
      setPlatformType(data.platform_type);
      setAuthType(
        data.extra_settings?.auth_type === "cookie"
          ? "cookie"
          : "api_key",
      );
      setSeuId(data.extra_settings?.seu_id ?? "");
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

  const handleProfileChange = useCallback(
    async (profileName: string) => {
      setInlineError("");
      setTestResult(null);
      try {
        const detail = await getProfile(profileName);
        setPlatformType(detail.platform_type as PlatformType);
        setApiUrl(detail.api_url);
        setApiKey("");
        setAuthType(
          detail.extra_settings?.auth_type === "cookie"
            ? "cookie"
            : "api_key",
        );
        setProfileReadOnly(detail.is_builtin);
        setEditing(false);
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      }
    },
    [onNotify],
  );

  const handleSave = useCallback(async () => {
    const validationError = validate({
      platformType,
      apiUrl,
      apiKey,
      authType,
      seuId,
    });
    setInlineError(validationError);
    setTestResult(null);
    if (validationError) {
      return;
    }
    setSaving(true);
    try {
      const payload = createPayload({
        platformType,
        apiUrl,
        apiKey,
        authType,
        seuId,
      });
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
  }, [apiKey, apiUrl, authType, onNotify, platformType, seuId]);

  const handleReset = useCallback(async () => {
    setSaving(true);
    setInlineError("");
    setTestResult(null);
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
      authType,
      seuId,
    });
    setInlineError(validationError);
    setTestResult(null);
    if (validationError) {
      return;
    }
    setTesting(true);
    try {
      const payload = createPayload({
        platformType,
        apiUrl,
        apiKey,
        authType,
        seuId,
      });
      const result = await testConnection(payload);
      setTestResult(result);
      onNotify(result.success ? "success" : "error", result.message);
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setTesting(false);
    }
  }, [apiKey, apiUrl, authType, isMock, onNotify, platformType, seuId]);

  return (
    <section className="space-y-3">
      <ProfileSelector
        onNotify={onNotify}
        onProfileChange={(name) => void handleProfileChange(name)}
        onActiveProfileResolved={(name) => {
          onActiveProfileResolved?.(name);
        }}
        onProfileSwitched={(name, voiceReloaded) => {
          onProfileSwitch?.(name, voiceReloaded);
        }}
      />

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
        <div className="brand-surface reveal-in rounded-xl p-4">
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
                disabled={!editing || saving || profileReadOnly}
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
                disabled={!editing || saving || isMock || profileReadOnly}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Auth Type
              </span>
              <select
                value={authType}
                onChange={(event) =>
                  setAuthType(event.target.value as AuthType)
                }
                disabled={!editing || saving || isMock || profileReadOnly}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="api_key">API Key</option>
                <option value="cookie">Session Cookie</option>
              </select>
            </label>

            <label className="block md:col-span-2">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                SEU ID (Optional)
              </span>
              <input
                type="text"
                value={seuId}
                onChange={(event) => setSeuId(event.target.value)}
                placeholder="Paste SEU ID for direct energy per unit endpoint"
                disabled={!editing || saving || isMock || platformType !== "reneryo"}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>

            <label className="block md:col-span-2">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                {authType === "cookie" ? "Session Cookie Value" : "API Key"}
              </span>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={
                  editing
                    ? authType === "cookie"
                      ? "Paste session cookie value or full Cookie: S=..."
                      : "Enter API key to update"
                    : config?.api_key ?? "****"
                }
                disabled={!editing || saving || isMock || profileReadOnly}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>
          </div>

          {inlineError && (
            <ErrorMessage title="Platform config error" message={inlineError} />
          )}
          {testResult && <ConnectionTestResult result={testResult} />}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleTest()}
              disabled={testing || saving}
              className="btn-brand-subtle rounded-lg px-3 py-2 text-xs font-semibold"
            >
              {testing ? (
                <span className="inline-flex items-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M21 12a9 9 0 10-9 9" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  Testing connection to {adapterTarget}...
                </span>
              ) : (
                "Test Connection"
              )}
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="btn-brand-primary rounded-lg px-3 py-2 text-xs font-semibold"
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
