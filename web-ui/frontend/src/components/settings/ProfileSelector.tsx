import { useCallback, useEffect, useState } from "react";

import {
  activateProfile,
  createProfile as apiCreateProfile,
  deleteProfile as apiDeleteProfile,
  getProfile,
  listProfiles,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  CreateProfileRequest,
  PlatformType,
  ProfileDetailResponse,
  ProfileMetadata,
} from "../../api/types";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";

export type ProfileSelectorProps = {
  refreshKey?: number;
  onProfileChange: (config: ProfileDetailResponse) => void;
  onNotify: (type: "success" | "error", message: string) => void;
  onProfileSwitch?: (profileName: string, voiceReloaded: boolean) => void;
  onActiveProfileResolved?: (profileName: string) => void;
};

const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

function validateProfileName(name: string): string {
  const trimmed = name.trim();
  if (trimmed.length < 2 || trimmed.length > 50) {
    return "Profile name must be 2\u201350 characters.";
  }
  if (!PROFILE_NAME_RE.test(trimmed)) {
    return "Only lowercase letters, numbers, and hyphens. Must start and end with a letter or number.";
  }
  return "";
}

export default function ProfileSelector({
  refreshKey = 0,
  onProfileChange,
  onNotify,
  onProfileSwitch,
  onActiveProfileResolved,
}: ProfileSelectorProps) {
  const { isDark } = useTheme();
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [activeProfileName, setActiveProfileName] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlatformType, setNewPlatformType] =
    useState<PlatformType>("reneryo");
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadProfiles = useCallback(async () => {
    setLoadingProfiles(true);
    try {
      const data = await listProfiles();
      const sorted = [...data.profiles].sort((a, b) => {
        if (a.is_builtin && !b.is_builtin) return -1;
        if (!a.is_builtin && b.is_builtin) return 1;
        return a.name.localeCompare(b.name);
      });
      setProfiles(sorted);
      setActiveProfileName(data.active_profile);
      onActiveProfileResolved?.(data.active_profile);
      setSelectedName((prev) => {
        if (!prev || !sorted.some((p) => p.name === prev)) {
          return data.active_profile;
        }
        return prev;
      });
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoadingProfiles(false);
    }
  }, [onActiveProfileResolved, onNotify]);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles, refreshKey]);

  const selectProfile = useCallback(
    async (name: string) => {
      setSelectedName(name);
      try {
        const config = await getProfile(name);
        onProfileChange(config);
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      }
    },
    [onProfileChange, onNotify],
  );

  const switchToProfile = useCallback(async (targetName: string) => {
    if (!targetName || targetName === activeProfileName) return;
    setSwitching(true);
    try {
      const activation = await activateProfile(targetName);
      const profile = await getProfile(targetName);
      setActiveProfileName(targetName);
      setSelectedName(targetName);
      onProfileChange(profile);
      onProfileSwitch?.(targetName, Boolean(activation.voice_reloaded));
      onNotify("success", `Switched to profile \u201c${targetName}\u201d.`);
      await loadProfiles();
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSwitching(false);
    }
  }, [
    activeProfileName,
    onProfileChange,
    onProfileSwitch,
    onNotify,
    loadProfiles,
  ]);

  const handleSwitch = useCallback(async () => {
    if (selectedName === activeProfileName) return;
    await switchToProfile(selectedName);
  }, [
    selectedName,
    activeProfileName,
    switchToProfile,
  ]);

  const handleSelectAndSwitch = useCallback(async (name: string) => {
    await selectProfile(name);
    if (name !== activeProfileName) {
      await switchToProfile(name);
    }
  }, [
    activeProfileName,
    selectProfile,
    switchToProfile,
  ]);

  const handleCreate = useCallback(async () => {
    const validationError = validateProfileName(newName);
    if (validationError) {
      onNotify("error", validationError);
      return;
    }
    setCreating(true);
    try {
      const trimmed = newName.trim();
      const payload: CreateProfileRequest = {
        name: trimmed,
        platform_type: newPlatformType,
        api_url: "",
        api_key: "",
        extra_settings: {},
      };
      await apiCreateProfile(payload);
      setNewName("");
      setShowNewForm(false);
      onNotify("success", `Profile \u201c${trimmed}\u201d created.`);
      await loadProfiles();
      await selectProfile(trimmed);
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setCreating(false);
    }
  }, [newName, newPlatformType, onNotify, loadProfiles, selectProfile]);

  const handleDelete = useCallback(async () => {
    const profile = profiles.find((p) => p.name === selectedName);
    if (!profile || profile.is_builtin) return;
    if (
      !window.confirm(
        `Delete profile \u201c${selectedName}\u201d? This cannot be undone.`,
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      const deletedName = selectedName;
      const deletedWasActive = deletedName === activeProfileName;
      await apiDeleteProfile(deletedName);
      onNotify("success", `Profile \u201c${deletedName}\u201d deleted.`);

      const refreshed = await listProfiles();
      const sorted = [...refreshed.profiles].sort((a, b) => {
        if (a.is_builtin && !b.is_builtin) return -1;
        if (!a.is_builtin && b.is_builtin) return 1;
        return a.name.localeCompare(b.name);
      });
      setProfiles(sorted);
      setActiveProfileName(refreshed.active_profile);
      setSelectedName((prev) => {
        if (!prev || prev === deletedName || !sorted.some((p) => p.name === prev)) {
          return refreshed.active_profile || sorted[0]?.name || "";
        }
        return prev;
      });

      if (deletedWasActive) {
        const fallbackName = refreshed.active_profile || sorted[0]?.name;
        if (fallbackName) {
          await selectProfile(fallbackName);
        }
      }
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setDeleting(false);
    }
  }, [selectedName, activeProfileName, profiles, onNotify, selectProfile]);

  const selectedProfile = profiles.find((p) => p.name === selectedName);
  const isSelectedActive = selectedName === activeProfileName;
  const isSelectedBuiltin = selectedProfile?.is_builtin ?? false;
  const busy = switching || deleting || creating;

  if (loadingProfiles && profiles.length === 0) {
    return (
      <div className="mb-3" data-testid="profile-selector-loading">
        <LoadingSpinner label="Loading profiles\u2026" size="sm" />
      </div>
    );
  }

  if (!loadingProfiles && profiles.length === 0) {
    return null;
  }

  return (
    <div className="mb-4 space-y-3" data-testid="profile-selector-section">
      <div className="flex flex-wrap items-end gap-2">
        <label className="block min-w-[200px] flex-1">
          <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
            Profile
          </span>
          <select
            value={selectedName}
            onChange={(e) => void handleSelectAndSwitch(e.target.value)}
            disabled={busy}
            className={`w-full rounded-lg border px-3 py-2 text-sm ${
              isDark
                ? "border-slate-600 bg-slate-800 text-slate-100"
                : "border-slate-300 bg-white text-slate-900"
            }`}
            data-testid="profile-dropdown"
          >
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
                {p.is_builtin ? " \uD83D\uDD12 Built-in" : ""}
                {p.is_active ? " \u25CF Active" : ""}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void handleSwitch()}
          disabled={isSelectedActive || busy}
          className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-colors ${
            isSelectedActive || busy ? "cursor-not-allowed opacity-50" : ""
          } ${
            isDark
              ? "border-emerald-500 bg-emerald-950/60 text-emerald-200 hover:bg-emerald-900/60"
              : "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
          }`}
          data-testid="profile-switch-btn"
        >
          {switching ? "Switching\u2026" : "Switch"}
        </button>

        <button
          type="button"
          onClick={() => setShowNewForm((v) => !v)}
          disabled={busy}
          className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
            isDark
              ? "border-sky-500 bg-sky-950/60 text-sky-200 hover:bg-sky-900/60"
              : "border-sky-300 bg-sky-50 text-sky-700 hover:bg-sky-100"
          }`}
          data-testid="profile-new-btn"
        >
          New Profile
        </button>

        {!isSelectedBuiltin && (
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={busy}
            className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
              isDark
                ? "border-rose-400 bg-rose-950/60 text-rose-200 hover:bg-rose-900/60"
                : "border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100"
            }`}
            data-testid="profile-delete-btn"
          >
            {deleting ? "Deleting\u2026" : "Delete"}
          </button>
        )}
      </div>

      {selectedProfile && (
        <div className="flex items-center gap-2" data-testid="profile-badges">
          {isSelectedActive && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
              data-testid="badge-active"
            >
              <span
                className="h-1.5 w-1.5 rounded-full bg-emerald-500"
                aria-hidden="true"
              />
              Active
            </span>
          )}
          {isSelectedBuiltin && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300"
              data-testid="badge-builtin"
            >
              <svg
                viewBox="0 0 24 24"
                className="h-3 w-3"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0110 0v4" />
              </svg>
              Built-in
            </span>
          )}
        </div>
      )}

      {showNewForm && (
        <div
          className={`rounded-lg border p-3 ${
            isDark
              ? "border-slate-600 bg-slate-800/60"
              : "border-slate-200 bg-slate-50"
          }`}
          data-testid="new-profile-form"
        >
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-[160px] flex-1">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Profile Name
              </span>
              <input
                type="text"
                value={newName}
                onChange={(e) =>
                  setNewName(
                    e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                  )
                }
                placeholder="my-custom-profile"
                maxLength={50}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${
                  isDark
                    ? "border-slate-600 bg-slate-700 text-slate-100"
                    : "border-slate-300 bg-white text-slate-900"
                }`}
                data-testid="profile-new-name"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                Platform
              </span>
              <select
                value={newPlatformType}
                onChange={(e) =>
                  setNewPlatformType(e.target.value as PlatformType)
                }
                className={`rounded-lg border px-3 py-2 text-sm ${
                  isDark
                    ? "border-slate-600 bg-slate-800 text-slate-100"
                    : "border-slate-300 bg-white text-slate-900"
                }`}
                data-testid="profile-new-platform"
              >
                <option value="reneryo">RENERYO</option>
                <option value="custom_rest">Custom REST</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={creating}
              className="btn-brand-primary rounded-lg px-3 py-2 text-xs font-semibold"
              data-testid="profile-create-btn"
            >
              {creating ? "Creating\u2026" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNewForm(false);
                setNewName("");
              }}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                isDark
                  ? "border-slate-500 bg-slate-700 text-slate-100"
                  : "border-slate-300 bg-white text-slate-700"
              }`}
              data-testid="profile-new-cancel"
            >
              Cancel
            </button>
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            Lowercase letters, numbers, and hyphens only. 2\u201350 characters.
          </p>
        </div>
      )}
    </div>
  );
}
