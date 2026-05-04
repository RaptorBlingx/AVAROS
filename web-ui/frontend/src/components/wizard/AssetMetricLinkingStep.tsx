import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getConfiguredAssets,
  listMetricMappings,
  saveConfiguredAssets,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  AssetMappingItem,
  CanonicalMetricName,
  MetricMapping,
} from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import Tooltip from "../common/Tooltip";
import { METRIC_OPTIONS } from "../common/metricMapping";
import { loadWizardPreset } from "./wizardPreset";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type AssetMetricLinkingStepProps = {
  onComplete: () => void;
  onSkip?: () => void;
  mode?: "wizard" | "settings";
  profileName?: string;
};

/** One row in the linking matrix: one asset's resource IDs per metric. */
type AssetLinkRow = {
  assetId: string;
  displayName: string;
  /** metric_name → resource_id  (editable by user) */
  resources: Record<string, string>;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function metricLabel(name: string): string {
  const match = METRIC_OPTIONS.find((o) => o.value === name);
  return match?.label ?? name;
}

/** True when at least one endpoint template uses a {resource_id} placeholder. */
function anyTemplateNeedsResourceId(mappings: MetricMapping[]): boolean {
  return mappings.some(
    (m) =>
      m.endpoint.includes("{resource_id}") ||
      m.endpoint.includes("{resource_uuid}"),
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AssetMetricLinkingStep({
  onComplete,
  onSkip,
  mode = "wizard",
  profileName,
}: AssetMetricLinkingStepProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [assets, setAssets] = useState<Record<string, AssetMappingItem>>({});
  const [mappedMetrics, setMappedMetrics] = useState<CanonicalMetricName[]>([]);
  const [rows, setRows] = useState<AssetLinkRow[]>([]);
  const [needsLinking, setNeedsLinking] = useState(false);

  /* ---------------------------------------------------------------- */
  /*  Load existing data                                               */
  /* ---------------------------------------------------------------- */

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [assetResponse, metricList] = await Promise.all([
        getConfiguredAssets(),
        listMetricMappings(),
      ]);

      const assetMap = assetResponse.asset_mappings ?? {};
      setAssets(assetMap);

      const metricNames = metricList.map(
        (m: MetricMapping) => m.canonical_metric,
      );
      setMappedMetrics(metricNames);

      // Decide if linking is needed: templates use {resource_id} placeholders
      setNeedsLinking(anyTemplateNeedsResourceId(metricList));

      // Build linking rows from existing assets
      const assetIds = Object.keys(assetMap);
      const initialRows: AssetLinkRow[] = assetIds.map((assetId) => {
        const mapping = assetMap[assetId] ?? {};
        const existingResources = mapping.metric_resources ?? {};
        const resources: Record<string, string> = {};
        for (const metric of metricNames) {
          resources[metric] = existingResources[metric] ?? "";
        }
        return {
          assetId,
          displayName:
            (mapping.display_name ?? "").trim() || assetId,
          resources,
        };
      });
      setRows(initialRows);
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  /* ---------------------------------------------------------------- */
  /*  Handlers                                                         */
  /* ---------------------------------------------------------------- */

  const updateResource = useCallback(
    (assetId: string, metric: string, value: string) => {
      setRows((prev) =>
        prev.map((row) =>
          row.assetId === assetId
            ? {
                ...row,
                resources: { ...row.resources, [metric]: value },
              }
            : row,
        ),
      );
    },
    [],
  );

  const autoFillAssetId = useCallback(() => {
    setRows((prev) =>
      prev.map((row) => {
        const filled: Record<string, string> = {};
        for (const [metric, existing] of Object.entries(row.resources)) {
          filled[metric] = existing || row.assetId;
        }
        return { ...row, resources: filled };
      }),
    );
  }, []);

  const [presetLoading, setPresetLoading] = useState(false);
  const [presetError, setPresetError] = useState("");

  const loadPreset = useCallback(async () => {
    setPresetLoading(true);
    setPresetError("");
    try {
      const preset = await loadWizardPreset(profileName);
      setRows((prev) =>
        prev.map((row) => {
          const presetLinking = preset.linking[row.assetId];
          if (!presetLinking) {
            return row;
          }
          const filled: Record<string, string> = {};
          for (const metric of Object.keys(row.resources)) {
            filled[metric] = presetLinking[metric] ?? row.resources[metric] ?? "";
          }
          return { ...row, resources: filled };
        }),
      );
    } catch (err: unknown) {
      setPresetError(err instanceof Error ? err.message : "Failed to load preset.");
    } finally {
      setPresetLoading(false);
    }
  }, [profileName]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError("");
    try {
      // Merge updated metric_resources into existing asset mappings
      const merged: Record<string, AssetMappingItem> = {};
      for (const row of rows) {
        const existing = assets[row.assetId] ?? {};
        const cleanResources: Record<string, string> = {};
        for (const [metric, resourceId] of Object.entries(row.resources)) {
          const trimmed = resourceId.trim();
          if (trimmed) {
            cleanResources[metric] = trimmed;
          }
        }
        merged[row.assetId] = {
          ...existing,
          metric_resources: cleanResources,
        };
      }
      // Include any assets that aren't in rows (shouldn't happen, but safe)
      for (const [assetId, mapping] of Object.entries(assets)) {
        if (!merged[assetId]) {
          merged[assetId] = mapping;
        }
      }

      await saveConfiguredAssets(merged);
      onComplete();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [assets, onComplete, rows]);

  /* ---------------------------------------------------------------- */
  /*  Derived state                                                    */
  /* ---------------------------------------------------------------- */

  const hasAssets = rows.length > 0;
  const hasMetrics = mappedMetrics.length > 0;

  const linkingStats = useMemo(() => {
    let filled = 0;
    let total = 0;
    for (const row of rows) {
      for (const metric of mappedMetrics) {
        total++;
        if ((row.resources[metric] ?? "").trim()) {
          filled++;
        }
      }
    }
    return { filled, total };
  }, [mappedMetrics, rows]);

  /* ---------------------------------------------------------------- */
  /*  Skip-able conditions                                             */
  /* ---------------------------------------------------------------- */

  // If no assets or no metrics, user can skip
  // If endpoints don't use {resource_id}, linking is optional
  const canSkip = !hasAssets || !hasMetrics || !needsLinking;

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  if (loading) {
    return <LoadingSpinner label="Loading assets and metrics…" />;
  }

  return (
    <section className="space-y-6">
      {/* Header */}
      {mode === "wizard" && (
      <div className="card-brand rounded-xl p-6">
        <p className="brand-step-label mb-1 text-xs font-bold uppercase tracking-wider">
          Step 4 of 7
        </p>
        <h2 className="brand-heading m-0 text-2xl font-bold">
          Asset–Metric Linking{" "}
          <Tooltip
            content="Connect each asset to its platform-specific resource IDs so AVAROS knows how to fetch data for each device."
            ariaLabel="Why asset-metric linking is needed"
          />
        </h2>
        <p className="brand-subtext m-0 mt-2 text-sm">
          Map each registered asset to the resource identifiers your platform
          uses. This allows endpoint templates like{" "}
          <code className="rounded bg-slate-700/50 px-1.5 py-0.5 text-xs text-cyan-300">
            {"{resource_id}"}
          </code>{" "}
          to resolve per-asset.
        </p>
      </div>
      )}

      {/* Error banner */}
      {error && (
        <ErrorMessage title="Asset-metric linking error" message={error} />
      )}

      {/* Empty states */}
      {!hasAssets && (
        <div className="card-brand rounded-xl p-6 text-center">
          <p className="m-0 text-sm text-slate-400">
            No assets registered yet. Go back to Step 2 to register assets, or
            skip this step.
          </p>
        </div>
      )}

      {hasAssets && !hasMetrics && (
        <div className="card-brand rounded-xl p-6 text-center">
          <p className="m-0 text-sm text-slate-400">
            No metric mappings configured yet. Go back to Step 3 to add metrics,
            or skip this step.
          </p>
        </div>
      )}

      {hasAssets && hasMetrics && !needsLinking && (
        <div className="card-brand rounded-xl p-6">
          <p className="m-0 text-sm text-emerald-400">
            ✓ Your metric endpoints don&apos;t use{" "}
            <code className="text-xs">{"{resource_id}"}</code> placeholders, so
            asset-metric linking is optional. You can skip this step or add
            resource IDs for future flexibility.
          </p>
        </div>
      )}

      {/* Linking matrix */}
      {hasAssets && hasMetrics && (
        <div className="card-brand space-y-4 rounded-xl p-6">
          <div className="flex items-center justify-between">
            <h3 className="m-0 text-base font-semibold text-slate-100">
              Resource ID Matrix
            </h3>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400">
                {linkingStats.filled} / {linkingStats.total} linked
              </span>
              <button
                type="button"
                onClick={() => void loadPreset()}
                disabled={presetLoading}
                className="btn-brand-primary rounded-lg px-3 py-1.5 text-xs font-semibold"
                title="Load all resource IDs from preset file (wizard-preset-reneryo.json)"
              >
                {presetLoading ? "Loading…" : "Load Preset"}
              </button>
              <button
                type="button"
                onClick={autoFillAssetId}
                className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                title="Auto-fill empty resource IDs with the asset ID (works when asset_id = resource_id)"
              >
                Auto-fill with Asset ID
              </button>
            </div>
          </div>

          {presetError && (
            <p className="m-0 text-xs text-rose-700 dark:text-rose-300">{presetError}</p>
          )}

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-600/50">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Asset
                  </th>
                  {mappedMetrics.map((metric) => (
                    <th
                      key={metric}
                      className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-400"
                    >
                      {metricLabel(metric)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.assetId}
                    className="border-b border-slate-700/30"
                  >
                    <td className="px-3 py-2">
                      <div>
                        <p className="m-0 text-sm font-medium text-slate-200">
                          {row.displayName}
                        </p>
                        <p className="m-0 text-[10px] text-slate-500">
                          {row.assetId}
                        </p>
                      </div>
                    </td>
                    {mappedMetrics.map((metric) => (
                      <td key={metric} className="px-3 py-2">
                        <input
                          type="text"
                          value={row.resources[metric] ?? ""}
                          onChange={(e) =>
                            updateResource(
                              row.assetId,
                              metric,
                              e.target.value,
                            )
                          }
                          placeholder="resource ID"
                          className="w-full min-w-[180px] rounded-lg border border-slate-600 bg-slate-800 px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {needsLinking && linkingStats.filled === 0 && (
            <p className="m-0 text-xs font-medium text-amber-400">
              ⚠ Your endpoint templates use{" "}
              <code className="text-xs">{"{resource_id}"}</code> —
              queries will fail unless you link at least one resource per asset.
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving || (!hasAssets || !hasMetrics)}
          className="btn-brand-primary rounded-lg px-5 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? "Saving…" : mode === "settings" ? "Save Linking" : "Save Linking & Continue"}
        </button>
        {onSkip && (
        <button
          type="button"
          onClick={onSkip}
          className="btn-brand-subtle rounded-lg px-5 py-2 text-sm font-semibold"
        >
          {canSkip ? "Skip" : "Skip for Now"}
        </button>
        )}
      </div>
    </section>
  );
}
