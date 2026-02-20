import { useCallback, useEffect, useMemo, useState } from "react";

import {
  activateProfile,
  createProfile,
  deleteProfile,
  listProfiles,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { ProfileMetadata } from "../../api/types";
import { useTheme } from "../common/ThemeProvider";

const PROFILE_NAME_REGEX = /^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$/;

type ProfileSelectorProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  onProfileChange: (profileName: string) => void;
  onActiveProfileResolved?: (profileName: string) => void;
  onProfileSwitched?: (profileName: string, voiceReloaded: boolean) => void;
};

export default function ProfileSelector({
  onNotify,
  onProfileChange,
  onActiveProfileResolved,
  onProfileSwitched,
}: ProfileSelectorProps) {
  const { isDark } = useTheme();
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [activeProfile, setActiveProfile] = useState("mock");
  const [selectedProfile, setSelectedProfile] = useState("mock");
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlatform, setNewPlatform] = useState("reneryo");
  const [creating, setCreating] = useState(false);
  const [nameError, setNameError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const loadProfiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listProfiles();
      setProfiles(data.profiles);
      setActiveProfile(data.active_profile);
      setSelectedProfile(data.active_profile);
      onProfileChange(data.active_profile);
      onActiveProfileResolved?.(data.active_profile);
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onNotify, onProfileChange, onActiveProfileResolved]);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  const handleSwitch = useCallback(async () => {
    if (selectedProfile === activeProfile) {
      return;
    }
    setSwitching(true);
    try {
      const result = await activateProfile(selectedProfile);
      setActiveProfile(result.active_profile);
      onNotify("success", `Switched to profile "${result.active_profile}"`);
      onProfileChange(result.active_profile);
      onActiveProfileResolved?.(result.active_profile);
      onProfileSwitched?.(
        result.active_profile,
        result.voice_reloaded ?? false,
      );
      await loadProfiles();
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSwitching(false);
    }
  }, [
    selectedProfile,
    activeProfile,
    onNotify,
    onProfileChange,
    onActiveProfileResolved,
    onProfileSwitched,
    loadProfiles,
  ]);

  const handleDelete = useCallback(
    async (name: string) => {
      try {
        const result = await deleteProfile(name);
        onNotify("success", result.message);
        setConfirmDelete(null);
        if (result.active_profile !== activeProfile) {
          setActiveProfile(result.active_profile);
          onProfileChange(result.active_profile);
          onActiveProfileResolved?.(result.active_profile);
        }
        setSelectedProfile(result.active_profile);
        await loadProfiles();
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      }
    },
    [activeProfile, onNotify, onProfileChange, onActiveProfileResolved, loadProfiles],
  );

  const handleCreate = useCallback(async () => {
    const trimmed = newName.trim().toLowerCase();
    if (!PROFILE_NAME_REGEX.test(trimmed)) {
      setNameError(
        "2-50 chars, lowercase alphanumeric + hyphens, no leading/trailing hyphen.",
      );
      return;
    }
    setCreating(true);
    setNameError("");
    try {
      await createProfile({
        name: trimmed,
        platform_type: newPlatform,
        api_url: "",
        api_key: "",
        extra_settings: {},
      });
      onNotify("success", `Profile "${trimmed}" created`);
      setShowNewForm(false);
      setNewName("");
      setNewPlatform("reneryo");
      await loadProfiles();
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setNameError(message);
      onNotify("error", message);
    } finally {
      setCreating(false);
    }
  }, [newName, newPlatform, onNotify, loadProfiles]);

  const selectedMeta = profiles.find((p) => p.name === selectedProfile);
  const isSelectedActive = selectedProfile === activeProfile;
  const isSelectedBuiltin = selectedMeta?.is_builtin ?? false;

  const badgeClasses = useMemo(
    () => (isActive: boolean, isBuiltin: boolean) => {
      if (isActive) {
        return isDark
          ? "bg-emerald-900/60 text-emerald-300 border-emerald-600"
          : "bg-emerald-50 text-emerald-700 border-emerald-200";
      }
      if (isBuiltin) {
        return isDark
          ? "bg-slate-700 text-slate-300 border-slate-600"
          : "bg-slate-100 text-slate-600 border-slate-300";
      }
      return "";
    },
    [isDark],
  );

  if (loading) {
    return (
      <div
        data-testid="profile-loading"
        className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200"
      >
        Loading profiles…
      </div>
    );
  }

  return (
    <div data-testid="profile-selector" className="mb-4 space-y-3">
      {/* Profile dropdown + controls */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="block flex-1 min-w-[200px]">
          <span className="mb-1 block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Active Profile
          </span>
          <select
            data-testid="profile-dropdown"
            value={selectedProfile}
            onChange={(e) => {
              setSelectedProfile(e.target.value);
              onProfileChange(e.target.value);
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
                {p.is_builtin ? " (Built-in)" : ""}
                {p.is_active ? " ● Active" : ""}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2">
          {/* Badges */}
          {isSelectedBuiltin && (
            <span
              data-testid="builtin-badge"
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${badgeClasses(false, true)}`}
            >
              <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                  clipRule="evenodd"
                />
              </svg>
              Built-in
            </span>
          )}
          {isSelectedActive && (
            <span
              data-testid="active-badge"
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${badgeClasses(true, false)}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Active
            </span>
          )}

          {/* Switch button */}
          {!isSelectedActive && (
            <button
              type="button"
              data-testid="switch-button"
              onClick={() => void handleSwitch()}
              disabled={switching}
              className="btn-brand-primary rounded-lg px-3 py-1.5 text-xs font-semibold"
            >
              {switching ? "Switching…" : "Switch"}
            </button>
          )}

          {/* New Profile button */}
          <button
            type="button"
            data-testid="new-profile-button"
            onClick={() => setShowNewForm((prev) => !prev)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
              isDark
                ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            New Profile
          </button>

          {/* Delete button (custom profiles only) */}
          {!isSelectedBuiltin && (
            <>
              {confirmDelete === selectedProfile ? (
                <span className="inline-flex items-center gap-1">
                  <button
                    type="button"
                    data-testid="confirm-delete-button"
                    onClick={() => void handleDelete(selectedProfile)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                      isDark
                        ? "border-rose-400 bg-rose-950/60 text-rose-200 hover:bg-rose-900/60"
                        : "border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100"
                    }`}
                  >
                    Confirm Delete
                  </button>
                  <button
                    type="button"
                    data-testid="cancel-delete-button"
                    onClick={() => setConfirmDelete(null)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                      isDark
                        ? "border-slate-500 bg-slate-700 text-slate-100"
                        : "border-slate-300 bg-white text-slate-700"
                    }`}
                  >
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  data-testid="delete-button"
                  onClick={() => setConfirmDelete(selectedProfile)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                    isDark
                      ? "border-rose-400 bg-rose-950/60 text-rose-200 hover:bg-rose-900/60"
                      : "border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100"
                  }`}
                >
                  Delete
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* New Profile Form */}
      {showNewForm && (
        <div
          data-testid="new-profile-form"
          className={`rounded-lg border p-4 ${
            isDark
              ? "border-slate-600 bg-slate-800/60"
              : "border-slate-200 bg-slate-50"
          }`}
        >
          <div className="flex flex-wrap items-end gap-3">
            <label className="block flex-1 min-w-[160px]">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Profile Name
              </span>
              <input
                type="text"
                data-testid="new-profile-name"
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value);
                  setNameError("");
                }}
                placeholder="my-reneryo-profile"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <label className="block min-w-[140px]">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Platform
              </span>
              <select
                data-testid="new-profile-platform"
                value={newPlatform}
                onChange={(e) => setNewPlatform(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="reneryo">RENERYO</option>
                <option value="custom_rest">Custom REST</option>
              </select>
            </label>
            <button
              type="button"
              data-testid="create-profile-button"
              onClick={() => void handleCreate()}
              disabled={creating}
              className="btn-brand-primary rounded-lg px-3 py-2 text-xs font-semibold"
            >
              {creating ? "Creating…" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNewForm(false);
                setNameError("");
                setNewName("");
              }}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                isDark
                  ? "border-slate-500 bg-slate-700 text-slate-100"
                  : "border-slate-300 bg-white text-slate-700"
              }`}
            >
              Cancel
            </button>
          </div>
          {nameError && (
            <p data-testid="name-error" className="mt-2 text-xs text-rose-600 dark:text-rose-400">
              {nameError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
