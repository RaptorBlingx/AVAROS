import { useCallback, useEffect, useState } from "react";
import type {
  ConnectionTestResponse,
  ProfileMetadata,
  SystemStatusResponse,
} from "../../api/types";
import { listProfiles, createProfile, activateProfile, getProfile } from "../../api/client";
import ConnectionTestResult from "../common/ConnectionTestResult";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import Tooltip from "../common/Tooltip";

type AuthType = "api_key" | "cookie" | "none";

const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

type PlatformSetupStepProps = {
  status: SystemStatusResponse | null;
  statusLoading: boolean;
  statusError: string;
  authType: AuthType;
  apiUrl: string;
  apiKey: string;
  formError: string;
  testResult: ConnectionTestResponse | null;
  testError: string;
  isTesting: boolean;
  isSaving: boolean;
  selectedProfile: string;
  onProfileChange: (profileName: string) => void;
  onAuthTypeChange: (value: AuthType) => void;
  onApiUrlChange: (value: string) => void;
  onApiKeyChange: (value: string) => void;
  onTestConnection: () => void;
  onSaveAndContinue: () => void;
};

export default function PlatformSetupStep({
  status,
  statusLoading,
  statusError,
  authType,
  apiUrl,
  apiKey,
  formError,
  testResult,
  testError,
  isTesting,
  isSaving,
  selectedProfile,
  onProfileChange,
  onAuthTypeChange,
  onApiUrlChange,
  onApiKeyChange,
  onTestConnection,
  onSaveAndContinue,
}: PlatformSetupStepProps) {

  /* ── Profile state ────────────────────────────────────────────── */
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [newProfileName, setNewProfileName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  const refreshProfiles = useCallback(async () => {
    setProfilesLoading(true);
    setProfileError("");
    try {
      const result = await listProfiles();
      setProfiles(result.profiles);
      if (!selectedProfile && result.active_profile) {
        onProfileChange(result.active_profile);
      }
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : "Failed to load profiles");
    } finally {
      setProfilesLoading(false);
    }
  }, [onProfileChange, selectedProfile]);

  useEffect(() => {
    void refreshProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Hydrate form from a profile (no activation — just loads fields) */
  const hydrateFromProfile = useCallback(
    async (name: string) => {
      try {
        const detail = await getProfile(name);
        onApiUrlChange(detail.api_url ?? "");
        const backendAuth = detail.extra_settings?.auth_type;
        if (backendAuth === "cookie") {
          onAuthTypeChange("cookie");
        } else if (backendAuth === "none") {
          onAuthTypeChange("none");
        } else {
          onAuthTypeChange("api_key");
        }
        onApiKeyChange("");
      } catch {
        // Profile may be new with no config yet — clear fields
        onApiUrlChange("");
        onAuthTypeChange("api_key");
        onApiKeyChange("");
      }
    },
    [onApiUrlChange, onAuthTypeChange, onApiKeyChange],
  );

  const handleSelectProfile = useCallback(
    async (name: string) => {
      setProfileError("");
      onProfileChange(name);
      await hydrateFromProfile(name);
    },
    [onProfileChange, hydrateFromProfile],
  );

  const handleCreateProfile = useCallback(async () => {
    const name = newProfileName.trim().toLowerCase();
    if (!name) {
      setProfileError("Profile name is required.");
      return;
    }
    if (!PROFILE_NAME_RE.test(name)) {
      setProfileError(
        "Profile name must be lowercase alphanumeric with hyphens, at least 2 characters (e.g. 'reneryo', 'humanenerdia').",
      );
      return;
    }
    if (profiles.some((p) => p.name === name)) {
      setProfileError(`Profile "${name}" already exists. Select it from the dropdown.`);
      return;
    }
    setIsCreating(true);
    setProfileError("");
    try {
      await createProfile({
        name,
        platform_type: "custom_rest",
        api_url: "http://placeholder.invalid",
        api_key: "",
        extra_settings: {},
      });
      onProfileChange(name);
      onApiUrlChange("");
      onApiKeyChange("");
      onAuthTypeChange("api_key");
      setNewProfileName("");
      setShowCreateForm(false);
      await refreshProfiles();
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : "Failed to create profile");
    } finally {
      setIsCreating(false);
    }
  }, [newProfileName, profiles, onProfileChange, onApiUrlChange, onApiKeyChange, onAuthTypeChange, refreshProfiles]);

  return (
    <section className="space-y-4">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 1 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Platform Setup
          </h2>
          <Tooltip
            content="Select or create a platform profile, then configure its API connection."
            ariaLabel="Why platform setup is needed"
          />
        </div>
        <p className="mb-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Each profile stores its own connection, assets, metrics, and linking. Configure the connection details below, then continue to asset registration.
        </p>
      </header>

      {/* ── Unified platform configuration card ─────────────────── */}
      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">

        {/* Status row */}
        {statusLoading && (
          <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading current system status..." size="sm" />
          </div>
        )}
        {!statusLoading && statusError && (
          <div className="mb-4">
            <ErrorMessage title="Status unavailable" message={statusError} />
          </div>
        )}
        {!statusLoading && !statusError && status && (
          <div className="mb-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Configured
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.configured ? "Yes" : "No"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Database
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.database_connected ? "Connected" : "Disconnected"}
              </p>
            </div>
          </div>
        )}

        {/* Profile selector */}
        <div className="space-y-4">
          <div>
            <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
              Platform Profile
            </p>
            {profilesLoading ? (
              <div className="mt-3">
                <LoadingSpinner label="Loading profiles..." size="sm" />
              </div>
            ) : (
              <div className="mt-2 space-y-3">
                <div className="flex flex-wrap items-end gap-3">
                  <label className="block flex-1">
                    <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                      Active Profile
                    </span>
                    <select
                      value={selectedProfile}
                      onChange={(e) => void handleSelectProfile(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                    >
                      {profiles.length === 0 && <option value="">No profiles</option>}
                      {profiles.map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.name}{p.is_active ? " (active)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="btn-brand-subtle rounded-lg px-3 py-2 text-xs font-semibold"
                    onClick={() => setShowCreateForm(!showCreateForm)}
                  >
                    {showCreateForm ? "Cancel" : "+ New Profile"}
                  </button>
                </div>

                {showCreateForm && (
                  <div className="flex flex-wrap items-end gap-2 rounded-lg border border-sky-200 bg-sky-50/50 p-3 dark:border-sky-500/30 dark:bg-sky-900/20">
                    <label className="block flex-1">
                      <span className="mb-1 block text-xs font-semibold text-slate-700 dark:text-slate-300">
                        New Profile Name
                      </span>
                      <input
                        type="text"
                        value={newProfileName}
                        onChange={(e) => setNewProfileName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                        placeholder="e.g. humanenerdia"
                        maxLength={40}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void handleCreateProfile();
                          }
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      className="btn-brand-primary rounded-lg px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={() => void handleCreateProfile()}
                      disabled={isCreating || !newProfileName.trim()}
                    >
                      {isCreating ? "Creating..." : "Create"}
                    </button>
                  </div>
                )}

                {profileError && (
                  <p className="m-0 text-xs text-rose-700 dark:text-rose-300">{profileError}</p>
                )}
              </div>
            )}
          </div>

          {/* Divider */}
          <hr className="border-slate-200 dark:border-slate-700" />

          {/* Connection fields — always visible */}
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                API URL
              </span>
              <input
                type="url"
                value={apiUrl}
                onChange={(event) => onApiUrlChange(event.target.value)}
                placeholder="https://api.example.com"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                Auth Type
              </span>
              <select
                value={authType}
                onChange={(event) =>
                  onAuthTypeChange(event.target.value as AuthType)
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="api_key">API Key</option>
                <option value="cookie">Session Cookie</option>
                <option value="none">No Authentication</option>
              </select>
            </label>

            {authType !== "none" && (
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {authType === "cookie" ? "Session Cookie Value" : "API Key"}
                </span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => onApiKeyChange(event.target.value)}
                  placeholder={
                    authType === "cookie"
                      ? "Paste session cookie (S=...)"
                      : "Enter your API key"
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
              </label>
            )}
          </div>
        </div>

        {/* Errors */}
        {formError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {formError}
          </div>
        )}

        {testError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {testError}
          </div>
        )}

        {testResult && <ConnectionTestResult result={testResult} />}

        {/* Action buttons */}
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onTestConnection}
            disabled={isTesting || isSaving}
          >
            {isTesting ? (
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
                Testing connection...
              </span>
            ) : (
              "Test Connection"
            )}
          </button>
          <button
            type="button"
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onSaveAndContinue}
            disabled={isSaving || isTesting}
          >
            {isSaving ? "Saving..." : "Save & Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
