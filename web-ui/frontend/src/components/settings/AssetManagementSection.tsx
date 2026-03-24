import { useCallback, useEffect, useState } from "react";

import {
  getConfiguredAssets,
  saveConfiguredAssets,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { PlatformType } from "../../api/types";
import AssetManagementRows from "./AssetManagementRows";
import {
  createEmptyRow,
  toPayload,
  toRows,
  type AssetRow,
} from "./assetManagementSection.helpers";

type NotifyFn = (type: "success" | "error", message: string) => void;

type AssetManagementSectionProps = {
  onNotify?: NotifyFn;
  refreshKey?: number;
  activeProfile?: string;
  platformType?: PlatformType | null;
  mode?: "settings" | "wizard";
  onComplete?: () => void;
  onSkip?: () => void;
};

export default function AssetManagementSection({
  onNotify,
  refreshKey = 0,
  activeProfile,
  platformType,
  mode = "settings",
  onComplete,
  onSkip,
}: AssetManagementSectionProps) {
  const [resolvedPlatform, setResolvedPlatform] = useState<PlatformType>(
    platformType ?? "unconfigured",
  );
  const [rows, setRows] = useState<AssetRow[]>([createEmptyRow()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const isUnconfigured = resolvedPlatform === "unconfigured";

  const resolvePlatform = useCallback(() => {
    if (platformType) {
      setResolvedPlatform(platformType);
      return;
    }
    setResolvedPlatform("custom_rest");
  }, [platformType]);

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const current = await getConfiguredAssets();
      setRows(toRows(current.asset_mappings));
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    resolvePlatform();
  }, [activeProfile, refreshKey, resolvePlatform]);

  useEffect(() => {
    void loadMappings();
  }, [activeProfile, loadMappings, refreshKey, resolvedPlatform]);

  const handleChange = useCallback(
    <K extends keyof AssetRow>(index: number, key: K, value: AssetRow[K]) => {
      setRows((prev) =>
        prev.map((row, rowIndex) =>
          rowIndex === index ? { ...row, [key]: value } : row,
        ),
      );
    },
    [],
  );

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, createEmptyRow()]);
  }, []);

  const deleteRow = useCallback((index: number) => {
    setRows((prev) => {
      const next = prev.filter((_, rowIndex) => rowIndex !== index);
      return next.length > 0 ? next : [createEmptyRow()];
    });
  }, []);

  const save = useCallback(async () => {
    if (isUnconfigured) {
      if (mode === "wizard" && onComplete) {
        onComplete();
      }
      return;
    }

    setSaving(true);
    setError("");
    try {
      const payload = toPayload(rows, resolvedPlatform);
      await saveConfiguredAssets(payload);
      onNotify?.("success", "Assets saved.");
      if (mode === "wizard" && onComplete) {
        onComplete();
      }
    } catch (err: unknown) {
      const message = toFriendlyErrorMessage(err);
      setError(message);
      onNotify?.("error", message);
    } finally {
      setSaving(false);
    }
  }, [isUnconfigured, mode, onComplete, onNotify, resolvedPlatform, rows]);

  return (
    <section className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-sm text-slate-600 dark:text-slate-300">
          {isUnconfigured
            ? "These are demo assets. Connect a real platform to configure your assets."
            : "Manage asset mappings used by voice and KPI queries."}
        </p>
        <div className="flex items-center gap-2">
          {!isUnconfigured && (
            <button
              type="button"
              className="btn-brand-subtle rounded-lg px-3 py-2 text-sm font-semibold"
              onClick={addRow}
            >
              Add Asset
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
          Loading asset configuration...
        </div>
      ) : null}

      <AssetManagementRows
        rows={rows}
        onChange={handleChange}
        onDelete={deleteRow}
      />

      <div className="flex flex-wrap gap-2">
        {mode === "wizard" && (
          <button
            type="button"
            className="btn-brand-subtle rounded-lg px-4 py-2 text-sm font-semibold"
            onClick={onSkip}
          >
            Skip
          </button>
        )}
        <button
          type="button"
          className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => void save()}
          disabled={saving || loading}
        >
          {saving
            ? "Saving..."
            : mode === "wizard"
              ? isUnconfigured
                ? "Continue"
                : "Save Mapping & Continue"
              : "Save Assets"}
        </button>
      </div>
    </section>
  );
}
