import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  discoverAssets,
  getAssetLinkingSummary,
  getConfiguredAssets,
  getPlatformConfig,
  saveConfiguredAssets,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  AssetDiscoveryResponse,
  AssetLinkingItem,
  AssetLinkingSummaryResponse,
  AssetRecord,
  PlatformType,
} from "../../api/types";
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
  const navigate = useNavigate();
  const [resolvedPlatform, setResolvedPlatform] = useState<PlatformType>(
    platformType ?? "mock",
  );
  const [rows, setRows] = useState<AssetRow[]>([createEmptyRow()]);
  const [discovery, setDiscovery] = useState<AssetDiscoveryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [discoveryNotice, setDiscoveryNotice] = useState("");
  const [reneryoSummary, setReneryoSummary] =
    useState<AssetLinkingSummaryResponse | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  const isMock = resolvedPlatform === "mock";
  const isCustomRest = resolvedPlatform === "custom_rest";
  const isReneryo = resolvedPlatform === "reneryo";
  const supportsDiscover =
    discovery?.supports_discovery ?? resolvedPlatform !== "custom_rest";

  const resolvePlatform = useCallback(async () => {
    if (platformType) {
      setResolvedPlatform(platformType);
      return;
    }
    try {
      const config = await getPlatformConfig();
      setResolvedPlatform(config.platform_type);
    } catch {
      setResolvedPlatform("mock");
    }
  }, [platformType]);

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (isReneryo) {
        const summary = await getAssetLinkingSummary();
        setReneryoSummary(summary);
        return;
      }
      const current = await getConfiguredAssets();
      setRows(toRows(current.asset_mappings));
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [isReneryo]);

  const runDiscovery = useCallback(async () => {
    setDiscovering(true);
    setError("");
    setDiscoveryNotice("");
    try {
      if (isReneryo) {
        const summary = await getAssetLinkingSummary();
        setReneryoSummary(summary);
        return;
      }
      const result = await discoverAssets();
      setDiscovery(result);
      if (isReneryo && result.discovery_source !== "adapter") {
        setDiscoveryNotice(
          "Live RENERYO discovery is unavailable. Showing registered assets only.",
        );
      }
      if (isReneryo) {
        setRows((prev) => {
          const next = [...prev];
          const discoveredAssets = Array.isArray(result.assets) ? result.assets : [];
          const seuAssets =
            result.discovery_source === "adapter"
              ? discoveredAssets.filter((asset) => asset.asset_type === "seu")
              : [];
          if (next.length === 1 && !next[0].assetId.trim() && seuAssets.length > 0) {
            return seuAssets.slice(0, 5).map((asset) => ({
              rowId: `discovered-${asset.asset_id}`,
              assetId: asset.asset_id,
              displayName: asset.display_name,
              assetType: "seu",
              aliases: asset.aliases.join(", "),
              endpointTemplate: "",
              seuId: asset.asset_id,
            }));
          }
          return next;
        });
      }
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setDiscovering(false);
    }
  }, [isReneryo]);

  useEffect(() => {
    void resolvePlatform();
  }, [activeProfile, refreshKey, resolvePlatform]);

  useEffect(() => {
    void loadMappings();
  }, [activeProfile, loadMappings, refreshKey, resolvedPlatform]);

  useEffect(() => {
    void runDiscovery();
  }, [runDiscovery]);

  const seuOptions = useMemo<AssetRecord[]>(
    () => (discovery?.assets ?? []).filter((asset) => asset.asset_type === "seu"),
    [discovery],
  );
  const reneryoImportedAssets = useMemo(
    () => reneryoSummary?.imported_assets ?? [],
    [reneryoSummary],
  );
  const reneryoDiagnosticAssets = useMemo(
    () => [
      ...(reneryoSummary?.unlinked_assets ?? []),
      ...(reneryoSummary?.discovered_assets ?? []),
    ],
    [reneryoSummary],
  );
  const fullyMappedReneryoAssets = useMemo(
    () =>
      reneryoImportedAssets.filter(
        (item) => item.linked_metric_count >= item.total_metrics,
      ).length,
    [reneryoImportedAssets],
  );

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
    if (isReneryo && mode === "settings") {
      navigate("/wizard?force=1");
      return;
    }

    if (isMock) {
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
  }, [isMock, isReneryo, mode, navigate, onComplete, onNotify, resolvedPlatform, rows]);

  const renderReneryoCard = useCallback((asset: AssetLinkingItem) => {
    const statusLabel =
      asset.linked_metric_count >= asset.total_metrics
        ? "Ready"
        : asset.linked_metric_count > 0
          ? "Partial"
          : "Missing";
    const statusClass =
      statusLabel === "Ready"
        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
        : statusLabel === "Partial"
          ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
          : "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300";
    return (
      <div
        key={`${asset.source}-${asset.asset_id}`}
        className="grid gap-2 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800 md:grid-cols-5"
      >
        <div className="md:col-span-2">
          <p className="m-0 text-xs uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400">
            Asset
          </p>
          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
            {asset.display_name}
          </p>
          <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
            {asset.asset_id} · {asset.asset_type}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-900/50 dark:text-slate-200 md:col-span-2">
          {asset.linked_metric_count}/{asset.total_metrics} metrics linked
          {asset.missing_metrics.length > 0 && (
            <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
              Missing: {asset.missing_metrics.slice(0, 4).join(", ")}
              {asset.missing_metrics.length > 4
                ? ` +${asset.missing_metrics.length - 4} more`
                : ""}
            </p>
          )}
        </div>
        <div className="flex items-center">
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass}`}
          >
            {statusLabel}
          </span>
        </div>
      </div>
    );
  }, []);

  return (
    <section className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-sm text-slate-600 dark:text-slate-300">
          {isMock
            ? "These are demo assets. Connect a real platform to configure your assets."
            : isReneryo
              ? "Logical AVAROS assets and RENERYO resource coverage are shown separately to avoid data-model confusion."
              : "Manage saved asset mappings used by voice and KPI queries. Use Discover Assets to validate live platform discovery."}
        </p>
        <div className="flex items-center gap-2">
          {supportsDiscover && (
            <button
              type="button"
              className="btn-brand-subtle rounded-lg px-3 py-2 text-sm font-semibold"
              onClick={() => void runDiscovery()}
              disabled={discovering || loading}
            >
              {discovering ? "Discovering..." : "Discover Assets"}
            </button>
          )}
          {!isMock && !isReneryo && (
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

      {discoveryNotice && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-900/40 dark:text-amber-200">
          {discoveryNotice}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
          Loading asset configuration...
        </div>
      ) : null}

      {isMock ? (
        <div className="space-y-2">
          {(discovery?.assets ?? []).map((asset) => (
            <div
              key={asset.asset_id}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <span className="font-semibold">{asset.display_name}</span>
              <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-xs uppercase dark:border-slate-500">
                {asset.asset_type}
              </span>
            </div>
          ))}
        </div>
      ) : isReneryo ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
            Imported assets with metric resources: {reneryoImportedAssets.length}
            <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
              Full coverage: {fullyMappedReneryoAssets}/{reneryoImportedAssets.length || 0}
            </span>
          </div>

          {reneryoImportedAssets.length === 0 ? (
            <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-900/30 dark:text-amber-200">
              No imported metric-resource links found yet. Open the wizard to import mapping_output.json.
            </div>
          ) : (
            <div className="space-y-3">{reneryoImportedAssets.map(renderReneryoCard)}</div>
          )}

          {reneryoDiagnosticAssets.length > 0 && (
            <div className="space-y-2 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="m-0 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400">
                  Developer Diagnostics
                </p>
                <button
                  type="button"
                  className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                  onClick={() => setShowDiagnostics((prev) => !prev)}
                >
                  {showDiagnostics
                    ? "Hide Diagnostics"
                    : `Show Diagnostics (${reneryoDiagnosticAssets.length})`}
                </button>
              </div>
              <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                Upstream RENERYO resources for troubleshooting only. They are excluded from KPI readiness.
              </p>
              {showDiagnostics && (
                <div className="space-y-3">
                  {reneryoDiagnosticAssets.map(renderReneryoCard)}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <AssetManagementRows
          rows={rows}
          isCustomRest={isCustomRest}
          seuOptions={seuOptions}
          onChange={handleChange}
          onDelete={deleteRow}
        />
      )}

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
              ? isMock
                ? "Continue"
                : "Save Mapping & Continue"
              : isReneryo
                ? "Open Wizard"
                : "Save Assets"}
        </button>
      </div>
    </section>
  );
}
