import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createPlatformConfig,
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
  ProfileDetailResponse,
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

type AuthType = "api_key" | "cookie" | "none";
const MOCK_PRESET_URL =
  (import.meta.env.VITE_MOCK_PRESET_URL || "http://reneryo-data-generator-api:8090").trim();

function normalizeUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

function isMockPresetConfig(config: {
  platformType: PlatformType;
  authType: AuthType;
  apiUrl: string;
}): boolean {
  return (
    config.platformType === "custom_rest" &&
    config.authType === "none" &&
    normalizeUrl(config.apiUrl) === normalizeUrl(MOCK_PRESET_URL)
  );
}

function toBackendAuthType(authType: AuthType): "bearer" | "cookie" | "none" {
  if (authType === "cookie") {
    return "cookie";
  }
  if (authType === "none") {
    return "none";
  }
  return "bearer";
}

function fromBackendAuthType(authType: string | undefined): AuthType {
  if (authType === "cookie") {
    return "cookie";
  }
  if (authType === "none") {
    return "none";
  }
  return "api_key";
}

function createPayload(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
  authType: AuthType;
  isMockPreset: boolean;
}): PlatformConfigRequest {
  const shouldBlankApiKey =
    config.platformType === "unconfigured" ||
    config.authType === "none" ||
    config.isMockPreset;
  return {
    platform_type: config.platformType,
    api_url:
      config.platformType === "unconfigured"
        ? ""
        : config.isMockPreset
        ? MOCK_PRESET_URL
        : config.apiUrl.trim(),
    api_key: shouldBlankApiKey ? "" : config.apiKey.trim(),
    extra_settings: {
      auth_type: config.isMockPreset ? "none" : toBackendAuthType(config.authType),
    },
  };
}

function validate(config: {
  platformType: PlatformType;
  apiUrl: string;
  apiKey: string;
  authType: AuthType;
  isMockPreset: boolean;
}): string {
  if (config.platformType === "unconfigured" || config.isMockPreset) {
    return "";
  }
  if (!config.apiUrl.trim()) {
    return "API URL is required.";
  }
  if (!/^https?:\/\//i.test(config.apiUrl.trim())) {
    return "API URL must start with http:// or https://.";
  }
  if (config.authType !== "none" && !config.apiKey.trim()) {
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
  const [platformType, setPlatformType] = useState<PlatformType>("unconfigured");
  const [authType, setAuthType] = useState<AuthType>("api_key");
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isMockPreset, setIsMockPreset] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(
    null,
  );
  const [inlineError, setInlineError] = useState("");
  const [isBuiltinProfile, setIsBuiltinProfile] = useState(false);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);

  const isUnconfigured = useMemo(() => platformType === "unconfigured", [platformType]);
  const adapterTarget = useMemo(
    () =>
      platformType === "custom_rest"
        ? isMockPreset
          ? "Mock API"
          : "REST API"
        : "Unconfigured",
    [isMockPreset, platformType],
  );

  const formLocked = isBuiltinProfile;

  const handleProfileChange = useCallback((profile: ProfileDetailResponse) => {
    const nextAuthType = fromBackendAuthType(profile.extra_settings?.auth_type);
    const nextApiUrl = profile.api_url;
    const nextPlatformType = profile.platform_type as PlatformType;
    setPlatformType(profile.platform_type as PlatformType);
    setApiUrl(nextApiUrl);
    setApiKey("");
    setAuthType(nextAuthType);
    setIsMockPreset(
      isMockPresetConfig({
        platformType: nextPlatformType,
        authType: nextAuthType,
        apiUrl: nextApiUrl,
      }),
    );
    setConfig({
      platform_type: nextPlatformType,
      api_url: nextApiUrl,
      api_key: profile.api_key,
      extra_settings: profile.extra_settings,
    });
    setIsBuiltinProfile(Boolean(profile.is_builtin));
    setEditing(false);
    setInlineError("");
    setTestResult(null);
  }, []);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setInlineError("");
    try {
      const data = await getPlatformConfig();
      setConfig(data);
      setPlatformType(data.platform_type as PlatformType);
      const nextAuthType = fromBackendAuthType(data.extra_settings?.auth_type);
      setAuthType(nextAuthType);
      setApiUrl(data.api_url);
      setApiKey("");
      setIsMockPreset(
        isMockPresetConfig({
          platformType: data.platform_type as PlatformType,
          authType: nextAuthType,
          apiUrl: data.api_url,
        }),
      );
      setIsBuiltinProfile(data.platform_type === "unconfigured");
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
    const validationError = validate({
      platformType,
      apiUrl,
      apiKey,
      authType,
      isMockPreset,
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
        isMockPreset,
      });
      const saved = await createPlatformConfig(payload);
      setConfig(saved);
      setEditing(false);
      setApiKey("");
      const savedAuthType = fromBackendAuthType(saved.extra_settings?.auth_type);
      setAuthType(savedAuthType);
      setApiUrl(saved.api_url);
      setIsMockPreset(
        isMockPresetConfig({
          platformType: saved.platform_type as PlatformType,
          authType: savedAuthType,
          apiUrl: saved.api_url,
        }),
      );
      setProfileRefreshKey((k) => k + 1);
      onNotify("success", "Platform config updated.");
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setSaving(false);
    }
  }, [apiKey, apiUrl, authType, isMockPreset, onNotify, platformType]);

  const handleReset = useCallback(async () => {
    const confirmed = window.confirm(
      "Reset platform configuration to unconfigured? This will disconnect from your current platform.",
    );
    if (!confirmed) return;

    setSaving(true);
    setInlineError("");
    setTestResult(null);
    try {
      await resetPlatformConfig();
      await loadConfig();
      setEditing(false);
      setProfileRefreshKey((k) => k + 1);
      setIsBuiltinProfile(true);
      onNotify("success", "Platform config reset to unconfigured.");
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
      apiKey: isUnconfigured ? "" : apiKey,
      authType,
      isMockPreset,
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
        isMockPreset,
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
  }, [
    apiKey,
    apiUrl,
    authType,
    isMockPreset,
    isUnconfigured,
    onNotify,
    platformType,
  ]);

  const handleUseMockPreset = useCallback(() => {
    if (!editing || saving || formLocked) {
      return;
    }
    setPlatformType("custom_rest");
    setAuthType("none");
    setApiUrl(MOCK_PRESET_URL);
    setApiKey("");
    setIsMockPreset(true);
    setInlineError("");
    setTestResult(null);
  }, [editing, formLocked, saving]);

  const handleUseApiMode = useCallback(() => {
    if (!editing || saving || formLocked) {
      return;
    }
    setIsMockPreset(false);
    setPlatformType("custom_rest");
    setAuthType((prev) => (prev === "none" ? "api_key" : prev));
    setApiUrl((prev) => (normalizeUrl(prev) === normalizeUrl(MOCK_PRESET_URL) ? "" : prev));
    setApiKey("");
    setInlineError("");
    setTestResult(null);
  }, [editing, formLocked, saving]);

  const handlePlatformTypeChange = useCallback((value: PlatformType) => {
    setPlatformType(value);
    if (value !== "custom_rest") {
      setIsMockPreset(false);
    }
  }, []);

  const handleProfileSwitchInternal = useCallback(
    (profileName: string, voiceReloaded: boolean) => {
      onProfileSwitch?.(profileName, voiceReloaded);
    },
    [onProfileSwitch],
  );

  return (
    <section className="space-y-3">
      <ProfileSelector
        refreshKey={profileRefreshKey}
        onProfileChange={handleProfileChange}
        onNotify={onNotify}
        onProfileSwitch={handleProfileSwitchInternal}
        onActiveProfileResolved={onActiveProfileResolved}
      />

      <header className="flex items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          {!formLocked && (
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
          )}
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
          {editing && !formLocked && !isUnconfigured && (
            <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/40">
              <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                Integration Mode
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleUseApiMode}
                  className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                  disabled={saving}
                >
                  Use API
                </button>
                <button
                  type="button"
                  onClick={handleUseMockPreset}
                  className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                  disabled={saving}
                >
                  Use Mock
                </button>
              </div>
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Adapter
              </span>
              <select
                value={platformType}
                onChange={(event) =>
                  handlePlatformTypeChange(event.target.value as PlatformType)
                }
                disabled={!editing || saving || formLocked}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="unconfigured">Unconfigured</option>
                <option value="custom_rest">REST API</option>
              </select>
            </label>

            {!isUnconfigured && (
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                  Current Mode
                </span>
                <input
                  type="text"
                  value={isMockPreset ? "Mock Preset" : "API Connection"}
                  readOnly
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                />
              </label>
            )}

            {isMockPreset && !isUnconfigured ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-900/30 dark:text-emerald-200 md:col-span-2">
                Mock preset is active. This profile uses the built-in mock endpoint with no
                authentication. Switch to <strong>Use API</strong> to edit URL and auth fields.
              </div>
            ) : (
              <>
                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    API URL
                  </span>
                  <input
                    type="url"
                    value={apiUrl}
                    onChange={(event) => setApiUrl(event.target.value)}
                    disabled={!editing || saving || formLocked || isUnconfigured}
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
                    disabled={!editing || saving || formLocked || isUnconfigured}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    <option value="api_key">API Key</option>
                    <option value="cookie">Session Cookie</option>
                    <option value="none">No Authentication</option>
                  </select>
                </label>
                {authType !== "none" && (
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
                      disabled={!editing || saving || formLocked || isUnconfigured}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                    />
                  </label>
                )}
              </>
            )}
          </div>

          {inlineError && (
            <ErrorMessage title="Platform config error" message={inlineError} />
          )}
          {testResult && <ConnectionTestResult result={testResult} />}

          <div className="mt-4 flex flex-wrap gap-2">
            {!isUnconfigured && !isMockPreset && (
              <button
                type="button"
                onClick={() => void handleTest()}
                disabled={testing || saving}
                className="btn-brand-subtle rounded-lg px-3 py-2 text-xs font-semibold"
              >
                {testing ? (
                  <span className="inline-flex items-center gap-2">
                    <svg
                      className="h-4 w-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                    >
                      <path
                        d="M21 12a9 9 0 10-9 9"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                    Testing connection to {adapterTarget}...
                  </span>
                ) : (
                  "Test Connection"
                )}
              </button>
            )}
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
